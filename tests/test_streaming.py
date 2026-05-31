import asyncio

from pulseox.streaming import (
    OpenedSession,
    run_until_deadline,
    supervise_stream,
)


class FakeAsyncClock:
    """Deterministic clock: monotonic() reads `now`, sleep() advances it."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_run_until_deadline_duration_authoritative_under_flood() -> None:
    clock = FakeAsyncClock()
    reason = asyncio.run(
        run_until_deadline(
            deadline=2.0,
            poll_interval=0.2,
            max_notifications=0,  # disabled
            get_count=lambda: 10_000,  # flood
            is_connected=lambda: True,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert reason == "deadline"
    assert clock.now >= 2.0


def test_run_until_deadline_count_cap_when_set() -> None:
    clock = FakeAsyncClock()
    state = {"n": 0}

    def get_count() -> int:
        state["n"] += 1
        return state["n"] * 3  # 3, 6, 9, ...

    reason = asyncio.run(
        run_until_deadline(
            deadline=100.0,
            poll_interval=0.2,
            max_notifications=5,
            get_count=get_count,
            is_connected=lambda: True,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert reason == "count_cap"


def test_run_until_deadline_detects_disconnect() -> None:
    clock = FakeAsyncClock()
    calls = {"n": 0}

    def is_connected() -> bool:
        calls["n"] += 1
        return calls["n"] < 3

    reason = asyncio.run(
        run_until_deadline(
            deadline=100.0,
            poll_interval=0.2,
            max_notifications=0,
            get_count=lambda: 0,
            is_connected=is_connected,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert reason == "disconnected"


def test_run_until_deadline_stops_on_should_stop() -> None:
    clock = FakeAsyncClock()
    reason = asyncio.run(
        run_until_deadline(
            deadline=100.0,
            poll_interval=0.2,
            max_notifications=0,
            get_count=lambda: 0,
            is_connected=lambda: True,
            should_stop=lambda: True,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert reason == "stopped"


def test_supervise_returns_stopped_as_terminal() -> None:
    clock = FakeAsyncClock()

    async def open_session() -> OpenedSession:
        return OpenedSession(subscribed=("u",), failed=(), handle="c1")

    async def run_session(session: OpenedSession, deadline: float) -> str:
        return "stopped"

    async def close_session(session: OpenedSession) -> None:
        return None

    result = asyncio.run(
        supervise_stream(
            run_seconds=100.0,
            reconnect=True,
            max_reconnect_attempts=3,
            open_session=open_session,
            run_session=run_session,
            close_session=close_session,
            on_disconnect=None,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.ended_reason == "stopped"
    assert result.reconnects == 0


def test_supervise_should_stop_aborts_reconnect() -> None:
    clock = FakeAsyncClock()

    async def open_session() -> OpenedSession:
        return OpenedSession(subscribed=("u",), failed=(), handle="c1")

    async def run_session(session: OpenedSession, deadline: float) -> str:
        return "disconnected"

    async def close_session(session: OpenedSession) -> None:
        return None

    result = asyncio.run(
        supervise_stream(
            run_seconds=100.0,
            reconnect=True,
            max_reconnect_attempts=3,
            open_session=open_session,
            run_session=run_session,
            close_session=close_session,
            on_disconnect=None,
            should_stop=lambda: True,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.ended_reason == "stopped"


def test_supervise_reconnects_once_then_finishes_at_deadline() -> None:
    clock = FakeAsyncClock()
    events: list[str] = []
    sessions = iter(
        [
            OpenedSession(subscribed=("uuidA",), failed=(), handle="c1"),
            OpenedSession(subscribed=("uuidA",), failed=(), handle="c2"),
        ]
    )
    reasons = iter(["disconnected", "deadline"])
    flushes = {"n": 0}

    async def open_session() -> OpenedSession:
        s = next(sessions)
        events.append(f"open:{s.handle}")
        return s

    async def run_session(session: OpenedSession, deadline: float) -> str:
        return next(reasons)

    async def close_session(session: OpenedSession) -> None:
        events.append(f"close:{session.handle}")

    result = asyncio.run(
        supervise_stream(
            run_seconds=100.0,
            reconnect=True,
            max_reconnect_attempts=5,
            open_session=open_session,
            run_session=run_session,
            close_session=close_session,
            on_disconnect=lambda: flushes.__setitem__("n", flushes["n"] + 1),
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.reconnects == 1
    assert result.ended_reason == "deadline"
    assert flushes["n"] == 1
    assert events == ["open:c1", "close:c1", "open:c2", "close:c2"]


def test_supervise_reconnect_exhausted_after_bounded_attempts() -> None:
    clock = FakeAsyncClock()
    opens = {"n": 0}

    async def open_session() -> OpenedSession:
        opens["n"] += 1
        if opens["n"] == 1:
            return OpenedSession(subscribed=("u",), failed=(), handle="c1")
        raise RuntimeError("cannot reconnect")

    async def run_session(session: OpenedSession, deadline: float) -> str:
        return "disconnected"

    async def close_session(session: OpenedSession) -> None:
        return None

    result = asyncio.run(
        supervise_stream(
            run_seconds=100.0,
            reconnect=True,
            max_reconnect_attempts=3,
            open_session=open_session,
            run_session=run_session,
            close_session=close_session,
            on_disconnect=None,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.ended_reason == "reconnect_exhausted"
    assert result.reconnects == 0
    assert opens["n"] == 1 + 3  # first open + 3 bounded reconnect attempts


def test_supervise_returns_count_cap_without_reconnect() -> None:
    clock = FakeAsyncClock()

    async def open_session() -> OpenedSession:
        return OpenedSession(subscribed=("u",), failed=(), handle="c1")

    async def run_session(session: OpenedSession, deadline: float) -> str:
        return "count_cap"

    async def close_session(session: OpenedSession) -> None:
        return None

    result = asyncio.run(
        supervise_stream(
            run_seconds=100.0,
            reconnect=True,
            max_reconnect_attempts=3,
            open_session=open_session,
            run_session=run_session,
            close_session=close_session,
            on_disconnect=None,
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.ended_reason == "count_cap"
    assert result.reconnects == 0


def test_supervise_stops_on_disconnect_when_reconnect_disabled() -> None:
    clock = FakeAsyncClock()
    flushes = {"n": 0}

    async def open_session() -> OpenedSession:
        return OpenedSession(subscribed=("u",), failed=(), handle="c1")

    async def run_session(session: OpenedSession, deadline: float) -> str:
        return "disconnected"

    async def close_session(session: OpenedSession) -> None:
        return None

    result = asyncio.run(
        supervise_stream(
            run_seconds=100.0,
            reconnect=False,
            max_reconnect_attempts=3,
            open_session=open_session,
            run_session=run_session,
            close_session=close_session,
            on_disconnect=lambda: flushes.__setitem__("n", flushes["n"] + 1),
            monotonic_fn=clock.monotonic,
            sleep_fn=clock.sleep,
        )
    )
    assert result.ended_reason == "disconnected"
    assert flushes["n"] == 1
    assert result.reconnects == 0
