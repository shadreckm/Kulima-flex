'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { archiveRun, deleteRun, listLiveRuns, listStoredRuns, reopenRun, type LiveRunRecord, type StoredRunRecord } from '../../lib/api'

function isDemoRun(run: StoredRunRecord): boolean {
  if (run.userId === null || run.userId === undefined) return true
  const idStr = String(run.runId).toLowerCase()
  if (idStr.startsWith('ostx-') || idStr.startsWith('pilot-')) return true
  const demoNames = ['agrinova malawi', 'greenlink foods', 'solarharvest cooperative', 'nilepay logistics', 'farmstack kenya', 'healthbridge lagos']
  if (demoNames.includes(String(run.startupName || '').toLowerCase())) return true
  return false
}

export default function RunsPage() {
  const { status: authStatus } = useSession()
  const [liveRuns, setLiveRuns] = useState<LiveRunRecord[]>([])
  const [storedRuns, setStoredRuns] = useState<StoredRunRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | number | null>(null)
  const [loading, setLoading] = useState(false)

  async function loadRuns() {
    setLoading(true)
    try {
      const [liveRes, storedRes] = await Promise.all([listLiveRuns(50), listStoredRuns(50, true)])
      setLiveRuns(liveRes.runs)
      setStoredRuns(storedRes.runs)
    } finally {
      setLoading(false)
    }
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
      title="Evaluation Run History"
      description="Inspect live evaluations, manage active stored runs, and archive completed analyses."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-[#0B5D3B] animate-pulse" />
          <span className="text-sm font-semibold text-slate-500">Loading runs…</span>
        </div>
      ) : null}

      {/* Live Runs */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-[#DDE6F0]">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Live Evaluations</h2>
          <span className="text-xs text-slate-500 font-semibold">{liveRuns.length} Active</span>
        </div>
        <div className="space-y-3">
          {liveRuns.length === 0 ? (
            <div className="py-6 text-center">
              <div className="text-xs font-semibold text-slate-500">No live evaluations running.</div>
              <div className="text-[11px] text-slate-400 mt-1">Start a new evaluation from the AI Analyst Workspace or Signals workspace.</div>
            </div>
          ) : liveRuns.map(run => (
            <div key={run.runId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 break-all">{run.runId}</div>
                  <div className="text-[11px] text-slate-500 mt-1">Created: {run.createdAt || '—'}</div>
                </div>
                <div className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-white text-slate-700 border border-[#DDE6F0] shrink-0">
                  {run.status}
                </div>
              </div>
              {run.completedAt ? <div className="text-[11px] text-slate-500 mt-1">Completed: {run.completedAt}</div> : null}
              {run.error ? <div className="text-xs text-red-600 font-semibold mt-1">{run.error}</div> : null}
            </div>
          ))}
        </div>
      </section>

      {/* Active & Archived */}
      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-[#DDE6F0]">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Active Evaluations</h2>
            <span className="text-xs text-slate-500 font-semibold">{activeStoredRuns.length}</span>
          </div>
          <div className="space-y-3">
            {activeStoredRuns.length === 0 ? (
              <div className="py-6 text-center">
                <div className="text-xs font-semibold text-slate-500">No active evaluations.</div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Start an evaluation from the{' '}
                  <Link href="/flex" className="text-[#0B5D3B] font-bold hover:underline">AI Analyst Workspace</Link>.
                </div>
              </div>
            ) : activeStoredRuns.map(run => (
              <div key={run.runId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-slate-900 truncate">{run.startupName}</div>
                    <div className="text-[11px] text-slate-500">{run.founderName}</div>
                  </div>
                  <span className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full shrink-0 ${
                    run.recommendation === 'Invest' ? 'bg-[#ECFDF3] text-[#027A48]' :
                    run.recommendation === 'Observe' ? 'bg-[#FFFAEB] text-[#B54708]' :
                    run.recommendation ? 'bg-[#FEF3F2] text-[#B42318]' : 'bg-slate-100 text-slate-600'
                  }`}>{run.recommendation || '—'}</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-1.5">
                  Run #{run.runId} · Score: {run.overallScore ?? '—'} · Trust: {run.trustScore ?? '—'} · Grade: {run.integrityGrade ?? '—'}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {isDemoRun(run) ? (
                    <span className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 font-bold text-[11px] border border-emerald-200">
                      Demo — Read Only
                    </span>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={busyId === run.runId}
                        onClick={() => withBusy(() => archiveRun(run.runId), run.runId)}
                        className="px-3 py-1.5 rounded-lg border border-[#DDE6F0] text-xs font-semibold text-slate-700 hover:bg-[#F5F8FC] disabled:opacity-50 transition"
                        aria-label="Archive this evaluation run"
                      >
                        {busyId === run.runId ? 'Archiving…' : 'Archive'}
                      </button>
                      <button
                        type="button"
                        disabled={busyId === run.runId}
                        onClick={() => withBusy(() => deleteRun(run.runId), run.runId)}
                        className="px-3 py-1.5 rounded-lg border border-red-200 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50 transition"
                        aria-label="Delete this evaluation run"
                      >
                        {busyId === run.runId ? 'Deleting…' : 'Delete'}
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-[#DDE6F0]">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Archived Evaluations</h2>
            <span className="text-xs text-slate-500 font-semibold">{archivedRuns.length}</span>
          </div>
          <div className="space-y-3">
            {archivedRuns.length === 0 ? (
              <div className="py-4 text-center text-xs text-slate-500">No archived evaluations yet.</div>
            ) : archivedRuns.map(run => (
              <div key={run.runId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-slate-900 truncate">{run.startupName}</div>
                    <div className="text-[11px] text-slate-500">{run.founderName}</div>
                  </div>
                  <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-500 shrink-0">Archived</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-1.5">
                  Run #{run.runId} · Archived: {run.archivedAt || '—'} · Score: {run.overallScore ?? '—'} · Trust: {run.trustScore ?? '—'}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {isDemoRun(run) ? (
                    <span className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 font-bold text-[11px] border border-emerald-200">
                      Demo — Read Only
                    </span>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={busyId === run.runId}
                        onClick={() => withBusy(() => reopenRun(run.runId), run.runId)}
                        className="px-3 py-1.5 rounded-lg border border-[#DDE6F0] text-xs font-semibold text-slate-700 hover:bg-[#F5F8FC] disabled:opacity-50 transition"
                        aria-label="Reopen this archived evaluation"
                      >
                        {busyId === run.runId ? 'Reopening…' : 'Reopen'}
                      </button>
                      <button
                        type="button"
                        disabled={busyId === run.runId}
                        onClick={() => withBusy(() => deleteRun(run.runId), run.runId)}
                        className="px-3 py-1.5 rounded-lg border border-red-200 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50 transition"
                        aria-label="Delete this archived evaluation"
                      >
                        {busyId === run.runId ? 'Deleting…' : 'Delete'}
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
