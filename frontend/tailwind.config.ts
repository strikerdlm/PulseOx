import type { Config } from 'tailwindcss';

/**
 * "Aeromedical instrument console" design tokens.
 * Dark, precise, patient-monitor-meets-cockpit. Calibrated clinical zone
 * colors; tabular-mono numerics; hairline structure.
 */
const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        console: {
          bg: '#070a0f',
          panel: '#0c1118',
          raised: '#11171f',
          border: '#1b2330',
          hair: '#232c3b',
          ink: '#e7eef6',
          muted: '#8b95a7',
          faint: '#566173',
        },
        vital: {
          normal: '#35d39a',
          borderline: '#f7c24b',
          warning: '#fb923c',
          critical: '#fb5a72',
          spo2: '#22d3ee',
          hr: '#f472b6',
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      letterSpacing: {
        label: '0.18em',
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 30px -12px rgba(0,0,0,0.7)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out both',
        rise: 'rise 0.5s cubic-bezier(0.16,1,0.3,1) both',
        sweep: 'sweep 1.4s ease-in-out infinite',
        'ping-dot': 'pingDot 1.6s cubic-bezier(0,0,0.2,1) infinite',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        rise: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        sweep: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        pingDot: {
          '0%': { transform: 'scale(1)', opacity: '0.7' },
          '70%, 100%': { transform: 'scale(2.4)', opacity: '0' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
