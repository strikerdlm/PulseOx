import asyncio

import pytest

import pulseox.ble as ble


class FakeAsyncClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeClient:
    """`is_connected` returns True for `connected_polls` reads, then False.

    `connected_polls=None` means always connected.
    """

    def __init__(self, connected_polls: int | None) -> None:
        self._polls = connected_polls
        self._count = 0

    @property
    def is_connected(self) -> bool:
        if self._polls is None:
            return True
        self._count += 1
        return self._count <= self._polls


def _patch_ble(monkeypatch: pytest.MonkeyPatch, clients: list[FakeClient]) -> None:
    it = iter(clients)

    async def fake_connect(target, timeout_s, connect_attempts):  # noqa: ANN001
        return next(it)

    async def fake_resolve(client, notify_uuids, *, auto_notify, on_services, timeout_s):  # noqa: ANN001
        return ["0000fff6-0000-1000-8000-00805f9b34fb"]

    async def fake_subscribe(client, uuids, handler, timeout_s):  # noqa: ANN001
        return (list(uuids), [])

    async def fake_stop(client, subscribed, timeout_s):  # noqa: ANN001
        return []

    async def fake_disconnect(client, timeout_s):  # noqa: ANN001
        return None

    async def fake_scan(address, timeout_s):  # noqa: ANN001
        return object()

    monkeypatch.setattr(ble, "_connect_client", fake_connect)
    monkeypatch.setattr(ble, "_resolve_notify_uuids", fake_resolve)
    monkeypatch.setattr(ble, "_subscribe_notifications", fake_subscribe)
    monkeypatch.setattr(ble, "_stop_notifications", fake_stop)
    monkeypatch.setattr(ble, "_disconnect_quietly", fake_disconnect)
    monkeypatch.setattr(ble, "scan_for_device", fake_scan)


def test_stream_duration_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeAsyncClock()
    _patch_ble(monkeypatch, [FakeClient(connected_polls=None)])

    result = asyncio.run(
        ble.stream_notifications(
            "AA:BB:CC:DD:EE:FF",
            notify_uuids=["0000fff6-0000-1000-8000-00805f9b34fb"],
            run_seconds=3.0,
            max_notifications=0,
            poll_interval=0.2,
            timeout_s=1.0,
            on_payload=lambda s, d: None,
            reconnect=True,
            max_reconnect_attempts=3,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.ended_reason == "deadline"
    assert clock.now >= 3.0
    assert result.reconnects == 0


def test_stream_reconnects_after_drop(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeAsyncClock()
    # client1 drops after 2 connectivity polls; client2 stays up to the deadline.
    _patch_ble(
        monkeypatch,
        [FakeClient(connected_polls=2), FakeClient(connected_polls=None)],
    )
    flushes = {"n": 0}

    result = asyncio.run(
        ble.stream_notifications(
            "AA:BB:CC:DD:EE:FF",
            notify_uuids=["0000fff6-0000-1000-8000-00805f9b34fb"],
            run_seconds=5.0,
            max_notifications=0,
            poll_interval=0.2,
            timeout_s=1.0,
            on_payload=lambda s, d: None,
            reconnect=True,
            max_reconnect_attempts=3,
            on_disconnect=lambda: flushes.__setitem__("n", flushes["n"] + 1),
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.reconnects == 1
    assert result.ended_reason == "deadline"
    assert flushes["n"] == 1
