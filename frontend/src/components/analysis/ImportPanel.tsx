'use client';

import { useCallback, useEffect, useState } from 'react';
import type { DragEvent } from 'react';
import type { PulseOxSample, SessionMeta } from '@/types/pulseox';
import { api, ApiError } from '@/lib/api';
import { parseCsvText } from '@/lib/data';
import { cn } from '@/lib/utils';

interface ImportPanelProps {
  onLoad: (samples: PulseOxSample[], name: string, serverBacked: boolean) => void;
  activeName: string | null;
}

export function ImportPanel({ onLoad, activeName }: ImportPanelProps): JSX.Element {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [serverOffline, setServerOffline] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      const { sessions: found } = await api.sessions();
      setSessions(found);
      setServerOffline(false);
    } catch {
      setServerOffline(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleFile = useCallback(
    async (file: File): Promise<void> => {
      setError(null);
      try {
        // Prefer the backend: it persists the file and yields a server-computed
        // oximetry report. Falls back to client-side parsing when offline.
        const res = await api.upload(file);
        onLoad(res.samples, res.name, true);
        void refresh();
      } catch {
        try {
          const text = await file.text();
          const samples = parseCsvText(text, { maxRows: 5000, onlyPlausible: false });
          if (samples.length === 0) throw new Error('No valid PulseOx rows in file');
          onLoad(samples, file.name, false);
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Could not parse file');
        }
      }
    },
    [onLoad, refresh],
  );

  const loadServer = async (name: string): Promise<void> => {
    setError(null);
    try {
      const { samples } = await api.session(name, 5000, false);
      onLoad(samples, name, true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load session');
    }
  };

  const onDrop = (e: DragEvent<HTMLLabelElement>): void => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void handleFile(file);
  };

  return (
    <div className="space-y-5">
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-7 text-center transition-colors',
          dragOver
            ? 'border-vital-spo2/70 bg-vital-spo2/5'
            : 'border-console-border hover:border-console-hair',
        )}
      >
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" className="text-console-muted">
          <path
            d="M12 16V4m0 0L8 8m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="readout text-xs text-console-ink">Drop a CSV or browse</span>
        <span className="label !text-[0.55rem]">PulseOx recording (.csv)</span>
        <input
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
      </label>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="label">Recorded on host</span>
          <button
            onClick={() => void refresh()}
            className="label !text-[0.55rem] text-vital-spo2 hover:underline"
          >
            refresh
          </button>
        </div>
        {serverOffline ? (
          <p className="readout text-xs text-console-faint">
            Backend offline — drop a file above, or start{' '}
            <span className="text-console-muted">python -m pulseox_server</span>.
          </p>
        ) : sessions.length === 0 ? (
          <p className="readout text-xs text-console-faint">No recorded sessions yet.</p>
        ) : (
          <div className="max-h-56 space-y-1 overflow-y-auto">
            {sessions.map((s) => (
              <button
                key={s.name}
                onClick={() => void loadServer(s.name)}
                className={cn(
                  'flex w-full items-center justify-between rounded-md border px-2.5 py-1.5 text-left text-xs transition-colors',
                  s.name === activeName
                    ? 'border-vital-spo2/50 bg-vital-spo2/10'
                    : 'border-console-border/60 hover:border-console-border',
                )}
              >
                <span className="readout truncate text-console-ink">{s.name}</span>
                <span className="label !text-[0.55rem]">{(s.size / 1024).toFixed(1)} kB</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <p className="readout rounded-md border border-vital-critical/30 bg-vital-critical/10 px-3 py-2 text-xs text-vital-critical">
          {error}
        </p>
      )}
    </div>
  );
}
