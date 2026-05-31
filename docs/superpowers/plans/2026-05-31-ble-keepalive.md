# BLE Keep-Alive (Timed Recording) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a `--duration N` recording run the full `N` seconds and save every plausible sample to CSV, surviving the raw-notification count cap and transient BLE link drops.

**Architecture:** Extract the bleak-free streaming orchestration (a monotonic-deadline loop + a reconnect supervisor) into a new `pulseox/streaming.py` so it is unit-testable with injected fakes. `pulseox/ble.py` keeps all Bleak I/O and wires real `connect/subscribe/run/close` callables into `streaming.supervise_stream`. Duration becomes the authoritative bound; `--max-notifications` becomes an opt-in safety ceiling (default disabled).

**Tech Stack:** Python 3.11, asyncio, Bleak 0.22.2, pytest, ruff. Spec: `docs/superpowers/specs/2026-05-31-ble-keepalive-design.md`.

---

## File Structure

- **Create** `pulseox/streaming.py` — bleak-free core: `NotifyFailure`, `OpenedSession`, `StreamResult`, reason constants, `run_until_deadline`, `supervise_stream`. One responsibility: time/reconnect orchestration over opaque sessions.
- **Modify** `pulseox/ble.py` — remove `_run_stream_loop`, `NotifyResult`, `_raise_on_stop_errors`, and the local `NotifyFailure`; import them/the core from `streaming`; rewrite `stream_notifications` to build real callables and delegate to `supervise_stream`; relax `_validate_stream_args` to allow `max_notifications == 0`.
- **Modify** `pulseox/record.py` — add public `flush()` and time-based flushing (`flush_interval_s`).
- **Modify** `pulseox/cli.py` — `--max-notifications` default `0`; add `--reconnect/--no-reconnect`, `--max-reconnect-attempts`; pass `on_disconnect=recorder.flush`; print a session summary.
- **Create** `tests/test_streaming.py` — unit tests for the core (no bleak, no hardware).
- **Create** `tests/test_ble_stream.py` — integration test of `stream_notifications` wiring with monkeypatched Bleak helpers.
- **Modify** `tests/test_record.py` — add flush tests (append; keep existing tests untouched).
- **Create** `tests/test_cli_args.py` — assert new CLI defaults.
- **Modify** `README.md` — document duration-authoritative behavior, `--max-notifications` default, reconnect flags.

---

### Task 0: Environment setup

**Files:** none (tooling only).

- [ ] **Step 1: Create a venv and install test deps**

Run:
```bash
python3 -m venv ~/.venvs/pulseox
~/.venvs/pulseox/bin/pip install -q --upgrade pip
~/.venvs/pulseox/bin/pip install -q "bleak==0.22.2" pytest ruff
```
Expected: installs without error (bleak pulls `dbus-fast` wheels on Linux).

- [ ] **Step 2: Verify imports and baseline tests**

Run:
```bash
cd /root/repos/PulseOx && ~/.venvs/pulseox/bin/python -c "import bleak, pulseox.ble, pulseox.record; print('ok')"
~/.venvs/pulseox/bin/pytest -q
```
Expected: prints `ok`; existing suite passes (4 test files).

> For all later steps, use `~/.venvs/pulseox/bin/pytest` and `~/.venvs/pulseox/bin/ruff`.

---

### Task 1: Streaming core — `run_until_deadline`

**Files:**
- Create: `pulseox/streaming.py`
- Test: `tests/test_streaming.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_streaming.py`:

```python
import asyncio

from pulseox.streaming import (
    NotifyFailure,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `~/.venvs/pulseox/bin/pytest tests/test_streaming.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pulseox.streaming'`.

- [ ] **Step 3: Create `pulseox/streaming.py` with the core types and `run_until_deadline`**

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# Reasons a stream segment can end.
REASON_DEADLINE = "deadline"
REASON_COUNT_CAP = "count_cap"
REASON_DISCONNECTED = "disconnected"
REASON_RECONNECT_EXHAUSTED = "reconnect_exhausted"


@dataclass(frozen=True, slots=True)
class NotifyFailure:
    """A characteristic UUID that failed to subscribe, with its error text."""

    uuid: str
    error: str


@dataclass(slots=True)
class OpenedSession:
    """A live subscription produced by an `open_session` callable.

    `handle` is opaque to this module (a BleakClient in production); only the
    injected run/close callables touch it.
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
) -> str:
    """Sleep in bounded steps until the deadline, a count cap, or a disconnect.

    Returns REASON_DEADLINE, REASON_COUNT_CAP, or REASON_DISCONNECTED. Bounded
    by `deadline` on the `monotonic_fn` clock.
    """
    _require_positive(poll_interval, "poll_interval")
    if max_notifications < 0:
        raise ValueError("max_notifications must be >= 0")

    while True:
        now = monotonic_fn()
        if now >= deadline:
            return REASON_DEADLINE
        if max_notifications and get_count() >= max_notifications:
            return REASON_COUNT_CAP
        if not is_connected():
            return REASON_DISCONNECTED
        await sleep_fn(min(poll_interval, deadline - now))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `~/.venvs/pulseox/bin/pytest tests/test_streaming.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pulseox/streaming.py tests/test_streaming.py
git commit -m "feat: deadline-bounded stream loop (duration authoritative)"
```

---

### Task 2: Streaming core — `supervise_stream` (reconnect)

**Files:**
- Modify: `pulseox/streaming.py`
- Test: `tests/test_streaming.py`

- [ ] **Step 1: Append failing tests to `tests/test_streaming.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `~/.venvs/pulseox/bin/pytest tests/test_streaming.py -q`
Expected: FAIL — `ImportError: cannot import name 'supervise_stream'`.

- [ ] **Step 3: Append `supervise_stream` to `pulseox/streaming.py`**

```python
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
) -> StreamResult:
    """Run one or more sessions until the deadline, reconnecting on drops.

    The first `open_session()` failure propagates (a run must subscribe at least
    once). Later drops are recovered when `reconnect` is True, bounded by both
    `max_reconnect_attempts` (consecutive failures) and the deadline.
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

        gap_start = monotonic_fn()
        new_session: OpenedSession | None = None
        for attempt in range(1, max_reconnect_attempts + 1):
            if monotonic_fn() >= deadline:
                break
            try:
                new_session = await open_session()
                break
            except Exception:
                await sleep_fn(min(0.25 * attempt, 1.0))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `~/.venvs/pulseox/bin/pytest tests/test_streaming.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add pulseox/streaming.py tests/test_streaming.py
git commit -m "feat: reconnect supervisor for streaming core"
```

---

### Task 3: Recorder — public `flush()` + time-based flushing

**Files:**
- Modify: `pulseox/record.py`
- Test: `tests/test_record.py`

- [ ] **Step 1: Append failing tests to `tests/test_record.py`**

```python
class _FlushSpy(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def test_recorder_time_based_flush() -> None:
    fp = _FlushSpy()
    # start=0.0, call1 now=0.0, call2 now=3.0 (>= 2.0s interval)
    clock = FakeClock([0.0, 0.0, 3.0])
    now_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1000,
        flush_interval_s=2.0,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now_dt,
    )

    frame = bytes([0xF1, 0x5C, 0x46])
    recorder.on_notification(sender=1, data=frame)  # now=0.0 -> no time flush
    after_first = fp.flush_count
    recorder.on_notification(sender=1, data=frame)  # now=3.0 -> time-based flush
    assert fp.flush_count > after_first


def test_recorder_flush_is_public_and_writes() -> None:
    fp = _FlushSpy()
    clock = FakeClock([0.0, 0.0])
    now_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=False,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1000,
        flush_interval_s=1000.0,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now_dt,
    )
    recorder.on_notification(sender=1, data=bytes([0xF1, 0x5C, 0x46]))
    before = fp.flush_count
    recorder.flush()
    recorder.flush()
    assert fp.flush_count == before + 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `~/.venvs/pulseox/bin/pytest tests/test_record.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'flush_interval_s'`.

- [ ] **Step 3: Modify `pulseox/record.py`**

In `PulseOxCsvRecorder.__init__`, change the signature to add `flush_interval_s` (place it right after `flush_every`):

```python
    def __init__(
        self,
        file: TextIO,
        *,
        write_header: bool,
        sample_hz: float,
        include_implausible: bool,
        flush_every: int,
        flush_interval_s: float = 2.0,
        monotonic_fn: Callable[[], float] = time.monotonic,
        now_utc_fn: Callable[[], datetime] = _now_utc,
    ) -> None:
```

In `__init__`, after `self._flush_every = _require_positive_int(flush_every, "flush_every")`, add:

```python
        self._flush_interval_s = _require_nonnegative_finite(
            flush_interval_s, "flush_interval_s"
        )
```

And after `self._last_write_mono: float | None = None`, add:

```python
        self._last_flush_mono = self._start_mono
```

Replace the existing `close()` method:

```python
    def close(self) -> None:
        """Flush buffered rows (does not close the underlying file)."""
        self.flush()
```

Add a public `flush()` immediately after `close()`:

```python
    def flush(self) -> None:
        """Flush buffered rows to the underlying file."""
        self._file.flush()
        self._rows_since_flush = 0
```

At the end of `on_notification`, replace the existing flush block:

```python
        if self._rows_since_flush >= self._flush_every:
            self._file.flush()
            self._rows_since_flush = 0
```

with time-aware flushing (note: do **not** call `self._monotonic()` again here — reuse `now_mono` so existing fake-clock tests keep their exact call counts):

```python
        time_due = (
            self._flush_interval_s > 0
            and (now_mono - self._last_flush_mono) >= self._flush_interval_s
        )
        if self._rows_since_flush >= self._flush_every or time_due:
            self.flush()
            self._last_flush_mono = now_mono
```

- [ ] **Step 4: Run the full record suite to verify pass + no regressions**

Run: `~/.venvs/pulseox/bin/pytest tests/test_record.py -q`
Expected: all pass (5 original + 2 new = 7).

- [ ] **Step 5: Commit**

```bash
git add pulseox/record.py tests/test_record.py
git commit -m "feat: recorder public flush() + time-based flushing"
```

---

### Task 4: `ble.py` — rewrite `stream_notifications` over the streaming core

**Files:**
- Modify: `pulseox/ble.py`
- Test: `tests/test_ble_stream.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_ble_stream.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/pulseox/bin/pytest tests/test_ble_stream.py -q`
Expected: FAIL — `stream_notifications` has no `monotonic_fn`/`sleep_fn`/`reconnect` parameters yet (`TypeError: unexpected keyword argument`).

- [ ] **Step 3: Edit `pulseox/ble.py` imports and top-of-file**

Replace the current top imports block (lines ~1–11) so it adds `time`, `Awaitable`, drops nothing essential, and imports the core from `streaming`:

```python
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
    REASON_DISCONNECTED,
    StreamResult,
    run_until_deadline,
    supervise_stream,
)
```

Delete the local `NotifyFailure` dataclass (now imported) and the `NotifyResult` dataclass. Keep `DeviceInfo`, `CharacteristicInfo`, `ServiceInfo`.

- [ ] **Step 4: Remove the obsolete loop/teardown helpers**

Delete `_run_stream_loop` and `_raise_on_stop_errors` entirely (they are replaced by the streaming core).

- [ ] **Step 5: Relax `_validate_stream_args`**

In `_validate_stream_args`, change:

```python
    if max_notifications <= 0:
        raise ValueError("max_notifications must be positive")
```

to:

```python
    if max_notifications < 0:
        raise ValueError("max_notifications must be >= 0")
```

- [ ] **Step 6: Replace `stream_notifications` with the supervisor-wired version**

Replace the entire `async def stream_notifications(...)` function (and its old body that used `_run_stream_loop`) with:

```python
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

    `run_seconds` (wall-clock) is the authoritative bound. `max_notifications`
    is an opt-in safety ceiling on raw notifications; 0 disables it. On a link
    drop with `reconnect=True`, the recorder is flushed (`on_disconnect`), the
    device is re-scanned, and streaming resumes against the remaining time.
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
        client = await _connect_client(target, timeout_s, connect_attempts=connect_attempts)
        try:
            effective_notify_uuids = await _resolve_notify_uuids(
                client,
                notify_uuids,
                auto_notify=auto_notify,
                on_services=on_services if not first_open["done"] else None,
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

        first_open["done"] = True
        return OpenedSession(
            subscribed=tuple(subscribed),
            failed=tuple(failures),
            handle=client,
        )

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
```

- [ ] **Step 7: Run the integration test + full streaming/record suites**

Run: `~/.venvs/pulseox/bin/pytest tests/test_ble_stream.py tests/test_streaming.py tests/test_record.py -q`
Expected: all pass.

- [ ] **Step 8: Lint the changed modules**

Run: `~/.venvs/pulseox/bin/ruff check pulseox/streaming.py pulseox/ble.py pulseox/record.py`
Expected: no errors. (If ruff flags an unused import such as `AdvertisementData`, confirm it is still referenced by `_scan_raw`/`scan_devices`; only remove imports that are genuinely unused after the edits.)

- [ ] **Step 9: Commit**

```bash
git add pulseox/ble.py tests/test_ble_stream.py
git commit -m "feat: reconnect-aware stream_notifications, duration authoritative"
```

---

### Task 5: `cli.py` — flags, defaults, flush hook, session summary

**Files:**
- Modify: `pulseox/cli.py`
- Test: `tests/test_cli_args.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_args.py`:

```python
import sys

import pytest

from pulseox import cli


def test_cli_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "--address", "AA:BB:CC:DD:EE:FF"])
    args = cli._parse_args()
    assert args.max_notifications == 0
    assert args.reconnect is True
    assert args.max_reconnect_attempts == 5


def test_cli_no_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "--address", "AA", "--no-reconnect"])
    args = cli._parse_args()
    assert args.reconnect is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/pulseox/bin/pytest tests/test_cli_args.py -q`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'reconnect'` (and `max_notifications` defaults to 1000).

- [ ] **Step 3: Edit `_parse_args` in `pulseox/cli.py`**

Change the `--max-notifications` argument to:

```python
    parser.add_argument(
        "--max-notifications",
        type=int,
        default=0,
        help=(
            "Safety ceiling on raw notifications processed; 0 = disabled (default). "
            "Duration is the authoritative bound."
        ),
    )
```

Immediately after the `--poll-interval` argument, add:

```python
    parser.add_argument(
        "--reconnect",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reconnect and resume recording if the BLE link drops (default: on)",
    )
    parser.add_argument(
        "--max-reconnect-attempts",
        type=int,
        default=5,
        help="Bounded consecutive reconnect attempts before giving up",
    )
```

- [ ] **Step 4: Edit `_run` in `pulseox/cli.py`**

Replace the `stream_notifications(...)` call and the following result handling. The new call passes the reconnect options and the recorder's flush as `on_disconnect`:

```python
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
            reconnect=args.reconnect,
            max_reconnect_attempts=args.max_reconnect_attempts,
            on_disconnect=(recorder.flush if recorder is not None else None),
            on_payload=on_payload,
        )
        rows = recorder.rows_written if recorder is not None else 0
        print(
            f"\nSession ended ({result.ended_reason}): "
            f"rows={rows} reconnects={result.reconnects} "
            f"gap={result.total_gap_s:.1f}s"
        )
        if result.failed:
            print("\nSome subscriptions failed:")
            for failure in result.failed:
                print(f"- {failure.uuid}: {failure.error}")
```

- [ ] **Step 5: Run the CLI test + full suite**

Run: `~/.venvs/pulseox/bin/pytest -q`
Expected: all tests pass (existing + streaming + ble + record + cli).

- [ ] **Step 6: Lint**

Run: `~/.venvs/pulseox/bin/ruff check pulseox/cli.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add pulseox/cli.py tests/test_cli_args.py
git commit -m "feat: CLI reconnect flags, duration-authoritative default, session summary"
```

---

### Task 6: Docs + final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README CSV/runtime section**

In `README.md`, under "### 5) Tuning runtime bounds/timeouts", replace the bullet list with:

```markdown
- `--duration`: how long to record (seconds). **Authoritative bound** — the run
  lasts the full duration regardless of notification rate.
- `--max-notifications`: opt-in safety ceiling on *raw* notifications; **`0`
  (default) disables it**. (Previously defaulted to `1000`, which could end a
  timed run early because high-rate waveform packets are counted before they are
  filtered out.)
- `--reconnect` / `--no-reconnect`: on a dropped BLE link, re-scan, reconnect,
  resubscribe, and resume appending to the same CSV until the duration elapses
  (default: on).
- `--max-reconnect-attempts`: bounded consecutive reconnect attempts (default 5).
- `--timeout`: per-operation BLE timeout (seconds)
- `--poll-interval`: internal bounded loop sleep (seconds)

At the end of a run the CLI prints a summary line:
`Session ended (deadline): rows=<n> reconnects=<n> gap=<seconds>s`.
```

- [ ] **Step 2: Run the complete suite, lint, and (best-effort) typecheck**

Run:
```bash
cd /root/repos/PulseOx
~/.venvs/pulseox/bin/pytest -q
~/.venvs/pulseox/bin/ruff check pulseox tests
```
Expected: all tests pass; ruff clean.

(Optional, only if `pyright` is available: `python -m pyright pulseox/streaming.py` — node-dependent; skip with a note if not installed.)

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document duration-authoritative recording and reconnect flags"
```

---

## Self-Review

**Spec coverage:**
- Deadline-based loop → Task 1 (`run_until_deadline`, monotonic deadline). ✔
- Decouple stop from raw-notification count; `--max-notifications` default 0 → Task 1 (cap optional), Task 4 (`_validate_stream_args` allows 0), Task 5 (CLI default 0). ✔
- Reconnect + resubscribe supervisor, same CSV appended → Task 2 (`supervise_stream`), Task 4 (re-scan + reopen via `_resolve_target`/`open_session`; recorder/file reused by caller). ✔
- Robust CSV flushing (public `flush()` + time-based) → Task 3; flush-on-drop hook → Task 5 (`on_disconnect=recorder.flush`). ✔
- CLI flags + summary → Task 5. ✔
- Tests for deadline authority, count cap opt-in, reconnect, exhaustion, recorder flush, existing green → Tasks 1–5. ✔
- README → Task 6. ✔

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✔

**Type consistency:** `run_until_deadline` / `supervise_stream` signatures, `OpenedSession(subscribed, failed, handle)`, `StreamResult(subscribed, failed, reconnects, total_gap_s, ended_reason)`, reason strings (`deadline`/`count_cap`/`disconnected`/`reconnect_exhausted`) are used identically in Tasks 1, 2, 4, 5. `stream_notifications` returns `StreamResult`; `cli` reads `.ended_reason`, `.reconnects`, `.total_gap_s`, `.failed`. `recorder.flush` matches the `on_disconnect: Callable[[], None]` hook. ✔

**Note on non-TDD reality:** the Bleak boundary can't be exercised against hardware in CI; Task 4 covers the wiring by monkeypatching the I/O helpers and driving a fake client whose `is_connected` flips — the orchestration logic itself is fully unit-tested in Tasks 1–2.
