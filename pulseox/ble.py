from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError


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


@dataclass(frozen=True, slots=True)
class NotifyFailure:
    uuid: str
    error: str


@dataclass(frozen=True, slots=True)
class NotifyResult:
    subscribed: tuple[str, ...]
    failed: tuple[NotifyFailure, ...]


OnPayload = Callable[[object, bytes], None]


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


async def scan_devices(timeout_s: float) -> list[DeviceInfo]:
    """Scan for BLE devices with a finite timeout."""
    _require_positive(timeout_s, "timeout_s")
    discovery_timeout = timeout_s
    op_timeout = timeout_s + 2.0

    # Bleak's typing coverage varies across versions. Treat it as an untyped
    # boundary and cast the result to our expected structure.
    scanner: Any = BleakScanner
    discovered_any = await asyncio.wait_for(
        scanner.discover(timeout=discovery_timeout, return_adv=True),
        timeout=op_timeout,
    )
    discovered = cast(dict[str, tuple[BLEDevice, AdvertisementData]], discovered_any)

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


async def _connect_client(address: str, timeout_s: float, connect_attempts: int) -> BleakClient:
    if connect_attempts <= 0:
        raise ValueError("connect_attempts must be positive")

    last_exc: Exception | None = None
    for attempt in range(1, connect_attempts + 1):
        client = BleakClient(address)
        client_any = cast(Any, client)
        try:
            await asyncio.wait_for(client_any.connect(), timeout=timeout_s)
            return client
        except Exception as exc:
            last_exc = exc
            await _disconnect_quietly(client, timeout_s)
            if attempt >= connect_attempts or not _should_retry_connect(exc):
                raise
            # Bounded backoff to reduce immediate reconnect failures.
            await asyncio.sleep(min(0.25 * attempt, 1.0))

    if last_exc is None:
        raise RuntimeError("Connect attempts exhausted")
    raise RuntimeError("Connect attempts exhausted") from last_exc


async def _get_services_info(client: BleakClient, timeout_s: float) -> list[ServiceInfo]:
    client_any = cast(Any, client)
    services_any = await asyncio.wait_for(client_any.get_services(), timeout=timeout_s)
    services_list = list(services_any)
    services_like = cast(Sequence[_BleakServiceLike], services_list)
    return _as_service_info(services_like)


async def fetch_services(address: str, timeout_s: float) -> list[ServiceInfo]:
    """Connect and fetch GATT services with timeouts."""
    _require_positive(timeout_s, "timeout_s")
    if not address:
        raise ValueError("address must be non-empty")

    client = await _connect_client(address, timeout_s, connect_attempts=3)
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


async def _run_stream_loop(
    run_seconds: float,
    poll_interval: float,
    max_notifications: int,
    get_count: Callable[[], int],
) -> None:
    max_iters = max(1, int(run_seconds / poll_interval) + 1)
    for _ in range(max_iters):
        await asyncio.sleep(poll_interval)
        if get_count() >= max_notifications:
            break


def _validate_stream_args(
    address: str,
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
    if max_notifications <= 0:
        raise ValueError("max_notifications must be positive")
    if not address:
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
        effective_notify_uuids = extract_notify_uuids(services_info)
    else:
        _require_nonempty(notify_uuids, "notify_uuids")
        effective_notify_uuids = list(notify_uuids)

    if not effective_notify_uuids:
        raise ValueError("No notify UUIDs available to subscribe")

    return effective_notify_uuids


def _require_subscribed(subscribed: Sequence[str]) -> None:
    if not subscribed:
        raise RuntimeError("Failed to subscribe to any notify characteristics")


def _raise_on_stop_errors(stop_errors: Sequence[str], caught: Exception | None) -> None:
    if stop_errors and caught is None:
        raise RuntimeError("Failed to stop notify: " + "; ".join(stop_errors))


async def stream_notifications(
    address: str,
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
) -> NotifyResult:
    """
    Subscribe to notifications and stream for a bounded duration/count.

    Notes:
        On Windows/WinRT, some devices can fail service discovery with a transient
        "Unreachable" error, especially when reconnecting quickly. This function
        optionally retries the connection (bounded) and can print services from the
        active connection to avoid connect/disconnect/connect sequences.

    Raises:
        ValueError: invalid arguments
        RuntimeError: if no notifications could be subscribed
    """
    _validate_stream_args(
        address,
        run_seconds,
        max_notifications,
        poll_interval,
        timeout_s,
        connect_attempts,
    )

    count = 0

    def handler(sender: object, data: bytearray) -> None:
        nonlocal count
        count += 1
        on_payload(sender, bytes(data))

    def get_count() -> int:
        return count

    caught: Exception | None = None
    subscribed: list[str] = []

    client = await _connect_client(address, timeout_s, connect_attempts=connect_attempts)
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
        _require_subscribed(subscribed)

        await _run_stream_loop(run_seconds, poll_interval, max_notifications, get_count)
    except Exception as exc:
        caught = exc
        raise
    finally:
        stop_errors = await _stop_notifications(client, subscribed, timeout_s)
        await _disconnect_quietly(client, timeout_s)
        _raise_on_stop_errors(stop_errors, caught)

    return NotifyResult(subscribed=tuple(subscribed), failed=tuple(failures))
