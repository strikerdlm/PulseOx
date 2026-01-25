from __future__ import annotations

import logging
import os
import sys
from typing import Final

_LEVELS: Final[dict[str, int]] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def configure_logging(*, level: str | None = None, debug: bool = False) -> str:
    """Configure process-wide logging to stderr.

    This repo is intentionally minimal and print-oriented for interactive CLI UX,
    but having structured logs (timestamps/levels/tracebacks) makes debugging BLE,
    Streamlit, and CSV issues dramatically easier.

    Logging level resolution (highest precedence first):
    - Explicit ``level`` argument
    - ``PULSEOX_LOG_LEVEL`` environment variable
    - ``DEBUG`` if ``debug=True`` else ``INFO``

    Args:
        level: A case-insensitive log level name (e.g. ``"INFO"``, ``"DEBUG"``).
        debug: Convenience flag to force ``DEBUG`` when no explicit/env level.

    Returns:
        The resolved uppercase log level name.

    Raises:
        ValueError: If the requested log level is unknown.
    """
    raw = (level or os.getenv("PULSEOX_LOG_LEVEL") or ("DEBUG" if debug else "INFO")).strip()
    resolved = raw.upper()
    if resolved not in _LEVELS:
        raise ValueError(f"Unknown log level: {raw!r}. Expected one of: {sorted(_LEVELS)}")

    # force=True ensures we don't accumulate duplicate handlers in Streamlit's
    # re-run model and still works fine for CLI execution.
    logging.basicConfig(
        level=_LEVELS[resolved],
        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )

    return resolved

