'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getDueFollowups, listAssessments, type AssessmentWorkspacePayload, type DecisionRecord } from '../../lib/api'
import TrustGauge from '../../components/TrustGauge/TrustGauge'
import KulimaLogo from '../../components/KulimaLogo/KulimaLogo'

export default function DashboardPage() {
  const { status: authStatus } = useSession()
  const [assessments, setAssessments] = useState<AssessmentWorkspacePayload[]>([])
  const [activeAssessment, setActiveAssessment] = useState<AssessmentWorkspacePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dueFollowups, setDueFollowups] = useState<DecisionRecord[]>([])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const assessmentsRes = await listAssessments(50)
        if (cancelled) return
        setAssessments(assessmentsRes.assessments || [])
        // Set the most recent assessment as active
        if (assessmentsRes.assessments && assessmentsRes.assessments.length > 0) {
          setActiveAssessment(assessmentsRes.assessments[0])
        }
      } catch (err) {
        if (!cancelled) setError(String(err))
      }
      // Outcome Layer V1: 30-day follow-up reminder (best-effort, never blocks the page)
      try {
        const dueRes = await getDueFollowups()
        if (!cancelled) setDueFollowups(dueRes.followups || [])
      } catch {
        // reminders are optional surface — ignore failures
      }
    }
    if (authStatus === 'authenticated') {
      load()
    }
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

  const activeAssessments = assessments.filter(a => a.status !== 'archived')
  const completedAssessments = assessments.filter(a => a.status === 'complete' || a.status === 'completed')

  return (
    <PilotWorkspaceShell
      workspace="Dashboard"
      title="Assessment Inventory"
      description="View all assessments, their status, trust scores, and decisions."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      {/* Executive Landing Hero — logo + platform identity above the fold */}
      <section className="p-5 md:p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <KulimaLogo variant="hero" />
          <div className="w-px h-14 bg-[#DDE6F0] flex-shrink-0 hidden sm:block" />
          <div>
            <div className="text-lg font-black text-slate-900 tracking-tight leading-tight">Kulima FLEX</div>
            <div className="text-xs font-bold text-[#0B5D3B] mt-0.5">Decision Intelligence Platform</div>
            <div className="text-[11px] text-slate-400 mt-1 max-w-sm">
              Evidence-backed assessment pipeline for NGOs, development programmes, government programmes and tourism enterprises.
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="px-3 py-1.5 rounded-lg bg-[#ECFDF3] border border-[#A6F4C5] text-[11px] font-bold text-[#027A48] uppercase tracking-wider">
            Assessment Context Active
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-[#EAF3FF] border border-[#D6E8FF] text-[11px] font-bold text-[#004085] uppercase tracking-wider">
            v2.0
          </div>
        </div>
      </section>

      {/* Outcome Layer V1: 30-day follow-up widget — pending, due date, recommendation, assessment */}
      {dueFollowups.length > 0 ? (
        <section className="rounded-[12px] bg-[#FFFAEB] border border-[#FEDF89] overflow-hidden">
          <Link href="/outcomes" className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 hover:border-[#F5B464] transition">
            <div>
              <div className="text-sm font-extrabold text-[#B54708]">
                Pending Follow-Ups ({dueFollowups.length}) — assessments completed 30+ days ago
              </div>
              <div className="text-xs text-slate-600 mt-0.5">
                Help us learn if these recommendations worked: two quick questions, 30 seconds each.
              </div>
            </div>
            <span className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] text-white text-[10px] font-extrabold uppercase tracking-wider shrink-0">
              Record follow-up →
            </span>
          </Link>
          <div className="border-t border-[#FEDF89] divide-y divide-[#FEDF89] bg-white">
            {dueFollowups.slice(0, 3).map(f => (
              <Link
                key={f.runId}
                href={`/outcomes?focus=${encodeURIComponent(String(f.runId))}`}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 hover:bg-[#F5F8FC] transition"
              >
                <div className="min-w-0">
                  <div className="text-xs font-extrabold text-slate-900 truncate">
                    {f.entityName || `Assessment #${f.runId}`}
                  </div>
                  <div className="text-[11px] text-slate-500 truncate">
                    Recommendation: <strong>{f.recommendation || '—'}</strong>
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">
                    {Number.isNaN(new Date(f.followupDueAt).getTime())
                      ? 'Check-in date not set'
                      : <>Due {new Date(f.followupDueAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })} · 30-day check-in</>}
                  </div>
                </div>
                <span className="text-[10px] font-black uppercase tracking-wider text-[#B54708] bg-[#FFFAEB] border border-[#FEDF89] px-2 py-1 rounded-full shrink-0">
                  {(() => {
                    const t = new Date(f.followupDueAt).getTime()
                    if (Number.isNaN(t)) return `Due ${new Date(f.followupDueAt).toLocaleDateString()}`
                    const days = Math.floor((Date.now() - t) / 86_400_000)
                    return days <= 0 ? 'Due today' : `Follow-up due ${days}d ago`
                  })()}
                </span>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {/* KPI Hero Row — above the fold */}
      <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {[
          {
            label: 'Total Assessments',
            value: String(assessments.length),
            accent: assessments.length > 0 ? 'text-[#12B76A]' : 'text-slate-900',
            sub: `${activeAssessments.length} active · ${completedAssessments.length} complete`,
          },
          {
            label: 'Active Assessment',
            value: activeAssessment?.displayEntity || activeAssessment?.organizationName || '—',
            accent: 'text-slate-900',
            sub: activeAssessment?.status || 'No active assessment',
          },
          {
            label: 'Status',
            value: activeAssessment?.status || '—',
            accent: 'text-slate-900',
            sub: 'of active assessment',
          },
          {
            label: 'Trust Score',
            value: activeAssessment?.trustScore ? String(activeAssessment.trustScore) : '—',
            accent: 'text-slate-900',
            sub: 'of active assessment',
          },
          {
            label: 'Documents',
            value: String(activeAssessment?.uploadedDocuments?.length || 0),
            accent: 'text-slate-900',
            sub: 'uploaded to assessment',
          },
        ].map(({ label, value, accent, sub }) => (
          <div key={label} className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col gap-1">
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{label}</div>
            <div className={`text-2xl font-black tracking-tight ${accent}`}>{value}</div>
            <div className="text-[10px] text-slate-400 font-medium">{sub}</div>
          </div>
        ))}
      </section>

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
                Create your first assessment by uploading documents from the{' '}
                <Link href="/" className="text-[#0B5D3B] font-bold hover:underline">landing page</Link>.
              </div>
            </div>
          ) : assessments.map(assessment => (
            <div key={assessment.assessmentId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 truncate">{assessment.displayEntity || assessment.organizationName || assessment.startupName}</div>
                  <div className="text-[11px] text-slate-500">{assessment.founderName}</div>
                  <div className="text-[10px] text-slate-400 mt-1.5">Status: {assessment.status}</div>
                </div>
                <Link
                  href={`/flex?assessmentId=${assessment.assessmentId}`}
                  className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-white text-slate-700 border border-[#DDE6F0] hover:bg-slate-50 shrink-0"
                >
                  View
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
