'use client'

import React, { useEffect, useState, Suspense } from 'react'
import { useSession, signIn } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { listStoredRuns, submitRunFeedback, type StoredRunRecord } from '../../lib/api'
import { loadCurrentRun } from '../../lib/current-run'
import TrustGauge from '../../components/TrustGauge/TrustGauge'

function FeedbackPageInner() {
  const { status: authStatus } = useSession()
  const searchParams = useSearchParams()
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [userName, setUserName] = useState('')
  const [rating, setRating] = useState(4)
  const [comment, setComment] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function loadRuns() {
      const res = await listStoredRuns(50, true)
      if (cancelled) return
      setRuns(res.runs)
      const paramRun = searchParams.get('run')
      const stored = loadCurrentRun()
      const nextSelected = paramRun || stored?.runId || String(res.runs[0]?.runId || '')
      setSelectedRunId(nextSelected)
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
        <button
          onClick={() => signIn()}
          className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm"
        >
          Sign in
        </button>
      </div>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setMessage(null)
    try {
      await submitRunFeedback(selectedRunId, {
        userName,
        rating,
        comment,
      })
      setMessage('Feedback recorded successfully for the pilot review loop.')
      setComment('')
      setRating(4)
    } catch (err) {
      setError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const selectedRun = runs.find(run => String(run.runId) === String(selectedRunId))

  return (
    <PilotWorkspaceShell
      workspace="Feedback"
      title="Pilot Feedback & Validation"
      description="Store review feedback against a completed run for the pilot evaluation loop."
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
      startupName={selectedRun?.startupName}
      recommendation={selectedRun?.recommendation}
      trustScore={selectedRun?.trustScore}
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="p-4 bg-emerald-50 text-emerald-800 rounded-[12px] border border-emerald-200 text-sm font-bold flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
          <span>{message}</span>
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas space-y-5">
            <div className="pb-3 border-b border-[#DDE6F0]">
              <h2 className="text-base font-extrabold text-slate-900">Submit Evaluation Feedback</h2>
              <p className="text-xs text-slate-500 mt-0.5">Captures decision committee input for institutional pilot tracking.</p>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Target Run</label>
              <select
                className="mt-1.5 w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 font-medium focus:outline-none focus:border-[#0B5D3B]"
                value={selectedRunId}
                onChange={(e) => setSelectedRunId(e.target.value)}
              >
                <option value="">Choose a stored run…</option>
                {runs.map(run => (
                  <option key={run.runId} value={run.runId}>
                    #{run.runId} · {run.startupName} · {run.founderName} (Trust: {run.trustScore ?? '—'})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Reviewer Name / Title</label>
              <input
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                className="mt-1.5 w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
                placeholder="e.g. SPARC Reviewer / OSTX Judge"
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Evaluation Confidence Rating</label>
                <span className="px-2 py-0.5 rounded bg-[#EAF3FF] text-[#004085] text-xs font-extrabold border border-[#D6E8FF]">
                  {rating} / 5 Stars
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={5}
                value={rating}
                onChange={(e) => setRating(Number(e.target.value))}
                className="mt-2 w-full accent-[#0B5D3B] cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">Reviewer Comments & Rationale</label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="mt-1.5 w-full p-3 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 min-h-32 focus:outline-none focus:border-[#0B5D3B]"
                placeholder="Assess evidence integrity, confidence score accuracy, risk signals, or thesis alignment..."
              />
            </div>

            <button
              type="submit"
              disabled={submitting || !selectedRunId}
              className="w-full sm:w-auto px-6 py-2.5 rounded-lg bg-[#0B5D3B] text-white text-xs font-extrabold uppercase tracking-wider hover:bg-[#08482E] transition disabled:opacity-50 shadow-sm"
            >
              {submitting ? 'Recording Feedback…' : 'Submit Review Feedback'}
            </button>
          </form>
        </div>

        <div className="space-y-6">
          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700 mb-3 pb-2 border-b border-[#DDE6F0]">
              Run Trust Overview
            </h3>
            {selectedRun ? (
              <div className="space-y-4">
                <TrustGauge score={selectedRun.trustScore} size="lg" showLabel={true} />
                <div className="pt-3 border-t border-[#DDE6F0] text-xs text-slate-600 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Startup:</span>
                    <span className="font-bold text-slate-900">{selectedRun.startupName}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Recommendation:</span>
                    <span className="font-bold text-slate-900">{selectedRun.recommendation || '—'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Integrity Grade:</span>
                    <span className="font-bold text-slate-900">{selectedRun.integrityGrade || '—'}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic py-4">
                Select a run on the left to view its trust score and verification telemetry.
              </div>
            )}
          </div>
        </div>
      </div>
    </PilotWorkspaceShell>
  )
}

export default function FeedbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <FeedbackPageInner />
    </Suspense>
  )
}
