'use client';

import { useMemo } from 'react';
import { EChartWrapper } from './EChartWrapper';
import { createHeartRateGaugeOption } from '@/lib/chartConfig';
import { getHeartRateStatus } from '@/lib/data';
import { cn } from '@/lib/utils';

interface HeartRateGaugeProps {
  value: number;
  previousValue?: number | null;
  className?: string;
}

/**
 * Heart Rate Gauge Chart Component
 *
 * Displays heart rate (pulse) with physiological threshold zones.
 *
 * Physiological Context:
 * Heart rate is measured in beats per minute (bpm) and varies based on
 * activity level, age, fitness, medications, and health conditions.
 *
 * Threshold Zones (based on AHA guidelines for resting adults):
 * - Bradycardia (<60 bpm): May be normal in athletes, or indicate issues
 * - Normal (60-100 bpm): Typical healthy resting range
 * - Elevated (100-130 bpm): Mild tachycardia, may indicate stress/exercise
 * - Tachycardia (>130 bpm): Significant elevation, warrants attention
 *
 * References:
 * 1. American Heart Association. Target Heart Rates Chart.
 *    https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates
 * 2. Palatini P. Heart rate as a risk factor for atherosclerosis.
 *    Drugs. 1999;57(5):713-724. DOI: 10.2165/00003495-199957050-00006
 */
export function HeartRateGauge({
  value,
  previousValue = null,
  className,
}: HeartRateGaugeProps): JSX.Element {
  const delta = previousValue !== null ? value - previousValue : null;
  const status = getHeartRateStatus(value);

  const option = useMemo(
    () => createHeartRateGaugeOption(value, delta),
    [value, delta]
  );

  return (
    <div className={cn('relative', className)}>
      {/* Status indicator */}
      <div className="absolute top-4 right-4 z-10">
        <div
          className={cn(
            'px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide',
            'flex items-center gap-2',
            status.status === 'normal' && 'bg-blue-500/20 text-blue-400',
            status.status === 'bradycardia' && 'bg-amber-500/20 text-amber-400',
            status.status === 'elevated' && 'bg-yellow-500/20 text-yellow-400',
            status.status === 'tachycardia' && 'bg-red-500/20 text-red-400 animate-pulse'
          )}
        >
          <span
            className={cn(
              'w-2 h-2 rounded-full',
              status.status === 'normal' && 'bg-blue-400',
              status.status === 'bradycardia' && 'bg-amber-400',
              status.status === 'elevated' && 'bg-yellow-400',
              status.status === 'tachycardia' && 'bg-red-400'
            )}
          />
          {status.label}
        </div>
      </div>

      {/* Heart icon animation */}
      <div className="absolute top-4 left-4 z-10">
        <div
          className="text-2xl animate-pulse"
          style={{
            animationDuration: `${60000 / value}ms`,
          }}
        >
          ❤️
        </div>
      </div>

      {/* Chart */}
      <EChartWrapper option={option} style={{ height: '280px' }} />

      {/* Clinical context footer */}
      <div className="mt-2 px-4 text-center">
        <p className="text-xs text-slate-400">
          Resting HR zones: Bradycardia &lt;60, Normal 60-100, Tachycardia &gt;100 bpm
        </p>
      </div>
    </div>
  );
}
