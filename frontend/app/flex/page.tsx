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

function FlexPageInner() {
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
      .then((s) => {
        setStatus(s.status)
        setCurrentRun({ ...currentRun, status: s.status, storedRunId: currentRun.storedRunId || (s.dbId ? String(s.dbId) : currentRun.storedRunId) }, { syncUrl: false })
      })
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
          if (currentRun) {
            setCurrentRun({
              ...currentRun,
              runId,
              status: s.status,
              storedRunId: s.dbId ? String(s.dbId) : currentRun.storedRunId,
            }, { syncUrl: false })
          }
          if (s.status === 'completed' || s.status === 'failed') {
            setPolling(false)
            clearInterval(interval)
          }
        } catch (err) {
          console.error('Polling error', err)
          setError(String(err))
          setPolling(false)
          clearInterval(interval)
        }
      }, 3000)
    }
    return () => clearInterval(interval)
  }, [runId, polling, currentRun, setCurrentRun])

  if (authStatus === 'loading' || !ready) {
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

  async function handleCreateRun(e?: React.FormEvent) {
    e?.preventDefault()
    setError(null)
    try {
      const res = await api.createRun(founder, startup)
      setRunId(res.runId)
      setStatus(res.status)
      setPolling(true)
      setShowCreateForm(false)
      const nextRun = {
        runId: res.runId,
        startupName: startup || 'Unnamed venture',
        founderName: founder || 'Unknown founder',
        status: res.status,
      }
      setCurrentRun(nextRun)
      saveRecentRun({
        runId: res.runId,
        founder: founder || 'Unknown founder',
        startup: startup || 'Unnamed venture',
        status: res.status,
        createdAt: new Date().toISOString(),
        route: 'flex',
      })
    } catch (err) {
      console.error('Create run failed', err)
      setError(String(err))
    }
  }

  const activeRun = currentRun && runId ? currentRun : null

  return (
    <div className="min-h-screen p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px] gap-6">
      <NavigationSidebar
        workspace="Flex"
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
                setStatus(null)
                setShowCreateForm(true)
              }}
            />
            {status === 'failed' ? <div className="text-red-600 text-sm">Run failed — see backend logs</div> : null}
            <ChatShell personaName="IC Analyst" runId={runId} />
          </>
        ) : (
          <div className="p-4 bg-white rounded shadow border border-gray-100">
            <h3 className="text-lg font-semibold mb-2">Start Investment Analysis</h3>
            <p className="text-sm text-gray-600 mb-4">
              Or select an OSTX validation case from the Dashboard to skip manual entry.
            </p>
            <form onSubmit={handleCreateRun} className="flex flex-col gap-3">
              <input value={founder} onChange={(e) => setFounder(e.target.value)} placeholder="Founder name" className="p-2 border rounded" />
              <input value={startup} onChange={(e) => setStartup(e.target.value)} placeholder="Startup name (optional)" className="p-2 border rounded" />
              <div className="flex gap-2">
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Create Run</button>
                <button type="button" onClick={() => { setFounder(''); setStartup('') }} className="px-4 py-2 border rounded">Clear</button>
              </div>
              {error ? <div className="text-red-600 text-sm">{error}</div> : null}
            </form>
          </div>
        )}
      </main>
      <ContextPanel type="flex" runId={runId} status={status} />
    </div>
  )
}

export default function FlexPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-sm text-gray-500">Loading…</div>}>
      <FlexPageInner />
    </Suspense>
  )
}
