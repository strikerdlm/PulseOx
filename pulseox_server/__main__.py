# pyright: reportUnknownMemberType=false
from __future__ import annotations

import uvicorn

from pulseox_server.app import create_app
from pulseox_server.config import HOST, PORT


def main() -> None:
    app = create_app()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
