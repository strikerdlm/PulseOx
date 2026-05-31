'use client';

import { useMemo } from 'react';
import type { LiveStream } from '@/lib/useLiveStream';
import { Panel } from '@/components/ui/Panel';
import { DeviceControl } from './DeviceControl';
import { InstrumentGauge } from '@/components/charts/InstrumentGauge';
import { TrendChart } from '@/components/charts/TrendChart';
import { HR_ZONES, SPO2_ZONES } from '@/lib/zones';

export function LiveView({ live }: { live: LiveStream }): JSX.Element {
  const { samples, latest, status } = live;
  const prev = samples.length > 1 ? samples[samples.length - 2] : null;
  const recording = status?.status === 'recording';

  const readout = useMemo(
    () => [
      ['Perfusion idx', latest ? String(latest.perfusion_index) : '–'],
      ['Sender', latest ? latest.sender : '–'],
      ['Quality', latest ? (latest.plausible ? 'plausible' : 'check') : '–'],
      ['Samples', String(samples.length)],
    ],
    [latest, samples.length],
  );

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[340px_1fr]">
      <Panel title="Device Control" className="lg:row-span-2 h-fit">
        <DeviceControl status={status} />
      </Panel>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <Panel title="SpO₂ · % saturation">
          <InstrumentGauge
            value={latest?.spo2_percent ?? null}
            previous={prev?.spo2_percent ?? null}
            min={70}
            max={100}
            zones={SPO2_ZONES}
            ticks={[70, 88, 92, 95, 100]}
            unit="%"
            label="SpO₂"
          />
        </Panel>
        <Panel title="Heart rate · bpm">
          <InstrumentGauge
            value={latest?.pulse_bpm ?? null}
            previous={prev?.pulse_bpm ?? null}
            min={40}
            max={180}
            zones={HR_ZONES}
            ticks={[40, 50, 100, 130, 180]}
            unit="bpm"
            label="HR"
          />
        </Panel>
      </div>

      <Panel
        title="Live trace"
        right={
          <span className="label !text-[0.6rem]">
            {recording ? `▲ streaming · ${samples.length} pts` : 'idle'}
          </span>
        }
      >
        {samples.length > 1 ? (
          <div className="h-[320px]">
            <TrendChart samples={samples} />
          </div>
        ) : (
          <Idle recording={recording} />
        )}
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-console-border/60 pt-3 sm:grid-cols-4">
          {readout.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between">
              <span className="label">{k}</span>
              <span className="readout text-xs text-console-ink">{v}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Idle({ recording }: { recording: boolean }): JSX.Element {
  return (
    <div className="flex h-[320px] flex-col items-center justify-center text-center">
      <div className="relative mb-4 h-12 w-40 overflow-hidden">
        <div className="absolute left-0 top-1/2 h-px w-full bg-console-border" />
        {recording && (
          <div className="absolute inset-0 animate-sweep bg-gradient-to-r from-transparent via-vital-spo2/40 to-transparent" />
        )}
      </div>
      <p className="readout text-sm text-console-muted">
        {recording ? 'Waiting for the first frame…' : 'No live signal'}
      </p>
      <p className="mt-1 max-w-xs text-xs text-console-faint">
        {recording
          ? 'Insert a finger; consumer oximeters only notify while actively measuring.'
          : 'Start a recording from Device Control to stream live vitals.'}
      </p>
    </div>
  );
}
