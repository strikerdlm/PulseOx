# PulseOx — BLE keep-alive (timed recording) design

**Date:** 2026-05-31
**Status:** Approved (brainstorming) → ready for implementation plan
**Phase:** 1 of 4 (see "Roadmap context" below)

## Problem

A timed recording started with `--duration N` disconnects long before `N`
seconds elapse, losing the rest of the session. Root cause, in priority order:

1. **Raw-notification count cap preempts duration (primary).**
   `ble.py` `stream_notifications` increments `count` in `handler` on *every*
   BLE notification — including the high-rate `0xF0`/`0xF2` waveform packets the
   A340B-LK emits at tens of Hz. The recorder filters those out *downstream*
   (`record.py`), but the counter has already ticked. `_run_stream_loop` breaks
   the moment `get_count() >= max_notifications`, and `--max-notifications`
   defaults to **1000** (`cli.py`). So a flood of waveform packets trips the cap
   in seconds-to-tens-of-seconds and the stream terminates → `finally` →
   `stop_notify` + `disconnect`. Fingerprint: README programmatic Example 8 sets
   `max_notifications=100_000` — a prior in-code workaround that never reached
   the CLI default.

2. **Iteration-counted loop drifts short of wall-clock (secondary).**
   `_run_stream_loop` runs `int(run_seconds / poll_interval) + 1` iterations,
   each sleeping `poll_interval`. Per-iteration scheduling/processing overhead
   makes the real elapsed time *under*-run the requested duration.

3. **No reconnect on a genuine link drop (tertiary).**
   If the BLE link actually drops mid-session (power saving, finger removal, RF),
   nothing detects it or recovers; the loop sleeps out the rest of the run
   collecting nothing, or `finally` raises on teardown.

## Goal

A `--duration N` recording runs the full `N` seconds (wall-clock authoritative)
and writes every plausible sample to CSV, surviving both the notification-rate
cap and transient BLE link drops. Bounded-execution discipline is preserved: the
loop is bounded by the monotonic deadline, and every reconnect path is bounded.

## Non-goals

- No change to the decode heuristics (`decode.py`) or CSV schema
  (`record.CSV_FIELDNAMES`).
- No new device support.
- No UI work (Phases 2–4).

## Design

### 1. Deadline-based stream loop (`ble.py`)

Replace `_run_stream_loop`'s iteration counting with a monotonic deadline:

```
deadline = monotonic() + run_seconds
while monotonic() < deadline:
    remaining = deadline - monotonic()
    await asyncio.sleep(min(poll_interval, remaining))
    if max_notifications and get_count() >= max_notifications:
        break
```

`run_seconds` is the authoritative bound. The clock source is injectable
(`monotonic_fn` parameter, default `time.monotonic`) so tests can drive it
deterministically.

### 2. Demote `--max-notifications` to an opt-in safety ceiling

- `max_notifications == 0` (or `None`) ⇒ **disabled** (no count-based stop).
- CLI default changes from `1000` to `0`. Help text: "Safety ceiling on raw
  notifications; 0 = disabled (default). Duration is the authoritative bound."
- `_validate_stream_args` allows `max_notifications == 0` (currently rejects
  non-positive). Positive values still enforced as a hard cap when set.
- Bounded execution is guaranteed by the deadline, not the count — preserves the
  repo's "all loops bounded" invariant.

### 3. Reconnect + resubscribe supervisor (`ble.py`)

Introduce a supervisor wrapping connect → resolve-uuids → subscribe → stream that,
**until the deadline**, recovers from disconnects:

- Detect disconnect via `client.is_connected` going false (polled in the stream
  loop) and via Bleak disconnect errors raised during streaming.
- On drop: call an injected `on_disconnect` hook (used to flush the recorder),
  then re-scan for the `BLEDevice` (BlueZ requires it), reconnect with bounded
  backoff (reuse `_connect_client`), resubscribe to the same UUIDs, and continue
  streaming against the *remaining* time budget (`deadline - now`).
- Bounds: total wall-clock bounded by the deadline; reconnect attempts bounded by
  `max_reconnect_attempts` (consecutive failures) — on exhaustion, stop cleanly
  and report.
- The same CSV file/recorder is reused across reconnects (append in place — the
  recorder already holds an open handle; no file reopen).
- Returns a richer `NotifyResult` (or a new `StreamResult`) carrying:
  `subscribed`, `failed`, `reconnects`, `total_gap_s`, `ended_reason`
  (`deadline` | `count_cap` | `reconnect_exhausted` | `cancelled`).

New params on `stream_notifications` (all with safe defaults so existing callers
keep working): `reconnect: bool = True`, `max_reconnect_attempts: int = 5`,
`on_disconnect: Callable[[], None] | None = None`,
`monotonic_fn: Callable[[], float] = time.monotonic`.

### 4. Robust CSV flushing (`record.py`)

- Add a public `flush()` method (currently only `close()` flushes).
- Add **time-based flush**: flush when `>= flush_interval_s` (default 2.0 s) has
  elapsed since the last flush, in addition to the existing `flush_every` row
  count. Guarantees a drop/crash loses at most ~2 s of buffered rows.
- `cli.py` passes `recorder.flush` as the `on_disconnect` hook.

### 5. CLI surface (`cli.py`)

- `--max-notifications` default → `0` (disabled), help updated.
- `--reconnect / --no-reconnect` (default on).
- `--max-reconnect-attempts` (default 5).
- End-of-run summary line (even with `--quiet`): rows written, reconnect count,
  total gap seconds, end reason.

## Testing

New/updated unit tests (no real BLE; inject fakes):

1. **Deadline authority** — fake clock + a `get_count` that floods past any cap;
   assert the loop runs until the deadline and does **not** stop early.
2. **Count cap opt-in** — `max_notifications=0` ⇒ never count-stops; a positive
   value ⇒ stops at that count.
3. **Reconnect/resubscribe** — a fake client whose `is_connected` flips false then
   true; assert `on_disconnect` (flush) fired, resubscribe happened, streaming
   continued against remaining time, and `reconnects == 1`.
4. **Reconnect exhaustion** — persistent failure ⇒ bounded attempts, clean stop,
   `ended_reason == "reconnect_exhausted"`.
5. **Recorder flush** — time-based flush triggers within `flush_interval_s`;
   `flush()` is idempotent and writes buffered rows.
6. Existing `test_record.py` / `test_decode.py` / `test_dashboard_data.py` stay
   green.

To keep `ble.py` unit-testable, the connect/scan/subscribe boundary is factored
behind small injectable callables so the supervisor logic can be exercised with
fakes (no Bleak, no hardware).

## Risks / trade-offs

- `stream_notifications` grows a supervisor loop. Mitigate by extracting the
  single-connection "subscribe + run until deadline-or-drop" into a helper, with
  the supervisor handling only reconnect orchestration — each unit stays small.
- Changing `--max-notifications` default is a behavior change; documented in
  README and the run summary. Anyone relying on the old 1000 cap can set it
  explicitly.
- Append-across-reconnect can produce a brief timestamp gap; surfaced via
  `total_gap_s` rather than hidden.

## Roadmap context (later phases — not in this spec)

This phase is standalone and shippable. Subsequent phases each get their own
spec → plan → implement cycle:

- **Phase 2 — FastAPI backend** (`pulseox_server/`): REST `scan/connect/start/
  stop/status/sessions/upload` + WebSocket `/stream`, wrapping `pulseox`
  (reuses this phase's streaming + reconnect).
- **Phase 3 — Frontend rebuild** (`frontend/`): Live mode (device control +
  realtime gauges/trend over WS) and Analysis mode (CSV upload + server path +
  plots/stats), responsive, redesigned gauges, fixed file import.
- **Phase 4 — Publication export + new analyses**: one-click session → Q1
  SVG/PNG via the `/echarts` skill; HRV/Poincaré, Bland-Altman, hypoxemia-burden,
  ridgeline analyses.

Streamlit (`streamlit_app.py`) and Reflex (`pulseox_reflex/`) are dropped to
consolidate on the Python-backend + TS/JS-frontend stack; reusable parsing in
`dashboard_data.py` is retained for the FastAPI backend.
