'use client'

// Platform Administration Console — Organizations.
//
// The one screen where a platform administrator *changes* customer state, so the
// rules it follows are the ones the backend enforces:
//
//  * Plan changes go through the customer billing engine. An upgrade applies
//    immediately, a downgrade schedules at period end, and the customer's own
//    payment history shows the same event. This screen never issues a bespoke
//    UPDATE and never claims a change the engine refused.
//  * Enterprise cannot be applied through the back door. Approval needs the
//    agreement ticked, exactly as customer-facing checkout does.
//  * Nothing here deletes customer data. There is no delete control, on purpose.
//  * Every control is rendered only if the session holds the capability the route
//    declares; the request is refused by the backend regardless of what this page
//    shows.
//
// Renaming is the one mutation that touches a customer-visible identifier, so it
// carries a reason and is audited with before/after.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  ActionButton,
  ActionFeedback,
  DataNotes,
  FetchStatus,
  Field,
  INPUT_CLASS,
  Metric,
  NO_DATA,
  Panel,
  Pill,
  Table,
  WindowPicker,
  fmtBytes,
  fmtDateTime,
  fmtInt,
  fmtMoney,
  relTime,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { useAdminAction } from '../../../hooks/useAdminAction'
import { usePlatformAdmin } from '../../../hooks/usePlatformAdmin'
import { hasCapability, SUBSCRIPTION_PLANS, SUBSCRIPTION_STATUSES, getAdminOrganizations, renameAdminOrganization, setAdminAccountStatus, setAdminEnterpriseActivation, updateAdminSubscription, createAdminOrganization, type AdminOrgDetailRow } from '../../../lib/admin'
import { useSession } from 'next-auth/react'

const LIMITS = [50, 100, 200, 500]
const STATUS_TONE: Record<string, 'good' | 'warn' | 'bad'> = {
  active: 'good',
  grace: 'warn',
  past_due: 'bad',
  suspended: 'bad',
  canceled: 'warn',
}

const emptyDraft = () => ({
  plan: '',
  status: '',
  amount: '',
  currency: '',
  billingCycle: '',
  currentPeriodEnd: '',
  graceUntil: '',
  cancelAtPeriodEnd: false,
  reason: '',
  name: '',
  contact: '',
  agreement: false,
})

export default function AdminOrganizationsPage() {
  const { status: authStatus } = useSession()
  const { session } = usePlatformAdmin(authStatus === 'authenticated')
  const canSubscriptions = hasCapability(session, 'manage_subscriptions')
  const canAccounts = hasCapability(session, 'manage_enterprise_accounts')

  const [windowDays, setWindowDays] = useState(30)
  const [limit, setLimit] = useState(200)
  const [searchInput, setSearchInput] = useState('')
  const [planInput, setPlanInput] = useState('')
  const [statusInput, setStatusInput] = useState('')
  const [filters, setFilters] = useState({ search: '', plan: '', status: '' })
  const [openOrg, setOpenOrg] = useState<string | null>(null)
  const [draft, setDraft] = useState(emptyDraft())
  const [newOrg, setNewOrg] = useState({ name: '', plan: 'free', ownerUserId: '', intendedOwnerEmail: '' })

  const load = () => getAdminOrganizations({
    search: filters.search || undefined,
    plan: filters.plan || undefined,
    status: filters.status || undefined,
    limit,
    windowDays,
  })
  const { data, busy, error, denied, reload } = useAdminFetch(load, [filters.search, filters.plan, filters.status, limit, windowDays])
  const action = useAdminAction(reload)

  const openRow = (row: AdminOrgDetailRow) => {
    if (openOrg === row.orgId) {
      setOpenOrg(null)
      return
    }
    setOpenOrg(row.orgId)
    setDraft({
      ...emptyDraft(),
      plan: row.subscriptionPlan || row.plan || 'free',
      status: row.billingStatus || '',
      name: row.name,
      currency: row.currency || '',
      amount: row.amount === null || row.amount === undefined ? '' : String(row.amount),
      billingCycle: row.billingCycle || '',
      currentPeriodEnd: row.currentPeriodEnd || '',
      cancelAtPeriodEnd: Boolean(row.cancelAtPeriodEnd),
      contact: '',
    })
    action.clear()
  }

  const applySubscription = (row: AdminOrgDetailRow) => {
    const before = {
      plan: row.subscriptionPlan || row.plan || 'free',
      status: row.billingStatus || '',
      currency: row.currency || '',
      amount: row.amount === null || row.amount === undefined ? '' : String(row.amount),
      billingCycle: row.billingCycle || '',
      currentPeriodEnd: row.currentPeriodEnd || '',
    }
    // Only the fields the operator actually altered are sent: the backend's
    // field patch ignores nulls, and an untouched column must never be rewritten
    // with the value the row happened to display.
    const body: Parameters<typeof updateAdminSubscription>[1] = { reason: draft.reason || undefined }
    if (draft.plan && draft.plan !== before.plan) body.plan = draft.plan
    if (draft.status && draft.status !== before.status) body.status = draft.status
    if (draft.currency && draft.currency !== before.currency) body.currency = draft.currency
    if (draft.amount !== '' && draft.amount !== before.amount) body.amount = Number(draft.amount)
    if (draft.billingCycle && draft.billingCycle !== before.billingCycle) body.billingCycle = draft.billingCycle
    if (draft.currentPeriodEnd && draft.currentPeriodEnd !== before.currentPeriodEnd) body.currentPeriodEnd = draft.currentPeriodEnd
    if (draft.graceUntil) body.graceUntil = draft.graceUntil
    if (draft.cancelAtPeriodEnd !== Boolean(row.cancelAtPeriodEnd)) body.cancelAtPeriodEnd = draft.cancelAtPeriodEnd

    return action.run(async () => {
      const result = await updateAdminSubscription(row.orgId, body)
      if (!result.changed) return `Nothing changed for ${row.name}: the record already held those values.`
      return `Subscription updated for ${row.name} — ${result.before.plan}/${result.before.status} → ${result.after.plan}/${result.after.status}.`
        + (result.planResult?.effective === 'period_end'
          ? ` The downgrade to ${result.planResult.pendingPlan} applies at period end (${result.planResult.effectiveAt || '—'}).`
          : '')
    })
  }

  const setAccountStatus = (row: AdminOrgDetailRow, target: string) => action.run(async () => {
    const result = await setAdminAccountStatus(row.orgId, { status: target, reason: draft.reason || undefined })
    return `${row.name}: status ${result.before.status || '—'} → ${result.after.status || target}.`
  })

  const runActivation = (row: AdminOrgDetailRow, verb: 'request' | 'approve' | 'reset') => action.run(async () => {
    const result = await setAdminEnterpriseActivation(row.orgId, {
      action: verb,
      agreementAccepted: verb === 'approve' ? draft.agreement : undefined,
      contact: draft.contact || undefined,
    })
    return `Enterprise activation for ${row.name}: ${result.before || 'none'} → ${result.after || 'cleared'}.`
      + (result.checkoutAllowed ? ' Customer checkout is now allowed.' : ' Customer checkout stays blocked until the agreement is approved.')
  })

  const rename = (row: AdminOrgDetailRow) => action.run(async () => {
    const result = await renameAdminOrganization(row.orgId, { name: draft.name, reason: draft.reason || undefined })
    return `Workspace renamed to “${result.name}” (slug /${result.slug}).`
  })

  const provision = () => action.run(async () => {
    const result = await createAdminOrganization({
      name: newOrg.name,
      plan: newOrg.plan,
      ownerUserId: newOrg.ownerUserId || undefined,
      intendedOwnerEmail: newOrg.intendedOwnerEmail || undefined,
    })
    return `Provisioned “${result.organization.name}” on ${result.organization.plan} (owner ${shortId(result.ownerUserId, 16)}${
      result.pendingOwnerEmail ? `, pending owner ${result.pendingOwnerEmail}` : ''
    }).`
  })

  return (
    <AdminConsoleShell
      section="organizations"
      title="Organizations"
      description="Every workspace on the platform with the subscription state you manage. Plan changes run through the customer billing engine, Enterprise still needs the agreement, and nothing here deletes customer data."
      toolbar={(
        <div className="flex items-center gap-2 flex-wrap">
          <form
            onSubmit={e => { e.preventDefault(); setFilters({ search: searchInput.trim(), plan: planInput, status: statusInput }) }}
            className="flex items-center gap-1 flex-wrap"
          >
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="name, slug or org id"
              maxLength={120}
              className="w-44 px-2.5 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-xs text-slate-800 focus:outline-none focus:border-[#0B5D3B]"
            />
            <select value={planInput} onChange={e => setPlanInput(e.target.value)} className={INPUT_CLASS} aria-label="Plan filter">
              <option value="">any plan</option>
              {SUBSCRIPTION_PLANS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={statusInput} onChange={e => setStatusInput(e.target.value)} className={INPUT_CLASS} aria-label="Billing status filter">
              <option value="">any status</option>
              {SUBSCRIPTION_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button
              type="submit"
              className="px-3 py-1.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-[10px] font-extrabold uppercase tracking-wider transition"
            >
              Filter
            </button>
            {(filters.search || filters.plan || filters.status) ? (
              <button
                type="button"
                onClick={() => { setSearchInput(''); setPlanInput(''); setStatusInput(''); setFilters({ search: '', plan: '', status: '' }) }}
                className="px-2 py-1.5 rounded-lg border border-[#DDE6F0] text-[10px] font-extrabold uppercase tracking-wider text-slate-500 hover:border-[#0B5D3B] transition"
              >
                Clear
              </button>
            ) : null}
          </form>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))} className={INPUT_CLASS} aria-label="Rows">
            {LIMITS.map(n => <option key={n} value={n}>top {n}</option>)}
          </select>
          <WindowPicker value={windowDays} onChange={setWindowDays} />
        </div>
      )}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Organizations" />

      {action.outcome ? (
        <ActionFeedback
          ok={action.outcome.ok}
          message={action.outcome.message}
          code={action.outcome.code}
          onDismiss={action.clear}
        />
      ) : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Organizations" value={fmtInt(data.totals.organizations)} hint={`${fmtInt(data.totals.teamWorkspaces)} team · ${fmtInt(data.totals.personalWorkspaces)} personal · ${fmtInt(data.totals.createdInWindow)} in ${data.windowDays}d`} />
            <Metric label="Needs attention" value={fmtInt(data.totals.needsAttention)} hint={data.attentionDefinition} tone={data.totals.needsAttention ? 'bad' : 'good'} />
            <Metric label="Suspended / past due" value={`${fmtInt(data.totals.suspended)} / ${fmtInt(data.totals.pastDue)}`} hint={`in grace ${fmtInt(data.totals.inGrace)} · no subscription row ${fmtInt(data.totals.withoutSubscriptionRow)}`} />
            <Metric label="Enterprise" value={fmtInt(data.totals.enterprise)} hint={`${fmtInt(data.totals.activationRequested)} activation request(s) waiting · ${fmtInt(data.totals.scheduledChanges)} scheduled change(s)`} />
          </div>

          <Panel
            title="Workspaces"
            note="One row per organization, newest first. Billing figures are the subscription record itself; a workspace with no row bills as free and is listed as such rather than as a paid plan."
          >
            <Table
              headers={['Workspace', 'Plan', 'Billing', 'Members', 'Assessments', 'Docs / storage', 'Last activity', '']}
              rows={data.organizations.map(row => {
                const isOpen = openOrg === row.orgId
                return [
                  (
                    <div>
                      <div className="font-bold text-slate-900 flex items-center gap-1.5">
                        {row.name}
                        {row.personal ? <Pill>personal</Pill> : null}
                        {row.needsAttention ? <Pill tone="bad">attention</Pill> : null}
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">{shortId(row.orgId, 24)} · /{row.slug}</div>
                      <div className="text-[10px] text-slate-400">created by {shortId(row.createdBy, 16)} · owner {shortId(row.primaryOwnerUserId, 16)}</div>
                    </div>
                  ),
                  (
                    <div>
                      <span className="font-bold uppercase text-[11px]">{row.plan}</span>
                      {row.pendingPlan ? <div className="text-[10px] text-[#B54708]">pending {row.pendingPlan}</div> : null}
                      {row.subscriptionPlan && row.subscriptionPlan !== row.plan ? (
                        <div className="text-[10px] text-slate-400">sub: {row.subscriptionPlan}</div>
                      ) : null}
                    </div>
                  ),
                  (
                    <div className="flex flex-col gap-1">
                      {row.billingStatus
                        ? <Pill tone={STATUS_TONE[row.billingStatus] || 'neutral'}>{row.billingStatus}</Pill>
                        : <span className="text-[11px] text-slate-400 italic">no subscription row</span>}
                      <span className="text-[10px] text-slate-500">{row.amount === null ? NO_DATA : fmtMoney(row.amount, row.currency || 'KES')}</span>
                      {row.currentPeriodEnd ? <span className="text-[10px] text-slate-400">period ends {relTime(row.currentPeriodEnd)}</span> : null}
                      {row.cancelAtPeriodEnd ? <span className="text-[10px] font-bold text-[#B54708]">cancels at period end</span> : null}
                      {row.activationState ? <span className="text-[10px] uppercase font-bold text-[#B54708]">activation {row.activationState}</span> : null}
                      {row.lastError ? <span className="text-[10px] text-[#B42318] break-words">{String(row.lastError).slice(0, 60)}</span> : null}
                    </div>
                  ),
                  fmtInt(row.members),
                  <span>{fmtInt(row.assessments)}<span className="text-[10px] text-slate-400"> ({fmtInt(row.assessmentsInWindow)} in window)</span></span>,
                  <span>{fmtInt(row.documents)} · {fmtBytes(row.storageBytes)}</span>,
                  <span title={fmtDateTime(row.lastActivityAt)}>{row.lastActivityAt ? relTime(row.lastActivityAt) : NO_DATA}</span>,
                  (
                    <button
                      type="button"
                      onClick={() => openRow(row)}
                      className="px-2.5 py-1 rounded-lg border border-[#DDE6F0] text-[10px] font-extrabold uppercase tracking-wider text-slate-600 hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition whitespace-nowrap"
                    >
                      {isOpen ? 'Close' : 'Manage'}
                    </button>
                  ),
                ]
              })}
            />

            {openOrg && data.organizations.some(o => o.orgId === openOrg) ? (() => {
              const row = data.organizations.find(o => o.orgId === openOrg)!
              return (
                <div className="mt-4 rounded-[12px] border border-[#DDE6F0] bg-[#F8FAFC] p-4 flex flex-col gap-4">
                  <div className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">
                    Manage {row.name}
                    <span className="ml-2 font-mono font-bold text-slate-400 normal-case tracking-normal">{shortId(row.orgId, 28)}</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <Field label="Plan">
                      <select value={draft.plan} onChange={e => setDraft({ ...draft, plan: e.target.value })} className={INPUT_CLASS} disabled={!canSubscriptions}>
                        {SUBSCRIPTION_PLANS.map(p => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </Field>
                    <Field label="Status">
                      <select value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value })} className={INPUT_CLASS} disabled={!canSubscriptions}>
                        <option value="">unchanged</option>
                        {SUBSCRIPTION_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </Field>
                    <Field label="Amount">
                      <input value={draft.amount} onChange={e => setDraft({ ...draft, amount: e.target.value })} className={INPUT_CLASS} inputMode="decimal" disabled={!canSubscriptions} />
                    </Field>
                    <Field label="Currency">
                      <input value={draft.currency} onChange={e => setDraft({ ...draft, currency: e.target.value })} className={INPUT_CLASS} maxLength={8} disabled={!canSubscriptions} />
                    </Field>
                    <Field label="Billing cycle">
                      <input value={draft.billingCycle} onChange={e => setDraft({ ...draft, billingCycle: e.target.value })} className={INPUT_CLASS} maxLength={32} placeholder="monthly | annual" disabled={!canSubscriptions} />
                    </Field>
                    <Field label="Period end (ISO)">
                      <input value={draft.currentPeriodEnd} onChange={e => setDraft({ ...draft, currentPeriodEnd: e.target.value })} className={INPUT_CLASS} maxLength={40} placeholder="2026-11-01T00:00:00+00:00" disabled={!canSubscriptions} />
                    </Field>
                    <Field label="Grace until (ISO)">
                      <input
                        value={draft.graceUntil}
                        onChange={e => setDraft({ ...draft, graceUntil: e.target.value })}
                        className={INPUT_CLASS}
                        maxLength={40}
                        placeholder="2026-11-08T00:00:00+00:00"
                        disabled={!canSubscriptions}
                      />
                    </Field>
                    <Field label="Reason (audit trail)">
                      <input value={draft.reason} onChange={e => setDraft({ ...draft, reason: e.target.value })} className={INPUT_CLASS} maxLength={300} placeholder="why this change is being made" />
                    </Field>
                  </div>

                  <label className="flex items-center gap-2 text-xs text-slate-700">
                    <input type="checkbox" checked={draft.cancelAtPeriodEnd} onChange={e => setDraft({ ...draft, cancelAtPeriodEnd: e.target.checked })} disabled={!canSubscriptions} />
                    Cancels at period end
                    <span className="text-[10px] text-slate-400">— a flag on the subscription, not an immediate cancellation</span>
                  </label>

                  <div className="flex items-center gap-2 flex-wrap">
                    <ActionButton label="Apply changes" tone="good" allowed={canSubscriptions} busy={action.busy} onClick={() => { void applySubscription(row) }} />
                    {row.billingStatus === 'suspended'
                      ? <ActionButton label="Reactivate" allowed={canSubscriptions} busy={action.busy} onClick={() => { void setAccountStatus(row, 'active') }} />
                      : <ActionButton label="Suspend" tone="bad" allowed={canSubscriptions} busy={action.busy} onClick={() => { void setAccountStatus(row, 'suspended') }} />}
                    <span className="text-[10px] text-slate-400">Suspend / reactivate use the billing engine's own transitions and are audited separately.</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-3 border-t border-[#DDE6F0]">
                    <Field label="Workspace name">
                      <input value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} className={INPUT_CLASS} maxLength={120} disabled={!canAccounts} />
                    </Field>
                    <Field label="Enterprise contact">
                      <input value={draft.contact} onChange={e => setDraft({ ...draft, contact: e.target.value })} className={INPUT_CLASS} maxLength={200} placeholder="who requested Enterprise" disabled={!canAccounts} />
                    </Field>
                    <label className="flex items-end gap-2 text-xs text-slate-700 pb-1.5">
                      <input type="checkbox" checked={draft.agreement} onChange={e => setDraft({ ...draft, agreement: e.target.checked })} disabled={!canAccounts} />
                      Custom agreement accepted
                    </label>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <ActionButton label="Rename workspace" allowed={canAccounts} busy={action.busy} onClick={() => { void rename(row) }} />
                    <ActionButton label="Request activation" allowed={canAccounts} busy={action.busy} onClick={() => { void runActivation(row, 'request') }} />
                    <ActionButton
                      label="Approve activation"
                      tone="good"
                      allowed={canAccounts}
                      busy={action.busy}
                      title={draft.agreement ? 'Records your explicit acceptance of the custom agreement' : 'Tick “Custom agreement accepted” first — approval is never implicit'}
                      onClick={() => { void runActivation(row, 'approve') }}
                    />
                    <ActionButton label="Reset activation" tone="warn" allowed={canAccounts} busy={action.busy} onClick={() => { void runActivation(row, 'reset') }} />
                  </div>

                  <p className="text-[10px] text-slate-400 leading-relaxed">
                    Enterprise cannot be applied to a workspace whose activation is not approved — the same gate customer checkout
                    enforces. Applying plan “enterprise” here while activation is unapproved is refused, not silently allowed.
                  </p>
                </div>
              )
            })() : null}
          </Panel>

          <Panel
            title="Provision a workspace"
            note="A platform-provisioned account is never left unowned: the acting administrator holds Owner until a real principal is attached. A user id that has never signed in cannot be attached — a typed email is only a note, never a membership."
          >
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <Field label="Name">
                <input value={newOrg.name} onChange={e => setNewOrg({ ...newOrg, name: e.target.value })} className={INPUT_CLASS} maxLength={120} placeholder="Acme Agri Holdings" />
              </Field>
              <Field label="Plan">
                <select value={newOrg.plan} onChange={e => setNewOrg({ ...newOrg, plan: e.target.value })} className={INPUT_CLASS}>
                  {SUBSCRIPTION_PLANS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </Field>
              <Field label="Owner user id (must have signed in)">
                <input value={newOrg.ownerUserId} onChange={e => setNewOrg({ ...newOrg, ownerUserId: e.target.value })} className={INPUT_CLASS} maxLength={200} placeholder="optional" />
              </Field>
              <Field label="Intended owner email">
                <input value={newOrg.intendedOwnerEmail} onChange={e => setNewOrg({ ...newOrg, intendedOwnerEmail: e.target.value })} className={INPUT_CLASS} maxLength={200} placeholder="note only" />
              </Field>
              <div className="flex items-end">
                <ActionButton
                  label="Create workspace"
                  tone="good"
                  allowed={canAccounts}
                  busy={action.busy}
                  onClick={() => { void provision() }}
                />
              </div>
            </div>
          </Panel>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
