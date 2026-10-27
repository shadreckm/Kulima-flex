'use client'

// Admin Console — Phase 1: platform overview.
//
// Seven numbers an operator needs before opening anything else, all platform-wide.
// Each one carries its own definition so a figure can never be read as something
// it isn't (e.g. "active users" is audit-derived, not a login counter).

import { useState } from 'react'
import AdminConsoleShell from '../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  FetchStatus,
  KV,
  Metric,
  Panel,
  Pill,
  WindowPicker,
  fmtBytes,
  fmtDateTime,
  fmtInt,
  fmtPct,
  mapItems,
  relTime,
} from '../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../hooks/useAdminFetch'
import { getAdminOverview } from '../../lib/admin'

export default function AdminOverviewPage() {
  const [windowDays, setWindowDays] = useState(30)
  const { data, busy, error, denied, reload } = useAdminFetch(() => getAdminOverview(windowDays), [windowDays])

  return (
    <AdminConsoleShell
      section="overview"
      title="Platform Overview"
      description="Every workspace on the platform in one snapshot. Read-only: opening a section only records that you opened it."
      toolbar={<WindowPicker value={windowDays} onChange={setWindowDays} />}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Overview" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric
              label="Total Organizations"
              value={fmtInt(data.organizations.total)}
              hint={`${fmtInt(data.organizations.teamWorkspaces)} team · ${fmtInt(data.organizations.personalWorkspaces)} personal · ${fmtInt(data.organizations.createdInWindow)} new in ${data.windowDays}d`}
            />
            <Metric
              label="Total Users"
              value={fmtInt(data.users.total)}
              hint={`${fmtInt(data.users.joinedInWindow)} joined in ${data.windowDays}d · distinct member identities across all workspaces`}
            />
            <Metric
              label="Active Users"
              value={fmtInt(data.users.activeInWindow)}
              hint={`Within ${data.windowDays}d: ${data.users.activityDefinition}`}
              tone={data.users.total && data.users.activeInWindow / data.users.total >= 0.4 ? 'good' : 'neutral'}
            />
            <Metric
              label="Assessments"
              value={fmtInt(data.assessments.total)}
              hint={`${fmtInt(data.assessments.createdInWindow)} created in ${data.windowDays}d · ${fmtInt(data.assessments.completedBriefs)} completed briefs`}
            />
            <Metric
              label="Reports"
              value={fmtInt(data.reports.exportedTotal)}
              hint={`${fmtInt(data.reports.exportedInWindow)} exported in ${data.windowDays}d · exports are audit events, not stored files`}
            />
            <Metric
              label="Conversations"
              value={fmtInt(data.conversations.total)}
              hint={`${fmtInt(data.conversations.messages)} messages · ${fmtInt(data.conversations.questionsInWindow)} asked in ${data.windowDays}d`}
            />
            <Metric
              label="Outcome Follow-Ups"
              value={fmtInt(data.outcomeFollowUps.total)}
              hint={`${fmtInt(data.outcomeFollowUps.answered)} answered · ${fmtInt(data.outcomeFollowUps.pending)} waiting · ${fmtInt(data.outcomeFollowUps.overdueNow)} past due`}
            />
            <Metric
              label="Follow-Up Completion"
              value={fmtPct(data.outcomeFollowUps.completionRate)}
              hint="Answered ÷ every decision record carrying a 30-day follow-up."
              tone={data.outcomeFollowUps.completionRate === null ? 'neutral' : data.outcomeFollowUps.completionRate >= 50 ? 'good' : 'warn'}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel
              title="Organizations by plan"
              note="Plan recorded on the workspace row. Personal workspaces are auto-provisioned on first sign-in, so a high free count is normal."
            >
              <BarList items={mapItems(data.organizations.byPlan)} emptyLabel="NO DATA — no workspaces exist yet." />
            </Panel>

            <Panel
              title="Assessments by status"
              note={`Status of every assessment context. ${fmtInt(data.documents.total)} documents uploaded (${fmtInt(data.documents.active)} not deleted, ${fmtBytes(data.documents.storageBytes)} stored).`}
            >
              <BarList items={mapItems(data.assessments.byStatus)} emptyLabel="NO DATA — no assessments created yet." />
            </Panel>

            <Panel
              title="Reports by kind"
              note="One audit event per export, keyed by the report the operator/customer generated."
            >
              <BarList items={mapItems(data.reports.byKind)} emptyLabel="NO DATA — nothing exported yet." />
            </Panel>

            <Panel
              title="Pipeline health"
              note="The audit log is the heartbeat: if events stop, work stopped — this is the first place to look when a section reads empty."
            >
              <div className="flex flex-col">
                <KV label="Audit events (all time)" value={fmtInt(data.pipelineHealth.auditEventsTotal)} />
                <KV label={`Audit events (${data.windowDays}d)`} value={fmtInt(data.pipelineHealth.auditEventsInWindow)} />
                <KV
                  label="Last event"
                  value={(
                    <span className="flex items-center gap-2">
                      {relTime(data.pipelineHealth.lastEventAt)}
                      <span className="text-slate-400 font-normal">{fmtDateTime(data.pipelineHealth.lastEventAt)}</span>
                    </span>
                  )}
                />
                <KV
                  label="Failed pipeline runs"
                  value={
                    data.pipelineHealth.failedRuns > 0
                      ? <Pill tone="bad">{fmtInt(data.pipelineHealth.failedRuns)}</Pill>
                      : <Pill tone="good">0</Pill>
                  }
                />
              </div>
            </Panel>
          </div>

          <Panel
            title="Most frequent activity"
            note={`Event types in the last ${data.windowDays} days, ranked. Full vocabulary lives in Phase 6.`}
          >
            <BarList items={data.pipelineHealth.topEventTypes.map(e => ({ label: e.eventType, value: e.count }))} max={8} />
          </Panel>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
