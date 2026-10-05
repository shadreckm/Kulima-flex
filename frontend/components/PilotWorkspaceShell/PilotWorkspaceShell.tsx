'use client'

import React from 'react'
import NavigationSidebar from '../NavigationSidebar/NavigationSidebar'
import KulimaLogo from '../KulimaLogo/KulimaLogo'
import UserMenu from '../UserMenu/UserMenu'
import { useState } from 'react'
import type { AssessmentContext } from '../../lib/assessment-store'

// ── Pipeline steps ────────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  { key: 'created',   label: 'Created',   shortLabel: 'Created'  },
  { key: 'research',  label: 'Research',  shortLabel: 'Research' },
  { key: 'evidence',  label: 'Evidence',  shortLabel: 'Evidence' },
  { key: 'signals',   label: 'Signals',   shortLabel: 'Signals'  },
  { key: 'decision',  label: 'Decision',  shortLabel: 'Decision' },
  { key: 'report',    label: 'Report',    shortLabel: 'Report'   },
] as const

type StepKey = typeof PIPELINE_STEPS[number]['key']
type StepState = 'done' | 'active' | 'pending'

function deriveStepStates(
  ctx: AssessmentContext | null | undefined,
  runStatus: string | null | undefined,
): Record<StepKey, StepState> {
  const rawStatus = String(ctx?.status || runStatus || 'intake').toLowerCase()
  const isDone    = rawStatus === 'complete' || rawStatus === 'completed'
  const isRunning = rawStatus === 'running'
  const hasDocs   = (ctx?.documentCount ?? 0) > 0 || (ctx?.uploadedDocuments?.length ?? 0) > 0
  const hasRun    = Boolean(ctx?.runId)
  const hasDecision = Boolean(
    ctx?.decision && typeof ctx.decision === 'object' && Object.keys(ctx.decision).length > 0
  )
  const hasResearch = Boolean(
    hasDocs || hasRun || isRunning || isDone
  )

  return {
    created:  'done',
    research: isDone ? 'done' : (hasResearch ? (isRunning ? 'active' : 'done') : 'pending'),
    evidence: isDone ? 'done' : (hasDocs ? 'done' : (hasRun ? 'active' : 'pending')),
    signals:  isDone ? 'done' : (hasDocs && hasRun ? (isDone ? 'done' : 'active') : 'pending'),
    decision: isDone || hasDecision ? 'done' : 'pending',
    report:   isDone ? 'done' : 'pending',
  }
}

// ── Styling helpers ───────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  complete:            'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]',
  completed:           'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]',
  running:             'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]',
  ready:               'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]',
  intake:              'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]',
  needs_confirmation:  'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]',
  failed:              'bg-[#FEF3F2] text-[#B42318] border-[#FECDCA]',
}

const TYPE_ICONS: Record<string, string> = {
  startup:             '🚀',
  ngo:                 '🌍',
  government_program:  '🏛️',
  development_program: '🏗️',
  tourism_sme:         '🏖️',
  accelerator:         '⚡',
}

// ── Props ─────────────────────────────────────────────────────────────────

type PilotWorkspaceShellProps = {
  workspace: string
  title: string
  description?: string
  runId?: string | number | null
  status?: string | null
  startupName?: string | null
  recommendation?: string | null
  trustScore?: number | null
  children: React.ReactNode
  rightRail?: React.ReactNode
  /** When provided, renders the consistent Assessment Header (Phases 1+2). */
  assessmentCtx?: AssessmentContext | null
}

// ── Component ─────────────────────────────────────────────────────────────

export default function PilotWorkspaceShell({
  workspace,
  title,
  description,
  runId,
  status,
  startupName,
  recommendation,
  trustScore,
  children,
  rightRail,
  assessmentCtx,
}: PilotWorkspaceShellProps) {
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)

  // Prefer assessmentCtx over legacy props
  const displayName   = assessmentCtx?.displayEntity || assessmentCtx?.entityName || startupName || null
  const displayType   = assessmentCtx?.assessmentTypeLabel || assessmentCtx?.entityLabel || null
  const typeIcon      = TYPE_ICONS[assessmentCtx?.entityType ?? ''] ?? ''
  const lead          = assessmentCtx?.founderOrLead || null
  const sector        = assessmentCtx?.sector || null
  const docCount      = assessmentCtx?.documentCount ?? assessmentCtx?.uploadedDocuments?.length ?? null
  const ctxTrust      = assessmentCtx?.trustScore
  const displayStatus = String(assessmentCtx?.status || status || 'intake').toLowerCase()
  const statusCls     = STATUS_COLOR[displayStatus] ?? 'bg-[#F5F8FC] text-slate-600 border-[#DDE6F0]'
  const statusLabel   = displayStatus.replace(/_/g, ' ')

  const stepStates = deriveStepStates(assessmentCtx, status)

  // Count how many steps are done (for the progress bar width)
  const donePct = Math.round(
    (Object.values(stepStates).filter(s => s === 'done').length / PIPELINE_STEPS.length) * 100
  )

  return (
    <div className="min-h-screen bg-[#F5F8FC] flex text-[#101828]">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex lg:flex-col w-64 flex-shrink-0 sticky top-0 h-screen p-4">
        <NavigationSidebar
          workspace={workspace}
          runId={assessmentCtx?.runId || runId}
          status={status}
          startupName={displayName}
          recommendation={recommendation}
          trustScore={ctxTrust ?? trustScore}
        />
      </div>

      {/* Mobile drawer */}
      {mobileDrawerOpen ? (
        <div
          className="fixed inset-0 bg-black/60 z-50 lg:hidden backdrop-blur-sm"
          onClick={() => setMobileDrawerOpen(false)}
        >
          <div
            className="fixed inset-y-0 left-0 w-72 z-50 p-4 bg-[#061C14] shadow-2xl overflow-y-auto flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <NavigationSidebar
              workspace={workspace}
              runId={assessmentCtx?.runId || runId}
              status={status}
              startupName={displayName}
              recommendation={recommendation}
              trustScore={ctxTrust ?? trustScore}
              onCloseMobile={() => setMobileDrawerOpen(false)}
            />
          </div>
        </div>
      ) : null}

      <div className="flex-1 flex flex-col min-w-0">
        {/* ── Sticky header ─────────────────────────────────────────── */}
        <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-[#DDE6F0] shadow-saas">

          {/* Row 1 — logo / breadcrumb */}
          <div className="px-4 md:px-8 py-3 flex items-center justify-between gap-4 max-w-7xl mx-auto">
            <div className="flex items-center gap-3 min-w-0">
              <button
                type="button"
                onClick={() => setMobileDrawerOpen(true)}
                className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100 border border-[#DDE6F0] transition focus:outline-none"
                aria-label="Open Navigation"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <div className="hidden sm:block"><KulimaLogo variant="header" /></div>
              <div className="w-px h-8 bg-[#DDE6F0] hidden sm:block flex-shrink-0" />
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <span className="hidden md:inline text-[#0B5D3B]">Kulima FLEX</span>
                  <span className="hidden md:inline">/</span>
                  <span className="text-[#0B5D3B]">{workspace}</span>
                </div>
                <h1 className="text-base font-extrabold text-[#101828] tracking-tight truncate">{title}</h1>
              </div>
            </div>

            {/* Right: user menu + status pill */}
            <div className="hidden sm:flex items-center gap-2 shrink-0">
              <UserMenu />
              {(assessmentCtx?.runId || runId) ? (
                <span className="bg-[#EAF3FF] border border-[#D6E8FF] px-3 py-1 rounded-lg text-[11px] font-bold text-[#004085] font-mono">
                  #{String(assessmentCtx?.runId || runId).slice(0, 10)}
                </span>
              ) : null}
              <span className={`px-2 py-0.5 rounded border text-[10px] font-extrabold uppercase tracking-wider ${statusCls}`}>
                {statusLabel}
              </span>
            </div>
          </div>

          {/* Row 2 — Assessment Header (Phase 1): always shown when ctx available */}
          {assessmentCtx ? (
            <div className="border-t border-[#DDE6F0] px-4 md:px-8 py-2 max-w-7xl mx-auto space-y-2">
              {/* Meta row */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                {/* Name + type */}
                <div className="flex items-center gap-1.5 min-w-0">
                  {typeIcon ? <span className="text-sm leading-none">{typeIcon}</span> : null}
                  <span className="text-xs font-extrabold text-[#101828] truncate max-w-[180px]">
                    {displayName || 'Assessment'}
                  </span>
                </div>
                {displayType ? (
                  <span className="px-2 py-0.5 rounded-full bg-[#F5F8FC] border border-[#DDE6F0] text-[10px] font-bold text-slate-600 uppercase tracking-wider">
                    {displayType}
                  </span>
                ) : null}

                {/* Lead */}
                {lead ? (
                  <span className="text-[11px] text-slate-500 font-medium hidden md:inline">
                    Lead: <strong className="text-slate-700">{lead}</strong>
                  </span>
                ) : null}

                {/* Sector */}
                {sector ? (
                  <span className="text-[11px] text-slate-400 hidden lg:inline">{sector}</span>
                ) : null}

                {/* Docs */}
                {docCount != null ? (
                  <span className="text-[11px] text-slate-500 font-medium hidden md:inline">
                    {docCount} doc{docCount !== 1 ? 's' : ''}
                  </span>
                ) : null}

                {/* Trust */}
                {ctxTrust != null ? (
                  <span className="text-[11px] font-bold text-[#0B5D3B] hidden md:inline">
                    Trust {Math.round(ctxTrust)}/100
                  </span>
                ) : null}

                {/* Status badge */}
                <span className={`ml-auto px-2 py-0.5 rounded border text-[10px] font-extrabold uppercase tracking-wider ${statusCls}`}>
                  {statusLabel}
                </span>
              </div>

              {/* Progress Tracker (Phase 2) — always visible, compact strip */}
              <div className="flex items-center gap-0">
                {PIPELINE_STEPS.map((step, idx) => {
                  const state = stepStates[step.key]
                  const isLast = idx === PIPELINE_STEPS.length - 1
                  return (
                    <React.Fragment key={step.key}>
                      <div className="flex flex-col items-center gap-0.5 min-w-0" style={{ minWidth: 52 }}>
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center border-2 text-[9px] font-black transition-all ${
                          state === 'done'   ? 'bg-[#12B76A] border-[#12B76A] text-white' :
                          state === 'active' ? 'bg-[#EAF3FF] border-[#2E90FA] text-[#004085] animate-pulse' :
                                               'bg-[#F5F8FC] border-[#DDE6F0] text-slate-300'
                        }`}>
                          {state === 'done' ? '✓' : (idx + 1)}
                        </div>
                        <span className={`text-[8px] font-bold uppercase tracking-wide leading-tight text-center ${
                          state === 'done'   ? 'text-[#027A48]' :
                          state === 'active' ? 'text-[#004085]' : 'text-slate-300'
                        }`}>{step.shortLabel}</span>
                      </div>
                      {!isLast ? (
                        <div className={`flex-1 h-0.5 min-w-[8px] mx-0.5 rounded-full ${
                          state === 'done' ? 'bg-[#12B76A]' : 'bg-[#DDE6F0]'
                        }`} />
                      ) : null}
                    </React.Fragment>
                  )
                })}
                {/* Overall % */}
                <span className="ml-3 text-[9px] font-bold text-slate-400 shrink-0">{donePct}%</span>
              </div>
            </div>
          ) : description ? (
            <div className="px-4 md:px-8 pb-2 max-w-7xl mx-auto text-xs text-slate-400 line-clamp-1 border-t border-[#DDE6F0]">
              {description}
            </div>
          ) : null}
        </header>

        {/* Workspace Body */}
        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {rightRail ? (
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 items-start">
              <div className="flex flex-col gap-6 min-w-0">{children}</div>
              <aside className="flex flex-col gap-6">{rightRail}</aside>
            </div>
          ) : (
            <div className="flex flex-col gap-6">{children}</div>
          )}
        </main>
      </div>
    </div>
  )
}
