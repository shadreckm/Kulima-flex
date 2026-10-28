'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getDecisionSnapshot, getFullBrief, reportDownloadHref, type DecisionSnapshot } from '../../lib/api'
import TrustGauge from '../../components/TrustGauge/TrustGauge'
import OutcomeFollowup from '../../components/OutcomeFollowup/OutcomeFollowup'
import { useAssessmentWorkspace } from '../../hooks/useAssessmentWorkspace'
import AssessmentGuard from '../../components/AssessmentGuard/AssessmentGuard'

type FullBrief = Record<string, any>

function domainScoreTone(score: number): string {
  if (score >= 70) return 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]'
  if (score >= 50) return 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]'
  return 'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
}

function domainScoreBar(score: number): string {
  if (score >= 70) return 'bg-[#12B76A]'
  if (score >= 50) return 'bg-[#F79009]'
  return 'bg-[#F04438]'
}

// Each assessment profile words its verdict differently (NGO → Strong
// Capacity, Programme → Ready, Government → Effective, Tourism → Ready for
// Growth, Startup → Invest). Colour must follow the meaning of the verdict,
// never the startup spelling only — otherwise a positive NGO outcome renders red.
const POSITIVE_VERDICTS = ['invest', 'strong capacity', 'ready', 'ready for growth', 'effective']
const NEGATIVE_VERDICTS = ['pass', 'at risk', 'needs strengthening', 'high risk', 'intervene']

function verdictTone(recommendation: string): 'positive' | 'neutral' | 'negative' {
  const v = (recommendation || '').toLowerCase().trim()
  if (POSITIVE_VERDICTS.includes(v)) return 'positive'
  if (NEGATIVE_VERDICTS.includes(v)) return 'negative'
  return 'neutral'
}

export default function DecisionWorkspacePage() {
  const { status: authStatus } = useSession()
  const { data: ctx, runId, loading: ctxLoading, error: ctxError, noAssessment } = useAssessmentWorkspace(authStatus === 'authenticated')
  const [brief, setBrief] = useState<FullBrief | null>(null)
  const [snapshot, setSnapshot] = useState<DecisionSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function loadBrief() {
      if (!runId) {
        setBrief(null)
        setSnapshot(null)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const data = await getFullBrief(runId)
        if (!cancelled) setBrief(data)
      } catch (err) {
        if (!cancelled) setError(String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
      // Expanded Decision Engine snapshot — best-effort; contexts without a
      // completed run keep the scorecard hidden.
      try {
        const snap = await getDecisionSnapshot(runId)
        if (!cancelled) setSnapshot(snap)
      } catch {
        if (!cancelled) setSnapshot(null)
      }
    }
    if (authStatus === 'authenticated') {
      loadBrief()
    }
    return () => { cancelled = true }
  }, [authStatus, runId])

  const displayEntity = ctx?.displayEntity || ctx?.organizationName || ctx?.startupName || ''
  const founderName = ctx?.founderName || ''

  // Extraction of Decision Dossier components — all derived from the
  // Assessment Context (single source of truth), never from stored runs.
  // A recommendation, a confidence figure or a trust score only appears here if
  // the run actually produced it. Placeholder verdicts and inferred scores are
  // the fastest way to lose a decision-maker's trust, so absence is shown as
  // absence: "Decision pending", "not scored", INSUFFICIENT EVIDENCE.
  const recommendation = ((ctx?.decision?.recommendation as string) || brief?.recommendation || '') as string
  // Confidence is stored as a 0–1 fraction and published as a percentage on the
  // decision snapshot; normalise once here so the screen never shows "1%".
  const rawConfidence = snapshot?.confidencePercent ?? (typeof brief?.confidence === 'number' ? brief.confidence : null)
  const confidenceKnown = rawConfidence != null
  const confidence = rawConfidence != null
    ? (rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence)
    : 0
  const trustScoreKnown = brief?.trust_score != null || ctx?.trustScore != null
  const trustScore = brief?.trust_score ?? ctx?.trustScore ?? 0
  const isEvidenceWeak = !trustScoreKnown || trustScore < 55

  const sources: Array<any> = Array.isArray(brief?.sources) ? brief.sources : []
  const uploadedEvidence: Array<any> = Array.isArray(brief?.uploaded_evidence) ? brief.uploaded_evidence : []
  const ei = brief?.evidence_integrity || null
  const contradictions: Array<any> = Array.isArray(ei?.contradictions) ? ei.contradictions : []
  const unsupportedClaims: Array<any> = Array.isArray(ei?.unsupported_claims) ? ei.unsupported_claims : []
  const redFlags: Array<any> = Array.isArray(brief?.red_flags) ? brief.red_flags : []
  const nextSteps: Array<string> = Array.isArray(brief?.next_steps) ? brief.next_steps : []

  // Phase 5: the decision page must answer "what am I supposed to do now?"
  // in the first screen — reason, evidence, confidence and next action, in words.
  const sourceCount = sources.length + uploadedEvidence.length
  const evidenceGrade: string | null = ei?.integrity_grade || snapshot?.reliabilityGrade || null
  const tone = isEvidenceWeak ? 'negative' : verdictTone(recommendation)
  const primaryNextAction =
    snapshot?.nextAction ||
    nextSteps[0] ||
    'Add the evidence still missing from this assessment, then re-run it to raise confidence in the decision.'
  const decisionReason =
    snapshot?.topReasons?.[0] ||
    (typeof brief?.investment_recommendation === 'string' && brief.investment_recommendation
      ? brief.investment_recommendation
      : 'No written rationale was recorded for this run.')

  // Extract signals from uploaded evidence + brief
  const signalsGenerated: Array<string> = []
  uploadedEvidence.forEach(doc => {
    if (Array.isArray(doc.signals_generated)) {
      signalsGenerated.push(...doc.signals_generated)
    }
  })
  if (redFlags.length > 0) {
    signalsGenerated.push(`${redFlags.length} structural risk flag${redFlags.length !== 1 ? 's' : ''} raised against this evidence`)
  }
  if (sources.length >= 3) {
    signalsGenerated.push(`${sources.length} independent sources were cross-checked against the uploaded documents`)
  }

  // Opportunity synthesis — grounded in the brief only (no hardcoded domain copy)
  const opportunities = [brief?.market_assessment, brief?.startup_assessment].filter(Boolean)

  if (authStatus === 'loading') {
    return <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
        <button onClick={() => signIn()} className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm">
          Sign in
        </button>
      </div>
    )
  }

  // Global Assessment Context Guard: no assessment → auto-redirect to the
  // landing page (upload workflow). Users never see a raw 404 or dead end.
  // Pass loading to prevent redirect loop during context hydration.
  if (noAssessment && !ctxLoading) {
    return <AssessmentGuard active loading={false} />
  }

  // STATE SYNCHRONIZATION FIX: Derive status from actual data, not just cached state
  // If decision snapshot exists, status should be 'complete' regardless of stored status
  const hasDecisionData = Boolean(snapshot || brief)
  const effectiveStatus = hasDecisionData ? 'complete' : (ctx?.status || 'active')

  return (
    <PilotWorkspaceShell
      workspace="Decision"
      title="Decision Workspace"
      description="The decision, the evidence it rests on, how much that evidence supports it, and what to do next."
      runId={runId}
      status={effectiveStatus === 'complete' ? 'active' : effectiveStatus}
      startupName={displayEntity || undefined}
      recommendation={recommendation}
      trustScore={trustScore || undefined}
      assessmentCtx={ctx ? {
        entityType: (ctx.assessmentType as any) || 'ngo',
        entityLabel: ctx.assessmentTypeLabel || 'Assessment',
        entityName: ctx.displayEntity || ctx.organizationName || ctx.startupName || '',
        founderOrLead: ctx.founderName || '',
        runId: ctx.runId || '',
        createdAt: ctx.createdAt || '',
        hasDocument: (ctx.documentCount ?? 0) > 0,
        assessmentId: ctx.assessmentId,
        assessmentTypeLabel: ctx.assessmentTypeLabel,
        status: ctx.status,
        displayEntity: ctx.displayEntity || ctx.organizationName || ctx.startupName,
        sector: ctx.sector,
        confidence: ctx.confidence,
        trustScore: ctx.trustScore,
        documentCount: ctx.documentCount,
        decision: ctx.decision,
      } : null}
    >
      {ctxError ? (
        <div className="p-4 bg-amber-50 text-amber-800 rounded-[12px] border border-amber-200 text-sm font-medium">
          {ctxError}{' '}
          <Link href="/flex" className="underline font-bold ml-2">Open workspace</Link>
        </div>
      ) : null}
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div> : null}
      {ctxLoading || loading ? (
        <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] text-sm text-slate-500 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#0B5D3B] animate-pulse" />
          Loading decision dossier from the Assessment Context…
        </div>
      ) : null}

      {/* Assessment Context & Export Action Bar — no run selector */}
      {runId ? (
        <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Assessment Context</label>
            <div className="mt-1.5 text-sm text-slate-900 font-bold truncate">
              {displayEntity || 'Assessment'}{founderName ? ` · Lead: ${founderName}` : ''}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {runId ? (
              <a
                href={reportDownloadHref(runId, 'memo', 'pdf')}
              download
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-xs font-extrabold uppercase tracking-wider transition shadow-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span>Export Decision Memo (PDF)</span>
            </a>
          ) : null}
        </div>
      </section>
      ) : null}

      {/* Outcome Layer V1: follow-up visibility in the decision surface —
          due banner, quiet countdown, or recorded review, all one-click. */}
      {runId ? <OutcomeFollowup runId={runId} /> : null}

      {/* Decision Dossier Master Grid (10 Core Elements) */}
      {brief ? (
        <div className="space-y-6">
          {/* Top Level Verdict & Confidence Hero */}
          <section className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas-elevated relative overflow-hidden">
            <div className={`absolute top-0 left-0 right-0 h-1.5 ${
              tone === 'positive' ? 'bg-[#12B76A]' :
              tone === 'neutral' ? 'bg-[#F79009]' : 'bg-[#F04438]'
            }`} />

            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]">
                    Decision Dossier
                  </span>
                  <span className="text-xs text-slate-500 font-mono">Assessment {ctx?.assessmentId ? ctx.assessmentId.slice(0, 8) : '—'}</span>
                </div>

                <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                  <span>{displayEntity || brief.startup_name || 'Assessment'}</span>
                  <span className={`text-xs px-3 py-1 rounded-full font-black uppercase tracking-wider ${
                    tone === 'positive' ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
                    tone === 'neutral' ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
                    'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
                  }`}>
                    {isEvidenceWeak ? 'INSUFFICIENT EVIDENCE' : recommendation || 'Decision pending'}
                  </span>
                </h1>

                <div className="text-xs text-slate-600 mt-1">
                  Lead: <strong className="text-slate-900">{brief.founder_name || founderName || '—'}</strong> · Sector: <strong className="text-slate-900">{brief.sector || ctx?.sector || '—'}</strong> · Region: <strong className="text-slate-900">{brief.geography || ctx?.country || '—'}</strong>
                </div>
              </div>

              <div className="bg-[#F5F8FC] border border-[#DDE6F0] p-4 rounded-[12px] flex items-center justify-between gap-6">
                <TrustGauge
                  score={trustScoreKnown ? trustScore : null}
                  size="md"
                  showLabel={true}
                  grade={evidenceGrade}
                  confidencePercent={confidenceKnown ? Math.round(confidence) : null}
                />
              </div>
            </div>

            {/* Reason · Evidence · Confidence · Next action, above everything else. */}
            <div className="mt-5 pt-4 border-t border-[#DDE6F0] grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 lg:gap-6">
              <div className="min-w-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-wider text-[#027A48]">Why this decision</div>
                    <p className="mt-1 text-slate-700 leading-relaxed">{decisionReason}</p>
                  </div>
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-wider text-[#004085]">Your next action</div>
                    <p className="mt-1 text-sm font-bold text-slate-900 leading-snug">{primaryNextAction}</p>
                  </div>
                </div>
                <div className="mt-3 text-[11px] text-slate-500">
                  Evidence: {sourceCount > 0 ? `${sourceCount} source${sourceCount !== 1 ? 's' : ''}` : 'no sources attached'} ·
                  {' '}<span title="A–F: integrity of the evidence base, scored on reliability, corroboration, recency and completeness">grade {evidenceGrade || 'not scored'}</span> ·
                  {' '}<span title="How firmly this evidence supports the verdict">confidence {confidenceKnown ? `${Math.round(confidence)}%` : 'not scored'}</span> ·
                  {' '}<span title="0–100: how much of this assessment rests on verifiable sources">trust score {trustScoreKnown ? `${trustScore}/100` : 'not scored'}</span>
                </div>
              </div>
              <div className="flex lg:flex-col items-center lg:items-end gap-2 text-[11px] font-bold shrink-0">
                <Link href="/evidence" className="px-3 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-slate-700 hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition">
                  Read the evidence
                </Link>
                <Link href="/reports" className="px-3 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-slate-700 hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition">
                  Generate the report
                </Link>
                <Link href="/outcomes" className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] text-white hover:bg-[#08482E] transition">
                  Record what happened
                </Link>
              </div>
            </div>
          </section>

          {/* Expanded Decision Engine — Nine Domain Scorecard (Step 7) */}
          {snapshot && snapshot.domainScores && Object.keys(snapshot.domainScores).length > 0 ? (
            <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3 pb-2 border-b border-[#DDE6F0]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#17855A]" />
                  <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">
                    Decision Engine — Domain Scorecard
                  </h2>
                </div>
                {snapshot.decisionScore != null ? (
                  <span className={`text-[10px] font-black px-2 py-1 rounded uppercase tracking-wider ${domainScoreTone(snapshot.decisionScore)}`}>
                    Decision Score {Math.round(snapshot.decisionScore)}/100
                    {snapshot.decisionBand ? ` · ${snapshot.decisionBand.replace(/_/g, ' ')}` : ''}
                  </span>
                ) : null}
              </div>

              {snapshot.decisionRationale && snapshot.decisionRationale.length > 0 ? (
                <div className="mb-3 p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Why this score</div>
                  <ul className="list-disc list-inside space-y-0.5 text-xs text-slate-700">
                    {snapshot.decisionRationale.map((line, idx) => (
                      <li key={idx}>{line}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {Object.entries(snapshot.domainScores).map(([key, dom]) => {
                  const domainScore = typeof dom.score === 'number' ? dom.score : 0
                  const weightPct = typeof dom.weight === 'number' ? Math.round(dom.weight * 100) : 0
                  const impact = typeof dom.impact === 'number' ? dom.impact : 0
                  return (
                    <div key={key} className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-extrabold text-slate-900">{dom.label}</span>
                        <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${domainScoreTone(domainScore)}`}>
                          {Math.round(domainScore)}/100
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden my-1.5">
                        <div
                          className={`h-full rounded-full ${domainScoreBar(domainScore)}`}
                          style={{ width: `${Math.max(0, Math.min(100, domainScore))}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[10px] font-semibold text-slate-500">
                        <span title="How much this domain contributes to the overall decision score.">Weight {weightPct}%</span>
                        <span
                          className={impact >= 0 ? 'text-[#027A48]' : 'text-[#B42318]'}
                          title="Points this domain added to or subtracted from the decision score."
                        >
                          Impact {impact >= 0 ? '+' : ''}{impact.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          ) : null}

          {/* 1. Executive Summary & 10. Decision Rationale */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[#DDE6F0]">
                <span className="w-2 h-2 rounded-full bg-[#0B5D3B]" />
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">1. Executive Summary</h2>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap font-medium">
                {brief.executive_summary || 'INSUFFICIENT EVIDENCE: No executive summary available.'}
              </p>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[#DDE6F0]">
                <span className="w-2 h-2 rounded-full bg-[#17855A]" />
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">10. Decision Rationale & Next Actions</h2>
              </div>
              <div className="text-xs text-slate-700 space-y-3">
                <p className="leading-relaxed font-medium">
                  {brief.investment_recommendation || (isEvidenceWeak
                    ? 'INSUFFICIENT EVIDENCE: The evidence does not meet the minimum confidence threshold for a decision of this kind.'
                    : `Based on the evidence assessed here (${trustScoreKnown ? `Trust Score ${trustScore}/100` : 'no trust score recorded yet'}), this assessment is ${recommendation ? `rated ${recommendation}` : 'still awaiting a decision'}.`
                  )}
                </p>
                {nextSteps.length > 0 ? (
                  <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                    <div className="font-bold text-slate-900 mb-1 uppercase text-[10px] tracking-wider text-slate-500">Recommended Next Actions</div>
                    <ul className="list-disc list-inside space-y-1 text-slate-700">
                      {nextSteps.map((step, idx) => (
                        <li key={idx}>{step}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          {/* 2. Key Evidence & 3. Trust Assessment */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#DDE6F0]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#004085]" />
                  <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">2. Key Evidence Used</h2>
                </div>
                <span className="text-[10px] font-bold text-slate-500">{sourceCount} traced sources</span>
              </div>
              <div className="space-y-2.5 text-xs max-h-72 overflow-y-auto pr-1">
                {sources.length === 0 && uploadedEvidence.length === 0 ? (
                  <div className="p-4 bg-[#F5F8FC] rounded text-slate-400 italic text-center">INSUFFICIENT EVIDENCE</div>
                ) : (
                  <>
                    {uploadedEvidence.map((doc, idx) => {
                      const docTrust = doc.trust_breakdown?.final_trust_score ?? doc.trust_score
                      return (
                      <div key={doc.id || idx} className="p-2.5 bg-[#EAF3FF] border border-[#D6E8FF] rounded-lg text-slate-800">
                        <div className="font-bold text-[#004085] flex items-center justify-between">
                          <span>Uploaded document: {doc.filename || doc.name}</span>
                          <span className="font-mono text-[10px]">
                            {typeof docTrust === 'number' ? `${Math.round(docTrust)}/100` : 'not scored'}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-600 mt-1">{doc.raw_summary || 'Summary not recorded for this document.'}</div>
                      </div>
                      )
                    })}
                    {sources.map((s, idx) => (
                      <div key={idx} className="p-2.5 bg-[#F5F8FC] border border-[#DDE6F0] rounded-lg text-slate-800">
                        <div className="font-bold text-slate-900 truncate">{s.title}</div>
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5 truncate">{s.url}</div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[#DDE6F0]">
                <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">3. Trust Assessment Breakdown</h2>
              </div>
              {(() => {
                // Trust factors are shown only when the assessment actually
                // produced them. No factor is ever displayed with a made-up
                // number — an unavailable factor says so.
                const tb = uploadedEvidence.find(d => d.trust_breakdown)?.trust_breakdown ?? null
                const asNum = (v: any) => (typeof v === 'number' ? v : null)
                const sourceRel = asNum(tb?.source_reliability)
                const corroboration = asNum(tb?.corroboration)
                const recency = asNum(tb?.recency)
                const completeness = asNum(tb?.completeness)
                const rationale  = tb?.rationale           ?? null
                return (
                  <>
                    <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                      {[
                        { label: 'Source Reliability (35%)', value: sourceRel },
                        { label: 'Corroboration (25%)',      value: corroboration },
                        { label: 'Recency (15%)',            value: recency },
                        { label: 'Completeness (25%)',       value: completeness },
                      ].map(({ label, value }) => (
                        <div key={label} className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                          <span className="text-[10px] font-bold text-slate-500 block">{label}</span>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-base font-black text-slate-900">
                              {value != null ? `${Math.round(value)}%` : <span className="text-[11px] font-bold text-slate-400 uppercase">Not recorded</span>}
                            </span>
                            {value != null ? (
                              <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                                <div className={`h-full rounded-full ${value >= 80 ? 'bg-[#12B76A]' : value >= 60 ? 'bg-[#F79009]' : 'bg-[#F04438]'}`}
                                  style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
                              </div>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                    {rationale ? (
                      <div className="text-[11px] text-slate-600 italic bg-[#F5F8FC] p-2.5 rounded border border-[#DDE6F0]">
                        {rationale}
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-600 italic bg-[#F5F8FC] p-2.5 rounded border border-[#DDE6F0]">
                        No factor rationale was recorded for these documents. The overall trust score above is
                        calculated from the evidence that is present.
                      </div>
                    )}
                  </>
                )
              })()}
            </div>
          </section>

          {/* WHY THIS DECISION — answers all 5 required questions */}
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[#DDE6F0]">
              <span className="w-2 h-2 rounded-full bg-[#17855A]" />
              <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">Why This Decision Was Made</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 text-xs">

              {/* Q1: What evidence exists? */}
              <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <div className="text-[10px] font-black uppercase tracking-wider text-[#004085] mb-2">What evidence exists?</div>
                {sources.length === 0 && uploadedEvidence.length === 0 ? (
                  <p className="text-slate-500 italic">No evidence sources attached.</p>
                ) : (
                  <ul className="space-y-1 text-slate-700 leading-5">
                    {uploadedEvidence.length > 0 && (
                      <li>✅ {uploadedEvidence.length} document{uploadedEvidence.length > 1 ? 's' : ''} uploaded by your team</li>
                    )}
                    {sources.length > 0 && (
                      <li>✅ {sources.length} external research source{sources.length > 1 ? 's' : ''} cross-checked</li>
                    )}
                    {ei?.integrity_grade && (
                      <li>📋 Evidence grade: <strong>{ei.integrity_grade}</strong>{typeof ei?.integrity_score === 'number' ? ` (${Math.round(ei.integrity_score)}/100)` : ' (score not recorded)'}</li>
                    )}
                    {ei?.claim_count != null && (
                      <li>🔖 {ei.claim_count} verified claim{ei.claim_count !== 1 ? 's' : ''} extracted</li>
                    )}
                  </ul>
                )}
              </div>

              {/* Q2: What evidence is missing? */}
              <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <div className="text-[10px] font-black uppercase tracking-wider text-amber-700 mb-2">What evidence is missing?</div>
                {unsupportedClaims.length === 0 && (ei?.verification_checklist?.length ?? 0) === 0 ? (
                  <p className="text-slate-500 italic">
                    {ei
                      ? 'The integrity check ran and found no missing-evidence gaps.'
                      : 'Not measured yet — evidence integrity has not been audited on this brief.'}
                  </p>
                ) : (
                  <ul className="space-y-1 text-slate-700 leading-5">
                    {unsupportedClaims.slice(0, 3).map((u, i) => (
                      <li key={i} className="text-amber-800">⚠ {u.description || String(u)}</li>
                    ))}
                    {(ei?.verification_checklist ?? []).slice(0, 2).map((item: string, i: number) => (
                      <li key={`vc${i}`} className="text-slate-600">□ {item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Q3: What signals mattered? */}
              <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <div className="text-[10px] font-black uppercase tracking-wider text-[#F79009] mb-2">What signals mattered?</div>
                {signalsGenerated.length === 0 && redFlags.length === 0 ? (
                  <p className="text-slate-500 italic">No signals generated yet.</p>
                ) : (
                  <ul className="space-y-1 text-slate-700 leading-5">
                    {signalsGenerated.slice(0, 3).map((sig, i) => (
                      <li key={i}>⚡ {sig}</li>
                    ))}
                    {redFlags.slice(0, 2).map((flag, i) => (
                      <li key={`rf${i}`} className="text-rose-700">🚩 {flag.title}: {flag.severity}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Q4: Why was this decision made? */}
              <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <div className="text-[10px] font-black uppercase tracking-wider text-[#027A48] mb-2">Why was this decision made?</div>
                <p className="text-slate-700 leading-5">
                  {brief?.investment_recommendation ||
                    (isEvidenceWeak
                      ? `The evidence here is not strong enough for a firm recommendation (${trustScoreKnown ? `trust score ${trustScore}/100` : 'no trust score recorded yet'}). Uploading the documents listed under missing evidence would raise it.`
                      : `${trustScoreKnown ? `Trust score ${trustScore}/100` : 'No trust score yet'} across ${sourceCount} source${sourceCount !== 1 ? 's' : ''} is what this assessment was built on. ${recommendation ? `Recommendation: ${recommendation}.` : 'No recommendation has been recorded yet.'}`
                    )
                  }
                </p>
              </div>

              {/* Q5: What should happen next? */}
              <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0] md:col-span-2 xl:col-span-2">
                <div className="text-[10px] font-black uppercase tracking-wider text-[#004085] mb-2">What should happen next?</div>
                {nextSteps.length > 0 ? (
                  <ol className="list-decimal list-inside space-y-1 text-slate-700 leading-5">
                    {nextSteps.map((step, i) => <li key={i}>{step}</li>)}
                  </ol>
                ) : (
                  <ul className="space-y-1 text-slate-700 leading-5">
                    {tone === 'positive' && <>
                      <li>✅ Confirm the decision and record who is accountable for it</li>
                      <li>📋 Verify the remaining evidence gaps before committing resources</li>
                      <li>📊 Export the report for your board, donor or committee</li>
                    </>}
                    {tone === 'neutral' && <>
                      <li>📅 Set a follow-up review date in Outcomes</li>
                      <li>📋 Request the corroborating documents listed under missing evidence</li>
                      <li>📊 Monitor the flagged risk signals for material change</li>
                    </>}
                    {tone === 'negative' && !isEvidenceWeak && <>
                      <li>📝 Record the rationale and what would change it</li>
                      <li>📤 Share the feedback memo with the team or partner</li>
                    </>}
                    {tone === 'negative' && isEvidenceWeak && <>
                      <li>📋 Upload the evidence still missing from this assessment</li>
                      <li>🔍 Re-run the research with broader keywords</li>
                      <li>📊 Work through the evidence checklist before deciding</li>
                    </>}
                  </ul>
                )}
              </div>
            </div>
          </section>

          {/* 4. Signals Detected, 5. Contradictions & 6. Missing Evidence */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[#DDE6F0]">
                <span className="w-2 h-2 rounded-full bg-[#F79009]" />
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">4. Signals Detected</h2>
              </div>
              <div className="space-y-2 text-xs">
                {signalsGenerated.length === 0 ? (
                  <div className="p-3 bg-[#F5F8FC] rounded text-slate-400 italic">No signals were recorded for this run.</div>
                ) : signalsGenerated.slice(0, 5).map((sig, idx) => (
                  <div key={idx} className="p-2.5 bg-[#FFFAEB] border border-[#FEDF89] rounded-lg text-slate-800 font-medium">
                    ⚡ {sig}
                  </div>
                ))}
              </div>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[#DDE6F0]">
                <span className="w-2 h-2 rounded-full bg-[#F04438]" />
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">5. Contradictions Found</h2>
              </div>
              <div className="space-y-2 text-xs">
                {contradictions.length === 0 ? (
                  <div className="p-3 bg-[#F5F8FC] rounded text-slate-500 font-medium">
                    {ei
                      ? '✓ The integrity check ran and found no conflicting claims between sources.'
                      : 'Evidence integrity has not been audited on this brief yet, so there is no contradiction check to report.'}
                  </div>
                ) : contradictions.map((c, idx) => (
                  <div key={idx} className="p-2.5 bg-[#FEF3F2] border border-[#FECDCA] rounded-lg text-slate-800">
                    <strong className="text-[#B42318] block">
                      {[c.severity, c.description || 'Contradiction between sources'].filter(Boolean).join(': ')}
                    </strong>
                    <span className="text-[11px] text-slate-600 mt-0.5 block">
                      {c.recommended_action || 'No specific action was recorded for this conflict — verify which source is correct, then re-run the assessment.'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[#DDE6F0]">
                <span className="w-2 h-2 rounded-full bg-slate-400" />
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">6. Missing Evidence</h2>
              </div>
              <div className="space-y-2 text-xs">
                {unsupportedClaims.length === 0 ? (
                  <div className="p-3 bg-[#F5F8FC] rounded text-slate-500 font-medium">
                    {ei
                      ? 'Every claim that was checked has supporting evidence attached.'
                      : 'Evidence integrity has not been audited on this brief yet, so no claim-by-claim gap list exists.'}
                  </div>
                ) : unsupportedClaims.map((u, idx) => (
                  <div key={idx} className="p-2.5 bg-[#F5F8FC] border border-[#DDE6F0] rounded-lg text-slate-800">
                    <strong className="text-slate-900 block">{u.description || String(u)}</strong>
                    <span className="text-[11px] text-slate-500 mt-0.5 block">
                      {u.recommended_action || 'No specific action was recorded for this gap — obtain a source that supports this claim, then re-run the assessment.'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* 7. Risks & 8. Opportunities */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#DDE6F0]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#F04438]" />
                  <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">7. Key Risks & Red Flags</h2>
                </div>
                <span className="text-[10px] font-bold text-rose-600">{redFlags.length} Identified</span>
              </div>
              <div className="space-y-2 text-xs">
                {redFlags.length === 0 ? (
                  <div className="p-3 bg-[#F5F8FC] rounded text-slate-500 font-medium">No red flags were recorded against the evidence reviewed.</div>
                ) : redFlags.map((flag, idx) => (
                  <div key={idx} className="p-3 bg-[#FEF3F2] border border-[#FECDCA] rounded-lg">
                    <div className="font-bold text-[#B42318]">{flag.severity?.toUpperCase()} · {flag.title}</div>
                    <p className="text-slate-700 mt-1 text-[11px] leading-relaxed">{flag.detail}</p>
                    {flag.mitigation ? (
                      <div className="mt-1.5 pt-1.5 border-t border-rose-200 text-[10px] text-slate-600">
                        Mitigation: <strong className="text-slate-900">{flag.mitigation}</strong>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#DDE6F0]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
                  <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">8. Opportunities To Act On</h2>
                </div>
                <span className="text-[10px] font-bold text-[#027A48]">What the evidence supports</span>
              </div>
              <div className="space-y-2 text-xs">
                {opportunities.length === 0 ? (
                  <div className="p-3 bg-[#F5F8FC] rounded text-slate-500 font-medium">No opportunities were synthesised from this evidence.</div>
                ) : opportunities.map((opp, idx) => (
                  <div key={idx} className="p-3 bg-[#ECFDF3] border border-[#A6F4C5] rounded-lg">
                    <div className="font-bold text-[#027A48]">Opportunity #{idx + 1}</div>
                    <p className="text-slate-700 mt-1 text-[11px] leading-relaxed">{opp}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      ) : (!ctxLoading && !ctxError ? (
        <div className="p-8 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-center">
          <div className="text-sm font-bold text-slate-700">No decision dossier generated yet</div>
          <div className="text-xs text-slate-500 mt-1">
            The intelligence run is either still processing or has not completed. Check the Research tab for pipeline status.
          </div>
          <Link href="/research" className="mt-4 inline-block px-4 py-2 rounded-lg bg-[#0B5D3B] text-white text-xs font-bold hover:bg-[#08482E] transition">
            View Research Status
          </Link>
        </div>
      ) : null)}
    </PilotWorkspaceShell>
  )
}
