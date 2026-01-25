from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import TextIO

from bleak.backends.device import BLEDevice

from pulseox.ble import (
    BleConnectError,
    DeviceInfo,
    ServiceInfo,
    fetch_services,
    scan_devices,
    scan_for_device,
    stream_notifications,
)
from pulseox.decode import decode_notification, hexlify
from pulseox.logging_utils import configure_logging
from pulseox.record import PulseOxCsvRecorder, open_csv_path

# NOTE: Keep CLI output print-based for UX, but use logging for debug/tracebacks.
logger = logging.getLogger(__name__)

# Default notify characteristic UUID for the tested oximeter.
#
# Observed GATT for the device used during development:
# - Service 0000fff0-0000-1000-8000-00805f9b34fb
# - Char   0000fff6-0000-1000-8000-00805f9b34fb  (notify)
# - Char   0000fff7-0000-1000-8000-00805f9b34fb  (write-without-response)
#
# Some other consumer oximeters expose UART-like characteristics; keep the UUID
# as a documented option but do not use it as the default.
LPOW_A340B_LK_NOTIFY_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"
ISSC_UART_LIKE_TX_UUID = "49535343-1e4d-4bd9-ba61-23c647249616"

DEFAULT_NOTIFY_UUID = LPOW_A340B_LK_NOTIFY_UUID


def _print_devices(devices: Sequence[DeviceInfo], *, sort_rssi: bool) -> list[DeviceInfo]:
    ordered = list(devices)
    if sort_rssi:
        ordered.sort(
            key=lambda d: (d.rssi is not None, d.rssi if d.rssi is not None else -9999),
            reverse=True,
        )

    for idx, dev in enumerate(ordered):
        name = dev.name or ""
        uuids = list(dev.advertised_uuids)
        rssi = f"{dev.rssi}dBm" if dev.rssi is not None else "?"
        print(f"[{idx}] {dev.address}  name={name!r}  rssi={rssi}  adv_uuids={uuids}")

    return ordered


def _print_gatt(services: Sequence[ServiceInfo]) -> None:
    print("\n== GATT services/characteristics ==")
    for svc in services:
        desc = f" ({svc.description})" if svc.description else ""
        print(f"- Service {svc.uuid}{desc}")
        for ch in svc.characteristics:
            props = ",".join(ch.properties)
            print(f"  - Char {ch.uuid}  props={props}")


def _choose_device(devices: Sequence[DeviceInfo]) -> str | None:
    if not devices:
        print("No BLE devices found.")
        return None
    choice = input("\nSelect device index to connect (or blank to quit): ").strip()
    if not choice:
        return None
    if not choice.isdigit():
        raise ValueError("Selection must be a numeric index")
    idx = int(choice)
    if idx < 0 or idx >= len(devices):
        raise ValueError("Selection out of range")
    return devices[idx].address


def _format_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _format_sender(sender: object) -> str:
    """Best-effort formatting for Bleak notification sender across backends."""
    if isinstance(sender, int):
        return f"0x{sender:04x}"

    handle = getattr(sender, "handle", None)
    if isinstance(handle, int):
        return f"0x{handle:04x}"

    uuid = getattr(sender, "uuid", None)
    if isinstance(uuid, str) and uuid:
        return uuid

    return str(sender)


def _make_notify_handler(
    *,
    recorder: PulseOxCsvRecorder | None,
    quiet: bool,
) -> Callable[[object, bytes], None]:
    def on_payload(sender: object, data: bytes) -> None:
        if recorder is not None:
            recorder.on_notification(sender=sender, data=data)

        if quiet:
            return

        ts = _format_timestamp()
        sender_str = _format_sender(sender)
        print(f"\n[{ts}] from={sender_str} len={len(data)} data={hexlify(data)}")
        decoded, remainder = decode_notification(data)
        for frame in decoded:
            tag = "OK" if frame.plausible else "?"
            print(
                "  "
                f"SpO2={frame.spo2_percent}%  "
                f"Pulse={frame.pulse_bpm}bpm  "
                f"PI={frame.perfusion_index}  "
                f"[{tag}]"
            )
        if remainder:
            print(f"  remainder={hexlify(remainder)}")

    return on_payload


def _wants_listen(args: argparse.Namespace) -> bool:
    return bool(args.auto_notify or args.notify_uuid or args.csv)


async def _resolve_device(args: argparse.Namespace) -> BLEDevice | None:
    """Resolve address to a BLEDevice via scan.

    On Linux (BlueZ), BleakClient requires the device to be known to D-Bus.
    We always scan to find the BLEDevice, even when --address is provided.
    """
    address = args.address

    if args.scan or args.scan_only or not address:
        devices = await scan_devices(timeout_s=args.timeout)
        devices = _print_devices(devices, sort_rssi=args.sort_rssi)

        if args.scan_only:
            return None

        if not address:
            selected = _choose_device(devices)
            if not selected:
                return None
            address = selected

    if not address:
        raise ValueError("address is required")

    # On Linux (BlueZ), we must scan to get a BLEDevice object that BlueZ knows.
    # Even if we just scanned above, do a targeted scan to get the raw BLEDevice.
    logger.debug("Scanning for device %s to register with BlueZ...", address)
    print(f"Scanning for {address}...")
    device = await scan_for_device(address, timeout_s=args.timeout)
    if device is None:
        print(
            f"\nDevice {address} not found during pre-connect scan.\n"
            "Make sure the device is awake/advertising and try again."
        )
        return None
    logger.debug("Found device: %s", device)
    return device


async def _maybe_print_gatt_only(
    args: argparse.Namespace,
    *,
    device: BLEDevice,
) -> bool:
    if args.print_gatt and not _wants_listen(args):
        services = await fetch_services(device, timeout_s=args.timeout)
        _print_gatt(services)
        return True
    return False


def _compute_notify_uuids(args: argparse.Namespace) -> list[str]:
    if args.auto_notify:
        return []
    return list(args.notify_uuid or [DEFAULT_NOTIFY_UUID])


def _open_csv_recorder(args: argparse.Namespace) -> tuple[PulseOxCsvRecorder | None, TextIO | None]:
    if not args.csv:
        return None, None

    sample_hz = 1.0 if args.sample_hz is None else float(args.sample_hz)
    opened = open_csv_path(args.csv, append=args.csv_append, overwrite=args.csv_overwrite)
    recorder = PulseOxCsvRecorder(
        opened.file,
        write_header=opened.write_header,
        sample_hz=sample_hz,
        include_implausible=args.include_implausible,
        flush_every=args.csv_flush_every,
    )
    return recorder, opened.file


async def _run(args: argparse.Namespace) -> None:
    device = await _resolve_device(args)
    if device is None:
        return

    if await _maybe_print_gatt_only(args, device=device):
        return

    on_services = _print_gatt if (args.print_gatt or args.auto_notify) else None
    notify_uuids = _compute_notify_uuids(args)

    recorder, csv_file = _open_csv_recorder(args)

    try:
        on_payload = _make_notify_handler(recorder=recorder, quiet=args.quiet)
        result = await stream_notifications(
            device,
            notify_uuids=notify_uuids,
            auto_notify=args.auto_notify,
            on_services=on_services,
            run_seconds=args.duration,
            max_notifications=args.max_notifications,
            poll_interval=args.poll_interval,
            timeout_s=args.timeout,
            connect_attempts=args.connect_attempts,
            on_payload=on_payload,
        )
        if result.failed:
            print("\nSome subscriptions failed:")
            for failure in result.failed:
                print(f"- {failure.uuid}: {failure.error}")
    finally:
        if recorder is not None:
            recorder.close()
        if csv_file is not None:
            csv_file.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BLE reader for LPOW A340B (best-effort)")
    parser.add_argument(
        "--log-level",
        default=None,
        help=(
            "Logging level for debug output (overrides PULSEOX_LOG_LEVEL). "
            "One of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Shortcut for debug logging (sets log level to DEBUG unless --log-level is set).",
    )
    parser.add_argument("--scan", action="store_true", help="Scan and list nearby BLE devices")
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Scan and print devices, then exit without connecting",
    )
    parser.add_argument(
        "--sort-rssi",
        action="store_true",
        help="When scanning, sort devices by strongest RSSI first",
    )
    parser.add_argument("--timeout", type=float, default=8.0, help="Timeout seconds for BLE ops")
    parser.add_argument(
        "--connect-attempts",
        type=int,
        default=3,
        help="Number of bounded BLE connect attempts before failing",
    )
    parser.add_argument("--address", help="BLE address (or UUID on macOS)")
    parser.add_argument(
        "--notify-uuid",
        action="append",
        default=[],
        help=(
            "Characteristic UUID to notify on "
            f"(default {DEFAULT_NOTIFY_UUID}; "
            f"UART-like TX example {ISSC_UART_LIKE_TX_UUID})"
        ),
    )
    parser.add_argument(
        "--auto-notify",
        action="store_true",
        help="Subscribe to all notify/indicate characteristics",
    )
    parser.add_argument(
        "--print-gatt",
        action="store_true",
        help="Print GATT services/characteristics (exits unless notify options are set)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Seconds to listen for notifications (bounded)",
    )
    parser.add_argument(
        "--max-notifications",
        type=int,
        default=1000,
        help="Maximum notifications to process (bounded)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.2,
        help="Polling interval for bounded loop, seconds",
    )

    parser.add_argument(
        "--csv",
        help="Write decoded samples to CSV at this path",
    )
    csv_mode = parser.add_mutually_exclusive_group()
    csv_mode.add_argument(
        "--csv-append",
        action="store_true",
        help="Append to --csv if it exists (write header only if file is empty)",
    )
    csv_mode.add_argument(
        "--csv-overwrite",
        action="store_true",
        help="Overwrite --csv if it exists",
    )
    parser.add_argument(
        "--csv-flush-every",
        type=int,
        default=10,
        help="Flush CSV every N written rows (bounded)",
    )
    parser.add_argument(
        "--sample-hz",
        type=float,
        default=None,
        help="Max CSV samples per second; 0 disables rate limit. Default: 1.0 when --csv is set",
    )
    parser.add_argument(
        "--include-implausible",
        action="store_true",
        help="Include implausible frames in CSV output",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-notification printing (recommended for CSV recording)",
    )

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        resolved_level = configure_logging(level=args.log_level, debug=bool(args.debug))
    except ValueError as e:
        raise SystemExit(str(e)) from e
    logger.debug("Logging initialized (level=%s).", resolved_level)
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except BleConnectError as e:
        # One concise, actionable message for the common "advertises but won't connect" case.
        logger.debug("BLE connect error details: %s", e, exc_info=True)
        print(
            "\nERROR: Could not connect to BLE device.\n"
            f"{e}\n\n"
            "Troubleshooting:\n"
            "- Make sure the device is awake and not already connected to a phone/OS.\n"
            "- Move closer; weak signal can advertise but fail to connect.\n"
            "- Try increasing timeouts/retries:\n"
            "  python -m pulseox.cli --address <ADDR> --timeout 20 --connect-attempts 5 ...\n"
            "- On Linux, ensure Bluetooth is unblocked and you have permissions (often group `bluetooth`).\n"
            "- If it still fails, run `--scan --sort-rssi` to confirm the address is stable.\n"
        )
        raise SystemExit(2) from None
    except Exception:
        # Avoid duplicate tracebacks: log one traceback (in debug) and exit.
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Unhandled exception in CLI.")
        else:
            logger.error(
                "Unhandled exception in CLI. Re-run with --debug for a full traceback."
            )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
