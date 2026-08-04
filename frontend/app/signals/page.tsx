'use client'

import React, { useEffect, useState } from 'react'
import { useSession, signIn } from 'next-auth/react'
import ChatShell from '../../components/ChatShell/ChatShell'
import ContextPanel from '../../components/ContextPanel/ContextPanel'
import NavigationSidebar from '../../components/NavigationSidebar/NavigationSidebar'
import * as api from '../../lib/api'
import { saveRecentRun, updateRecentRunStatus } from '../../lib/run-history'

export default function SignalsPage() {
  const { status: authStatus } = useSession()

  const [founder, setFounder] = useState('')
  const [startup, setStartup] = useState('')
  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)

  useEffect(() => {
    let interval: any
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
          console.error('Polling error', err)
          setError(String(err))
          setPolling(false)
          clearInterval(interval)
        }
      }, 3000)
    }
    return () => clearInterval(interval)
  }, [runId, polling])

  if (authStatus === 'loading') {
    return <div className="min-h-screen flex items-center justify-center text-sm text-gray-600">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-semibold">Sign in to use Kulima OS</div>
        <button
          onClick={() => signIn()}
          className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700"
        >
          Sign in
        </button>
      </div>
    )
  }

  async function handleCreateRun(e?: React.FormEvent) {
    e && e.preventDefault()
    setError(null)
    try {
      const res = await api.createRun(founder, startup)
      setRunId(res.runId)
      setStatus(res.status)
      setPolling(true)
      saveRecentRun({
        runId: res.runId,
        founder: founder || 'Unknown founder',
        startup: startup || 'Unnamed venture',
        status: res.status,
        createdAt: new Date().toISOString(),
        route: 'signals',
      })
    } catch (err) {
      console.error('Create run failed', err)
      setError(String(err))
    }
  }

  return (
    <div className="min-h-screen p-6 grid grid-cols-[240px_1fr_360px] gap-6">
      <NavigationSidebar workspace="Signals" runId={runId} status={status} />
      <main className="flex flex-col">
        {!runId ? (
          <div className="p-4 bg-white rounded shadow">
            <h3 className="text-lg font-semibold mb-2">Start Investment Analysis (Signals)</h3>
            <form onSubmit={handleCreateRun} className="flex flex-col gap-3">
              <input value={founder} onChange={(e) => setFounder(e.target.value)} placeholder="Founder name" className="p-2 border rounded" />
              <input value={startup} onChange={(e) => setStartup(e.target.value)} placeholder="Startup name (optional)" className="p-2 border rounded" />
              <div className="flex gap-2">
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Create Run</button>
                <button type="button" onClick={() => { setFounder(''); setStartup('') }} className="px-4 py-2 border rounded">Clear</button>
              </div>
              {error && <div className="text-red-600">{error}</div>}
            </form>
          </div>
        ) : (
          <div>
            <div id="run-status" className="mb-2">Run: <strong>{runId}</strong> — status: <em>{status}</em></div>
            {status === 'failed' && <div className="text-red-600">Run failed — see backend logs</div>}
            <ChatShell personaName="Signals Analyst" runId={runId} />
          </div>
        )}
      </main>
      <ContextPanel type="signals" runId={runId} status={status} />
    </div>
  )
}
