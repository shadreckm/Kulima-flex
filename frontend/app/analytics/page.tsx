'use client'

import React, { useEffect, useState } from 'react'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getPilotAnalytics, listStoredRuns, isDemoRunRecord, type PilotAnalyticsMetrics, type StoredRunRecord } from '../../lib/api'

function metric(metrics: PilotAnalyticsMetrics | null, key: string): string {
  if (!metrics) return '—'
  const value = metrics[key]
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(1)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return value
  return '—'
}

export default function AnalyticsPage() {
  const { status: authStatus } = useSession()
  const [metrics, setMetrics] = useState<PilotAnalyticsMetrics | null>(null)
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const [analyticsRes, runsRes] = await Promise.all([getPilotAnalytics(), listStoredRuns(100, true)])
      if (cancelled) return
      setMetrics(analyticsRes)
      setRuns(runsRes.runs.filter(run => !isDemoRunRecord(run)))
    }
    if (authStatus === 'authenticated') {
      load().catch(err => setError(String(err)))
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

  const activeRuns = runs.filter(run => !run.archivedAt)
  const archivedRuns = runs.filter(run => run.archivedAt)
  const topRuns = [...runs].sort((a, b) => Number(b.overallScore || 0) - Number(a.overallScore || 0)).slice(0, 5)

  return (
    <PilotWorkspaceShell
      workspace="Analytics"
      title="Portfolio Analytics"
      description="Verdict counts, evidence coverage and trust across every assessment stored in this workspace."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      <section className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          ['Total Assessments', metric(metrics, 'total_runs'), 'Every assessment run stored in this workspace.'],
          ['Invest', metric(metrics, 'invest_count'), 'Assessments whose verdict is the engine term "Invest" — the startup-profile wording of a proceed decision.'],
          ['Co-Invest', metric(metrics, 'co_invest_count'), 'Verdict "Co-Invest": proceed only alongside another funder or partner.'],
          ['Observe', metric(metrics, 'observe_count'), 'Verdict "Observe": not yet enough evidence to decide either way.'],
          ['Pass', metric(metrics, 'pass_count'), 'Verdict "Pass": do not proceed on the current evidence.'],
          ['Average Score', metric(metrics, 'average_score'), '0–100 composite score, averaged over the stored runs. A run with no score yet counts as zero, so a partly finished portfolio reads low.'],
          ['Average Confidence', metric(metrics, 'average_confidence'), '0–1: how firmly the recorded evidence supports each verdict. This is not the same as trust (0–100).'],
          ['Average Trust', metric(metrics, 'average_trust'), '0–100: how much of each assessment rests on verifiable, corroborated sources.'],
          ['Average Risk', metric(metrics, 'average_risk'), '0–100: average risk exposure flagged by the signals engine.'],
          ['Evidence Coverage', `${metric(metrics, 'evidence_coverage')}%`, 'Sources per claim: of the claims these assessments make, how many a recorded source can back (source count ÷ claim count).'],
          ['Verification Coverage', `${metric(metrics, 'signal_coverage')}%`, 'Share of the core narrative sections (lead, entity, diligence, risk, memo) actually produced for each run.'],
          ['Avg Unsupported Claims', metric(metrics, 'average_unsupported_claims'), 'Average number of claims per run that no source could back up.'],
        ].map(([label, value, hint]) => (
          <div
            key={label}
            className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas"
            title={hint}
          >
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{label}</div>
            <div className="mt-1.5 text-2xl font-black text-slate-900 tracking-tight">{value}</div>
            <div className="mt-1 text-[10px] text-slate-400 leading-snug">{hint}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">Portfolio Mix</h2>
          <div className="grid grid-cols-2 gap-3 text-sm text-slate-700">
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Active</div>
              <div className="text-xl font-black text-slate-900 mt-1">{activeRuns.length}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Archived</div>
              <div className="text-xl font-black text-slate-900 mt-1">{archivedRuns.length}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider" title="Assessments whose verdict is the engine term 'Invest' — the strongest proceed verdict the decision engine issues.">Proceed verdicts (Invest)</div>
              <div className="text-xl font-black text-slate-900 mt-1">{metric(metrics, 'invest_count')}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Co-Invest</div>
              <div className="text-xl font-black text-slate-900 mt-1">{metric(metrics, 'co_invest_count')}</div>
            </div>
          </div>
        </div>

        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-1 pb-2.5 border-b border-[#DDE6F0]">Top Assessments by Score</h2>
          <p className="text-[11px] text-slate-500 mb-3">
            Score is the composite verdict (0–100); Trust is the evidence base behind it; Grade is evidence integrity (A–F).
            A dash means the run never produced that figure.
          </p>
          <div className="space-y-3">
            {topRuns.length === 0 ? (
              <div className="text-sm font-bold text-slate-700 py-3">No documents uploaded yet</div>
            ) : topRuns.map(run => (
              <div key={run.runId} className="border border-[#DDE6F0] bg-[#F5F8FC] rounded-lg p-3">
                <div className="text-xs font-bold text-slate-900">{run.startupName}</div>
                <div className="text-[11px] text-slate-500">{run.founderName}</div>
                <div className="text-[10px] text-slate-400 mt-1">Score {run.overallScore ?? 'not scored'} · Trust {run.trustScore ?? 'not scored'} · Grade {run.integrityGrade ?? 'not audited'}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
