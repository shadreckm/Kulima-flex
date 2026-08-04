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
    return <div className="min-h-screen flex items-center justify-center text-sm text-gray-600">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-semibold">Sign in to use Kulima OS</div>
        <button onClick={() => signIn()} className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">
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
      title="Analytics Workspace"
      description="Read-only pilot analytics derived from stored runs only. No mock data and no new model calls."
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}

      <section className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          ['Total Runs', metric(metrics, 'total_runs')],
          ['Invest', metric(metrics, 'invest_count')],
          ['Co-Invest', metric(metrics, 'co_invest_count')],
          ['Observe', metric(metrics, 'observe_count')],
          ['Pass', metric(metrics, 'pass_count')],
          ['Average Score', metric(metrics, 'average_score')],
          ['Average Confidence', metric(metrics, 'average_confidence')],
          ['Average Trust', metric(metrics, 'average_trust')],
          ['Average Risk', metric(metrics, 'average_risk')],
          ['Evidence Coverage', `${metric(metrics, 'evidence_coverage')}%`],
          ['Signal Coverage', `${metric(metrics, 'signal_coverage')}%`],
          ['Avg Unsupported Claims', metric(metrics, 'average_unsupported_claims')],
        ].map(([label, value]) => (
          <div key={label} className="p-4 bg-white rounded shadow border border-gray-100">
            <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
            <div className="mt-2 text-2xl font-semibold text-gray-900">{value}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-4 bg-white rounded shadow border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Run Mix</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-gray-700">
            <div>Active runs: <span className="font-semibold">{activeRuns.length}</span></div>
            <div>Archived runs: <span className="font-semibold">{archivedRuns.length}</span></div>
            <div>IC-ready investments: <span className="font-semibold">{metric(metrics, 'invest_count')}</span></div>
            <div>IC-ready co-invests: <span className="font-semibold">{metric(metrics, 'co_invest_count')}</span></div>
          </div>
        </div>

        <div className="p-4 bg-white rounded shadow border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Top Runs by Score</h2>
          <div className="mt-3 space-y-3">
            {topRuns.length === 0 ? (
              <div className="text-sm text-gray-500">No stored runs available.</div>
            ) : topRuns.map(run => (
              <div key={run.runId} className="border rounded p-3 text-sm text-gray-700">
                <div className="font-medium text-gray-900">{run.startupName}</div>
                <div className="text-xs text-gray-500">{run.founderName}</div>
                <div className="text-xs text-gray-600 mt-1">Score {run.overallScore ?? '—'} · Trust {run.trustScore ?? '—'} · Reliability {run.integrityGrade ?? '—'}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
