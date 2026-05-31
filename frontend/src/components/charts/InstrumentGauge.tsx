'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { zoneFor, type Zone } from '@/lib/zones';

interface InstrumentGaugeProps {
  value: number | null;
  previous?: number | null;
  min: number;
  max: number;
  zones: Zone[];
  unit: string;
  label: string;
  ticks: number[];
  className?: string;
}

const CX = 130;
const CY = 138;
const R_BAND = 104; // zone band radius
const R_VALUE = 104; // value arc radius (same track)
const START = -122;
const END = 122;
const SWEEP = END - START;

function polar(r: number, angleCwFromTop: number): { x: number; y: number } {
  const a = ((angleCwFromTop - 90) * Math.PI) / 180;
  return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a) };
}

function arcPath(r: number, a0: number, a1: number): string {
  const p0 = polar(r, a0);
  const p1 = polar(r, a1);
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
  return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
}

/**
 * Custom SVG instrument gauge: clinical zone bands, an animated value arc that
 * fills via stroke-dashoffset, boundary ticks, and a tabular-mono readout.
 */
export function InstrumentGauge({
  value,
  previous = null,
  min,
  max,
  zones,
  unit,
  label,
  ticks,
  className,
}: InstrumentGaugeProps): JSX.Element {
  const span = max - min;
  const toAngle = (v: number): number =>
    START + (Math.min(Math.max(v, min), max) - min) / span * SWEEP;

  const hasValue = value !== null && Number.isFinite(value);
  const zone = hasValue ? zoneFor(zones, value as number) : null;
  const fraction = hasValue ? (toAngle(value as number) - START) / SWEEP : 0;
  const delta = hasValue && previous !== null ? (value as number) - previous : null;

  const trackPath = useMemo(() => arcPath(R_VALUE, START, END), []);
  const bands = useMemo(
    () =>
      zones.map((z) => ({
        d: arcPath(R_BAND, toAngle(z.from), toAngle(z.to)),
        color: z.color,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [zones, min, max],
  );

  const tip = hasValue ? polar(R_VALUE, toAngle(value as number)) : null;

  return (
    <div className={cn('relative w-full', className)}>
      <svg viewBox="0 0 260 196" className="w-full" role="img" aria-label={`${label} gauge`}>
        <defs>
          <filter id={`glow-${label}`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3.2" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* base track */}
        <path d={trackPath} fill="none" stroke="#161d29" strokeWidth={14} strokeLinecap="round" />

        {/* clinical zone bands */}
        {bands.map((b, i) => (
          <path
            key={i}
            d={b.d}
            fill="none"
            stroke={b.color}
            strokeOpacity={0.32}
            strokeWidth={14}
            strokeLinecap="butt"
          />
        ))}

        {/* boundary ticks + labels */}
        {ticks.map((t) => {
          const a = toAngle(t);
          const inner = polar(R_BAND - 12, a);
          const outer = polar(R_BAND + 3, a);
          const lab = polar(R_BAND - 24, a);
          return (
            <g key={t}>
              <line
                x1={inner.x}
                y1={inner.y}
                x2={outer.x}
                y2={outer.y}
                stroke="#39455a"
                strokeWidth={1.4}
              />
              <text
                x={lab.x}
                y={lab.y}
                fill="#6b7689"
                fontSize={9}
                fontFamily="'IBM Plex Mono', monospace"
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {t}
              </text>
            </g>
          );
        })}

        {/* animated value arc (fills via dashoffset) */}
        {hasValue && zone && (
          <path
            d={trackPath}
            fill="none"
            stroke={zone.color}
            strokeWidth={14}
            strokeLinecap="round"
            pathLength={1000}
            strokeDasharray={1000}
            strokeDashoffset={1000 * (1 - fraction)}
            filter={`url(#glow-${label})`}
            style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(0.16,1,0.3,1), stroke 0.4s linear' }}
          />
        )}

        {/* reading indicator */}
        {tip && zone && (
          <circle cx={tip.x} cy={tip.y} r={5.5} fill={zone.color} stroke="#070a0f" strokeWidth={2} />
        )}
      </svg>

      {/* center readout */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-end pb-7">
        <div className="label mb-1">{label}</div>
        <div
          className="readout font-semibold leading-none"
          style={{ fontSize: '3.4rem', color: zone?.color ?? '#566173' }}
        >
          {hasValue ? Math.round(value as number) : '––'}
          <span className="readout ml-1 align-top text-sm text-console-faint">{unit}</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span
            className="readout rounded px-1.5 py-0.5 text-[0.65rem] font-medium"
            style={{
              color: zone?.color ?? '#566173',
              background: zone ? `${zone.color}1a` : 'transparent',
            }}
          >
            {zone?.label ?? 'NO SIGNAL'}
          </span>
          {delta !== null && delta !== 0 && (
            <span className="readout text-[0.65rem] text-console-muted">
              {delta > 0 ? '▲' : '▼'} {Math.abs(delta)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
