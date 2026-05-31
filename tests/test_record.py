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


class _FlushSpy(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def test_recorder_time_based_flush() -> None:
    fp = _FlushSpy()
    # start=0.0, call1 now=0.0, call2 now=3.0 (>= 2.0s interval)
    clock = FakeClock([0.0, 0.0, 3.0])
    now_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1000,
        flush_interval_s=2.0,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now_dt,
    )

    frame = bytes([0xF1, 0x5C, 0x46])
    recorder.on_notification(sender=1, data=frame)  # now=0.0 -> no time flush
    after_first = fp.flush_count
    recorder.on_notification(sender=1, data=frame)  # now=3.0 -> time-based flush
    assert fp.flush_count > after_first


def test_on_notification_returns_typed_sample() -> None:
    fp = io.StringIO()
    clock = FakeClock([0.0, 0.0])
    now_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now_dt,
    )

    sample = recorder.on_notification(sender=11, data=bytes([0xF1, 0x5C, 0x46]))
    assert sample is not None
    assert sample["spo2_percent"] == 92
    assert sample["pulse_bpm"] == 70
    assert sample["perfusion_index"] == 0
    assert sample["plausible"] is True
    assert isinstance(sample["elapsed_s"], float)
    assert sample["timestamp_utc"] == now_dt.isoformat(timespec="milliseconds")


def test_on_notification_returns_none_when_skipped() -> None:
    fp = io.StringIO()
    clock = FakeClock([0.0, 0.0])
    now_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=True,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now_dt,
    )

    # F1 with pulse=0 is implausible -> skipped -> None.
    out = recorder.on_notification(sender=11, data=bytes([0xF1, 0x00, 0x00]))
    assert out is None


def test_recorder_flush_is_public_and_writes() -> None:
    fp = _FlushSpy()
    clock = FakeClock([0.0, 0.0])
    now_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    recorder = PulseOxCsvRecorder(
        fp,
        write_header=False,
        sample_hz=0.0,
        include_implausible=False,
        flush_every=1000,
        flush_interval_s=1000.0,
        monotonic_fn=clock.monotonic,
        now_utc_fn=lambda: now_dt,
    )
    recorder.on_notification(sender=1, data=bytes([0xF1, 0x5C, 0x46]))
    before = fp.flush_count
    recorder.flush()
    recorder.flush()
    assert fp.flush_count == before + 2
