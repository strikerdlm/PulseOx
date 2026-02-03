'use client';

import { useMemo } from 'react';
import { EChartWrapper } from './EChartWrapper';
import { createDistributionChartOption } from '@/lib/chartConfig';
import type { PulseOxSample } from '@/types/pulseox';
import { cn } from '@/lib/utils';

interface DistributionChartProps {
  samples: PulseOxSample[];
  className?: string;
}

/**
 * Distribution Chart Component
 *
 * Displays histograms of SpO₂ and Heart Rate values with clinical zone coloring.
 *
 * Statistical Context:
 * Distribution analysis helps identify patterns in physiological data:
 * - Central tendency (where most values cluster)
 * - Spread (variability of measurements)
 * - Outliers (potentially clinically significant values)
 *
 * Color Coding:
 * - Colors match clinical threshold zones from gauge charts
 * - Helps quickly identify proportion of readings in each zone
 *
 * References:
 * 1. Wickham, H. "A layered grammar of graphics." Journal of Computational
 *    and Graphical Statistics, 19(1):3-28, 2010. DOI: 10.1198/jcgs.2009.07098
 * 2. Wilke, C.O. Fundamentals of Data Visualization. O'Reilly Media, 2019.
 */
export function DistributionChart({
  samples,
  className,
}: DistributionChartProps): JSX.Element {
  const { spo2Values, hrValues } = useMemo(() => {
    return {
      spo2Values: samples.map((s) => s.spo2_percent),
      hrValues: samples.map((s) => s.pulse_bpm),
    };
  }, [samples]);

  const option = useMemo(
    () => createDistributionChartOption(spo2Values, hrValues),
    [spo2Values, hrValues]
  );

  if (samples.length === 0) {
    return (
      <div className={cn('flex items-center justify-center h-60', className)}>
        <p className="text-slate-400">No data available for distribution analysis</p>
      </div>
    );
  }

  return (
    <div className={cn('relative', className)}>
      {/* Chart */}
      <EChartWrapper option={option} style={{ height: '280px' }} />

      {/* Chart description */}
      <div className="mt-2 px-4 text-center">
        <p className="text-xs text-slate-400">
          Value distributions with clinical zone coloring. Bar colors indicate 
          the clinical significance of each value range.
        </p>
      </div>
    </div>
  );
}
