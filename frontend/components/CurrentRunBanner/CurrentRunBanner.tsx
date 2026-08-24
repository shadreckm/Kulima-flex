'use client'

import React from 'react'
import type { CurrentRunState } from '../../lib/current-run'
import TrustGauge from '../TrustGauge/TrustGauge'

type Props = {
  run: CurrentRunState
  onClear?: () => void
  compact?: boolean
}

export default function CurrentRunBanner({ run, onClear, compact = false }: Props) {
  const isInvest = run.recommendation === 'INVEST'
  const isObserve = run.recommendation === 'OBSERVE'

  return (
    <section className={`bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        {/* Identity Section */}
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]">
              Active Dossier
            </span>
            <span className="text-xs text-slate-500 font-mono">Run: {String(run.runId).slice(0, 16)}</span>
          </div>

          <div className="text-lg md:text-xl font-extrabold text-[#101828] mt-1.5 tracking-tight flex items-center gap-2.5">
            <span>{run.startupName || 'Active Venture Analysis'}</span>
            {run.recommendation ? (
              <span className={`text-xs px-2.5 py-0.5 rounded-full font-extrabold uppercase tracking-wide ${
                isInvest
                  ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]'
                  : isObserve
                  ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]'
                  : 'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
              }`}>
                {run.recommendation}
              </span>
            ) : null}
          </div>

          {run.founderName ? (
            <div className="text-xs text-slate-600 mt-0.5">
              Founder: <strong className="text-slate-900">{run.founderName}</strong>
            </div>
          ) : null}
        </div>

        {/* Visual Trust Gauge Container */}
        <div className="flex items-center gap-4 bg-[#F5F8FC] border border-[#DDE6F0] p-3 rounded-[10px] w-full md:w-auto justify-between md:justify-start">
          <TrustGauge
            score={run.trustScore}
            size="sm"
            showLabel={true}
            confidencePercent={run.trustScore ? Math.min(96, run.trustScore + 6) : null}
          />

          {onClear ? (
            <button
              type="button"
              onClick={onClear}
              className="text-xs font-semibold text-[#0B5D3B] hover:text-[#08482E] underline ml-2 whitespace-nowrap"
            >
              Switch run
            </button>
          ) : null}
        </div>
      </div>
    </section>
  )
}
