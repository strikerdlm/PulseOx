from datetime import UTC, datetime, timedelta

from pulseox.analysis import analyze_samples
from pulseox.dashboard_data import PulseOxSample

_BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


def _mk(elapsed: float, spo2: int, hr: int = 70) -> PulseOxSample:
    return PulseOxSample(
        timestamp_utc=_BASE + timedelta(seconds=elapsed),
        elapsed_s=float(elapsed),
        sender="0x000b",
        spo2_percent=spo2,
        pulse_bpm=hr,
        perfusion_index=0,
        plausible=True,
        raw_frame_hex="f1",
        raw_notification_hex="f1",
        remainder_hex="",
    )


def test_t90_integrates_over_time_and_excludes_gaps() -> None:
    # 0..9 at 1 Hz: first five SpO2=95, next five SpO2=88 (below 90).
    # Then a 30 s reconnect gap, then 40,41,42 at 95.
    samples = (
        [_mk(t, 95) for t in range(5)]
        + [_mk(t, 88) for t in range(5, 10)]
        + [_mk(40, 95), _mk(41, 95), _mk(42, 95)]
    )
    a = analyze_samples(samples)

    # Below-90 intervals are i=5,6,7,8 (dt=1 each); i=9's interval is the 30 s
    # gap and must be excluded, not counted as 30 s at 88.
    assert a.t90_s == 4.0
    # Recorded time excludes the gap: 11 one-second intervals.
    assert a.recorded_s == 11.0
    assert abs(a.pct_below_90 - (4.0 / 11.0 * 100)) < 1e-6
    assert a.spo2_min == 88


def test_odi_suppressed_for_coarse_sampling() -> None:
    # 0.2 Hz (every 5 s) — too coarse for ODI.
    samples = [_mk(t, 96 if t % 10 else 90) for t in range(0, 100, 5)]
    a = analyze_samples(samples)
    assert a.odi is None
    assert a.odi_available is False
    assert a.odi_reason is not None
    assert a.events == ()


def test_odi_counts_events_at_adequate_rate() -> None:
    # 1 Hz, baseline 97, two ~10 s desaturations to 90 (drop 7 ≥ 4).
    spo2: list[int] = []
    for t in range(120):
        if 20 <= t <= 30 or 60 <= t <= 70:
            spo2.append(90)
        else:
            spo2.append(97)
    samples = [_mk(t, spo2[t]) for t in range(120)]
    a = analyze_samples(samples)

    assert a.odi_available is True
    assert len(a.events) == 2
    assert a.events[0].nadir == 90
    assert a.events[0].drop >= 4
    assert a.odi is not None and a.odi > 0


def test_basic_stats_and_zones() -> None:
    samples = [_mk(t, 90 + (t % 5)) for t in range(10)]  # 90..94 cycling, 1 Hz
    a = analyze_samples(samples)
    assert a.spo2_min == 90
    assert a.spo2_max == 94
    assert a.n_samples == 10
    assert abs(sum(a.zone_pct.values()) - 100.0) < 1e-6


def test_degenerate_inputs() -> None:
    assert analyze_samples([]).n_samples == 0
    one = analyze_samples([_mk(0, 97)])
    assert one.n_samples == 1
    assert one.recorded_s == 0.0
    assert one.odi_available is False
