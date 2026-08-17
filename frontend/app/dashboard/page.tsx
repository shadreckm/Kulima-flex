'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getPilotAnalytics, listLiveRuns, listStoredRuns, type LiveRunRecord, type PilotAnalyticsMetrics, type StoredRunRecord } from '../../lib/api'

import { useRouter } from 'next/navigation'
import { OSTX_CASES, saveCurrentRun } from '../../lib/current-run'

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
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}

      {/* OSTX Validation Cases Hero Section */}
      <section className="p-5 bg-gradient-to-r from-emerald-900 to-green-900 text-white rounded-lg shadow-md">
        <div className="flex items-center justify-between gap-4 mb-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-emerald-100">OSTX Validation Cases</h2>
            <p className="text-xs text-emerald-200 mt-1">
              One-click preset workflows. Explore end-to-end Flex, Signals, Evidence, Reports, Analytics, and Feedback.
            </p>
          </div>
          <span className="bg-emerald-800 text-emerald-100 text-xs px-2.5 py-1 rounded font-semibold uppercase tracking-wider">
            Ready to Explore
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          {OSTX_CASES.map((c, idx) => (
            <div
              key={c.liveRunId}
              onClick={() => handleLaunchOstxCase(c)}
              className="bg-white/10 hover:bg-white/20 backdrop-blur-sm border border-emerald-500/30 rounded-lg p-4 cursor-pointer transition flex flex-col justify-between hover:border-emerald-400"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-emerald-300">Case #{idx + 1}</span>
                  <span className={`text-xs px-2 py-0.5 rounded font-bold uppercase ${
                    c.outcome === 'INVEST' ? 'bg-emerald-500 text-white' :
                    c.outcome === 'OBSERVE' ? 'bg-amber-500 text-white' : 'bg-rose-500 text-white'
                  }`}>
                    {c.outcome}
                  </span>
                </div>
                <div className="text-lg font-bold mt-2 text-white">{c.startupName}</div>
                <div className="text-xs text-emerald-200 mt-0.5">{c.founderName}</div>
                <p className="text-xs text-emerald-100/90 mt-2 leading-relaxed">{c.summary}</p>
              </div>
              <div className="mt-4 pt-3 border-t border-emerald-500/30 flex items-center justify-between">
                <span className="text-xs text-emerald-300">Trust Score: <strong className="text-white">{c.trustScore}</strong></span>
                <span className="text-xs font-medium text-emerald-200 underline group-hover:text-white flex items-center gap-1">
                  Launch Workflow →
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Built Today vs Roadmap Architecture Section */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-5 bg-white rounded-lg shadow border border-emerald-100">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block"></span>
            <h2 className="text-base font-bold text-gray-900">Built Today (OSTX Core Engine)</h2>
          </div>
          <div className="space-y-2.5 text-xs text-gray-700">
            <div className="p-2.5 bg-emerald-50/60 rounded border border-emerald-100">
              <span className="font-semibold text-gray-900">Flex Intelligence:</span> IC Analyst assistant, interactive briefing, and decision snapshot.
            </div>
            <div className="p-2.5 bg-emerald-50/60 rounded border border-emerald-100">
              <span className="font-semibold text-gray-900">Signals Intelligence:</span> High-priority risk & opportunity signal detection and priority ranking.
            </div>
            <div className="p-2.5 bg-emerald-50/60 rounded border border-emerald-100">
              <span className="font-semibold text-gray-900">Evidence Workspace:</span> Contradiction detection, source attribution, and verification checklists.
            </div>
            <div className="p-2.5 bg-emerald-50/60 rounded border border-emerald-100">
              <span className="font-semibold text-gray-900">Reports Workspace:</span> PDF/TXT generation for Memos, Full IC Reports, Signals, DD, & One-Pagers.
            </div>
            <div className="p-2.5 bg-emerald-50/60 rounded border border-emerald-100">
              <span className="font-semibold text-gray-900">Analytics Workspace:</span> Read-only cohort statistics, evidence coverage, and trust metrics.
            </div>
          </div>
        </div>

        <div className="p-5 bg-white rounded-lg shadow border border-gray-100">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block"></span>
            <h2 className="text-base font-bold text-gray-900">Roadmap (Future Intelligence Layers)</h2>
          </div>
          <div className="space-y-2.5 text-xs text-gray-600">
            <div className="p-2.5 bg-gray-50 rounded border border-gray-100">
              <span className="font-semibold text-gray-900">MEAL Intelligence:</span> Monitoring, Evaluation, Accountability, and Learning framework for post-investment tracking.
            </div>
            <div className="p-2.5 bg-gray-50 rounded border border-gray-100">
              <span className="font-semibold text-gray-900">Impact Intelligence:</span> Climate resilience scoring, socio-economic impact measurement, and carbon credit auditability.
            </div>
            <div className="p-2.5 bg-gray-50 rounded border border-gray-100">
              <span className="font-semibold text-gray-900">Development Intelligence Layer:</span> Automated alignment with DFI mandates, SDGs, and multi-lateral compliance frameworks.
            </div>
          </div>
        </div>
      </section>

      {/* Metrics Grid */}
      <section className="grid grid-cols-2 xl:grid-cols-4 gap-4">
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
          <div key={label} className="p-4 bg-white rounded shadow border border-gray-100">
            <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
            <div className="mt-2 text-2xl font-semibold text-gray-900">{value}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-4 bg-white rounded shadow border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Live Runs</h2>
          <div className="mt-3 space-y-3">
            {liveRuns.length === 0 ? (
              <div className="text-sm text-gray-500">No live runs recorded yet.</div>
            ) : liveRuns.map(run => (
              <div key={run.runId} className="border rounded p-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="text-sm font-medium text-gray-900 break-all">{run.runId}</div>
                  <div className="text-xs text-gray-600">{run.status}</div>
                </div>
                <div className="text-xs text-gray-500 mt-1">Created: {run.createdAt || '—'}{run.completedAt ? ` · Completed: ${run.completedAt}` : ''}</div>
                {run.error ? <div className="text-xs text-red-600 mt-1">{run.error}</div> : null}
              </div>
            ))}
          </div>
        </div>

        <div className="p-4 bg-white rounded shadow border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Recent Stored Runs</h2>
          <div className="mt-3 space-y-3">
            {latestRuns.length === 0 ? (
              <div className="text-sm text-gray-500">No stored runs available yet.</div>
            ) : latestRuns.map(run => (
              <div key={run.runId} className="border rounded p-3">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{run.startupName}</div>
                    <div className="text-xs text-gray-500">{run.founderName}</div>
                  </div>
                  <div className="text-xs text-gray-600">{run.archivedAt ? 'Archived' : 'Active'}</div>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Score {run.overallScore ?? '—'} · Trust {run.trustScore ?? '—'} · {run.integrityGrade ?? '—'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
