'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  getActiveAssessment,
  getAssessmentWorkspace,
  type AssessmentWorkspacePayload,
} from '../lib/api'

export type UseAssessmentWorkspaceResult = {
  /** The Assessment Context — single source of truth for every workspace tab. */
  data: AssessmentWorkspacePayload | null
  assessmentId: string | null
  runId: string | null
  loading: boolean
  error: string | null
  /** True when no assessment exists → the Global Assessment Guard redirects to '/' (upload workflow). */
  noAssessment: boolean
  reload: () => Promise<void>
}

/**
 * Single-source-of-truth reader for workspace tabs.
 *
 * Resolves the Assessment Context through:
 *   GET /api/v1/assessment-workspace/{id}   (when ?id= / ?assessmentId= present)
 *   GET /api/v1/assessment-workspace/active (otherwise)
 *
 * No localStorage, no stored-run lookups, no legacy run IDs.
 */
export function useAssessmentWorkspace(enabled: boolean): UseAssessmentWorkspaceResult {
  const searchParams = useSearchParams()
  const [data, setData] = useState<AssessmentWorkspacePayload | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  const [noAssessment, setNoAssessment] = useState(false)

  const load = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    setNoAssessment(false)
    const idParam = searchParams.get('id') || searchParams.get('assessmentId')
    try {
      const payload = idParam
        ? await getAssessmentWorkspace(idParam)
        : await getActiveAssessment()
      setData(payload)
    } catch (e: any) {
      // If getActiveAssessment fails, try to load from local assessment store
      // This handles the case where the assessment was just created but the
      // backend hasn't indexed it yet or org_id isn't set
      if (!idParam) {
        try {
          const { loadAssessmentContext } = await import('../lib/assessment-store')
          const localCtx = loadAssessmentContext()
          if (localCtx?.assessmentId) {
            const fallbackPayload = await getAssessmentWorkspace(localCtx.assessmentId)
            setData(fallbackPayload)
            return
          }
        } catch (fallbackErr) {
          // ignore fallback errors
        }
      }
      // Check if this is a "no assessment" error (404 with message about no assessment context)
      const isNoAssessmentError = e?.message?.includes('No assessment context found') ||
                                  e?.message?.includes('not found or not accessible') ||
                                  e?.status === 404 ||
                                  String(e).includes('404')
      if (isNoAssessmentError && !idParam) {
        // Global Assessment Guard: no raw API error is ever surfaced.
        setNoAssessment(true)
        setError(null)
        setData(null)
      } else {
        setError('The workspace could not be loaded. Please try again.')
        setData(null)
      }
    } finally {
      setLoading(false)
    }
  }, [enabled, searchParams])

  useEffect(() => {
    void load()
  }, [load])

  return {
    data,
    assessmentId: data?.assessmentId || null,
    runId: data?.runId || null,
    loading,
    error,
    noAssessment,
    reload: load,
  }
}
