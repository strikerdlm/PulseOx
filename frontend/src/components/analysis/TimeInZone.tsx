'use client';

import { useMemo } from 'react';
import type { PulseOxSample } from '@/types/pulseox';
import { SPO2_ZONES, zoneFor } from '@/lib/zones';

/**
 * SpO₂ "oxygenation burden": share of samples spent in each clinical zone.
 */
export function TimeInZone({ samples }: { samples: PulseOxSample[] }): JSX.Element {
  const dist = useMemo(() => {
    const counts = new Map<string, number>();
    SPO2_ZONES.forEach((z) => counts.set(z.label, 0));
    samples.forEach((s) => {
      const z = zoneFor(SPO2_ZONES, s.spo2_percent);
      counts.set(z.label, (counts.get(z.label) ?? 0) + 1);
    });
    const total = samples.length || 1;
    return SPO2_ZONES.map((z) => ({
      ...z,
      pct: ((counts.get(z.label) ?? 0) / total) * 100,
    }));
  }, [samples]);

  const belowNormal = dist
    .filter((z) => z.label !== 'Normal')
    .reduce((a, z) => a + z.pct, 0);

  return (
    <div className="space-y-4">
      <div className="flex h-5 w-full overflow-hidden rounded-md border border-console-border">
        {dist.map((z) => (
          <div
            key={z.label}
            title={`${z.label}: ${z.pct.toFixed(1)}%`}
            style={{ width: `${z.pct}%`, background: z.color }}
            className="h-full transition-[width] duration-500"
          />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        {dist.map((z) => (
          <div key={z.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: z.color }} />
            <span className="label flex-1 !tracking-normal">{z.label}</span>
            <span className="readout text-xs text-console-ink">{z.pct.toFixed(0)}%</span>
          </div>
        ))}
      </div>
      <p className="readout text-xs text-console-muted">
        Time below 95% SpO₂:{' '}
        <span className={belowNormal > 0 ? 'text-vital-borderline' : 'text-vital-normal'}>
          {belowNormal.toFixed(1)}%
        </span>
      </p>
    </div>
  );
}
