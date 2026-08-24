'use client'

import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import TrustGauge from '../../components/TrustGauge/TrustGauge'
import {
  getDecisionHistory,
  getOutcomeIntelligence,
  saveOutcome,
  type OutcomeUpdatePayload,
} from '../../lib/api'

type Tab = 'history' | 'intelligence' | 'calibration' | 'meal' | 'timeline'

const OUTCOME_STATUSES = ['Pending', 'In Progress', 'Completed', 'Successful', 'Partially Successful', 'Unsuccessful']
const OUTCOME_COLORS: Record<string, string> = {
  'Successful': 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]',
  'Partially Successful': 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]',
  'Unsuccessful': 'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]',
  'Completed': 'bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]',
  'In Progress': 'bg-[#F0FDF4] text-[#16a34a] border border-[#bbf7d0]',
  'Pending': 'bg-slate-100 text-slate-700 border border-slate-300',
}

export default function OutcomesPage() {
  const { status: authStatus } = useSession()
  const [activeTab, setActiveTab] = useState<Tab>('history')
  const [decisions, setDecisions] = useState<Record<string, any>[]>([])
  const [intelligence, setIntelligence] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  // Local mutation state for outcome updates
  const [draftOutcomes, setDraftOutcomes] = useState<Record<number, OutcomeUpdatePayload>>({})

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [hist, intel] = await Promise.all([
        getDecisionHistory(100),
        getOutcomeIntelligence(),
      ])
      setDecisions(hist.decisions)
      setIntelligence(intel)
    } catch (err: any) {
      setError(err.message || String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (authStatus === 'authenticated') {
      loadAll()
    }
  }, [authStatus, loadAll])

  function getDraft(runId: number): OutcomeUpdatePayload {
    const row = decisions.find(d => d.id === runId)
    return draftOutcomes[runId] || {
      outcome_status: row?.outcome_status || 'Pending',
      outcome_notes: row?.outcome_notes || '',
      what_happened: row?.what_happened || '',
      what_was_predicted: row?.what_was_predicted || '',
      what_was_missed: row?.what_was_missed || '',
      what_worked: row?.what_worked || '',
      what_failed: row?.what_failed || '',
    }
  }

  function patchDraft(runId: number, patch: Partial<OutcomeUpdatePayload>) {
    setDraftOutcomes(prev => ({
      ...prev,
      [runId]: { ...getDraft(runId), ...patch },
    }))
  }

  async function handleSave(runId: number) {
    setSavingId(runId)
    setSaveSuccess(null)
    try {
      await saveOutcome(runId, getDraft(runId))
      setSaveSuccess(`Outcome updated for run #${runId}`)
      await loadAll()
    } catch (err: any) {
      setError(err.message || String(err))
    } finally {
      setSavingId(null)
    }
  }

  const calibrationBins: any[] = intelligence?.calibration?.calibration_bins || []
  const mealsData: any[] = useMemo(() => {
    // Derive MEAL-like indicators from decisions corpus
    const total = decisions.length
    const successful = decisions.filter(d => d.outcome_status === 'Successful').length
    const partSuccessful = decisions.filter(d => d.outcome_status === 'Partially Successful').length
    const unsuccessful = decisions.filter(d => d.outcome_status === 'Unsuccessful').length
    const pending = decisions.filter(d => !d.outcome_status || d.outcome_status === 'Pending').length
    const avgTrust = total > 0 ? Math.round(decisions.reduce((s, d) => s + (d.trust_score || 0), 0) / total) : 0
    return [
      { id: 'dec_total', name: 'Total Decisions Made', target: 10, actual: total, unit: 'decisions', status: total >= 10 ? 'ON_TRACK' : 'AT_RISK' },
      { id: 'dec_success', name: 'Successful Outcomes', target: total, actual: successful, unit: 'deals', status: successful > 0 ? 'ON_TRACK' : 'INSUFFICIENT_EVIDENCE' },
      { id: 'dec_partial', name: 'Partially Successful', target: 0, actual: partSuccessful, unit: 'deals', status: 'AT_RISK' },
      { id: 'dec_fail', name: 'Unsuccessful Outcomes', target: 0, actual: unsuccessful, unit: 'deals', status: unsuccessful === 0 ? 'ON_TRACK' : 'OFF_TRACK' },
      { id: 'dec_pending', name: 'Pending / In-Progress Decisions', target: 0, actual: pending, unit: 'decisions', status: pending > 5 ? 'AT_RISK' : 'ON_TRACK' },
      { id: 'avg_trust', name: 'Average Trust Score at Decision', target: 80, actual: avgTrust, unit: '/100', status: avgTrust >= 80 ? 'ON_TRACK' : avgTrust >= 60 ? 'AT_RISK' : 'OFF_TRACK' },
    ]
  }, [decisions])

  const timelineStages = useMemo(() => [
    { stage: 'Information', icon: '📥', description: 'Raw data, pitch documents, OSINT sources collected per venture.' },
    { stage: 'Evidence', icon: '📋', description: 'Structured document ingestion, chunk extraction, source attribution.' },
    { stage: 'Trust', icon: '⚖️', description: 'Deterministic 4-factor scoring: Source Reliability, Corroboration, Recency, Completeness.' },
    { stage: 'Signals', icon: '⚡', description: 'Automated Risk, Opportunity, and Anomaly extraction from evidence corpus.' },
    { stage: 'Decision', icon: '🎯', description: 'Investment Committee verdict: Invest / Observe / Pass with rationale.' },
    { stage: 'Outcome', icon: '📊', description: 'Actual real-world result: Successful / Partially Successful / Unsuccessful.' },
    { stage: 'Learning', icon: '🧠', description: 'Trust calibration, accuracy measurement, lessons extracted for future decisions.' },
  ], [])

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

  const TABS: { id: Tab; label: string }[] = [
    { id: 'history', label: 'Decision History' },
    { id: 'intelligence', label: 'Outcome Intelligence' },
    { id: 'calibration', label: 'Trust Calibration' },
    { id: 'meal', label: 'MEAL Dashboard' },
    { id: 'timeline', label: 'Decision Timeline' },
  ]

  return (
    <PilotWorkspaceShell
      workspace="Outcomes"
      title="Decision Learning System"
      description="Evidence → Trust → Signals → Decision → Outcome → Learning. Close the feedback loop."
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div> : null}
      {saveSuccess ? (
        <div className="p-4 bg-emerald-50 text-emerald-800 rounded-[12px] border border-emerald-200 text-sm font-bold flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#12B76A]" />
          {saveSuccess}
        </div>
      ) : null}

      {/* Tab bar */}
      <div className="flex items-center gap-1 bg-white border border-[#DDE6F0] rounded-[12px] p-1.5 overflow-x-auto shadow-saas">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-[8px] text-xs font-extrabold uppercase tracking-wider transition whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-[#061C14] text-white shadow-sm'
                : 'text-slate-600 hover:bg-[#F5F8FC] hover:text-slate-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab: Decision History */}
      {activeTab === 'history' ? (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700">
              Decision Registry ({decisions.length} records)
            </h2>
            {loading ? <span className="text-xs text-slate-500 animate-pulse">Loading…</span> : null}
          </div>

          {decisions.length === 0 && !loading ? (
            <div className="p-8 text-center bg-white rounded-[12px] border border-dashed border-[#DDE6F0] text-slate-500 text-sm font-medium">
              No decisions recorded yet. Run a venture evaluation to populate the Decision Registry.
            </div>
          ) : null}

          {decisions.map(d => {
            const runId = d.id as number
            const isOpen = expandedId === runId
            const draft = getDraft(runId)
            return (
              <div key={runId} className="bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas overflow-hidden">
                {/* Row header */}
                <button
                  className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#F5F8FC] transition text-left"
                  onClick={() => setExpandedId(isOpen ? null : runId)}
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <span className="text-xs font-mono text-slate-400 shrink-0">#{runId}</span>
                    <div className="min-w-0">
                      <div className="text-sm font-extrabold text-slate-900 truncate">{d.startup_name}</div>
                      <div className="text-xs text-slate-500 truncate">{d.founder_name} · {new Date(d.created_at).toLocaleDateString()}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider ${
                      d.recommendation === 'Invest' ? 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]' :
                      d.recommendation === 'Observe' ? 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]' :
                      'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
                    }`}>
                      {d.recommendation || 'OBSERVE'}
                    </span>
                    <span className={`text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider ${OUTCOME_COLORS[d.outcome_status || 'Pending'] || OUTCOME_COLORS['Pending']}`}>
                      {d.outcome_status || 'Pending'}
                    </span>
                    <TrustGauge score={d.trust_score ?? 0} size="sm" showLabel={false} />
                    <svg className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Expanded outcome editor + lessons */}
                {isOpen ? (
                  <div className="border-t border-[#DDE6F0] px-5 py-4 bg-[#F5F8FC] space-y-4">
                    {/* Outcome Status Update */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">Outcome Status</label>
                        <select
                          className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm font-bold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
                          value={draft.outcome_status}
                          onChange={e => patchDraft(runId, { outcome_status: e.target.value })}
                        >
                          {OUTCOME_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">Outcome Date</label>
                        <input
                          type="date"
                          className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm font-bold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
                          value={draft.outcome_date || ''}
                          onChange={e => patchDraft(runId, { outcome_date: e.target.value || null })}
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">Notes</label>
                        <input
                          type="text"
                          className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
                          placeholder="Brief outcome note…"
                          value={draft.outcome_notes || ''}
                          onChange={e => patchDraft(runId, { outcome_notes: e.target.value })}
                        />
                      </div>
                    </div>

                    {/* Lessons Learned */}
                    <div>
                      <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-2">Lessons Learned</div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {([
                          { key: 'what_happened', label: 'What Happened' },
                          { key: 'what_was_predicted', label: 'What Was Predicted' },
                          { key: 'what_was_missed', label: 'What Was Missed' },
                          { key: 'what_worked', label: 'What Worked' },
                          { key: 'what_failed', label: 'What Failed' },
                        ] as { key: keyof OutcomeUpdatePayload; label: string }[]).map(({ key, label }) => (
                          <div key={key}>
                            <label className="block text-[10px] font-bold text-slate-500 mb-1">{label}</label>
                            <textarea
                              rows={2}
                              className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-xs text-slate-900 focus:outline-none focus:border-[#0B5D3B] resize-none"
                              placeholder={`${label}…`}
                              value={(draft as any)[key] || ''}
                              onChange={e => patchDraft(runId, { [key]: e.target.value } as any)}
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <button
                      onClick={() => handleSave(runId)}
                      disabled={savingId === runId}
                      className={`px-5 py-2.5 rounded-lg text-xs font-extrabold uppercase tracking-wider transition shadow-sm ${
                        savingId === runId
                          ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                          : 'bg-[#0B5D3B] hover:bg-[#08482E] text-white'
                      }`}
                    >
                      {savingId === runId ? 'Saving…' : 'Save Outcome & Lessons'}
                    </button>
                  </div>
                ) : null}
              </div>
            )
          })}
        </section>
      ) : null}

      {/* Tab: Outcome Intelligence */}
      {activeTab === 'intelligence' && intelligence ? (
        <section className="space-y-6">
          {/* Top Accuracy Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Total Decisions', value: intelligence.total_decisions, suffix: '', color: 'text-slate-900' },
              { label: 'Completed Outcomes', value: intelligence.completed_outcomes, suffix: '', color: 'text-[#004085]' },
              { label: 'Recommendation Accuracy', value: intelligence.completed_outcomes > 0 ? `${intelligence.recommendation_accuracy}%` : 'INSUFFICIENT EVIDENCE', suffix: '', color: 'text-[#027A48]' },
              { label: 'Trust Accuracy', value: intelligence.completed_outcomes > 0 ? `${intelligence.trust_accuracy}%` : 'INSUFFICIENT EVIDENCE', suffix: '', color: 'text-[#0B5D3B]' },
            ].map(card => (
              <div key={card.label} className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{card.label}</div>
                <div className={`text-xl font-black mt-1 ${card.color}`}>{card.value}</div>
              </div>
            ))}
          </div>

          {/* Decisions with outcomes */}
          <div className="bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas overflow-hidden">
            <div className="px-5 py-4 border-b border-[#DDE6F0]">
              <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">Completed Outcome Records</h2>
            </div>
            <div className="divide-y divide-[#DDE6F0]">
              {intelligence.decisions?.filter((d: any) => d.outcome_status && d.outcome_status !== 'Pending').length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm italic">
                  INSUFFICIENT EVIDENCE: No completed outcomes yet. Update decision statuses in the Decision History tab.
                </div>
              ) : intelligence.decisions?.filter((d: any) => d.outcome_status && d.outcome_status !== 'Pending').map((d: any) => (
                <div key={d.id} className="px-5 py-4 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-slate-900">{d.startup_name}</div>
                    <div className="text-xs text-slate-500">Prediction: <strong>{d.recommendation}</strong> · Score: <strong>{d.trust_score}/100</strong></div>
                    {d.what_happened ? <div className="text-xs text-slate-600 mt-1 italic">"{d.what_happened}"</div> : null}
                  </div>
                  <span className={`text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider shrink-0 ${OUTCOME_COLORS[d.outcome_status] || OUTCOME_COLORS['Pending']}`}>
                    {d.outcome_status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : activeTab === 'intelligence' ? (
        <div className="p-8 text-center text-slate-400 text-sm">Loading intelligence data…</div>
      ) : null}

      {/* Tab: Trust Calibration */}
      {activeTab === 'calibration' ? (
        <section className="space-y-6">
          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900 mb-1">Trust Score Predictive Analysis</h2>
            <p className="text-xs text-slate-600 mb-4">Measures whether trust scores issued at decision time accurately predicted real-world outcomes.</p>

            {intelligence?.calibration?.calibration_summary ? (
              <div className="p-4 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0] text-sm font-medium text-slate-700 mb-4">
                {intelligence.calibration.calibration_summary}
              </div>
            ) : null}

            <div className="space-y-3">
              {calibrationBins.map((bin: any) => {
                const rate = bin.success_rate as number
                const isPredictive = bin.is_predictive as boolean
                const barWidth = rate > 0 ? `${rate}%` : '5%'
                const barColor = isPredictive ? 'bg-[#12B76A]' : 'bg-[#F04438]'
                return (
                  <div key={bin.tier} className="p-4 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0]">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="text-xs font-extrabold text-slate-900">{bin.tier}</span>
                        <span className="text-[11px] text-slate-500 ml-2">
                          {bin.decision_count} decisions · {bin.successful_count} successful
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-black ${isPredictive ? 'text-[#027A48]' : 'text-[#B42318]'}`}>
                          {bin.decision_count === 0 ? 'INSUFFICIENT EVIDENCE' : `${rate}% success rate`}
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${isPredictive ? 'bg-[#ECFDF3] text-[#027A48]' : 'bg-[#FEF3F2] text-[#B42318]'}`}>
                          {bin.decision_count === 0 ? 'NO DATA' : isPredictive ? 'PREDICTIVE' : 'NOT PREDICTIVE'}
                        </span>
                      </div>
                    </div>
                    <div className="w-full bg-[#DDE6F0] rounded-full h-2">
                      <div className={`${barColor} h-2 rounded-full transition-all duration-500`} style={{ width: barWidth }} />
                    </div>
                  </div>
                )
              })}
            </div>

            {calibrationBins.every((b: any) => b.decision_count === 0) ? (
              <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-[10px] text-xs font-medium text-amber-800">
                INSUFFICIENT EVIDENCE: Update outcome statuses for completed decisions to generate trust calibration data.
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {/* Tab: MEAL Dashboard */}
      {activeTab === 'meal' ? (
        <section className="space-y-6">
          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900 mb-1">MEAL Framework Dashboard</h2>
            <p className="text-xs text-slate-600 mb-4">Monitoring, Evaluation, Accountability & Learning — computed from real decision and outcome data only.</p>

            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[#DDE6F0]">
                    <th className="text-left py-2 px-3 text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Indicator</th>
                    <th className="text-right py-2 px-3 text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Target</th>
                    <th className="text-right py-2 px-3 text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Actual</th>
                    <th className="text-right py-2 px-3 text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Variance</th>
                    <th className="text-right py-2 px-3 text-[10px] font-extrabold uppercase tracking-wider text-slate-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#DDE6F0]">
                  {mealsData.map(m => {
                    const variance = m.actual != null ? m.actual - m.target : null
                    const statusColors: Record<string, string> = {
                      'ON_TRACK': 'text-[#027A48] bg-[#ECFDF3]',
                      'AT_RISK': 'text-[#B54708] bg-[#FFFAEB]',
                      'OFF_TRACK': 'text-[#B42318] bg-[#FEF3F2]',
                      'INSUFFICIENT_EVIDENCE': 'text-slate-500 bg-slate-100',
                    }
                    return (
                      <tr key={m.id} className="hover:bg-[#F5F8FC]">
                        <td className="py-3 px-3 font-medium text-slate-900">{m.name}</td>
                        <td className="py-3 px-3 text-right font-mono text-slate-700">{m.target}{m.unit}</td>
                        <td className="py-3 px-3 text-right font-bold font-mono text-slate-900">
                          {m.actual != null ? `${m.actual}${m.unit}` : '—'}
                        </td>
                        <td className={`py-3 px-3 text-right font-mono ${variance != null && variance >= 0 ? 'text-[#027A48]' : 'text-[#B42318]'}`}>
                          {variance != null ? (variance >= 0 ? `+${variance}` : `${variance}`) : '—'}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${statusColors[m.status] || statusColors['INSUFFICIENT_EVIDENCE']}`}>
                            {m.status.replace(/_/g, ' ')}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {/* Tab: Decision Timeline */}
      {activeTab === 'timeline' ? (
        <section className="space-y-6">
          <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900 mb-1">Decision Intelligence Chain</h2>
            <p className="text-xs text-slate-600 mb-6">Visual map of the complete evidence-to-learning lifecycle. Every outcome traces back to its evidence and trust signal.</p>

            <div className="relative">
              {/* Vertical connector */}
              <div className="absolute left-7 top-8 bottom-8 w-0.5 bg-[#DDE6F0]" />

              <div className="space-y-4">
                {timelineStages.map((stage, idx) => {
                  const isCompleted = idx < 5
                  const isLast = idx === timelineStages.length - 1
                  return (
                    <div key={stage.stage} className="relative flex items-start gap-4 pl-0">
                      {/* Node circle */}
                      <div className={`relative z-10 w-14 h-14 rounded-full border-2 flex items-center justify-center text-lg shrink-0 ${
                        isLast ? 'bg-[#061C14] border-[#0B5D3B] shadow-lg' :
                        isCompleted ? 'bg-[#0B5D3B] border-[#17855A]' :
                        'bg-white border-[#DDE6F0]'
                      }`}>
                        {stage.icon}
                      </div>
                      {/* Content */}
                      <div className={`flex-1 p-4 rounded-[10px] border ${
                        isLast ? 'bg-[#061C14] border-[#0E3627]' :
                        isCompleted ? 'bg-[#ECFDF3] border-[#A6F4C5]' :
                        'bg-[#F5F8FC] border-[#DDE6F0]'
                      }`}>
                        <div className={`text-xs font-extrabold uppercase tracking-wider mb-1 ${isLast ? 'text-emerald-400' : isCompleted ? 'text-[#027A48]' : 'text-slate-500'}`}>
                          Stage {idx + 1}
                        </div>
                        <div className={`text-sm font-black ${isLast ? 'text-white' : 'text-slate-900'}`}>{stage.stage}</div>
                        <p className={`text-xs mt-1 leading-relaxed ${isLast ? 'text-emerald-300' : isCompleted ? 'text-[#065F46]' : 'text-slate-600'}`}>
                          {stage.description}
                        </p>
                        {isCompleted && (
                          <div className={`mt-2 text-[10px] font-bold uppercase tracking-wider ${isLast ? 'text-emerald-400' : 'text-[#027A48]'}`}>
                            ✓ IMPLEMENTED & LIVE
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </PilotWorkspaceShell>
  )
}
