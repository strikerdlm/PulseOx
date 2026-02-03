'use client';

import { useMemo } from 'react';
import { EChartWrapper } from './EChartWrapper';
import type { EChartsOption } from 'echarts';
import type { PulseOxSample } from '@/types/pulseox';
import { cn } from '@/lib/utils';

interface CorrelationScatterProps {
  samples: PulseOxSample[];
  className?: string;
}

/**
 * Correlation Scatter Plot Component
 *
 * Visualizes the relationship between SpO₂ and Heart Rate values.
 * Useful for identifying patterns and correlations in physiological data.
 *
 * Clinical Insight:
 * In healthy individuals, SpO₂ and HR may show inverse correlation during
 * hypoxemic episodes (compensatory tachycardia). This visualization helps
 * identify such patterns.
 *
 * References:
 * - Pretto JJ, et al. "Effects of exercise on oxygen saturation."
 *   Respir Physiol Neurobiol. 2010.
 */
export function CorrelationScatter({
  samples,
  className,
}: CorrelationScatterProps): JSX.Element {
  const { option, correlation } = useMemo(() => {
    if (samples.length < 2) {
      return { option: null, correlation: null };
    }

    const data = samples.map((s) => [s.spo2_percent, s.pulse_bpm]);

    // Calculate Pearson correlation coefficient
    const n = samples.length;
    const sumX = samples.reduce((a, s) => a + s.spo2_percent, 0);
    const sumY = samples.reduce((a, s) => a + s.pulse_bpm, 0);
    const sumXY = samples.reduce((a, s) => a + s.spo2_percent * s.pulse_bpm, 0);
    const sumX2 = samples.reduce((a, s) => a + s.spo2_percent * s.spo2_percent, 0);
    const sumY2 = samples.reduce((a, s) => a + s.pulse_bpm * s.pulse_bpm, 0);

    const numerator = n * sumXY - sumX * sumY;
    const denominator = Math.sqrt(
      (n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY)
    );
    const r = denominator !== 0 ? numerator / denominator : 0;

    // Calculate linear regression for trendline
    const meanX = sumX / n;
    const meanY = sumY / n;
    const slope = numerator / (n * sumX2 - sumX * sumX);
    const intercept = meanY - slope * meanX;

    // Generate regression line points
    const minX = Math.min(...samples.map((s) => s.spo2_percent));
    const maxX = Math.max(...samples.map((s) => s.spo2_percent));
    const regressionLine = [
      [minX, slope * minX + intercept],
      [maxX, slope * maxX + intercept],
    ];

    const echartOption: EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: '#334155',
        textStyle: {
          color: '#f1f5f9',
        },
        formatter: (params: unknown) => {
          const p = params as { value: number[] };
          if (!p.value) return '';
          return `SpO₂: ${p.value[0]}%<br/>HR: ${p.value[1]} bpm`;
        },
      },
      grid: {
        left: '12%',
        right: '8%',
        top: '15%',
        bottom: '15%',
      },
      xAxis: {
        type: 'value',
        name: 'SpO₂ (%)',
        nameLocation: 'middle',
        nameGap: 30,
        nameTextStyle: {
          color: '#94a3b8',
          fontSize: 12,
        },
        min: 70,
        max: 100,
        axisLine: {
          lineStyle: {
            color: '#475569',
          },
        },
        axisLabel: {
          color: '#94a3b8',
          formatter: '{value}%',
        },
        splitLine: {
          lineStyle: {
            color: '#334155',
            type: 'dashed',
          },
        },
      },
      yAxis: {
        type: 'value',
        name: 'Heart Rate (bpm)',
        nameLocation: 'middle',
        nameGap: 45,
        nameTextStyle: {
          color: '#94a3b8',
          fontSize: 12,
        },
        min: 40,
        max: 180,
        axisLine: {
          lineStyle: {
            color: '#475569',
          },
        },
        axisLabel: {
          color: '#94a3b8',
        },
        splitLine: {
          lineStyle: {
            color: '#334155',
            type: 'dashed',
          },
        },
      },
      series: [
        {
          name: 'Measurements',
          type: 'scatter',
          data: data,
          symbolSize: 10,
          itemStyle: {
            color: {
              type: 'radial',
              x: 0.5,
              y: 0.5,
              r: 0.5,
              colorStops: [
                { offset: 0, color: '#60a5fa' },
                { offset: 1, color: '#3b82f6' },
              ],
            },
            shadowBlur: 10,
            shadowColor: 'rgba(59, 130, 246, 0.5)',
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 20,
              shadowColor: 'rgba(59, 130, 246, 0.8)',
            },
          },
        },
        {
          name: 'Trend Line',
          type: 'line',
          data: regressionLine,
          smooth: false,
          showSymbol: false,
          lineStyle: {
            color: '#f59e0b',
            width: 2,
            type: 'dashed',
          },
          tooltip: {
            show: false,
          },
        },
        // Add visual map zones
        {
          name: 'Normal SpO₂ Zone',
          type: 'scatter',
          data: [],
          markArea: {
            silent: true,
            itemStyle: {
              color: 'rgba(34, 197, 94, 0.1)',
            },
            data: [
              [
                { xAxis: 95, yAxis: 40 },
                { xAxis: 100, yAxis: 180 },
              ],
            ],
          },
        },
        {
          name: 'Warning SpO₂ Zone',
          type: 'scatter',
          data: [],
          markArea: {
            silent: true,
            itemStyle: {
              color: 'rgba(245, 158, 11, 0.1)',
            },
            data: [
              [
                { xAxis: 88, yAxis: 40 },
                { xAxis: 95, yAxis: 180 },
              ],
            ],
          },
        },
        {
          name: 'Critical SpO₂ Zone',
          type: 'scatter',
          data: [],
          markArea: {
            silent: true,
            itemStyle: {
              color: 'rgba(239, 68, 68, 0.1)',
            },
            data: [
              [
                { xAxis: 70, yAxis: 40 },
                { xAxis: 88, yAxis: 180 },
              ],
            ],
          },
        },
      ],
    };

    return { option: echartOption, correlation: r };
  }, [samples]);

  if (!option || samples.length < 2) {
    return (
      <div className={cn('flex items-center justify-center h-80', className)}>
        <p className="text-slate-400">
          Insufficient data for correlation analysis (need at least 2 samples)
        </p>
      </div>
    );
  }

  const correlationStrength = Math.abs(correlation ?? 0);
  const correlationLabel =
    correlationStrength < 0.3
      ? 'Weak'
      : correlationStrength < 0.7
        ? 'Moderate'
        : 'Strong';
  const correlationDirection =
    (correlation ?? 0) > 0 ? 'Positive' : (correlation ?? 0) < 0 ? 'Negative' : 'None';

  return (
    <div className={cn('relative', className)}>
      {/* Correlation coefficient badge */}
      <div className="absolute top-4 right-4 z-10">
        <div className="px-4 py-2 rounded-xl bg-slate-800/80 border border-slate-700/50">
          <p className="text-xs text-slate-400 uppercase tracking-wider">
            Pearson Correlation (r)
          </p>
          <p className="text-xl font-bold text-slate-100">
            {(correlation ?? 0).toFixed(3)}
          </p>
          <p className="text-xs text-slate-400">
            {correlationLabel} {correlationDirection}
          </p>
        </div>
      </div>

      {/* Chart */}
      <EChartWrapper option={option} style={{ height: '350px' }} />

      {/* Legend */}
      <div className="mt-2 px-4 flex flex-wrap gap-4 justify-center text-xs">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-blue-500" />
          <span className="text-slate-400">Data Points</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-6 h-0.5 bg-amber-500" style={{ borderStyle: 'dashed' }} />
          <span className="text-slate-400">Trend Line</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 bg-green-500/30" />
          <span className="text-slate-400">Normal (≥95%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 bg-amber-500/30" />
          <span className="text-slate-400">Warning (88-94%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 bg-red-500/30" />
          <span className="text-slate-400">Critical (&lt;88%)</span>
        </div>
      </div>
    </div>
  );
}
