'use client'

// Admin Console — Phase 2: user management.
//
// Who exists, where they belong, what plan they are on and what they last did.
// Everything here is an operator reading across workspaces; the console cannot
// change any of it. Role and membership edits stay in the customer workspace
// (Settings → Members), where the acting user holds the organization permission.

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
import { getAdminUsers } from '../../../lib/admin'

const LIMITS = [50, 100, 250, 500]

export default function AdminUsersPage() {
  const [windowDays, setWindowDays] = useState(30)
  const [limit, setLimit] = useState(100)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const { data, busy, error, denied, reload } = useAdminFetch(
    () => getAdminUsers({ search: query || undefined, limit, windowDays }),
    [query, limit, windowDays],
  )

  return (
    <AdminConsoleShell
      section="users"
      title="User Management"
      description="Users, organizations, plans, roles and recent activity — platform-wide and read-only. Membership edits happen inside a workspace, never here."
      toolbar={(
        <div className="flex items-center gap-2 flex-wrap">
          <form
            onSubmit={e => { e.preventDefault(); setQuery(search.trim()) }}
            className="flex items-center gap-1"
          >
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="name, email or user id"
              maxLength={120}
              className="w-48 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-[10px] font-extrabold uppercase tracking-wider transition"
            >
              Search
            </button>
            {query ? (
              <button
                type="button"
                onClick={() => { setSearch(''); setQuery('') }}
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
            aria-label="Rows per section"
          >
            {LIMITS.map(n => <option key={n} value={n}>top {n}</option>)}
          </select>
          <WindowPicker value={windowDays} onChange={setWindowDays} />
        </div>
      )}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="User management" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Users listed" value={fmtInt(data.userCount)} hint={data.search ? `matching "${data.search}"` : `member identities on ${data.windowDays}d window`} />
            <Metric label="Organizations listed" value={fmtInt(data.organizations.length)} hint="workspaces, newest first" />
            <Metric label="Roles in use" value={fmtInt(Object.keys(data.roles).length)} hint={Object.entries(data.roles).map(([r, c]) => `${r}: ${c}`).join(' · ') || 'NO DATA'} />
            <Metric label="Plans in use" value={fmtInt(data.plans.length)} hint={data.plans.map(p => `${p.planId} (${p.organizations})`).join(' · ') || 'NO DATA'} />
          </div>

          <Panel
            title="Users"
            note="One row per user id. Roles are the organization roles attached to each membership — they describe a workspace, not the platform. 'Active' means an audit event inside the window."
          >
            <Table
              headers={['User', 'Roles', 'Workspaces', 'Assessments', 'Audit events', 'Last activity', 'Active']}
              rows={data.users.map(u => [
                (
                  <div>
                    <div className="font-bold text-slate-900">{u.displayName || shortId(u.userId, 20)}</div>
                    <div className="text-[11px] text-slate-500">{u.email || <span className="italic">no email on membership</span>}</div>
                    <div className="text-[10px] font-mono text-slate-400">{shortId(u.userId, 28)}</div>
                  </div>
                ),
                (
                  <div className="flex flex-wrap gap-1">
                    {(u.roles || []).map(r => <Pill key={r}>{r}</Pill>)}
                    {!u.roles?.length ? <span className="text-[11px] text-slate-400">—</span> : null}
                  </div>
                ),
                fmtInt(u.orgCount),
                fmtInt(u.assessments),
                fmtInt(u.auditEvents),
                <span title={fmtDateTime(u.lastActivityAt)}>{relTime(u.lastActivityAt)}</span>,
                u.active ? <Pill tone="good">Active</Pill> : <Pill>Idle</Pill>,
              ])}
            />
          </Panel>

          <Panel
            title="Organizations"
            note="Every workspace with its plan, seats and heaviest usage. Personal workspaces are auto-provisioned per identity on first sign-in."
          >
            <Table
              headers={['Workspace', 'Plan', 'Members', 'Assessments', 'Docs', 'Billing', 'Last activity', 'Created']}
              rows={data.organizations.map(o => [
                (
                  <div>
                    <div className="font-bold text-slate-900 flex items-center gap-1.5">
                      {o.name}
                      {o.personal ? <Pill>personal</Pill> : null}
                    </div>
                    <div className="text-[10px] font-mono text-slate-400">{shortId(o.id, 24)} · /{o.slug}</div>
                  </div>
                ),
                <span className="font-bold uppercase text-[11px]">{o.plan}</span>,
                fmtInt(o.members),
                fmtInt(o.assessments),
                fmtInt(o.documents),
                o.billingStatus
                  ? <Pill tone={o.billingStatus === 'active' ? 'good' : o.billingStatus === 'past_due' ? 'bad' : 'warn'}>{o.billingStatus}</Pill>
                  : <span className="text-[11px] text-slate-400 italic">no subscription row</span>,
                <span title={fmtDateTime(o.lastActivityAt)}>{relTime(o.lastActivityAt)}</span>,
                fmtDateTime(o.createdAt),
              ])}
            />
          </Panel>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel
              title="Plans"
              note="Organizations per plan and the memberships those workspaces hold. Personal workspaces sit on 'free' by design, so a large free count is not a conversion failure."
            >
              <Table
                headers={['Plan', 'Organizations', 'Memberships']}
                rows={data.plans.map(p => [
                  <span className="font-bold uppercase text-[11px]">{p.planId}</span>,
                  fmtInt(p.organizations),
                  fmtInt(p.memberships),
                ])}
              />
            </Panel>

            <Panel title="Roles" note="Membership rows per organization role across every workspace.">
              <BarList items={mapItems(data.roles)} emptyLabel="NO DATA — no memberships recorded." />
            </Panel>
          </div>

          <Panel
            title="Recent activity"
            note="The 25 most recent audit events on the platform, newest first — sign-ins, uploads, exports, plan changes. Full log with filters: Phase 6."
          >
            <Table
              headers={['When', 'Event', 'Workspace', 'User', 'Detail']}
              rows={data.activity.map(a => [
                <span title={fmtDateTime(a.createdAt)}>{relTime(a.createdAt)}</span>,
                <span className="font-mono text-[11px] font-bold text-slate-700">{a.eventType}</span>,
                shortId(a.orgId, 18),
                shortId(a.userId, 18),
                <span className="text-[11px] text-slate-500">
                  {Object.entries(a.metadata || {}).slice(0, 3).map(([k, v]) => `${k}=${String(v).slice(0, 24)}`).join(' · ') || '—'}
                </span>,
              ])}
            />
          </Panel>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
