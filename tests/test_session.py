import asyncio
from collections.abc import Sequence
from pathlib import Path

import pytest

from pulseox.streaming import StreamResult
from pulseox_server.session import (
    DeviceSession,
    NoRecordingError,
    RecordingActiveError,
    RecordingConfig,
)


async def _fake_resolve(address: str, timeout_s: float) -> object:
    return address


async def _fake_resolve_none(address: str, timeout_s: float) -> object | None:
    return None


def _f1_frame() -> bytes:
    # 0xF1 spo2=0x5C(92) pulse=0x46(70) -> plausible
    return bytes([0xF1, 0x5C, 0x46])


async def _fake_stream_three(
    target: object,
    *,
    notify_uuids: Sequence[str],
    run_seconds: float,
    max_notifications: int,
    poll_interval: float,
    timeout_s: float,
    on_payload: object,
    reconnect: bool,
    on_disconnect: object,
    should_stop: object,
) -> StreamResult:
    assert callable(on_payload)
    for _ in range(3):
        on_payload(11, _f1_frame())
    return StreamResult(("u",), (), 0, 0.0, "deadline")


async def _fake_stream_until_stop(
    target: object,
    *,
    notify_uuids: Sequence[str],
    run_seconds: float,
    max_notifications: int,
    poll_interval: float,
    timeout_s: float,
    on_payload: object,
    reconnect: bool,
    on_disconnect: object,
    should_stop: object,
) -> StreamResult:
    assert callable(on_payload)
    assert callable(should_stop)
    i = 0
    while not should_stop() and i < 1000:
        on_payload(11, _f1_frame())
        await asyncio.sleep(0)
        i += 1
    return StreamResult(("u",), (), 0, 0.0, "stopped")


async def _fake_stream_raises(
    target: object,
    *,
    notify_uuids: Sequence[str],
    run_seconds: float,
    max_notifications: int,
    poll_interval: float,
    timeout_s: float,
    on_payload: object,
    reconnect: bool,
    on_disconnect: object,
    should_stop: object,
) -> StreamResult:
    raise RuntimeError("boom")


def test_session_records_and_publishes(tmp_path: Path) -> None:
    async def go() -> None:
        session = DeviceSession(
            sessions_dir=tmp_path,
            stream_fn=_fake_stream_three,
            resolve_fn=_fake_resolve,
        )
        await session.start(
            RecordingConfig(address="X", duration_s=5.0, sample_hz=0.0, session_name="t1")
        )
        await session.wait()
        st = session.status_dict()
        assert st["status"] == "idle"
        assert st["ended_reason"] == "deadline"
        assert st["rows"] == 3
        _latest, frames = session.hub.since(0)
        samples = [f for f in frames if f["type"] == "sample"]
        assert len(samples) == 3
        assert samples[0]["spo2_percent"] == 92
        assert (tmp_path / "t1.csv").exists()

    asyncio.run(go())


def test_session_stop_is_cooperative(tmp_path: Path) -> None:
    async def go() -> None:
        session = DeviceSession(
            sessions_dir=tmp_path,
            stream_fn=_fake_stream_until_stop,
            resolve_fn=_fake_resolve,
        )
        await session.start(
            RecordingConfig(address="X", duration_s=100.0, sample_hz=0.0, session_name="t2")
        )
        await asyncio.sleep(0)
        await session.stop()
        st = session.status_dict()
        assert st["status"] == "idle"
        assert st["ended_reason"] == "stopped"

    asyncio.run(go())


def test_session_double_start_rejected(tmp_path: Path) -> None:
    async def go() -> None:
        session = DeviceSession(
            sessions_dir=tmp_path,
            stream_fn=_fake_stream_until_stop,
            resolve_fn=_fake_resolve,
        )
        await session.start(
            RecordingConfig(address="X", duration_s=100.0, session_name="t3")
        )
        with pytest.raises(RecordingActiveError):
            await session.start(
                RecordingConfig(address="X", duration_s=100.0, session_name="t3b")
            )
        await session.stop()

    asyncio.run(go())


def test_session_stop_without_recording_raises(tmp_path: Path) -> None:
    async def go() -> None:
        session = DeviceSession(
            sessions_dir=tmp_path,
            stream_fn=_fake_stream_three,
            resolve_fn=_fake_resolve,
        )
        with pytest.raises(NoRecordingError):
            await session.stop()

    asyncio.run(go())


def test_session_error_status(tmp_path: Path) -> None:
    async def go() -> None:
        session = DeviceSession(
            sessions_dir=tmp_path,
            stream_fn=_fake_stream_raises,
            resolve_fn=_fake_resolve,
        )
        await session.start(
            RecordingConfig(address="X", duration_s=5.0, session_name="t4")
        )
        await session.wait()
        st = session.status_dict()
        assert st["status"] == "error"
        assert "boom" in str(st["error"])

    asyncio.run(go())


def test_session_device_not_found(tmp_path: Path) -> None:
    async def go() -> None:
        session = DeviceSession(
            sessions_dir=tmp_path,
            stream_fn=_fake_stream_three,
            resolve_fn=_fake_resolve_none,
        )
        await session.start(
            RecordingConfig(address="X", duration_s=5.0, session_name="t5")
        )
        await session.wait()
        st = session.status_dict()
        assert st["status"] == "error"

    asyncio.run(go())


def test_safe_session_path_rejects_traversal(tmp_path: Path) -> None:
    session = DeviceSession(sessions_dir=tmp_path)
    for bad in ("../escape", "a/b", "..", ".hidden"):
        with pytest.raises(ValueError):
            session.safe_session_path(bad)
    good = session.safe_session_path("ok")
    assert good.name == "ok.csv"
    assert good.parent == tmp_path.resolve()
