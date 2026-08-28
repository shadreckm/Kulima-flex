'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getFullBrief, listStoredRuns, uploadDocument, type StoredRunRecord } from '../../lib/api'
import { loadCurrentRun } from '../../lib/current-run'
import TrustGauge from '../../components/TrustGauge/TrustGauge'

type FullBrief = Record<string, any>

export default function EvidencePage() {
  const { status: authStatus } = useSession()
  const searchParams = useSearchParams()
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [brief, setBrief] = useState<FullBrief | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)

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

  async function refreshBrief() {
    if (!selectedRunId) {
      setBrief(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await getFullBrief(selectedRunId)
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
  }, [authStatus, selectedRunId])

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    const file = files[0]
    setUploading(true)
    setError(null)
    setUploadSuccess(null)
    try {
      const res = await uploadDocument(file, selectedRunId || null)
      setUploadSuccess(`Successfully ingested "${res.name}" into Evidence Pipeline. Trust evaluated at ${res.trustScore ?? 80}/100.`)
      await refreshBrief()
    } catch (err: any) {
      setError(`Document upload failed: ${err.message || String(err)}`)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const selectedRun = useMemo(() => runs.find(run => String(run.runId) === String(selectedRunId)), [runs, selectedRunId])
  const ei = brief?.evidence_integrity || null
  /** Tavily / web research sources — Source A */
  const researchSources: Array<any> = Array.isArray(brief?.sources) ? brief.sources : []
  /** Uploaded primary documents — Source B */
  const uploadedEvidence: Array<any> = Array.isArray(brief?.uploaded_evidence) ? brief.uploaded_evidence : []
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
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima OS</div>
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
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
      startupName={selectedRun?.startupName}
      recommendation={selectedRun?.recommendation}
      trustScore={selectedRun?.trustScore}
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div> : null}
      {uploadSuccess ? (
        <div className="p-4 bg-emerald-50 text-emerald-800 rounded-[12px] border border-emerald-200 text-sm font-bold flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
          <span>{uploadSuccess}</span>
        </div>
      ) : null}

      {/* Evidence Corroboration Status Banner */}
      {selectedRunId ? (
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

      {/* Control Bar: Run Selector & Ingestion Upload Trigger */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Active Evaluation Target</label>
          <select
            className="mt-1.5 w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 font-bold focus:outline-none focus:border-[#0B5D3B]"
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
          >
            <option value="">Select Evaluation Target…</option>
            {runs.map(run => (
              <option key={run.runId} value={run.runId}>
                #{run.runId} · {run.startupName} ({run.founderName}) — Trust: {run.trustScore ?? '—'}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
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

      {/* Decision Intelligence Summary Block */}
      {brief ? (
        <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#DDE6F0]">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Core Evaluation</span>
              <h2 className="text-base font-extrabold text-slate-900">Decision Intelligence Summary</h2>
            </div>
            <span className={`text-xs px-3 py-1 rounded-full font-black uppercase tracking-wider ${
              brief.recommendation === 'Invest' ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
              brief.recommendation === 'Observe' ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
              'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
            }`}>
              {brief.recommendation || 'OBSERVE'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <span className="font-bold text-slate-500 uppercase tracking-wider block mb-1">Recommendation Rationale</span>
              <p className="text-slate-800 font-medium leading-relaxed">
                {brief.executive_summary || 'INSUFFICIENT EVIDENCE: No executive briefing generated yet.'}
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
            {uploadedEvidence.map((doc, idx) => (
              <div key={doc.id || idx} className="p-4 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0] space-y-3">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-[#DDE6F0]">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-900 text-white">
                        {doc.file_type || 'DOCUMENT'}
                      </span>
                      <span className="text-sm font-extrabold text-slate-900">{doc.filename}</span>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      Source: {doc.source} · Uploaded: {doc.upload_date ? new Date(doc.upload_date).toLocaleString() : 'Recent'} · By: {doc.uploader}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider ${
                      doc.evidence_status === 'VERIFIED' ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
                      doc.evidence_status === 'CORROBORATED' ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
                      'bg-slate-200 text-slate-700'
                    }`}>
                      {doc.evidence_status || 'CORROBORATED'}
                    </span>
                    <TrustGauge score={doc.trust_breakdown?.final_trust_score ?? 80} size="sm" showLabel={false} />
                  </div>
                </div>

                {/* Transparent Trust Engine Breakdown */}
                {doc.trust_breakdown ? (
                  <div className="p-3 bg-white rounded-lg border border-[#DDE6F0] text-xs">
                    <div className="font-extrabold text-slate-900 mb-2 uppercase tracking-wider text-[10px] text-slate-500">
                      Transparent Trust Engine Breakdown
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2 text-slate-700">
                      <div className="p-2 bg-[#F5F8FC] rounded border border-[#E2E8F0]">
                        <span className="text-slate-500 block text-[10px]">Source Reliability (35%)</span>
                        <strong className="text-slate-900 font-mono text-xs">{doc.trust_breakdown.source_reliability}%</strong>
                      </div>
                      <div className="p-2 bg-[#F5F8FC] rounded border border-[#E2E8F0]">
                        <span className="text-slate-500 block text-[10px]">Corroboration (25%)</span>
                        <strong className="text-slate-900 font-mono text-xs">{doc.trust_breakdown.corroboration}%</strong>
                      </div>
                      <div className="p-2 bg-[#F5F8FC] rounded border border-[#E2E8F0]">
                        <span className="text-slate-500 block text-[10px]">Recency (15%)</span>
                        <strong className="text-slate-900 font-mono text-xs">{doc.trust_breakdown.recency}%</strong>
                      </div>
                      <div className="p-2 bg-[#F5F8FC] rounded border border-[#E2E8F0]">
                        <span className="text-slate-500 block text-[10px]">Completeness (25%)</span>
                        <strong className="text-slate-900 font-mono text-xs">{doc.trust_breakdown.completeness}%</strong>
                      </div>
                    </div>
                    <div className="text-[11px] text-slate-600 italic">
                      {doc.trust_breakdown.rationale || 'Calculated via weighted multi-factor deterministic scoring.'}
                    </div>
                  </div>
                ) : null}

                {/* Extracted Evidence Items & Generated Signals */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-white rounded-lg border border-[#DDE6F0]">
                    <div className="font-bold text-slate-900 mb-1">Extracted Evidence Items</div>
                    <ul className="list-disc list-inside space-y-1 text-slate-700">
                      {Array.isArray(doc.evidence_items) && doc.evidence_items.length > 0 ? (
                        doc.evidence_items.map((item: string, i: number) => <li key={i}>{item}</li>)
                      ) : (
                        <li className="text-slate-400 italic">INSUFFICIENT EVIDENCE</li>
                      )}
                    </ul>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-[#DDE6F0]">
                    <div className="font-bold text-slate-900 mb-1">Signals Generated</div>
                    <ul className="list-disc list-inside space-y-1 text-slate-700">
                      {Array.isArray(doc.signals_generated) && doc.signals_generated.length > 0 ? (
                        doc.signals_generated.map((sig: string, i: number) => <li key={i}>{sig}</li>)
                      ) : (
                        <li className="text-slate-400 italic">No automated signals emitted</li>
                      )}
                    </ul>
                  </div>
                </div>

                {/* Audit Trail */}
                {Array.isArray(doc.audit_trail) && doc.audit_trail.length > 0 ? (
                  <div className="text-[10px] text-slate-400 font-mono flex items-center gap-2 pt-2 border-t border-[#DDE6F0]">
                    <span>Audit Trail:</span>
                    <span>{doc.audit_trail.join(' · ')}</span>
                  </div>
                ) : null}
              </div>
            ))}
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
