'use client';

import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  headerRight?: ReactNode;
  variant?: 'default' | 'glass' | 'gradient';
  glow?: 'none' | 'green' | 'blue' | 'red';
}

/**
 * Card component for dashboard content containers.
 *
 * Design inspired by modern dashboard UIs with:
 * - Glass-morphism effects
 * - Subtle gradients
 * - Optional glow effects for status indication
 */
export function Card({
  children,
  className,
  title,
  subtitle,
  headerRight,
  variant = 'default',
  glow = 'none',
}: CardProps): JSX.Element {
  return (
    <div
      className={cn(
        'rounded-2xl border transition-all duration-300',
        // Base styles
        variant === 'default' && 'bg-slate-800/50 border-slate-700/50',
        variant === 'glass' && [
          'bg-gradient-to-br from-slate-800/40 to-slate-900/40',
          'border-slate-600/30 backdrop-blur-xl',
          'shadow-xl shadow-black/10',
        ],
        variant === 'gradient' && [
          'bg-gradient-to-br from-slate-800/60 via-slate-800/40 to-slate-900/60',
          'border-slate-600/20 backdrop-blur-lg',
        ],
        // Glow effects
        glow === 'green' && 'shadow-lg shadow-green-500/10 border-green-500/20',
        glow === 'blue' && 'shadow-lg shadow-blue-500/10 border-blue-500/20',
        glow === 'red' && 'shadow-lg shadow-red-500/10 border-red-500/20',
        className
      )}
    >
      {(title || headerRight) && (
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/30">
          <div>
            {title && (
              <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
            )}
            {subtitle && (
              <p className="text-sm text-slate-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          {headerRight && <div>{headerRight}</div>}
        </div>
      )}
      <div className={cn((title || headerRight) ? 'p-6' : 'p-6')}>{children}</div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string | number;
  unit?: string;
  change?: number | null;
  icon?: ReactNode;
  status?: 'normal' | 'warning' | 'critical';
}

/**
 * Stat Card for displaying key metrics with change indicators.
 */
export function StatCard({
  title,
  value,
  unit,
  change,
  icon,
  status = 'normal',
}: StatCardProps): JSX.Element {
  return (
    <div
      className={cn(
        'rounded-xl border p-4 transition-all',
        'bg-gradient-to-br from-slate-800/50 to-slate-900/50',
        status === 'normal' && 'border-slate-700/50',
        status === 'warning' && 'border-amber-500/30 shadow-amber-500/10 shadow-lg',
        status === 'critical' && 'border-red-500/30 shadow-red-500/10 shadow-lg'
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-400">{title}</p>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-2xl font-bold text-slate-100">{value}</span>
            {unit && <span className="text-sm text-slate-400">{unit}</span>}
          </div>
          {change !== null && change !== undefined && (
            <div
              className={cn(
                'mt-1 text-xs font-medium',
                change > 0 && 'text-green-400',
                change < 0 && 'text-red-400',
                change === 0 && 'text-slate-400'
              )}
            >
              {change > 0 ? '↑' : change < 0 ? '↓' : '→'} {Math.abs(change)}
              {unit}
            </div>
          )}
        </div>
        {icon && (
          <div
            className={cn(
              'p-2 rounded-lg',
              status === 'normal' && 'bg-slate-700/50 text-slate-300',
              status === 'warning' && 'bg-amber-500/20 text-amber-400',
              status === 'critical' && 'bg-red-500/20 text-red-400'
            )}
          >
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
