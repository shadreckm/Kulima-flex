'use client'

import React, { useEffect, useState } from 'react'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getPilotAnalytics, listStoredRuns, type PilotAnalyticsMetrics, type StoredRunRecord } from '../../lib/api'

function metric(metrics: PilotAnalyticsMetrics | null, key: string): string {
  if (!metrics) return '—'
  const value = metrics[key]
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(1)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return value
  return '—'
}

export default function AnalyticsPage() {
  const { status: authStatus } = useSession()
  const [metrics, setMetrics] = useState<PilotAnalyticsMetrics | null>(null)
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const [analyticsRes, runsRes] = await Promise.all([getPilotAnalytics(), listStoredRuns(100, true)])
      if (cancelled) return
      setMetrics(analyticsRes)
      setRuns(runsRes.runs)
    }
    if (authStatus === 'authenticated') {
      load().catch(err => setError(String(err)))
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

  const activeRuns = runs.filter(run => !run.archivedAt)
  const archivedRuns = runs.filter(run => run.archivedAt)
  const topRuns = [...runs].sort((a, b) => Number(b.overallScore || 0) - Number(a.overallScore || 0)).slice(0, 5)

  return (
    <PilotWorkspaceShell
      workspace="Analytics"
      title="Portfolio Analytics"
      description="Portfolio analytics derived from completed evaluation runs."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      <section className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          ['Total Evaluations', metric(metrics, 'total_runs')],
          ['Invest', metric(metrics, 'invest_count')],
          ['Co-Invest', metric(metrics, 'co_invest_count')],
          ['Observe', metric(metrics, 'observe_count')],
          ['Pass', metric(metrics, 'pass_count')],
          ['Average Score', metric(metrics, 'average_score')],
          ['Average Confidence', metric(metrics, 'average_confidence')],
          ['Average Trust', metric(metrics, 'average_trust')],
          ['Average Risk', metric(metrics, 'average_risk')],
          ['Evidence Coverage', `${metric(metrics, 'evidence_coverage')}%`],
          ['Verification Coverage', `${metric(metrics, 'signal_coverage')}%`],
          ['Avg Unsupported Claims', metric(metrics, 'average_unsupported_claims')],
        ].map(([label, value]) => (
          <div key={label} className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{label}</div>
            <div className="mt-1.5 text-2xl font-black text-slate-900 tracking-tight">{value}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">Portfolio Mix</h2>
          <div className="grid grid-cols-2 gap-3 text-sm text-slate-700">
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Active</div>
              <div className="text-xl font-black text-slate-900 mt-1">{activeRuns.length}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Archived</div>
              <div className="text-xl font-black text-slate-900 mt-1">{archivedRuns.length}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">IC-Ready (Invest)</div>
              <div className="text-xl font-black text-slate-900 mt-1">{metric(metrics, 'invest_count')}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Co-Invest</div>
              <div className="text-xl font-black text-slate-900 mt-1">{metric(metrics, 'co_invest_count')}</div>
            </div>
          </div>
        </div>

        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">Top Evaluations by Score</h2>
          <div className="space-y-3">
            {topRuns.length === 0 ? (
              <div className="text-xs text-slate-500 py-3">No evaluations available.</div>
            ) : topRuns.map(run => (
              <div key={run.runId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
                <div className="text-xs font-bold text-slate-900">{run.startupName}</div>
                <div className="text-[11px] text-slate-500">{run.founderName}</div>
                <div className="text-[10px] text-slate-400 mt-1">Score {run.overallScore ?? '—'} · Trust {run.trustScore ?? '—'} · Grade {run.integrityGrade ?? '—'}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
