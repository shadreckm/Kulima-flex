'use client'

import React, { useEffect, useState, Suspense } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import ChatShell from '../../components/ChatShell/ChatShell'
import ContextPanel from '../../components/ContextPanel/ContextPanel'
import NavigationSidebar from '../../components/NavigationSidebar/NavigationSidebar'
import AssessmentSummaryBar from '../../components/AssessmentSummaryBar/AssessmentSummaryBar'
import WorkspaceHeader from '../../components/WorkspaceHeader'
import AssessmentProgress from '../../components/AssessmentProgress'
import * as api from '../../lib/api'
import { useAssessmentBootstrap } from '../../hooks/useAssessmentBootstrap'

function FlexPageInner() {
  const { status: authStatus } = useSession()
  // Assessment Context drives everything — no legacy current-run store.
  const { assessmentContext, bootState, retry } = useAssessmentBootstrap({
    route: 'flex',
  })

  const runId = assessmentContext?.runId || null
  const [statusOverride, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const status = statusOverride ?? assessmentContext?.status ?? null

  useEffect(() => {
    setPolling(bootState === 'started')
  }, [bootState])

  useEffect(() => {
    if (!runId || !polling) return
    let cancelled = false
    const interval = setInterval(async () => {
      try {
        const s = await api.getRunStatus(runId)
        if (cancelled) return
        setStatus(s.status)
        if (s.status === 'completed' || s.status === 'failed') {
          setPolling(false)
        }
      } catch (err) {
        if (!cancelled) setError(String(err))
        setPolling(false)
      }
    }, 3000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [runId, polling])

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

  return (
    <div className="min-h-screen bg-[#F5F8FC] p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px] gap-6">
      <NavigationSidebar
        workspace="AI Analyst Workspace"
        runId={runId}
        status={status}
        startupName={assessmentContext?.displayEntity || assessmentContext?.entityName}
        recommendation={assessmentContext?.decision?.recommendation}
        trustScore={assessmentContext?.trustScore}
      />
      <main className="flex flex-col gap-4">
        {assessmentContext ? <AssessmentSummaryBar context={assessmentContext} status={status} /> : null}
        {runId ? (
          <>
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
          <section className="rounded-xl border border-[#DDE6F0] bg-white p-5 shadow-saas sm:p-6">
            <h1 className="text-lg font-bold text-slate-900">No assessment context found</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Create an assessment from your documents to open the AI Analyst workspace.
            </p>
            <Link
              href="/"
              className="mt-4 inline-flex min-h-11 items-center justify-center rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-sm font-bold text-white transition hover:bg-[#08482E] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0B5D3B]"
            >
              Start an assessment
            </Link>
          </section>
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
