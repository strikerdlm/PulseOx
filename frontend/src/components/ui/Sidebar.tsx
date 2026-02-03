'use client';

import { useState } from 'react';
import type { DashboardSettings } from '@/types/pulseox';
import { cn } from '@/lib/utils';

interface SidebarProps {
  settings: DashboardSettings;
  onSettingsChange: (settings: DashboardSettings) => void;
  isOpen: boolean;
  onToggle: () => void;
}

/**
 * Settings Sidebar Component
 *
 * Provides controls for configuring dashboard data display.
 * Includes data source, filtering, and refresh options.
 */
export function Sidebar({
  settings,
  onSettingsChange,
  isOpen,
  onToggle,
}: SidebarProps): JSX.Element {
  const [localCsvPath, setLocalCsvPath] = useState(settings.csvPath);

  const handleCsvPathChange = (): void => {
    onSettingsChange({ ...settings, csvPath: localCsvPath });
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-50 h-full w-72 transition-transform duration-300 ease-in-out',
          'bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950',
          'border-r border-slate-800/50 shadow-2xl',
          isOpen ? 'translate-x-0' : '-translate-x-full',
          'lg:translate-x-0 lg:static lg:z-auto'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="p-6 border-b border-slate-800/50">
            <h2 className="text-lg font-semibold text-slate-100">Settings</h2>
            <p className="text-sm text-slate-400 mt-1">Configure data source</p>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Data Source Section */}
            <section>
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                Data Source
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-2">
                    CSV Path
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={localCsvPath}
                      onChange={(e) => setLocalCsvPath(e.target.value)}
                      className={cn(
                        'flex-1 px-3 py-2 rounded-lg text-sm',
                        'bg-slate-800/50 border border-slate-700/50',
                        'text-slate-200 placeholder-slate-500',
                        'focus:outline-none focus:ring-2 focus:ring-blue-500/50'
                      )}
                      placeholder="path/to/data.csv"
                    />
                    <button
                      onClick={handleCsvPathChange}
                      className={cn(
                        'px-3 py-2 rounded-lg text-sm font-medium',
                        'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30',
                        'transition-colors'
                      )}
                    >
                      Load
                    </button>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Enter path to PulseOx CSV file
                  </p>
                </div>
              </div>
            </section>

            {/* Filtering Section */}
            <section>
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                Filtering
              </h3>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm text-slate-300">
                      Only plausible samples
                    </label>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Filter implausible readings
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      onSettingsChange({
                        ...settings,
                        onlyPlausible: !settings.onlyPlausible,
                      })
                    }
                    className={cn(
                      'relative w-11 h-6 rounded-full transition-colors',
                      settings.onlyPlausible
                        ? 'bg-blue-500'
                        : 'bg-slate-700'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white',
                        'transition-transform',
                        settings.onlyPlausible && 'translate-x-5'
                      )}
                    />
                  </button>
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-2">
                    Window (rows): {settings.windowRows}
                  </label>
                  <input
                    type="range"
                    min={20}
                    max={500}
                    step={10}
                    value={settings.windowRows}
                    onChange={(e) =>
                      onSettingsChange({
                        ...settings,
                        windowRows: parseInt(e.target.value, 10),
                      })
                    }
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>20</span>
                    <span>500</span>
                  </div>
                </div>
              </div>
            </section>

            {/* Refresh Section */}
            <section>
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                Auto-Refresh
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-2">
                    Interval: {settings.refreshSeconds}s
                    {settings.refreshSeconds === 0 && ' (disabled)'}
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={5}
                    step={0.5}
                    value={settings.refreshSeconds}
                    onChange={(e) =>
                      onSettingsChange({
                        ...settings,
                        refreshSeconds: parseFloat(e.target.value),
                      })
                    }
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>Off</span>
                    <span>5s</span>
                  </div>
                </div>
              </div>
            </section>

            {/* Recorder Example */}
            <section>
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                Recorder Command
              </h3>

              <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/30">
                <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap break-all">
                  python -m pulseox.cli --address &quot;FF:FF:FF:FF:00:21&quot; --csv
                  session.csv --csv-overwrite --duration 600 --quiet
                </pre>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Example command to record PulseOx data to CSV
              </p>
            </section>
          </div>

          {/* Footer */}
          <div className="p-6 border-t border-slate-800/50">
            <div className="text-xs text-slate-500 space-y-1">
              <p className="font-medium text-slate-400">PulseOx Dashboard v1.0</p>
              <p>Safety monitoring for pulse oximetry</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Toggle button for mobile */}
      <button
        onClick={onToggle}
        className={cn(
          'fixed top-4 left-4 z-30 lg:hidden',
          'p-2 rounded-lg',
          'bg-slate-800/80 backdrop-blur border border-slate-700/50',
          'text-slate-300 hover:text-slate-100',
          'transition-colors'
        )}
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
      </button>
    </>
  );
}
