from __future__ import annotations

import os
from pathlib import Path

# Diego's real device (LPOW A340B-LK) — keep as the default everywhere.
DEFAULT_ADDRESS = "FF:FF:FF:FF:00:21"
DEFAULT_NOTIFY_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"

HOST = "127.0.0.1"
PORT = 8000

# Frontend dev origin allowed for CORS / WebSocket.
ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def get_sessions_dir() -> Path:
    """Directory where recorded session CSVs live (env-overridable)."""
    raw = os.environ.get("PULSEOX_SESSIONS_DIR", "").strip()
    path = Path(raw) if raw else Path("sessions")
    path.mkdir(parents=True, exist_ok=True)
    return path
