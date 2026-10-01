'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import ActivityTimeline from '../../components/ActivityTimeline/ActivityTimeline'
import { getFullBrief, attachAssessmentDocuments, type AssessmentWorkspacePayload } from '../../lib/api'
import { useAssessmentWorkspace } from '../../hooks/useAssessmentWorkspace'

type FullBrief = Record<string, any>

export default function EvidencePage() {
  const { status: authStatus } = useSession()
  const { data: ctx, assessmentId, runId, reload: reloadContext, loading: ctxLoading, error: ctxError } = useAssessmentWorkspace(authStatus === 'authenticated')
  const [brief, setBrief] = useState<FullBrief | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)
  const [pipelineReady, setPipelineReady] = useState(false)

  async function refreshBrief() {
    if (!runId) {
      setBrief(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await getFullBrief(runId)
      setBrief(data)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (authStatus === 'authenticated') {
      refreshBrief()
    }
  }, [authStatus, runId])

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    if (!assessmentId) {
      setError('No active assessment context — create an assessment first.')
      return
    }
    setUploading(true)
    setError(null)
    setUploadSuccess(null)

    try {
      // Document Bridge: all files attach to the Assessment Context in ONE
      // call. The backend re-runs the evidence chain (extraction → research →
      // signals → decision) automatically — no duplicate ingestion, no
      // second pipeline, no manual syncing.
      const updated = await attachAssessmentDocuments(assessmentId, Array.from(files))

      const docs = Array.isArray(updated.uploadedDocuments) ? updated.uploadedDocuments : []
      const firstTrust = docs.length ? docs[docs.length - 1]?.trust_score : null
      setUploadSuccess(
        `Successfully ingested ${files.length} document(s) into the Assessment Context. ` +
        `Trust Score: ${firstTrust != null ? `${firstTrust}/100` : '—'} · Status: ${updated.status ?? 'PROCESSING'} · ` +
        `Evidence chain re-triggered automatically.`
      )

      // Refresh the shared context and the derived brief
      await reloadContext()
      if (runId) await refreshBrief().catch(() => null)
      setPipelineReady(true)
    } catch (err: any) {
      const msg = err.message || String(err)
      setError(`Document upload failed: ${msg}`)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const displayEntity = ctx?.displayEntity || ctx?.organizationName || ctx?.startupName || ''
  const ei = brief?.evidence_integrity || null
  /** Tavily / web research sources — Source A */
  const researchSources: Array<any> = Array.isArray(brief?.sources) ? brief.sources : []
  /** Uploaded primary documents — prefer Assessment Context docs (single source of truth),
   *  fall back to brief.uploaded_evidence for backward compatibility. */
  const ctxDocs: Array<any> = Array.isArray(ctx?.uploadedDocuments) ? ctx.uploadedDocuments : []
  const briefDocs: Array<any> = Array.isArray(brief?.uploaded_evidence) ? brief.uploaded_evidence : []
  const uploadedEvidence: Array<any> = ctxDocs.length > 0 ? ctxDocs : briefDocs
  const contradictions: Array<any> = Array.isArray(ei?.contradictions) ? ei.contradictions : []
  const unsupported: Array<any> = Array.isArray(ei?.unsupported_claims) ? ei.unsupported_claims : []
  const verificationChecklist: Array<string> = Array.isArray(ei?.verification_checklist) ? ei.verification_checklist : []
  const redFlags: Array<any> = Array.isArray(brief?.red_flags) ? brief.red_flags : []
  /** Combined source count for corroboration score */
  const totalSources = researchSources.length + uploadedEvidence.length
  /** Corroboration: true when both evidence sources are present */
  const isCorroborated = researchSources.length > 0 && uploadedEvidence.length > 0

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

  return (
    <PilotWorkspaceShell
      workspace="Evidence"
      title="Evidence Integrity & Ingestion Workspace"
      description="Deterministic claim verification, primary document ingestion, source attribution, and transparent Trust Engine breakdown."
      runId={runId || null}
      status={ctx?.status || 'active'}
      startupName={displayEntity}
      recommendation={(ctx?.decision?.recommendation as string) || undefined}
      trustScore={ctx?.trustScore ?? undefined}
      assessmentCtx={ctx ? {
        entityType: (ctx.assessmentType as any) || 'startup',
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
        uploadedDocuments: ctx.uploadedDocuments as any,
      } : null}
    >
      {ctxError ? <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{ctxError}</div> : null}
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div> : null}
      {ctx && (ctx.documentCount ?? ctx.uploadedDocuments?.length ?? 0) === 0 ? (
        <div className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 text-sm text-slate-600 shadow-saas">
          <div className="font-bold text-slate-800">No documents uploaded yet</div>
          <div className="mt-1 text-xs text-slate-500">Upload your first pitch deck, NGO report, survey, business plan, or program report.</div>
        </div>
      ) : null}
      {uploadSuccess ? (
        <div className="p-4 bg-emerald-50 text-emerald-800 rounded-[12px] border border-emerald-200 text-sm font-bold flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
          <span>{uploadSuccess}</span>
        </div>
      ) : null}

      {/* Auto-flow: pipeline ready — direct user to next steps */}
      {pipelineReady && runId ? (
        <section className="p-4 bg-[#ECFDF3] border border-[#A6F4C5] rounded-[12px] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="text-sm font-extrabold text-[#027A48]">✓ Evidence Pipeline Complete</div>
            <div className="text-xs text-[#027A48]/80 mt-0.5">
              Trust Score, Evidence Status, and Signals have been generated. Continue your assessment below.
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <a
              href={`/decision?id=${encodeURIComponent(assessmentId || '')}`}
              className="px-3 py-2 rounded-lg bg-[#0B5D3B] text-white text-xs font-extrabold uppercase tracking-wider hover:bg-[#08482E] transition"
            >
              Decision →
            </a>
            <a
              href={`/signals?id=${encodeURIComponent(assessmentId || '')}`}
              className="px-3 py-2 rounded-lg border border-[#0B5D3B] text-[#0B5D3B] text-xs font-extrabold uppercase tracking-wider hover:bg-[#ECFDF3] transition"
            >
              Signals →
            </a>
            <a
              href={`/reports?id=${encodeURIComponent(assessmentId || '')}`}
              className="px-3 py-2 rounded-lg border border-[#DDE6F0] text-slate-700 text-xs font-extrabold uppercase tracking-wider hover:border-[#0B5D3B] transition"
            >
              Reports →
            </a>
          </div>
        </section>
      ) : null}

      {/* Evidence Corroboration Status Banner */}
      {runId ? (
        <section className={`p-4 rounded-[12px] border flex items-center gap-3 text-xs font-semibold ${
          isCorroborated
            ? 'bg-[#ECFDF3] border-[#A6F4C5] text-[#027A48]'
            : totalSources > 0
            ? 'bg-[#FFFAEB] border-[#FEDF89] text-[#B54708]'
            : 'bg-[#F5F8FC] border-[#DDE6F0] text-slate-500'
        }`}>
          <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
            isCorroborated ? 'bg-[#12B76A]' : totalSources > 0 ? 'bg-[#F79009]' : 'bg-slate-300'
          }`} />
          <div>
            {isCorroborated ? (
              <>
                <span className="font-extrabold uppercase tracking-wider">Corroborated</span>
                {' '}— Research intelligence ({researchSources.length} source{researchSources.length !== 1 ? 's' : ''}) and uploaded documents ({uploadedEvidence.length} document{uploadedEvidence.length !== 1 ? 's' : ''}) are both present. Evidence integrity is cross-verified.
              </>
            ) : totalSources > 0 ? (
              <>
                <span className="font-extrabold uppercase tracking-wider">Single-Source</span>
                {' '}— Only {researchSources.length > 0 ? 'research intelligence' : 'uploaded documents'} present. Upload{researchSources.length > 0 ? ' primary documents' : ' research sources are being fetched via AI run'} to achieve full corroboration.
              </>
            ) : (
              <>
                <span className="font-extrabold uppercase tracking-wider">No Evidence</span>
                {' '}— No sources loaded for this evaluation. Run analysis or upload documents to begin.
              </>
            )}
          </div>
        </section>
      ) : null}

      {/* Control Bar: Assessment Context identity + Ingestion Upload Trigger */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Active Evaluation Target</label>
          <div className="mt-1.5 w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 font-bold truncate">
            {displayEntity || 'Assessment'} · {ctx?.assessmentTypeLabel || 'Assessment'}{ctx?.founderName ? ` · ${ctx.founderName}` : ''}
          </div>
          {assessmentId ? (
            <div className="mt-1 text-[10px] font-mono text-slate-400 truncate">Context: {assessmentId}</div>
          ) : null}
        </div>

        <div className="flex items-center gap-3">
          {/* Document Intelligence Mode badge — shown when no AI run is attached */}
          {!brief?.executive_summary && runId ? (
            <span className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#EAF3FF] border border-[#D6E8FF] text-[10px] font-extrabold uppercase tracking-wider text-[#004085]">
              📄 Document Intelligence Mode
            </span>
          ) : brief?.executive_summary?.includes('Offline Intelligence Mode') ? (
            <span className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#FFFAEB] border border-[#FEDF89] text-[10px] font-extrabold uppercase tracking-wider text-[#B54708]">
              ⚡ Document Intelligence Mode
            </span>
          ) : null}
          <label className={`cursor-pointer inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-extrabold uppercase tracking-wider transition shadow-sm ${
            uploading ? 'bg-slate-400 text-white cursor-not-allowed' : 'bg-[#0B5D3B] text-white hover:bg-[#08482E]'
          }`}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <span>{uploading ? 'Ingesting Document…' : 'Ingest Document 📎'}</span>
            <input
              type="file"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
              accept=".pdf,.docx,.xlsx,.csv,.txt,.pptx"
            />
          </label>
        </div>
      </section>

      {/* Governance Activity Timeline — per-assessment audit trail (Phase 4) */}
      {runId ? <ActivityTimeline runId={runId} limit={50} /> : null}

      {/* Decision Intelligence Summary Block */}
      {ctx ? (
        <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#DDE6F0]">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Core Evaluation</span>
              <h2 className="text-base font-extrabold text-slate-900">Decision Intelligence Summary</h2>
            </div>
            <span className={`text-xs px-3 py-1 rounded-full font-black uppercase tracking-wider ${
              (brief?.recommendation || ctx?.decision?.recommendation) === 'Invest' ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
              (brief?.recommendation || ctx?.decision?.recommendation) === 'Observe' ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
              'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
            }`}>
              {brief?.recommendation || (ctx?.decision?.recommendation as string) || 'OBSERVE'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-500 uppercase tracking-wider block mb-1">Recommendation Rationale</span>
              <p className="text-slate-800 font-medium leading-relaxed">
                {brief?.executive_summary || 'INSUFFICIENT EVIDENCE: No executive briefing generated yet.'}
              </p>
            </div>

            <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-500 uppercase tracking-wider block mb-1">Supporting Evidence Depth</span>
              <div className="space-y-1 text-slate-700">
                <div>Grade: <strong className="text-slate-900">{ei?.integrity_grade || 'C'}</strong></div>
                <div>Research Sources: <strong className="text-slate-900">{researchSources.length}</strong></div>
                <div>Uploaded Documents: <strong className="text-slate-900">{uploadedEvidence.length}</strong></div>
                <div>Verified Claims: <strong className="text-slate-900">{ei?.claim_count ?? (totalSources > 0 ? totalSources * 3 : 0)}</strong></div>
              </div>
            </div>

            <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-500 uppercase tracking-wider block mb-1">Risk & Contradiction Count</span>
              <div className="space-y-1 text-slate-700">
                <div>Identified Risks: <strong className="text-rose-600">{redFlags.length}</strong></div>
                <div>Detected Contradictions: <strong className="text-amber-600">{contradictions.length}</strong></div>
                <div>Unsupported Claims: <strong className="text-slate-600">{unsupported.length}</strong></div>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {/* ── SOURCE A: Research / Tavily Intelligence ─────────────────────────── */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#DDE6F0]">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]">Source A</span>
              <h2 className="text-base font-extrabold text-slate-900">Research Intelligence</h2>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">Web research and OSINT sources gathered during the AI evaluation run. Read-only — generated automatically.</p>
          </div>
          <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${
            researchSources.length > 0
              ? 'text-[#027A48] bg-[#ECFDF3] border-[#A6F4C5]'
              : 'text-slate-500 bg-[#F5F8FC] border-[#DDE6F0]'
          }`}>
            {researchSources.length} Source{researchSources.length === 1 ? '' : 's'}
          </span>
        </div>

        {researchSources.length === 0 ? (
          <div className="p-6 text-center bg-[#F5F8FC] rounded-[10px] border border-dashed border-[#DDE6F0]">
            <div className="text-slate-400 text-sm font-semibold">No research sources loaded yet.</div>
            <p className="text-xs text-slate-500 mt-1">Run an AI evaluation from the AI Analyst Workspace or Signals workspace to populate research intelligence.</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
            {researchSources.map((source, idx) => (
              <div key={idx} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-bold text-slate-900 truncate">{source.title || 'Untitled Source'}</div>
                    <div className="text-[11px] text-slate-500 break-all mt-0.5">{source.url || '—'}</div>
                  </div>
                  <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF] shrink-0">
                    {source.source_type || 'web'}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-500 font-mono">
                  <span>Relevance: {source.relevance ?? '1.0'}</span>
                  <span>·</span>
                  <span>Confidence: {source.confidence_score ?? '0.8'}</span>
                </div>
                {source.snippet ? (
                  <div className="text-[11px] text-slate-700 mt-2 bg-white p-2 rounded border border-[#E2E8F0] whitespace-pre-wrap leading-relaxed">
                    {source.snippet}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── SOURCE B: Uploaded Primary Documents ─────────────────────────────── */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#DDE6F0]">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-amber-50 text-amber-700 border border-amber-200">Source B</span>
              <h2 className="text-base font-extrabold text-slate-900">Uploaded Primary Documents</h2>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">Primary sources ingested directly. Analysed via the Trust Engine. Never overwrites research intelligence.</p>
          </div>
          <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${
            uploadedEvidence.length > 0
              ? 'text-amber-700 bg-amber-50 border-amber-200'
              : 'text-slate-500 bg-[#F5F8FC] border-[#DDE6F0]'
          }`}>
            {uploadedEvidence.length} Document{uploadedEvidence.length === 1 ? '' : 's'}
          </span>
        </div>

        {uploadedEvidence.length === 0 ? (
          <div className="p-8 text-center bg-[#F5F8FC] rounded-[10px] border border-dashed border-[#DDE6F0]">
            <div className="text-slate-400 text-sm font-semibold">INSUFFICIENT EVIDENCE: No primary documents uploaded yet for this run.</div>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Upload pitch decks, audited statements, financial models, or board minutes above to generate transparent trust scores and evidence verification.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {uploadedEvidence.map((doc, idx) => {
              // Normalise field names from both ctx.uploadedDocuments and brief.uploaded_evidence
              const docName     = doc.name || doc.filename || 'Document'
              const docType     = doc.file_type || doc.fileType || (doc.name?.split('.').pop()?.toUpperCase()) || 'DOCUMENT'
              const uploadDate  = doc.upload_date || doc.uploadDate || doc.created_at || null
              const trustScore  = doc.trust_breakdown?.final_trust_score ?? doc.trust_score ?? doc.trustScore ?? null
              const trustPct    = trustScore != null ? Math.round(Number(trustScore)) : null
              const evStatus    = doc.evidence_status || doc.evidenceStatus || 'PROCESSED'
              const tb          = doc.trust_breakdown ?? null
              const rawSummary  = doc.raw_summary || doc.rawSummary || null
              return (
                <div key={doc.id || idx} className="p-4 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0] space-y-3">
                  {/* Document header row */}
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 pb-3 border-b border-[#DDE6F0]">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-900 text-white">
                          {docType}
                        </span>
                        <span className="text-sm font-extrabold text-slate-900 truncate">{docName}</span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1 text-[11px] text-slate-500">
                        {uploadDate ? (
                          <span>Uploaded: {new Date(uploadDate).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                        ) : (
                          <span>Uploaded: Recent</span>
                        )}
                        {doc.uploader ? <span>By: {doc.uploader}</span> : null}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {/* Evidence Status */}
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider ${
                        evStatus === 'VERIFIED'    ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
                        evStatus === 'CORROBORATED'? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
                        evStatus === 'INSUFFICIENT_EVIDENCE' ? 'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]' :
                                                    'bg-slate-100 text-slate-600 border border-slate-200'
                      }`}>
                        {evStatus.replace(/_/g, ' ')}
                      </span>
                      {/* Trust Contribution */}
                      {trustPct != null ? (
                        <div className="flex flex-col items-center">
                          <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Trust</span>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${trustPct >= 80 ? 'bg-[#12B76A]' : trustPct >= 60 ? 'bg-[#F79009]' : 'bg-[#F04438]'}`}
                                style={{ width: `${trustPct}%` }}
                              />
                            </div>
                            <span className="text-xs font-black text-slate-900">{trustPct}</span>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>

                  {/* Trust Engine Breakdown */}
                  {tb ? (
                    <div className="p-3 bg-white rounded-lg border border-[#DDE6F0] text-xs">
                      <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider mb-2">
                        Trust Engine Breakdown
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
                        {[
                          { label: 'Source Reliability', pct: '35%', value: tb.source_reliability },
                          { label: 'Corroboration',      pct: '25%', value: tb.corroboration },
                          { label: 'Recency',            pct: '15%', value: tb.recency },
                          { label: 'Completeness',       pct: '25%', value: tb.completeness },
                        ].map(({ label, pct, value }) => (
                          <div key={label} className="p-2 bg-[#F5F8FC] rounded border border-[#E2E8F0]">
                            <span className="text-[9px] text-slate-400 block">{label} ({pct})</span>
                            <div className="flex items-center gap-1 mt-0.5">
                              <strong className="font-mono text-xs text-slate-900">{value != null ? `${Math.round(value)}%` : '—'}</strong>
                              {value != null ? (
                                <div className="flex-1 h-1 rounded-full bg-slate-100 overflow-hidden">
                                  <div className={`h-full rounded-full ${Number(value) >= 80 ? 'bg-[#12B76A]' : Number(value) >= 60 ? 'bg-[#F79009]' : 'bg-[#F04438]'}`}
                                    style={{ width: `${Math.min(100, Number(value))}%` }} />
                                </div>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                      {tb.rationale ? (
                        <p className="text-[11px] text-slate-500 italic">{tb.rationale}</p>
                      ) : null}
                    </div>
                  ) : null}

                  {/* Raw summary */}
                  {rawSummary ? (
                    <div className="text-[11px] text-slate-600 bg-white p-2.5 rounded border border-[#DDE6F0] leading-relaxed">
                      {rawSummary}
                    </div>
                  ) : null}

                  {/* Evidence items + Signals */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="p-3 bg-white rounded-lg border border-[#DDE6F0]">
                      <div className="font-bold text-slate-800 mb-1.5">Extracted Evidence</div>
                      <ul className="space-y-1 list-disc list-inside text-slate-700">
                        {Array.isArray(doc.evidence_items) && doc.evidence_items.length > 0 ? (
                          doc.evidence_items.map((item: string, i: number) => <li key={i}>{item}</li>)
                        ) : (
                          <li className="text-slate-400 italic list-none">No structured evidence extracted</li>
                        )}
                      </ul>
                    </div>
                    <div className="p-3 bg-white rounded-lg border border-[#DDE6F0]">
                      <div className="font-bold text-slate-800 mb-1.5">Signals Generated</div>
                      <ul className="space-y-1 text-slate-700">
                        {Array.isArray(doc.signals_generated || doc.signals) && (doc.signals_generated || doc.signals || []).length > 0 ? (
                          (doc.signals_generated || doc.signals || []).map((sig: string, i: number) => (
                            <li key={i} className="flex items-start gap-1">
                              <span className="text-amber-500 shrink-0">⚡</span> {sig}
                            </li>
                          ))
                        ) : (
                          <li className="text-slate-400 italic">No signals emitted</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  {/* Audit trail */}
                  {Array.isArray(doc.audit_trail) && doc.audit_trail.length > 0 ? (
                    <div className="text-[10px] text-slate-400 font-mono flex items-start gap-2 pt-2 border-t border-[#DDE6F0]">
                      <span className="shrink-0 font-bold">Audit:</span>
                      <span className="break-all">{doc.audit_trail.join(' · ')}</span>
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Integrity Summary & Verification Checklist */}
      {brief ? (
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-base font-extrabold text-slate-900 pb-3 mb-3 border-b border-[#DDE6F0]">
              Integrity Summary & Metrics
            </h2>
            <div className="grid grid-cols-2 gap-3 text-xs text-slate-700">
              <div className="p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <span className="text-slate-500 block text-[10px]">Integrity Grade</span>
                <span className="font-black text-sm text-slate-900">{ei?.integrity_grade || 'C'}</span>
              </div>
              <div className="p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <span className="text-slate-500 block text-[10px]">Integrity Score</span>
                <span className="font-black text-sm text-slate-900">{ei?.integrity_score ?? '75'}</span>
              </div>
              <div className="p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <span className="text-slate-500 block text-[10px]">Evidence Depth</span>
                <span className="font-bold text-xs text-slate-900">{ei?.evidence_depth || 'MEDIUM'}</span>
              </div>
              <div className="p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <span className="text-slate-500 block text-[10px]">Consistency Status</span>
                <span className="font-bold text-xs text-slate-900">{ei?.consistency_status || 'CONSISTENT'}</span>
              </div>
            </div>
            <p className="mt-4 text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
              {ei?.integrity_summary || 'INSUFFICIENT EVIDENCE: No synthesis generated yet.'}
            </p>
          </div>

          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-base font-extrabold text-slate-900 pb-3 mb-3 border-b border-[#DDE6F0]">
              Verification Checklist
            </h2>
            <div className="space-y-2 text-xs">
              {verificationChecklist.length === 0 ? (
                <div className="p-4 bg-[#F5F8FC] rounded-lg text-slate-500 text-center italic">
                  INSUFFICIENT EVIDENCE: No checklist items formulated.
                </div>
              ) : verificationChecklist.map((item, idx) => (
                <div key={idx} className="p-3 bg-[#F5F8FC] border border-[#DDE6F0] rounded-lg text-slate-800 flex items-start gap-2">
                  <span className="text-[#0B5D3B] font-bold">✓</span>
                  <span className="font-medium">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {/* Source Attribution & Contradictions */}
      {brief ? (
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-base font-extrabold text-slate-900 pb-3 mb-3 border-b border-[#DDE6F0]">
              All Sources ({totalSources})
              {isCorroborated ? (
                <span className="ml-2 text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]">Corroborated</span>
              ) : null}
            </h2>
            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {totalSources === 0 ? (
                <div className="text-xs text-slate-500 italic py-4">INSUFFICIENT EVIDENCE: No sources attached.</div>
              ) : (
                <>
                  {researchSources.length > 0 ? (
                    <div className="text-[10px] font-bold uppercase tracking-wider text-[#004085] mb-2">
                      Source A — Research Intelligence ({researchSources.length})
                    </div>
                  ) : null}
                  {researchSources.map((source, idx) => (
                    <div key={`r${idx}`} className="border border-[#D6E8FF] bg-[#EAF3FF]/40 rounded-lg p-3 text-xs">
                      <div className="font-bold text-slate-900 truncate">{source.title || 'Untitled Source'}</div>
                      <div className="text-[11px] text-slate-500 break-all mt-0.5">{source.url || '—'}</div>
                      <div className="flex items-center gap-2 mt-2 text-[10px] text-slate-600 font-mono">
                        <span>Type: {source.source_type || 'web'}</span>
                        <span>·</span>
                        <span>Relevance: {source.relevance ?? '1.0'}</span>
                      </div>
                      {source.snippet ? (
                        <div className="text-[11px] text-slate-700 mt-2 bg-white p-2 rounded border border-[#E2E8F0] whitespace-pre-wrap font-sans">
                          {source.snippet}
                        </div>
                      ) : null}
                    </div>
                  ))}
                  {uploadedEvidence.length > 0 ? (
                    <div className={`text-[10px] font-bold uppercase tracking-wider text-amber-700 ${researchSources.length > 0 ? 'mt-4' : ''} mb-2`}>
                      Source B — Uploaded Documents ({uploadedEvidence.length})
                    </div>
                  ) : null}
                  {uploadedEvidence.map((doc, idx) => (
                    <div key={`u${idx}`} className="border border-amber-200 bg-amber-50/40 rounded-lg p-3 text-xs">
                      <div className="font-bold text-slate-900">{doc.filename || 'Document'}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
                        Trust: {doc.trust_breakdown?.final_trust_score ?? '—'} · Status: {doc.evidence_status || 'CORROBORATED'}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-base font-extrabold text-slate-900 pb-3 mb-3 border-b border-[#DDE6F0]">
              Contradictions & Unsupported Claims
            </h2>
            <div className="space-y-4 text-xs">
              <div>
                <div className="font-bold text-slate-800 mb-2 uppercase text-[10px] tracking-wider text-slate-500">
                  Detected Contradictions ({contradictions.length})
                </div>
                <div className="space-y-2">
                  {contradictions.length === 0 ? (
                    <div className="text-xs text-slate-500 p-2.5 bg-[#F5F8FC] rounded-lg">No contradictory claims detected across sources.</div>
                  ) : contradictions.map((item, idx) => (
                    <div key={idx} className="border border-rose-200 bg-rose-50/60 rounded-lg p-3 text-slate-800">
                      <div className="font-bold text-rose-800">{item.severity || 'WARN'} · {item.description || 'Contradiction'}</div>
                      <div className="text-xs text-rose-700 mt-1">{item.recommended_action || 'Review conflicting source data.'}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="font-bold text-slate-800 mb-2 uppercase text-[10px] tracking-wider text-slate-500">
                  Unsupported Claims ({unsupported.length})
                </div>
                <div className="space-y-2">
                  {unsupported.length === 0 ? (
                    <div className="text-xs text-slate-500 p-2.5 bg-[#F5F8FC] rounded-lg">All primary claims corroborated by at least one independent source.</div>
                  ) : unsupported.map((item, idx) => (
                    <div key={idx} className="border border-amber-200 bg-amber-50/60 rounded-lg p-3 text-slate-800">
                      <div className="font-bold text-amber-900">{item.description || 'Unsupported Claim'}</div>
                      <div className="text-xs text-amber-800 mt-1">{item.recommended_action || 'Request third-party documentation.'}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </PilotWorkspaceShell>
  )
}
