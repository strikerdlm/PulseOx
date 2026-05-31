'use client';

import type { SessionStatus } from '@/types/pulseox';
import { cn } from '@/lib/utils';

export type Mode = 'live' | 'analysis';

interface TopBarProps {
  mode: Mode;
  onMode: (mode: Mode) => void;
  connected: boolean;
  status: SessionStatus | null;
}

const MODES: { id: Mode; label: string }[] = [
  { id: 'live', label: 'Live' },
  { id: 'analysis', label: 'Analysis' },
];

export function TopBar({ mode, onMode, connected, status }: TopBarProps): JSX.Element {
  const recording = status?.status === 'recording';
  return (
    <header className="sticky top-0 z-30 border-b border-console-border/70 bg-console-bg/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <Logo recording={recording} />
          <div className="leading-tight">
            <div className="readout text-sm font-semibold tracking-label text-console-ink">
              PULSE<span className="text-vital-spo2">OX</span>
            </div>
            <div className="label">Aeromedical Oximetry Console</div>
          </div>
        </div>

        <nav className="flex items-center gap-1 rounded-full border border-console-border bg-console-panel/60 p-1">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => onMode(m.id)}
              className={cn(
                'rounded-full px-4 py-1.5 text-xs font-medium transition-colors',
                mode === m.id
                  ? 'bg-vital-spo2/15 text-vital-spo2'
                  : 'text-console-muted hover:text-console-ink',
              )}
            >
              {m.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2 rounded-full border border-console-border bg-console-panel/60 px-3 py-1.5">
          <span className="relative flex h-2 w-2">
            {connected && (
              <span
                className="absolute inline-flex h-full w-full animate-ping-dot rounded-full"
                style={{ background: recording ? '#35d39a' : '#22d3ee' }}
              />
            )}
            <span
              className="relative inline-flex h-2 w-2 rounded-full"
              style={{ background: connected ? (recording ? '#35d39a' : '#22d3ee') : '#566173' }}
            />
          </span>
          <span className="label !text-[0.6rem] hidden sm:inline">
            {connected ? (recording ? 'Recording' : 'Backend live') : 'Backend offline'}
          </span>
        </div>
      </div>
    </header>
  );
}

function Logo({ recording }: { recording: boolean }): JSX.Element {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
      <rect x="1" y="1" width="28" height="28" rx="8" fill="#0c1118" stroke="#1b2330" />
      <path
        d="M5 16 H10 L12 9 L15 21 L17 13 L19 16 H25"
        fill="none"
        stroke={recording ? '#35d39a' : '#22d3ee'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
