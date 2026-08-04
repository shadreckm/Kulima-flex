'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getPilotAnalytics, listLiveRuns, listStoredRuns, type LiveRunRecord, type PilotAnalyticsMetrics, type StoredRunRecord } from '../../lib/api'

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

  const quickLinks = [
    { label: 'Flex', href: '/flex', note: 'Create and inspect investment runs' },
    { label: 'Signals', href: '/signals', note: 'Review signals from completed runs' },
    { label: 'Evidence', href: '/evidence', note: 'Open stored evidence and sources' },
    { label: 'Reports', href: '/reports', note: 'Download IC-ready reports' },
    { label: 'Analytics', href: '/analytics', note: 'View pilot metrics and cohort trends' },
    { label: 'Feedback', href: '/feedback', note: 'Capture pilot review feedback' },
    { label: 'Runs', href: '/runs', note: 'Inspect active and archived runs' },
    { label: 'Settings', href: '/settings', note: 'Session and workspace settings' },
  ]

  return (
    <PilotWorkspaceShell
      workspace="Dashboard"
      title="Pilot Dashboard"
      description="Surface the implemented pilot workspaces, live runs, stored evidence, reports, and analytics."
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}

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

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {quickLinks.map(link => (
          <Link key={link.href} href={link.href} className="p-4 bg-white rounded shadow border border-gray-100 hover:border-blue-300 hover:shadow-md transition">
            <div className="text-lg font-semibold text-gray-900">{link.label}</div>
            <div className="text-sm text-gray-600 mt-1">{link.note}</div>
          </Link>
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

      <section className="p-4 bg-white rounded shadow border border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900">Run Health</h2>
        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-700">
          <div>Active stored runs: <span className="font-semibold">{activeStoredRuns.length}</span></div>
          <div>Archived stored runs: <span className="font-semibold">{archivedRuns.length}</span></div>
          <div>Pass count: <span className="font-semibold">{metric(metrics, 'pass_count')}</span></div>
          <div>Invest count: <span className="font-semibold">{metric(metrics, 'invest_count')}</span></div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
