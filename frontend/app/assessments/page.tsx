'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getActiveAssessment, listAssessments, getDecisionHistory, type AssessmentWorkspacePayload } from '../../lib/api'
import { FollowupChip, followupStateFromRow } from '../../components/OutcomeFollowup/OutcomeFollowup'

/** Pipeline states in the words a programme team uses, not the API's snake_case. */
const STATUS_TEXT: Record<string, string> = {
  intake: 'Draft',
  needs_confirmation: 'Needs confirmation',
  ready: 'Ready to run',
  running: 'Running',
  complete: 'Complete',
  completed: 'Complete',
  failed: 'Failed',
}

function statusText(status?: string | null): string {
  const key = String(status || '').toLowerCase()
  if (!key) return 'Status not recorded'
  return STATUS_TEXT[key] || key.replace(/_/g, ' ')
}

export default function AssessmentsPage() {
  const { status: authStatus } = useSession()
  const [assessments, setAssessments] = useState<AssessmentWorkspacePayload[]>([])
  const [activeAssessment, setActiveAssessment] = useState<AssessmentWorkspacePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // Outcome Layer V1: run_id -> decision-history row, loaded once for the
  // whole list so every card can show its follow-up state without N+1 calls.
  const [followupByRun, setFollowupByRun] = useState<Record<string, Record<string, any>>>({})

  async function loadAssessments() {
    setLoading(true)
    try {
      const assessmentsRes = await listAssessments(50)
      setAssessments(assessmentsRes.assessments || [])
      try {
        const active = await getActiveAssessment()
        setActiveAssessment(active)
      } catch {
        setActiveAssessment(null)
      }
      // Best-effort: cards simply omit the chip if outcome data is unavailable.
      try {
        const hist = await getDecisionHistory(200)
        const map: Record<string, Record<string, any>> = {}
        for (const d of hist.decisions || []) {
          if (d.id != null) map[String(d.id)] = d
        }
        setFollowupByRun(map)
      } catch {
        setFollowupByRun({})
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    if (authStatus !== 'authenticated') return
    loadAssessments().catch(err => {
      if (!cancelled) setError(String(err))
    })
    return () => { cancelled = true }
  }, [authStatus])

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
    <PilotWorkspaceShell
      workspace="Assessments"
      title="Assessment Inventory"
      description="Every assessment in this workspace with its profile, pipeline state, evidence trust and verdict."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-[#0B5D3B] animate-pulse" />
          <span className="text-sm font-semibold text-slate-500">Loading assessments…</span>
        </div>
      ) : null}

      {/* Active Assessment */}
      {activeAssessment && (
        <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-[#DDE6F0]">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Active Assessment</h2>
            <span className="text-xs text-slate-500 font-semibold">Current</span>
          </div>
          <div className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="text-xs font-bold text-slate-900 truncate">{activeAssessment.displayEntity || activeAssessment.organizationName || activeAssessment.startupName}</div>
                <div className="text-[11px] text-slate-500">{activeAssessment.assessmentTypeLabel || 'Assessment'}{activeAssessment.founderName ? ` · Lead: ${activeAssessment.founderName}` : ''}</div>
                <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-400 mt-1.5">
                  <span title="Pipeline state of this assessment">Status: {statusText(activeAssessment.status)}</span>
                  <span>·</span>
                  <span
                    title="0–100: how much of this assessment rests on verifiable, corroborated sources"
                  >
                    Trust {activeAssessment.trustScore != null ? `${Math.round(activeAssessment.trustScore)}/100` : 'not scored'}
                  </span>
                  <span>·</span>
                  <span>
                    Verdict: {activeAssessment.decision?.recommendation || 'pending'}
                  </span>
                  {activeAssessment.runId ? <FollowupChip runId={activeAssessment.runId} state={followupStateFromRow(followupByRun[String(activeAssessment.runId)])} /> : null}
                </div>
              </div>
              <Link
                href={`/flex?assessmentId=${activeAssessment.assessmentId}`}
                className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-[#0B5D3B] text-white hover:bg-[#08482E] shrink-0"
              >
                Open
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Assessment List */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-[#DDE6F0]">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">All Assessments</h2>
          <span className="text-xs text-slate-500 font-semibold">{assessments.length}</span>
        </div>
        <div className="space-y-3">
          {assessments.length === 0 ? (
            <div className="py-6 text-center">
              <div className="text-sm font-bold text-slate-700">No assessments yet</div>
              <div className="text-[11px] text-slate-400 mt-1">
                Start an assessment by uploading your documents from the{' '}
                <Link href="/" className="text-[#0B5D3B] font-bold hover:underline">Kulima FLEX home screen</Link>.
              </div>
            </div>
          ) : assessments.map(assessment => (
            <div key={assessment.assessmentId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 truncate">{assessment.displayEntity || assessment.organizationName || assessment.startupName}</div>
                  <div className="text-[11px] text-slate-500">{assessment.assessmentTypeLabel || 'Assessment'}{assessment.founderName ? ` · Lead: ${assessment.founderName}` : ''}</div>
                  <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-400 mt-1.5">
                    <span title="Pipeline state of this assessment">Status: {statusText(assessment.status)}</span>
                    <span>·</span>
                    <span title="0–100: how much of this assessment rests on verifiable, corroborated sources">
                      Trust {assessment.trustScore != null ? `${Math.round(assessment.trustScore)}/100` : 'not scored'}
                    </span>
                    <span>·</span>
                    <span>Verdict: {assessment.decision?.recommendation || 'pending'}</span>
                    {assessment.runId ? <FollowupChip runId={assessment.runId} state={followupStateFromRow(followupByRun[String(assessment.runId)])} /> : null}
                  </div>
                </div>
                <Link
                  href={`/flex?assessmentId=${assessment.assessmentId}`}
                  className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-white text-slate-700 border border-[#DDE6F0] hover:bg-slate-50 shrink-0"
                >
                  Open
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
