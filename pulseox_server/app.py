# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnusedFunction=false
# pyright: reportUntypedFunctionDecorator=false, reportUnknownParameterType=false
# NOTE: FastAPI/Starlette route decorators and WebSocket I/O carry partial type
# information under pyright strict; relax only the framework-noise rules here
# (mirroring pulseox_reflex/app.py). The core logic stays fully typed.
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pulseox.dashboard_data import load_recent_samples_from_path, sample_to_dict
from pulseox_server.config import (
    ALLOWED_ORIGINS,
    DEFAULT_ADDRESS,
    DEFAULT_NOTIFY_UUID,
    get_sessions_dir,
)
from pulseox_server.session import (
    DeviceSession,
    NoRecordingError,
    RecordingActiveError,
    RecordingConfig,
)

_BACKLOG_FRAMES = 300
_WS_POLL_S = 0.2


class StartRequest(BaseModel):
    address: str = DEFAULT_ADDRESS
    duration_s: float = 300.0
    sample_hz: float = 1.0
    reconnect: bool = True
    notify_uuid: str = DEFAULT_NOTIFY_UUID
    session_name: str | None = None


class ScanRequest(BaseModel):
    timeout_s: float = 6.0


def create_app(  # noqa: C901 - FastAPI route handlers are nested by design
    *,
    session: DeviceSession | None = None,
    sessions_dir: Path | None = None,
) -> FastAPI:
    sdir = sessions_dir if sessions_dir is not None else get_sessions_dir()
    sess = session if session is not None else DeviceSession(sessions_dir=sdir)

    app = FastAPI(title="PulseOx backend", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/status")
    async def status() -> dict[str, object]:
        return sess.status_dict()

    @app.post("/api/scan")
    async def scan(req: ScanRequest) -> dict[str, object]:
        return {"devices": await sess.scan(req.timeout_s)}

    @app.post("/api/recording/start", status_code=202)
    async def start(req: StartRequest) -> dict[str, object]:
        try:
            await sess.start(RecordingConfig(**req.model_dump()))
        except RecordingActiveError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return sess.status_dict()

    @app.post("/api/recording/stop")
    async def stop() -> dict[str, object]:
        try:
            await sess.stop()
        except NoRecordingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return sess.status_dict()

    @app.get("/api/sessions")
    async def sessions() -> dict[str, object]:
        items: list[dict[str, object]] = []
        for path in sorted(sdir.glob("*.csv")):
            stat = path.stat()
            items.append(
                {"name": path.name, "size": stat.st_size, "modified": stat.st_mtime}
            )
        return {"sessions": items}

    @app.get("/api/sessions/{name}")
    async def get_session(
        name: str,
        max_rows: int = Query(500, alias="maxRows"),
        only_plausible: bool = Query(True, alias="onlyPlausible"),
    ) -> dict[str, object]:
        path = _resolve_or_400(sess, name)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"session not found: {name}")
        samples = load_recent_samples_from_path(
            str(path), max_rows=max_rows, only_plausible=only_plausible
        )
        return {
            "samples": [sample_to_dict(s) for s in samples],
            "metadata": {"name": path.name, "returnedRows": len(samples)},
        }

    @app.post("/api/upload")
    async def upload(file: UploadFile) -> dict[str, object]:
        raw_name = Path(file.filename or "upload.csv").name
        path = _resolve_or_400(sess, raw_name)
        content = await file.read()
        path.write_bytes(content)
        samples = load_recent_samples_from_path(
            str(path), max_rows=500, only_plausible=True
        )
        return {
            "name": path.name,
            "samples": [sample_to_dict(s) for s in samples],
            "metadata": {"returnedRows": len(samples)},
        }

    @app.websocket("/ws/stream")
    async def ws_stream(ws: WebSocket) -> None:
        await ws.accept()
        latest, backlog = sess.hub.backlog(_BACKLOG_FRAMES)
        try:
            for frame in backlog:
                await ws.send_json(frame)
            await ws.send_json({"type": "status", **sess.status_dict()})
            cursor = latest
            while True:
                cursor, frames = sess.hub.since(cursor)
                for frame in frames:
                    await ws.send_json(frame)
                await asyncio.sleep(_WS_POLL_S)
        except WebSocketDisconnect:
            return

    return app


def _resolve_or_400(sess: DeviceSession, name: str) -> Path:
    try:
        return sess.safe_session_path(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
