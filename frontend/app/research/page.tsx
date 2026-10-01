'use client'

import React, { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getActiveAssessment, getAssessmentWorkspace, type AssessmentWorkspacePayload } from '../../lib/api'

function ResearchPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { status: authStatus } = useSession()
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<AssessmentWorkspacePayload | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function loadResearch() {
      setLoading(true)
      setError(null)
      try {
        const assessmentIdParam = searchParams.get('id') || searchParams.get('assessmentId')
        let payload: AssessmentWorkspacePayload
        if (assessmentIdParam) {
          payload = await getAssessmentWorkspace(assessmentIdParam)
        } else {
          payload = await getActiveAssessment()
        }
        if (!cancelled) setData(payload)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'No active assessment found. Please create an assessment first.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    if (authStatus === 'authenticated') {
      loadResearch()
    } else if (authStatus === 'unauthenticated') {
      setLoading(false)
    }
    return () => {
      cancelled = true
    }
  }, [authStatus, searchParams])

  const status = data?.research?.status ?? data?.status ?? 'pending'
  const sources: any[] = data?.research?.sources ?? []
  const findings: string[] = data?.research?.tavily_findings ?? (data?.research?.summary ? [data.research.summary] : [])
  const entities: any[] = data?.research?.entities ?? (data?.displayEntity ? [{ name: data.displayEntity, label: data.assessmentTypeLabel }] : [])
  const progress = data?.research?.progress ?? (status === 'complete' || status === 'completed' ? 100 : (status === 'running' ? 50 : 20))

  return (
    <PilotWorkspaceShell
      workspace="Research"
      title="Research Intelligence"
      description="External OSINT, market analysis, institutional registry signals, and contextual research."
      runId={data?.runId || null}
      status={status}
      startupName={data?.displayEntity || data?.organizationName || data?.startupName}
      trustScore={data?.trustScore}
    >
      {loading && (
        <div className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-[#0B5D3B] animate-pulse" />
          <span className="text-sm font-semibold text-slate-500">Loading research intelligence…</span>
        </div>
      )}

      {error && !loading && (
        <div className="p-4 rounded-[12px] border border-amber-300 bg-amber-50 text-sm text-amber-800">
          {error}{' '}
          <button className="underline font-bold ml-2" onClick={() => router.push('/')}>
            Create assessment
          </button>
        </div>
      )}

      {data && !loading && (
        <div className="space-y-6">
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Research Pipeline Status</h2>
              <span className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                {String(status)}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs font-bold text-slate-600 mb-1">
              <span>Sources: {sources.length}</span>
              <span>Findings: {findings.length}</span>
              <span>Entities: {entities.length}</span>
            </div>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-[#0B5D3B] transition-all duration-500 rounded-full"
                style={{ width: `${Math.min(100, Math.max(0, Number(progress)))}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-slate-500">{Number(progress)}% processing completed</p>
          </section>

          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3">Extracted & Corroborated Entities</h2>
            {entities.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No entities extracted yet.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {entities.map((e, i) => (
                  <span key={i} className="rounded-full bg-[#EAF8F0] border border-[#B7E6CC] text-[#117A4B] px-3 py-1 text-xs font-semibold">
                    {String(e.name ?? e.label ?? e)}
                  </span>
                ))}
              </div>
            )}
          </section>

          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3">Research Findings & Synthesized Context</h2>
            {findings.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No external findings synthesized yet.</p>
            ) : (
              <div className="space-y-3">
                {findings.map((f, i) => (
                  <div key={i} className="p-3 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0] text-xs leading-5 text-slate-700">
                    {String(f)}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3">Sources & Evidence Attribution</h2>
            {sources.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No external sources recorded yet.</p>
            ) : (
              <ul className="space-y-2">
                {sources.map((s, i) => (
                  <li key={i} className="p-3 bg-white rounded-lg border border-[#DDE6F0] flex flex-col gap-1">
                    <div className="text-xs font-bold text-slate-900">
                      {s.url ? (
                        <a className="text-[#0B5D3B] hover:underline" href={String(s.url)} target="_blank" rel="noreferrer">
                          {String(s.title ?? s.url)}
                        </a>
                      ) : (
                        String(s.title ?? 'Source')
                      )}
                    </div>
                    {s.snippet && <p className="text-[11px] text-slate-500 leading-4">{String(s.snippet)}</p>}
                  </li>
                ))}
              </ul>
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
