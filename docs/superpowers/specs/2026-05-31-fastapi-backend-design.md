# PulseOx — FastAPI backend design

**Date:** 2026-05-31
**Status:** Approved (architecture) → ready for implementation plan
**Phase:** 2 of 4 (see [Phase 1 spec](2026-05-31-ble-keepalive-design.md))

## Problem

The browser cannot speak BLE (`bleak` is Python). To let the TypeScript UI
control the oximeter and show realtime data, a local Python service must wrap the
`pulseox` package and expose HTTP + WebSocket. This phase builds that service.

## Goal

A local FastAPI app (`127.0.0.1:8000`) that can scan for devices, start/stop a
timed recording (reusing the Phase 1 reconnect-aware streamer), stream live
samples to WebSocket clients, list/serve recorded sessions, and accept CSV
uploads — all emitting the exact `PulseOxSample` shape the frontend already
defines.

## The data contract (pin this)

The WS `sample` frame payload and the `GET /api/sessions/{name}` rows MUST match
`frontend/src/types/pulseox.ts::PulseOxSample` field-for-field — identical to
`pulseox.record.CSV_FIELDNAMES` and `pulseox.dashboard_data.PulseOxSample`:

```
timestamp_utc: str (ISO-8601), elapsed_s: float, sender: str,
spo2_percent: int, pulse_bpm: int, perfusion_index: int,
plausible: bool, raw_frame_hex: str, raw_notification_hex: str,
remainder_hex: str
```

A `pulseox.dashboard_data.sample_to_dict(sample) -> dict` helper produces this
shape (added in this phase) and is the single serialization point.

## Two mechanism decisions (the hard part)

### 1. Sync → async fan-out: a poll-based broadcaster

`OnPayload` is a **synchronous** callback; bleak calls it on the loop thread in
sync context. `websocket.send_json()` is a coroutine and **cannot be awaited from
inside `on_payload`**. Therefore:

- `on_payload` stays purely synchronous: decode + `recorder.on_notification` +
  `hub.publish({"type": "sample", **sample_dict})`.
- A **`SampleHub`** holds a bounded `deque` of `(seq, frame)` with a monotonic
  `seq`. `publish()` is sync-safe (loop-thread, single-threaded). `since(cursor)`
  returns `(latest_seq, [frames with seq > cursor])`.
- Each **WebSocket connection** runs its own async loop: on connect, replay the
  current backlog (recent frames) then poll `hub.since(cursor)` every ~0.2 s and
  `await ws.send_json(frame)`. ~200 ms latency is irrelevant for ~1 Hz vitals.
- Per-connection isolation: a send failure breaks only that connection's loop and
  removes it; one dead socket cannot stall recording or other clients.

The deque doubles as the late-joiner replay buffer (no separate structure).

### 2. Stop is a cooperative signal, not task cancellation

Cancelling the background `asyncio.Task` raises `CancelledError` inside
`run_until_deadline`'s sleep and unwinds **before** `close_session` runs — leaking
the BleakClient and depending on the wrapper's `finally` for the CSV flush.
Instead, extend the Phase 1 streaming core:

- Add `should_stop: Callable[[], bool]` to `run_until_deadline` (same shape as the
  count-cap check) returning a new `REASON_STOPPED`.
- `supervise_stream` and `stream_notifications` thread `should_stop` through;
  `REASON_STOPPED` is terminal (like `deadline`, no reconnect).
- `POST /recording/stop` sets an `asyncio.Event`; `should_stop=event.is_set`. Stop
  now flows through the normal `close_session` + flush path — same cooperative
  philosophy as making duration authoritative.

The background-task wrapper still uses `try/finally` to flush+close the recorder
and publish a terminal `status` frame, as defence in depth.

## Components

```
pulseox_server/
  __init__.py
  hub.py        # SampleHub: bounded frame log, sync publish + since()
  session.py    # DeviceSession state machine + _run_recording coroutine
  app.py        # FastAPI routes + WS endpoint (thin)
  config.py     # settings: host/port, sessions_dir (env PULSEOX_SESSIONS_DIR)
  __main__.py   # uvicorn entry, binds 127.0.0.1:8000
```

### `SampleHub` (hub.py) — sync, no asyncio; fully unit-testable
- `publish(frame: dict) -> int` — append `(seq, frame)`, return seq.
- `since(cursor: int) -> tuple[int, list[dict]]` — frames with seq > cursor.
- `backlog(limit: int) -> tuple[int, list[dict]]` — last ≤limit frames + latest seq.
- Bounded `deque(maxlen=…)`; `seq` strictly increasing across the run.

### `DeviceSession` (session.py) — state machine
States: `idle → recording → (stopping) → idle|error`. Single active recording.
- `stream_fn` injected (default `pulseox.ble.stream_notifications`) so tests use a
  fake — no real bleak.
- `start(config) -> None`: reject if not `idle` (raises `RecordingActive`). Opens
  the CSV recorder (`open_csv_path` + `PulseOxCsvRecorder`), builds the sync
  `on_payload`, resets the hub, launches `_run_recording` as a background task,
  sets status `recording`, publishes a `status` frame.
- `_run_recording(config)` (awaitable; tested directly): calls
  `await stream_fn(address, …, on_payload=…, on_disconnect=recorder.flush,
  should_stop=self._stop.is_set, reconnect=config.reconnect)`; `try/finally`
  flushes+closes recorder, records `ended_reason`/rows, sets status `idle`,
  publishes terminal `status` frame. Exceptions → status `error` + error frame.
- `stop() -> None`: set `self._stop`; await the task (bounded).
- `status_dict() -> dict`: `{status, address, duration_s, elapsed_s, rows,
  reconnects, ended_reason, session_file}`.
- `scan(timeout) -> list[dict]`: wraps `pulseox.ble.scan_devices`; each device
  `{address, name, rssi, advertised_uuids}`.

`RecordingConfig`: `address: str` (default `FF:FF:FF:FF:00:21`),
`duration_s: float`, `sample_hz: float = 1.0`, `reconnect: bool = True`,
`notify_uuid: str | None`, `session_name: str | None` (else timestamped).

### FastAPI app (app.py) — thin routes over one `DeviceSession`
- `GET  /api/health` → `{"status":"ok"}`
- `GET  /api/status` → `session.status_dict()`
- `POST /api/scan` `{timeout?}` → `{devices:[…]}`
- `POST /api/recording/start` `RecordingConfig` → 202 `status_dict` (409 if active)
- `POST /api/recording/stop` → `status_dict` (409 if idle)
- `GET  /api/sessions` → `{sessions:[{name,size,modified,rows?}]}` (list `*.csv`)
- `GET  /api/sessions/{name}?maxRows=&onlyPlausible=` → `{samples:[…],metadata}`
  using `dashboard_data.load_recent_samples_from_path` + `sample_to_dict`
- `POST /api/upload` (multipart CSV) → stores under sessions dir, returns parsed
  `{samples,metadata,name}`
- `WS   /ws/stream` → on connect send `backlog`; then poll `hub.since(cursor)` →
  `send_json`. CORS allows `http://localhost:3000`.

### Path-traversal guard
`{name}` and the upload filename are sanitized: reject `/`, `\`, `..`, leading
dots; resolve under `sessions_dir` and verify the resolved path stays within it
(equivalent to the existing `/api/samples` workspace check). One shared
`_safe_session_path(name) -> Path` helper.

## Sessions storage
Recordings live in `sessions/` at repo root (gitignored), overridable via
`PULSEOX_SESSIONS_DIR`. Runtime recordings are app data, not generated
deliverables, so the workspace `exports/` rule does not apply.

## Dependency + consolidation changes
- Add: `fastapi`, `uvicorn[standard]`, `python-multipart` (upload), `httpx` (dev,
  for `TestClient`). Keep `bleak`.
- Remove: `plotly`, `reflex`, `streamlit`, `streamlit-autorefresh`.
- Delete `streamlit_app.py` and `pulseox_reflex/` (consolidate on Python-backend
  + TS frontend). **Own commit**, independent of the backend code.
- `pyproject.toml`: drop the `exclude = ["streamlit_app.py"]` pyright line.

## Testing
- `SampleHub`: publish/since/backlog ordering + bound (pure unit).
- `streaming` core: `should_stop` ⇒ `REASON_STOPPED`; supervisor treats it
  terminal (no reconnect). Extend `tests/test_streaming.py`.
- `DeviceSession._run_recording`: fake `stream_fn` that publishes N samples then
  returns; assert hub frames, recorder rows, status transitions, terminal frame;
  a fake that loops until `should_stop` ⇒ `stop()` ends it; error path ⇒ status
  `error`.
- FastAPI routes via `TestClient` with the session's `stream_fn`/`scan` monkey-
  patched: health/status/scan/start(409 on double)/stop/sessions/sessions{name}/
  upload; a WS test that starts a fake recording and reads `sample` frames.
- All Phase 1 tests stay green.

## Critical-path sequencing (build order)
1. `streaming` `should_stop`/`REASON_STOPPED` (+ thread through ble).
2. `SampleHub`.
3. `DeviceSession` start→stream→stop→CSV with a fake `stream_fn`.
4. FastAPI `health/status/start/stop` + `WS /ws/stream`.
5. `scan`, `sessions`, `sessions/{name}`.
6. `upload`.
7. Dependency swap + delete streamlit/reflex (own commit).

Stop after (4) is already the Phase-3-unblocking core; (5)–(7) layer on.

## Non-goals
- No auth/TLS (localhost-only local tool).
- No multi-device concurrent recording.
- No frontend changes (Phase 3).
