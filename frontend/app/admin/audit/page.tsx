'use client'

// Admin Console — Phase 6: audit logs.
//
// The platform-wide log, with the four buckets an operator is asked to watch:
// assessment creation, deletes, role changes and billing events. Bucket counts
// are computed from the same filters the event page uses, and the vocabulary
// behind each bucket lives on the server — this screen cannot drift from it.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  FetchStatus,
  Metric,
  Panel,
  Pill,
  Table,
  WindowPicker,
  fmtDateTime,
  fmtInt,
  mapItems,
  relTime,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { AUDIT_BUCKETS, getAdminAudit, type AdminAuditBucket } from '../../../lib/admin'

const LIMITS = [50, 100, 200, 500, 1000]

export default function AdminAuditPage() {
  const [windowDays, setWindowDays] = useState<number | undefined>(30)
  const [limit, setLimit] = useState(200)
  const [bucket, setBucket] = useState<AdminAuditBucket | undefined>(undefined)
  const [orgInput, setOrgInput] = useState('')
  const [userInput, setUserInput] = useState('')
  const [orgId, setOrgId] = useState('')
  const [userId, setUserId] = useState('')

  const { data, busy, error, denied, reload } = useAdminFetch(
    () => getAdminAudit({ bucket, orgId: orgId || undefined, userId: userId || undefined, windowDays, limit }),
    [bucket, orgId, userId, windowDays, limit],
  )

  return (
    <AdminConsoleShell
      section="audit"
      title="Audit Logs"
      description="Every recorded action across every workspace. The log is append-only: this console reads it, nothing here edits or removes an entry."
      toolbar={(
        <div className="flex items-center gap-2 flex-wrap">
          <form
            className="flex items-center gap-1"
            onSubmit={e => { e.preventDefault(); setOrgId(orgInput.trim()); setUserId(userInput.trim()) }}
          >
            <input
              value={orgInput}
              onChange={e => setOrgInput(e.target.value)}
              placeholder="workspace id"
              maxLength={120}
              className="w-36 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <input
              value={userInput}
              onChange={e => setUserInput(e.target.value)}
              placeholder="user id"
              maxLength={120}
              className="w-36 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-[10px] font-extrabold uppercase tracking-wider transition"
            >
              Filter
            </button>
            {orgId || userId ? (
              <button
                type="button"
                onClick={() => { setOrgInput(''); setUserInput(''); setOrgId(''); setUserId('') }}
                className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] text-[10px] font-extrabold uppercase tracking-wider text-slate-500 hover:border-[#0B5D3B] transition"
              >
                Clear
              </button>
            ) : null}
          </form>
          <select
            value={limit}
            onChange={e => setLimit(Number(e.target.value))}
            className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-[11px] font-bold text-slate-700 focus:outline-none focus:border-[#0B5D3B]"
            aria-label="Maximum events returned"
          >
            {LIMITS.map(n => <option key={n} value={n}>top {n}</option>)}
          </select>
          <WindowPicker
            value={windowDays ?? 0}
            onChange={d => setWindowDays(d === 0 ? undefined : d)}
            options={[0, 7, 30, 90, 365]}
          />
        </div>
      )}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Audit logs" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {AUDIT_BUCKETS.map(b => (
              <button
                key={b.id}
                type="button"
                onClick={() => setBucket(bucket === b.id ? undefined : b.id)}
                className={`text-left bg-white rounded-[12px] border shadow-saas p-4 transition ${
                  bucket === b.id ? 'border-[#0B5D3B] ring-2 ring-[#0B5D3B]/20' : 'border-[#DDE6F0] hover:border-[#0B5D3B]'
                }`}
              >
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{b.label}</div>
                <div className="mt-1.5 text-2xl font-black tracking-tight tabular-nums text-[#101828]">
                  {fmtInt(data.totals[b.totalKey])}
                </div>
                <div className="mt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  {bucket === b.id ? 'filtering • click to clear' : 'click to filter'}
                </div>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Events on this page" value={fmtInt(data.count)} hint={`limit ${data.filters.limit}`} />
            <Metric label="Matching the filters" value={fmtInt(data.totals.matchingEvents)} hint="Full-log count behind this page, not just the rows shown." />
            <Metric label="Total events logged" value={fmtInt(data.totals.totalEvents)} hint="Append-only since the platform started." />
            <Metric
              label="Workspaces / users in view"
              value={`${fmtInt(data.distinctOrgs)} / ${fmtInt(data.distinctUsers)}`}
              hint={`Login events ${fmtInt(data.totals.loginEvents)} · report exports ${fmtInt(data.totals.reportExports)} · provider health ${fmtInt(data.totals.providerHealth)}`}
            />
          </div>

          <Panel
            title="Event log"
            note={bucket
              ? `Filtered to the "${AUDIT_BUCKETS.find(b => b.id === bucket)?.label}" bucket${data.filters.windowDays ? ` · last ${data.filters.windowDays} days` : ''}. Newest first.`
              : 'Newest first. Metadata is shown exactly as recorded — the log is never rewritten to look tidier.'}
          >
            <Table
              headers={['When', 'Event', 'Category', 'Workspace', 'Actor', 'Ref', 'Metadata']}
              rows={data.events.map(e => [
                <span title={fmtDateTime(e.createdAt)}>{relTime(e.createdAt)}</span>,
                <div>
                  <div className="font-bold text-slate-800">{e.label}</div>
                  <div className="text-[10px] font-mono text-slate-400">{e.eventType}</div>
                </div>,
                <Pill>{e.category}</Pill>,
                <div>
                  <div className="text-[11px] text-slate-700">{e.orgName || 'unnamed'}</div>
                  <div className="text-[10px] font-mono text-slate-400">{shortId(e.orgId, 14)}</div>
                </div>,
                <span className="font-mono text-[10px] text-slate-500">{shortId(e.userId, 16)}</span>,
                <span className="font-mono text-[10px] text-slate-500">
                  {e.runId ? `run ${shortId(e.runId, 10)}` : e.assessmentId ? `ctx ${shortId(e.assessmentId, 10)}` : e.documentId ? `doc ${shortId(e.documentId, 10)}` : '—'}
                </span>,
                <span className="text-[11px] text-slate-500">
                  {Object.entries(e.metadata || {}).slice(0, 4).map(([k, v]) => `${k}=${String(v).slice(0, 28)}`).join(' · ') || '—'}
                </span>,
              ])}
            />
          </Panel>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel title="By category" note="Categories come from the audit repository's own vocabulary, so they match the customer-facing activity timeline.">
              <BarList items={mapItems(data.byCategory)} emptyLabel="NO DATA — no events matched." />
            </Panel>
            <Panel title="By event type" note="Types present in this page of results.">
              <BarList items={mapItems(data.byEventType)} max={12} emptyLabel="NO DATA — no events matched." />
            </Panel>
          </div>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
