'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';

interface Reference {
  id: string;
  authors: string;
  title: string;
  journal: string;
  year: number;
  doi?: string;
  url?: string;
  category: 'clinical' | 'methodology' | 'guidelines' | 'regulatory';
}

/**
 * Scientific References Component
 *
 * Displays verifiable citations for clinical thresholds and methodology.
 * All references are from peer-reviewed sources or official guidelines.
 */
export function References(): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const references: Reference[] = [
    // Clinical References
    {
      id: 'jubran2015',
      authors: 'Jubran A',
      title: 'Pulse oximetry',
      journal: 'Critical Care',
      year: 2015,
      doi: '10.1186/s13054-015-0984-8',
      url: 'https://ccforum.biomedcentral.com/articles/10.1186/s13054-015-0984-8',
      category: 'clinical',
    },
    {
      id: 'leon2024',
      authors: 'León-Valladares D, et al.',
      title: 'Determining factors of pulse oximetry accuracy: a literature review',
      journal: 'Revista Clínica Española (English Edition)',
      year: 2024,
      doi: '10.1016/j.rceng.2024.04.005',
      url: 'https://doi.org/10.1016/j.rceng.2024.04.005',
      category: 'clinical',
    },
    {
      id: 'gudelunas2022',
      authors: 'Gudelunas MK, et al.',
      title: 'Low perfusion and missed diagnosis of hypoxemia by pulse oximetry in darkly pigmented skin: a prospective study',
      journal: 'Anesthesia & Analgesia',
      year: 2022,
      doi: '10.1213/ANE.0000000000006755',
      url: 'https://doi.org/10.1213/ANE.0000000000006755',
      category: 'clinical',
    },
    {
      id: 'albeltagi2024',
      authors: 'Al-Beltagi M, et al.',
      title: 'Pulse oximetry in pediatric care: Balancing advantages and limitations',
      journal: 'World Journal of Clinical Pediatrics',
      year: 2024,
      doi: '10.5409/wjcp.v13.i3.96950',
      url: 'https://doi.org/10.5409/wjcp.v13.i3.96950',
      category: 'clinical',
    },
    // Guidelines
    {
      id: 'aha2020',
      authors: 'American Heart Association',
      title: 'Target Heart Rates Chart',
      journal: 'AHA Guidelines',
      year: 2020,
      url: 'https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates',
      category: 'guidelines',
    },
    {
      id: 'palatini1999',
      authors: 'Palatini P',
      title: 'Heart rate as a risk factor for atherosclerosis and cardiovascular mortality',
      journal: 'Drugs',
      year: 1999,
      doi: '10.2165/00003495-199957050-00006',
      url: 'https://doi.org/10.2165/00003495-199957050-00006',
      category: 'guidelines',
    },
    // Regulatory
    {
      id: 'fda2021',
      authors: 'U.S. Food and Drug Administration',
      title: 'Pulse Oximeter Accuracy and Limitations: FDA Safety Communication',
      journal: 'FDA Safety Communications',
      year: 2021,
      url: 'https://www.fda.gov/medical-devices/safety-communications/pulse-oximeter-accuracy-and-limitations-fda-safety-communication',
      category: 'regulatory',
    },
    // Methodology
    {
      id: 'tufte2001',
      authors: 'Tufte ER',
      title: 'The Visual Display of Quantitative Information',
      journal: 'Graphics Press',
      year: 2001,
      category: 'methodology',
    },
    {
      id: 'cleveland1994',
      authors: 'Cleveland WS',
      title: 'The Elements of Graphing Data',
      journal: 'Hobart Press',
      year: 1994,
      category: 'methodology',
    },
    {
      id: 'kelleher2011',
      authors: 'Kelleher C, Wagener T',
      title: 'Ten guidelines for effective data visualization in scientific publications',
      journal: 'Environmental Modelling & Software',
      year: 2011,
      doi: '10.1016/j.envsoft.2010.12.006',
      url: 'https://doi.org/10.1016/j.envsoft.2010.12.006',
      category: 'methodology',
    },
  ];

  const categories = [
    { id: 'clinical', label: 'Clinical Studies', color: 'text-emerald-400' },
    { id: 'guidelines', label: 'Guidelines', color: 'text-blue-400' },
    { id: 'regulatory', label: 'Regulatory', color: 'text-amber-400' },
    { id: 'methodology', label: 'Methodology', color: 'text-purple-400' },
  ];

  const filteredRefs = activeCategory
    ? references.filter((r) => r.category === activeCategory)
    : references;

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/30 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-700/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">📚</span>
          <div className="text-left">
            <h3 className="text-lg font-semibold text-slate-100">
              Scientific References & Citations
            </h3>
            <p className="text-sm text-slate-400">
              {references.length} peer-reviewed sources and official guidelines
            </p>
          </div>
        </div>
        <svg
          className={cn(
            'w-5 h-5 text-slate-400 transition-transform',
            isExpanded && 'rotate-180'
          )}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Expandable content */}
      {isExpanded && (
        <div className="border-t border-slate-700/50">
          {/* Category filters */}
          <div className="px-6 py-4 flex flex-wrap gap-2 border-b border-slate-700/30">
            <button
              onClick={() => setActiveCategory(null)}
              className={cn(
                'px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
                activeCategory === null
                  ? 'bg-slate-600 text-slate-100'
                  : 'bg-slate-800/50 text-slate-400 hover:text-slate-300'
              )}
            >
              All ({references.length})
            </button>
            {categories.map((cat) => {
              const count = references.filter((r) => r.category === cat.id).length;
              return (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
                    activeCategory === cat.id
                      ? 'bg-slate-600 text-slate-100'
                      : 'bg-slate-800/50 text-slate-400 hover:text-slate-300'
                  )}
                >
                  {cat.label} ({count})
                </button>
              );
            })}
          </div>

          {/* References list */}
          <div className="p-6 space-y-4 max-h-96 overflow-y-auto">
            {filteredRefs.map((ref, index) => {
              const catInfo = categories.find((c) => c.id === ref.category);
              return (
                <div
                  key={ref.id}
                  className="p-4 rounded-lg bg-slate-800/30 border border-slate-700/30"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={cn(
                            'text-xs font-medium uppercase',
                            catInfo?.color || 'text-slate-400'
                          )}
                        >
                          [{index + 1}] {ref.category}
                        </span>
                        <span className="text-xs text-slate-500">{ref.year}</span>
                      </div>
                      <p className="text-sm text-slate-200 font-medium">
                        {ref.authors}
                      </p>
                      <p className="text-sm text-slate-300 mt-1">
                        &ldquo;{ref.title}&rdquo;
                      </p>
                      <p className="text-xs text-slate-400 mt-1 italic">
                        {ref.journal}
                      </p>
                      {ref.doi && (
                        <p className="text-xs text-slate-500 mt-1">
                          DOI: {ref.doi}
                        </p>
                      )}
                    </div>
                    {ref.url && (
                      <a
                        href={ref.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={cn(
                          'flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium',
                          'bg-blue-500/10 text-blue-400 hover:bg-blue-500/20',
                          'transition-colors'
                        )}
                      >
                        View →
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Disclaimer */}
          <div className="px-6 py-4 border-t border-slate-700/30 bg-slate-900/30">
            <p className="text-xs text-slate-500">
              <strong className="text-slate-400">Medical Disclaimer:</strong> This
              dashboard is for research and educational purposes only. It is not
              intended for diagnosis, treatment, or clinical decision-making.
              SpO₂ readings from consumer pulse oximeters may have accuracy
              limitations. Always consult healthcare professionals for medical
              decisions.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
