'use client';

import type { DataStatistics } from '@/types/pulseox';
import { cn } from '@/lib/utils';

interface StatisticsProps {
  stats: DataStatistics | null;
  className?: string;
}

/**
 * Statistics Summary Component
 *
 * Displays key statistical metrics from the pulse oximetry data.
 */
export function Statistics({ stats, className }: StatisticsProps): JSX.Element {
  if (!stats) {
    return (
      <div className={cn('p-4 text-center text-slate-400', className)}>
        No statistics available
      </div>
    );
  }

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  return (
    <div className={cn('grid grid-cols-2 md:grid-cols-4 gap-4', className)}>
      {/* SpO₂ Stats */}
      <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border border-emerald-500/20">
        <p className="text-xs text-emerald-400 font-medium uppercase tracking-wider">
          SpO₂ Range
        </p>
        <p className="text-2xl font-bold text-slate-100 mt-1">
          {stats.spo2.min}-{stats.spo2.max}%
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Mean: {stats.spo2.mean.toFixed(1)}% ± {stats.spo2.stdDev.toFixed(1)}
        </p>
      </div>

      {/* HR Stats */}
      <div className="p-4 rounded-xl bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-500/20">
        <p className="text-xs text-blue-400 font-medium uppercase tracking-wider">
          Heart Rate Range
        </p>
        <p className="text-2xl font-bold text-slate-100 mt-1">
          {stats.heartRate.min}-{stats.heartRate.max}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Mean: {stats.heartRate.mean.toFixed(0)} ± {stats.heartRate.stdDev.toFixed(1)} bpm
        </p>
      </div>

      {/* Sample Count */}
      <div className="p-4 rounded-xl bg-gradient-to-br from-purple-500/10 to-purple-600/5 border border-purple-500/20">
        <p className="text-xs text-purple-400 font-medium uppercase tracking-wider">
          Total Samples
        </p>
        <p className="text-2xl font-bold text-slate-100 mt-1">
          {stats.sampleCount}
        </p>
        <p className="text-xs text-slate-400 mt-1">Valid measurements</p>
      </div>

      {/* Time Range */}
      <div className="p-4 rounded-xl bg-gradient-to-br from-amber-500/10 to-amber-600/5 border border-amber-500/20">
        <p className="text-xs text-amber-400 font-medium uppercase tracking-wider">
          Time Range
        </p>
        <p className="text-2xl font-bold text-slate-100 mt-1">
          {formatDuration(stats.timeRangeSeconds)}
        </p>
        <p className="text-xs text-slate-400 mt-1">Recording duration</p>
      </div>
    </div>
  );
}
