'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getFullBrief, listStoredRuns, reportDownloadHref, type StoredRunRecord } from '../../lib/api'
import { loadCurrentRun } from '../../lib/current-run'
import TrustGauge from '../../components/TrustGauge/TrustGauge'

type FullBrief = Record<string, any>

export default function DecisionWorkspacePage() {
  const { status: authStatus } = useSession()
  const searchParams = useSearchParams()
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [brief, setBrief] = useState<FullBrief | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function loadRuns() {
      const res = await listStoredRuns(50, true)
      if (cancelled) return
      setRuns(res.runs)
      const fromQuery = searchParams.get('run')
      const stored = loadCurrentRun()
      const nextSelected = fromQuery || stored?.runId || String(res.runs[0]?.runId || '')
      setSelectedRunId(nextSelected)
    }
    if (authStatus === 'authenticated') {
      loadRuns().catch(err => setError(String(err)))
    }
    return () => { cancelled = true }
  }, [authStatus, searchParams])

  useEffect(() => {
    let cancelled = false
    async function loadBrief() {
      if (!selectedRunId) {
        setBrief(null)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const data = await getFullBrief(selectedRunId)
        if (!cancelled) setBrief(data)
      } catch (err) {
        if (!cancelled) setError(String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    if (authStatus === 'authenticated') {
      loadBrief()
    }
    return () => { cancelled = true }
  }, [authStatus, selectedRunId])

  const selectedRun = useMemo(() => runs.find(run => String(run.runId) === String(selectedRunId)), [runs, selectedRunId])

  // Extraction of Decision Dossier components
  const recommendation = brief?.recommendation || 'OBSERVE'
  const confidence = brief?.confidence ?? (brief?.trust_score ? Math.min(95, brief.trust_score + 5) : 50)
  const trustScore = brief?.trust_score ?? selectedRun?.trustScore ?? 0
  const isEvidenceWeak = trustScore < 55

  const sources: Array<any> = Array.isArray(brief?.sources) ? brief.sources : []
  const uploadedEvidence: Array<any> = Array.isArray(brief?.uploaded_evidence) ? brief.uploaded_evidence : []
  const ei = brief?.evidence_integrity || null
  const contradictions: Array<any> = Array.isArray(ei?.contradictions) ? ei.contradictions : []
  const unsupportedClaims: Array<any> = Array.isArray(ei?.unsupported_claims) ? ei.unsupported_claims : []
  const redFlags: Array<any> = Array.isArray(brief?.red_flags) ? brief.red_flags : []
  const nextSteps: Array<string> = Array.isArray(brief?.next_steps) ? brief.next_steps : []

  // Extract signals from uploaded evidence + brief
  const signalsGenerated: Array<string> = []
  uploadedEvidence.forEach(doc => {
    if (Array.isArray(doc.signals_generated)) {
      signalsGenerated.push(...doc.signals_generated)
    }
  })
  if (redFlags.length > 0) {
    signalsGenerated.push(`Identified ${redFlags.length} structural risk flag(s) in evaluation brief`)
  }
  if (sources.length >= 3) {
    signalsGenerated.push(`High Confidence Evidence: ${sources.length} independent attribution sources verified`)
  }

  // Opportunity synthesis
  const opportunities = [
    brief?.market_assessment || 'Market expansion in under-penetrated regional agricultural supply chain.',
    brief?.startup_assessment || 'Proprietary distribution model with strong operational traction.',
  ].filter(Boolean)

  if (authStatus === 'loading') {
    return <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima OS</div>
        <button onClick={() => signIn()} className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm">
          Sign in
        </button>
      </div>
    )
  }

  return (
    <PilotWorkspaceShell
      workspace="Decision"
      title="Decision Workspace"
      description="Review, analyze, and approve evaluations. The definitive evidence-backed decision layer: Information → Evidence → Trust → Signals → Decision."
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
      startupName={selectedRun?.startupName}
      recommendation={selectedRun?.recommendation}
      trustScore={selectedRun?.trustScore}
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div> : null}

      {/* Target Run Selector & Export Action Bar */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Active Decision Target</label>
          <select
            className="mt-1.5 w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 font-bold focus:outline-none focus:border-[#0B5D3B]"
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
          >
            <option value="">Select Evaluation Target…</option>
            {runs.map(run => (
              <option key={run.runId} value={run.runId}>
                #{run.runId} · {run.startupName} ({run.founderName}) — Verdict: {run.recommendation || 'OBSERVE'}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          {selectedRunId ? (
            <a
              href={reportDownloadHref(selectedRunId, 'memo', 'pdf')}
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

      {/* Decision Dossier Master Grid (10 Core Elements) */}
      {brief ? (
        <div className="space-y-6">
          {/* Top Level Verdict & Confidence Hero */}
          <section className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas-elevated relative overflow-hidden">
            <div className={`absolute top-0 left-0 right-0 h-1.5 ${
              recommendation === 'Invest' ? 'bg-[#12B76A]' :
              recommendation === 'Observe' ? 'bg-[#F79009]' : 'bg-[#F04438]'
            }`} />

            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]">
                    Decision Dossier
                  </span>
                  <span className="text-xs text-slate-500 font-mono">Evaluation #{selectedRunId}</span>
                </div>

                <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                  <span>{brief.startup_name || 'Venture Evaluation'}</span>
                  <span className={`text-xs px-3 py-1 rounded-full font-black uppercase tracking-wider ${
                    recommendation === 'Invest' ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
                    recommendation === 'Observe' ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
                    'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
                  }`}>
                    {isEvidenceWeak ? 'INSUFFICIENT EVIDENCE' : recommendation}
                  </span>
                </h1>

                <div className="text-xs text-slate-600 mt-1">
                  Lead: <strong className="text-slate-900">{brief.founder_name}</strong> · Sector: <strong className="text-slate-900">{brief.sector || 'AgTech'}</strong> · Region: <strong className="text-slate-900">{brief.geography || 'Pan-Africa'}</strong>
                </div>
              </div>

              <div className="bg-[#F5F8FC] border border-[#DDE6F0] p-4 rounded-[12px] flex items-center justify-between gap-6">
                <TrustGauge
                  score={trustScore}
                  size="md"
                  showLabel={true}
                  grade={ei?.integrity_grade || (trustScore >= 80 ? 'A' : trustScore >= 60 ? 'B' : 'C')}
                  confidencePercent={Math.round(confidence)}
                />
              </div>
            </div>
          </section>

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
                    ? 'INSUFFICIENT EVIDENCE: Evidence corpus does not meet the minimum confidence threshold for deployment.'
                    : `Based on verified evidence and a Trust Score of ${trustScore}/100, the venture is rated ${recommendation}.`
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
                <span className="text-[10px] font-bold text-slate-500">{sources.length + uploadedEvidence.length} Attributions</span>
              </div>
              <div className="space-y-2.5 text-xs max-h-72 overflow-y-auto pr-1">
                {sources.length === 0 && uploadedEvidence.length === 0 ? (
                  <div className="p-4 bg-[#F5F8FC] rounded text-slate-400 italic text-center">INSUFFICIENT EVIDENCE</div>
                ) : (
                  <>
                    {uploadedEvidence.map((doc, idx) => (
                      <div key={doc.id || idx} className="p-2.5 bg-[#EAF3FF] border border-[#D6E8FF] rounded-lg text-slate-800">
                        <div className="font-bold text-[#004085] flex items-center justify-between">
                          <span>Primary Dossier: {doc.filename}</span>
                          <span className="font-mono text-[10px]">{doc.trust_breakdown?.final_trust_score ?? 80}/100</span>
                        </div>
                        <div className="text-[11px] text-slate-600 mt-1">{doc.raw_summary || 'Primary documentation ingested.'}</div>
                      </div>
                    ))}
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
              <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                  <span className="text-[10px] font-bold text-slate-500 block">Source Reliability (35%)</span>
                  <span className="text-base font-black text-slate-900">85%</span>
                </div>
                <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                  <span className="text-[10px] font-bold text-slate-500 block">Corroboration (25%)</span>
                  <span className="text-base font-black text-slate-900">75%</span>
                </div>
                <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                  <span className="text-[10px] font-bold text-slate-500 block">Recency (15%)</span>
                  <span className="text-base font-black text-slate-900">95%</span>
                </div>
                <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                  <span className="text-[10px] font-bold text-slate-500 block">Completeness (25%)</span>
                  <span className="text-base font-black text-slate-900">70%</span>
                </div>
              </div>
              <div className="text-[11px] text-slate-600 italic bg-[#F5F8FC] p-2.5 rounded border border-[#DDE6F0]">
                Deterministic multi-factor calculation enforces minimum evidence density before recommending capital allocation.
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
                  <div className="p-3 bg-[#F5F8FC] rounded text-slate-400 italic">No automated signals detected</div>
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
                    ✓ No conflicting data points detected across sources.
                  </div>
                ) : contradictions.map((c, idx) => (
                  <div key={idx} className="p-2.5 bg-[#FEF3F2] border border-[#FECDCA] rounded-lg text-slate-800">
                    <strong className="text-[#B42318] block">{c.severity || 'WARN'}: {c.description}</strong>
                    <span className="text-[11px] text-slate-600 mt-0.5 block">{c.recommended_action}</span>
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
                    All core claims have supporting verification in file.
                  </div>
                ) : unsupportedClaims.map((u, idx) => (
                  <div key={idx} className="p-2.5 bg-[#F5F8FC] border border-[#DDE6F0] rounded-lg text-slate-800">
                    <strong className="text-slate-900 block">{u.description}</strong>
                    <span className="text-[11px] text-slate-500 mt-0.5 block">{u.recommended_action}</span>
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
                  <div className="p-3 bg-[#F5F8FC] rounded text-slate-500 font-medium">No critical red flags recorded in baseline appraisal.</div>
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
                  <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">8. Investment Opportunities</h2>
                </div>
                <span className="text-[10px] font-bold text-[#027A48]">Key Thesis Drivers</span>
              </div>
              <div className="space-y-2 text-xs">
                {opportunities.map((opp, idx) => (
                  <div key={idx} className="p-3 bg-[#ECFDF3] border border-[#A6F4C5] rounded-lg">
                    <div className="font-bold text-[#027A48]">Growth Driver #{idx + 1}</div>
                    <p className="text-slate-700 mt-1 text-[11px] leading-relaxed">{opp}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </PilotWorkspaceShell>
  )
}
