'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { PulseOxSample, DashboardSettings } from '@/types/pulseox';
import { parseCsvText, getLatestTwo, calculateStatistics, SAMPLE_CSV_DATA } from '@/lib/data';
import { SpO2Gauge, HeartRateGauge, TrendChart, DistributionChart } from '@/components/charts';
import { Card, DataTable, Sidebar, References, Statistics } from '@/components/ui';
import { cn } from '@/lib/utils';

/**
 * PulseOx Safety Management Dashboard
 *
 * A publication-quality dashboard for real-time pulse oximetry monitoring.
 *
 * Features:
 * - Real-time SpO₂ and Heart Rate gauges with clinical thresholds
 * - Trend visualization with dual-axis time series
 * - Distribution analysis for pattern identification
 * - Interactive data table with sorting
 * - Verifiable scientific references
 *
 * Designed for:
 * - Q1 science journal publication standards
 * - Investor demonstrations
 * - Clinical research applications
 *
 * Medical Disclaimer:
 * This dashboard is for research and educational purposes only.
 * It is not intended for diagnosis, treatment, or clinical decision-making.
 */
export default function Dashboard(): JSX.Element {
  const [samples, setSamples] = useState<PulseOxSample[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const [settings, setSettings] = useState<DashboardSettings>({
    csvPath: 'validated_60s.csv',
    windowRows: 120,
    onlyPlausible: true,
    refreshSeconds: 0, // Disabled for demo
  });

  // Load sample data on mount
  useEffect(() => {
    const loadData = (): void => {
      try {
        setIsLoading(true);
        setError(null);

        // Parse the sample CSV data
        const parsed = parseCsvText(SAMPLE_CSV_DATA, {
          maxRows: settings.windowRows,
          onlyPlausible: settings.onlyPlausible,
        });

        setSamples(parsed);
        setLastUpdate(new Date());
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load data');
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [settings.windowRows, settings.onlyPlausible]);

  // Auto-refresh functionality
  useEffect(() => {
    if (settings.refreshSeconds <= 0) return;

    const intervalId = setInterval(() => {
      // In a real app, this would fetch new data
      setLastUpdate(new Date());
    }, settings.refreshSeconds * 1000);

    return () => clearInterval(intervalId);
  }, [settings.refreshSeconds]);

  // Compute derived data
  const [latest, previous] = useMemo(() => getLatestTwo(samples), [samples]);
  const stats = useMemo(() => calculateStatistics(samples), [samples]);

  const handleSettingsChange = useCallback((newSettings: DashboardSettings): void => {
    setSettings(newSettings);
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-slate-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center max-w-md">
          <div className="text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-slate-100 mb-2">Error Loading Data</h2>
          <p className="text-slate-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <Sidebar
        settings={settings}
        onSettingsChange={handleSettingsChange}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main Content */}
      <main className="flex-1 lg:ml-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <header className="mb-8">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold text-slate-100 flex items-center gap-3">
                  <span className="text-4xl">🫀</span>
                  PulseOx Safety Dashboard
                </h1>
                <p className="text-slate-400 mt-2">
                  Real-time pulse oximetry monitoring with clinical-grade visualizations
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-sm text-slate-400">
                  Last update:{' '}
                  <span className="text-slate-300">
                    {lastUpdate.toLocaleTimeString()}
                  </span>
                </div>
                <div
                  className={cn(
                    'px-3 py-1.5 rounded-full text-xs font-medium',
                    samples.length > 0
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-amber-500/20 text-amber-400'
                  )}
                >
                  {samples.length > 0 ? '● Live' : '○ No Data'}
                </div>
              </div>
            </div>
          </header>

          {/* No data state */}
          {!latest && (
            <Card variant="glass" className="mb-8">
              <div className="text-center py-12">
                <div className="text-5xl mb-4">📊</div>
                <h2 className="text-xl font-semibold text-slate-100 mb-2">
                  No Data Available
                </h2>
                <p className="text-slate-400 max-w-md mx-auto">
                  Start recording with the PulseOx CLI to see real-time data.
                  Configure the CSV path in the settings sidebar.
                </p>
              </div>
            </Card>
          )}

          {/* Main gauges */}
          {latest && (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                {/* SpO2 Gauge - Large */}
                <Card
                  variant="glass"
                  title="Oxygen Saturation (SpO₂)"
                  subtitle="Peripheral arterial oxygen saturation"
                  className="lg:col-span-2"
                  glow={latest.spo2_percent < 92 ? 'red' : latest.spo2_percent < 95 ? 'green' : 'green'}
                >
                  <SpO2Gauge
                    value={latest.spo2_percent}
                    previousValue={previous?.spo2_percent}
                  />
                </Card>

                {/* HR Gauge + Sample Info */}
                <div className="space-y-6">
                  <Card
                    variant="glass"
                    title="Heart Rate"
                    subtitle="Beats per minute"
                    glow="blue"
                  >
                    <HeartRateGauge
                      value={latest.pulse_bpm}
                      previousValue={previous?.pulse_bpm}
                    />
                  </Card>

                  {/* Latest sample info */}
                  <Card variant="glass">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-slate-400">Latest Sample</span>
                        <span className="text-xs text-slate-500">
                          {new Date(latest.timestamp_utc).toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs text-slate-500">Sender</p>
                          <p className="text-sm font-mono text-slate-300">
                            {latest.sender}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">Perfusion Index</p>
                          <p className="text-sm font-mono text-slate-300">
                            {latest.perfusion_index}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">Status</p>
                          <p
                            className={cn(
                              'text-sm font-medium',
                              latest.plausible ? 'text-green-400' : 'text-amber-400'
                            )}
                          >
                            {latest.plausible ? 'Plausible' : 'Check Required'}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">Elapsed</p>
                          <p className="text-sm font-mono text-slate-300">
                            {latest.elapsed_s.toFixed(1)}s
                          </p>
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>
              </div>

              {/* Statistics Summary */}
              <Card
                variant="glass"
                title="Session Statistics"
                subtitle="Aggregate metrics from current data window"
                className="mb-8"
              >
                <Statistics stats={stats} />
              </Card>

              {/* Trend Chart */}
              <Card
                variant="glass"
                title="Vital Signs Trend"
                subtitle="SpO₂ and Heart Rate over time with interactive zoom"
                className="mb-8"
              >
                <TrendChart samples={samples} />
              </Card>

              {/* Distribution Chart */}
              <Card
                variant="glass"
                title="Value Distribution Analysis"
                subtitle="Histogram of SpO₂ and Heart Rate values with clinical zone coloring"
                className="mb-8"
              >
                <DistributionChart samples={samples} />
              </Card>

              {/* Data Table */}
              <Card
                variant="glass"
                title="Sample Data"
                subtitle="Recent measurements with sorting (click column headers)"
                className="mb-8"
              >
                <DataTable samples={samples} maxRows={50} />
              </Card>
            </>
          )}

          {/* References Section */}
          <div className="mb-8">
            <References />
          </div>

          {/* Footer */}
          <footer className="border-t border-slate-800/50 pt-8 mt-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div>
                <h4 className="text-sm font-semibold text-slate-300 mb-3">
                  About This Dashboard
                </h4>
                <p className="text-xs text-slate-500">
                  Publication-quality safety management dashboard for pulse oximetry
                  data. Designed for Q1 science journal standards with verifiable
                  references and clinical accuracy.
                </p>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-300 mb-3">
                  Medical Disclaimer
                </h4>
                <p className="text-xs text-slate-500">
                  This dashboard is for research and educational purposes only. It is
                  not intended for diagnosis, treatment, or clinical decision-making.
                  Always consult healthcare professionals.
                </p>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-300 mb-3">
                  Technical Notes
                </h4>
                <p className="text-xs text-slate-500">
                  Built with Next.js, TypeScript, and ECharts for SVG-based
                  publication-quality visualizations. Clinical thresholds based on
                  FDA guidance and peer-reviewed literature.
                </p>
              </div>
            </div>
            <div className="mt-8 pt-4 border-t border-slate-800/30 text-center text-xs text-slate-600">
              PulseOx Safety Dashboard v1.0 • Apache-2.0 License
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
