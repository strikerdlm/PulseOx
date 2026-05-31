'use client';

import { useEffect, useRef, useState } from 'react';
import type { PulseOxSample, SessionState, SessionStatus, WsFrame } from '@/types/pulseox';
import { api } from './api';

export interface LiveStream {
  /** Whether the WebSocket is currently open. */
  connected: boolean;
  /** Rolling buffer of recent live samples (capped at `maxSamples`). */
  samples: PulseOxSample[];
  /** Most recent backend status frame, if any. */
  status: SessionStatus | null;
  /** Convenience: the newest sample, or null. */
  latest: PulseOxSample | null;
}

/**
 * Subscribe to the backend `/ws/stream` WebSocket and accumulate live samples.
 * Auto-reconnects with a short backoff. Resets the local buffer on the rising
 * edge of a new recording so a fresh session starts clean.
 */
export function useLiveStream(maxSamples = 600): LiveStream {
  const [connected, setConnected] = useState(false);
  const [samples, setSamples] = useState<PulseOxSample[]>([]);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const prevState = useRef<SessionState | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;

    const connect = (): void => {
      ws = new WebSocket(api.wsUrl());

      ws.onopen = (): void => setConnected(true);

      ws.onclose = (): void => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 1500);
      };

      ws.onerror = (): void => ws?.close();

      ws.onmessage = (event: MessageEvent<string>): void => {
        let frame: WsFrame;
        try {
          frame = JSON.parse(event.data) as WsFrame;
        } catch {
          return;
        }
        if (frame.type === 'sample') {
          setSamples((prev) => {
            const next = prev.concat(frame);
            return next.length > maxSamples ? next.slice(-maxSamples) : next;
          });
        } else {
          if (frame.status === 'recording' && prevState.current !== 'recording') {
            setSamples([]);
          }
          prevState.current = frame.status;
          setStatus(frame);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, [maxSamples]);

  return {
    connected,
    samples,
    status,
    latest: samples.length > 0 ? samples[samples.length - 1] : null,
  };
}
