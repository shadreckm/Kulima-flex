'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useSearchParams } from 'next/navigation'
import { useAssessmentWorkspace } from '../../hooks/useAssessmentWorkspace'
import { getActivity, type AuditEventRecord } from '../../lib/enterprise'

/**
 * Activity Workspace — governance audit trail scoped to the Assessment Context.
 *
 * Resolves the context through GET /api/v1/assessment-workspace/{id} or /active,
 * then loads the audit stream via typed getActivity({ assessmentId }) from
 * enterprise.ts. No localStorage, no stored-run lookups, no demo assumptions.
 *
 * Backend event vocabulary (kulima.core.audit):
 *   assessment.created · assessment.started · assessment.evidence_attached
 *   research.triggered · signals.generated · decision.generated
 *   assessment.deleted (+ feedback / export / access events).
 */
const EVENT_LABELS: Record<string, string> = {
  'assessment.created': 'Assessment Created',
  'assessment.started': 'Research Started',
  'assessment.evidence_attached': 'Documents Uploaded',
  'documents.uploaded': 'Documents Uploaded',
  'research.triggered': 'Research Started',
  'research.completed': 'Research Completed',
  'signals.generated': 'Signals Generated',
  'decision.generated': 'Decision Generated',
  'reports.exported': 'Reports Exported',
  'export.created': 'Reports Exported',
  'feedback.submitted': 'Feedback Submitted',
  'user.login': 'User Login',
  'assessment.deleted': 'Assessment Deleted',
}

function ActivityInner() {
  const { status: authStatus } = useSession()
  const router = useRouter()
  const { data: ctx, loading: ctxLoading, error: ctxError, noAssessment } = useAssessmentWorkspace(authStatus === 'authenticated')
  const [events, setEvents] = useState<AuditEventRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (authStatus !== 'authenticated' || !ctx) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await getActivity({ assessmentId: ctx.assessmentId, limit: 100 })
        if (cancelled) return
        setEvents(Array.isArray(res?.events) ? res.events : [])
      } catch (e: any) {
        // The audit feed is informational — never block the page on it.
        if (!cancelled) setError(e?.message ?? 'Activity feed unavailable.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [authStatus, ctx])

  if (authStatus === 'loading') {
    return <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Checking session…</div>
  }
  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
        <button onClick={() => signIn()} className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm">Sign in</button>
      </div>
    )
  }

  // Redirect to Create Assessment if no assessment exists
  if (noAssessment && !ctxLoading) {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">No Assessment Found</div>
        <div className="text-sm text-slate-500">Create an assessment to view activity.</div>
        <Link href="/" className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm">
          Create Assessment
        </Link>
      </div>
    )
  }

  const displayEntity = ctx?.displayEntity || ctx?.organizationName || ctx?.startupName || ''

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold">Activity Timeline</h1>
      <p className="mt-1 text-sm text-slate-500 max-w-2xl">
        Every action on this assessment in order — what was uploaded, when research and signals ran, when the decision
        was made and what was exported. This is the audit record your institution points to afterwards.
      </p>
      {displayEntity ? (
        <p className="mt-1 text-sm text-slate-500">
          {displayEntity} · {ctx?.assessmentTypeLabel || 'Assessment'}
        </p>
      ) : null}

      {ctxError && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {ctxError}{' '}
          <Link className="underline" href="/flex">Open workspace</Link>
        </div>
      )}

      {error && !ctxError && (
        <div className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">{error}</div>
      )}

      {loading && !ctxError && <p className="mt-4 text-sm opacity-70">Loading activity…</p>}

      {!loading && !ctxError && !error && events.length === 0 && (
        <p className="mt-4 text-sm opacity-70">No activity yet for this assessment.</p>
      )}

      {events.length > 0 && (
        <ol className="mt-6 space-y-4 border-l-2 border-gray-200 pl-6">
          {events.map((e, i) => {
            const label = EVENT_LABELS[e.eventType] ?? e.label ?? e.eventType
            const meta = e.metadata && typeof e.metadata === 'object' ? e.metadata : {}
            const detailParts: string[] = []
            if (meta.founder) detailParts.push(`Lead: ${String(meta.founder)}`)
            if (meta.startup) detailParts.push(String(meta.startup))
            if (meta.documents) detailParts.push(`${meta.documents} document${Number(meta.documents) === 1 ? '' : 's'} attached`)
            if (meta.count) detailParts.push(`${meta.count} record${Number(meta.count) === 1 ? '' : 's'}`)
            if (meta.runId) detailParts.push(`run ${meta.runId}`)
            const when = e.createdAt ? new Date(e.createdAt) : null
            const whenText = when && !Number.isNaN(when.getTime())
              ? when.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
              : (e.createdAt ?? '')
            return (
              <li key={e.id ?? i} className="relative">
                <span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full bg-[#159A62]" />
                <div className="text-sm font-medium">{label}</div>
                <div className="text-xs opacity-70">
                  {whenText}
                  {detailParts.length ? ` — ${detailParts.join(' · ')}` : ''}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

export default function ActivityPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <ActivityInner />
    </Suspense>
  )
}
