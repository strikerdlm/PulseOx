# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# NOTE: Starlette TestClient wraps httpx, whose response methods (.json/.post/
# .status_code) are typed as Unknown under pyright strict. Relax that noise here.
from pathlib import Path

from fastapi.testclient import TestClient

from pulseox.record import CSV_FIELDNAMES
from pulseox.streaming import StreamResult
from pulseox_server.app import create_app
from pulseox_server.session import DeviceSession

_SAMPLE_FRAME = bytes([0xF1, 0x62, 0x46])  # spo2=0x62(98) pulse=0x46(70)


async def _fake_resolve(address: str, timeout_s: float) -> object:
    return address


async def _emit_one_wait_stop(
    target: object,
    *,
    on_payload: object,
    should_stop: object,
    **_kw: object,
) -> StreamResult:
    import asyncio

    assert callable(on_payload)
    assert callable(should_stop)
    on_payload(11, _SAMPLE_FRAME)
    while not should_stop():
        await asyncio.sleep(0.005)
    return StreamResult(("u",), (), 0, 0.0, "stopped")


def _make_client(tmp_path: Path) -> TestClient:
    sess = DeviceSession(
        sessions_dir=tmp_path,
        stream_fn=_emit_one_wait_stop,
        resolve_fn=_fake_resolve,
    )
    # Context-manager use keeps the event loop alive so the background
    # recording task progresses between requests.
    return TestClient(create_app(session=sess, sessions_dir=tmp_path))


def _write_csv(path: Path) -> None:
    header = ",".join(CSV_FIELDNAMES)
    row = "2026-01-01T00:00:00.000+00:00,0.000000,0x000b,98,70,0,1,f1-62-46,f1-62-46,"
    path.write_text(f"{header}\n{row}\n", encoding="utf-8")


def test_health_and_status(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/status").json()["status"] == "idle"


def test_start_then_stop(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        r = client.post(
            "/api/recording/start",
            json={"address": "X", "duration_s": 100.0, "sample_hz": 0.0, "session_name": "r1"},
        )
        assert r.status_code == 202
        assert r.json()["status"] == "recording"

        s = client.post("/api/recording/stop")
        assert s.status_code == 200
        body = s.json()
        assert body["status"] == "idle"
        assert body["ended_reason"] == "stopped"
        assert (tmp_path / "r1.csv").exists()


def test_double_start_conflicts(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        client.post(
            "/api/recording/start",
            json={"address": "X", "duration_s": 100.0, "session_name": "d1"},
        )
        again = client.post(
            "/api/recording/start",
            json={"address": "X", "duration_s": 100.0, "session_name": "d2"},
        )
        assert again.status_code == 409
        client.post("/api/recording/stop")


def test_stop_when_idle_conflicts(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        assert client.post("/api/recording/stop").status_code == 409


def test_sessions_list_and_get(tmp_path: Path) -> None:
    _write_csv(tmp_path / "existing.csv")
    with _make_client(tmp_path) as client:
        listing = client.get("/api/sessions").json()
        names = [s["name"] for s in listing["sessions"]]
        assert "existing.csv" in names

        got = client.get("/api/sessions/existing.csv").json()
        assert got["metadata"]["returnedRows"] == 1
        sample = got["samples"][0]
        assert sample["spo2_percent"] == 98
        assert sample["pulse_bpm"] == 70
        assert sample["plausible"] is True


def test_get_missing_session_404(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        assert client.get("/api/sessions/nope.csv").status_code == 404


def test_session_analysis(tmp_path: Path) -> None:
    header = ",".join(CSV_FIELDNAMES)
    rows = "\n".join(
        f"2026-01-01T00:00:{s:02d}.000+00:00,{float(s):.6f},0x000b,{spo2},70,0,1,f1,f1,"
        for s, spo2 in enumerate([95, 95, 88, 88, 90])
    )
    (tmp_path / "an.csv").write_text(f"{header}\n{rows}\n", encoding="utf-8")
    with _make_client(tmp_path) as client:
        body = client.get("/api/sessions/an.csv/analysis").json()
        assert body["n_samples"] == 5
        assert body["spo2"]["min"] == 88
        assert body["t90_s"] >= 0
        assert "odi_available" in body


def test_upload_csv(tmp_path: Path) -> None:
    header = ",".join(CSV_FIELDNAMES)
    row = "2026-01-01T00:00:00.000+00:00,0.000000,0x000b,97,72,0,1,f1-61-48,f1-61-48,"
    content = f"{header}\n{row}\n".encode()
    with _make_client(tmp_path) as client:
        r = client.post("/api/upload", files={"file": ("up.csv", content, "text/csv")})
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "up.csv"
        assert body["samples"][0]["spo2_percent"] == 97
        assert (tmp_path / "up.csv").exists()


def test_ws_streams_sample(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        start = client.post(
            "/api/recording/start",
            json={
                "address": "X",
                "duration_s": 100.0,
                "sample_hz": 0.0,
                "session_name": "ws1",
            },
        )
        assert start.status_code == 202

        with client.websocket_connect("/ws/stream") as ws:
            got_sample = False
            for _ in range(12):
                frame = ws.receive_json()
                if frame.get("type") == "sample":
                    assert frame["spo2_percent"] == 98
                    got_sample = True
                    break
            assert got_sample

        client.post("/api/recording/stop")
