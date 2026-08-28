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
  const [showDemoEvals, setShowDemoEvals] = useState(false)

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
  const activeEvaluations = activeStoredRuns.length + liveRuns.length

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
      description="Active evaluations, trust distribution, and outcome performance at a glance."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      {/* KPI Hero Row — above the fold */}
      <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {[
          {
            label: 'Active Evaluations',
            value: String(activeEvaluations),
            accent: activeEvaluations > 0 ? 'text-[#12B76A]' : 'text-slate-900',
            sub: `${liveRuns.length} live · ${activeStoredRuns.length} stored`,
          },
          {
            label: 'Average Trust Score',
            value: metric(metrics, 'average_trust'),
            accent: 'text-slate-900',
            sub: 'across all evaluations',
          },
          {
            label: 'Decision Accuracy',
            value: metric(metrics, 'average_score'),
            accent: 'text-slate-900',
            sub: 'pipeline average score',
          },
          {
            label: 'Evidence Coverage',
            value: `${metric(metrics, 'evidence_coverage')}%`,
            accent: 'text-slate-900',
            sub: 'of evaluations verified',
          },
          {
            label: 'Verification Coverage',
            value: `${metric(metrics, 'signal_coverage')}%`,
            accent: 'text-slate-900',
            sub: 'signal-verified runs',
          },
        ].map(({ label, value, accent, sub }) => (
          <div key={label} className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col gap-1">
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{label}</div>
            <div className={`text-2xl font-black tracking-tight ${accent}`}>{value}</div>
            <div className="text-[10px] text-slate-400 font-medium">{sub}</div>
          </div>
        ))}
      </section>

      {/* Pipeline Evaluations — collapsed by default */}
      <section className="bg-gradient-to-br from-[#061C14] via-[#0B5D3B] to-[#17855A] text-white rounded-[12px] border border-[#0E3627] shadow-saas-elevated overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 border-b border-white/10">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">
                Evaluation Suite
              </span>
            </div>
            <h2 className="text-lg font-black tracking-tight text-white mt-1">
              Pipeline Evaluations
            </h2>
            <p className="text-xs text-emerald-100/80 mt-0.5 max-w-2xl">
              Explore the full evaluation pipeline: AI analysis, evidence integrity, signals, and reporting.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowDemoEvals(v => !v)}
            className="self-start md:self-auto shrink-0 bg-[#174836] hover:bg-[#1E6047] text-emerald-200 border border-emerald-400/30 text-xs px-4 py-2 rounded-lg font-bold uppercase tracking-wider transition-colors"
          >
            {showDemoEvals ? 'Hide Demo Evaluations' : 'Load Demo Evaluations'}
          </button>
        </div>

        {showDemoEvals ? (
          <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-5">
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
                    <span className="text-xs text-emerald-300 font-medium">Trust Assessment:</span>
                    <TrustGauge score={c.trustScore} size="sm" showLabel={false} />
                  </div>
                  <span className="text-xs font-bold text-emerald-300 group-hover:text-white flex items-center gap-1 group-hover:translate-x-0.5 transition-all">
                    Launch →
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {/* Secondary Metrics Grid */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          ['Stored Runs', metric(metrics, 'total_runs')],
          ['Live Runs', String(liveRuns.length)],
          ['Archived Runs', String(archivedRuns.length)],
          ['Average Confidence', metric(metrics, 'average_confidence')],
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
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Active Evaluations</h2>
            <span className="text-xs text-slate-500 font-semibold">{liveRuns.length} Live</span>
          </div>
          <div className="space-y-3">
            {liveRuns.length === 0 ? (
              <div className="py-6 text-center">
                <div className="text-xs font-semibold text-slate-500">No active evaluations.</div>
                <div className="text-[11px] text-slate-400 mt-1">Upload documents or create a new evaluation in the Runs workspace.</div>
                <Link href="/runs" className="mt-3 inline-block text-xs font-bold text-[#0B5D3B] hover:underline">
                  Go to Runs →
                </Link>
              </div>
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
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Recent Evaluations</h2>
            <span className="text-xs text-slate-500 font-semibold">{latestRuns.length} Loaded</span>
          </div>
          <div className="space-y-3">
            {latestRuns.length === 0 ? (
              <div className="py-6 text-center">
                <div className="text-xs font-semibold text-slate-500">No evaluations available.</div>
                <div className="text-[11px] text-slate-400 mt-1">Upload documents or create a new evaluation.</div>
                <Link href="/runs" className="mt-3 inline-block text-xs font-bold text-[#0B5D3B] hover:underline">
                  Go to Runs →
                </Link>
              </div>
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
