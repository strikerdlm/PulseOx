from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# Reasons a stream segment or run can end.
REASON_DEADLINE = "deadline"
REASON_COUNT_CAP = "count_cap"
REASON_DISCONNECTED = "disconnected"
REASON_RECONNECT_EXHAUSTED = "reconnect_exhausted"
REASON_STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class NotifyFailure:
    """A characteristic UUID that failed to subscribe, with its error text."""

    uuid: str
    error: str


@dataclass(slots=True)
class OpenedSession:
    """A live subscription produced by an ``open_session`` callable.

    ``handle`` is opaque to this module (a ``BleakClient`` in production); only
    the injected run/close callables touch it.
    """

    subscribed: tuple[str, ...]
    failed: tuple[NotifyFailure, ...]
    handle: object


@dataclass(frozen=True, slots=True)
class StreamResult:
    """Outcome of a (possibly multi-segment) streaming run."""

    subscribed: tuple[str, ...]
    failed: tuple[NotifyFailure, ...]
    reconnects: int
    total_gap_s: float
    ended_reason: str


def _require_positive(value: float, name: str) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


async def run_until_deadline(
    *,
    deadline: float,
    poll_interval: float,
    max_notifications: int,
    get_count: Callable[[], int],
    is_connected: Callable[[], bool],
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], Awaitable[None]],
    should_stop: Callable[[], bool] | None = None,
) -> str:
    """Sleep in bounded steps until stop, the deadline, a count cap, or a drop.

    Returns ``REASON_STOPPED``, ``REASON_DEADLINE``, ``REASON_COUNT_CAP``, or
    ``REASON_DISCONNECTED``. The loop is bounded by ``deadline`` measured on the
    ``monotonic_fn`` clock; ``max_notifications == 0`` disables the count cap.
    ``should_stop`` (when provided) is a cooperative stop signal checked first so
    a requested stop unwinds through the normal teardown path.
    """
    _require_positive(poll_interval, "poll_interval")
    if max_notifications < 0:
        raise ValueError("max_notifications must be >= 0")

    while True:
        if should_stop is not None and should_stop():
            return REASON_STOPPED
        now = monotonic_fn()
        if now >= deadline:
            return REASON_DEADLINE
        if max_notifications and get_count() >= max_notifications:
            return REASON_COUNT_CAP
        if not is_connected():
            return REASON_DISCONNECTED
        await sleep_fn(min(poll_interval, deadline - now))


async def _attempt_reconnect(
    *,
    open_session: Callable[[], Awaitable[OpenedSession]],
    max_reconnect_attempts: int,
    deadline: float,
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], Awaitable[None]],
) -> OpenedSession | None:
    """Try to re-open a session, bounded by attempts and the deadline."""
    for attempt in range(1, max_reconnect_attempts + 1):
        if monotonic_fn() >= deadline:
            break
        try:
            return await open_session()
        except Exception:
            await sleep_fn(min(0.25 * attempt, 1.0))
    return None


async def supervise_stream(
    *,
    run_seconds: float,
    reconnect: bool,
    max_reconnect_attempts: int,
    open_session: Callable[[], Awaitable[OpenedSession]],
    run_session: Callable[[OpenedSession, float], Awaitable[str]],
    close_session: Callable[[OpenedSession], Awaitable[None]],
    on_disconnect: Callable[[], None] | None,
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], Awaitable[None]],
    should_stop: Callable[[], bool] | None = None,
) -> StreamResult:
    """Run one or more sessions until the deadline, reconnecting on drops.

    The first ``open_session()`` failure propagates (a run must subscribe at
    least once). Later drops are recovered when ``reconnect`` is True, bounded by
    both ``max_reconnect_attempts`` (consecutive failures) and the deadline. A
    ``should_stop`` signal also aborts a pending reconnect with ``REASON_STOPPED``.
    """
    _require_positive(run_seconds, "run_seconds")
    if max_reconnect_attempts <= 0:
        raise ValueError("max_reconnect_attempts must be positive")

    deadline = monotonic_fn() + run_seconds
    reconnects = 0
    total_gap_s = 0.0

    session = await open_session()
    subscribed, failed = session.subscribed, session.failed

    while True:
        reason = await run_session(session, deadline)
        await close_session(session)

        if reason != REASON_DISCONNECTED:
            return StreamResult(subscribed, failed, reconnects, total_gap_s, reason)

        if on_disconnect is not None:
            on_disconnect()

        if not reconnect or monotonic_fn() >= deadline:
            ended = REASON_DEADLINE if monotonic_fn() >= deadline else REASON_DISCONNECTED
            return StreamResult(subscribed, failed, reconnects, total_gap_s, ended)

        if should_stop is not None and should_stop():
            return StreamResult(subscribed, failed, reconnects, total_gap_s, REASON_STOPPED)

        gap_start = monotonic_fn()
        new_session = await _attempt_reconnect(
            open_session=open_session,
            max_reconnect_attempts=max_reconnect_attempts,
            deadline=deadline,
            monotonic_fn=monotonic_fn,
            sleep_fn=sleep_fn,
        )
        total_gap_s += monotonic_fn() - gap_start

        if new_session is None:
            ended = (
                REASON_DEADLINE
                if monotonic_fn() >= deadline
                else REASON_RECONNECT_EXHAUSTED
            )
            return StreamResult(subscribed, failed, reconnects, total_gap_s, ended)

        reconnects += 1
        session = new_session
        subscribed, failed = session.subscribed, session.failed
