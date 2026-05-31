import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PulseOx Console — Pulse Oximetry Monitoring',
  description:
    'Aeromedical instrument console for real-time and recorded pulse oximetry: live SpO₂ / heart-rate gauges, device control, and session analysis.',
  keywords: [
    'pulse oximetry',
    'SpO2',
    'oxygen saturation',
    'heart rate',
    'aerospace medicine',
    'realtime monitoring',
  ],
  authors: [{ name: 'PulseOx' }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen text-console-ink antialiased">{children}</body>
    </html>
  );
}
