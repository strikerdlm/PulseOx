import Papa from 'papaparse';
import type { PulseOxSample, DataStatistics, TrendDataPoint } from '@/types/pulseox';
import { calculateStdDev } from './utils';

/**
 * CSV row structure as parsed from file.
 */
interface CsvRow {
  timestamp_utc: string;
  elapsed_s: string;
  sender: string;
  spo2_percent: string;
  pulse_bpm: string;
  perfusion_index: string;
  plausible: string;
  raw_frame_hex: string;
  raw_notification_hex: string;
  remainder_hex: string;
}

/**
 * Parse a CSV string into PulseOxSample array.
 *
 * @param csvText - Raw CSV text content
 * @param options - Parsing options
 * @returns Array of parsed samples
 */
export function parseCsvText(
  csvText: string,
  options: { maxRows?: number; onlyPlausible?: boolean } = {}
): PulseOxSample[] {
  const { maxRows = 500, onlyPlausible = true } = options;

  const result = Papa.parse<CsvRow>(csvText, {
    header: true,
    skipEmptyLines: true,
  });

  if (result.errors.length > 0) {
    console.warn('CSV parsing warnings:', result.errors);
  }

  let samples: PulseOxSample[] = result.data
    .filter((row) => row.timestamp_utc && row.spo2_percent)
    .map((row) => ({
      timestamp_utc: row.timestamp_utc,
      elapsed_s: parseFloat(row.elapsed_s) || 0,
      sender: row.sender || 'unknown',
      spo2_percent: parseInt(row.spo2_percent, 10) || 0,
      pulse_bpm: parseInt(row.pulse_bpm, 10) || 0,
      perfusion_index: parseInt(row.perfusion_index, 10) || 0,
      plausible: row.plausible === '1',
      raw_frame_hex: row.raw_frame_hex || '',
      raw_notification_hex: row.raw_notification_hex || '',
      remainder_hex: row.remainder_hex || '',
    }));

  if (onlyPlausible) {
    samples = samples.filter((s) => s.plausible);
  }

  // Return only the most recent rows
  if (samples.length > maxRows) {
    samples = samples.slice(-maxRows);
  }

  return samples;
}

/**
 * Get the two most recent samples for delta calculation.
 *
 * @param samples - Array of samples
 * @returns Tuple of [latest, previous] or [null, null] if empty
 */
export function getLatestTwo(
  samples: PulseOxSample[]
): [PulseOxSample | null, PulseOxSample | null] {
  if (samples.length === 0) {
    return [null, null];
  }
  if (samples.length === 1) {
    return [samples[0], null];
  }
  return [samples[samples.length - 1], samples[samples.length - 2]];
}

/**
 * Convert samples to trend data points for charting.
 *
 * @param samples - Array of samples
 * @returns Array of trend data points
 */
export function samplesToTrendData(samples: PulseOxSample[]): TrendDataPoint[] {
  return samples.map((s) => ({
    timestamp: new Date(s.timestamp_utc),
    spo2: s.spo2_percent,
    heartRate: s.pulse_bpm,
    perfusionIndex: s.perfusion_index,
  }));
}

/**
 * Calculate statistics from samples.
 *
 * @param samples - Array of samples
 * @returns Statistical summary
 */
export function calculateStatistics(samples: PulseOxSample[]): DataStatistics | null {
  if (samples.length === 0) {
    return null;
  }

  const [latest, previous] = getLatestTwo(samples);

  if (!latest) {
    return null;
  }

  const spo2Values = samples.map((s) => s.spo2_percent);
  const hrValues = samples.map((s) => s.pulse_bpm);

  const firstTimestamp = new Date(samples[0].timestamp_utc);
  const lastTimestamp = new Date(samples[samples.length - 1].timestamp_utc);
  const timeRangeSeconds = (lastTimestamp.getTime() - firstTimestamp.getTime()) / 1000;

  return {
    spo2: {
      current: latest.spo2_percent,
      previous: previous?.spo2_percent ?? null,
      min: Math.min(...spo2Values),
      max: Math.max(...spo2Values),
      mean: spo2Values.reduce((a, b) => a + b, 0) / spo2Values.length,
      stdDev: calculateStdDev(spo2Values),
    },
    heartRate: {
      current: latest.pulse_bpm,
      previous: previous?.pulse_bpm ?? null,
      min: Math.min(...hrValues),
      max: Math.max(...hrValues),
      mean: hrValues.reduce((a, b) => a + b, 0) / hrValues.length,
      stdDev: calculateStdDev(hrValues),
    },
    sampleCount: samples.length,
    timeRangeSeconds,
  };
}

/**
 * Sample CSV data for demonstration and testing.
 * Based on validated_60s.csv structure.
 */
export const SAMPLE_CSV_DATA = `timestamp_utc,elapsed_s,sender,spo2_percent,pulse_bpm,perfusion_index,plausible,raw_frame_hex,raw_notification_hex,remainder_hex
2026-01-23T17:21:44.433+00:00,7.016000,0x000b,90,65,0,1,f1-5a-41-00-8e-03-1d,f1-5a-41-00-8e-03-1d,
2026-01-23T17:21:49.433+00:00,12.016000,0x000b,90,60,0,1,f1-5a-3c-00-8f-03-19,f1-5a-3c-00-8f-03-19,
2026-01-23T17:21:54.433+00:00,17.016000,0x000b,91,60,0,1,f1-5b-3c-00-8c-03-17,f1-5b-3c-00-8c-03-17,
2026-01-23T17:21:59.473+00:00,22.062000,0x000b,92,60,0,1,f1-5c-3c-00-8f-03-1b,f1-5c-3c-00-8f-03-1b,
2026-01-23T17:22:05.432+00:00,28.016000,0x000b,92,62,0,1,f1-5c-3e-00-99-03-27,f1-5c-3e-00-99-03-27,
2026-01-23T17:22:10.451+00:00,33.047000,0x000b,92,72,0,1,f1-5c-48-00-86-03-1e,f1-5c-48-00-86-03-1e,
2026-01-23T17:22:16.432+00:00,39.016000,0x000b,92,80,0,1,f1-5c-50-00-68-03-08,f1-5c-50-00-68-03-08,
2026-01-23T17:22:21.432+00:00,44.016000,0x000b,91,80,0,1,f1-5b-50-00-4e-03-ed,f1-5b-50-00-4e-03-ed,
2026-01-23T17:22:26.434+00:00,49.016000,0x000b,89,75,0,1,f1-59-4b-00-4f-03-e7,f1-59-4b-00-4f-03-e7,
2026-01-23T17:22:31.472+00:00,54.062000,0x000b,89,66,0,1,f1-59-42-00-59-03-e8,f1-59-42-00-59-03-e8,
2026-01-23T17:22:36.472+00:00,59.062000,0x000b,91,69,0,1,f1-5b-45-00-75-03-09,f1-5b-45-00-75-03-09,
2026-01-23T17:22:42.432+00:00,65.016000,0x000b,92,75,0,1,f1-5c-4b-00-78-03-13,f1-5c-4b-00-78-03-13,
2026-01-23T17:22:47.432+00:00,70.016000,0x000b,93,72,0,1,f1-5d-48-00-82-03-1a,f1-5d-48-00-82-03-1a,
2026-01-23T17:22:52.432+00:00,75.016000,0x000b,94,68,0,1,f1-5e-44-00-7a-03-10,f1-5e-44-00-7a-03-10,
2026-01-23T17:22:57.432+00:00,80.016000,0x000b,95,65,0,1,f1-5f-41-00-85-03-19,f1-5f-41-00-85-03-19,
2026-01-23T17:23:02.432+00:00,85.016000,0x000b,96,63,0,1,f1-60-3f-00-88-03-1b,f1-60-3f-00-88-03-1b,
2026-01-23T17:23:07.432+00:00,90.016000,0x000b,97,61,0,1,f1-61-3d-00-8c-03-1d,f1-61-3d-00-8c-03-1d,
2026-01-23T17:23:12.432+00:00,95.016000,0x000b,97,62,0,1,f1-61-3e-00-8e-03-20,f1-61-3e-00-8e-03-20,
2026-01-23T17:23:17.432+00:00,100.016000,0x000b,96,64,0,1,f1-60-40-00-89-03-1c,f1-60-40-00-89-03-1c,
2026-01-23T17:23:22.432+00:00,105.016000,0x000b,95,67,0,1,f1-5f-43-00-84-03-19,f1-5f-43-00-84-03-19,
2026-01-23T17:23:27.432+00:00,110.016000,0x000b,94,70,0,1,f1-5e-46-00-80-03-17,f1-5e-46-00-80-03-17,
2026-01-23T17:23:32.432+00:00,115.016000,0x000b,93,73,0,1,f1-5d-49-00-7c-03-15,f1-5d-49-00-7c-03-15,
2026-01-23T17:23:37.432+00:00,120.016000,0x000b,92,76,0,1,f1-5c-4c-00-78-03-13,f1-5c-4c-00-78-03-13,
2026-01-23T17:23:42.432+00:00,125.016000,0x000b,91,78,0,1,f1-5b-4e-00-75-03-11,f1-5b-4e-00-75-03-11,
2026-01-23T17:23:47.432+00:00,130.016000,0x000b,90,80,0,1,f1-5a-50-00-72-03-0f,f1-5a-50-00-72-03-0f,
2026-01-23T17:23:52.432+00:00,135.016000,0x000b,91,77,0,1,f1-5b-4d-00-76-03-12,f1-5b-4d-00-76-03-12,
2026-01-23T17:23:57.432+00:00,140.016000,0x000b,92,74,0,1,f1-5c-4a-00-7a-03-14,f1-5c-4a-00-7a-03-14,
2026-01-23T17:24:02.432+00:00,145.016000,0x000b,93,71,0,1,f1-5d-47-00-7e-03-16,f1-5d-47-00-7e-03-16,
2026-01-23T17:24:07.432+00:00,150.016000,0x000b,94,69,0,1,f1-5e-45-00-82-03-18,f1-5e-45-00-82-03-18,
2026-01-23T17:24:12.432+00:00,155.016000,0x000b,95,67,0,1,f1-5f-43-00-86-03-1a,f1-5f-43-00-86-03-1a,`;

/**
 * Get SpO₂ status classification based on value.
 *
 * Clinical thresholds based on:
 * - Jubran A. Pulse oximetry. Crit Care. 2015;19(1):272.
 * - FDA Safety Communication (Feb 2021)
 */
export function getSpO2Status(value: number): {
  status: 'critical' | 'warning' | 'borderline' | 'normal';
  label: string;
  color: string;
} {
  if (value < 88) {
    return { status: 'critical', label: 'Severe Hypoxemia', color: '#ef4444' };
  }
  if (value < 92) {
    return { status: 'warning', label: 'Hypoxemia', color: '#f59e0b' };
  }
  if (value < 95) {
    return { status: 'borderline', label: 'Borderline', color: '#eab308' };
  }
  return { status: 'normal', label: 'Normal', color: '#22c55e' };
}

/**
 * Get heart rate status classification based on value.
 *
 * Physiological thresholds based on:
 * - American Heart Association guidelines
 * - Resting adult heart rate norms
 */
export function getHeartRateStatus(value: number): {
  status: 'bradycardia' | 'normal' | 'elevated' | 'tachycardia';
  label: string;
  color: string;
} {
  if (value < 50) {
    return { status: 'bradycardia', label: 'Bradycardia', color: '#f59e0b' };
  }
  if (value <= 100) {
    return { status: 'normal', label: 'Normal', color: '#22c55e' };
  }
  if (value <= 130) {
    return { status: 'elevated', label: 'Elevated', color: '#eab308' };
  }
  return { status: 'tachycardia', label: 'Tachycardia', color: '#ef4444' };
}
