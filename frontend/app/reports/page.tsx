'use client'

import React, { Suspense } from 'react'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { reportDownloadHref } from '../../lib/api'
import { useAssessmentWorkspace } from '../../hooks/useAssessmentWorkspace'
import Link from 'next/link'

// ── Report definitions with entity-type framing ───────────────────────────

type ReportKind = 'memo' | 'report' | 'signals' | 'due-diligence' | 'one-pager'

type ReportDef = {
  kind: ReportKind
  label: string
  description: string
  useCases: string[]         // which assessment types this is most useful for
  audience: string           // who reads this report
  format: 'pdf' | 'txt'
  primary: boolean           // show as primary CTA
}

const REPORTS: ReportDef[] = [
  {
    kind: 'memo',
    label: 'Investment / Decision Memo',
    description: 'Executive recommendation, rationale, trust score, key risks and opportunities in a single signed document.',
    useCases: ['Startup', 'Tourism SME', 'NGO', 'Development Program', 'Government Program'],
    audience: 'Investment Committee · Donor Board · Senior Management',
    format: 'pdf',
    primary: true,
  },
  {
    kind: 'report',
    label: 'Full IC Report',
    description: 'Complete analysis package: evidence integrity, domain scores, signal breakdown, contradictions, and MEAL indicators.',
    useCases: ['Startup', 'NGO', 'Development Program', 'Government Program'],
    audience: 'Investment Committee · Program Review Panel · Auditors',
    format: 'pdf',
    primary: true,
  },
  {
    kind: 'signals',
    label: 'Signals Report',
    description: 'Detected risk and opportunity signals across 9 domains: Trust, Risk, Market, Funding, Climate, Tourism, Community, Environment, Opportunity.',
    useCases: ['Startup', 'Tourism SME', 'NGO', 'Government Program'],
    audience: 'Risk Officers · Program Analysts · Sector Specialists',
    format: 'pdf',
    primary: false,
  },
  {
    kind: 'due-diligence',
    label: 'Due Diligence Summary',
    description: 'Evidence integrity audit, source attribution, corroboration status, verification checklist, and unsupported claims.',
    useCases: ['Startup', 'NGO', 'Development Program'],
    audience: 'Legal Team · External Auditors · Compliance Officers',
    format: 'pdf',
    primary: false,
  },
  {
    kind: 'one-pager',
    label: 'Executive One Pager',
    description: 'Single-page summary for board, donor, or parliamentary review. Verdict, trust score, and top 3 findings.',
    useCases: ['Startup', 'Tourism SME', 'NGO', 'Government Program'],
    audience: 'Board · Parliament · Donors · Partners',
    format: 'pdf',
    primary: false,
  },
]

// ── Future integrations (Phase 7 architecture) ────────────────────────────

const FUTURE_INTEGRATIONS = [
  { label: 'UNDP Result-Based Management', note: 'Coming soon · NGO / Development Program', icon: '🇺🇳' },
  { label: 'EU PPRD / PRAG Standards',     note: 'Coming soon · Government Program',       icon: '🇪🇺' },
  { label: 'USAID MEL Framework',          note: 'Coming soon · Development Program',       icon: '🏛️' },
  { label: 'IFC ESG Standards',            note: 'Coming soon · Startup / Tourism SME',     icon: '🌍' },
]

// ── Page ─────────────────────────────────────────────────────────────────

function ReportsPageInner() {
  const { status: authStatus } = useSession()
  const { data: ctx, runId, loading, error } = useAssessmentWorkspace(authStatus === 'authenticated')

  const entityTypeLabel = ctx?.assessmentTypeLabel || 'Assessment'
  const entityName = ctx?.displayEntity || ctx?.organizationName || ctx?.startupName || 'Current Assessment'

  if (authStatus === 'loading') {
    return <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
        <button onClick={() => signIn()} className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm">Sign in</button>
      </div>
    )
  }

  return (
    <PilotWorkspaceShell
      workspace="Reports"
      title="Reports"
      description="Download evidence-backed reports for your investment committee, donors, or program review."
      runId={runId}
      status={ctx?.status}
      startupName={entityName}
      trustScore={ctx?.trustScore}
      assessmentCtx={ctx ? {
        entityType: (ctx.assessmentType as any) || 'startup',
        entityLabel: ctx.assessmentTypeLabel || 'Assessment',
        entityName: ctx.displayEntity || ctx.organizationName || ctx.startupName || '',
        founderOrLead: ctx.founderName || '',
        runId: ctx.runId || '',
        createdAt: ctx.createdAt || '',
        hasDocument: (ctx.documentCount ?? 0) > 0,
        assessmentId: ctx.assessmentId,
        assessmentTypeLabel: ctx.assessmentTypeLabel,
        status: ctx.status,
        displayEntity: ctx.displayEntity || ctx.organizationName || ctx.startupName,
        sector: ctx.sector,
        confidence: ctx.confidence,
        trustScore: ctx.trustScore,
        documentCount: ctx.documentCount,
        decision: ctx.decision,
      } : null}
    >
      {error && !loading && (
        <div className="p-4 bg-amber-50 text-amber-800 rounded-[12px] border border-amber-200 text-sm">
          {error}{' '}
          <Link href="/flex" className="underline font-bold ml-2">Open workspace</Link>
        </div>
      )}

      {loading && (
        <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] text-sm text-slate-400 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#0B5D3B] animate-pulse" />
          Loading assessment context…
        </div>
      )}

      {/* Report header */}
      {ctx && (
        <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Current Assessment</div>
            <div className="text-base font-black text-slate-900 mt-0.5">{entityName}</div>
            <div className="flex items-center gap-2 mt-1 flex-wrap text-[11px] text-slate-500">
              <span>{entityTypeLabel}</span>
              {ctx.founderName && <><span>·</span><span>Lead: {ctx.founderName}</span></>}
              {ctx.trustScore != null && <><span>·</span><span className="font-bold text-[#0B5D3B]">Trust {Math.round(ctx.trustScore)}/100</span></>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-black px-2.5 py-1 rounded border uppercase tracking-wider ${
              ctx.status === 'complete' || ctx.status === 'completed' ? 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]' :
              ctx.status === 'running' ? 'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]' :
              'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]'
            }`}>{ctx.status || 'pending'}</span>
          </div>
        </section>
      )}

      {/* Report downloads */}
      {!runId && !loading ? (
        <div className="p-8 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-center">
          <div className="text-2xl mb-3">📊</div>
          <div className="text-sm font-bold text-slate-700">No assessment in progress</div>
          <div className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">Upload documents and run an assessment to generate downloadable reports.</div>
          <Link href="/" className="mt-4 inline-block px-4 py-2 rounded-lg bg-[#0B5D3B] text-white text-xs font-bold hover:bg-[#08482E] transition">
            Start Assessment →
          </Link>
        </div>
      ) : null}

      {runId ? (
        <>
          {/* Primary reports */}
          <section>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-3">Primary Reports</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {REPORTS.filter(r => r.primary).map(report => (
                <div key={report.kind} className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div>
                      <div className="text-sm font-extrabold text-slate-900">{report.label}</div>
                      <div className="text-xs text-slate-500 mt-1 leading-5">{report.description}</div>
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-400 mb-3">
                    <span className="font-bold">Audience:</span> {report.audience}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <a
                      className="px-4 py-2 rounded-lg bg-[#0B5D3B] text-white hover:bg-[#08482E] text-xs font-bold transition shadow-sm inline-flex items-center gap-1.5"
                      href={reportDownloadHref(runId, report.kind, 'pdf')}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Download PDF
                    </a>
                    <a
                      className="px-4 py-2 rounded-lg border border-[#DDE6F0] text-xs font-semibold text-slate-700 hover:bg-[#F5F8FC] transition"
                      href={reportDownloadHref(runId, report.kind, 'txt')}
                    >
                      Download TXT
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Supporting reports */}
          <section>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-3">Supporting Reports</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {REPORTS.filter(r => !r.primary).map(report => (
                <div key={report.kind} className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="text-sm font-extrabold text-slate-900 mb-1">{report.label}</div>
                  <div className="text-xs text-slate-500 leading-5 mb-2">{report.description}</div>
                  <div className="text-[10px] text-slate-400 mb-3">
                    <span className="font-bold">Audience:</span> {report.audience}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <a
                      className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] text-white hover:bg-[#08482E] text-xs font-bold transition"
                      href={reportDownloadHref(runId, report.kind, 'pdf')}
                    >
                      PDF
                    </a>
                    <a
                      className="px-3 py-1.5 rounded-lg border border-[#DDE6F0] text-xs font-semibold text-slate-700 hover:bg-[#F5F8FC] transition"
                      href={reportDownloadHref(runId, report.kind, 'txt')}
                    >
                      TXT
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}

      {/* Future integrations */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#DDE6F0]">
          <h2 className="text-sm font-extrabold text-slate-700 uppercase tracking-wider">Report Integrations — Roadmap</h2>
          <span className="text-[10px] font-bold text-slate-400 uppercase">Coming Soon</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {FUTURE_INTEGRATIONS.map(intg => (
            <div key={intg.label} className="flex items-center gap-3 p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="text-xl">{intg.icon}</span>
              <div>
                <div className="text-xs font-bold text-slate-700">{intg.label}</div>
                <div className="text-[10px] text-slate-400">{intg.note}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}

export default function ReportsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <ReportsPageInner />
    </Suspense>
  )
}
