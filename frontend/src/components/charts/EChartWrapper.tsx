'use client';

import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { EChartsOption, ECharts } from 'echarts';

interface EChartWrapperProps {
  option: EChartsOption;
  style?: React.CSSProperties;
  className?: string;
  onChartReady?: (chart: ECharts) => void;
}

/**
 * EChart wrapper component with proper lifecycle management.
 *
 * Features:
 * - Automatic resize handling
 * - Proper cleanup on unmount
 * - Animation support
 * - Publication-quality rendering
 */
export function EChartWrapper({
  option,
  style,
  className,
  onChartReady,
}: EChartWrapperProps): JSX.Element {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    // Initialize chart
    chartInstance.current = echarts.init(chartRef.current, undefined, {
      renderer: 'svg', // SVG for publication quality
    });

    if (onChartReady && chartInstance.current) {
      onChartReady(chartInstance.current);
    }

    // Handle resize
    const handleResize = (): void => {
      chartInstance.current?.resize();
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstance.current?.dispose();
    };
  }, [onChartReady]);

  // Update option when it changes
  useEffect(() => {
    if (chartInstance.current && option) {
      chartInstance.current.setOption(option, {
        notMerge: true,
        lazyUpdate: false,
      });
    }
  }, [option]);

  return (
    <div
      ref={chartRef}
      style={{ width: '100%', height: '100%', ...style }}
      className={className}
    />
  );
}
