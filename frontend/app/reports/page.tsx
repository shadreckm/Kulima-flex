'use client'

import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { listStoredRuns, reportDownloadHref, type StoredRunRecord } from '../../lib/api'
import { loadCurrentRun } from '../../lib/current-run'
import Link from 'next/link'
import KulimaLogo from '../../components/KulimaLogo/KulimaLogo'

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
      const fromQuery = searchParams.get('run')
      const stored = loadCurrentRun()
      setSelectedRunId(fromQuery || stored?.runId || String(res.runs[0]?.runId || ''))
    }
    if (authStatus === 'authenticated') {
      loadRuns().catch(err => setError(String(err)))
    }
    return () => { cancelled = true }
  }, [authStatus, searchParams])

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
        <button onClick={() => signIn()} className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm">
          Sign in
        </button>
      </div>
    )
  }

  const selectedRun = runs.find(run => String(run.runId) === String(selectedRunId))

  const downloads = [
    { label: 'Investment Memo', kind: 'memo' as const, description: 'Executive investment recommendation and rationale.' },
    { label: 'Full IC Report', kind: 'report' as const, description: 'Complete intelligence committee analysis package.' },
    { label: 'Signals Report', kind: 'signals' as const, description: 'Detected risk and opportunity signals.' },
    { label: 'Due Diligence Summary', kind: 'due-diligence' as const, description: 'Evidence integrity and verification audit.' },
    { label: 'Executive One Pager', kind: 'one-pager' as const, description: 'Single-page overview for board or donor review.' },
  ]

  return (
    <PilotWorkspaceShell
      workspace="Reports"
      title="Reports Archive"
      description="Access historical export archive. Download memos, decision reports, signals, due diligence summaries, and executive one-pagers."
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      {/* Branded report header */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <KulimaLogo variant="report" />
          <div className="w-px h-10 bg-[#DDE6F0] flex-shrink-0" />
          <div>
            <div className="text-xs font-extrabold uppercase tracking-wider text-slate-500">Kulima OS</div>
            <div className="text-sm font-black text-slate-900">Decision Intelligence Reports</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Evidence-backed exports for investment committees, donors, and program evaluators</div>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-2 bg-[#ECFDF3] border border-[#A6F4C5] px-3 py-1.5 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
          <span className="text-[11px] font-bold text-[#027A48] uppercase tracking-wider">Export Ready</span>
        </div>
      </section>

      {runs.length === 0 ? (
        <div className="p-8 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-center">
          <div className="text-sm font-bold text-slate-700">No evaluations available.</div>
          <div className="text-xs text-slate-500 mt-1">Upload documents or create a new evaluation in the Runs workspace.</div>
          <Link href="/runs" className="mt-4 inline-block px-4 py-2 rounded-lg bg-[#0B5D3B] text-white text-xs font-bold hover:bg-[#08482E] transition">
            Go to Runs
          </Link>
        </div>
      ) : (
        <>
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">Select Evaluation</label>
            <select
              className="w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 font-medium focus:outline-none focus:border-[#0B5D3B]"
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
            >
              <option value="">Select Evaluation Target…</option>
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
                <div key={report.kind} className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                  <div className="text-sm font-extrabold text-slate-900">{report.label}</div>
                  <div className="text-xs text-slate-500 mt-1">{report.description}</div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <a
                      className="px-4 py-2 rounded-lg bg-[#0B5D3B] text-white hover:bg-[#08482E] text-xs font-bold transition shadow-sm"
                      href={reportDownloadHref(selectedRun.runId, report.kind, 'pdf')}
                    >
                      Download PDF
                    </a>
                    <a
                      className="px-4 py-2 rounded-lg border border-[#DDE6F0] text-xs font-semibold text-slate-700 hover:bg-[#F5F8FC] transition"
                      href={reportDownloadHref(selectedRun.runId, report.kind, 'txt')}
                    >
                      Download TXT
                    </a>
                  </div>
                </div>
              ))}
            </section>
          ) : (
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-xs text-slate-500">
              Select an evaluation target above to unlock report downloads.
            </div>
          )}
        </>
      )}
    </PilotWorkspaceShell>
  )
}
