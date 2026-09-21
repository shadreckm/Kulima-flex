'use client'

import React from 'react'
import type { AssessmentContext } from '../../lib/assessment-store'

type Props = {
  context: AssessmentContext
  /** Live run status overrides the stored context status when available. */
  status?: string | null
  compact?: boolean
}

const STATUS_LABELS: Record<string, string> = {
  intake: 'Draft',
  needs_confirmation: 'Needs Confirmation',
  ready: 'Ready',
  running: 'Running',
  complete: 'Complete',
  failed: 'Failed',
}

/**
 * Step 4: the Signals / Flex surfaces only display what the single intake
 * already knows — Assessment, Type, Status. No duplicate questions.
 */
export default function AssessmentSummaryBar({ context, status, compact = false }: Props) {
  const statusKey = String(context.status || 'intake')
  const runStatus = status ? String(status).toLowerCase() : ''
  const displayStatusKey =
    runStatus === 'completed' ? 'complete' : runStatus === 'running' ? 'running' : statusKey
  const statusLabel = STATUS_LABELS[displayStatusKey] || displayStatusKey
  const healthy = displayStatusKey === 'ready' || displayStatusKey === 'running' || displayStatusKey === 'complete'

  const entity = context.displayEntity || context.entityName || 'Pending extraction'
  const typeLabel = context.assessmentTypeLabel || context.entityLabel || 'Assessment'
  const docCount = context.documentCount ?? context.uploadedDocuments?.length ?? 0

  return (
    <section
      aria-label="Assessment context"
      className={`bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas ${compact ? 'px-4 py-3' : 'px-5 py-3.5'}`}
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-[9px] font-black uppercase tracking-wider text-slate-400">Assessment</span>
          <span className="font-extrabold text-[#101828] truncate max-w-[240px]">{entity}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-black uppercase tracking-wider text-slate-400">Type</span>
          <span className="font-bold text-slate-800">{typeLabel}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-black uppercase tracking-wider text-slate-400">Status</span>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider border ${
              healthy
                ? 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]'
                : 'bg-[#FFFAEB] text-[#7A4B00] border-[#FEDF89]'
            }`}
          >
            {statusLabel}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-4 text-[10px] text-slate-400 font-semibold">
          {context.confidence != null && <span>{Math.round(context.confidence * 100)}% extraction</span>}
          <span>
            {docCount} document{docCount === 1 ? '' : 's'}
          </span>
          {context.trustScore != null && <span>Trust {Math.round(context.trustScore)}/100</span>}
          <span className="hidden md:inline text-slate-300">Collected once · reused everywhere</span>
        </div>
      </div>
    </section>
  )
}
