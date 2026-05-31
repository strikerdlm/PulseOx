/**
 * PulseOx Dashboard Type Definitions
 *
 * These types represent pulse oximetry data structures based on
 * the CSV schema from pulseox.record module.
 */

/**
 * A single pulse oximetry sample reading.
 *
 * SpO₂ Reference Ranges (FDA, clinical guidelines):
 * - Normal: 95-100% (healthy individuals)
 * - Borderline: 92-94% (may warrant monitoring)
 * - Hypoxemia: <92% (supplemental oxygen may be indicated)
 * - Severe Hypoxemia: <88% (immediate clinical attention)
 *
 * Heart Rate Reference Ranges (adults, resting):
 * - Bradycardia: <60 bpm
 * - Normal: 60-100 bpm
 * - Tachycardia: >100 bpm
 * - Maximum: ~220-age (exercise)
 *
 * References:
 * - FDA: https://www.fda.gov/medical-devices/safety-communications/pulse-oximeter-accuracy-and-limitations-fda-safety-communication
 * - AHA: Circulation 2020;141:e619-e663
 */
export interface PulseOxSample {
  /** ISO 8601 UTC timestamp (e.g., "2026-01-23T17:21:44.433+00:00") */
  timestamp_utc: string;
  /** Seconds since recording started (monotonic) */
  elapsed_s: number;
  /** BLE sender handle or UUID */
  sender: string;
  /** Functional arterial oxygen saturation estimate (0-100%) */
  spo2_percent: number;
  /** Pulse rate in beats per minute (typically 20-250 valid range) */
  pulse_bpm: number;
  /** Perfusion index (signal quality indicator, 0-15) */
  perfusion_index: number;
  /** Whether sample passed plausibility checks */
  plausible: boolean;
  /** Raw measurement frame in hex (device-dependent) */
  raw_frame_hex: string;
  /** Full BLE notification payload hex */
  raw_notification_hex: string;
  /** Remainder bytes if payload not multiple of frame length */
  remainder_hex: string;
}

/**
 * A BLE device discovered by a scan (backend /api/scan).
 */
export interface DeviceInfo {
  address: string;
  name: string | null;
  rssi: number | null;
  advertised_uuids: string[];
}

export type SessionState = 'idle' | 'recording' | 'error';

/**
 * Backend recording status (/api/status, and WS status frames).
 */
export interface SessionStatus {
  status: SessionState;
  address: string | null;
  duration_s: number | null;
  elapsed_s: number;
  rows: number;
  reconnects: number;
  ended_reason: string | null;
  session_file: string | null;
  error: string | null;
}

/**
 * A recorded session file on the backend host (/api/sessions).
 */
export interface SessionMeta {
  name: string;
  size: number;
  modified: number;
}

/**
 * Parameters for POST /api/recording/start.
 */
export interface RecordingParams {
  address: string;
  duration_s: number;
  sample_hz: number;
  reconnect: boolean;
  notify_uuid?: string;
  session_name?: string;
}

export interface VitalStats {
  mean: number;
  median: number;
  min: number;
  max: number;
  std: number;
}

export interface DesatEvent {
  start_s: number;
  end_s: number;
  duration_s: number;
  nadir: number;
  drop: number;
}

/**
 * Server-computed oximetry metrics (/api/sessions/{name}/analysis). Computed
 * once in `pulseox/analysis.py`; never recomputed in the frontend.
 */
export interface SessionAnalysis {
  n_samples: number;
  recorded_s: number;
  span_s: number;
  effective_hz: number;
  spo2: VitalStats;
  hr: VitalStats;
  t90_s: number;
  t88_s: number;
  pct_below_90: number;
  pct_below_88: number;
  zone_seconds: Record<string, number>;
  zone_pct: Record<string, number>;
  odi: number | null;
  odi_available: boolean;
  odi_reason: string | null;
  events: DesatEvent[];
}

/**
 * Frames pushed over the /ws/stream WebSocket. A `sample` frame is a
 * PulseOxSample plus a discriminating `type`; a `status` frame wraps
 * SessionStatus. The frontend ignores the extra `type` field.
 */
export type WsFrame =
  | ({ type: 'sample' } & PulseOxSample)
  | ({ type: 'status' } & SessionStatus);

/**
 * Dashboard UI settings for data display configuration.
 */
export interface DashboardSettings {
  /** Path to CSV data file */
  csvPath: string;
  /** Number of recent rows to display */
  windowRows: number;
  /** Filter to only plausible samples */
  onlyPlausible: boolean;
  /** Auto-refresh interval in seconds (0 = disabled) */
  refreshSeconds: number;
}

/**
 * SpO₂ clinical threshold zones for gauge visualization.
 *
 * Based on clinical guidelines and FDA recommendations:
 * - Critical (<88%): Severe hypoxemia requiring immediate attention
 * - Warning (88-91%): Hypoxemia, supplemental O₂ may be indicated
 * - Borderline (92-94%): Below optimal, monitoring recommended
 * - Normal (95-100%): Healthy oxygen saturation
 *
 * Reference: Jubran A. Pulse oximetry. Crit Care. 2015;19(1):272.
 * DOI: 10.1186/s13054-015-0984-8
 */
export interface SpO2Thresholds {
  critical: { min: number; max: number; color: string; label: string };
  warning: { min: number; max: number; color: string; label: string };
  borderline: { min: number; max: number; color: string; label: string };
  normal: { min: number; max: number; color: string; label: string };
}

/**
 * Heart rate physiological zones for gauge visualization.
 *
 * Based on AHA guidelines for resting adult heart rate:
 * - Bradycardia (<60 bpm): May be normal for athletes, or indicate conduction issues
 * - Normal (60-100 bpm): Typical healthy resting range
 * - Elevated (100-130 bpm): Mild tachycardia, may indicate stress/exercise
 * - Tachycardia (>130 bpm): Significant elevation, warrants attention
 *
 * Reference: American Heart Association. Target Heart Rates Chart.
 * https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates
 */
export interface HeartRateThresholds {
  bradycardia: { min: number; max: number; color: string; label: string };
  normal: { min: number; max: number; color: string; label: string };
  elevated: { min: number; max: number; color: string; label: string };
  tachycardia: { min: number; max: number; color: string; label: string };
}

/**
 * Time series data point for trend visualization.
 */
export interface TrendDataPoint {
  timestamp: Date;
  spo2: number;
  heartRate: number;
  perfusionIndex: number;
}

/**
 * Statistics summary for data analysis.
 */
export interface DataStatistics {
  spo2: {
    current: number;
    previous: number | null;
    min: number;
    max: number;
    mean: number;
    stdDev: number;
  };
  heartRate: {
    current: number;
    previous: number | null;
    min: number;
    max: number;
    mean: number;
    stdDev: number;
  };
  sampleCount: number;
  timeRangeSeconds: number;
}

/**
 * Chart export configuration for publication-quality output.
 */
export interface ExportConfig {
  /** Output format */
  format: 'png' | 'svg' | 'pdf';
  /** Resolution in DPI (300 recommended for print) */
  dpi: number;
  /** Include title in export */
  includeTitle: boolean;
  /** Include legend in export */
  includeLegend: boolean;
  /** Background color (transparent for 'rgba(0,0,0,0)') */
  backgroundColor: string;
}
