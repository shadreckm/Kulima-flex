'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import * as api from '../lib/api'
import {
  contextNeedsConfirmation,
  loadAssessmentContext,
  saveIntakeContext,
  type AssessmentContext,
} from '../lib/assessment-store'

export type AssessmentBootState =
  | 'idle'
  | 'none'
  | 'no_assessment'
  | 'starting'
  | 'started'
  | 'needs_confirmation'
  | 'error'

type Options = {
  /** Deprecated legacy param — ignored. The Assessment Context is the only gate. */
  ready?: boolean
  /** Deprecated legacy param — ignored. */
  hasCurrentRun?: boolean
  /** Deprecated legacy param — ignored. Run state lives in the context. */
  setCurrentRun?: (run: unknown, options?: unknown) => void
  route?: string
}

/**
 * Single-intake bootstrap, Assessment-Context-only.
 *
 * When the shared Assessment Context exists but no run has started yet, start
 * (or reuse) the intelligence run automatically. Run identity is resolved from
 * the context, never from a legacy localStorage current-run store.
 */
export function useAssessmentBootstrap(options: Options = {}) {
  const { status: authStatus } = useSession()
  const [assessmentContext, setAssessmentContext] = useState<AssessmentContext | null>(null)
  const [bootState, setBootState] = useState<AssessmentBootState>('idle')
  const [attempt, setAttempt] = useState(0)
  const startedRef = useRef<string | null>(null)

  // MVP reliability (Issue 4): when a run is attached but the assessment has
  // not yet reached complete, poll the run status and re-sync the shared
  // context on completion so Research / Evidence / Signals / Decision / Reports
  // all refresh automatically — no page stays in a loading state.
  useEffect(() => {
    if (authStatus === 'loading') return
    const ctx = loadAssessmentContext()
    if (!ctx?.runId) return
    if (ctx.status === 'complete' || ctx.status === 'completed') return
    let cancelled = false
    let ticks = 0
    const interval = setInterval(async () => {
      ticks += 1
      if (ticks > 150) {
        clearInterval(interval)
        return
      }
      try {
        const s = await api.getRunStatus(ctx.runId)
        const st = String(s?.status || '').toLowerCase()
        if (cancelled) return
        if (st === 'complete' || st === 'completed' || st === 'failed') {
          clearInterval(interval)
          // Re-fetch the full assessment context so research / signals / decision
          // / reports propagate to every workspace listening on the store.
          try {
            if (ctx.assessmentId) {
              const full = await api.getAssessment(ctx.assessmentId)
              if (!cancelled && full) {
                const synced = saveIntakeContext(full)
                setAssessmentContext(synced)
              }
            }
          } catch {
            // Best-effort: at minimum record the completed status.
            if (!cancelled) {
              const updated = saveIntakeContext({ ...(ctx as unknown as Record<string, any>), status: st })
              setAssessmentContext(updated)
            }
          }
        }
      } catch {
        // Transient errors keep polling until the tick budget is exhausted.
      }
    }, 3000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [authStatus, attempt, bootState])

  useEffect(() => {
    // Do not run while the session is still resolving — an unauthenticated
    // probe of getActiveAssessment() would fail silently, cache 'none', and
    // never re-run once auth resolves, leaving the workspace empty.
    if (authStatus === 'loading') return
    let cancelled = false
    let ctx = loadAssessmentContext()

    async function syncAndStart() {
      if (!ctx?.assessmentId) {
        try {
          const active = await api.getActiveAssessment()
          if (active?.assessmentId) {
            ctx = saveIntakeContext(active)
          }
        } catch (activeErr) {
          // If getActiveAssessment fails, retry a few times with exponential backoff
          // This handles the case where the assessment was just created but the
          // backend hasn't indexed it yet
          for (let i = 0; i < 3; i++) {
            await new Promise(r => setTimeout(r, 500 * (i + 1)))
            try {
              const retryActive = await api.getActiveAssessment()
              if (retryActive?.assessmentId) {
                ctx = saveIntakeContext(retryActive)
                break
              }
            } catch {
              // continue retrying
            }
          }
        }
      }
      if (cancelled) return
      setAssessmentContext(ctx)
      if (!ctx?.assessmentId) {
        setBootState('no_assessment')
        return
      }

      // A run is already attached to this assessment — reuse it.
      if (ctx.runId) {
        setBootState('started')
        return
      }

      if (contextNeedsConfirmation(ctx)) {
        setBootState('needs_confirmation')
        return
      }
      if (startedRef.current === ctx.assessmentId) return
      startedRef.current = ctx.assessmentId

      setBootState('starting')
      try {
        const res = await api.startAssessmentRun(ctx.assessmentId)
        if (cancelled) return
        // Persist the runId straight into the Assessment Context — no
        // legacy current-run store, no recent-run history.
        ctx = {
          ...ctx,
          runId: res.runId,
          status: (res.status as AssessmentContext['status']) || 'running',
        }
        saveIntakeContext(ctx)
        setAssessmentContext(ctx)
        setBootState('started')
      } catch (err) {
        if (cancelled) return
        startedRef.current = null
        setBootState('error')
      }
    }

    syncAndStart()
    return () => {
      cancelled = true
    }
  }, [attempt, authStatus])

  /** Re-attempt the automatic run start after a failure. */
  const retry = useCallback(() => {
    startedRef.current = null
    setAttempt(n => n + 1)
  }, [])

  return { assessmentContext, bootState, retry }
}
