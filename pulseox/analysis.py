from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from pulseox.dashboard_data import PulseOxSample

# Thresholds / definitions (see docs/superpowers/specs/2026-05-31-analysis-export-design.md).
_T90 = 90
_T88 = 88
_DESAT_DROP = 4.0
_BASELINE_WINDOW_S = 60.0
_MIN_EVENT_S = 8.0
_ODI_MAX_MEDIAN_DT_S = 1.5
_GAP_FACTOR = 3.0
_GAP_FLOOR_S = 2.0

# SpO2 clinical zones (name, lo inclusive, hi exclusive). Mirrors the frontend.
_SPO2_ZONES: tuple[tuple[str, int, int], ...] = (
    ("Severe", 0, 88),
    ("Hypoxemia", 88, 92),
    ("Borderline", 92, 95),
    ("Normal", 95, 101),
)


@dataclass(frozen=True, slots=True)
class DesaturationEvent:
    start_s: float
    end_s: float
    duration_s: float
    nadir: int
    drop: float


@dataclass(frozen=True, slots=True)
class SessionAnalysis:
    n_samples: int
    recorded_s: float
    span_s: float
    effective_hz: float
    spo2_mean: float
    spo2_median: float
    spo2_min: int
    spo2_max: int
    spo2_std: float
    hr_mean: float
    hr_median: float
    hr_min: int
    hr_max: int
    hr_std: float
    t90_s: float
    t88_s: float
    pct_below_90: float
    pct_below_88: float
    zone_seconds: dict[str, float]
    zone_pct: dict[str, float]
    odi: float | None
    odi_available: bool
    odi_reason: str | None
    events: tuple[DesaturationEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "n_samples": self.n_samples,
            "recorded_s": round(self.recorded_s, 3),
            "span_s": round(self.span_s, 3),
            "effective_hz": round(self.effective_hz, 3),
            "spo2": {
                "mean": round(self.spo2_mean, 2),
                "median": self.spo2_median,
                "min": self.spo2_min,
                "max": self.spo2_max,
                "std": round(self.spo2_std, 2),
            },
            "hr": {
                "mean": round(self.hr_mean, 2),
                "median": self.hr_median,
                "min": self.hr_min,
                "max": self.hr_max,
                "std": round(self.hr_std, 2),
            },
            "t90_s": round(self.t90_s, 2),
            "t88_s": round(self.t88_s, 2),
            "pct_below_90": round(self.pct_below_90, 2),
            "pct_below_88": round(self.pct_below_88, 2),
            "zone_seconds": {k: round(v, 2) for k, v in self.zone_seconds.items()},
            "zone_pct": {k: round(v, 2) for k, v in self.zone_pct.items()},
            "odi": None if self.odi is None else round(self.odi, 2),
            "odi_available": self.odi_available,
            "odi_reason": self.odi_reason,
            "events": [
                {
                    "start_s": round(e.start_s, 2),
                    "end_s": round(e.end_s, 2),
                    "duration_s": round(e.duration_s, 2),
                    "nadir": e.nadir,
                    "drop": round(e.drop, 2),
                }
                for e in self.events
            ],
        }


def _zone_name(value: int) -> str:
    for name, lo, hi in _SPO2_ZONES:
        if lo <= value < hi:
            return name
    return _SPO2_ZONES[-1][0] if value >= _SPO2_ZONES[-1][1] - 1 else _SPO2_ZONES[0][0]


def _std(values: Sequence[int]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _baseline_max(elapsed: Sequence[float], spo2: Sequence[int], i: int) -> int:
    """Max SpO₂ over the preceding baseline window, inclusive of sample i."""
    t_hi = elapsed[i]
    t_lo = t_hi - _BASELINE_WINDOW_S
    return max(spo2[j] for j in range(len(spo2)) if t_lo < elapsed[j] <= t_hi)


def _detect_desaturations(
    elapsed: Sequence[float], spo2: Sequence[int]
) -> tuple[DesaturationEvent, ...]:
    n = len(spo2)
    in_event = [spo2[i] <= _baseline_max(elapsed, spo2, i) - _DESAT_DROP for i in range(n)]

    events: list[DesaturationEvent] = []
    i = 0
    while i < n:
        if not in_event[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and in_event[j + 1]:
            j += 1
        duration = elapsed[j] - elapsed[i]
        if duration >= _MIN_EVENT_S:
            nadir = min(spo2[i : j + 1])
            baseline = _baseline_max(elapsed, spo2, i)
            events.append(
                DesaturationEvent(
                    start_s=elapsed[i],
                    end_s=elapsed[j],
                    duration_s=duration,
                    nadir=nadir,
                    drop=float(baseline - nadir),
                )
            )
        i = j + 1
    return tuple(events)


def _empty() -> SessionAnalysis:
    zeros = {name: 0.0 for name, _, _ in _SPO2_ZONES}
    return SessionAnalysis(
        n_samples=0,
        recorded_s=0.0,
        span_s=0.0,
        effective_hz=0.0,
        spo2_mean=0.0,
        spo2_median=0.0,
        spo2_min=0,
        spo2_max=0,
        spo2_std=0.0,
        hr_mean=0.0,
        hr_median=0.0,
        hr_min=0,
        hr_max=0,
        hr_std=0.0,
        t90_s=0.0,
        t88_s=0.0,
        pct_below_90=0.0,
        pct_below_88=0.0,
        zone_seconds=dict(zeros),
        zone_pct=dict(zeros),
        odi=None,
        odi_available=False,
        odi_reason="no samples",
        events=(),
    )


def analyze_samples(samples: Sequence[PulseOxSample]) -> SessionAnalysis:
    """Compute defensible pulse-oximetry session metrics.

    Time-based metrics (T90/T88, zone seconds) integrate over real ``elapsed_s``
    deltas with reconnect gaps excluded; ODI is suppressed when the effective
    sampling rate is too coarse to resolve desaturations.
    """
    n = len(samples)
    if n == 0:
        return _empty()

    spo2 = [s.spo2_percent for s in samples]
    hr = [s.pulse_bpm for s in samples]
    elapsed = [s.elapsed_s for s in samples]

    span_s = elapsed[-1] - elapsed[0]
    dts = [elapsed[i + 1] - elapsed[i] for i in range(n - 1)]
    dts_pos = [d for d in dts if d > 0]
    median_dt = statistics.median(dts_pos) if dts_pos else 0.0
    effective_hz = 1.0 / median_dt if median_dt > 0 else 0.0
    gap_threshold = max(_GAP_FACTOR * median_dt, _GAP_FLOOR_S) if median_dt > 0 else float("inf")

    recorded_s = 0.0
    t90 = 0.0
    t88 = 0.0
    zone_seconds = {name: 0.0 for name, _, _ in _SPO2_ZONES}
    for i in range(n - 1):
        dt = dts[i]
        if dt <= 0 or dt > gap_threshold:
            continue
        recorded_s += dt
        value = spo2[i]
        if value < _T90:
            t90 += dt
        if value < _T88:
            t88 += dt
        zone_seconds[_zone_name(value)] += dt

    pct90 = (t90 / recorded_s * 100.0) if recorded_s > 0 else 0.0
    pct88 = (t88 / recorded_s * 100.0) if recorded_s > 0 else 0.0
    zone_pct = {
        k: (v / recorded_s * 100.0 if recorded_s > 0 else 0.0) for k, v in zone_seconds.items()
    }

    if median_dt == 0 or median_dt > _ODI_MAX_MEDIAN_DT_S:
        events: tuple[DesaturationEvent, ...] = ()
        odi: float | None = None
        odi_available = False
        odi_reason = (
            f"sampling too coarse (median Δ={median_dt:.1f}s) to resolve desaturations for ODI"
            if median_dt > 0
            else "insufficient samples for ODI"
        )
    else:
        events = _detect_desaturations(elapsed, spo2)
        hours = recorded_s / 3600.0
        odi = (len(events) / hours) if hours > 0 else 0.0
        odi_available = True
        odi_reason = None

    return SessionAnalysis(
        n_samples=n,
        recorded_s=recorded_s,
        span_s=span_s,
        effective_hz=effective_hz,
        spo2_mean=statistics.mean(spo2),
        spo2_median=statistics.median(spo2),
        spo2_min=min(spo2),
        spo2_max=max(spo2),
        spo2_std=_std(spo2),
        hr_mean=statistics.mean(hr),
        hr_median=statistics.median(hr),
        hr_min=min(hr),
        hr_max=max(hr),
        hr_std=_std(hr),
        t90_s=t90,
        t88_s=t88,
        pct_below_90=pct90,
        pct_below_88=pct88,
        zone_seconds=zone_seconds,
        zone_pct=zone_pct,
        odi=odi,
        odi_available=odi_available,
        odi_reason=odi_reason,
        events=events,
    )
