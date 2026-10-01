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

  const load = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    try {
      const idParam = searchParams.get('id') || searchParams.get('assessmentId')
      const payload = idParam
        ? await getAssessmentWorkspace(idParam)
        : await getActiveAssessment()
      setData(payload)
    } catch (e: any) {
      setError(e?.message || 'No active assessment found. Create an assessment first.')
      setData(null)
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
    reload: load,
  }
}
