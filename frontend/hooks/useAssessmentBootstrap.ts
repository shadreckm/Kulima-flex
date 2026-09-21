'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../lib/api'
import {
  contextNeedsConfirmation,
  loadAssessmentContext,
  type AssessmentContext,
} from '../lib/assessment-store'
import type { CurrentRunState } from '../lib/current-run'
import { saveRecentRun } from '../lib/run-history'

export type AssessmentBootState =
  | 'idle'
  | 'none'
  | 'starting'
  | 'started'
  | 'needs_confirmation'
  | 'error'

type Options = {
  /** True once the current-run store has hydrated. */
  ready: boolean
  /** True when a run is already active (auto-start is skipped). */
  hasCurrentRun: boolean
  setCurrentRun: (run: CurrentRunState, options?: { syncUrl?: boolean }) => void
  route: 'flex' | 'signals'
}

/**
 * Single-intake bootstrap: when the shared Assessment Context exists but no
 * run has started yet, start (or reuse) the intelligence run automatically —
 * Tavily research is driven by the extracted entity, so the user is never
 * asked for the founder or organisation again (Steps 5 & 8).
 */
export function useAssessmentBootstrap({ ready, hasCurrentRun, setCurrentRun, route }: Options) {
  const [assessmentContext, setAssessmentContext] = useState<AssessmentContext | null>(null)
  const [bootState, setBootState] = useState<AssessmentBootState>('idle')
  const [attempt, setAttempt] = useState(0)
  const startedRef = useRef<string | null>(null)

  useEffect(() => {
    if (!ready) return
    const ctx = loadAssessmentContext()
    setAssessmentContext(ctx)
    if (!ctx?.assessmentId) {
      setBootState('none')
      return
    }
    if (hasCurrentRun) return
    if (contextNeedsConfirmation(ctx)) {
      setBootState('needs_confirmation')
      return
    }
    if (startedRef.current === ctx.assessmentId) return
    startedRef.current = ctx.assessmentId

    let cancelled = false
    setBootState('starting')
    api
      .startAssessmentRun(ctx.assessmentId)
      .then((res) => {
        if (cancelled) return
        setCurrentRun(
          {
            runId: res.runId,
            startupName: ctx.entityName || ctx.displayEntity || 'Assessment',
            founderName: ctx.founderOrLead || '',
            entityType: ctx.entityType,
            status: res.status || 'running',
          },
          { syncUrl: false },
        )
        saveRecentRun({
          runId: res.runId,
          founder: ctx.founderOrLead || '',
          startup: ctx.entityName || ctx.displayEntity || 'Assessment',
          status: res.status || 'running',
          createdAt: new Date().toISOString(),
          route,
        })
        setBootState('started')
      })
      .catch(() => {
        if (cancelled) return
        startedRef.current = null
        setBootState('error')
      })
    return () => {
      cancelled = true
    }
  }, [ready, hasCurrentRun, setCurrentRun, route, attempt])

  /** Re-attempt the automatic run start after a failure. */
  const retry = useCallback(() => {
    startedRef.current = null
    setAttempt(n => n + 1)
  }, [])

  return { assessmentContext, bootState, retry }
}
