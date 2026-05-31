from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

from pulseox.streaming import (
    NotifyFailure,
    OpenedSession,
    StreamResult,
    run_until_deadline,
    supervise_stream,
)


class BleConnectError(RuntimeError):
    """Raised when a BLE connection attempt fails after bounded retries."""

    def __init__(
        self,
        *,
        address: str,
        timeout_s: float,
        connect_attempts: int,
        attempt: int,
        underlying: BaseException,
    ) -> None:
        self.address = address
        self.timeout_s = timeout_s
        self.connect_attempts = connect_attempts
        self.attempt = attempt
        self.underlying = underlying

        msg = (
            "BLE connect failed.\n"
            f"Address: {address}\n"
            f"Attempt: {attempt}/{connect_attempts}\n"
            f"Timeout: {timeout_s:.3f}s\n"
            f"Underlying: {underlying.__class__.__name__}: {underlying}"
        )
        super().__init__(msg)


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    address: str
    name: str | None
    rssi: int | None
    advertised_uuids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CharacteristicInfo:
    uuid: str
    properties: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ServiceInfo:
    uuid: str
    description: str
    characteristics: tuple[CharacteristicInfo, ...]


OnPayload = Callable[[object, bytes], None]

# Standard GATT characteristic that is not used for oximeter data, and on some
# Windows/WinRT setups may reject subscriptions with Access Denied.
GATT_SERVICE_CHANGED_UUID = "00002a05-0000-1000-8000-00805f9b34fb"


def _require_positive(value: float, name: str) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _is_unreachable_error(exc: BaseException) -> bool:
    msg = str(exc)
    return "unreachable" in msg.lower()


def _should_retry_connect(exc: BaseException) -> bool:
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, BleakError) and _is_unreachable_error(exc):
        return True
    return False


async def _disconnect_quietly(client: BleakClient, timeout_s: float) -> None:
    """Best-effort disconnect to reduce WinRT callback noise on teardown."""
    try:
        await asyncio.wait_for(client.disconnect(), timeout=timeout_s)
    except Exception:
        return


class _BleakCharacteristicLike(Protocol):
    uuid: str
    properties: Sequence[str]


class _BleakServiceLike(Protocol):
    uuid: str
    description: str | None
    characteristics: Sequence[_BleakCharacteristicLike]


def _as_service_info(services: Sequence[_BleakServiceLike]) -> list[ServiceInfo]:
    svc_list: list[ServiceInfo] = []
    for svc in services:
        chars: list[CharacteristicInfo] = []
        for ch in svc.characteristics:
            chars.append(CharacteristicInfo(uuid=ch.uuid, properties=tuple(ch.properties)))
        svc_list.append(
            ServiceInfo(
                uuid=svc.uuid,
                description=svc.description or "",
                characteristics=tuple(chars),
            )
        )
    return svc_list


def _require_nonempty(seq: Sequence[str], name: str) -> Sequence[str]:
    if not seq:
        raise ValueError(f"{name} must not be empty")
    return seq


async def _scan_raw(timeout_s: float) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
    """Low-level scan returning raw Bleak device/adv map."""
    _require_positive(timeout_s, "timeout_s")
    op_timeout = timeout_s + 2.0
    scanner: Any = BleakScanner
    discovered_any = await asyncio.wait_for(
        scanner.discover(timeout=timeout_s, return_adv=True),
        timeout=op_timeout,
    )
    return cast(dict[str, tuple[BLEDevice, AdvertisementData]], discovered_any)


async def scan_devices(timeout_s: float) -> list[DeviceInfo]:
    """Scan for BLE devices with a finite timeout."""
    discovered = await _scan_raw(timeout_s)

    results: list[DeviceInfo] = []
    for address, (dev, adv) in discovered.items():
        name = dev.name or adv.local_name
        results.append(
            DeviceInfo(
                address=address,
                name=name,
                rssi=adv.rssi,
                advertised_uuids=tuple(adv.service_uuids),
            )
        )
    return results


async def scan_for_device(address: str, timeout_s: float) -> BLEDevice | None:
    """Scan and return the BLEDevice for a specific address (case-insensitive).

    On Linux (BlueZ), BleakClient requires the device to be known to the D-Bus
    object manager. If you only have an address string from a previous session,
    the device won't be found. This function scans and returns the BLEDevice
    object, which can then be passed to BleakClient for a successful connect.

    Returns:
        The BLEDevice if found, or None if not discovered within timeout.
    """
    if not address:
        raise ValueError("address must be non-empty")
    _require_positive(timeout_s, "timeout_s")

    target = address.lower()
    discovered = await _scan_raw(timeout_s)
    for addr, (dev, _adv) in discovered.items():
        if addr.lower() == target:
            return dev
    return None


async def _connect_client(
    address_or_device: str | BLEDevice,
    timeout_s: float,
    connect_attempts: int,
) -> BleakClient:
    """Connect to a BLE device with bounded retries.

    Args:
        address_or_device: Either a string address or a BLEDevice from a scan.
            On Linux (BlueZ), passing a BLEDevice is required for reliable
            connections; passing a string alone may fail with "device not found."
        timeout_s: Timeout per connection attempt.
        connect_attempts: Max number of bounded retries.
    """
    if connect_attempts <= 0:
        raise ValueError("connect_attempts must be positive")

    # Normalize address for error messages
    if isinstance(address_or_device, str):
        display_address = address_or_device.lower()
    else:
        display_address = address_or_device.address.lower()

    for attempt in range(1, connect_attempts + 1):
        client = BleakClient(address_or_device)
        client_any = cast(Any, client)
        try:
            await asyncio.wait_for(client_any.connect(), timeout=timeout_s)
            return client
        except Exception as exc:
            await _disconnect_quietly(client, timeout_s)
            if attempt >= connect_attempts or not _should_retry_connect(exc):
                raise BleConnectError(
                    address=display_address,
                    timeout_s=timeout_s,
                    connect_attempts=connect_attempts,
                    attempt=attempt,
                    underlying=exc,
                ) from exc
            # Bounded backoff to reduce immediate reconnect failures.
            await asyncio.sleep(min(0.25 * attempt, 1.0))

    # Defensive fallback: the loop is exhaustive.
    raise RuntimeError("Connect attempts exhausted unexpectedly")


async def _get_services_info(client: BleakClient, timeout_s: float) -> list[ServiceInfo]:
    client_any = cast(Any, client)
    services_any = await asyncio.wait_for(client_any.get_services(), timeout=timeout_s)
    services_list = list(services_any)
    services_like = cast(Sequence[_BleakServiceLike], services_list)
    return _as_service_info(services_like)


def _get_address(address_or_device: str | BLEDevice) -> str:
    """Extract address string for validation/logging."""
    if isinstance(address_or_device, str):
        return address_or_device
    return address_or_device.address


async def fetch_services(
    address_or_device: str | BLEDevice,
    timeout_s: float,
) -> list[ServiceInfo]:
    """Connect and fetch GATT services with timeouts.

    Args:
        address_or_device: Either a string address or a BLEDevice from a scan.
            On Linux (BlueZ), passing a BLEDevice is more reliable.
        timeout_s: Timeout for BLE operations.
    """
    _require_positive(timeout_s, "timeout_s")
    addr = _get_address(address_or_device)
    if not addr:
        raise ValueError("address must be non-empty")

    client = await _connect_client(address_or_device, timeout_s, connect_attempts=3)
    try:
        return await _get_services_info(client, timeout_s)
    finally:
        await _disconnect_quietly(client, timeout_s)


def extract_notify_uuids(services: Sequence[ServiceInfo]) -> list[str]:
    """Return characteristic UUIDs that support notify/indicate."""
    notify_uuids: list[str] = []
    for svc in services:
        for ch in svc.characteristics:
            props = {p.lower() for p in ch.properties}
            if "notify" in props or "indicate" in props:
                notify_uuids.append(ch.uuid)
    return notify_uuids


def _effective_auto_notify_uuids(services: Sequence[ServiceInfo]) -> list[str]:
    """Return auto-notify UUIDs after excluding non-data characteristics."""
    uuids = extract_notify_uuids(services)
    return [u for u in uuids if u.lower() != GATT_SERVICE_CHANGED_UUID]


def _format_uuid_list(uuids: Sequence[str], *, max_items: int) -> str:
    """Format a potentially-long UUID list for error messages."""
    if max_items <= 0:
        raise ValueError("max_items must be positive")

    total = len(uuids)
    if total == 0:
        return "[]"

    shown = list(uuids[:max_items])
    shown_str = ", ".join(repr(u) for u in shown)

    if total > max_items:
        return f"[{shown_str}, ... (+{total - max_items} more)]"

    return f"[{shown_str}]"


def _format_subscribe_failures(failures: Sequence[NotifyFailure], *, max_items: int) -> str:
    """Format notify subscription failures for error messages."""
    if max_items <= 0:
        raise ValueError("max_items must be positive")

    if not failures:
        return "[]"

    shown = list(failures[:max_items])
    parts = [f"{f.uuid}: {f.error}" for f in shown]
    if len(failures) > max_items:
        parts.append(f"... (+{len(failures) - max_items} more)")
    return "; ".join(parts)


async def _subscribe_notifications(
    client: BleakClient,
    notify_uuids: Sequence[str],
    handler: Callable[[object, bytearray], None],
    timeout_s: float,
) -> tuple[list[str], list[NotifyFailure]]:
    subscribed: list[str] = []
    failures: list[NotifyFailure] = []

    client_any = cast(Any, client)
    for uuid in notify_uuids:
        try:
            await asyncio.wait_for(client_any.start_notify(uuid, handler), timeout=timeout_s)
            subscribed.append(uuid)
        except Exception as exc:
            failures.append(NotifyFailure(uuid=uuid, error=repr(exc)))

    return subscribed, failures


async def _stop_notifications(
    client: BleakClient,
    subscribed: Sequence[str],
    timeout_s: float,
) -> list[str]:
    stop_errors: list[str] = []
    client_any = cast(Any, client)
    for uuid in subscribed:
        try:
            await asyncio.wait_for(client_any.stop_notify(uuid), timeout=timeout_s)
        except Exception as exc:
            stop_errors.append(f"{uuid}: {exc!r}")
    return stop_errors


def _validate_stream_args(
    address_or_device: str | BLEDevice,
    run_seconds: float,
    max_notifications: int,
    poll_interval: float,
    timeout_s: float,
    connect_attempts: int,
) -> None:
    _require_positive(run_seconds, "run_seconds")
    _require_positive(poll_interval, "poll_interval")
    _require_positive(timeout_s, "timeout_s")
    if connect_attempts <= 0:
        raise ValueError("connect_attempts must be positive")
    if max_notifications < 0:
        raise ValueError("max_notifications must be >= 0")
    addr = _get_address(address_or_device)
    if not addr:
        raise ValueError("address must be non-empty")


async def _resolve_notify_uuids(
    client: BleakClient,
    notify_uuids: Sequence[str],
    *,
    auto_notify: bool,
    on_services: Callable[[Sequence[ServiceInfo]], None] | None,
    timeout_s: float,
) -> list[str]:
    services_info: list[ServiceInfo] | None = None
    if auto_notify or on_services is not None:
        services_info = await _get_services_info(client, timeout_s)
        if on_services is not None:
            on_services(services_info)

    if auto_notify:
        if services_info is None:
            raise RuntimeError("services_info must be available for auto_notify")
        effective_notify_uuids = _effective_auto_notify_uuids(services_info)
    else:
        _require_nonempty(notify_uuids, "notify_uuids")
        effective_notify_uuids = list(notify_uuids)

    if not effective_notify_uuids:
        raise ValueError("No notify UUIDs available to subscribe")

    return effective_notify_uuids


def _require_subscribed(
    subscribed: Sequence[str],
    *,
    address: str,
    attempted: Sequence[str],
    failures: Sequence[NotifyFailure],
    available_notify_uuids: Sequence[str] | None,
    services_error: Exception | None,
) -> None:
    if subscribed:
        return

    if not address:
        raise ValueError("address must be non-empty")

    msg_lines = [
        "Failed to subscribe to any notify characteristics.",
        f"Address: {address}",
        f"Attempted UUIDs: {_format_uuid_list(attempted, max_items=8)}",
        f"Errors: {_format_subscribe_failures(failures, max_items=8)}",
    ]

    if available_notify_uuids is not None:
        msg_lines.append(
            "Available notify/indicate UUIDs from service discovery: "
            + _format_uuid_list(available_notify_uuids, max_items=12)
        )
    elif services_error is not None:
        msg_lines.append(f"Service discovery after failure also failed: {services_error!r}")

    msg_lines.append(
        "Hint: run with --print-gatt to inspect the device GATT; "
        "if needed, pass --notify-uuid explicitly or use --auto-notify."
    )

    raise RuntimeError("\n".join(msg_lines))


async def _open_subscribed_session(
    *,
    target: str | BLEDevice,
    notify_uuids: Sequence[str],
    handler: Callable[[object, bytearray], None],
    auto_notify: bool,
    on_services: Callable[[Sequence[ServiceInfo]], None] | None,
    timeout_s: float,
    connect_attempts: int,
    display_address: str,
) -> OpenedSession:
    """Connect, resolve UUIDs, and subscribe; return a live OpenedSession.

    Disconnects best-effort and re-raises if subscription cannot be established.
    """
    client = await _connect_client(target, timeout_s, connect_attempts=connect_attempts)
    try:
        effective_notify_uuids = await _resolve_notify_uuids(
            client,
            notify_uuids,
            auto_notify=auto_notify,
            on_services=on_services,
            timeout_s=timeout_s,
        )
        subscribed, failures = await _subscribe_notifications(
            client, effective_notify_uuids, handler, timeout_s
        )

        available_notify_uuids: list[str] | None = None
        services_error: Exception | None = None
        if not subscribed:
            try:
                services_info = await _get_services_info(client, timeout_s)
                available_notify_uuids = _effective_auto_notify_uuids(services_info)
            except Exception as exc:
                services_error = exc

        _require_subscribed(
            subscribed,
            address=display_address,
            attempted=effective_notify_uuids,
            failures=failures,
            available_notify_uuids=available_notify_uuids,
            services_error=services_error,
        )
    except Exception:
        await _disconnect_quietly(client, timeout_s)
        raise

    return OpenedSession(
        subscribed=tuple(subscribed),
        failed=tuple(failures),
        handle=client,
    )


async def stream_notifications(
    address_or_device: str | BLEDevice,
    notify_uuids: Sequence[str],
    run_seconds: float,
    max_notifications: int,
    poll_interval: float,
    timeout_s: float,
    on_payload: OnPayload,
    *,
    auto_notify: bool = False,
    on_services: Callable[[Sequence[ServiceInfo]], None] | None = None,
    connect_attempts: int = 3,
    reconnect: bool = True,
    max_reconnect_attempts: int = 5,
    on_disconnect: Callable[[], None] | None = None,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> StreamResult:
    """Subscribe and stream for a bounded duration, reconnecting on drops.

    ``run_seconds`` (wall-clock) is the authoritative bound. ``max_notifications``
    is an opt-in safety ceiling on *raw* notifications; ``0`` disables it. On a
    link drop with ``reconnect=True``, the recorder is flushed (``on_disconnect``),
    the device is re-scanned, and streaming resumes against the remaining time.

    Args:
        address_or_device: Either a string address or a BLEDevice from a scan.
            On Linux (BlueZ), passing a BLEDevice is more reliable because BlueZ
            requires the device to be known to the D-Bus object manager.

    Raises:
        ValueError: invalid arguments
        RuntimeError: if no notifications could be subscribed on the first connect
    """
    _validate_stream_args(
        address_or_device,
        run_seconds,
        max_notifications,
        poll_interval,
        timeout_s,
        connect_attempts,
    )
    if max_reconnect_attempts <= 0:
        raise ValueError("max_reconnect_attempts must be positive")

    display_address = _get_address(address_or_device)
    original_target = address_or_device

    count = 0

    def handler(sender: object, data: bytearray) -> None:
        nonlocal count
        count += 1
        on_payload(sender, bytes(data))

    def get_count() -> int:
        return count

    first_open = {"done": False}

    async def _resolve_target() -> str | BLEDevice:
        # First connect reuses the caller-provided target (cli already scanned).
        # Reconnects re-scan because BlueZ needs a fresh BLEDevice object.
        if not first_open["done"]:
            return original_target
        dev = await scan_for_device(display_address, timeout_s=timeout_s)
        if dev is None:
            raise BleakError(f"device {display_address} not found on reconnect scan")
        return dev

    async def open_session() -> OpenedSession:
        target = await _resolve_target()
        session = await _open_subscribed_session(
            target=target,
            notify_uuids=notify_uuids,
            handler=handler,
            auto_notify=auto_notify,
            on_services=on_services if not first_open["done"] else None,
            timeout_s=timeout_s,
            connect_attempts=connect_attempts,
            display_address=display_address,
        )
        first_open["done"] = True
        return session

    async def run_session(session: OpenedSession, deadline: float) -> str:
        client = cast(BleakClient, session.handle)
        return await run_until_deadline(
            deadline=deadline,
            poll_interval=poll_interval,
            max_notifications=max_notifications,
            get_count=get_count,
            is_connected=lambda: bool(client.is_connected),
            monotonic_fn=monotonic_fn,
            sleep_fn=sleep_fn,
        )

    async def close_session(session: OpenedSession) -> None:
        client = cast(BleakClient, session.handle)
        # Best-effort teardown; a dropped device may error here, which is fine.
        await _stop_notifications(client, session.subscribed, timeout_s)
        await _disconnect_quietly(client, timeout_s)

    return await supervise_stream(
        run_seconds=run_seconds,
        reconnect=reconnect,
        max_reconnect_attempts=max_reconnect_attempts,
        open_session=open_session,
        run_session=run_session,
        close_session=close_session,
        on_disconnect=on_disconnect,
        monotonic_fn=monotonic_fn,
        sleep_fn=sleep_fn,
    )
