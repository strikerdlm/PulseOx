import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PulseOx Safety Dashboard | Real-time Pulse Oximetry Monitoring',
  description:
    'Publication-quality safety management dashboard for pulse oximetry data visualization. Features real-time SpO₂ and heart rate monitoring with clinical threshold indicators.',
  keywords: [
    'pulse oximetry',
    'SpO2 monitoring',
    'oxygen saturation',
    'heart rate',
    'medical dashboard',
    'safety monitoring',
    'healthcare visualization',
  ],
  authors: [{ name: 'PulseOx Dashboard' }],
  openGraph: {
    title: 'PulseOx Safety Dashboard',
    description:
      'Real-time pulse oximetry monitoring with clinical-grade visualizations',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-radial-gradient antialiased">
        {children}
      </body>
    </html>
  );
}
