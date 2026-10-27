'use client'

/*
 * Outcome Layer V1 — Adoption surface (no new data model).
 *
 * One component, four visibility states, rendered wherever a decision lives:
 * Decision workspace, Reports, Dashboard rows, AI Analyst, Assessment cards.
 *
 *   answered + rated outcome  → inline outcome review (what happened, lessons)
 *   answered, outcome unknown → one-click outcome chips (Pending…Unsuccessful)
 *   pending, due date passed  → amber "Decision Follow-Up Due" + one-click form
 *   pending, before due date  → quiet single line with days remaining
 *
 * The update form captures the full V1 journey in one save:
 * Decision Taken · Recommendation Followed · Comments · Outcome → Save → Done.
 * Every state is best-effort: a failed fetch renders nothing — the follow-up
 * must never block or break the page it is surfaced on.
 */

import React, { useEffect, useMemo, useState } from 'react'
import {
  getDecisionHistory,
  getDecisionRecord,
  getOutcome,
  outcomeReviewDownloadHref,
  saveFollowupAnswer,
  saveOutcome,
  type DecisionRecord,
  type OutcomeUpdatePayload,
} from '../../lib/api'

const DECISION_TAKEN_OPTIONS = [
  { value: 'yes', label: 'Yes — decision taken' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'no', label: 'No — nothing decided yet' },
  { value: 'unknown', label: 'Unknown' },
]
const FOLLOWED_OPTIONS = [
  { value: 'fully', label: 'Fully followed' },
  { value: 'partially', label: 'Partially followed' },
  { value: 'no', label: 'Not followed / diverged' },
  { value: 'not_yet', label: 'Too early to tell' },
  { value: 'unknown', label: 'Unknown' },
]
const ANSWER_LABELS: Record<string, string> = Object.fromEntries(
  [...DECISION_TAKEN_OPTIONS, ...FOLLOWED_OPTIONS].map(o => [o.value, o.label]),
)
const OUTCOME_CHIPS = ['Successful', 'Partially Successful', 'Unsuccessful', 'In Progress', 'Pending']
const RATED_OUTCOMES = ['Successful', 'Partially Successful', 'Unsuccessful']

function _isNumericRun(runId?: string | number | null): boolean {
  return runId != null && /^\d+$/.test(String(runId))
}

function _daysBetween(fromIso: string | null | undefined, toMs: number): number | null {
  if (!fromIso) return null
  const t = new Date(fromIso).getTime()
  if (Number.isNaN(t)) return null
  return Math.round((toMs - t) / 86_400_000)
}

// ── Batch chip for list surfaces (Assessments cards etc.) ───────────────────
// Built from a decision-history row (getDecisionHistory), so a whole list
// needs one API call — no per-card fetches.

export type FollowupRowState = {
  kind: 'answered' | 'due' | 'upcoming' | 'none'
  days: number | null   // days overdue when kind==='due'; days remaining when 'upcoming'
  outcomeStatus?: string
  label: string
}

export function followupStateFromRow(row: Record<string, any> | undefined): FollowupRowState {
  if (!row) return { kind: 'none', days: null, label: '' }
  if (row.followup_status === 'answered') {
    const status = row.outcome_status && row.outcome_status !== 'Pending' ? String(row.outcome_status) : undefined
    return {
      kind: 'answered',
      days: null,
      outcomeStatus: status,
      label: status ? `Followed up · ${status}` : 'Followed up ✓',
    }
  }
  const due = _daysBetween(row.followup_due_at, Date.now())
  if (due !== null && due >= 0) return { kind: 'due', days: due, label: due === 0 ? 'Follow-up due today' : `Follow-up due ${due}d ago` }
  if (due !== null) return { kind: 'upcoming', days: -due, label: `Follow-up in ${-due}d` }
  return { kind: 'none', days: null, label: '' }
}

const CHIP_TONES: Record<FollowupRowState['kind'], string> = {
  answered: 'bg-[#EAF3FF] text-[#004085] border-[#D6E8FF]',
  due: 'bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]',
  upcoming: 'bg-slate-50 text-slate-500 border-[#DDE6F0]',
  none: 'bg-slate-50 text-slate-400 border-[#DDE6F0]',
}

export function FollowupChip({ runId, state }: { runId: number | string; state: FollowupRowState }) {
  if (state.kind === 'none') return null
  return (
    <a
      href={`/outcomes?focus=${encodeURIComponent(String(runId))}`}
      className={`text-[9px] px-2 py-0.5 rounded-full font-black uppercase tracking-wider border shrink-0 hover:opacity-80 transition ${CHIP_TONES[state.kind]}`}
      title={state.kind === 'due' ? 'Open the follow-up form' : state.kind === 'answered' ? 'View recorded follow-up' : 'Follow-up window not open yet'}
    >
      {state.label}
    </a>
  )
}

// ── Workspace header chip ───────────────────────────────────────────────────
// Rendered inside PilotWorkspaceShell, so every surface a user naturally
// returns to (Flex workspace, Signals, Research, Evidence, Feedback, Decision,
// Reports) carries the follow-up state without any page-level wiring.
// Deliberately reads the batch history endpoint instead of the record
// endpoint: showing a header must never lazily CREATE a decision record.

export function FollowupHeaderChip({ runId }: { runId?: string | number | null }) {
  const [state, setState] = useState<FollowupRowState | null>(null)
  useEffect(() => {
    setState(null)
    if (!_isNumericRun(runId)) return
    let cancelled = false
    getDecisionHistory(200)
      .then(h => {
        if (cancelled) return
        const row = (h.decisions || []).find(d => String(d.id) === String(runId))
        // No row, or row without a decision record → nothing to show yet.
        if (row && row.followup_status) setState(followupStateFromRow(row))
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [runId])
  if (!state || state.kind === 'none' || !_isNumericRun(runId)) return null
  return (
    <a
      href={`/outcomes?focus=${encodeURIComponent(String(runId))}`}
      className={`px-2.5 py-1 rounded-lg text-[10px] font-extrabold uppercase tracking-wider border shrink-0 hover:opacity-80 transition ${CHIP_TONES[state.kind]}`}
      title={state.kind === 'due' ? 'Decision follow-up is due — record it now' : state.kind === 'answered' ? 'Follow-up recorded — view or update' : state.label}
    >
      {state.kind === 'due' ? '⏳ Follow-Up Due' : state.label}
    </a>
  )
}

// ── Panel surface ───────────────────────────────────────────────────────────

type Props = {
  runId?: string | number | null
  /** Show the Outcome select inside the update form (hide when the surrounding
   *  UI already owns outcome editing, e.g. the outcomes registry row editor). */
  showOutcomeSelect?: boolean
  /** Compact rendering inside cards (no outer white card wrapper). */
  compact?: boolean
  onSaved?: () => void
}

export default function OutcomeFollowup({ runId, showOutcomeSelect = true, compact = false, onSaved }: Props) {
  const [record, setRecord] = useState<DecisionRecord | null>(null)
  const [outcome, setOutcome] = useState<Record<string, any> | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  // Form state
  const [decisionTaken, setDecisionTaken] = useState('')
  const [followed, setFollowed] = useState('')
  const [comment, setComment] = useState('')
  const [outcomeStatus, setOutcomeStatus] = useState('')

  useEffect(() => {
    setRecord(null)
    setOutcome(null)
    setEditing(false)
    setErr(null)
    if (!_isNumericRun(runId)) return
    let cancelled = false
    // Best-effort: any failure leaves the surface invisible rather than broken.
    getDecisionRecord(runId as string | number)
      .then(rec => {
        if (cancelled) return
        setRecord(rec)
        setDecisionTaken(rec.decisionTaken || '')
        setFollowed(rec.recommendationFollowed || '')
        setComment(rec.decisionComment || '')
      })
      .catch(() => {})
    getOutcome(runId as string | number)
      .then(o => { if (!cancelled) setOutcome(o || null) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [runId])

  const state = useMemo(() => {
    if (!record) return null
    const overdueDays = _daysBetween(record.followupDueAt, Date.now())
    const answered = record.followupStatus === 'answered'
    const rated = RATED_OUTCOMES.includes(outcome?.outcome_status || '')
    return { answered, overdueDays, rated }
  }, [record, outcome])

  async function persist(target?: Partial<OutcomeUpdatePayload>) {
    if (!record) return
    setSaving(true)
    setErr(null)
    try {
      if (target || outcomeStatus) {
        // Merge with the stored outcome so a status-only click never erases
        // existing notes or lessons.
        const base: OutcomeUpdatePayload = {
          outcome_status: outcome?.outcome_status || 'Pending',
          outcome_date: outcome?.outcome_date || null,
          outcome_notes: outcome?.outcome_notes || '',
          what_happened: outcome?.what_happened || '',
          what_was_predicted: outcome?.what_was_predicted || '',
          what_was_missed: outcome?.what_was_missed || '',
          what_worked: outcome?.what_worked || '',
          what_failed: outcome?.what_failed || '',
        }
        await saveOutcome(record.runId, { ...base, ...(target || { outcome_status: outcomeStatus }) })
        setOutcome(prev => ({ ...(prev || {}), ...(target || { outcome_status: outcomeStatus }) }))
      }
      if (target === undefined) {
        const updated = await saveFollowupAnswer(record.runId, {
          decisionTaken: decisionTaken || 'unknown',
          recommendationFollowed: followed || 'unknown',
          comment: comment.trim(),
        })
        setRecord(updated)
        setEditing(false)
      }
      onSaved?.()
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  function openForm() {
    setEditing(true)
    setErr(null)
  }

  // One-tap capture: the two required answers saved directly, so a returning
  // user records the decision state in under 30 seconds and can refine the
  // comment/outcome later through Update. "not_yet" stays honest — it is
  // excluded from followed-rate denominators, never counted as "not followed".
  async function quickSave(taken: string) {
    if (!record) return
    setSaving(true)
    setErr(null)
    try {
      const updated = await saveFollowupAnswer(record.runId, {
        decisionTaken: taken,
        recommendationFollowed: 'not_yet',
        comment: '',
      })
      setRecord(updated)
      setDecisionTaken(updated.decisionTaken || '')
      setFollowed(updated.recommendationFollowed || '')
      setComment(updated.decisionComment || '')
      onSaved?.()
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  if (!record || !state) return null

  const wrapper = compact ? '' : 'bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas'

  // ── Update form (shared by due banner and answered→edit) ──
  const form = (
    <div className="mt-3 space-y-3">
      {err ? <div className="p-2 bg-red-50 text-red-700 border border-red-200 rounded-lg text-xs font-medium">{err}</div> : null}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">1. Was a decision taken?</label>
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
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">2. Was the recommendation followed?</label>
          <select
            className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm font-bold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
            value={followed}
            onChange={e => setFollowed(e.target.value)}
          >
            <option value="">Select…</option>
            {FOLLOWED_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">
          3. Comments <span className="normal-case font-bold text-slate-400">(optional)</span>
        </label>
        <textarea
          className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:border-[#0B5D3B] resize-y min-h-[56px]"
          placeholder="What actually happened…"
          value={comment}
          maxLength={2000}
          onChange={e => setComment(e.target.value)}
        />
      </div>
      {showOutcomeSelect ? (
        <div>
          <label className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-1">
            4. Outcome <span className="normal-case font-bold text-slate-400">(if known — optional)</span>
          </label>
          <select
            className="w-full p-2 border border-[#DDE6F0] rounded-lg bg-white text-sm font-bold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
            value={outcomeStatus}
            onChange={e => setOutcomeStatus(e.target.value)}
          >
            <option value="">Not ready to rate yet</option>
            {OUTCOME_CHIPS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      ) : null}
      <div className="flex items-center gap-3">
        <button
          onClick={() => persist()}
          disabled={saving || decisionTaken === '' || followed === ''}
          className={`px-4 py-2 rounded-lg text-xs font-extrabold uppercase tracking-wider transition shadow-sm ${
            saving || decisionTaken === '' || followed === ''
              ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
              : 'bg-[#0B5D3B] hover:bg-[#08482E] text-white'
          }`}
        >
          {saving ? 'Saving…' : 'Save & done'}
        </button>
        <button
          onClick={() => { setEditing(false); setErr(null) }}
          className="px-3 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-slate-800 transition"
        >
          Cancel
        </button>
      </div>
    </div>
  )

  // ── State 1: answered — show the review inline (Phase 4) ──
  if (state.answered) {
    return (
      <section className={`${wrapper} ${compact ? 'p-3' : 'p-4'}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider bg-[#EAF3FF] text-[#004085] border border-[#D6E8FF]">
              ✓ Follow-up recorded
            </span>
            {outcome?.outcome_status && outcome.outcome_status !== 'Pending' ? (
              <span className="text-[10px] px-2.5 py-1 rounded-full font-black uppercase tracking-wider bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]">
                {outcome.outcome_status}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {state.rated ? (
              <a
                href={outcomeReviewDownloadHref(record.runId, 'pdf')}
                className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-lg border border-[#DDE6F0] text-slate-600 hover:bg-[#F5F8FC] transition"
              >
                ↓ Outcome Review
              </a>
            ) : null}
            <button
              onClick={() => (editing ? setEditing(false) : openForm())}
              className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-lg bg-white border border-[#DDE6F0] text-slate-700 hover:bg-[#F5F8FC] transition"
            >
              {editing ? 'Close' : 'Update'}
            </button>
          </div>
        </div>
        {!editing ? (
          <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-700">
            <div>Decision taken: <strong>{ANSWER_LABELS[record.decisionTaken || ''] || record.decisionTaken || '—'}</strong></div>
            <div>Recommendation: <strong>{ANSWER_LABELS[record.recommendationFollowed || ''] || record.recommendationFollowed || '—'}</strong></div>
            {record.decisionComment ? (
              <div className="md:col-span-2 text-slate-600 italic">"{record.decisionComment}"</div>
            ) : null}
            {outcome?.what_happened ? (
              <div className="md:col-span-2 text-slate-600"><span className="font-extrabold uppercase text-[10px] tracking-wider text-slate-500">What happened · </span>{outcome.what_happened}</div>
            ) : null}
            {outcome?.what_worked || outcome?.what_failed || outcome?.what_was_missed ? (
              <div className="md:col-span-2 text-slate-600">
                <span className="font-extrabold uppercase text-[10px] tracking-wider text-slate-500">Lessons · </span>
                {[outcome?.what_worked && `Worked: ${outcome.what_worked}`,
                  outcome?.what_failed && `Failed: ${outcome.what_failed}`,
                  outcome?.what_was_missed && `Missed: ${outcome.what_was_missed}`].filter(Boolean).join(' · ')}
              </div>
            ) : null}
          </div>
        ) : (
          form
        )}
        {!editing && !state.rated ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Outcome so far:</span>
            {OUTCOME_CHIPS.slice(0, 4).map(s => (
              <button
                key={s}
                disabled={saving}
                onClick={() => persist({ outcome_status: s })}
                className={`text-[10px] px-2 py-0.5 rounded-full font-bold border transition ${
                  outcome?.outcome_status === s
                    ? 'bg-[#061C14] text-white border-[#061C14]'
                    : 'bg-white text-slate-600 border-[#DDE6F0] hover:border-[#0B5D3B] hover:text-[#0B5D3B]'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        ) : null}
      </section>
    )
  }

  // ── State 2: pending + due date passed — the reminder (Phase 2) ──
  if (state.overdueDays !== null && state.overdueDays >= 0) {
    return (
      <section className={`rounded-[12px] border p-4 ${editing ? 'bg-[#FFFAEB] border-[#FEDF89]' : 'bg-[#FFFAEB] border-[#FEDF89]'}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-sm font-extrabold text-[#B54708]">
              ⏳ Decision Follow-Up Due
            </div>
            <div className="text-xs text-slate-600 mt-0.5">
              {state.overdueDays === 0
                ? 'The 30-day check-in is due today.'
                : `${state.overdueDays} day${state.overdueDays === 1 ? '' : 's'} past the 30-day check-in.`}{' '}
              We recommended <strong>{record.recommendation || '—'}</strong> — did it hold up? Takes under a minute.
            </div>
          </div>
          {!editing ? (
            <button
              onClick={openForm}
              className="px-4 py-2 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-[10px] font-extrabold uppercase tracking-wider transition shadow-sm shrink-0"
            >
              One-click update →
            </button>
          ) : null}
        </div>
        {!editing ? (
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
                onClick={() => quickSave(o.v)}
                className="text-[10px] px-2.5 py-1 rounded-full font-bold bg-white text-slate-700 border border-[#FEDF89] hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition disabled:opacity-50"
              >
                {o.label}
              </button>
            ))}
          </div>
        ) : null}
        {err ? <div className="mt-2 p-2 bg-red-50 text-red-700 border border-red-200 rounded-lg text-xs font-medium">{err}</div> : null}
        {editing ? form : null}
      </section>
    )
  }

  // ── State 3: pending, window not open yet — quiet, never intrusive ──
  const daysRemaining = state.overdueDays !== null ? Math.max(0, -state.overdueDays) : null
  return (
    <div className={`${compact ? 'text-[11px]' : 'text-xs'} text-slate-400 flex items-center gap-2 ${compact ? '' : 'px-1 py-1.5'}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shrink-0" />
      {daysRemaining !== null
        ? `Decision follow-up opens in ${daysRemaining} day${daysRemaining === 1 ? '' : 's'} — we will ask whether a decision was taken and followed.`
        : 'Decision follow-up: we will check in 30 days after this assessment.'}
    </div>
  )
}
