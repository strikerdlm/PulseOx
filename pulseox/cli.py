from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import TextIO

from pulseox.ble import (
    DeviceInfo,
    ServiceInfo,
    fetch_services,
    scan_devices,
    stream_notifications,
)
from pulseox.decode import decode_payload, hexlify
from pulseox.record import PulseOxCsvRecorder, open_csv_path

UART_TX_UUID = "49535343-1E4D-4BD9-BA61-23C647249616"


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
        decoded, remainder = decode_payload(data)
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


async def _resolve_address(args: argparse.Namespace) -> str | None:
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

    return address


async def _maybe_print_gatt_only(args: argparse.Namespace, *, address: str) -> bool:
    if args.print_gatt and not _wants_listen(args):
        services = await fetch_services(address=address, timeout_s=args.timeout)
        _print_gatt(services)
        return True
    return False


def _compute_notify_uuids(args: argparse.Namespace) -> list[str]:
    if args.auto_notify:
        return []
    return list(args.notify_uuid or [UART_TX_UUID])


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
    address = await _resolve_address(args)
    if address is None:
        return

    if await _maybe_print_gatt_only(args, address=address):
        return

    on_services = _print_gatt if (args.print_gatt or args.auto_notify) else None
    notify_uuids = _compute_notify_uuids(args)

    recorder, csv_file = _open_csv_recorder(args)

    try:
        on_payload = _make_notify_handler(recorder=recorder, quiet=args.quiet)
        result = await stream_notifications(
            address=address,
            notify_uuids=notify_uuids,
            auto_notify=args.auto_notify,
            on_services=on_services,
            run_seconds=args.duration,
            max_notifications=args.max_notifications,
            poll_interval=args.poll_interval,
            timeout_s=args.timeout,
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
    parser.add_argument("--address", help="BLE address (or UUID on macOS)")
    parser.add_argument(
        "--notify-uuid",
        action="append",
        default=[],
        help=f"Characteristic UUID to notify on (default {UART_TX_UUID})",
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
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
