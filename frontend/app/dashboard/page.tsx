'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getPilotAnalytics, listLiveRuns, listStoredRuns, type LiveRunRecord, type PilotAnalyticsMetrics, type StoredRunRecord } from '../../lib/api'
import { useRouter } from 'next/navigation'
import { OSTX_CASES, saveCurrentRun } from '../../lib/current-run'
import TrustGauge from '../../components/TrustGauge/TrustGauge'

function metric(metrics: PilotAnalyticsMetrics | null, key: string): string {
  if (!metrics) return '—'
  const value = metrics[key]
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(1)
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return value
  return '—'
}

export default function DashboardPage() {
  const { status: authStatus } = useSession()
  const router = useRouter()
  const [metrics, setMetrics] = useState<PilotAnalyticsMetrics | null>(null)
  const [liveRuns, setLiveRuns] = useState<LiveRunRecord[]>([])
  const [storedRuns, setStoredRuns] = useState<StoredRunRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [analyticsRes, liveRes, storedRes] = await Promise.all([
          getPilotAnalytics(),
          listLiveRuns(20),
          listStoredRuns(20, true),
        ])
        if (cancelled) return
        setMetrics(analyticsRes)
        setLiveRuns(liveRes.runs)
        setStoredRuns(storedRes.runs)
      } catch (err) {
        if (!cancelled) setError(String(err))
      }
    }
    if (authStatus === 'authenticated') {
      load()
    }
    return () => { cancelled = true }
  }, [authStatus])

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
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima OS</div>
        <button
          onClick={() => signIn()}
          className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm"
        >
          Sign in
        </button>
      </div>
    )
  }

  const archivedRuns = storedRuns.filter(run => run.archivedAt)
  const activeStoredRuns = storedRuns.filter(run => !run.archivedAt)
  const latestRuns = [...storedRuns].sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt))).slice(0, 5)

  function handleLaunchOstxCase(c: typeof OSTX_CASES[number]) {
    const runState = {
      runId: c.liveRunId,
      startupName: c.startupName,
      founderName: c.founderName,
      recommendation: c.recommendation,
      trustScore: c.trustScore,
      status: 'completed',
    }
    saveCurrentRun(runState)
    router.push(`/flex?run=${encodeURIComponent(c.liveRunId)}`)
  }

  return (
    <PilotWorkspaceShell
      workspace="Dashboard"
      title="Kulima OS — Executive Dashboard"
      description="Select an OSTX validation case or review active intelligence runs, evidence integrity, and pilot metrics."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      {/* OSTX Validation Cases Hero Section */}
      <section className="p-6 bg-gradient-to-br from-[#061C14] via-[#0B5D3B] to-[#17855A] text-white rounded-[12px] border border-[#0E3627] shadow-saas-elevated">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4 pb-3 border-b border-white/15">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">
                Evaluation Suite
              </span>
              <span className="text-xs text-emerald-200 font-semibold">OSTX Presets</span>
            </div>
            <h2 className="text-xl md:text-2xl font-black tracking-tight text-white mt-1">
              OSTX Validation Cases
            </h2>
            <p className="text-xs text-emerald-100/80 mt-1 max-w-2xl leading-relaxed">
              One-click preset workflows. Explore end-to-end Flex IC Analyst, Signals Intelligence, Evidence Integrity, Reports, and Pilot Feedback.
            </p>
          </div>
          <span className="self-start md:self-auto bg-[#174836] text-emerald-200 border border-emerald-400/30 text-xs px-3 py-1.5 rounded-lg font-bold uppercase tracking-wider">
            Ready to Explore
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-4">
          {OSTX_CASES.map((c, idx) => (
            <div
              key={c.liveRunId}
              onClick={() => handleLaunchOstxCase(c)}
              className="bg-white/10 hover:bg-white/15 backdrop-blur-md border border-white/15 hover:border-emerald-400 rounded-[12px] p-5 cursor-pointer transition-all duration-200 flex flex-col justify-between group shadow-sm hover:shadow-md"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-extrabold uppercase tracking-widest text-emerald-300">
                    Case #{idx + 1}
                  </span>
                  <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-black uppercase tracking-wider ${
                    c.outcome === 'INVEST' ? 'bg-[#12B76A] text-white shadow-sm' :
                    c.outcome === 'OBSERVE' ? 'bg-[#F79009] text-white shadow-sm' :
                    'bg-[#F04438] text-white shadow-sm'
                  }`}>
                    {c.outcome}
                  </span>
                </div>
                <div className="text-lg font-black mt-2.5 text-white tracking-tight group-hover:text-emerald-200 transition-colors">
                  {c.startupName}
                </div>
                <div className="text-xs text-emerald-200/90 font-medium mt-0.5">{c.founderName}</div>
                <p className="text-xs text-emerald-100/80 mt-3 leading-relaxed">{c.summary}</p>
              </div>

              <div className="mt-5 pt-3 border-t border-white/15 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-emerald-300 font-medium">Trust Dial:</span>
                  <TrustGauge score={c.trustScore} size="sm" showLabel={false} />
                </div>
                <span className="text-xs font-bold text-emerald-300 group-hover:text-white flex items-center gap-1 group-hover:translate-x-0.5 transition-all">
                  Launch →
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Built Today vs Roadmap Architecture Section */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center gap-2 mb-3.5 pb-2.5 border-b border-[#DDE6F0]">
            <span className="w-2.5 h-2.5 rounded-full bg-[#12B76A] inline-block"></span>
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
              Built Today (OSTX Core Engine)
            </h2>
          </div>
          <div className="space-y-2.5 text-xs text-slate-700">
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-900">Flex Intelligence:</span> IC Analyst assistant, interactive briefing, and decision snapshot.
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-900">Signals Intelligence:</span> High-priority risk & opportunity signal detection and priority ranking.
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-900">Evidence Workspace:</span> Contradiction detection, source attribution, and verification checklists.
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-900">Reports Workspace:</span> PDF/TXT generation for Memos, Full IC Reports, Signals, DD, & One-Pagers.
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-900">Analytics Workspace:</span> Read-only cohort statistics, evidence coverage, and trust metrics.
            </div>
          </div>
        </div>

        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center gap-2 mb-3.5 pb-2.5 border-b border-[#DDE6F0]">
            <span className="w-2.5 h-2.5 rounded-full bg-[#004085] inline-block"></span>
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
              Roadmap (Future Intelligence Layers)
            </h2>
          </div>
          <div className="space-y-2.5 text-xs text-slate-600">
            <div className="p-3 bg-[#EAF3FF] rounded-lg border border-[#D6E8FF]">
              <span className="font-bold text-[#004085]">MEAL Intelligence:</span> Monitoring, Evaluation, Accountability, and Learning framework for post-investment tracking.
            </div>
            <div className="p-3 bg-[#EAF3FF] rounded-lg border border-[#D6E8FF]">
              <span className="font-bold text-[#004085]">Impact Intelligence:</span> Climate resilience scoring, socio-economic impact measurement, and carbon credit auditability.
            </div>
            <div className="p-3 bg-[#EAF3FF] rounded-lg border border-[#D6E8FF]">
              <span className="font-bold text-[#004085]">Development Intelligence Layer:</span> Automated alignment with DFI mandates, SDGs, and multi-lateral compliance frameworks.
            </div>
          </div>
        </div>
      </section>

      {/* Metrics Grid */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          ['Stored Runs', metric(metrics, 'total_runs')],
          ['Live Runs', String(liveRuns.length)],
          ['Archived Runs', String(archivedRuns.length)],
          ['Average Score', metric(metrics, 'average_score')],
          ['Average Confidence', metric(metrics, 'average_confidence')],
          ['Average Trust', metric(metrics, 'average_trust')],
          ['Evidence Coverage', `${metric(metrics, 'evidence_coverage')}%`],
          ['Signal Coverage', `${metric(metrics, 'signal_coverage')}%`],
        ].map(([label, value]) => (
          <div key={label} className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{label}</div>
            <div className="mt-1.5 text-2xl font-black text-slate-900 tracking-tight">{value}</div>
          </div>
        ))}
      </section>

      {/* Live Runs and Recent Stored Runs */}
      <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-[#DDE6F0]">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Live Runs</h2>
            <span className="text-xs text-slate-500 font-semibold">{liveRuns.length} Active</span>
          </div>
          <div className="space-y-3">
            {liveRuns.length === 0 ? (
              <div className="text-xs text-slate-500 py-3">No live runs recorded yet.</div>
            ) : liveRuns.map(run => (
              <div key={run.runId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="text-xs font-bold text-slate-900 break-all">{run.runId}</div>
                  <div className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-white text-slate-700 border border-[#DDE6F0]">
                    {run.status}
                  </div>
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Created: {run.createdAt || '—'}{run.completedAt ? ` · Completed: ${run.completedAt}` : ''}
                </div>
                {run.error ? <div className="text-xs text-red-600 font-semibold mt-1">{run.error}</div> : null}
              </div>
            ))}
          </div>
        </div>

        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-[#DDE6F0]">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Recent Stored Runs</h2>
            <span className="text-xs text-slate-500 font-semibold">{latestRuns.length} Loaded</span>
          </div>
          <div className="space-y-3">
            {latestRuns.length === 0 ? (
              <div className="text-xs text-slate-500 py-3">No stored runs available yet.</div>
            ) : latestRuns.map(run => (
              <div key={run.runId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 truncate">{run.startupName}</div>
                  <div className="text-[11px] text-slate-500">{run.founderName}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Score: {run.overallScore ?? '—'} · Grade: {run.integrityGrade ?? '—'}
                  </div>
                </div>
                {run.trustScore != null ? (
                  <TrustGauge score={run.trustScore} size="sm" showLabel={false} />
                ) : (
                  <span className="text-xs text-slate-400 italic">No score</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
