'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getFullBrief, listStoredRuns, type StoredRunRecord } from '../../lib/api'

type FullBrief = Record<string, any>

export default function EvidencePage() {
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
      const nextSelected = fromQuery || String(res.runs[0]?.runId || '')
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
  const ei = brief?.evidence_integrity || null
  const sources: Array<any> = Array.isArray(brief?.sources) ? brief.sources : []
  const contradictions: Array<any> = Array.isArray(ei?.contradictions) ? ei.contradictions : []
  const unsupported: Array<any> = Array.isArray(ei?.unsupported_claims) ? ei.unsupported_claims : []
  const verificationChecklist: Array<string> = Array.isArray(ei?.verification_checklist) ? ei.verification_checklist : []

  if (authStatus === 'loading') {
    return <div className="min-h-screen flex items-center justify-center text-sm text-gray-600">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-semibold">Sign in to use Kulima OS</div>
        <button onClick={() => signIn()} className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">
          Sign in
        </button>
      </div>
    )
  }

  return (
    <PilotWorkspaceShell
      workspace="Evidence"
      title="Evidence Workspace"
      description="Inspect the stored evidence integrity data, source attribution, contradictions, and verification checklist for a completed run."
      runId={selectedRunId || null}
      status={selectedRun?.archivedAt ? 'archived' : 'active'}
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}

      <section className="p-4 bg-white rounded shadow border border-gray-100">
        <label className="block text-sm font-medium text-gray-700">Select run</label>
        <select
          className="mt-2 w-full p-2 border rounded"
          value={selectedRunId}
          onChange={(e) => setSelectedRunId(e.target.value)}
        >
          <option value="">Choose a stored run…</option>
          {runs.map(run => (
            <option key={run.runId} value={run.runId}>
              #{run.runId} · {run.startupName} · {run.founderName}
            </option>
          ))}
        </select>
        {selectedRun ? (
          <div className="mt-3 text-xs text-gray-500">
            Score {selectedRun.overallScore ?? '—'} · Trust {selectedRun.trustScore ?? '—'} · Reliability {selectedRun.integrityGrade ?? '—'}
          </div>
        ) : null}
      </section>

      {loading && !brief ? <div className="p-4 text-sm text-gray-500">Loading evidence…</div> : null}

      {brief ? (
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="p-4 bg-white rounded shadow border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">Integrity Summary</h2>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-gray-700">
              <div>Grade: <span className="font-semibold">{ei?.integrity_grade || '—'}</span></div>
              <div>Score: <span className="font-semibold">{ei?.integrity_score ?? '—'}</span></div>
              <div>Depth: <span className="font-semibold">{ei?.evidence_depth || '—'}</span></div>
              <div>Consistency: <span className="font-semibold">{ei?.consistency_status || '—'}</span></div>
              <div>Sources reviewed: <span className="font-semibold">{ei?.source_count ?? '—'}</span></div>
              <div>Claims extracted: <span className="font-semibold">{ei?.claim_count ?? '—'}</span></div>
            </div>
            <p className="mt-4 text-sm text-gray-700 whitespace-pre-wrap">{ei?.integrity_summary || 'No evidence summary available.'}</p>
          </div>

          <div className="p-4 bg-white rounded shadow border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">Verification Checklist</h2>
            <div className="mt-3 space-y-2">
              {verificationChecklist.length === 0 ? (
                <div className="text-sm text-gray-500">No checklist items available for this run.</div>
              ) : verificationChecklist.map((item, idx) => (
                <div key={idx} className="p-3 border rounded text-sm text-gray-700">{item}</div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {brief ? (
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="p-4 bg-white rounded shadow border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">Source Attribution</h2>
            <div className="mt-3 space-y-3">
              {sources.length === 0 ? (
                <div className="text-sm text-gray-500">No sources attached to this run.</div>
              ) : sources.map((source, idx) => (
                <div key={idx} className="border rounded p-3">
                  <div className="text-sm font-medium text-gray-900">{source.title || 'Untitled source'}</div>
                  <div className="text-xs text-gray-500 break-all mt-1">{source.url || '—'}</div>
                  <div className="text-xs text-gray-600 mt-2">
                    Type: {source.source_type || '—'} · Relevance: {source.relevance ?? '—'} · Confidence: {source.confidence_score ?? '—'}
                  </div>
                  {source.snippet ? <div className="text-xs text-gray-700 mt-2 whitespace-pre-wrap">{source.snippet}</div> : null}
                </div>
              ))}
            </div>
          </div>

          <div className="p-4 bg-white rounded shadow border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">Evidence Findings</h2>
            <div className="mt-3 space-y-4">
              <div>
                <div className="text-sm font-medium text-gray-800">Contradictions</div>
                <div className="mt-2 space-y-2">
                  {contradictions.length === 0 ? (
                    <div className="text-sm text-gray-500">No contradictions recorded.</div>
                  ) : contradictions.map((item, idx) => (
                    <div key={idx} className="border rounded p-3 text-sm text-gray-700">
                      <div className="font-medium">{item.severity || '—'} · {item.description || 'Contradiction'}</div>
                      <div className="text-xs text-gray-500 mt-1">{item.recommended_action || 'No recommended action provided.'}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-sm font-medium text-gray-800">Unsupported Claims</div>
                <div className="mt-2 space-y-2">
                  {unsupported.length === 0 ? (
                    <div className="text-sm text-gray-500">No unsupported claims recorded.</div>
                  ) : unsupported.map((item, idx) => (
                    <div key={idx} className="border rounded p-3 text-sm text-gray-700">
                      <div>{item.description || 'Unsupported claim'}</div>
                      <div className="text-xs text-gray-500 mt-1">{item.recommended_action || 'No recommended action provided.'}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {brief ? (
        <section className="p-4 bg-white rounded shadow border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Evidence-Driven Brief Summary</h2>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-700">
            <div><span className="font-medium">Recommendation:</span> {brief.recommendation || '—'}</div>
            <div><span className="font-medium">Confidence:</span> {brief.confidence ?? '—'}</div>
            <div><span className="font-medium">Top risks:</span> {Array.isArray(brief.red_flags) ? brief.red_flags.length : 0}</div>
            <div><span className="font-medium">Next steps:</span> {Array.isArray(brief.next_steps) ? brief.next_steps.length : 0}</div>
          </div>
        </section>
      ) : null}
    </PilotWorkspaceShell>
  )
}
