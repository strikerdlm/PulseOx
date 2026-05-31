'use client';

import { useState } from 'react';
import { TopBar, type Mode } from '@/components/layout/TopBar';
import { LiveView } from '@/components/live/LiveView';
import { AnalysisView } from '@/components/analysis/AnalysisView';
import { useLiveStream } from '@/lib/useLiveStream';

/**
 * PulseOx Console — aeromedical instrument UI.
 *
 * Live mode: control the BLE device (scan / start / stop) and watch realtime
 * SpO₂ and heart-rate gauges + live trace, streamed from the FastAPI backend
 * over WebSocket. Analysis mode: import a recorded CSV (upload or host session)
 * and explore it with publication-grade charts.
 *
 * Research/education only — not for diagnosis or treatment.
 */
export default function Page(): JSX.Element {
  const [mode, setMode] = useState<Mode>('live');
  const live = useLiveStream();

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar mode={mode} onMode={setMode} connected={live.connected} status={live.status} />

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
        {mode === 'live' ? <LiveView live={live} /> : <AnalysisView />}
      </main>

      <footer className="border-t border-console-border/60 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-[1400px] flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
          <p className="readout text-xs text-console-faint">
            PulseOx Console · clinical thresholds per FDA &amp; peer-reviewed literature
          </p>
          <p className="readout text-xs text-console-faint">
            Research / education only — not for diagnosis or treatment.
          </p>
        </div>
      </footer>
    </div>
  );
}
