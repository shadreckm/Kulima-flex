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
import { useAssessmentBootstrap } from '../../hooks/useAssessmentBootstrap'

// Domain config mirrors ContextPanel but for the main-column overview
const DOMAIN_DISPLAY: Array<{ key: string; label: string; icon: string; description: string }> = [
  { key: 'trust',           label: 'Trust',        icon: '🛡️', description: 'Source reliability, corroboration, and evidence integrity.' },
  { key: 'risk',            label: 'Risk',          icon: '⚠️', description: 'Material risks and red flags requiring attention.' },
  { key: 'opportunity',     label: 'Opportunity',   icon: '🌱', description: 'Growth drivers and upside signals.' },
  { key: 'market',          label: 'Market',        icon: '📈', description: 'Market size, competition, and positioning.' },
  { key: 'funding',         label: 'Funding',       icon: '💰', description: 'Funding readiness, burn rate, and capital efficiency.' },
  { key: 'climate',         label: 'Climate',       icon: '🌤️', description: 'Climate risk, sustainability, and net-zero alignment.' },
  { key: 'tourism',         label: 'Tourism',       icon: '🧭', description: 'Tourism and destination impact signals.' },
  { key: 'community_impact',label: 'Community',     icon: '🤝', description: 'Social impact, beneficiary reach, and community outcomes.' },
  { key: 'environmental',   label: 'Environment',   icon: '🌿', description: 'Environmental compliance and ecological footprint.' },
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

  // Single intake: the shared Assessment Context drives the run identity —
  // no founder / startup / entity-type re-entry, no legacy current-run store.
  const { assessmentContext, bootState, retry } = useAssessmentBootstrap({
    route: 'signals',
  })

  if (authStatus === 'loading') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">
        Checking session…
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

  return (
    <div className="min-h-screen bg-[#F5F8FC] p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px] gap-6">
      <NavigationSidebar
        workspace="Signals"
        runId={runId}
        status={status}
        startupName={assessmentContext?.displayEntity || assessmentContext?.entityName}
        recommendation={assessmentContext?.decision?.recommendation}
        trustScore={assessmentContext?.trustScore}
      />
      <main className="flex flex-col gap-4">
        {assessmentContext ? <AssessmentSummaryBar context={assessmentContext} status={status} /> : null}
        {assessmentContext && runId ? (
          <>
            <ChatShell personaName="Signals Analyst" runId={runId} />
            {/* Phase 5: Signal Domains Overview — always visible when signals loaded */}
            {signalsSummary ? (
              <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#DDE6F0]">
                  <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Signal Domains</h2>
                  <div className="flex items-center gap-2 text-[10px] font-bold">
                    {signalsSummary.critical > 0 && <span className="px-2 py-0.5 rounded bg-red-100 text-red-700 border border-red-200">{signalsSummary.critical} Critical</span>}
                    {signalsSummary.high > 0 && <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200">{signalsSummary.high} High</span>}
                    {signalsSummary.medium > 0 && <span className="px-2 py-0.5 rounded bg-yellow-100 text-yellow-700 border border-yellow-200">{signalsSummary.medium} Medium</span>}
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                  {DOMAIN_DISPLAY.map(({ key, label, icon, description }) => {
                    const domainData = signalsSummary.domains?.[key]
                    const signals = domainData?.signals ?? [
                      ...(signalsSummary.topRisks || []),
                      ...(signalsSummary.topOpportunities || []),
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
                            <span className="text-[10px] font-bold text-slate-400">{total} signal{total !== 1 ? 's' : ''}</span>
                          )}
                        </div>

                        {/* Score bar */}
                        {score != null && (
                          <div className="h-1 rounded-full bg-slate-200 overflow-hidden mb-2">
                            <div className={`h-full rounded-full ${domainBar(score)}`}
                              style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
                          </div>
                        )}

                        {/* Description / summary */}
                        <p className="text-[11px] text-slate-500 leading-4 mb-2">
                          {summary || description}
                        </p>

                        {/* Risk / Opportunity counts */}
                        <div className="flex items-center gap-2 text-[10px]">
                          {riskCount > 0 && (
                            <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 font-bold">
                              {riskCount} Risk
                            </span>
                          )}
                          {oppCount > 0 && (
                            <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold">
                              {oppCount} Opportunity
                            </span>
                          )}
                          {riskCount === 0 && oppCount === 0 && total === 0 && (
                            <span className="text-slate-400 italic">No signals detected</span>
                          )}
                        </div>

                        {/* Domain recommendation */}
                        {domainData?.recommendation ? (
                          <div className="mt-2 pt-2 border-t border-slate-200 text-[10px] text-[#0B5D3B] font-bold">
                            → {domainData.recommendation}
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              </section>
            ) : null}
          </>
        ) : assessmentContext?.assessmentId ? (
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-sm">
            {bootState === 'needs_confirmation' ? (
              <>
                <div className="font-bold text-slate-900">
                  Extraction confidence is low — confirm the assessment identity once.
                </div>
                <p className="text-xs text-slate-500 mt-1 leading-5">
                  The shared assessment context was created from your upload, but the entity name could
                  not be extracted with confidence. Confirm it on the intake page — you will not be asked
                  again anywhere else.
                </p>
                <Link
                  href="/"
                  className="inline-block mt-3 rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-xs font-extrabold uppercase tracking-wider text-white hover:bg-[#08482E] transition"
                >
                  Review assessment details →
                </Link>
              </>
            ) : bootState === 'error' ? (
              <>
                <div className="font-bold text-slate-900">Could not start the assessment run.</div>
                <p className="text-xs text-slate-500 mt-1 leading-5">
                  The shared context is ready — retry starting the intelligence run. Tavily research and
                  signals run automatically once started.
                </p>
                {error ? (
                  <div className="mt-2 font-mono text-[10px] text-red-600 break-all">{error}</div>
                ) : null}
                <button
                  type="button"
                  onClick={retry}
                  className="mt-3 rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-xs font-extrabold uppercase tracking-wider text-white hover:bg-[#08482E] transition"
                >
                  Retry run start
                </button>
              </>
            ) : (
              <>
                <div className="font-bold text-slate-900 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#F79009] animate-pulse" />
                  Starting your assessment run from the shared context…
                </div>
                <p className="text-xs text-slate-500 mt-1 leading-5">
                  Tavily research and signal generation are driven by the extracted entity —{' '}
                  <strong className="text-slate-800">
                    {assessmentContext.displayEntity || assessmentContext.entityName || 'Assessment'}
                  </strong>
                  . No founder or organisation re-entry is needed.
                </p>
              </>
            )}
          </section>
        ) : (
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-sm">
            <div className="font-bold text-slate-900">No active assessment context found.</div>
            <p className="text-xs text-slate-500 mt-1 leading-5">
              To begin signals analysis, create an assessment on the landing page by uploading your documents.
            </p>
            <Link
              href="/"
              className="inline-block mt-3 rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-xs font-extrabold uppercase tracking-wider text-white hover:bg-[#08482E] transition"
            >
              Create Assessment →
            </Link>
          </section>
        )}
      </main>
      <ContextPanel type="signals" runId={runId} status={status} />
    </div>
  )
}

export default function SignalsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <SignalsPageInner />
    </Suspense>
  )
}
