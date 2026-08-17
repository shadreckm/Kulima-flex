'use client'

import React, { useEffect, useState, Suspense } from 'react'
import { useSession, signIn } from 'next-auth/react'
import ChatShell from '../../components/ChatShell/ChatShell'
import ContextPanel from '../../components/ContextPanel/ContextPanel'
import NavigationSidebar from '../../components/NavigationSidebar/NavigationSidebar'
import CurrentRunBanner from '../../components/CurrentRunBanner/CurrentRunBanner'
import * as api from '../../lib/api'
import { saveRecentRun, updateRecentRunStatus } from '../../lib/run-history'
import { useCurrentRun } from '../../hooks/useCurrentRun'

function SignalsPageInner() {
  const { status: authStatus } = useSession()
  const { currentRun, ready, setCurrentRun, clearRun, hasCurrentRun } = useCurrentRun()

  const [founder, setFounder] = useState('')
  const [startup, setStartup] = useState('')
  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)

  useEffect(() => {
    if (!ready || !currentRun?.runId) return
    setRunId(currentRun.runId)
    setStatus(currentRun.status || 'completed')
    api.getRunStatus(currentRun.runId)
      .then((s) => setStatus(s.status))
      .catch(() => setStatus(currentRun.status || 'completed'))
  }, [ready, currentRun?.runId])

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined
    if (runId && polling) {
      interval = setInterval(async () => {
        try {
          const s = await api.getRunStatus(runId)
          setStatus(s.status)
          updateRecentRunStatus(runId, s.status)
          if (s.status === 'completed' || s.status === 'failed') {
            setPolling(false)
            clearInterval(interval)
          }
        } catch (err) {
          setError(String(err))
          setPolling(false)
          clearInterval(interval)
        }
      }, 3000)
    }
    return () => clearInterval(interval)
  }, [runId, polling])

  if (authStatus === 'loading' || !ready) {
    return <div className="min-h-screen flex items-center justify-center text-sm text-gray-600">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-semibold">Sign in to use Kulima OS</div>
        <button onClick={() => signIn()} className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">Sign in</button>
      </div>
    )
  }

  async function handleCreateRun(e?: React.FormEvent) {
    e?.preventDefault()
    setError(null)
    try {
      const res = await api.createRun(founder, startup)
      setRunId(res.runId)
      setStatus(res.status)
      setPolling(true)
      setShowCreateForm(false)
      setCurrentRun({
        runId: res.runId,
        startupName: startup || 'Unnamed venture',
        founderName: founder || 'Unknown founder',
        status: res.status,
      })
      saveRecentRun({
        runId: res.runId,
        founder: founder || 'Unknown founder',
        startup: startup || 'Unnamed venture',
        status: res.status,
        createdAt: new Date().toISOString(),
        route: 'signals',
      })
    } catch (err) {
      setError(String(err))
    }
  }

  const activeRun = currentRun && runId ? currentRun : null

  return (
    <div className="min-h-screen p-6 grid grid-cols-[240px_1fr_360px] gap-6">
      <NavigationSidebar
        workspace="Signals"
        runId={runId}
        status={status}
        startupName={activeRun?.startupName}
        recommendation={activeRun?.recommendation}
        trustScore={activeRun?.trustScore}
      />
      <main className="flex flex-col gap-4">
        {hasCurrentRun && activeRun && !showCreateForm ? (
          <>
            <CurrentRunBanner
              run={activeRun}
              onClear={() => {
                clearRun()
                setRunId(null)
                setShowCreateForm(true)
              }}
            />
            <ChatShell personaName="Signals Analyst" runId={runId} />
          </>
        ) : (
          <div className="p-4 bg-white rounded shadow border border-gray-100">
            <h3 className="text-lg font-semibold mb-2">Signals Intelligence</h3>
            <p className="text-sm text-gray-600 mb-4">Select a run from the Dashboard or create a new analysis.</p>
            <form onSubmit={handleCreateRun} className="flex flex-col gap-3">
              <input value={founder} onChange={(e) => setFounder(e.target.value)} placeholder="Founder name" className="p-2 border rounded" />
              <input value={startup} onChange={(e) => setStartup(e.target.value)} placeholder="Startup name (optional)" className="p-2 border rounded" />
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded w-fit">Create Run</button>
              {error ? <div className="text-red-600 text-sm">{error}</div> : null}
            </form>
          </div>
        )}
      </main>
      <ContextPanel type="signals" runId={runId} status={status} />
    </div>
  )
}

export default function SignalsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-sm text-gray-500">Loading…</div>}>
      <SignalsPageInner />
    </Suspense>
  )
}
