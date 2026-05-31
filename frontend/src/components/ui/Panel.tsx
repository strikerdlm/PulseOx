'use client';

import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PanelProps {
  title?: string;
  right?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

/**
 * Instrument-console surface: hairline panel with a tracked-out label header.
 */
export function Panel({
  title,
  right,
  className,
  bodyClassName,
  children,
}: PanelProps): JSX.Element {
  return (
    <section className={cn('panel animate-rise overflow-hidden', className)}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-console-border/70 px-4 py-2.5">
          {title && <span className="label">{title}</span>}
          {right && <div className="flex items-center gap-2">{right}</div>}
        </header>
      )}
      <div className={cn('p-4', bodyClassName)}>{children}</div>
    </section>
  );
}
