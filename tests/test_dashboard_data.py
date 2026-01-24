from __future__ import annotations

from pathlib import Path

import pytest

from pulseox.dashboard_data import (
    latest_two,
    load_recent_samples_from_path,
    parse_samples_from_csv_text,
    read_csv_tail_text,
)


def test_read_csv_tail_text_includes_header_and_last_rows(tmp_path: Path) -> None:
    p = tmp_path / "session.csv"
    p.write_text(
        "a,b\n" "1,x\n" "2,y\n" "3,z\n",
        encoding="utf-8",
    )

    tail = read_csv_tail_text(str(p), max_data_rows=2)
    assert tail.splitlines()[0] == "a,b"
    assert tail.splitlines()[1:] == ["2,y", "3,z"]


def test_parse_samples_from_csv_text_filters_implausible() -> None:
    csv_text = (
        "timestamp_utc,elapsed_s,sender,spo2_percent,pulse_bpm,perfusion_index,plausible,"
        "raw_frame_hex,raw_notification_hex,remainder_hex\n"
        "2026-01-23T17:21:44.433+00:00,1.0,0x000b,90,65,0,1,aa,bb,\n"
        "2026-01-23T17:21:45.433+00:00,2.0,0x000b,10,5,0,0,cc,dd,\n"
    )
    samples = parse_samples_from_csv_text(csv_text, max_rows=10, only_plausible=True)
    assert len(samples) == 1
    assert samples[0].spo2_percent == 90


def test_load_recent_samples_from_path_and_latest_two(tmp_path: Path) -> None:
    p = tmp_path / "pulse.csv"
    p.write_text(
        "timestamp_utc,elapsed_s,sender,spo2_percent,pulse_bpm,perfusion_index,plausible,"
        "raw_frame_hex,raw_notification_hex,remainder_hex\n"
        "2026-01-23T17:21:44.433+00:00,1.0,0x000b,90,65,0,1,aa,bb,\n"
        "2026-01-23T17:21:45.433+00:00,2.0,0x000b,91,66,0,1,cc,dd,\n",
        encoding="utf-8",
    )
    samples = load_recent_samples_from_path(str(p), max_rows=50, only_plausible=True)
    latest, prev = latest_two(samples)
    assert latest is not None
    assert prev is not None
    assert latest.spo2_percent == 91
    assert prev.spo2_percent == 90


def test_read_csv_tail_text_errors_on_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV is empty"):
        _ = read_csv_tail_text(str(p), max_data_rows=10)
