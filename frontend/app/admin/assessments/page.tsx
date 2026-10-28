'use client'

// Platform Administration Console — Assessments.
//
// Every assessment on the platform, regardless of workspace, next to the pipeline
// state that produced it. The list is deliberately *not* window-filtered: an
// administrator searching for an older assessment expects it to appear. The window
// scopes the counts above it, and the header says which is which, because a number
// silently narrowed by a filter reads as a platform total.
//
// Read-only. Nothing here starts, stops, edits or deletes an assessment — that
// would be a customer's decision made on their behalf.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  FetchStatus,
  Metric,
  NO_DATA,
  Panel,
  Pill,
  Table,
  WindowPicker,
  fmtDateTime,
  fmtInt,
  fmtNum,
  fmtPct,
  mapItems,
  relTime,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { getAdminAssessments } from '../../../lib/admin'

const LIMITS = [50, 100, 250, 500]
const STATUSES = ['complete', 'completed', 'running', 'failed', 'pending', 'draft']
const STATUS_TONE: Record<string, 'good' | 'warn' | 'bad' | 'info'> = {
  complete: 'good',
  completed: 'good',
  running: 'info',
  pending: 'warn',
  failed: 'bad',
}

export default function AdminAssessmentsPage() {
  const [windowDays, setWindowDays] = useState(30)
  const [limit, setLimit] = useState(100)
  const [statusInput, setStatusInput] = useState('')
  const [orgInput, setOrgInput] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [filters, setFilters] = useState({ status: '', orgId: '', search: '' })

  const { data, busy, error, denied, reload } = useAdminFetch(
    () => getAdminAssessments({
      status: filters.status || undefined,
      orgId: filters.orgId || undefined,
      search: filters.search || undefined,
      limit,
      windowDays,
    }),
    [filters.status, filters.orgId, filters.search, limit, windowDays],
  )

  return (
    <AdminConsoleShell
      section="assessments"
      title="Assessments"
      description="Every assessment on the platform and the pipeline runs behind them. Read-only by design: an assessment is a customer's work product."
      toolbar={(
        <div className="flex items-center gap-2 flex-wrap">
          <form
            onSubmit={e => { e.preventDefault(); setFilters({ status: statusInput, orgId: orgInput.trim(), search: searchInput.trim() }) }}
            className="flex items-center gap-1 flex-wrap"
          >
            <select value={statusInput} onChange={e => setStatusInput(e.target.value)} className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-[11px] font-bold text-slate-700 focus:outline-none focus:border-[#0B5D3B]" aria-label="Status filter">
              <option value="">any status</option>
              {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <input
              value={orgInput}
              onChange={e => setOrgInput(e.target.value)}
              placeholder="organization id"
              maxLength={120}
              className="w-40 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="assessment, run or user id"
              maxLength={120}
              className="w-48 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-[10px] font-extrabold uppercase tracking-wider transition"
            >
              Filter
            </button>
            {(filters.status || filters.orgId || filters.search) ? (
              <button
                type="button"
                onClick={() => { setStatusInput(''); setOrgInput(''); setSearchInput(''); setFilters({ status: '', orgId: '', search: '' }) }}
                className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] text-[10px] font-extrabold uppercase tracking-wider text-slate-500 hover:border-[#0B5D3B] transition"
              >
                Clear
              </button>
            ) : null}
          </form>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))} className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-[11px] font-bold text-slate-700 focus:outline-none focus:border-[#0B5D3B]" aria-label="Rows">
            {LIMITS.map(n => <option key={n} value={n}>top {n}</option>)}
          </select>
          <WindowPicker value={windowDays} onChange={setWindowDays} />
        </div>
      )}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Assessments" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Assessments" value={fmtInt(data.totals.assessments)} hint={`${fmtInt(data.totals.createdInWindow)} created in ${data.windowDays}d · ${fmtInt(data.totals.listed)} listed here`} />
            <Metric label="Never run" value={fmtInt(data.totals.neverRun)} hint="no pipeline run id attached — created but never executed" tone={data.totals.neverRun ? 'warn' : 'good'} />
            <Metric label="Pipeline runs" value={fmtInt(data.totals.pipelineRuns)} hint={`${fmtInt(data.totals.runningNow)} running · ${fmtInt(data.totals.completedRuns)} completed`} />
            <Metric
              label="Failure rate"
              value={fmtPct(data.totals.failureRate)}
              hint={data.totals.failureRate === null
                ? NO_DATA
                : `${fmtInt(data.totals.failedRuns)} of ${fmtInt(data.totals.pipelineRuns)} runs · avg ${data.totals.averageRunSeconds === null ? NO_DATA : `${fmtNum(data.totals.averageRunSeconds, 0)}s`} per completed run`}
              tone={(data.totals.failureRate ?? 0) > 10 ? 'bad' : 'neutral'}
            />
          </div>

          <Panel
            title="Assessments"
            note="One row per assessment record, newest first. Status is what the record holds today; a 'complete' row with no run id is an assessment that was created and never executed."
          >
            <Table
              headers={['Assessment', 'Type', 'Status', 'Run', 'Workspace', 'User', 'Created', 'Updated']}
              rows={data.assessments.map(a => [
                (
                  <div>
                    <div className="text-[11px] font-mono font-bold text-slate-700">{shortId(a.assessmentId, 26)}</div>
                  </div>
                ),
                <span className="text-[11px] uppercase font-bold text-slate-600">{a.assessmentType || NO_DATA}</span>,
                a.status ? <Pill tone={STATUS_TONE[a.status] || 'neutral'}>{a.status}</Pill> : <span className="text-[11px] text-slate-400">—</span>,
                a.runId ? <span className="text-[11px] font-mono text-slate-500">{shortId(a.runId, 18)}</span> : <span className="text-[11px] text-slate-400 italic">never run</span>,
                (
                  <div>
                    <div className="text-[11px] font-bold text-slate-700">{a.orgName || shortId(a.orgId, 14)}</div>
                    <div className="text-[10px] font-mono text-slate-400">{shortId(a.orgId, 20)}</div>
                  </div>
                ),
                <span className="text-[10px] font-mono text-slate-500">{shortId(a.userId, 18)}</span>,
                <span title={fmtDateTime(a.createdAt)}>{a.createdAt ? relTime(a.createdAt) : NO_DATA}</span>,
                <span title={fmtDateTime(a.updatedAt)}>{a.updatedAt ? relTime(a.updatedAt) : NO_DATA}</span>,
              ])}
            />
          </Panel>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel title="Status distribution" note="All assessments on the platform, not only the listed rows.">
              <BarList items={mapItems(data.byStatus)} emptyLabel="NO DATA — no assessments recorded." />
            </Panel>

            <Panel
              title="Recent failed runs"
              note="The 25 most recent pipeline failures, newest first. An error message here is what the run recorded; the provider chain and its fallbacks are on Provider Health."
            >
              <Table
                headers={['Run', 'Status', 'Workspace', 'Error', 'Failed']}
                rows={data.recentFailures.map(f => [
                  <span className="text-[11px] font-mono font-bold text-slate-700">{shortId(f.runId, 20)}</span>,
                  <Pill tone="bad">{f.status || 'failed'}</Pill>,
                  <span className="text-[10px] font-mono text-slate-500">{shortId(f.orgId, 16)}</span>,
                  <span className="text-[11px] text-slate-600 break-words">{(f.errorMessage || '').slice(0, 140) || NO_DATA}</span>,
                  <span title={fmtDateTime(f.completedAt || f.createdAt)}>{(f.completedAt || f.createdAt) ? relTime(f.completedAt || f.createdAt) : NO_DATA}</span>,
                ])}
                emptyLabel="NO DATA — no failed runs recorded."
              />
            </Panel>
          </div>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
