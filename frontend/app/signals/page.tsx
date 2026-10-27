'use client'

import React, { useEffect, useState, Suspense } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import ChatShell from '../../components/ChatShell/ChatShell'
import ContextPanel from '../../components/ContextPanel/ContextPanel'
import NavigationSidebar from '../../components/NavigationSidebar/NavigationSidebar'
import AssessmentSummaryBar from '../../components/AssessmentSummaryBar/AssessmentSummaryBar'
import * as api from '../../lib/api'
import type { SignalsSummary } from '../../lib/api'
import { useAssessmentBootstrap, type AssessmentBootState } from '../../hooks/useAssessmentBootstrap'
import AssessmentGuard from '../../components/AssessmentGuard/AssessmentGuard'

// Domain config mirrors ContextPanel but for the main-column overview
// PRIMARY EXPERIENCE: NGO and Development Program signal domains prioritized for V1
const DOMAIN_DISPLAY: Array<{ key: string; label: string; icon: string; description: string }> = [
  { key: 'trust',           label: 'Trust',        icon: 'ðŸ›¡ï¸', description: 'Source reliability, corroboration, and evidence integrity.' },
  { key: 'risk',            label: 'Risk',          icon: 'âš ï¸', description: 'Material risks and red flags requiring attention.' },
  { key: 'opportunity',     label: 'Opportunity',   icon: 'ðŸŒ±', description: 'Growth drivers and upside signals.' },
  { key: 'market',          label: 'Market',        icon: 'ðŸ“ˆ', description: 'Market size, competition, and positioning.' },
  { key: 'funding',         label: 'Funding',       icon: 'ðŸ’°', description: 'Funding readiness, burn rate, and capital efficiency.' },
  { key: 'climate',         label: 'Climate',       icon: 'ðŸŒ¤ï¸', description: 'Climate risk, sustainability, and net-zero alignment.' },
  { key: 'tourism',         label: 'Tourism',       icon: 'ðŸ§­', description: 'Tourism and destination impact signals.' },
  { key: 'community_impact',label: 'Community',     icon: 'ðŸ¤', description: 'Social impact, beneficiary reach, and community outcomes.' },
  { key: 'environmental',   label: 'Environment',   icon: 'ðŸŒ¿', description: 'Environmental compliance and ecological footprint.' },
]

function domainScoreTone(score: number): string {
  if (score >= 70) return 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]'
  if (score >= 50) return 'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]'
  return 'bg-[#FEF3F2] text-[#B42318] border-[#FECDCA]'
}

function domainBar(score: number): string {
  if (score >= 70) return 'bg-[#12B76A]'
  if (score >= 50) return 'bg-[#F79009]'
  return 'bg-[#F04438]'
}

function SignalsPageInner() {
  const { status: authStatus } = useSession()
  const [signalsSummary, setSignalsSummary] = useState<SignalsSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Single intake: the shared Assessment Context drives the run identity â€”
  // no founder / startup / entity-type re-entry, no legacy current-run store.
  const { assessmentContext, bootState, retry } = useAssessmentBootstrap({
    route: 'signals',
  })

  if (authStatus === 'loading') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">
        Checking sessionâ€¦
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
        <button
          onClick={() => signIn()}
          className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm"
        >
          Sign in
        </button>
      </div>
    )
  }

  const runId = assessmentContext?.runId || null
  const status = assessmentContext?.status || null
  const isLoading = bootState === 'idle' || bootState === 'starting' || bootState === 'started'

  // Global Assessment Guard: no assessment → auto-redirect to landing page
  // Only redirect when bootState is definitively 'no_assessment' - not while loading.
  if (bootState === 'no_assessment' || (bootState === 'none' && !assessmentContext)) {
    return <AssessmentGuard active label="Preparing your assessment…" loading={isLoading} />
  }

  // MVP reliability: Signals page must render whenever the assessment has
  // reached complete OR signals data exists — never poll forever. While the
  // context carries a signalsSummary (propagated on completion), render the
  // domain grid directly from it.
  const contextSignalsSummary = (assessmentContext?.signalsSummary ?? null) as SignalsSummary | null
  const effectiveSignals = signalsSummary || contextSignalsSummary
  const assessmentComplete = !!status && ['complete', 'completed'].includes(String(status).toLowerCase())
  const showDomains = Boolean(effectiveSignals) || assessmentComplete

  // STATE SYNCHRONIZATION FIX: Derive status from actual data, not just cached state
  // If signals exist, status should be 'complete' regardless of stored status
  const hasSignalsData = Boolean(effectiveSignals)
  const effectiveStatus = hasSignalsData ? 'complete' : status

  // Refetch the live summary from the run API when a run exists (once, plus a
  // short retry window if the run has just completed).
  useEffect(() => {
    if (!runId) return
    let cancelled = false
    let attempts = 0
    const maxAttempts = assessmentComplete ? 3 : 1
    async function load() {
      try {
        const data = await api.getSignalsSummary(runId as string)
        if (!cancelled && data) setSignalsSummary(data)
      } catch {
        // Context-level signalsSummary remains as the rendering source.
      }
    }
    load().then(() => {
      const timer = setInterval(() => {
        attempts += 1
        if (cancelled || attempts >= maxAttempts) {
          clearInterval(timer)
          return
        }
        load()
      }, 4000)
      return () => clearInterval(timer)
    })
    return () => {
      cancelled = true
    }
  }, [runId, assessmentComplete])

  return (
    <div className="h-screen overflow-hidden bg-[#F5F8FC] p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px] gap-6">
      <NavigationSidebar
        workspace="Signals"
        runId={runId}
        status={effectiveStatus}
        startupName={assessmentContext?.displayEntity || assessmentContext?.entityName}
        recommendation={assessmentContext?.decision?.recommendation}
        trustScore={assessmentContext?.trustScore}
      />
      <main className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
        {assessmentContext ? (
          <div className="flex-shrink-0">
            <AssessmentSummaryBar context={assessmentContext} status={effectiveStatus} hasData={hasSignalsData} />
          </div>
        ) : null}
        {assessmentContext && runId ? (
          <>
            <ChatShell personaName="Signals Analyst" runId={runId} />
            {/* Phase 5 + MVP reliability: Signal Domains Overview â€” renders
                whenever signals exist or the assessment is complete. */}
            {showDomains && effectiveSignals ? (
              <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#DDE6F0]">
                  <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Signal Domains</h2>
                  <div className="flex items-center gap-2 text-[10px] font-bold">
                    {effectiveSignals.critical > 0 && <span className="px-2 py-0.5 rounded bg-red-100 text-red-700 border border-red-200">{effectiveSignals.critical} Critical</span>}
                    {effectiveSignals.high > 0 && <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200">{effectiveSignals.high} High</span>}
                    {effectiveSignals.medium > 0 && <span className="px-2 py-0.5 rounded bg-yellow-100 text-yellow-700 border border-yellow-200">{effectiveSignals.medium} Medium</span>}
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                  {DOMAIN_DISPLAY.map(({ key, label, icon, description }) => {
                  const domainData = effectiveSignals.domains?.[key]
                    const signals = domainData?.signals ?? [
                      ...(effectiveSignals.topRisks || []),
                      ...(effectiveSignals.topOpportunities || []),
                    ].filter(s => (s.category || '').toLowerCase().includes(key.replace('_', '')))
                    const score = domainData?.score
                    const summary = domainData?.summary
                    const riskCount = domainData?.riskCount ?? signals.filter(s => s.direction === 'risk').length
                    const oppCount = domainData?.opportunityCount ?? signals.filter(s => s.direction === 'opportunity').length
                    const total = domainData?.count ?? signals.length

                    return (
                      <div key={key} className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                        {/* Domain header */}
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-base leading-none">{icon}</span>
                            <span className="text-xs font-extrabold text-slate-900">{label}</span>
                          </div>
                          {score != null ? (
                            <span className={`text-[10px] font-black px-1.5 py-0.5 rounded border ${domainScoreTone(score)}`}>
                              {Math.round(score)}/100
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-400">—</span>
                          )}
                        </div>
                        {summary ? (
                          <p className="text-[11px] text-slate-600 leading-relaxed">{summary}</p>
                        ) : null}
                        {total > 0 ? (
                          <div className="mt-2 text-[10px] text-slate-500">
                            {riskCount > 0 && <span className="text-red-600">{riskCount} risk</span>}
                            {riskCount > 0 && oppCount > 0 && <span> · </span>}
                            {oppCount > 0 && <span className="text-green-600">{oppCount} opportunity</span>}
                            {total > 0 && <span> · {total} total</span>}
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              </section>
            ) : null}
          </>
        ) : null}
        {!assessmentContext ? (
          <AssessmentGuard active label="Preparing your assessment…" loading={isLoading} />
        ) : null}
      </main>
      <ContextPanel type="signals" runId={runId} status={effectiveStatus} />
    </div>
  )
}

export default function SignalsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loadingâ€¦</div>}>
      <SignalsPageInner />
    </Suspense>
  )
}
