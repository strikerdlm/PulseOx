'use client';

import { useMemo } from 'react';
import { EChartWrapper } from './EChartWrapper';
import type { EChartsOption } from 'echarts';
import type { DataStatistics } from '@/types/pulseox';
import { cn } from '@/lib/utils';

interface VitalSignsRadarProps {
  stats: DataStatistics | null;
  className?: string;
}

/**
 * Vital Signs Radar Chart Component
 *
 * Multi-dimensional visualization of vital sign metrics showing:
 * - Current values vs optimal ranges
 * - Normalized scores for comparison
 * - Overall health assessment at a glance
 *
 * Design rationale:
 * Radar charts effectively display multivariate data in a compact form,
 * allowing quick assessment of overall patient status.
 *
 * References:
 * - Friendly, M. "A brief history of data visualization." In Handbook of
 *   Data Visualization, pp. 15-56. Springer, 2008.
 */
export function VitalSignsRadar({
  stats,
  className,
}: VitalSignsRadarProps): JSX.Element {
  const option = useMemo((): EChartsOption | null => {
    if (!stats) return null;

    // Normalize values to 0-100 scale for radar display
    // SpO2: 70-100 maps to 0-100
    // HR: 40-180 maps to 0-100 (with optimal around 60-80)

    const spo2Current = ((stats.spo2.current - 70) / 30) * 100;
    const spo2Stability = Math.max(0, 100 - (stats.spo2.stdDev * 10));
    const hrCurrent = Math.max(0, 100 - Math.abs(stats.heartRate.current - 70) * 2);
    const hrStability = Math.max(0, 100 - (stats.heartRate.stdDev * 2));
    const dataQuality = Math.min(100, stats.sampleCount * 2);
    const timeAdequacy = Math.min(100, (stats.timeRangeSeconds / 60) * 20);

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: '#334155',
        textStyle: {
          color: '#f1f5f9',
        },
      },
      legend: {
        data: ['Current Status', 'Optimal Range'],
        bottom: 10,
        textStyle: {
          color: '#94a3b8',
          fontSize: 12,
        },
      },
      radar: {
        indicator: [
          { name: 'SpO₂ Level', max: 100 },
          { name: 'SpO₂ Stability', max: 100 },
          { name: 'HR Optimal', max: 100 },
          { name: 'HR Stability', max: 100 },
          { name: 'Data Quality', max: 100 },
          { name: 'Recording Time', max: 100 },
        ],
        center: ['50%', '48%'],
        radius: '65%',
        shape: 'polygon',
        splitNumber: 4,
        axisName: {
          color: '#94a3b8',
          fontSize: 11,
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(71, 85, 105, 0.5)',
          },
        },
        splitArea: {
          show: true,
          areaStyle: {
            color: [
              'rgba(59, 130, 246, 0.05)',
              'rgba(59, 130, 246, 0.1)',
              'rgba(59, 130, 246, 0.15)',
              'rgba(59, 130, 246, 0.2)',
            ],
          },
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(71, 85, 105, 0.5)',
          },
        },
      },
      series: [
        {
          name: 'Vital Signs Assessment',
          type: 'radar',
          data: [
            {
              value: [
                Math.round(spo2Current),
                Math.round(spo2Stability),
                Math.round(hrCurrent),
                Math.round(hrStability),
                Math.round(dataQuality),
                Math.round(timeAdequacy),
              ],
              name: 'Current Status',
              symbol: 'circle',
              symbolSize: 6,
              lineStyle: {
                color: '#3b82f6',
                width: 2,
              },
              itemStyle: {
                color: '#3b82f6',
              },
              areaStyle: {
                color: 'rgba(59, 130, 246, 0.3)',
              },
            },
            {
              value: [90, 90, 90, 90, 80, 80],
              name: 'Optimal Range',
              symbol: 'circle',
              symbolSize: 4,
              lineStyle: {
                color: '#22c55e',
                width: 2,
                type: 'dashed',
              },
              itemStyle: {
                color: '#22c55e',
              },
              areaStyle: {
                color: 'rgba(34, 197, 94, 0.1)',
              },
            },
          ],
        },
      ],
    };
  }, [stats]);

  if (!stats || !option) {
    return (
      <div className={cn('flex items-center justify-center h-80', className)}>
        <p className="text-slate-400">No data available for assessment</p>
      </div>
    );
  }

  // Calculate overall score
  const overallScore = Math.round(
    (((stats.spo2.current - 70) / 30) * 100 * 0.4) +
    ((100 - stats.spo2.stdDev * 10) * 0.15) +
    ((100 - Math.abs(stats.heartRate.current - 70) * 2) * 0.25) +
    ((100 - stats.heartRate.stdDev * 2) * 0.2)
  );

  return (
    <div className={cn('relative', className)}>
      {/* Overall score badge */}
      <div className="absolute top-4 left-4 z-10">
        <div
          className={cn(
            'px-4 py-2 rounded-xl',
            'bg-gradient-to-br',
            overallScore >= 80 && 'from-green-500/20 to-green-600/10 border border-green-500/30',
            overallScore >= 60 && overallScore < 80 && 'from-yellow-500/20 to-yellow-600/10 border border-yellow-500/30',
            overallScore < 60 && 'from-red-500/20 to-red-600/10 border border-red-500/30'
          )}
        >
          <p className="text-xs text-slate-400 uppercase tracking-wider">Overall Score</p>
          <p
            className={cn(
              'text-2xl font-bold',
              overallScore >= 80 && 'text-green-400',
              overallScore >= 60 && overallScore < 80 && 'text-yellow-400',
              overallScore < 60 && 'text-red-400'
            )}
          >
            {overallScore}%
          </p>
        </div>
      </div>

      {/* Chart */}
      <EChartWrapper option={option} style={{ height: '350px' }} />

      {/* Assessment legend */}
      <div className="mt-2 px-4 grid grid-cols-3 gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-slate-400">Excellent (≥80)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-yellow-500" />
          <span className="text-slate-400">Good (60-79)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-slate-400">Needs Attention (&lt;60)</span>
        </div>
      </div>
    </div>
  );
}
