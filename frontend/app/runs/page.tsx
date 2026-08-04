'use client'

import React, { useEffect, useState } from 'react'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { archiveRun, deleteRun, listLiveRuns, listStoredRuns, reopenRun, type LiveRunRecord, type StoredRunRecord } from '../../lib/api'

export default function RunsPage() {
  const { status: authStatus } = useSession()
  const [liveRuns, setLiveRuns] = useState<LiveRunRecord[]>([])
  const [storedRuns, setStoredRuns] = useState<StoredRunRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | number | null>(null)

  async function loadRuns() {
    const [liveRes, storedRes] = await Promise.all([listLiveRuns(50), listStoredRuns(50, true)])
    setLiveRuns(liveRes.runs)
    setStoredRuns(storedRes.runs)
  }

  useEffect(() => {
    let cancelled = false
    if (authStatus !== 'authenticated') return
    loadRuns().catch(err => {
      if (!cancelled) setError(String(err))
    })
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

  async function withBusy(action: () => Promise<any>, id: string | number) {
    setBusyId(id)
    setError(null)
    try {
      await action()
      await loadRuns()
    } catch (err) {
      setError(String(err))
    } finally {
      setBusyId(null)
    }
  }

  const archivedRuns = storedRuns.filter(run => run.archivedAt)
  const activeStoredRuns = storedRuns.filter(run => !run.archivedAt)

  return (
    <PilotWorkspaceShell
      workspace="Runs"
      title="Run History"
      description="Inspect live runs, active stored runs, archived runs, and manage run lifecycle actions."
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}

      <section className="p-4 bg-white rounded shadow border border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900">Live Runs</h2>
        <div className="mt-3 space-y-3">
          {liveRuns.length === 0 ? (
            <div className="text-sm text-gray-500">No live runs recorded yet.</div>
          ) : liveRuns.map(run => (
            <div key={run.runId} className="border rounded p-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-gray-900 break-all">{run.runId}</div>
                  <div className="text-xs text-gray-500 mt-1">Created: {run.createdAt || '—'}</div>
                </div>
                <div className="text-xs text-gray-600">{run.status}</div>
              </div>
              {run.completedAt ? <div className="text-xs text-gray-500 mt-1">Completed: {run.completedAt}</div> : null}
              {run.error ? <div className="text-xs text-red-600 mt-1">{run.error}</div> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-4 bg-white rounded shadow border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Active Stored Runs</h2>
          <div className="mt-3 space-y-3">
            {activeStoredRuns.length === 0 ? (
              <div className="text-sm text-gray-500">No active stored runs available.</div>
            ) : activeStoredRuns.map(run => (
              <div key={run.runId} className="border rounded p-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{run.startupName}</div>
                    <div className="text-xs text-gray-500">{run.founderName}</div>
                  </div>
                  <div className="text-xs text-gray-600">{run.recommendation || '—'}</div>
                </div>
                <div className="text-xs text-gray-500 mt-1">Run #{run.runId} · Created {run.createdAt}</div>
                <div className="text-xs text-gray-500 mt-1">Score {run.overallScore ?? '—'} · Trust {run.trustScore ?? '—'} · Reliability {run.integrityGrade ?? '—'}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busyId === run.runId}
                    onClick={() => withBusy(() => archiveRun(run.runId), run.runId)}
                    className="px-3 py-1.5 rounded border text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    Archive
                  </button>
                  <button
                    type="button"
                    disabled={busyId === run.runId}
                    onClick={() => withBusy(() => deleteRun(run.runId), run.runId)}
                    className="px-3 py-1.5 rounded border text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="p-4 bg-white rounded shadow border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Archived Runs</h2>
          <div className="mt-3 space-y-3">
            {archivedRuns.length === 0 ? (
              <div className="text-sm text-gray-500">No archived runs yet.</div>
            ) : archivedRuns.map(run => (
              <div key={run.runId} className="border rounded p-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{run.startupName}</div>
                    <div className="text-xs text-gray-500">{run.founderName}</div>
                  </div>
                  <div className="text-xs text-gray-600">Archived</div>
                </div>
                <div className="text-xs text-gray-500 mt-1">Run #{run.runId} · Archived {run.archivedAt || '—'}</div>
                <div className="text-xs text-gray-500 mt-1">Score {run.overallScore ?? '—'} · Trust {run.trustScore ?? '—'} · Reliability {run.integrityGrade ?? '—'}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busyId === run.runId}
                    onClick={() => withBusy(() => reopenRun(run.runId), run.runId)}
                    className="px-3 py-1.5 rounded border text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    Reopen
                  </button>
                  <button
                    type="button"
                    disabled={busyId === run.runId}
                    onClick={() => withBusy(() => deleteRun(run.runId), run.runId)}
                    className="px-3 py-1.5 rounded border text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
