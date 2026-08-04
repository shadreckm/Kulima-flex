'use client'

import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { listStoredRuns, reportDownloadHref, type StoredRunRecord } from '../../lib/api'

export default function ReportsPage() {
  const { status: authStatus } = useSession()
  const searchParams = useSearchParams()
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function loadRuns() {
      const res = await listStoredRuns(50, true)
      if (cancelled) return
      setRuns(res.runs)
      setSelectedRunId(searchParams.get('run') || String(res.runs[0]?.runId || ''))
    }
    if (authStatus === 'authenticated') {
      loadRuns().catch(err => setError(String(err)))
    }
    return () => { cancelled = true }
  }, [authStatus, searchParams])

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

  const selectedRun = runs.find(run => String(run.runId) === String(selectedRunId))

  const downloads = [
    { label: 'Investment Memo', kind: 'memo' as const },
    { label: 'Full IC Report', kind: 'report' as const },
    { label: 'Signals Report', kind: 'signals' as const },
    { label: 'Due Diligence Summary', kind: 'due-diligence' as const },
    { label: 'Executive One Pager', kind: 'one-pager' as const },
  ]

  return (
    <PilotWorkspaceShell
      workspace="Reports"
      title="Reports Workspace"
      description="Download the already-implemented memo, full report, signals report, due diligence summary, and executive one pager for a stored run."
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}

      <section className="p-4 bg-white rounded shadow border border-gray-100">
        <label className="block text-sm font-medium text-gray-700">Select run</label>
        <select className="mt-2 w-full p-2 border rounded" value={selectedRunId} onChange={(e) => setSelectedRunId(e.target.value)}>
          <option value="">Choose a stored run…</option>
          {runs.map(run => (
            <option key={run.runId} value={run.runId}>
              #{run.runId} · {run.startupName} · {run.founderName}
            </option>
          ))}
        </select>
      </section>

      {selectedRun ? (
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {downloads.map(report => (
            <div key={report.kind} className="p-4 bg-white rounded shadow border border-gray-100">
              <div className="text-lg font-semibold text-gray-900">{report.label}</div>
              <div className="text-sm text-gray-600 mt-1">PDF and text downloads are generated from the stored brief.</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <a className="px-3 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 text-sm" href={reportDownloadHref(selectedRun.runId, report.kind, 'pdf')}>
                  Download PDF
                </a>
                <a className="px-3 py-2 rounded border text-sm hover:bg-gray-50" href={reportDownloadHref(selectedRun.runId, report.kind, 'txt')}>
                  Download TXT
                </a>
              </div>
            </div>
          ))}
        </section>
      ) : (
        <div className="p-4 text-sm text-gray-500">Choose a stored run to unlock downloads.</div>
      )}
    </PilotWorkspaceShell>
  )
}
