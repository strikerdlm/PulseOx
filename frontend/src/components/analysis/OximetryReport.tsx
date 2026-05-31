'use client';

import type { SessionAnalysis } from '@/types/pulseox';
import { zoneFor, SPO2_ZONES } from '@/lib/zones';

interface OximetryReportProps {
  analysis: SessionAnalysis | null;
  serverBacked: boolean;
}

function fmtDuration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}m ${r.toString().padStart(2, '0')}s`;
}

export function OximetryReport({ analysis, serverBacked }: OximetryReportProps): JSX.Element {
  if (!serverBacked) {
    return (
      <p className="readout text-xs text-console-faint">
        The oximetry report is computed by the backend. Start{' '}
        <span className="text-console-muted">python -m pulseox_server</span> and load a host
        session (or re-drop the file while it is running) to see nadir, T90/T88, and ODI.
      </p>
    );
  }
  if (!analysis) {
    return <p className="readout text-xs text-console-faint">Computing report…</p>;
  }

  const nadirColor = zoneFor(SPO2_ZONES, analysis.spo2.min).color;
  const t90Color = analysis.pct_below_90 > 0 ? '#f7c24b' : '#35d39a';
  const coverage =
    analysis.span_s > 0 ? (analysis.recorded_s / analysis.span_s) * 100 : 100;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      <Tile label="Nadir SpO₂" value={`${analysis.spo2.min}`} unit="%" color={nadirColor} />
      <Tile
        label="Mean SpO₂"
        value={analysis.spo2.mean.toFixed(1)}
        unit="%"
        sub={`σ ${analysis.spo2.std.toFixed(1)}`}
      />
      <Tile
        label="Time < 90%"
        value={fmtDuration(analysis.t90_s)}
        sub={`${analysis.pct_below_90.toFixed(1)}%`}
        color={t90Color}
      />
      <Tile
        label="Time < 88%"
        value={fmtDuration(analysis.t88_s)}
        sub={`${analysis.pct_below_88.toFixed(1)}%`}
        color={analysis.pct_below_88 > 0 ? '#fb923c' : '#35d39a'}
      />
      <Tile
        label="ODI / hr"
        value={analysis.odi_available && analysis.odi !== null ? analysis.odi.toFixed(1) : 'n/a'}
        sub={analysis.odi_available ? `${analysis.events.length} events` : 'rate too coarse'}
        title={analysis.odi_reason ?? undefined}
        color={analysis.odi_available ? undefined : '#566173'}
      />
      <Tile
        label="Mean HR"
        value={analysis.hr.mean.toFixed(0)}
        unit="bpm"
        sub={`${analysis.hr.min}–${analysis.hr.max}`}
      />
      <Tile label="Recorded" value={fmtDuration(analysis.recorded_s)} sub={`${analysis.n_samples} pts`} />
      <Tile
        label="Coverage"
        value={`${coverage.toFixed(0)}`}
        unit="%"
        sub={`Δ̃ ${analysis.effective_hz.toFixed(1)} Hz`}
        color={coverage < 90 ? '#f7c24b' : undefined}
      />
    </div>
  );
}

interface TileProps {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  color?: string;
  title?: string;
}

function Tile({ label, value, unit, sub, color, title }: TileProps): JSX.Element {
  return (
    <div
      title={title}
      className="rounded-lg border border-console-border/70 bg-console-bg/40 px-3 py-2.5"
    >
      <div className="label mb-1.5 truncate">{label}</div>
      <div className="readout text-xl font-semibold leading-none" style={{ color: color ?? '#e7eef6' }}>
        {value}
        {unit && <span className="ml-0.5 text-xs text-console-faint">{unit}</span>}
      </div>
      {sub && <div className="readout mt-1 text-[0.65rem] text-console-muted">{sub}</div>}
    </div>
  );
}
