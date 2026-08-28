'use client'

import React, { useEffect, useState, Suspense } from 'react'
import { useSession, signIn } from 'next-auth/react'
import ChatShell from '../../components/ChatShell/ChatShell'
import ContextPanel from '../../components/ContextPanel/ContextPanel'
import NavigationSidebar from '../../components/NavigationSidebar/NavigationSidebar'
import CurrentRunBanner from '../../components/CurrentRunBanner/CurrentRunBanner'
import EntityIntakeForm from '../../components/EntityIntakeForm/EntityIntakeForm'
import * as api from '../../lib/api'
import { entityToRunParams } from '../../lib/entity-types'
import { saveRecentRun, updateRecentRunStatus } from '../../lib/run-history'
import { useCurrentRun } from '../../hooks/useCurrentRun'

function SignalsPageInner() {
  const { status: authStatus } = useSession()
  const { currentRun, ready, setCurrentRun, clearRun, hasCurrentRun } = useCurrentRun()

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

  async function handleCreateRun(params: ReturnType<typeof entityToRunParams>) {
    setError(null)
    const res = await api.createRun(params.founder, params.startup, {
      entityType: params.entityType,
      entityMeta: params.entityMeta,
    })
    setRunId(res.runId)
    setStatus(res.status)
    setPolling(true)
    setShowCreateForm(false)
    setCurrentRun({
      runId: res.runId,
      startupName: params.startup || params.founder,
      founderName: params.founder,
      entityType: params.entityType,
      programName: params.entityMeta?.programName || '',
      status: res.status,
    })
    saveRecentRun({
      runId: res.runId,
      founder: params.founder,
      startup: params.startup || params.founder,
      status: res.status,
      createdAt: new Date().toISOString(),
      route: 'signals',
    })
  }

  const activeRun = currentRun && runId ? currentRun : null

  return (
    <div className="min-h-screen bg-[#F5F8FC] p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px] gap-6">
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
          <EntityIntakeForm
            onSubmit={handleCreateRun}
            error={error}
            title="Start Signals Intelligence"
            subtitle="Select the entity type and enter the required fields to begin risk and opportunity signal detection."
            submitLabel="Start Signals Analysis"
          />
        )}
      </main>
      <ContextPanel type="signals" runId={runId} status={status} />
    </div>
  )
}

export default function SignalsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <SignalsPageInner />
    </Suspense>
  )
}
