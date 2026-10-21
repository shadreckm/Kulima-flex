'use client'

/**
 * Global Assessment Context Guard (Production Blocker 1).
 *
 * Centralizes the "no assessment" behavior for every workspace route so users
 * NEVER see a raw 404 / "No assessment context found" error:
 *
 *   Assessment exists       → the page renders normally (children).
 *   No assessment exists    → automatic redirect to the landing page ('/')
 *                             which starts the upload workflow.
 *
 * Usage (any workspace page):
 *   const { noAssessment, loading, data } = useAssessmentWorkspace(enabled)
 *   if (noAssessment && !loading) return <AssessmentGuard />
 *   // or wrap content: <AssessmentGuard active={noAssessment && !loading}>…</AssessmentGuard>
 */

import { useEffect, useRef, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'

export function AssessmentGuard({
  active,
  children,
  redirectTo = '/',
  label = 'Opening the upload workflow…',
  loading = false,
}: {
  /** True when the workspace resolved no Assessment Context. */
  active: boolean
  /** Page content when the guard is not active. */
  children?: ReactNode
  /** Redirect target (landing page starts the upload workflow). */
  redirectTo?: string
  /** Brief transition label shown while redirecting. */
  label?: string
  /** True when still loading context - do NOT redirect while loading. */
  loading?: boolean
}) {
  const router = useRouter()
  const redirectedRef = useRef(false)

  useEffect(() => {
    // DO NOT REDIRECT while loading - prevents redirect loop during context hydration
    if (!active || loading || redirectedRef.current) return
    // HYDRATION GRACE: a context created seconds ago may not be indexed by the
    // backend yet. Give the bootstrap retries a final grace window before
    // bouncing back to the landing page — this is what breaks the loop.
    const grace = setTimeout(() => {
      if (redirectedRef.current) return
      redirectedRef.current = true
      // Replace (not push) so Back never returns the user to a dead workspace.
      router.replace(redirectTo)
    }, 2000)
    return () => clearTimeout(grace)
  }, [active, loading, redirectTo, router])

  if (!active) return <>{children}</>

  // Show loading state instead of redirecting while hydrating context
  if (loading) {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-[#0B5D3B] animate-pulse" />
          <span className="text-sm font-semibold text-slate-500">Loading Assessment Context…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <span className="w-3 h-3 rounded-full bg-[#0B5D3B] animate-pulse" />
        <span className="text-sm font-semibold text-slate-500">{label}</span>
      </div>
    </div>
  )
}

export default AssessmentGuard
