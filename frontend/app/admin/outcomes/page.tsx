'use client'

// Admin Console — Phase 5: outcome intelligence.
//
// Whether the platform's advice is being acted on, and what it is learning.
// This reuses the exact calibration engine the customer outcomes page uses
// (unscoped), so an operator and a customer can never see two different
// versions of the same rate. Bands below the minimum sample size are printed as
// observations, never as calibration.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  EmptyNote,
  FetchStatus,
  KV,
  Metric,
  Panel,
  Pill,
  Table,
  WindowPicker,
  fmtDate,
  fmtDateTime,
  fmtInt,
  fmtNum,
  fmtPct,
  mapItems,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { getAdminOutcomes } from '../../../lib/admin'

const FOLLOWED_LABELS: Record<string, string> = {
  yes: 'Decision taken',
  in_progress: 'Decision in progress',
  no: 'No decision yet',
  unknown: 'Unknown',
  fully: 'Followed fully',
  partially: 'Partially followed',
  not_yet: 'Too early to tell',
}

export default function AdminOutcomesPage() {
  const [windowDays, setWindowDays] = useState(30)
  const { data, busy, error, denied, reload } = useAdminFetch(() => getAdminOutcomes(windowDays), [windowDays])

  const learning = data?.decisionLearning

  return (
    <AdminConsoleShell
      section="outcomes"
      title="Outcome Intelligence"
      description="Follow-up completion, pending outcomes and what the platform has actually learned from settled decisions."
      toolbar={<WindowPicker value={windowDays} onChange={setWindowDays} />}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Outcome intelligence" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric
              label="Follow-ups issued"
              value={fmtInt(data.followUpCompletion.total)}
              hint={`Every decision record carries a ${data.followUpCompletion.cadenceDays}-day check-in`}
            />
            <Metric
              label="Follow-Up Completion"
              value={fmtPct(data.followUpCompletion.completionRate)}
              hint={`${fmtInt(data.followUpCompletion.answered)} answered · ${fmtInt(data.followUpCompletion.answeredInWindow)} in ${data.windowDays}d`}
              tone={data.followUpCompletion.completionRate === null ? 'neutral' : data.followUpCompletion.completionRate >= 50 ? 'good' : 'warn'}
            />
            <Metric
              label="Pending Outcomes"
              value={fmtInt(data.pendingOutcomes.count)}
              hint={`${fmtInt(data.pendingOutcomes.overdue)} already past their due date`}
              tone={data.pendingOutcomes.overdue > 0 ? 'warn' : 'neutral'}
            />
            <Metric
              label="Recommendation followed"
              value={fmtPct(data.followedRate.rate)}
              hint={`${fmtInt(data.followedRate.followed)} of ${fmtInt(data.followedRate.decidable)} decidable answers. ${data.followedRate.definition}`}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel title="Decision taken (answered follow-ups)" note="Distribution of the first follow-up question.">
              <BarList
                items={Object.entries(data.decisionTaken.byAnswer).map(([k, v]) => ({ label: FOLLOWED_LABELS[k] || k || 'unknown', value: v }))}
                emptyLabel="NO DATA — no follow-ups answered yet."
              />
              <div className="mt-3 text-[11px] text-slate-500">
                Decision rate on answered records: <strong className="text-slate-800">{fmtPct(data.decisionTaken.decisionRate)}</strong>
              </div>
            </Panel>

            <Panel title="Days to follow-up" note={data.daysToFollowUp.definition}>
              <div className="flex flex-col">
                <KV label="Samples" value={fmtInt(data.daysToFollowUp.samples)} />
                <KV label="Average" value={data.daysToFollowUp.average === null ? 'NO DATA' : `${fmtNum(data.daysToFollowUp.average, 1)} days`} />
                <KV label="Median" value={data.daysToFollowUp.median === null ? 'NO DATA' : `${fmtNum(data.daysToFollowUp.median, 1)} days`} />
                <KV
                  label="Feedback ratings"
                  value={learning?.feedback.ratings
                    ? `${fmtInt(learning.feedback.ratings)} · avg ${fmtNum(learning.feedback.average, 2)} / 5 · ${fmtInt(learning.feedback.positive)} at 4+`
                    : 'NO DATA'}
                />
              </div>
            </Panel>
          </div>

          <Panel
            title="Pending outcomes"
            note={data.pendingOutcomes.definition}
            right={<Pill tone={data.pendingOutcomes.overdue ? 'warn' : 'good'}>{fmtInt(data.pendingOutcomes.overdue)} overdue</Pill>}
          >
            <Table
              headers={['Entity', 'Workspace', 'Recommendation', 'Trust', 'Due', 'State']}
              rows={data.pendingOutcomes.rows.map(p => [
                <div>
                  <div className="font-bold text-slate-800">{p.entityName || shortId(p.runId, 16)}</div>
                  <div className="text-[10px] font-mono text-slate-400">{shortId(p.runId, 20)}</div>
                </div>,
                <div>
                  <div className="text-[11px] text-slate-600">{p.orgName || 'unnamed'}</div>
                  <div className="text-[10px] font-mono text-slate-400">{shortId(p.orgId, 14)}</div>
                </div>,
                <span className="font-bold uppercase text-[11px]">{p.recommendation || '—'}</span>,
                <span className="tabular-nums">
                  {p.trustScore === null || p.trustScore === undefined ? '—' : fmtNum(p.trustScore, 0)}
                  {p.integrityGrade ? <span className="ml-1 text-[10px] text-slate-400">{p.integrityGrade}</span> : null}
                </span>,
                <span title={fmtDateTime(p.followupDueAt)}>{fmtDate(p.followupDueAt)}</span>,
                p.dueState === 'overdue'
                  ? <Pill tone="bad">{fmtInt(p.daysOverdue)}d overdue</Pill>
                  : <Pill tone="info">{p.dueState.replace(/_/g, ' ')}</Pill>,
              ])}
            />
            <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div>
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 mb-2">Settled outcome ratings</div>
                <BarList items={mapItems(data.pendingOutcomes.outcomeStatuses)} emptyLabel="NO DATA — no outcome records yet." />
              </div>
              <div className="pt-5 lg:pt-0">
                <KV label="Outcome records" value={fmtInt(data.pendingOutcomes.outcomeRowsTotal)} />
                <KV label="With lessons written" value={fmtInt(data.pendingOutcomes.outcomeRowsWithLessons)} />
                <KV label="Settled (completed / rated)" value={fmtInt(learning?.settledOutcomes ?? 0)} />
              </div>
            </div>
          </Panel>

          {learning ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <Panel
                title="Decision learning"
                note="Accuracy figures stay empty until real completed outcomes exist — a 0% read as measured failure would be a fabricated number."
              >
                <div className="flex flex-col">
                  <KV label="Decisions recorded" value={fmtInt(learning.summary.total_decisions)} />
                  <KV label="Completed outcomes" value={fmtInt(learning.summary.completed_outcomes)} />
                  <KV label="Recommendation accuracy" value={fmtPct(learning.summary.recommendation_accuracy)} />
                  <KV label="High-trust success rate" value={fmtPct(learning.summary.trust_accuracy)} />
                  <KV label="Signal accuracy" value={fmtPct(learning.summary.signal_accuracy)} />
                </div>
                <div className="mt-3 p-3 rounded-lg bg-[#F5F8FC] border border-[#DDE6F0] text-[11px] text-slate-600 leading-relaxed">
                  {learning.calibration.calibration_summary}
                </div>
              </Panel>

              <Panel title="Trust-band calibration" note={learning.calibration.bandNote}>
                <Table
                  headers={['Band', 'Decisions', 'Completed', 'Successful', 'Rate', 'Reading']}
                  rows={learning.calibration.bins.map(b => [
                    <span className="font-bold text-slate-800">{b.tier}</span>,
                    fmtInt(b.decision_count),
                    fmtInt(b.completed_count),
                    fmtInt(b.successful_count),
                    b.completed_count ? `${fmtNum(b.success_rate, 1)}%` : 'NO DATA',
                    b.completed_count >= 10
                      ? <Pill tone="good">reportable</Pill>
                      : <Pill tone="warn">observation only</Pill>,
                  ])}
                />
                <div className="mt-3">
                  {learning.calibration.reportableBands.length ? (
                    <EmptyNote label={`${learning.calibration.reportableBands.length} band(s) cleared the 10-completed threshold.`} />
                  ) : (
                    <EmptyNote label="NO CALIBRATION YET — no band has 10 completed outcomes. The platform does not call a handful of outcomes a rate." />
                  )}
                </div>
              </Panel>
            </div>
          ) : null}

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
