'use client';

import { useState } from 'react';
import type { DeviceInfo, SessionStatus } from '@/types/pulseox';
import { api, ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';

const DEFAULT_ADDRESS = 'FF:FF:FF:FF:00:21';

interface DeviceControlProps {
  status: SessionStatus | null;
}

export function DeviceControl({ status }: DeviceControlProps): JSX.Element {
  const [address, setAddress] = useState(DEFAULT_ADDRESS);
  const [minutes, setMinutes] = useState(5);
  const [sampleHz, setSampleHz] = useState(1);
  const [reconnect, setReconnect] = useState(true);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recording = status?.status === 'recording';

  const guard = async (fn: () => Promise<void>): Promise<void> => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Unexpected error');
    }
  };

  const onScan = (): Promise<void> =>
    guard(async () => {
      setScanning(true);
      try {
        const { devices: found } = await api.scan(6);
        setDevices(found);
      } finally {
        setScanning(false);
      }
    });

  const onStart = (): Promise<void> =>
    guard(async () => {
      setBusy(true);
      try {
        await api.start({
          address,
          duration_s: Math.max(1, Math.round(minutes * 60)),
          sample_hz: sampleHz,
          reconnect,
        });
      } finally {
        setBusy(false);
      }
    });

  const onStop = (): Promise<void> =>
    guard(async () => {
      setBusy(true);
      try {
        await api.stop();
      } finally {
        setBusy(false);
      }
    });

  return (
    <div className="space-y-5">
      <Field label="Device address">
        <input
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          disabled={recording}
          spellCheck={false}
          className="readout w-full rounded-lg border border-console-border bg-console-bg/60 px-3 py-2 text-sm text-console-ink outline-none focus:border-vital-spo2/60 disabled:opacity-50"
        />
      </Field>

      <button
        onClick={onScan}
        disabled={scanning || recording}
        className="flex w-full items-center justify-center gap-2 rounded-lg border border-console-border bg-console-raised/60 py-2 text-xs font-medium text-console-ink transition-colors hover:border-vital-spo2/50 disabled:opacity-50"
      >
        {scanning ? 'Scanning…' : 'Scan for devices'}
      </button>

      {devices.length > 0 && (
        <div className="max-h-32 space-y-1 overflow-y-auto">
          {devices.map((d) => (
            <button
              key={d.address}
              onClick={() => setAddress(d.address)}
              className={cn(
                'flex w-full items-center justify-between rounded-md border px-2.5 py-1.5 text-left text-xs transition-colors',
                d.address === address
                  ? 'border-vital-spo2/50 bg-vital-spo2/10'
                  : 'border-console-border/60 hover:border-console-border',
              )}
            >
              <span className="readout truncate text-console-ink">{d.name || d.address}</span>
              <span className="label !text-[0.55rem]">{d.rssi ?? '–'} dBm</span>
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label={`Duration · ${minutes} min`}>
          <input
            type="range"
            min={1}
            max={120}
            value={minutes}
            disabled={recording}
            onChange={(e) => setMinutes(parseInt(e.target.value, 10))}
            className="w-full"
          />
        </Field>
        <Field label={`Sample · ${sampleHz} Hz`}>
          <input
            type="range"
            min={0.2}
            max={4}
            step={0.2}
            value={sampleHz}
            disabled={recording}
            onChange={(e) => setSampleHz(parseFloat(e.target.value))}
            className="w-full"
          />
        </Field>
      </div>

      <label className="flex cursor-pointer items-center justify-between">
        <span className="label">Auto-reconnect on drop</span>
        <span className="relative inline-flex">
          <input
            type="checkbox"
            checked={reconnect}
            disabled={recording}
            onChange={(e) => setReconnect(e.target.checked)}
            className="peer sr-only"
          />
          <span className="h-5 w-9 rounded-full bg-console-border transition-colors peer-checked:bg-vital-spo2/60" />
          <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-console-ink transition-transform peer-checked:translate-x-4" />
        </span>
      </label>

      <div className="flex gap-3 pt-1">
        <button
          onClick={onStart}
          disabled={busy || recording}
          className="flex-1 rounded-lg bg-vital-normal/15 py-2.5 text-sm font-semibold text-vital-normal ring-1 ring-inset ring-vital-normal/30 transition-colors hover:bg-vital-normal/25 disabled:opacity-40"
        >
          ▶ Start
        </button>
        <button
          onClick={onStop}
          disabled={busy || !recording}
          className="flex-1 rounded-lg bg-vital-critical/15 py-2.5 text-sm font-semibold text-vital-critical ring-1 ring-inset ring-vital-critical/30 transition-colors hover:bg-vital-critical/25 disabled:opacity-40"
        >
          ■ Stop
        </button>
      </div>

      {error && (
        <p className="readout rounded-md border border-vital-critical/30 bg-vital-critical/10 px-3 py-2 text-xs text-vital-critical">
          {error}
        </p>
      )}

      <StatusReadout status={status} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }): JSX.Element {
  return (
    <div className="space-y-1.5">
      <div className="label">{label}</div>
      {children}
    </div>
  );
}

function StatusReadout({ status }: { status: SessionStatus | null }): JSX.Element {
  const rows: [string, string][] = [
    ['State', status?.status ?? 'unknown'],
    ['Elapsed', status ? `${status.elapsed_s.toFixed(0)} s` : '–'],
    ['Rows', status ? String(status.rows) : '–'],
    ['Reconnects', status ? String(status.reconnects) : '–'],
  ];
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-console-border/60 pt-4">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between">
          <span className="label">{k}</span>
          <span className="readout text-xs text-console-ink">{v}</span>
        </div>
      ))}
    </div>
  );
}
