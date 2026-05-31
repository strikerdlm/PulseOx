'use client';

import { useRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { downloadPng, downloadSvg } from '@/lib/exportFigure';

interface PanelProps {
  title?: string;
  right?: ReactNode;
  /** When set, shows SVG/PNG export controls for the first <svg> in the body. */
  exportName?: string;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

/**
 * Instrument-console surface: hairline panel with a tracked-out label header
 * and optional figure-export controls.
 */
export function Panel({
  title,
  right,
  exportName,
  className,
  bodyClassName,
  children,
}: PanelProps): JSX.Element {
  const bodyRef = useRef<HTMLDivElement>(null);

  const exportFigure = (type: 'svg' | 'png'): void => {
    const svg = bodyRef.current?.querySelector('svg');
    if (!(svg instanceof SVGSVGElement)) return;
    if (type === 'svg') downloadSvg(svg, exportName ?? 'figure');
    else void downloadPng(svg, exportName ?? 'figure');
  };

  const hasHeader = Boolean(title || right || exportName);

  return (
    <section className={cn('panel animate-rise overflow-hidden', className)}>
      {hasHeader && (
        <header className="flex items-center justify-between gap-3 border-b border-console-border/70 px-4 py-2.5">
          {title && <span className="label">{title}</span>}
          <div className="flex items-center gap-2">
            {right}
            {exportName && (
              <div className="flex items-center gap-1">
                <ExportButton onClick={() => exportFigure('svg')}>SVG</ExportButton>
                <ExportButton onClick={() => exportFigure('png')}>PNG</ExportButton>
              </div>
            )}
          </div>
        </header>
      )}
      <div ref={bodyRef} className={cn('p-4', bodyClassName)}>
        {children}
      </div>
    </section>
  );
}

function ExportButton({
  onClick,
  children,
}: {
  onClick: () => void;
  children: ReactNode;
}): JSX.Element {
  return (
    <button
      onClick={onClick}
      className="label rounded border border-console-border/70 px-1.5 py-0.5 !text-[0.55rem] text-console-muted transition-colors hover:border-vital-spo2/50 hover:text-vital-spo2"
    >
      ⤓ {children}
    </button>
  );
}
