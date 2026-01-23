import csv
import io
from collections.abc import Sequence
from datetime import UTC, datetime

from pulseox.record import CSV_FIELDNAMES, PulseOxCsvRecorder


class FakeClock:
    def __init__(self, times: Sequence[float]) -> None:
        if not times:
            raise ValueError("times must be non-empty")
        self._times = list(times)
        self._idx = 0

    def monotonic(self) -> float:
        if self._idx >= len(self._times):
            return self._times[-1]
        t = self._times[self._idx]
        self._idx += 1
        return t


def test_csv_rate_limiting_records_at_most_sample_hz() -> None:
    fp = io.StringIO()
    clock = FakeClock([0.0, 0.0, 0.1, 1.0])
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=1.0,
        include_implausible=False,
        flush_every=1,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now,
    )

    frame = bytes([0x0A, 0x00, 0x00, 60, 98])

    recorder.on_notification(sender=11, data=frame)
    recorder.on_notification(sender=11, data=frame)
    recorder.on_notification(sender=11, data=frame)

    fp.seek(0)
    rows = list(csv.DictReader(fp))

    assert rows
    assert list(rows[0].keys()) == list(CSV_FIELDNAMES)
    assert len(rows) == 2
    assert abs(float(rows[0]["elapsed_s"]) - 0.0) < 1e-6
    assert abs(float(rows[1]["elapsed_s"]) - 1.0) < 1e-6


def test_csv_skips_implausible_by_default() -> None:
    fp = io.StringIO()
    clock = FakeClock([0.0, 0.0])
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now,
    )

    # Pulse < 20 bpm => implausible.
    implausible = bytes([0x0A, 0x00, 0x00, 4, 3])
    recorder.on_notification(sender=11, data=implausible)

    fp.seek(0)
    rows = list(csv.DictReader(fp))

    assert rows == []


def test_csv_selects_last_plausible_frame_in_notification() -> None:
    fp = io.StringIO()
    clock = FakeClock([0.0, 0.0])
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now,
    )

    implausible = bytes([0x0A, 0x00, 0x00, 4, 3])
    plausible = bytes([0x0A, 0x00, 0x00, 60, 98])
    payload = implausible + plausible + b"\xaa"

    recorder.on_notification(sender=11, data=payload)

    fp.seek(0)
    rows = list(csv.DictReader(fp))

    assert len(rows) == 1
    assert rows[0]["spo2_percent"] == "98"
    assert rows[0]["pulse_bpm"] == "60"
    assert rows[0]["perfusion_index"] == "10"
    assert rows[0]["plausible"] == "1"
    assert rows[0]["remainder_hex"] == "aa"


def test_csv_records_a340b_lk_f1_measurement() -> None:
    fp = io.StringIO()
    clock = FakeClock([0.0, 0.0])
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now,
    )

    payload = bytes([0xF1, 0x5C, 0x46, 0x00, 0x5B, 0x03, 0xF0])
    recorder.on_notification(sender=11, data=payload)

    fp.seek(0)
    rows = list(csv.DictReader(fp))

    assert len(rows) == 1
    assert rows[0]["spo2_percent"] == "92"
    assert rows[0]["pulse_bpm"] == "70"
    assert rows[0]["perfusion_index"] == "0"
    assert rows[0]["plausible"] == "1"
    assert rows[0]["raw_frame_hex"] == "f1-5c-46-00-5b-03-f0"
    assert rows[0]["raw_notification_hex"] == "f1-5c-46-00-5b-03-f0"
    assert rows[0]["remainder_hex"] == ""


def test_csv_skips_a340b_lk_non_measurement_packets() -> None:
    fp = io.StringIO()
    clock = FakeClock([0.0, 0.0, 1.0])
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=True,
        flush_every=1,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now,
    )

    # High-rate packets starting with 0xF0/0xF2 should not create garbage rows.
    recorder.on_notification(sender=11, data=bytes([0xF0, 0x00, 0x00, 0x00, 0x00, 0x00]))
    recorder.on_notification(sender=11, data=bytes([0xF2, 0x41, 0x33, 0x34, 0x30, 0x42]))

    fp.seek(0)
    rows = list(csv.DictReader(fp))
    assert rows == []
