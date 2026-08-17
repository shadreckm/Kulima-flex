'use client'

import React, { useEffect, useState, Suspense } from 'react'
import { useSession, signIn } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { listStoredRuns, submitRunFeedback, type StoredRunRecord } from '../../lib/api'

import { loadCurrentRun } from '../../lib/current-run'

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
      setMessage('Feedback captured for the pilot review loop.')
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
      title="Pilot Feedback"
      description="Store review feedback against a completed run for the pilot loop."
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}
      {message ? <div className="p-4 bg-green-50 text-green-700 rounded border border-green-200">{message}</div> : null}

      <form onSubmit={handleSubmit} className="p-4 bg-white rounded shadow border border-gray-100 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Select run</label>
          <select className="mt-2 w-full p-2 border rounded" value={selectedRunId} onChange={(e) => setSelectedRunId(e.target.value)}>
            <option value="">Choose a stored run…</option>
            {runs.map(run => (
              <option key={run.runId} value={run.runId}>
                #{run.runId} · {run.startupName} · {run.founderName}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">User</label>
          <input value={userName} onChange={(e) => setUserName(e.target.value)} className="mt-2 w-full p-2 border rounded" placeholder="Pilot user name" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Rating</label>
          <input type="range" min={1} max={5} value={rating} onChange={(e) => setRating(Number(e.target.value))} className="mt-2 w-full" />
          <div className="text-xs text-gray-500 mt-1">{rating} / 5</div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Comment</label>
          <textarea value={comment} onChange={(e) => setComment(e.target.value)} className="mt-2 w-full p-2 border rounded min-h-32" placeholder="What worked, what was missing, what should improve next?" />
        </div>

        <button
          type="submit"
          disabled={submitting || !selectedRunId}
          className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? 'Submitting…' : 'Submit Feedback'}
        </button>
      </form>
    </PilotWorkspaceShell>
  )
}

export default function FeedbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-sm text-gray-500">Loading…</div>}>
      <FeedbackPageInner />
    </Suspense>
  )
}
