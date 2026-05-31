from __future__ import annotations

import csv
import io
import math
from collections import deque
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _require_nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _require_positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _require_nonnegative_finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise TypeError(f"{name} must be a float")
    fval = float(value)
    if not math.isfinite(fval) or fval < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return fval


def _parse_int_field(row: dict[str, str], name: str) -> int:
    raw = row.get(name)
    if raw is None:
        raise ValueError(f"Missing field: {name}")
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"Invalid int for {name}: {raw!r}") from e


def _parse_float_field(row: dict[str, str], name: str) -> float:
    raw = row.get(name)
    if raw is None:
        raise ValueError(f"Missing field: {name}")
    try:
        return float(raw)
    except ValueError as e:
        raise ValueError(f"Invalid float for {name}: {raw!r}") from e


def _parse_bool01_field(row: dict[str, str], name: str) -> bool:
    raw = row.get(name)
    if raw is None:
        raise ValueError(f"Missing field: {name}")
    if raw == "1":
        return True
    if raw == "0":
        return False
    raise ValueError(f"Invalid 0/1 for {name}: {raw!r}")


def _parse_iso8601_timestamp(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp_utc must be non-empty")
    try:
        # CSV uses `datetime.isoformat(timespec="milliseconds")`, e.g.:
        # 2026-01-23T17:21:44.433+00:00
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from e


@dataclass(frozen=True, slots=True)
class PulseOxSample:
    """One decoded CSV sample row.

    The schema matches `pulseox.record.CSV_FIELDNAMES`.
    """

    timestamp_utc: datetime
    elapsed_s: float
    sender: str
    spo2_percent: int
    pulse_bpm: int
    perfusion_index: int
    plausible: bool
    raw_frame_hex: str
    raw_notification_hex: str
    remainder_hex: str


def parse_samples_from_csv_text(
    csv_text: str,
    *,
    max_rows: int,
    only_plausible: bool,
) -> list[PulseOxSample]:
    """Parse up to `max_rows` samples from CSV text.

    This function is intentionally strict: malformed rows raise ValueError.
    Use it with already-recorded CSVs from `pulseox.record`.
    """
    _require_nonempty_str(csv_text, "csv_text")
    _require_positive_int(max_rows, "max_rows")

    fp = io.StringIO(csv_text)
    reader = csv.DictReader(fp)
    if not reader.fieldnames:
        raise ValueError("CSV is missing a header row")

    out: deque[PulseOxSample] = deque(maxlen=max_rows)
    for row in reader:
        # DictReader can return `None` keys on ragged rows; fail closed.
        if any(k is None for k in row):
            raise ValueError("CSV row has missing columns")

        plausible = _parse_bool01_field(row, "plausible")
        if only_plausible and not plausible:
            continue

        ts = row.get("timestamp_utc")
        if ts is None:
            raise ValueError("Missing field: timestamp_utc")

        sample = PulseOxSample(
            timestamp_utc=_parse_iso8601_timestamp(ts),
            elapsed_s=_require_nonnegative_finite(
                _parse_float_field(row, "elapsed_s"), "elapsed_s"
            ),
            sender=_require_nonempty_str(row.get("sender", ""), "sender"),
            spo2_percent=_parse_int_field(row, "spo2_percent"),
            pulse_bpm=_parse_int_field(row, "pulse_bpm"),
            perfusion_index=_parse_int_field(row, "perfusion_index"),
            plausible=plausible,
            raw_frame_hex=_require_nonempty_str(row.get("raw_frame_hex", ""), "raw_frame_hex"),
            raw_notification_hex=_require_nonempty_str(
                row.get("raw_notification_hex", ""), "raw_notification_hex"
            ),
            remainder_hex=row.get("remainder_hex", "") or "",
        )
        out.append(sample)

    return list(out)


def _iter_file_lines(path: Path) -> Iterator[str]:
    # Separated for testability/mocking.
    with path.open("r", encoding="utf-8", newline="") as f:
        yield from f


def read_csv_tail_text(path: str, *, max_data_rows: int) -> str:
    """Read CSV header + last N data rows as text.

    This is memory-bounded (keeps only N lines) and designed for dashboards
    that refresh frequently.
    """
    _require_nonempty_str(path, "path")
    _require_positive_int(max_data_rows, "max_data_rows")

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    if p.is_dir():
        raise IsADirectoryError(str(p))

    it = _iter_file_lines(p)
    try:
        header = next(it)
    except StopIteration as e:
        raise ValueError(f"CSV is empty: {p}") from e

    if not header.strip():
        raise ValueError(f"CSV header is blank: {p}")

    tail: deque[str] = deque(maxlen=max_data_rows)
    for line in it:
        # Keep raw line endings as read; StringIO handles both.
        if line.strip():
            tail.append(line)

    # Ensure header ends with exactly one newline to keep DictReader happy.
    header_norm = header.rstrip("\r\n") + "\n"
    data_text = "".join(tail)
    return header_norm + data_text


def load_recent_samples_from_path(
    path: str,
    *,
    max_rows: int,
    only_plausible: bool,
) -> list[PulseOxSample]:
    """Load recent samples from a CSV file path."""
    csv_text = read_csv_tail_text(path, max_data_rows=max_rows)
    # We can still get fewer than max_rows due to filtering.
    return parse_samples_from_csv_text(csv_text, max_rows=max_rows, only_plausible=only_plausible)


def latest_two(
    samples: Sequence[PulseOxSample],
) -> tuple[PulseOxSample | None, PulseOxSample | None]:
    """Return (latest, previous) samples from a list."""
    if not samples:
        return None, None
    if len(samples) == 1:
        return samples[-1], None
    return samples[-1], samples[-2]


def sample_to_dict(sample: PulseOxSample) -> dict[str, object]:
    """Serialize a sample to the PulseOxSample wire contract (frontend types)."""
    return {
        "timestamp_utc": sample.timestamp_utc.isoformat(timespec="milliseconds"),
        "elapsed_s": sample.elapsed_s,
        "sender": sample.sender,
        "spo2_percent": sample.spo2_percent,
        "pulse_bpm": sample.pulse_bpm,
        "perfusion_index": sample.perfusion_index,
        "plausible": sample.plausible,
        "raw_frame_hex": sample.raw_frame_hex,
        "raw_notification_hex": sample.raw_notification_hex,
        "remainder_hex": sample.remainder_hex,
    }


def samples_to_series(
    samples: Iterable[PulseOxSample],
) -> tuple[list[datetime], list[int], list[int]]:
    """Convert samples into (timestamps, spo2, hr) series for charting."""
    ts: list[datetime] = []
    spo2: list[int] = []
    hr: list[int] = []
    for s in samples:
        ts.append(s.timestamp_utc)
        spo2.append(s.spo2_percent)
        hr.append(s.pulse_bpm)
    return ts, spo2, hr
