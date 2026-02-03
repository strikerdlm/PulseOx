'use client';

import { useMemo } from 'react';
import { EChartWrapper } from './EChartWrapper';
import { createSpO2GaugeOption } from '@/lib/chartConfig';
import { getSpO2Status } from '@/lib/data';
import { cn } from '@/lib/utils';

interface SpO2GaugeProps {
  value: number;
  previousValue?: number | null;
  className?: string;
}

/**
 * SpO₂ Gauge Chart Component
 *
 * Displays peripheral oxygen saturation with clinical threshold zones.
 *
 * Clinical Context:
 * SpO₂ (peripheral oxygen saturation) is an estimate of arterial oxygen
 * saturation (SaO₂) measured non-invasively via pulse oximetry.
 *
 * Threshold Zones (based on clinical guidelines):
 * - Normal (≥95%): Healthy oxygen saturation
 * - Borderline (92-94%): Below optimal, monitoring recommended
 * - Hypoxemia (88-91%): Supplemental O₂ may be indicated
 * - Severe Hypoxemia (<88%): Immediate clinical attention needed
 *
 * References:
 * 1. Jubran A. Pulse oximetry. Crit Care. 2015;19(1):272.
 *    DOI: 10.1186/s13054-015-0984-8
 * 2. FDA Safety Communication (Feb 19, 2021): Pulse Oximeter Accuracy
 *    https://www.fda.gov/medical-devices/safety-communications/pulse-oximeter-accuracy-and-limitations-fda-safety-communication
 */
export function SpO2Gauge({
  value,
  previousValue = null,
  className,
}: SpO2GaugeProps): JSX.Element {
  const delta = previousValue !== null ? value - previousValue : null;
  const status = getSpO2Status(value);

  const option = useMemo(
    () => createSpO2GaugeOption(value, delta),
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
            status.status === 'normal' && 'bg-green-500/20 text-green-400',
            status.status === 'borderline' && 'bg-yellow-500/20 text-yellow-400',
            status.status === 'warning' && 'bg-amber-500/20 text-amber-400',
            status.status === 'critical' && 'bg-red-500/20 text-red-400 animate-pulse'
          )}
        >
          <span
            className={cn(
              'w-2 h-2 rounded-full',
              status.status === 'normal' && 'bg-green-400',
              status.status === 'borderline' && 'bg-yellow-400',
              status.status === 'warning' && 'bg-amber-400',
              status.status === 'critical' && 'bg-red-400'
            )}
          />
          {status.label}
        </div>
      </div>

      {/* Chart */}
      <EChartWrapper option={option} style={{ height: '380px' }} />

      {/* Clinical context footer */}
      <div className="mt-2 px-4 text-center">
        <p className="text-xs text-slate-400">
          SpO₂ reference thresholds: Normal ≥95%, Borderline 92-94%, 
          Hypoxemia &lt;92%
        </p>
      </div>
    </div>
  );
}
