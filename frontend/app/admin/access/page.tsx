'use client'

// Platform Administration Console — Administrators (the role itself).
//
// The one screen that shows the platform plane as the backend actually builds it:
// PLATFORM_ADMIN stored in its own table, organization roles in theirs, and the
// environment only ever as break-glass. It is also the only place a platform
// administrator can hand the role to somebody else, which is exactly why the role
// is *not* a value in the organization enum — a customer-facing membership editor
// must never be able to grant cross-workspace visibility.
//
// Two rules this screen cannot work around, because the store enforces them:
// the last active administrator cannot be revoked, and neither can the configured
// primary. Both would lock the platform out of its own console.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  ActionButton,
  ActionFeedback,
  BarList,
  DataNotes,
  FetchStatus,
  Field,
  INPUT_CLASS,
  KV,
  Metric,
  NO_DATA,
  Panel,
  Pill,
  Table,
  fmtDateTime,
  fmtInt,
  relTime,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { useAdminAction } from '../../../hooks/useAdminAction'
import { usePlatformAdmin } from '../../../hooks/usePlatformAdmin'
import { useSession } from 'next-auth/react'
import {
  ALL_CAPABILITIES,
  CAPABILITY_LABELS,
  getAdminAccess,
  grantAdminRole,
  revokeAdminRole,
  type AdminRosterRow,
} from '../../../lib/admin'

export default function AdminAccessPage() {
  const { status: authStatus } = useSession()
  const { session } = usePlatformAdmin(authStatus === 'authenticated')
  const [grant, setGrant] = useState({ email: '', userId: '', displayName: '' })
  const [reason, setReason] = useState('')
  const [showRevoked, setShowRevoked] = useState(true)

  const { data, busy, error, denied, reload } = useAdminFetch(() => getAdminAccess(30), [])
  const action = useAdminAction(reload)

  const canGrant = Boolean(session?.isPlatformAdmin && session?.capabilities?.includes('manage_platform_admins'))
  const me = String(session?.identity?.verifiedEmail || '').toLowerCase()
  const myUserId = String(session?.identity?.userId || '')

  const rows: AdminRosterRow[] = (data?.admins || []).filter(a => showRevoked || a.status === 'active')

  const doGrant = () => action.run(async () => {
    const result = await grantAdminRole({
      email: grant.email.trim() || undefined,
      userId: grant.userId.trim() || undefined,
      displayName: grant.displayName.trim() || undefined,
    })
    const who = result.admin.email || shortId(result.admin.userId, 20)
    const verb = result.outcome === 'revived' ? 'revived' : result.outcome === 'already_active' ? 'already held by' : 'granted to'
    return `PLATFORM_ADMIN ${verb} ${who}. ${result.activeCount} active administrator(s).`
  })

  const doRevoke = (row: AdminRosterRow) => action.run(async () => {
    const identity = row.email || row.userId || row.principal
    const result = await revokeAdminRole(identity, reason || undefined)
    return `Access revoked for ${row.email || shortId(row.userId, 20)} — the row is retained as revoked. ${result.activeCount} active administrator(s) remain.`
  })

  return (
    <AdminConsoleShell
      section="access"
      title="Administrators"
      description="Who holds PLATFORM_ADMIN, how each grant was obtained, and what the role actually grants. Organization roles are listed alongside precisely because they grant nothing here."
      toolbar={(
        <label className="flex items-center gap-2 text-[11px] font-bold text-slate-600">
          <input type="checkbox" checked={showRevoked} onChange={e => setShowRevoked(e.target.checked)} />
          Show revoked history
        </label>
      )}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Administrators" />

      {action.outcome ? (
        <ActionFeedback ok={action.outcome.ok} message={action.outcome.message} code={action.outcome.code} onDismiss={action.clear} />
      ) : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Active administrators" value={fmtInt(data.store.activeCount)} hint={`${fmtInt(data.store.rowCount)} roster row(s) including history`} tone={data.store.activeCount ? 'good' : 'bad'} />
            <Metric label="Role store" value={data.store.configured ? 'provisioned' : 'empty'} hint={data.store.error || `primary: ${data.store.primaryEmail || NO_DATA}`} tone={data.store.configured ? 'good' : 'warn'} />
            <Metric label="Break-glass identities" value={fmtInt(data.breakGlass.size)} hint={data.breakGlass.envNames.join(' · ')} tone={data.breakGlass.size ? 'warn' : 'neutral'} />
            <Metric label="Your capabilities" value={`${session?.capabilities?.length ?? 0}/${ALL_CAPABILITIES.length}`} hint={session?.roleLabel || NO_DATA} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel
              title="PLATFORM_ADMIN — what the role grants"
              note={data.platformRole.note}
            >
              <Table
                headers={['Capability', 'Grants', 'You hold it']}
                rows={data.platformRole.capabilities.map(c => [
                  <span className="font-mono text-[11px] font-bold text-slate-700">{c.id}</span>,
                  <span className="text-[11px] text-slate-600">{c.label}</span>,
                  session?.capabilities?.includes(c.id) ? <Pill tone="good">yes</Pill> : <Pill>no</Pill>,
                ])}
              />
            </Panel>

            <Panel
              title="Organization roles are a separate plane"
              note="A workspace role governs one workspace. None of them resolve to a platform capability, and no membership endpoint can write a platform row — that separation is what keeps an Org Admin from promoting themselves to cross-workspace visibility."
            >
              <Table
                headers={['Organization role', 'Platform capabilities granted', 'Memberships']}
                rows={data.orgRoles.map(r => [
                  (
                    <div>
                      <div className="text-[11px] font-bold text-slate-800">{r.label}</div>
                      <div className="text-[10px] font-mono text-slate-400">{r.id}</div>
                    </div>
                  ),
                  r.platformCapabilities.length
                    ? <span className="text-[11px]">{r.platformCapabilities.join(', ')}</span>
                    : <Pill tone="bad">none</Pill>,
                  fmtInt(data.roleDistribution[r.id] ?? 0),
                ])}
              />
              <div className="mt-3">
                <BarList items={Object.entries(data.roleDistribution).map(([label, value]) => ({ label, value }))} emptyLabel="NO DATA — no memberships recorded." />
              </div>
            </Panel>
          </div>

          <Panel
            title="Roster"
            note="The platform principals, active and revoked. Revoked rows stay visible on purpose: history is not rewritten, so you can see who held access and who removed it."
          >
            <Table
              headers={['Principal', 'Identity', 'Source', 'Granted by', 'Last seen', 'Status', '']}
              rows={rows.map(row => {
                const isMe = (row.email && row.email.toLowerCase() === me) || (row.userId && row.userId === myUserId)
                return [
                  <span className="font-mono text-[11px] font-bold text-slate-700">{shortId(row.principal, 30)}</span>,
                  (
                    <div>
                      <div className="text-[11px] font-bold text-slate-800">{row.displayName || row.email || shortId(row.userId, 20)}</div>
                      {row.email ? <div className="text-[10px] text-slate-500">{row.email}</div> : null}
                      {row.userId ? <div className="text-[10px] font-mono text-slate-400">{shortId(row.userId, 26)}</div> : null}
                      {row.isPrimary ? <Pill tone="info">primary</Pill> : null}
                      {isMe ? <span className="ml-1 text-[10px] font-extrabold uppercase text-[#0B5D3B]">you</span> : null}
                    </div>
                  ),
                  <span className="text-[11px] uppercase font-bold text-slate-600">{row.source}</span>,
                  <span className="text-[10px] font-mono text-slate-500">{shortId(row.grantedBy, 20)}</span>,
                  <span title={fmtDateTime(row.lastSeenAt)}>{row.lastSeenAt ? relTime(row.lastSeenAt) : 'never via console'}</span>,
                  (
                    <div className="flex flex-col gap-1">
                      <Pill tone={row.status === 'active' ? 'good' : 'neutral'}>{row.status}</Pill>
                      <span className="text-[10px] text-slate-400">granted {fmtDateTime(row.grantedAt)}</span>
                      {row.revokedAt ? <span className="text-[10px] text-slate-400">revoked {fmtDateTime(row.revokedAt)} by {shortId(row.revokedBy, 14)}</span> : null}
                    </div>
                  ),
                  row.status === 'active' ? (
                    <ActionButton
                      label="Revoke"
                      tone="bad"
                      allowed={canGrant && !row.isPrimary}
                      busy={action.busy}
                      title={row.isPrimary
                        ? 'The configured primary administrator cannot be revoked from the console — move KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL on the deployment instead'
                        : 'Revoke this principal’s PLATFORM_ADMIN role (kept in history as revoked)'}
                      onClick={() => { void doRevoke(row) }}
                    />
                  ) : <span className="text-[10px] text-slate-400 italic">history only</span>,
                ]
              })}
            />
            <div className="mt-3 flex items-center gap-2">
              <input
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="reason recorded with the next revocation"
                maxLength={300}
                className={`${INPUT_CLASS} w-80`}
              />
            </div>
          </Panel>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel
              title="Grant PLATFORM_ADMIN"
              note="A grant needs an identifier the session can actually prove: a user id that has signed in, or an email address the provider verified. An email typed into organization member management is neither, which is why it is never consulted for this role."
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Field label="Email (provider-verified)">
                  <input value={grant.email} onChange={e => setGrant({ ...grant, email: e.target.value })} className={INPUT_CLASS} maxLength={200} placeholder="name@organisation.com" />
                </Field>
                <Field label="User id (JWT subject)">
                  <input value={grant.userId} onChange={e => setGrant({ ...grant, userId: e.target.value })} className={INPUT_CLASS} maxLength={200} placeholder="from the Users panel" />
                </Field>
                <Field label="Display name">
                  <input value={grant.displayName} onChange={e => setGrant({ ...grant, displayName: e.target.value })} className={INPUT_CLASS} maxLength={200} placeholder="optional" />
                </Field>
              </div>
              <div className="mt-3 flex items-center gap-3 flex-wrap">
                <ActionButton label="Grant role" tone="good" allowed={canGrant} busy={action.busy} onClick={() => { void doGrant() }} />
                <span className="text-[10px] text-slate-400">
                  {(!grant.email.trim() && !grant.userId.trim()) ? 'Needs an email or a user id.' : `Grants all ${ALL_CAPABILITIES.length} capabilities: ${Object.values(CAPABILITY_LABELS).slice(0, 3).join(', ')}…`}
                </span>
              </div>
            </Panel>

            <Panel
              title="How access was provisioned"
              note="Provisioning comes from configuration and from an existing administrator. Revoked grants are never silently restored by a restart — re-granting is an explicit act."
            >
              <KV label="Bootstrapped from" value={data.store.bootstrappedFrom.length ? data.store.bootstrappedFrom.join(', ') : 'no configured identities'} />
              <KV label="Primary administrator" value={data.store.primaryEmail || NO_DATA} />
              <KV label="Break-glass variables" value={data.breakGlass.envNames.join(' · ')} />
              <KV label="Break-glass note" value={data.breakGlass.note} />
              {session?.grantedBy === 'env_allow_list' ? (
                <div className="mt-3 rounded-[12px] border border-[#FEDF89] bg-[#FFFAEB] p-3 text-[11px] text-[#B54708] leading-relaxed">
                  Your own access is currently break-glass, not a stored role. Grant yourself the role once the roster is reachable so
                  every future action is attributed to PLATFORM_ADMIN rather than the environment.
                </div>
              ) : null}
            </Panel>
          </div>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
