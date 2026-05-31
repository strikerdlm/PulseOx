'use client';

import { useMemo, useState } from 'react';
import type { PulseOxSample } from '@/types/pulseox';
import { Panel } from '@/components/ui/Panel';
import { ImportPanel } from './ImportPanel';
import { TimeInZone } from './TimeInZone';
import { TrendChart, DistributionChart, CorrelationScatter } from '@/components/charts';
import { PoincarePlot } from '@/components/charts/PoincarePlot';
import { Statistics } from '@/components/ui/Statistics';
import { DataTable } from '@/components/ui/DataTable';
import { calculateStatistics } from '@/lib/data';

export function AnalysisView(): JSX.Element {
  const [samples, setSamples] = useState<PulseOxSample[]>([]);
  const [name, setName] = useState<string | null>(null);
  const stats = useMemo(() => calculateStatistics(samples), [samples]);
  const hasData = samples.length > 0;

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[340px_1fr]">
      <Panel title="Import session" className="h-fit lg:sticky lg:top-20">
        <ImportPanel
          activeName={name}
          onLoad={(s, n) => {
            setSamples(s);
            setName(n);
          }}
        />
      </Panel>

      {!hasData ? (
        <EmptyState />
      ) : (
        <div className="space-y-5">
          <Panel
            title="Session statistics"
            right={<span className="label !text-[0.6rem]">{name}</span>}
          >
            <Statistics stats={stats} />
          </Panel>

          <Panel title="SpO₂ oxygenation burden">
            <TimeInZone samples={samples} />
          </Panel>

          <Panel title="Vital-signs trend">
            <div className="h-[340px]">
              <TrendChart samples={samples} />
            </div>
          </Panel>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Panel title="Value distribution">
              <div className="h-[300px]">
                <DistributionChart samples={samples} />
              </div>
            </Panel>
            <Panel title="SpO₂ × HR correlation">
              <div className="h-[300px]">
                <CorrelationScatter samples={samples} />
              </div>
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Panel title="Heart-rate return map">
              <PoincarePlot samples={samples} />
            </Panel>
            <Panel title="Sample log" bodyClassName="p-0">
              <DataTable samples={samples} maxRows={40} />
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState(): JSX.Element {
  return (
    <Panel className="flex min-h-[420px] items-center justify-center">
      <div className="max-w-sm text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-console-border bg-console-raised/50">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" className="text-vital-spo2">
            <path
              d="M3 13h3l2-7 4 14 2-7h4"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h2 className="readout text-base font-semibold text-console-ink">No session loaded</h2>
        <p className="mt-2 text-sm text-console-muted">
          Drop a recorded CSV, or pick a session captured on the host. Charts,
          oxygenation burden, and the sample log render here.
        </p>
      </div>
    </Panel>
  );
}
