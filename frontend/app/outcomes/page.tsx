'use client'

import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import TrustGauge from '../../components/TrustGauge/TrustGauge'
import OutcomeFollowup from '../../components/OutcomeFollowup/OutcomeFollowup'
import {
  getDecisionHistory,
  getDueFollowups,
  getOutcome,
  getOutcomeIntelligence,
  isDemoRunRecord,
  outcomeReviewDownloadHref,
  saveFollowupAnswer,
  saveOutcome,
  type DecisionRecord,
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

// Outcome Layer V1: the two 30-day follow-up questions.
const DECISION_TAKEN_OPTIONS = [
  { value: 'yes', label: 'Yes — decision taken' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'no', label: 'No — nothing decided yet' },
  { value: 'unknown', label: 'Unknown' },
]
const RECOMMENDATION_FOLLOWED_OPTIONS = [
  { value: 'fully', label: 'Fully followed' },
  { value: 'partially', label: 'Partially followed' },
  { value: 'no', label: 'Not followed / diverged' },
  { value: 'not_yet', label: 'Too early to tell' },
  { value: 'unknown', label: 'Unknown' },
]
const ANSWER_LABELS: Record<string, string> = Object.fromEntries(
  [...DECISION_TAKEN_OPTIONS, ...RECOMMENDATION_FOLLOWED_OPTIONS].map(o => [o.value, o.label]),
)

function _daysSince(iso: string | null): number | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  return Math.max(0, Math.floor((Date.now() - t) / 86_400_000))
}

/**
 * Verdict colouring for the registry. Each assessment profile words its verdict
 * differently (NGO → Strong Capacity, Programme → Ready, Government → Effective,
 * Tourism → Ready for Growth, Startup → Invest), so the colour follows the
 * meaning of the verdict — matching on the startup spelling alone would render a
 * positive NGO outcome red.
 */
function verdictBadge(recommendation: string | null | undefined): string {
  const v = String(recommendation || '').toLowerCase()
  if (!v) return 'bg-slate-100 text-slate-600 border border-slate-300'
  if (v.includes('co-invest') || v.includes('follow-on') || v.includes('observe') ||
      v.includes('review required') || v.includes('moderate') || v.includes('partial')) {
    return 'bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]'
  }
  if (v.includes('pass') || v.includes('weak') || v.includes('not ready') || v.includes('high risk')) {
    return 'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
  }
  if (v.includes('invest') || v.includes('ready') || v.includes('capacity') ||
      v.includes('effective') || v.includes('strong') || v.includes('exemplary')) {
    return 'bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]'
  }
  return 'bg-slate-100 text-slate-600 border border-slate-300'
}

function FollowUpCard({ record, onAnswered }: {
  record: DecisionRecord
  onAnswered: (updated: DecisionRecord) => void
}) {
  const [decisionTaken, setDecisionTaken] = useState('')
  const [followed, setFollowed] = useState('')
  const [comment, setComment] = useState('')
  const [outcomeStatus, setOutcomeStatus] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const canSave = decisionTaken !== '' && followed !== '' && !saving
  const daysSince = _daysSince(record.decisionSnapshotAt)

  // One-tap capture path: records the required pair instantly (followed =
  // too-early-to-tell, which rate math excludes honestly); the full form
  // below stays available for comments and outcome ratings.
  async function quickSubmit(taken: string) {
    setSaving(true)
    setErr(null)
    try {
      onAnswered(await saveFollowupAnswer(record.runId, { decisionTaken: taken, recommendationFollowed: 'not_yet', comment: '' }))
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  async function submit() {
    setSaving(true)
    setErr(null)
    try {
      const updated = await saveFollowupAnswer(record.runId, { decisionTaken, recommendationFollowed: followed, comment: comment.trim() })
      if (outcomeStatus) {
        // Merge with any stored outcome so rating the status never erases
        // notes or lessons recorded earlier.
        let base: OutcomeUpdatePayload = { outcome_status: outcomeStatus }
        try {
          const existing = await getOutcome(record.runId)
          base = {
            outcome_status: outcomeStatus,
            outcome_date: existing?.outcome_date || null,
            outcome_notes: existing?.outcome_notes || '',
            what_happened: existing?.what_happened || '',
            what_was_predicted: existing?.what_was_predicted || '',
            what_was_missed: existing?.what_was_missed || '',
            what_worked: existing?.what_worked || '',
            what_failed: existing?.what_failed || '',
          }
        } catch {
          // no outcome yet — status-only payload is fine
        }
        await saveOutcome(record.runId, base)
      }
      onAnswered(updated)
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white rounded-[12px] border border-[#FEDF89] shadow-saas p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-extrabold text-slate-900">
          {record.entityName || `Run #${record.runId}`}
          <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-wider bg-[#FFFAEB] text-[#B54708] border border-[#FEDF89]">
            Follow-up waiting
          </span>
        </div>
        <div className="text-xs text-slate-500">
          {daysSince !== null ? `Assessment completed ${daysSince} days ago` : 'Assessment completed'} · we recommended <strong className="text-slate-800">{record.recommendation || '—'}</strong>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500 leading-relaxed">
        We check in 30 days after every assessment to see whether the decision moved.
        Three quick fields — under a minute. Your answer appears next to this
        decision in the registry and in the Outcome Snapshot section of future report exports.
        Nothing is scored and nothing breaks if you skip it — the request just stays here until you answer.
      </p>
      {err ? <div className="mt-3 p-2 bg-red-50 text-red-700 border border-red-200 rounded-lg text-xs font-medium">{err}</div> : null}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Answer in one tap:</span>
        {[
          { v: 'yes', label: '✓ Decision taken' },
          { v: 'in_progress', label: '↻ Decision in progress' },
          { v: 'no', label: 'No decision yet' },
        ].map(o => (
          <button
            key={o.v}
            disabled={saving}
            onClick={() => quickSubmit(o.v)}
            className="text-[10px] px-2.5 py-1 rounded-full font-bold bg-white text-slate-700 border border-[#FEDF89] hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition disabled:opacity-50"
          >
            {o.label}
          </button>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">
            1. Was a decision taken?
          </label>
          <select
            className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm font-bold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
            value={decisionTaken}
            onChange={e => setDecisionTaken(e.target.value)}
          >
            <option value="">Select…</option>
            {DECISION_TAKEN_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">
            2. Was the recommendation followed?
          </label>
          <select
            className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm font-bold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
            value={followed}
            onChange={e => setFollowed(e.target.value)}
          >
            <option value="">Select…</option>
            {RECOMMENDATION_FOLLOWED_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
      <div className="mt-4">
        <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">
          3. Comments <span className="normal-case font-bold text-slate-400">(optional)</span>
        </label>
        <textarea
          className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:border-[#0B5D3B] resize-y min-h-[64px]"
          placeholder="What actually happened? Any context we should know about this decision…"
          value={comment}
          maxLength={2000}
          onChange={e => setComment(e.target.value)}
        />
      </div>
      <div className="mt-4">
        <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">
          4. Outcome <span className="normal-case font-bold text-slate-400">(if known — optional)</span>
        </label>
        <select
          className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm font-bold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
          value={outcomeStatus}
          onChange={e => setOutcomeStatus(e.target.value)}
        >
          <option value="">Not ready to rate yet</option>
          {OUTCOME_STATUSES.filter(s => s !== 'Completed').map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <button
        onClick={submit}
        disabled={!canSave}
        className={`mt-4 px-5 py-2.5 rounded-lg text-xs font-extrabold uppercase tracking-wider transition shadow-sm ${
          canSave ? 'bg-[#0B5D3B] hover:bg-[#08482E] text-white' : 'bg-slate-200 text-slate-400 cursor-not-allowed'
        }`}
      >
        {saving ? 'Saving…' : 'Save & done'}
      </button>
    </div>
  )
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
  // Outcome Layer V1: 30-day follow-up queue
  const [dueFollowups, setDueFollowups] = useState<DecisionRecord[]>([])
  const focusConsumed = useRef(false)

  // Deep link from any follow-up reminder (/outcomes?focus=<run_id>): open
  // that decision's row and scroll it into view — one click from banner to
  // the update form. Consumed once so re-renders never re-steal the view.
  useEffect(() => {
    if (focusConsumed.current || decisions.length === 0) return
    const focus = new URLSearchParams(window.location.search).get('focus')
    if (!focus) return
    focusConsumed.current = true
    const id = Number(focus)
    if (!Number.isNaN(id)) {
      setActiveTab('history')
      setExpandedId(id)
      setTimeout(() => {
        document.getElementById(`decision-row-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 150)
    }
  }, [decisions])

  // Phase 6 — Pilot Health: adoption metrics computed from the decision
  // registry rows only (no new backend fields, no inferred data). Empty
  // measures print NO DATA rather than a fabricated zero-percent.
  const pilotHealth = useMemo(() => {
    const dayMs = 86_400_000
    const total = decisions.length
    const answeredRows = decisions.filter(d => d.followup_status === 'answered')
    const ratedRows = decisions.filter(d => ['Successful', 'Partially Successful', 'Unsuccessful'].includes(d.outcome_status))
    const diffs = (rows: any[], from: (d: any) => string | null, to: (d: any) => string | null): number[] =>
      rows.map(d => {
        const a = from(d), b = to(d)
        if (!a || !b) return null
        const v = Math.round((new Date(b).getTime() - new Date(a).getTime()) / dayMs)
        return Number.isNaN(v) ? null : Math.max(0, v)
      }).filter((x): x is number => x != null).sort((a, b) => a - b)
    const ff = diffs(answeredRows, d => d.decision_snapshot_at || d.followup_due_at || d.created_at, d => d.answered_at)
    const velocity = diffs(answeredRows.filter(d => d.decision_taken === 'yes'), d => d.created_at, d => d.answered_at)
    // Decision Followed Rate: fully/partially ÷ decidable answers. not_yet and
    // unknown are excluded from the denominator — never counted as "not followed".
    const decidable = answeredRows.filter(d => ['fully', 'partially', 'no'].includes(d.recommendation_followed))
    const followed = decidable.filter(d => d.recommendation_followed === 'fully' || d.recommendation_followed === 'partially')
    const avg = (xs: number[]) => xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length * 10) / 10 : null
    const median = (xs: number[]) => xs.length ? xs[Math.floor(xs.length / 2)] : null
    return {
      total,
      answered: answeredRows.length,
      rated: ratedRows.length,
      captureRate: total ? Math.round(answeredRows.length / total * 100) : null,
      followedRate: decidable.length ? Math.round(followed.length / decidable.length * 100) : null,
      followedSample: decidable.length,
      avgFollowUpDays: avg(ff),
      followUpSample: ff.length,
      velocityDays: median(velocity),
      velocitySample: velocity.length,
    }
  }, [decisions])

  // Local mutation state for outcome updates
  const [draftOutcomes, setDraftOutcomes] = useState<Record<number, OutcomeUpdatePayload>>({})

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [hist, intel, due] = await Promise.all([
        getDecisionHistory(100),
        getOutcomeIntelligence(),
        getDueFollowups(),
      ])
      setDecisions(hist.decisions.filter(decision => !isDemoRunRecord({
        runId: decision.run_id || decision.id || '',
        startupName: decision.startup_name || decision.startupName,
        userId: decision.user_id,
      })))
      setIntelligence(intel)
      setDueFollowups(due.followups)
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
    // Derive MEAL-like indicators from the decisions corpus. Counts come from
    // recorded outcomes only; an indicator with no data reads null and renders
    // as NO DATA. Targets belong to the institution's own logframe, so the
    // platform never invents one here.
    const total = decisions.length
    const rated = decisions.filter(d => d.outcome_status && d.outcome_status !== 'Pending').length
    const successful = decisions.filter(d => d.outcome_status === 'Successful').length
    const partSuccessful = decisions.filter(d => d.outcome_status === 'Partially Successful').length
    const unsuccessful = decisions.filter(d => d.outcome_status === 'Unsuccessful').length
    const unrated = total - rated
    // Average only over decisions that actually carry a trust score — treating a
    // missing score as zero would depress the average with an invented figure.
    const scored = decisions.map(d => Number(d.trust_score)).filter(n => Number.isFinite(n) && n > 0)
    const avgTrust = scored.length > 0 ? Math.round(scored.reduce((s, n) => s + n, 0) / scored.length) : null
    const noOutcomes = rated === 0 ? 'INSUFFICIENT_EVIDENCE' : ''
    return [
      { id: 'dec_total', name: 'Decisions recorded', target: null, actual: total, unit: '', status: total > 0 ? 'ON_TRACK' : 'INSUFFICIENT_EVIDENCE' },
      { id: 'dec_success', name: 'Outcomes rated successful', target: null, actual: successful, unit: '', status: noOutcomes || (successful > 0 ? 'ON_TRACK' : 'OFF_TRACK') },
      { id: 'dec_partial', name: 'Outcomes rated partially successful', target: null, actual: partSuccessful, unit: '', status: noOutcomes || (partSuccessful > 0 ? 'AT_RISK' : 'ON_TRACK') },
      { id: 'dec_fail', name: 'Outcomes rated unsuccessful', target: null, actual: unsuccessful, unit: '', status: noOutcomes || (unsuccessful === 0 ? 'ON_TRACK' : 'OFF_TRACK') },
      { id: 'dec_pending', name: 'Decisions with no outcome recorded yet', target: null, actual: unrated, unit: '', status: total === 0 ? 'INSUFFICIENT_EVIDENCE' : unrated > 0 ? 'AT_RISK' : 'ON_TRACK' },
      { id: 'avg_trust', name: 'Average trust score at decision', target: null, actual: avgTrust, unit: '/100', status: avgTrust == null ? 'INSUFFICIENT_EVIDENCE' : avgTrust >= 80 ? 'ON_TRACK' : avgTrust >= 60 ? 'AT_RISK' : 'OFF_TRACK' },
    ]
  }, [decisions])

  const timelineStages = useMemo(() => [
    {
      stage: 'Information',
      svgPath: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
      description: 'Reports, programme documents, surveys and public sources collected for each entity.',
    },
    {
      stage: 'Evidence',
      svgPath: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
      description: 'Structured document ingestion, chunk extraction, source attribution.',
    },
    {
      stage: 'Trust',
      svgPath: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
      description: 'Deterministic 4-factor scoring: Source Reliability, Corroboration, Recency, Completeness.',
    },
    {
      stage: 'Signals',
      svgPath: 'M13 10V3L4 14h7v7l9-11h-7z',
      description: 'Automated Risk, Opportunity, and Anomaly extraction from evidence corpus.',
    },
    {
      stage: 'Decision',
      svgPath: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
      description: 'Decision verdict in the language of the institution — capacity, programme performance, or investment — with rationale and evidence basis.',
    },
    {
      stage: 'Outcome',
      svgPath: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
      description: 'Actual real-world result: Successful / Partially Successful / Unsuccessful.',
    },
    {
      stage: 'Learning',
      svgPath: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
      description: 'Trust calibration, accuracy measurement, lessons extracted for future decisions.',
    },
  ], [])

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
      title="Outcome Intelligence"
      description="Track real-world results, calibrate trust scores, and close the evidence-to-learning feedback loop."
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div> : null}
      {loading && activeTab !== 'history' ? (
        <div className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-[#0B5D3B] animate-pulse" />
          <span className="text-sm font-semibold text-slate-500">Loading outcome data…</span>
        </div>
      ) : null}
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
          {/* Pilot Health — adoption metrics (capture rate, days to follow-up,
              decision velocity). Honest empties: NO DATA until rows exist. */}
          <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700">Pilot Health</h2>
              <span className="text-[10px] text-slate-400 font-semibold">{pilotHealth.total} decisions tracked</span>
            </div>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="p-3 rounded-lg bg-[#F5F8FC] border border-[#DDE6F0]">
                <div className="text-lg font-black text-[#0B5D3B]">{pilotHealth.captureRate !== null ? `${pilotHealth.captureRate}%` : 'NO DATA'}</div>
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mt-0.5">Outcome capture rate</div>
                <div className="text-[10px] text-slate-400">{pilotHealth.answered}/{pilotHealth.total} decisions answered the follow-up</div>
              </div>
              <div className="p-3 rounded-lg bg-[#F5F8FC] border border-[#DDE6F0]">
                <div className="text-lg font-black text-[#0B5D3B]">{pilotHealth.followedRate !== null ? `${pilotHealth.followedRate}%` : 'NO DATA'}</div>
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mt-0.5">Decision followed rate</div>
                <div className="text-[10px] text-slate-400">fully/partially of decidable answers (n={pilotHealth.followedSample})</div>
              </div>
              <div className="p-3 rounded-lg bg-[#F5F8FC] border border-[#DDE6F0]">
                <div className="text-lg font-black text-[#0B5D3B]">{pilotHealth.rated} <span className="text-xs font-bold text-slate-500">/ {pilotHealth.total}</span></div>
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mt-0.5">Outcomes rated</div>
                <div className="text-[10px] text-slate-400">Successful · Partially · Unsuccessful</div>
              </div>
              <div className="p-3 rounded-lg bg-[#F5F8FC] border border-[#DDE6F0]">
                <div className="text-lg font-black text-[#0B5D3B]">{pilotHealth.avgFollowUpDays !== null ? `${pilotHealth.avgFollowUpDays}d` : 'NO DATA'}</div>
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mt-0.5">Days to follow-up</div>
                <div className="text-[10px] text-slate-400">avg after the window opened (n={pilotHealth.followUpSample})</div>
              </div>
              <div className="p-3 rounded-lg bg-[#F5F8FC] border border-[#DDE6F0]">
                <div className="text-lg font-black text-[#0B5D3B]">{pilotHealth.velocityDays !== null ? `${pilotHealth.velocityDays}d` : 'NO DATA'}</div>
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mt-0.5">Decision velocity</div>
                <div className="text-[10px] text-slate-400">median: assessment → decision confirmed (n={pilotHealth.velocitySample})</div>
              </div>
            </div>
          </div>
          {dueFollowups.length > 0 ? (
            <div className="space-y-3">
              <div className="p-4 rounded-[12px] bg-[#FFFAEB] border border-[#FEDF89]">
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-[#B54708]">
                  30-Day Follow-ups Waiting ({dueFollowups.length})
                </h2>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                  These assessments were completed more than 30 days ago. Help us learn whether
                  the recommendation worked — just two questions each: <strong>was a decision
                  taken</strong>, and <strong>was the recommendation followed</strong>.
                  Answers are stored with the decision and shown in report exports. They are
                  optional: ignoring them blocks nothing, and the request stays in this queue.
                </p>
              </div>
              {dueFollowups.map(f => (
                <FollowUpCard
                  key={f.runId}
                  record={f}
                  onAnswered={updated => {
                    setDueFollowups(prev => prev.filter(x => x.runId !== updated.runId))
                    setSaveSuccess(`Follow-up recorded for ${updated.entityName || `run #${updated.runId}`}`)
                    loadAll().catch(() => {})
                  }}
                />
              ))}
            </div>
          ) : null}
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-700">
              Decision Registry ({decisions.length} records)
            </h2>
            {loading ? <span className="text-xs text-slate-500 animate-pulse">Loading…</span> : null}
          </div>

          {decisions.length === 0 && !loading ? (
            <div className="p-8 text-center bg-white rounded-[12px] border border-dashed border-[#DDE6F0] text-slate-500 text-sm font-medium">
              No decisions recorded yet. Complete an assessment and its decision will appear here.
            </div>
          ) : null}

          {decisions.map(d => {
            const runId = d.id as number
            const isOpen = expandedId === runId
            const draft = getDraft(runId)
            return (
              <div key={runId} id={`decision-row-${runId}`} className="bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas overflow-hidden">
                {/* Row header */}
                <button
                  className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#F5F8FC] transition text-left"
                  onClick={() => setExpandedId(isOpen ? null : runId)}
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <span className="text-xs font-mono text-slate-400 shrink-0">#{runId}</span>
                    <div className="min-w-0">
                      <div className="text-sm font-extrabold text-slate-900 truncate">{d.startup_name}</div>
                      <div className="text-xs text-slate-500 truncate">
                        {[d.founder_name ? `Lead: ${d.founder_name}` : null,
                          d.created_at && !Number.isNaN(new Date(d.created_at).getTime())
                            ? new Date(d.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
                            : 'Date not recorded'].filter(Boolean).join(' · ')}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider ${verdictBadge(d.recommendation)}`}>
                      {d.recommendation || 'Decision pending'}
                    </span>
                    <span
                      className={`text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider ${OUTCOME_COLORS[d.outcome_status || 'Pending'] || OUTCOME_COLORS['Pending']}`}
                      title="Outcome status: recorded only once someone closes the loop on this decision. Nothing here is estimated."
                    >
                      {d.outcome_status || 'No Outcome Recorded'}
                    </span>
                    {d.followup_status === 'answered' ? (
                      <span
                        className="text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]"
                        title={`Follow-up: ${ANSWER_LABELS[d.decision_taken] || d.decision_taken} · ${ANSWER_LABELS[d.recommendation_followed] || d.recommendation_followed}`}
                      >
                        Follow-up ✓
                      </span>
                    ) : null}
                    <TrustGauge score={d.trust_score ?? null} size="sm" showLabel={false} />
                    <svg className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Phase 4: recorded follow-up + outcome readable without
                    expanding — the registry itself tells the story. */}
                {!isOpen && (d.followup_status === 'answered' || d.what_happened) ? (
                  <div className="px-5 pb-3 -mt-1 text-xs text-slate-600 leading-relaxed">
                    {d.followup_status === 'answered' ? (
                      <span>
                        ✓ {ANSWER_LABELS[d.decision_taken] || d.decision_taken} · {ANSWER_LABELS[d.recommendation_followed] || d.recommendation_followed}
                      </span>
                    ) : null}
                    {d.what_happened ? (
                      <span className={d.followup_status === 'answered' ? ' ml-2' : ''}>
                        {String(d.what_happened).length > 140 ? `${String(d.what_happened).slice(0, 140)}…` : d.what_happened}
                      </span>
                    ) : d.decision_comment ? (
                      <span className={d.followup_status === 'answered' ? ' ml-2' : ''}>
                        “{String(d.decision_comment).length > 140 ? `${String(d.decision_comment).slice(0, 140)}…` : d.decision_comment}”
                      </span>
                    ) : null}
                  </div>
                ) : null}

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

                    {/* Outcome Layer V1: Decision follow-up — view, inline
                        update, and recorded review in one surface. Outcome
                        status stays owned by the editor above (no duplicate). */}
                    <div className="p-3 rounded-lg bg-white border border-[#DDE6F0]">
                      <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">Decision Outcome (30-day follow-up)</div>
                      <OutcomeFollowup runId={runId} showOutcomeSelect={false} compact />
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

                    <div className="flex flex-wrap items-center gap-3">
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
                      {/* The Outcome Review Report exists only once an outcome has
                          been rated — before that there would be nothing to review. */}
                      {d.outcome_status && d.outcome_status !== 'Pending' ? (
                        <a
                          href={outcomeReviewDownloadHref(runId, 'pdf')}
                          className="px-4 py-2.5 rounded-lg text-xs font-extrabold uppercase tracking-wider border border-[#DDE6F0] bg-white text-slate-700 hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition"
                          title="Outcome Review Report: the recommendation, the decision taken, what happened, and the lessons recorded here."
                        >
                          ↓ Outcome Review Report
                        </a>
                      ) : null}
                    </div>
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
          {/* Top accuracy cards — every figure carries its own definition. */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Decisions Recorded', value: String(intelligence.total_decisions), hint: 'Every decision written in this workspace, whether or not an outcome has been recorded against it yet.', color: 'text-slate-900' },
              { label: 'Outcomes Recorded', value: String(intelligence.completed_outcomes), hint: 'Decisions where someone has closed the loop and recorded what actually happened.', color: 'text-[#004085]' },
              {
                label: 'Recorded Outcomes That Worked',
                value: intelligence.recommendation_accuracy != null ? `${intelligence.recommendation_accuracy}%` : 'NOT MEASURED',
                hint: 'Of the decisions with a recorded outcome, how many were logged Successful or Partially Successful. Nothing is estimated: with no recorded outcomes this reads NOT MEASURED.',
                color: 'text-[#027A48]',
              },
              {
                label: 'High-Trust Outcomes That Worked',
                value: intelligence.trust_accuracy != null ? `${intelligence.trust_accuracy}%` : 'NOT MEASURED',
                hint: 'Success rate of the High Trust band (trust score 80–100) among recorded outcomes. This is the number that tests the Trust Layer itself — it stays unmeasured until real outcomes accumulate.',
                color: 'text-[#0B5D3B]',
              },
            ].map(card => (
              <div key={card.label} className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas" title={card.hint}>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 leading-tight">{card.label}</div>
                <div className={`text-xl font-black mt-1 ${card.color}`}>{card.value}</div>
                <div className="text-[10px] text-slate-400 mt-1.5 leading-snug">{card.hint}</div>
              </div>
            ))}
          </div>

          {/* Decisions with outcomes */}
          <div className="bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas overflow-hidden">
            <div className="px-5 py-4 border-b border-[#DDE6F0]">
              <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900">Completed Outcome Records</h2>
              <p className="text-[11px] text-slate-500 mt-1">What was recommended, the trust score behind it, and what was recorded as having happened.</p>
            </div>
            <div className="divide-y divide-[#DDE6F0]">
              {intelligence.decisions?.filter((d: any) => d.outcome_status && d.outcome_status !== 'Pending').length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm italic">
                  INSUFFICIENT EVIDENCE: No outcomes have been recorded yet. Record one against a decision in the Decision Registry and it appears here.
                </div>
              ) : intelligence.decisions?.filter((d: any) => d.outcome_status && d.outcome_status !== 'Pending').map((d: any) => (
                <div key={d.id} className="px-5 py-4 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-slate-900">{d.startup_name}</div>
                    <div className="text-xs text-slate-500">
                      Recommendation: <strong>{d.recommendation || 'not recorded'}</strong>
                      {' '}· Trust at decision time:{' '}
                      <strong>{d.trust_score != null ? `${d.trust_score}/100` : 'not scored'}</strong>
                    </div>
                    {d.what_happened ? <div className="text-xs text-slate-600 mt-1 italic">&ldquo;{d.what_happened}&rdquo;</div> : null}
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
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-900 mb-1">Did Our Trust Scores Predict What Happened?</h2>
            <p className="text-xs text-slate-600 mb-1">
              Decisions are grouped by the trust score they were given, then compared with the outcome actually recorded for each one.
              &quot;Successful&quot; means an outcome was recorded as Successful or Partially Successful — nothing is inferred or projected.
            </p>
            <p className="text-[11px] text-slate-400 mb-4">
              A band needs roughly ten completed outcomes before its rate describes a pattern; below that it is a small-sample observation only.
            </p>

            {intelligence?.calibration?.calibration_summary ? (
              <div className="p-4 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0] text-sm font-medium text-slate-700 mb-4">
                {intelligence.calibration.calibration_summary}
              </div>
            ) : null}

            <div className="space-y-3">
              {calibrationBins.map((bin: any) => {
                const rate = bin.success_rate as number
                const isPredictive = bin.is_predictive as boolean
                // Calibration is only meaningful once outcomes are COMPLETED —
                // decisions without outcomes must read NO DATA, never a rate.
                const completed = bin.completed_count ?? 0
                const hasOutcomes = completed > 0
                const barWidth = rate > 0 ? `${rate}%` : '5%'
                const barColor = isPredictive ? 'bg-[#12B76A]' : 'bg-[#F04438]'
                return (
                  <div key={bin.tier} className="p-4 bg-[#F5F8FC] rounded-[10px] border border-[#DDE6F0]">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="text-xs font-extrabold text-slate-900">{bin.tier}</span>
                        <span className="text-[11px] text-slate-500 ml-2">
                          {bin.decision_count} decisions · {completed} with a recorded outcome · {bin.successful_count} successful
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-black ${!hasOutcomes ? 'text-slate-500' : isPredictive ? 'text-[#027A48]' : 'text-[#B42318]'}`}>
                          {!hasOutcomes ? 'NO COMPLETED OUTCOMES' : `${rate}% success rate`}
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${!hasOutcomes ? 'bg-slate-100 text-slate-600 border border-slate-200' : isPredictive ? 'bg-[#ECFDF3] text-[#027A48]' : 'bg-[#FEF3F2] text-[#B42318]'}`}>
                          {!hasOutcomes ? 'NOT MEASURED' : isPredictive ? 'PREDICTIVE' : 'NOT PREDICTIVE'}
                        </span>
                      </div>
                    </div>
                    {hasOutcomes ? (
                      <div className="w-full bg-[#DDE6F0] rounded-full h-2">
                        <div className={`${barColor} h-2 rounded-full transition-all duration-500`} style={{ width: barWidth }} />
                      </div>
                    ) : (
                      <div className="text-[10px] text-slate-400 italic">
                        No bar is drawn: this band has no recorded outcomes yet, so there is nothing to plot.
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {calibrationBins.every((b: any) => (b.completed_count ?? b.decision_count ?? 0) === 0) ? (
              <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-[10px] text-xs font-medium text-amber-800">
                INSUFFICIENT EVIDENCE: No outcomes have been recorded yet, so trust calibration cannot be measured. Record outcomes against completed decisions and this analysis fills itself in.
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
            <p className="text-xs text-slate-600 mb-4">Monitoring, Evaluation, Accountability &amp; Learning — computed from real decision and outcome data only.</p>

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
                    // Variance only exists against a target the institution set;
                    // without one it reads '—' rather than an implied judgement.
                    const variance = m.actual != null && m.target != null ? m.actual - m.target : null
                    const statusColors: Record<string, string> = {
                      'ON_TRACK': 'text-[#027A48] bg-[#ECFDF3]',
                      'AT_RISK': 'text-[#B54708] bg-[#FFFAEB]',
                      'OFF_TRACK': 'text-[#B42318] bg-[#FEF3F2]',
                      'INSUFFICIENT_EVIDENCE': 'text-slate-500 bg-slate-100',
                    }
                    return (
                      <tr key={m.id} className="hover:bg-[#F5F8FC]">
                        <td className="py-3 px-3 font-medium text-slate-900">{m.name}</td>
                        <td className="py-3 px-3 text-right font-mono text-slate-500">
                          {m.target != null ? `${m.target}${m.unit}` : 'not set'}
                        </td>
                        <td className="py-3 px-3 text-right font-bold font-mono text-slate-900">
                          {m.actual != null ? `${m.actual}${m.unit}` : 'NO DATA'}
                        </td>
                        <td className={`py-3 px-3 text-right font-mono ${variance != null && variance >= 0 ? 'text-[#027A48]' : 'text-slate-400'}`}>
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
            <p className="mt-3 text-[11px] text-slate-500 leading-relaxed">
              Every figure above is counted from recorded decisions and recorded outcomes — nothing is projected.
              <strong className="font-bold text-slate-700"> Target</strong> reads <em>not set</em> because delivery targets
              belong to your logframe, not to the platform; statuses compare what happened against what was rated,
              and show <em>insufficient evidence</em> until outcomes are recorded.
            </p>
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
                      <div className={`relative z-10 w-14 h-14 rounded-full border-2 flex items-center justify-center shrink-0 ${
                        isLast ? 'bg-[#061C14] border-[#0B5D3B] shadow-lg' :
                        isCompleted ? 'bg-[#0B5D3B] border-[#17855A]' :
                        'bg-white border-[#DDE6F0]'
                      }`}>
                        <svg className={`w-6 h-6 ${isLast ? 'text-emerald-400' : isCompleted ? 'text-white' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d={stage.svgPath} />
                        </svg>
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
