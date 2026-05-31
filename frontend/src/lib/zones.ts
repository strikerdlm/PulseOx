/**
 * Clinical zone bands for the instrument gauges.
 *
 * SpO₂ thresholds: Jubran A. Crit Care 2015;19:272; FDA Safety Comm. (Feb 2021).
 * HR thresholds: AHA resting-adult ranges.
 */
export interface Zone {
  from: number;
  to: number;
  color: string;
  label: string;
}

export const SPO2_ZONES: Zone[] = [
  { from: 70, to: 88, color: '#fb5a72', label: 'Severe' },
  { from: 88, to: 92, color: '#fb923c', label: 'Hypoxemia' },
  { from: 92, to: 95, color: '#f7c24b', label: 'Borderline' },
  { from: 95, to: 100, color: '#35d39a', label: 'Normal' },
];

export const HR_ZONES: Zone[] = [
  { from: 40, to: 50, color: '#f7c24b', label: 'Brady' },
  { from: 50, to: 100, color: '#35d39a', label: 'Normal' },
  { from: 100, to: 130, color: '#f7c24b', label: 'Elevated' },
  { from: 130, to: 180, color: '#fb5a72', label: 'Tachy' },
];

export function zoneFor(zones: Zone[], value: number): Zone {
  for (const z of zones) {
    if (value >= z.from && value < z.to) return z;
  }
  return value < zones[0].from ? zones[0] : zones[zones.length - 1];
}
