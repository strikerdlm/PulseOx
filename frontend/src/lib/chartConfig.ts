/**
 * ECharts Configuration for Publication-Quality Visualizations
 *
 * Designed for Q1 science journal standards with:
 * - High-resolution exports (300+ DPI)
 * - Accessible color palettes
 * - Clear typography and labeling
 * - Proper axis scaling and grid lines
 *
 * References for chart design in scientific publications:
 * - Tufte, E.R. The Visual Display of Quantitative Information (2001)
 * - Cleveland, W.S. The Elements of Graphing Data (1994)
 * - Kelleher, C. & Wagener, T. Ten guidelines for effective data visualization (2011)
 */

import type { EChartsOption } from 'echarts';

/**
 * Base theme configuration for all charts.
 * Optimized for dark dashboard background with high contrast.
 */
export const BASE_THEME = {
  backgroundColor: 'transparent',
  textStyle: {
    fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
    color: '#e2e8f0',
    fontSize: 12,
  },
  title: {
    textStyle: {
      fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
      fontWeight: 600,
      fontSize: 16,
      color: '#f1f5f9',
    },
    subtextStyle: {
      fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
      fontSize: 12,
      color: '#94a3b8',
    },
  },
  axisLine: {
    lineStyle: {
      color: '#475569',
    },
  },
  splitLine: {
    lineStyle: {
      color: '#334155',
      type: 'dashed' as const,
    },
  },
};

/**
 * SpO₂ clinical color palette.
 * Colors chosen for accessibility and clinical meaning.
 */
export const SPO2_COLORS = {
  critical: '#ef4444',    // Red - severe hypoxemia (<88%)
  warning: '#f59e0b',     // Amber - hypoxemia (88-91%)
  borderline: '#eab308',  // Yellow - borderline (92-94%)
  normal: '#22c55e',      // Green - normal (95-100%)
  primary: '#10b981',     // Emerald - main indicator
};

/**
 * Heart rate clinical color palette.
 */
export const HR_COLORS = {
  bradycardia: '#f59e0b', // Amber - <60 bpm
  normal: '#3b82f6',      // Blue - 60-100 bpm
  elevated: '#eab308',    // Yellow - 100-130 bpm
  tachycardia: '#ef4444', // Red - >130 bpm
  primary: '#3b82f6',     // Blue - main indicator
};

/**
 * Create SpO₂ gauge chart option.
 *
 * Clinical thresholds based on:
 * - Jubran A. Pulse oximetry. Crit Care. 2015;19(1):272
 * - FDA Safety Communication (Feb 19, 2021)
 */
export function createSpO2GaugeOption(
  value: number,
  delta: number | null = null
): EChartsOption {
  const deltaText = delta !== null
    ? ` (${delta >= 0 ? '+' : ''}${delta}%)`
    : '';

  return {
    ...BASE_THEME,
    series: [
      {
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 70,
        max: 100,
        splitNumber: 6,
        center: ['50%', '55%'],
        radius: '85%',
        itemStyle: {
          color: getSpO2GaugeColor(value),
          shadowColor: getSpO2GaugeColor(value),
          shadowBlur: 15,
        },
        progress: {
          show: true,
          roundCap: true,
          width: 18,
        },
        pointer: {
          icon: 'path://M2.9,0.7L2.9,0.7c1.4,0,2.6,1.2,2.6,2.6v115c0,1.4-1.2,2.6-2.6,2.6l0,0c-1.4,0-2.6-1.2-2.6-2.6V3.3C0.3,1.9,1.4,0.7,2.9,0.7z',
          length: '60%',
          width: 8,
          offsetCenter: [0, '-5%'],
          itemStyle: {
            color: '#f1f5f9',
            shadowColor: 'rgba(0, 0, 0, 0.3)',
            shadowBlur: 8,
            shadowOffsetX: 2,
            shadowOffsetY: 4,
          },
        },
        axisLine: {
          roundCap: true,
          lineStyle: {
            width: 18,
            color: [
              [0.6, SPO2_COLORS.critical],   // 70-88%
              [0.73, SPO2_COLORS.warning],   // 88-92%
              [0.83, SPO2_COLORS.borderline], // 92-95%
              [1, SPO2_COLORS.normal],        // 95-100%
            ],
          },
        },
        axisTick: {
          splitNumber: 2,
          distance: -25,
          lineStyle: {
            width: 2,
            color: '#475569',
          },
        },
        splitLine: {
          distance: -30,
          length: 12,
          lineStyle: {
            width: 3,
            color: '#475569',
          },
        },
        axisLabel: {
          distance: -45,
          color: '#94a3b8',
          fontSize: 13,
          fontWeight: 500,
          formatter: (value: number) => {
            if (value === 70 || value === 100) return `${value}%`;
            if (value === 88 || value === 92 || value === 95) return `${value}`;
            return '';
          },
        },
        title: {
          offsetCenter: [0, '75%'],
          fontSize: 20,
          fontWeight: 600,
          color: '#f1f5f9',
        },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '30%'],
          fontSize: 56,
          fontWeight: 700,
          formatter: `{value}%${deltaText}`,
          color: '#f1f5f9',
        },
        data: [
          {
            value: value,
            name: 'SpO₂',
          },
        ],
      },
    ],
  };
}

/**
 * Get gauge color based on SpO₂ value.
 */
function getSpO2GaugeColor(value: number): string {
  if (value < 88) return SPO2_COLORS.critical;
  if (value < 92) return SPO2_COLORS.warning;
  if (value < 95) return SPO2_COLORS.borderline;
  return SPO2_COLORS.normal;
}

/**
 * Create Heart Rate gauge chart option.
 *
 * Physiological zones based on:
 * - American Heart Association guidelines
 * - Standard adult resting heart rate ranges
 */
export function createHeartRateGaugeOption(
  value: number,
  delta: number | null = null
): EChartsOption {
  const deltaText = delta !== null
    ? ` (${delta >= 0 ? '+' : ''}${delta})`
    : '';

  return {
    ...BASE_THEME,
    series: [
      {
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 40,
        max: 180,
        splitNumber: 7,
        center: ['50%', '55%'],
        radius: '85%',
        itemStyle: {
          color: getHRGaugeColor(value),
          shadowColor: getHRGaugeColor(value),
          shadowBlur: 15,
        },
        progress: {
          show: true,
          roundCap: true,
          width: 14,
        },
        pointer: {
          icon: 'path://M2.9,0.7L2.9,0.7c1.4,0,2.6,1.2,2.6,2.6v115c0,1.4-1.2,2.6-2.6,2.6l0,0c-1.4,0-2.6-1.2-2.6-2.6V3.3C0.3,1.9,1.4,0.7,2.9,0.7z',
          length: '60%',
          width: 6,
          offsetCenter: [0, '-5%'],
          itemStyle: {
            color: '#f1f5f9',
            shadowColor: 'rgba(0, 0, 0, 0.3)',
            shadowBlur: 8,
          },
        },
        axisLine: {
          roundCap: true,
          lineStyle: {
            width: 14,
            color: [
              [0.14, HR_COLORS.bradycardia],  // 40-60 bpm
              [0.43, HR_COLORS.normal],       // 60-100 bpm
              [0.64, HR_COLORS.elevated],     // 100-130 bpm
              [1, HR_COLORS.tachycardia],     // 130-180 bpm
            ],
          },
        },
        axisTick: {
          splitNumber: 2,
          distance: -22,
          lineStyle: {
            width: 2,
            color: '#475569',
          },
        },
        splitLine: {
          distance: -26,
          length: 10,
          lineStyle: {
            width: 2,
            color: '#475569',
          },
        },
        axisLabel: {
          distance: -38,
          color: '#94a3b8',
          fontSize: 11,
          fontWeight: 500,
          formatter: (value: number) => {
            if ([40, 60, 100, 130, 180].includes(value)) return `${value}`;
            return '';
          },
        },
        title: {
          offsetCenter: [0, '75%'],
          fontSize: 16,
          fontWeight: 600,
          color: '#f1f5f9',
        },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '30%'],
          fontSize: 42,
          fontWeight: 700,
          formatter: `{value} bpm${deltaText}`,
          color: '#f1f5f9',
        },
        data: [
          {
            value: value,
            name: 'Heart Rate',
          },
        ],
      },
    ],
  };
}

/**
 * Get gauge color based on heart rate value.
 */
function getHRGaugeColor(value: number): string {
  if (value < 60) return HR_COLORS.bradycardia;
  if (value <= 100) return HR_COLORS.normal;
  if (value <= 130) return HR_COLORS.elevated;
  return HR_COLORS.tachycardia;
}

/**
 * Create dual-axis trend chart for SpO₂ and Heart Rate over time.
 *
 * Design principles for time-series visualization:
 * - Cleveland, W.S. The Elements of Graphing Data (1994)
 * - Dual y-axis with clear differentiation
 * - Tooltips with precise values
 */
export function createTrendChartOption(
  timestamps: string[],
  spo2Values: number[],
  hrValues: number[]
): EChartsOption {
  return {
    ...BASE_THEME,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#334155',
      borderWidth: 1,
      textStyle: {
        color: '#f1f5f9',
        fontSize: 13,
      },
      formatter: (params: unknown) => {
        const dataParams = params as Array<{
          name: string;
          seriesName: string;
          value: number;
          color: string;
        }>;
        if (!Array.isArray(dataParams) || dataParams.length === 0) return '';

        const time = dataParams[0].name;
        let content = `<div style="font-weight: 600; margin-bottom: 8px;">${time}</div>`;

        dataParams.forEach((param) => {
          const unit = param.seriesName === 'SpO₂' ? '%' : ' bpm';
          content += `
            <div style="display: flex; align-items: center; margin: 4px 0;">
              <span style="display: inline-block; width: 10px; height: 10px; 
                background: ${param.color}; border-radius: 50%; margin-right: 8px;"></span>
              <span style="margin-right: 8px;">${param.seriesName}:</span>
              <span style="font-weight: 600;">${param.value}${unit}</span>
            </div>
          `;
        });

        return content;
      },
    },
    legend: {
      data: ['SpO₂', 'Heart Rate'],
      top: 10,
      textStyle: {
        color: '#94a3b8',
        fontSize: 13,
      },
      itemWidth: 20,
      itemHeight: 10,
    },
    grid: {
      left: '4%',
      right: '4%',
      bottom: '12%',
      top: '15%',
      containLabel: true,
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
        minValueSpan: 5,
      },
      {
        type: 'slider',
        show: true,
        height: 20,
        bottom: 5,
        start: 0,
        end: 100,
        borderColor: '#334155',
        backgroundColor: 'rgba(30, 41, 59, 0.5)',
        fillerColor: 'rgba(59, 130, 246, 0.2)',
        handleStyle: {
          color: '#3b82f6',
        },
        textStyle: {
          color: '#94a3b8',
        },
      },
    ],
    xAxis: {
      type: 'category',
      data: timestamps,
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: '#475569',
        },
      },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
        rotate: 30,
      },
      axisTick: {
        lineStyle: {
          color: '#475569',
        },
      },
    },
    yAxis: [
      {
        type: 'value',
        name: 'SpO₂ (%)',
        min: 70,
        max: 100,
        position: 'left',
        nameTextStyle: {
          color: SPO2_COLORS.primary,
          fontWeight: 600,
          fontSize: 12,
        },
        axisLine: {
          show: true,
          lineStyle: {
            color: SPO2_COLORS.primary,
          },
        },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
          formatter: '{value}%',
        },
        splitLine: {
          lineStyle: {
            color: '#334155',
            type: 'dashed',
          },
        },
      },
      {
        type: 'value',
        name: 'HR (bpm)',
        min: 40,
        max: 180,
        position: 'right',
        nameTextStyle: {
          color: HR_COLORS.primary,
          fontWeight: 600,
          fontSize: 12,
        },
        axisLine: {
          show: true,
          lineStyle: {
            color: HR_COLORS.primary,
          },
        },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
        },
        splitLine: {
          show: false,
        },
      },
    ],
    series: [
      {
        name: 'SpO₂',
        type: 'line',
        yAxisIndex: 0,
        data: spo2Values,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          color: SPO2_COLORS.primary,
        },
        lineStyle: {
          width: 3,
          color: SPO2_COLORS.primary,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
              { offset: 1, color: 'rgba(16, 185, 129, 0)' },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            type: 'dashed',
            width: 1,
          },
          data: [
            {
              yAxis: 92,
              label: {
                formatter: '92% threshold',
                position: 'insideEndTop',
                color: '#f59e0b',
                fontSize: 10,
              },
              lineStyle: {
                color: '#f59e0b',
              },
            },
          ],
        },
      },
      {
        name: 'Heart Rate',
        type: 'line',
        yAxisIndex: 1,
        data: hrValues,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          color: HR_COLORS.primary,
        },
        lineStyle: {
          width: 3,
          color: HR_COLORS.primary,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0)' },
            ],
          },
        },
      },
    ],
  };
}

/**
 * Create statistics bar chart for data distribution.
 */
export function createDistributionChartOption(
  spo2Values: number[],
  hrValues: number[]
): EChartsOption {
  // Calculate histogram bins for SpO₂
  const spo2Bins = calculateHistogram(spo2Values, 70, 100, 6);
  const hrBins = calculateHistogram(hrValues, 40, 180, 7);

  return {
    ...BASE_THEME,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#334155',
    },
    legend: {
      data: ['SpO₂ Distribution', 'HR Distribution'],
      top: 10,
      textStyle: {
        color: '#94a3b8',
      },
    },
    grid: [
      { left: '10%', right: '55%', top: '20%', bottom: '15%' },
      { left: '55%', right: '10%', top: '20%', bottom: '15%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: spo2Bins.labels,
        gridIndex: 0,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
        axisLine: { lineStyle: { color: '#475569' } },
      },
      {
        type: 'category',
        data: hrBins.labels,
        gridIndex: 1,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
        axisLine: { lineStyle: { color: '#475569' } },
      },
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        name: 'Count',
        nameTextStyle: { color: '#94a3b8' },
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
      },
      {
        type: 'value',
        gridIndex: 1,
        name: 'Count',
        nameTextStyle: { color: '#94a3b8' },
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
      },
    ],
    series: [
      {
        name: 'SpO₂ Distribution',
        type: 'bar',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: spo2Bins.counts.map((count, i) => ({
          value: count,
          itemStyle: {
            color: getSpO2BinColor(spo2Bins.binEdges[i]),
            borderRadius: [4, 4, 0, 0],
          },
        })),
        barWidth: '60%',
      },
      {
        name: 'HR Distribution',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: hrBins.counts.map((count, i) => ({
          value: count,
          itemStyle: {
            color: getHRBinColor(hrBins.binEdges[i]),
            borderRadius: [4, 4, 0, 0],
          },
        })),
        barWidth: '60%',
      },
    ],
  };
}

/**
 * Calculate histogram bins for data.
 */
function calculateHistogram(
  values: number[],
  min: number,
  max: number,
  numBins: number
): { counts: number[]; labels: string[]; binEdges: number[] } {
  const binSize = (max - min) / numBins;
  const counts = new Array(numBins).fill(0);
  const labels: string[] = [];
  const binEdges: number[] = [];

  for (let i = 0; i < numBins; i++) {
    const binStart = min + i * binSize;
    const binEnd = binStart + binSize;
    binEdges.push(binStart);
    labels.push(`${Math.round(binStart)}-${Math.round(binEnd)}`);
  }

  values.forEach((value) => {
    const binIndex = Math.min(
      Math.floor((value - min) / binSize),
      numBins - 1
    );
    if (binIndex >= 0 && binIndex < numBins) {
      counts[binIndex]++;
    }
  });

  return { counts, labels, binEdges };
}

/**
 * Get color for SpO₂ histogram bin.
 */
function getSpO2BinColor(binStart: number): string {
  if (binStart < 88) return SPO2_COLORS.critical;
  if (binStart < 92) return SPO2_COLORS.warning;
  if (binStart < 95) return SPO2_COLORS.borderline;
  return SPO2_COLORS.normal;
}

/**
 * Get color for HR histogram bin.
 */
function getHRBinColor(binStart: number): string {
  if (binStart < 60) return HR_COLORS.bradycardia;
  if (binStart < 100) return HR_COLORS.normal;
  if (binStart < 130) return HR_COLORS.elevated;
  return HR_COLORS.tachycardia;
}
