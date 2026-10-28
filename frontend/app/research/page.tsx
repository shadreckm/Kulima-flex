'use client'

import React, { Suspense } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import WorkspaceHeader from '../../components/WorkspaceHeader'
import AssessmentProgress from '../../components/AssessmentProgress'
import { normalizeEntityType } from '../../lib/assessment-store'
import { useAssessmentWorkspace } from '../../hooks/useAssessmentWorkspace'
import AssessmentGuard from '../../components/AssessmentGuard/AssessmentGuard'

function ResearchPageInner() {
  const router = useRouter()
  const { status: authStatus } = useSession()
  const { data, loading, error, noAssessment } = useAssessmentWorkspace(authStatus === 'authenticated')

  const status = data?.research?.status ?? data?.status ?? 'pending'
  const sources: any[] = data?.research?.sources ?? []
  const sanitizeResearchText = (txt: any) => {
    if (!txt) return ''
    return String(txt)
      .replace(/%PDF-[0-9.]+/gi, '')
      .replace(/(?:CreationDate|ModDate|Creator|Producer|Author|Subject|Keywords|Title)\s*[:=]\s*[^\n\r;]+/gi, '')
      .replace(/\b(?:xref|endobj|endstream|startxref|trailer)\b/gi, '')
      .replace(/\/(?:Root|Info|Size|Filter|Length|FlateDecode)\b/gi, '')
      .trim()
  }

  const rawFindings: string[] = data?.research?.tavily_findings ?? (data?.research?.summary ? [data.research.summary] : [])
  const findings: string[] = rawFindings.map(sanitizeResearchText).filter(Boolean)
  const entities: any[] = data?.research?.entities ?? (data?.displayEntity ? [{ name: data.displayEntity, label: data.assessmentTypeLabel }] : [])
  const researchSummary: string = data?.research?.summary ?? data?.research?.synthesis ?? ''

  const synthesizedFallback =
    data?.research?.summary ||
    data?.research?.synthesis ||
    (findings.length > 0 ? findings.slice(0, 3).join(' ') : '') ||
    (sources.length > 0 ? `Evidence analysis grounded in ${sources.length} primary and research sources.` : '') ||
    (data?.problemStatement ? String(data.problemStatement) : '') ||
    ''

  const effectiveSummary =
    (researchSummary && researchSummary.trim()) ||
    (String(status).toLowerCase() === 'completed' || String(status).toLowerCase() === 'complete' ? synthesizedFallback : '')

  // Phase 2: Research completion is only when actual usable output exists
  const hasUsableResearch = (effectiveSummary && effectiveSummary.length > 30) || (sources.length > 0 && findings.length > 0)
  const docIntelMode: boolean = data?.research?.mode === 'document_intelligence'
  const docIntelFindings: string[] = data?.research?.document_findings ?? (docIntelMode && data?.extractedTextPreview ? [data.extractedTextPreview] : [])

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
  if (noAssessment && !loading) {
    return <AssessmentGuard active loading={false} />
  }

  // STATE SYNCHRONIZATION FIX: Derive status from actual data, not just cached state
  // If usable research exists, status should be 'complete' regardless of stored status.
  // All downstream consumers (header, progress steps, banners) must read this
  // derived status — never the raw cached string.
  const effectiveStatus = hasUsableResearch ? 'complete' : status
  const effectiveStatusLower = String(effectiveStatus).toLowerCase()
  const isRunning = effectiveStatusLower === 'running' && !hasUsableResearch
  // A completion percentage appears only when the pipeline reported one or
  // research output genuinely exists. Guessing 20% / 50% for a stage that never
  // published progress puts an unverifiable number in front of a decision-maker.
  const derivedProgress: number | null = hasUsableResearch
    ? 100
    : (typeof data?.research?.progress === 'number' ? Math.round(data.research.progress) : null)
  const docCount = data?.documentCount ?? data?.uploadedDocuments?.length ?? 0
  const hasSignalsOutput =
    (data?.signals?.length ?? 0) > 0 ||
    Object.keys((data as Record<string, any> | null)?.signalsSummary ?? {}).length > 0
  const hasDecisionOutput = Object.keys(data?.decision ?? {}).length > 0
  const hasReportOutput = Object.keys(data?.reports ?? {}).length > 0
  const runComplete = ['complete', 'completed'].includes(String(data?.status || '').toLowerCase())
  // Each stage reads as complete from its own output only: research finishing has
  // not produced a decision or a report.
  const derivedProgressSteps: Array<{ key: string; label: string; status: 'complete' | 'pending' | 'in_progress' }> = [
    { key: 'created', label: 'Assessment', status: 'complete' },
    { key: 'research', label: 'Research', status: hasUsableResearch || runComplete ? 'complete' : (isRunning ? 'in_progress' : 'pending') },
    { key: 'evidence', label: 'Evidence', status: docCount > 0 ? 'complete' : 'pending' },
    { key: 'signals', label: 'Signals', status: hasSignalsOutput || runComplete ? 'complete' : 'pending' },
    { key: 'decision', label: 'Decision', status: hasDecisionOutput || runComplete ? 'complete' : 'pending' },
    { key: 'report', label: 'Reports', status: hasReportOutput || runComplete ? 'complete' : 'pending' },
  ]

  return (
    <PilotWorkspaceShell
      workspace="Research"
      title="Research Intelligence"
      description="Public sources, sector context, registry checks and document evidence gathered for this assessment."
      runId={data?.runId || null}
      status={effectiveStatus}
      startupName={data?.displayEntity || data?.organizationName || data?.startupName}
      trustScore={data?.trustScore}
      assessmentCtx={data ? {
        entityType: (data.assessmentType as any) || 'ngo',
        entityLabel: data.assessmentTypeLabel || 'Assessment',
        entityName: data.displayEntity || data.organizationName || data.startupName || '',
        founderOrLead: data.founderName || '',
        runId: data.runId || '',
        createdAt: data.createdAt || '',
        hasDocument: (data.documentCount ?? 0) > 0,
        assessmentId: data.assessmentId,
        assessmentTypeLabel: data.assessmentTypeLabel,
        status: data.status,
        displayEntity: data.displayEntity || data.organizationName || data.startupName,
        sector: data.sector,
        confidence: data.confidence,
        trustScore: data.trustScore,
        documentCount: data.documentCount,
      } : null}
    >
      {data && !loading && (
        <div className="space-y-4 mb-6">
          <WorkspaceHeader
            assessmentName={data?.displayEntity || data?.organizationName || data?.startupName}
            assessmentType={normalizeEntityType(data?.assessmentType)}
            organization={data?.organizationName}
            founder={data?.founderName}
            status={effectiveStatus}
            documentCount={data?.uploadedDocuments?.length || 0}
            progress={derivedProgress ?? undefined}
          />
          <AssessmentProgress steps={derivedProgressSteps} />
        </div>
      )}

      {loading && (
        <div className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-[#0B5D3B] animate-pulse" />
          <span className="text-sm font-semibold text-slate-500">Loading research intelligence…</span>
        </div>
      )}

      {error && !loading && !noAssessment && (
        <div className="p-4 rounded-[12px] border border-amber-300 bg-amber-50 text-sm text-amber-800">
          {error}{' '}
          <button className="underline font-bold ml-2" onClick={() => router.push('/flex')}>
            Open workspace
          </button>
        </div>
      )}

      {data && !loading && (
        <div className="space-y-6">
          {docIntelMode ? (
            <section role="status" aria-live="polite" className="rounded-[12px] border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
              <div className="flex items-center gap-2 font-bold">
                <span>📄</span>
                <span>Document Intelligence Mode — no live AI provider served this run</span>
              </div>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                {data.research?.message || 'Research is grounded in uploaded documents, extraction, trust scoring, and available external sources. Live web research is inactive.'}
              </p>
            </section>
          ) : null}

          {/* Pipeline Status + Summary */}
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#DDE6F0]">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Research Summary</h2>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-500">
                  <span>{sources.length} source{sources.length !== 1 ? 's' : ''}</span>
                  <span>·</span>
                  <span>{findings.length} finding{findings.length !== 1 ? 's' : ''}</span>
                  <span>·</span>
                  <span>{entities.length} entit{entities.length !== 1 ? 'ies' : 'y'}</span>
                </div>
                <span className={`text-[10px] font-black px-2 py-0.5 rounded uppercase tracking-wider border ${
                  hasUsableResearch ? 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]' :
                  isRunning ? 'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]' :
                  'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]'
                }`}>
                  {hasUsableResearch ? 'COMPLETE' : String(effectiveStatus).toUpperCase()}
                </span>
              </div>
            </div>

            {/* Progress bar — drawn only when a real percentage exists. */}
            {derivedProgress != null ? (
              <>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 mb-2">
                  <div
                    className="h-full bg-[#0B5D3B] transition-all duration-700 rounded-full"
                    style={{ width: `${Math.min(100, Math.max(0, derivedProgress))}%` }}
                  />
                </div>
                <p className="text-xs text-slate-500 mb-3">{derivedProgress}% complete</p>
              </>
            ) : (
              <p className="text-xs text-slate-500 mb-3">
                {isRunning ? 'Research is running — this stage has not reported a completion percentage.' : 'No completion percentage reported for this stage.'}
              </p>
            )}

            {effectiveSummary ? (
              <div className="p-3.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0] text-xs text-slate-700 leading-6">
                {effectiveSummary}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">
                {isRunning ? 'Research in progress — findings will appear here.' : 'No research summary available yet.'}
              </p>
            )}
          </section>

          {/* Entities */}
          {entities.length > 0 ? (
            <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3 pb-2 border-b border-[#DDE6F0]">
                Extracted Entities
              </h2>
              <div className="flex flex-wrap gap-2">
                {entities.map((e, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5 rounded-full bg-[#EAF8F0] border border-[#B7E6CC] text-[#117A4B] px-3 py-1 text-xs font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#12B76A] flex-shrink-0" />
                    {String(e.name ?? e.label ?? e)}
                    {e.type ? <span className="text-[#027A48]/60 text-[10px]">({e.type})</span> : null}
                  </span>
                ))}
              </div>
            </section>
          ) : null}

          {/* Tavily / live findings */}
          {findings.length > 0 ? (
            <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3 pb-2 border-b border-[#DDE6F0]">
                Live Web Research Findings
                <span className="ml-2 text-[10px] font-bold text-slate-400 normal-case tracking-normal">
                  from public sources · {findings.length}
                </span>
              </h2>
              <div className="space-y-2.5">
                {findings.map((f, i) => (
                  <div key={i} className="p-3 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0] text-xs leading-5 text-slate-700">
                    <span className="text-[10px] font-bold text-[#004085] uppercase tracking-wider mr-2">#{i + 1}</span>
                    {String(f)}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {/* Document Intelligence findings */}
          {docIntelFindings.length > 0 ? (
            <section className="p-5 bg-white rounded-[12px] border border-amber-200 shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3 pb-2 border-b border-amber-200">
                📄 Document Intelligence Findings
                <span className="ml-2 text-[10px] font-bold text-amber-600 normal-case tracking-normal">extracted from uploaded documents</span>
              </h2>
              <div className="space-y-2.5">
                {docIntelFindings.map((f, i) => (
                  <div key={i} className="p-3 bg-amber-50 rounded-lg border border-amber-100 text-xs leading-5 text-amber-900">
                    {String(f)}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {/* Sources */}
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3 pb-2 border-b border-[#DDE6F0]">
              Sources & Attribution
              <span className="ml-2 text-[10px] font-bold text-slate-400 normal-case tracking-normal">({sources.length})</span>
            </h2>
            {sources.length === 0 ? (
              <p className="text-xs text-slate-400 italic py-2">
                {docIntelMode ? 'Live sources not available in Document Intelligence Mode.' : 'No external sources recorded yet.'}
              </p>
            ) : (
              <div className="space-y-3">
                {sources.map((s, i) => (
                  <div key={i} className="p-3 bg-white rounded-lg border border-[#DDE6F0]">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-bold text-slate-900">
                          {s.url ? (
                            <a className="text-[#0B5D3B] hover:underline" href={String(s.url)} target="_blank" rel="noreferrer">
                              {String(s.title ?? s.url)}
                            </a>
                          ) : (
                            String(s.title ?? `Source ${i + 1}`)
                          )}
                        </div>
                        {s.url ? (
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5 truncate">{String(s.url)}</div>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {s.source_type ? (
                          <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]">
                            {s.source_type}
                          </span>
                        ) : null}
                        {s.relevance != null ? (
                          <span
                            className="text-[9px] font-bold text-slate-400"
                            title="Relevance 0–1: how closely this source matches the entity under assessment, as reported by the research provider. It is not a trust score — trust is scored per document on the Evidence screen."
                          >
                            relevance {Number(s.relevance).toFixed(2)} / 1
                          </span>
                        ) : null}
                      </div>
                    </div>
                    {s.snippet ? (
                      <p className="mt-2 text-[11px] text-slate-600 leading-4 line-clamp-3">{String(s.snippet)}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </PilotWorkspaceShell>
  )
}

export default function ResearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <ResearchPageInner />
    </Suspense>
  )
}
