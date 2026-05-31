import type {
  DeviceInfo,
  PulseOxSample,
  RecordingParams,
  SessionAnalysis,
  SessionMeta,
  SessionStatus,
} from '@/types/pulseox';

/**
 * Base URL of the local PulseOx FastAPI backend. Override with
 * NEXT_PUBLIC_API_BASE (e.g. when the backend runs on another host).
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      // Only force JSON for string bodies; FormData must keep its own
      // multipart boundary set by the browser.
      headers:
        typeof init?.body === 'string'
          ? { 'content-type': 'application/json' }
          : undefined,
      ...init,
    });
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${API_BASE}. Is \`python -m pulseox_server\` running?`,
      0,
    );
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export interface SessionData {
  samples: PulseOxSample[];
  metadata: { name?: string; returnedRows: number };
}

export const api = {
  base: API_BASE,

  health: (): Promise<{ status: string }> => jsonFetch('/api/health'),

  status: (): Promise<SessionStatus> => jsonFetch('/api/status'),

  scan: (timeoutS = 6): Promise<{ devices: DeviceInfo[] }> =>
    jsonFetch('/api/scan', {
      method: 'POST',
      body: JSON.stringify({ timeout_s: timeoutS }),
    }),

  start: (params: RecordingParams): Promise<SessionStatus> =>
    jsonFetch('/api/recording/start', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  stop: (): Promise<SessionStatus> =>
    jsonFetch('/api/recording/stop', { method: 'POST' }),

  sessions: (): Promise<{ sessions: SessionMeta[] }> => jsonFetch('/api/sessions'),

  session: (
    name: string,
    maxRows = 2000,
    onlyPlausible = true,
  ): Promise<SessionData> =>
    jsonFetch(
      `/api/sessions/${encodeURIComponent(name)}?maxRows=${maxRows}&onlyPlausible=${onlyPlausible}`,
    ),

  analysis: (name: string): Promise<SessionAnalysis> =>
    jsonFetch(`/api/sessions/${encodeURIComponent(name)}/analysis`),

  upload: (file: File): Promise<SessionData & { name: string }> => {
    const form = new FormData();
    form.append('file', file);
    return jsonFetch('/api/upload', { method: 'POST', body: form });
  },

  wsUrl: (): string => `${API_BASE.replace(/^http/, 'ws')}/ws/stream`,
};
