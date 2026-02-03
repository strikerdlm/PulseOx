'use client';

import { useMemo } from 'react';
import { EChartWrapper } from './EChartWrapper';
import { createTrendChartOption } from '@/lib/chartConfig';
import type { PulseOxSample } from '@/types/pulseox';
import { formatChartTime } from '@/lib/utils';
import { cn } from '@/lib/utils';

interface TrendChartProps {
  samples: PulseOxSample[];
  className?: string;
}

/**
 * Dual-Axis Trend Chart Component
 *
 * Displays SpO₂ and Heart Rate trends over time with interactive features.
 *
 * Visualization Design Principles:
 * - Dual y-axes for different measurement units (%, bpm)
 * - Smooth curves with area fills for visual clarity
 * - Interactive zoom and pan for data exploration
 * - Clinical threshold markers for context
 * - High contrast colors for accessibility
 *
 * References:
 * 1. Cleveland, W.S. The Elements of Graphing Data. Hobart Press, 1994.
 * 2. Tufte, E.R. The Visual Display of Quantitative Information. Graphics Press, 2001.
 * 3. Kelleher, C. & Wagener, T. "Ten guidelines for effective data visualization
 *    in scientific publications." Environmental Modelling & Software, 2011.
 *    DOI: 10.1016/j.envsoft.2010.12.006
 */
export function TrendChart({
  samples,
  className,
}: TrendChartProps): JSX.Element {
  const { timestamps, spo2Values, hrValues } = useMemo(() => {
    const ts = samples.map((s) => formatChartTime(s.timestamp_utc));
    const spo2 = samples.map((s) => s.spo2_percent);
    const hr = samples.map((s) => s.pulse_bpm);
    return { timestamps: ts, spo2Values: spo2, hrValues: hr };
  }, [samples]);

  const option = useMemo(
    () => createTrendChartOption(timestamps, spo2Values, hrValues),
    [timestamps, spo2Values, hrValues]
  );

  // Calculate quick stats
  const stats = useMemo(() => {
    if (spo2Values.length === 0) return null;

    const spo2Min = Math.min(...spo2Values);
    const spo2Max = Math.max(...spo2Values);
    const spo2Avg = spo2Values.reduce((a, b) => a + b, 0) / spo2Values.length;

    const hrMin = Math.min(...hrValues);
    const hrMax = Math.max(...hrValues);
    const hrAvg = hrValues.reduce((a, b) => a + b, 0) / hrValues.length;

    return { spo2Min, spo2Max, spo2Avg, hrMin, hrMax, hrAvg };
  }, [spo2Values, hrValues]);

  if (samples.length === 0) {
    return (
      <div className={cn('flex items-center justify-center h-80', className)}>
        <p className="text-slate-400">No data available for trend visualization</p>
      </div>
    );
  }

  return (
    <div className={cn('relative', className)}>
      {/* Mini stats bar */}
      {stats && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 flex gap-6">
          <div className="flex items-center gap-2 text-xs">
            <span className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="text-slate-400">SpO₂:</span>
            <span className="text-slate-200 font-medium">
              {stats.spo2Min}-{stats.spo2Max}% (avg: {stats.spo2Avg.toFixed(1)}%)
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-3 h-3 rounded-full bg-blue-500" />
            <span className="text-slate-400">HR:</span>
            <span className="text-slate-200 font-medium">
              {stats.hrMin}-{stats.hrMax} (avg: {stats.hrAvg.toFixed(0)} bpm)
            </span>
          </div>
        </div>
      )}

      {/* Chart */}
      <EChartWrapper option={option} style={{ height: '350px' }} />

      {/* Chart description */}
      <div className="mt-2 px-4 text-center">
        <p className="text-xs text-slate-400">
          Time series visualization with dual y-axes. Use mouse wheel to zoom, 
          drag slider to pan. SpO₂ 92% threshold marked for clinical reference.
        </p>
      </div>
    </div>
  );
}
