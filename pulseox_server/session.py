from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pulseox.ble import DeviceInfo, scan_devices, scan_for_device, stream_notifications
from pulseox.record import PulseOxCsvRecorder, open_csv_path
from pulseox.streaming import StreamResult
from pulseox_server.config import DEFAULT_ADDRESS, DEFAULT_NOTIFY_UUID
from pulseox_server.hub import SampleHub

# Callable that performs a bounded BLE stream (defaults to stream_notifications).
StreamFn = Callable[..., Awaitable[StreamResult]]
# Resolve an address string to a connectable target (BLEDevice) or None.
ResolveFn = Callable[[str, float], Awaitable[object | None]]
ScanFn = Callable[[float], Awaitable[list[DeviceInfo]]]

_TIMEOUT_S = 8.0
_POLL_INTERVAL_S = 0.2


class RecordingActiveError(RuntimeError):
    """Raised when starting a recording while one is already active."""


class NoRecordingError(RuntimeError):
    """Raised when stopping with no active recording."""


@dataclass(frozen=True, slots=True)
class RecordingConfig:
    address: str = DEFAULT_ADDRESS
    duration_s: float = 300.0
    sample_hz: float = 1.0
    reconnect: bool = True
    notify_uuid: str = DEFAULT_NOTIFY_UUID
    session_name: str | None = None


class DeviceSession:
    """Single-device recording state machine wrapping the pulseox streamer.

    States: ``idle`` → ``recording`` → ``idle`` | ``error``. The streaming call is
    injected (``stream_fn``) so the manager is unit-testable without bleak.
    """

    def __init__(
        self,
        *,
        sessions_dir: Path,
        hub: SampleHub | None = None,
        stream_fn: StreamFn = stream_notifications,
        resolve_fn: ResolveFn = scan_for_device,
        scan_fn: ScanFn = scan_devices,
    ) -> None:
        self._sessions_dir = sessions_dir
        self.hub = hub if hub is not None else SampleHub()
        self._stream_fn = stream_fn
        self._resolve_fn = resolve_fn
        self._scan_fn = scan_fn

        self._status = "idle"
        self._stop = False
        self._task: asyncio.Task[None] | None = None
        self._config: RecordingConfig | None = None
        self._recorder: PulseOxCsvRecorder | None = None
        self._csv_file: TextIO | None = None
        self._session_file: str | None = None
        self._started_mono: float | None = None
        self._rows = 0
        self._reconnects = 0
        self._ended_reason: str | None = None
        self._error: str | None = None

    # -- public API ---------------------------------------------------------

    async def scan(self, timeout_s: float = 6.0) -> list[dict[str, object]]:
        devices = await self._scan_fn(timeout_s)
        return [
            {
                "address": d.address,
                "name": d.name,
                "rssi": d.rssi,
                "advertised_uuids": list(d.advertised_uuids),
            }
            for d in devices
        ]

    async def start(self, config: RecordingConfig) -> None:
        if self._status == "recording":
            raise RecordingActiveError("a recording is already in progress")

        name = config.session_name or self._default_name()
        path = self.safe_session_path(name)
        opened = open_csv_path(str(path), append=False, overwrite=True)

        self._recorder = PulseOxCsvRecorder(
            opened.file,
            write_header=opened.write_header,
            sample_hz=config.sample_hz,
            include_implausible=False,
            flush_every=10,
        )
        self._csv_file = opened.file
        self._session_file = path.name
        self._config = config
        self._stop = False
        self._rows = 0
        self._reconnects = 0
        self._ended_reason = None
        self._error = None
        self.hub.clear()
        self._started_mono = time.monotonic()
        self._status = "recording"
        self.hub.publish({"type": "status", **self.status_dict()})

        self._task = asyncio.create_task(self._run_recording(config))

    async def stop(self) -> None:
        if self._status != "recording":
            raise NoRecordingError("no recording in progress")
        self._stop = True
        await self.wait()

    async def wait(self) -> None:
        if self._task is not None:
            await self._task

    def status_dict(self) -> dict[str, object]:
        recorder = self._recorder
        live_rows = recorder.rows_written if recorder is not None else 0
        rows = live_rows if self._status == "recording" else self._rows
        elapsed = 0.0
        if self._started_mono is not None:
            elapsed = round(time.monotonic() - self._started_mono, 1)
        cfg = self._config
        return {
            "status": self._status,
            "address": cfg.address if cfg is not None else None,
            "duration_s": cfg.duration_s if cfg is not None else None,
            "elapsed_s": elapsed,
            "rows": rows,
            "reconnects": self._reconnects,
            "ended_reason": self._ended_reason,
            "session_file": self._session_file,
            "error": self._error,
        }

    def safe_session_path(self, name: str) -> Path:
        """Resolve ``name`` to a CSV path inside the sessions dir (guarded)."""
        if not name or "/" in name or "\\" in name or name.startswith(".") or ".." in name:
            raise ValueError(f"invalid session name: {name!r}")
        if not name.endswith(".csv"):
            name = f"{name}.csv"
        root = self._sessions_dir.resolve()
        path = (root / name).resolve()
        if root != path.parent:
            raise ValueError("session path escapes sessions dir")
        return path

    # -- internals ----------------------------------------------------------

    def _default_name(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"session_{stamp}.csv"

    async def _run_recording(self, config: RecordingConfig) -> None:
        recorder = self._recorder
        csv_file = self._csv_file
        if recorder is None or csv_file is None:  # pragma: no cover - set by start()
            raise RuntimeError("recording not initialized")

        def on_payload(sender: object, data: bytes) -> None:
            sample = recorder.on_notification(sender=sender, data=data)
            if sample is not None:
                self.hub.publish({"type": "sample", **sample})

        try:
            target = await self._resolve_fn(config.address, _TIMEOUT_S)
            if target is None:
                raise RuntimeError(f"device {config.address} not found")
            result = await self._stream_fn(
                target,
                notify_uuids=[config.notify_uuid],
                run_seconds=config.duration_s,
                max_notifications=0,
                poll_interval=_POLL_INTERVAL_S,
                timeout_s=_TIMEOUT_S,
                on_payload=on_payload,
                reconnect=config.reconnect,
                on_disconnect=recorder.flush,
                should_stop=lambda: self._stop,
            )
            self._reconnects = result.reconnects
            self._ended_reason = result.ended_reason
        except Exception as exc:  # noqa: BLE001 - surface any failure as error status
            self._error = repr(exc)
            self._ended_reason = "error"
        finally:
            recorder.flush()
            recorder.close()
            csv_file.close()
            self._rows = recorder.rows_written
            self._status = "error" if self._error is not None else "idle"
            self.hub.publish({"type": "status", **self.status_dict()})
