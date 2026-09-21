'use client'

import React, { useEffect, useState, Suspense } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import ChatShell from '../../components/ChatShell/ChatShell'
import ContextPanel from '../../components/ContextPanel/ContextPanel'
import NavigationSidebar from '../../components/NavigationSidebar/NavigationSidebar'
import CurrentRunBanner from '../../components/CurrentRunBanner/CurrentRunBanner'
import EntityIntakeForm from '../../components/EntityIntakeForm/EntityIntakeForm'
import AssessmentSummaryBar from '../../components/AssessmentSummaryBar/AssessmentSummaryBar'
import * as api from '../../lib/api'
import { entityToRunParams } from '../../lib/entity-types'
import { saveRecentRun, updateRecentRunStatus } from '../../lib/run-history'
import { useCurrentRun } from '../../hooks/useCurrentRun'
import { useAssessmentBootstrap } from '../../hooks/useAssessmentBootstrap'

function FlexPageInner() {
  const { status: authStatus } = useSession()
  const { currentRun, ready, setCurrentRun, clearRun, hasCurrentRun } = useCurrentRun()

  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)

  // Single intake: the shared Assessment Context drives the run identity —
  // no founder / startup / entity-type re-entry on this page.
  const { assessmentContext, bootState, retry } = useAssessmentBootstrap({
    ready,
    hasCurrentRun,
    setCurrentRun,
    route: 'flex',
  })

  useEffect(() => {
    if (bootState === 'started') setPolling(true)
  }, [bootState])

  useEffect(() => {
    if (!ready || !currentRun?.runId) return
    setRunId(currentRun.runId)
    setStatus(currentRun.status || 'completed')
    api.getRunStatus(currentRun.runId)
      .then((s) => {
        setStatus(s.status)
        setCurrentRun(
          { ...currentRun, status: s.status, storedRunId: currentRun.storedRunId || (s.dbId ? String(s.dbId) : currentRun.storedRunId) },
          { syncUrl: false },
        )
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
            setCurrentRun(
              { ...currentRun, runId, status: s.status, storedRunId: s.dbId ? String(s.dbId) : currentRun.storedRunId },
              { syncUrl: false },
            )
          }
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
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
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
    const nextRun = {
      runId: res.runId,
      startupName: params.startup || params.founder,
      founderName: params.founder,
      entityType: params.entityType,
      programName: params.entityMeta?.programName || '',
      status: res.status,
    }
    setCurrentRun(nextRun)
    saveRecentRun({
      runId: res.runId,
      founder: params.founder,
      startup: params.startup || params.founder,
      status: res.status,
      createdAt: new Date().toISOString(),
      route: 'flex',
    })
  }

  const activeRun = currentRun && runId ? currentRun : null

  return (
    <div className="min-h-screen bg-[#F5F8FC] p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px] gap-6">
      <NavigationSidebar
        workspace="AI Analyst Workspace"
        runId={runId}
        status={status}
        startupName={activeRun?.startupName}
        recommendation={activeRun?.recommendation}
        trustScore={activeRun?.trustScore}
      />
      <main className="flex flex-col gap-4">
        {assessmentContext ? <AssessmentSummaryBar context={assessmentContext} status={status} /> : null}
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
            {status === 'failed' ? (
              <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
                This evaluation run encountered an error. Start a new evaluation or contact support.
              </div>
            ) : null}
            <ChatShell personaName="IC Analyst" runId={runId} />
          </>
        ) : assessmentContext?.assessmentId ? (
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-sm">
            {bootState === 'needs_confirmation' ? (
              <>
                <div className="font-bold text-slate-900">
                  Extraction confidence is low — confirm the assessment identity once.
                </div>
                <p className="text-xs text-slate-500 mt-1 leading-5">
                  The shared assessment context was created from your upload, but the entity name could
                  not be extracted with confidence. Confirm it on the intake page — Ask IC and every other
                  workspace reuse it automatically.
                </p>
                <Link
                  href="/"
                  className="inline-block mt-3 rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-xs font-extrabold uppercase tracking-wider text-white hover:bg-[#08482E] transition"
                >
                  Review assessment details →
                </Link>
              </>
            ) : bootState === 'error' ? (
              <>
                <div className="font-bold text-slate-900">Could not start the assessment run.</div>
                <p className="text-xs text-slate-500 mt-1 leading-5">
                  The shared context is ready — retry starting the intelligence run. Tavily research and
                  the IC Analyst will work from the extracted entity.
                </p>
                {error ? (
                  <div className="mt-2 font-mono text-[10px] text-red-600 break-all">{error}</div>
                ) : null}
                <button
                  type="button"
                  onClick={retry}
                  className="mt-3 rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-xs font-extrabold uppercase tracking-wider text-white hover:bg-[#08482E] transition"
                >
                  Retry run start
                </button>
              </>
            ) : (
              <>
                <div className="font-bold text-slate-900 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#F79009] animate-pulse" />
                  Starting your assessment run from the shared context…
                </div>
                <p className="text-xs text-slate-500 mt-1 leading-5">
                  Tavily research and the IC Analyst are driven by the extracted entity —{' '}
                  <strong className="text-slate-800">
                    {assessmentContext.displayEntity || assessmentContext.entityName || 'Assessment'}
                  </strong>
                  . No founder or organisation re-entry is needed.
                </p>
              </>
            )}
          </section>
        ) : (
          <EntityIntakeForm
            onSubmit={handleCreateRun}
            error={error}
            title="Start AI Analyst Evaluation"
            subtitle="No shared assessment context found — create one to skip these fields next time. Enter the entity details once to begin an evidence-backed analysis."
            submitLabel="Start Evaluation"
          />
        )}
      </main>
      <ContextPanel type="flex" runId={runId} status={status} />
    </div>
  )
}

export default function FlexPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <FlexPageInner />
    </Suspense>
  )
}
