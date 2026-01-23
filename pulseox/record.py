from __future__ import annotations

import csv
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pulseox.decode import DecodedFrame, decode_a340b_lk_notification, decode_payload, hexlify

# A340B-LK device-specific packet types observed on the notify characteristic.
_A340B_LK_NON_MEASUREMENT_PREFIXES = (0xF0, 0xF2)

CSV_FIELDNAMES: tuple[str, ...] = (
    "timestamp_utc",
    "elapsed_s",
    "sender",
    "spo2_percent",
    "pulse_bpm",
    "perfusion_index",
    "plausible",
    "raw_frame_hex",
    "raw_notification_hex",
    "remainder_hex",
)


def _require_nonnegative_finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise TypeError(f"{name} must be a float")
    fval = float(value)
    if not math.isfinite(fval) or fval < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return fval


def _require_positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _require_nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def format_sender(sender: object) -> str:
    """Best-effort formatting for Bleak notification sender across backends."""
    if isinstance(sender, int):
        return f"0x{sender:04x}"

    handle = getattr(sender, "handle", None)
    if isinstance(handle, int):
        return f"0x{handle:04x}"

    uuid = getattr(sender, "uuid", None)
    if isinstance(uuid, str) and uuid:
        return uuid

    return str(sender)


def _select_frame(
    frames: Sequence[DecodedFrame], *, include_implausible: bool
) -> DecodedFrame | None:
    if not frames:
        return None

    if include_implausible:
        return frames[-1]

    # Prefer the last plausible frame in the notification payload.
    for frame in reversed(frames):
        if frame.plausible:
            return frame

    return None


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CsvOpenResult:
    file: TextIO
    write_header: bool


def open_csv_path(path: str, *, append: bool, overwrite: bool) -> CsvOpenResult:
    """Open a CSV file for writing.

    Safety:
        If the file already exists, the caller must explicitly choose append
        or overwrite.

    Args:
        path: Output path.
        append: Append to an existing file.
        overwrite: Truncate/overwrite an existing file.

    Returns:
        CsvOpenResult containing the opened file handle and whether a header
        should be written.

    Raises:
        ValueError: invalid argument combinations
        FileExistsError: if file exists and neither append nor overwrite is set
        IsADirectoryError: if path is a directory
        FileNotFoundError: if the parent directory does not exist
    """
    _require_nonempty_str(path, "path")
    if append and overwrite:
        raise ValueError("append and overwrite are mutually exclusive")

    p = Path(path)

    parent = p.parent
    if parent != Path() and not parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {parent}")

    if p.exists() and p.is_dir():
        raise IsADirectoryError(str(p))

    if p.exists() and not (append or overwrite):
        raise FileExistsError(f"Refusing to overwrite existing file: {p}")

    if overwrite:
        mode = "w"
        write_header = True
    elif append:
        mode = "a"
        write_header = (not p.exists()) or (p.stat().st_size == 0)
    else:
        # New file.
        mode = "w"
        write_header = True

    fp = p.open(mode, encoding="utf-8", newline="")
    return CsvOpenResult(file=fp, write_header=write_header)


class PulseOxCsvRecorder:
    """Rate-limited CSV recorder for decoded pulse oximeter frames."""

    def __init__(
        self,
        file: TextIO,
        *,
        write_header: bool,
        sample_hz: float,
        include_implausible: bool,
        flush_every: int,
        monotonic_fn: Callable[[], float] = time.monotonic,
        now_utc_fn: Callable[[], datetime] = _now_utc,
    ) -> None:
        self._file = file
        self._monotonic = monotonic_fn
        self._now_utc = now_utc_fn

        self._sample_hz = _require_nonnegative_finite(sample_hz, "sample_hz")
        self._include_implausible = bool(include_implausible)
        self._flush_every = _require_positive_int(flush_every, "flush_every")

        self._min_interval_s = 0.0 if self._sample_hz == 0.0 else (1.0 / self._sample_hz)
        self._start_mono = self._monotonic()
        self._last_write_mono: float | None = None
        self._rows_since_flush = 0
        self._rows_written = 0

        self._writer = csv.DictWriter(file, fieldnames=list(CSV_FIELDNAMES))
        if write_header:
            self._writer.writeheader()
            self._file.flush()

    @property
    def rows_written(self) -> int:
        return self._rows_written

    def close(self) -> None:
        """Flush buffered rows (does not close the underlying file)."""
        self._file.flush()
        self._rows_since_flush = 0

    def on_notification(self, *, sender: object, data: bytes) -> None:
        """Handle one BLE notification payload.

        This method is synchronous and designed to be used as a Bleak
        notification callback.
        """
        now_mono = self._monotonic()
        if self._min_interval_s > 0 and self._last_write_mono is not None:
            if (now_mono - self._last_write_mono) < self._min_interval_s:
                return

        payload = bytes(data)

        # Prefer the A340B-LK measurement packet (0xF1 ...) when present.
        selected: DecodedFrame | None = None
        remainder: bytes = b""

        frame = decode_a340b_lk_notification(payload)
        if frame is not None:
            if frame.plausible or self._include_implausible:
                selected = frame
                remainder = b""
            else:
                return
        else:
            # On A340B-LK, other high-rate packets (e.g., 0xF0 waveform-like)
            # can look like plausible 5-byte frames but do not represent
            # SpO2/HR measurements. Skip them to avoid garbage CSV rows.
            if payload and payload[0] in _A340B_LK_NON_MEASUREMENT_PREFIXES and len(payload) != 5:
                return

            decoded, remainder = decode_payload(payload)
            selected = _select_frame(decoded, include_implausible=self._include_implausible)
            if selected is None:
                return

        ts = self._now_utc().isoformat(timespec="milliseconds")
        elapsed_s = now_mono - self._start_mono

        remainder_hex = hexlify(remainder) if remainder else ""

        row: dict[str, str] = {
            "timestamp_utc": ts,
            "elapsed_s": f"{elapsed_s:.6f}",
            "sender": format_sender(sender),
            "spo2_percent": str(selected.spo2_percent),
            "pulse_bpm": str(selected.pulse_bpm),
            "perfusion_index": str(selected.perfusion_index),
            "plausible": "1" if selected.plausible else "0",
            "raw_frame_hex": hexlify(selected.raw),
            "raw_notification_hex": hexlify(data),
            "remainder_hex": remainder_hex,
        }

        self._writer.writerow(row)
        self._rows_written += 1
        self._rows_since_flush += 1
        self._last_write_mono = now_mono

        if self._rows_since_flush >= self._flush_every:
            self._file.flush()
            self._rows_since_flush = 0
