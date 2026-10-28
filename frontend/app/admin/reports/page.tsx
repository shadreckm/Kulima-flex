'use client'

// Platform Administration Console — Reports.
//
// There is no `reports` table. A report exists as the audit event that records it
// was produced, and this panel says so on its face: counting exports from
// `report.exported` events keeps the number reconcilable with the audit log rather
// than implying a store that protects nothing. The file itself lives in the
// customer's workspace (or in the export response), not here.
//
// Read-only: an export is evidence of what a customer generated.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  FetchStatus,
  Metric,
  NO_DATA,
  Panel,
  Table,
  WindowPicker,
  fmtDateTime,
  fmtInt,
  mapItems,
  relTime,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { getAdminReports } from '../../../lib/admin'

const LIMITS = [50, 150, 250, 500]

export default function AdminReportsPage() {
  const [windowDays, setWindowDays] = useState(30)
  const [limit, setLimit] = useState(150)
  const [orgInput, setOrgInput] = useState('')
  const [orgId, setOrgId] = useState('')

  const { data, busy, error, denied, reload } = useAdminFetch(
    () => getAdminReports({ orgId: orgId || undefined, limit, windowDays }),
    [orgId, limit, windowDays],
  )

  return (
    <AdminConsoleShell
      section="reports"
      title="Reports"
      description="Every document the platform has produced, read from the export events. No report rows are stored, so the audit entry is the record."
      toolbar={(
        <div className="flex items-center gap-2 flex-wrap">
          <form
            onSubmit={e => { e.preventDefault(); setOrgId(orgInput.trim()) }}
            className="flex items-center gap-1"
          >
            <input
              value={orgInput}
              onChange={e => setOrgInput(e.target.value)}
              placeholder="organization id"
              maxLength={120}
              className="w-44 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-[10px] font-extrabold uppercase tracking-wider transition"
            >
              Filter
            </button>
            {orgId ? (
              <button
                type="button"
                onClick={() => { setOrgInput(''); setOrgId('') }}
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
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Reports" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Exports ever" value={fmtInt(data.totals.exports)} hint={`${fmtInt(data.totals.exportsInWindow)} in ${data.windowDays}d · ${fmtInt(data.totals.listed)} listed here`} />
            <Metric label="Workspaces exporting" value={fmtInt(data.totals.distinctOrgs)} hint="distinct organizations among the listed rows" />
            <Metric label="Users exporting" value={fmtInt(data.totals.distinctUsers)} hint="distinct user ids among the listed rows" />
            <Metric label="Report kinds" value={fmtInt(Object.keys(data.byKind).length)} hint={Object.entries(data.byKind).map(([k, c]) => `${k}: ${c}`).join(' · ') || NO_DATA} />
          </div>

          <Panel
            title="Exported documents"
            note={data.sourceNote}
          >
            <Table
              headers={['When', 'Workspace', 'User', 'Report', 'Format', 'File', 'Assessment']}
              rows={data.reports.map(r => [
                <span title={fmtDateTime(r.createdAt)}>{r.createdAt ? relTime(r.createdAt) : NO_DATA}</span>,
                (
                  <div>
                    <div className="text-[11px] font-bold text-slate-700">{r.orgName || shortId(r.orgId, 14)}</div>
                    <div className="text-[10px] font-mono text-slate-400">{shortId(r.orgId, 20)}</div>
                  </div>
                ),
                <span className="text-[10px] font-mono text-slate-500">{shortId(r.userId, 18)}</span>,
                <span className="text-[11px] font-bold uppercase text-slate-700">{r.reportKind}</span>,
                <span className="text-[11px] font-mono text-slate-600">{r.format}</span>,
                <span className="text-[11px] text-slate-600 break-words">{r.fileName || <span className="italic text-slate-400">name not recorded</span>}</span>,
                <span className="text-[10px] font-mono text-slate-400">{shortId(r.assessmentId, 18)}</span>,
              ])}
            />
          </Panel>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel title="By report kind" note="Counted across the listed rows only — the same events the table above shows, so the totals reconcile.">
              <BarList items={mapItems(data.byKind)} emptyLabel="NO DATA — no exports in this view." />
            </Panel>
            <Panel title="By format" note="PDF, memo, one-pager and signals are produced by the same export path; a format that never appears was simply never requested.">
              <BarList items={mapItems(data.byFormat)} emptyLabel="NO DATA — no exports in this view." />
            </Panel>
          </div>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
