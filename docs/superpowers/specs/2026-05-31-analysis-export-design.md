# PulseOx — oximetry analysis + figure export design

**Date:** 2026-05-31
**Status:** Approved (architecture) → implementation
**Phase:** 4 of 4

## Goal

Add defensible pulse-oximetry session metrics, surface them in the console, and
allow exporting publication-quality figures. The reader is a physician, so the
metric definitions — not the plumbing — are the risk.

## Correctness decisions (non-negotiable)

1. **Time-based metrics integrate over real time, not sample fraction.** Phase 1
   intentionally produces gappy/irregular sampling. For consecutive samples
   `i → i+1`, `dt = elapsed_s[i+1] − elapsed_s[i]`. An interval is a **gap**
   (excluded from numerator *and* denominator) when `dt > gap_threshold`, where
   `gap_threshold = max(3 × median_dt, 2.0 s)`. Otherwise the interval counts
   for `dt` seconds, holding sample `i`'s value (zero-order hold). So
   `t90_s = Σ dt_i · [spo2_i < 90]` over non-gap intervals, and
   `recorded_s = Σ dt_i` over non-gap intervals. `pct_below_90 = t90_s / recorded_s`.

2. **ODI is rate-gated.** `effective_hz = 1 / median_dt`. ODI (desaturations/hour)
   is only computed when `median_dt ≤ 1.5 s` (~≥0.67 Hz). Below that, return
   `odi = None`, `odi_available = False`, `odi_reason = "sampling too coarse
   (Δ̃=<x>s) for ODI"`. T90/T88/nadir/mean are returned at any rate.

3. **Desaturation event = explicit definition.** Baseline at sample `i` =
   **max SpO₂ over the preceding `baseline_window_s = 60 s`** (resting level). A
   sample is *in event* when `spo2_i ≤ baseline_i − drop` (`drop = 4`). Contiguous
   in-event samples form an event; keep events with `duration_s ≥ min_event_s
   = 8 s`. `nadir` = min SpO₂ during the event; `drop` = `baseline − nadir`.
   `odi = len(events) / (recorded_s / 3600)`.

4. **One source of truth.** All metrics live in `pulseox/analysis.py`. The
   backend exposes them at `GET /api/sessions/{name}/analysis`. The frontend
   **never** recomputes them in TypeScript. Drag/drop import routes through
   `/api/upload` (which already persists + parses), so an uploaded file becomes a
   host session and gets the same server-computed report. If the backend is
   offline, drag/drop still renders charts client-side but shows "report
   requires the backend" instead of fabricating numbers in TS.

## Components

### `pulseox/analysis.py` (pure, TDD)
- `DesaturationEvent(start_s, end_s, duration_s, nadir, drop)`.
- `SessionAnalysis` dataclass (all metrics) + `to_dict()` for the API.
- `analyze_samples(samples: Sequence[PulseOxSample]) -> SessionAnalysis`.
- Degenerate inputs (0 or 1 sample) → zeros / empty events, `odi_available=False`.

### Backend
- `GET /api/sessions/{name}/analysis` → `analysis.to_dict()` (reuses the path
  guard + `load_recent_samples_from_path`, `only_plausible=True`).

### Frontend
- `api.analysis(name)`; `OximetryReport.tsx` panel (nadir, mean, T90/T88, ODI or
  the suppressed reason, event count, coverage), shown in Analysis when a server
  session/name is available.
- Drag/drop in `ImportPanel` tries `api.upload` first (→ host session + report);
  falls back to client parse (charts only) when the backend is offline.
- **Figure export:** a small util that pulls each ECharts instance's SVG/PNG via
  the native API and downloads it — in-app, client-side, no backend.

### Publication pipeline (offline, documented — not wired into the backend)
- A short README note: render journal-themed figures from a session with the
  `/echarts` skill (`echarts` CLI, Nature/NEJM/Lancet themes, 300 DPI) to
  `exports/`. The backend is **not** shelled out to Node.

## Testing
- T90 integration with a **synthetic known-answer series + an injected gap**
  (proves gaps are excluded, not attributed to the last reading).
- ODI **suppressed** at 0.2 Hz; ODI **counts events** on a synthetic ≥1 Hz series
  with two engineered dips.
- nadir/mean/zone basics; degenerate inputs.
- Backend route test (host session → analysis JSON) via TestClient.
- All existing tests stay green.

## Non-goals
- No beat-to-beat HRV (the device reports averaged HR; the Poincaré return map
  from Phase 3 already gives an honest short-term-variability view).
- No Bland-Altman (needs two measurement methods; out of scope for one device).
