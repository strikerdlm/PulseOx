'use client';

import { useState, useMemo } from 'react';
import type { PulseOxSample } from '@/types/pulseox';
import { formatTimestamp } from '@/lib/utils';
import { getSpO2Status, getHeartRateStatus } from '@/lib/data';
import { cn } from '@/lib/utils';

interface DataTableProps {
  samples: PulseOxSample[];
  maxRows?: number;
  className?: string;
}

type SortField = 'timestamp' | 'spo2' | 'hr' | 'pi';
type SortDirection = 'asc' | 'desc';

/**
 * Interactive Data Table Component
 *
 * Displays pulse oximetry samples in a sortable, scrollable table.
 *
 * Features:
 * - Column sorting
 * - Status-based cell coloring
 * - Compact view for dashboard use
 * - Hover states for row selection
 */
export function DataTable({
  samples,
  maxRows = 50,
  className,
}: DataTableProps): JSX.Element {
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Sort samples
  const sortedSamples = useMemo(() => {
    const displaySamples = samples.slice(-maxRows);

    return [...displaySamples].sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'timestamp':
          comparison = new Date(a.timestamp_utc).getTime() - new Date(b.timestamp_utc).getTime();
          break;
        case 'spo2':
          comparison = a.spo2_percent - b.spo2_percent;
          break;
        case 'hr':
          comparison = a.pulse_bpm - b.pulse_bpm;
          break;
        case 'pi':
          comparison = a.perfusion_index - b.perfusion_index;
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [samples, maxRows, sortField, sortDirection]);

  const handleSort = (field: SortField): void => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }): JSX.Element => (
    <span className="ml-1 inline-block w-4">
      {sortField === field && (sortDirection === 'asc' ? '↑' : '↓')}
    </span>
  );

  if (samples.length === 0) {
    return (
      <div className={cn('flex items-center justify-center h-40', className)}>
        <p className="text-slate-400">No sample data available</p>
      </div>
    );
  }

  return (
    <div className={cn('overflow-hidden rounded-lg', className)}>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="bg-slate-800/50 border-b border-slate-700/50">
              <th
                className="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider cursor-pointer hover:text-slate-100 transition-colors"
                onClick={() => handleSort('timestamp')}
              >
                Time (UTC)
                <SortIcon field="timestamp" />
              </th>
              <th
                className="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider cursor-pointer hover:text-slate-100 transition-colors"
                onClick={() => handleSort('spo2')}
              >
                SpO₂ (%)
                <SortIcon field="spo2" />
              </th>
              <th
                className="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider cursor-pointer hover:text-slate-100 transition-colors"
                onClick={() => handleSort('hr')}
              >
                HR (bpm)
                <SortIcon field="hr" />
              </th>
              <th
                className="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider cursor-pointer hover:text-slate-100 transition-colors"
                onClick={() => handleSort('pi')}
              >
                PI
                <SortIcon field="pi" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Sender
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/30">
            {sortedSamples.map((sample, index) => {
              const spo2Status = getSpO2Status(sample.spo2_percent);
              const hrStatus = getHeartRateStatus(sample.pulse_bpm);

              return (
                <tr
                  key={`${sample.timestamp_utc}-${index}`}
                  className="hover:bg-slate-700/20 transition-colors"
                >
                  <td className="px-4 py-2 text-sm text-slate-300 font-mono">
                    {formatTimestamp(sample.timestamp_utc)}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded text-sm font-medium',
                        spo2Status.status === 'normal' && 'bg-green-500/20 text-green-400',
                        spo2Status.status === 'borderline' && 'bg-yellow-500/20 text-yellow-400',
                        spo2Status.status === 'warning' && 'bg-amber-500/20 text-amber-400',
                        spo2Status.status === 'critical' && 'bg-red-500/20 text-red-400'
                      )}
                    >
                      {sample.spo2_percent}%
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded text-sm font-medium',
                        hrStatus.status === 'normal' && 'bg-blue-500/20 text-blue-400',
                        hrStatus.status === 'bradycardia' && 'bg-amber-500/20 text-amber-400',
                        hrStatus.status === 'elevated' && 'bg-yellow-500/20 text-yellow-400',
                        hrStatus.status === 'tachycardia' && 'bg-red-500/20 text-red-400'
                      )}
                    >
                      {sample.pulse_bpm}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-sm text-slate-400">
                    {sample.perfusion_index}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        sample.plausible
                          ? 'bg-green-500/10 text-green-400'
                          : 'bg-red-500/10 text-red-400'
                      )}
                    >
                      {sample.plausible ? 'Valid' : 'Check'}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-sm text-slate-500 font-mono">
                    {sample.sender}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Table footer */}
      <div className="bg-slate-800/30 px-4 py-2 border-t border-slate-700/30">
        <p className="text-xs text-slate-400">
          Showing {sortedSamples.length} of {samples.length} samples
          {sortedSamples.length < samples.length && ' (most recent)'}
        </p>
      </div>
    </div>
  );
}
