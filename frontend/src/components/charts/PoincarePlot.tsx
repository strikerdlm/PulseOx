'use client';

import { useMemo } from 'react';
import type { PulseOxSample } from '@/types/pulseox';
import { EChartWrapper } from './EChartWrapper';
import { createPoincareOption } from '@/lib/chartConfig';

/**
 * Heart-rate Poincaré return map (HRₙ vs HRₙ₊₁) — short-term variability.
 */
export function PoincarePlot({ samples }: { samples: PulseOxSample[] }): JSX.Element {
  const option = useMemo(
    () => createPoincareOption(samples.map((s) => s.pulse_bpm), '#f472b6', 'HR'),
    [samples],
  );
  return (
    <div className="h-[300px]">
      <EChartWrapper option={option} style={{ height: '100%' }} />
    </div>
  );
}
