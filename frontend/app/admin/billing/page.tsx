'use client'

// Admin Console — Phase 3: billing.
//
// Money and provider configuration for the whole platform. Note what this page
// deliberately does *not* claim: amounts are only what the payment ledger
// recorded. A hosted-link payment that never carried an amount stays NULL and is
// counted without a figure, so revenue is never rounded up into existence.

import { useState } from 'react'
import AdminConsoleShell from '../../../components/AdminConsole/AdminConsoleShell'
import {
  BarList,
  DataNotes,
  FetchStatus,
  KV,
  Metric,
  Panel,
  Pill,
  Table,
  WindowPicker,
  fmtDateTime,
  fmtInt,
  fmtMoney,
  mapItems,
  shortId,
} from '../../../components/AdminConsole/adminUi'
import { useAdminFetch } from '../../../hooks/useAdminFetch'
import { getAdminBilling, type AdminPaymentEvent } from '../../../lib/admin'

const EVENT_TONE: Record<string, 'good' | 'warn' | 'bad' | 'info' | 'neutral'> = {
  payment_success: 'good',
  payment_received: 'good',
  payment_failed: 'bad',
  payment_cancelled: 'warn',
  checkout_initiated: 'info',
  plan_changed: 'info',
  downgrade_scheduled: 'warn',
  suspended: 'bad',
  reactivated: 'good',
  enterprise_activation_requested: 'warn',
  enterprise_agreement_approved: 'info',
}

function EventTable({ events }: { events: AdminPaymentEvent[] }) {
  return (
    <Table
      headers={['When', 'Event', 'Workspace', 'Plan', 'From', 'Amount', 'Ref']}
      rows={events.map(e => [
        fmtDateTime(e.createdAt),
        <Pill tone={EVENT_TONE[e.eventType] || 'neutral'}>{e.eventType}</Pill>,
        <div>
          <div className="font-bold text-slate-800">{e.orgName || <span className="text-slate-400 italic">unnamed</span>}</div>
          <div className="text-[10px] font-mono text-slate-400">{shortId(e.orgId, 18)}</div>
        </div>,
        <span className="font-bold uppercase text-[11px]">{e.plan || '—'}</span>,
        <span className="text-[11px] text-slate-500">{e.previousPlan ? `${e.previousPlan} →` : '—'}</span>,
        e.amount === null || e.amount === undefined
          ? <span className="text-[11px] text-slate-400 italic">not recorded</span>
          : <span className="tabular-nums font-bold">{fmtMoney(e.amount, e.currency || undefined)}</span>,
        <span className="font-mono text-[10px] text-slate-500">{shortId(e.txRef, 16)}</span>,
      ])}
    />
  )
}

export default function AdminBillingPage() {
  const [windowDays, setWindowDays] = useState(30)
  const { data, busy, error, denied, reload } = useAdminFetch(() => getAdminBilling(windowDays), [windowDays])

  return (
    <AdminConsoleShell
      section="billing"
      title="Billing Health"
      description="PayChangu configuration, plan status across every workspace, upgrade history and failed payments. Nothing here can be changed — plan changes are customer actions inside a workspace."
      toolbar={<WindowPicker value={windowDays} onChange={setWindowDays} />}
      onReload={reload}
      busy={busy}
    >
      <FetchStatus busy={busy} error={error} denied={denied} hasData={!!data} section="Billing" />

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric
              label={`Collected (${data.windowDays}d)`}
              value={fmtMoney(data.revenue.collectedInWindow, data.revenue.currency)}
              hint={`${fmtInt(data.revenue.collectedEventCount)} success events. ${data.revenue.note}`}
            />
            <Metric
              label="Active paid subscriptions"
              value={fmtInt(data.revenue.paidActiveSubscriptions)}
              hint={`Recurring value ${fmtMoney(data.revenue.recurringActivePaid, data.revenue.currency)} · ${fmtInt(data.revenue.paidWithoutAmount)} carry no recorded amount`}
            />
            <Metric
              label="Subscriptions tracked"
              value={fmtInt(data.planStatus.subscriptions)}
              hint={`${fmtInt(data.planStatus.organizations)} workspaces · ${fmtInt(data.planStatus.withoutSubscriptionRow)} with no subscription row yet`}
            />
            <Metric
              label="Failed / cancelled payments"
              value={fmtInt(data.failedPayments.count)}
              hint={`Within the ledger read. Upgrade events: ${fmtInt(data.upgradeHistory.count)}`}
              tone={data.failedPayments.count > 0 ? 'bad' : 'good'}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel
              title="PayChangu"
              note={data.paychangu.modeNote}
              right={<Pill tone={data.paychangu.demoMode ? 'warn' : 'good'}>{data.paychangu.demoMode ? 'demo mode' : data.paychangu.mode}</Pill>}
            >
              <div className="flex flex-col">
                <KV label="API secret" value={data.paychangu.apiSecretConfigured ? <Pill tone="good">configured</Pill> : <Pill tone="warn">not set (hosted links only)</Pill>} />
                <KV label="Webhook secret" value={data.paychangu.webhookSecretConfigured ? <Pill tone="good">configured</Pill> : <Pill tone="warn">not set</Pill>} />
                <KV label="Quota enforcement" value={data.paychangu.enforcementEnabled ? <Pill tone="good">enabled</Pill> : <Pill tone="info">off — plans reported, not enforced</Pill>} />
                <KV label="Link auto-confirm" value={data.paychangu.linkAutoconfirm ? <Pill tone="info">on return</Pill> : <Pill>webhook only</Pill>} />
                <KV label="Currency / grace" value={`${data.paychangu.currency} · ${data.paychangu.gracePeriodDays} days`} />
                <KV label="Base URL" value={<span className="font-mono text-[11px]">{data.paychangu.baseUrl}</span>} />
              </div>
            </Panel>

            <Panel
              title="Payment links by plan"
              note="Hosted links are created in PayChangu and stored on the plan definition. Enterprise links stay closed until an agreement is approved."
            >
              <Table
                headers={['Plan', 'Price', 'Link', 'Approval']}
                rows={data.paychangu.paymentLinks.map(l => [
                  <div>
                    <div className="font-bold text-slate-800">{l.name}</div>
                    <div className="text-[10px] font-mono text-slate-400">{l.planId}</div>
                  </div>,
                  l.priceLabel,
                  l.link
                    ? <a href={l.link} target="_blank" rel="noreferrer" className="text-[11px] font-bold text-[#0B5D3B] underline">open</a>
                    : <span className="text-[11px] text-slate-400 italic">not configured</span>,
                  l.requiresApproval ? <Pill tone="warn">required</Pill> : <Pill>self-serve</Pill>,
                ])}
              />
            </Panel>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Panel title="Plan status by subscription state" note={`Known states: ${data.planStatus.knownStatuses.join(', ')}.`}>
              <BarList items={mapItems(data.planStatus.byStatus)} emptyLabel="NO DATA — no subscription rows." />
            </Panel>
            <Panel title="Plan status by plan">
              <BarList items={mapItems(data.planStatus.byPlan)} emptyLabel="NO DATA — no subscription rows." />
            </Panel>
          </div>

          <Panel
            title="Needs attention"
            note="Grace, past due, suspended, cancelled, an unresolved last error, or an enterprise activation still requested. Empty means every subscription is clean."
          >
            <Table
              headers={['Workspace', 'Plan', 'Status', 'Grace until', 'Pending plan', 'Activation', 'Last error']}
              rows={data.planStatus.attention.map(a => [
                <div>
                  <div className="font-bold text-slate-800">{a.orgName || <span className="text-slate-400 italic">unnamed</span>}</div>
                  <div className="text-[10px] font-mono text-slate-400">{shortId(a.orgId, 18)}</div>
                </div>,
                <span className="font-bold uppercase text-[11px]">{a.plan}</span>,
                <Pill tone={a.status === 'past_due' || a.status === 'suspended' ? 'bad' : 'warn'}>{a.status}</Pill>,
                fmtDateTime(a.graceUntil),
                a.pendingPlan || '—',
                a.activationState || '—',
                <span className="text-[11px] text-[#B42318]">{a.lastError || ''}</span>,
              ])}
            />
          </Panel>

          <Panel
            title="Upgrade history"
            note={`Plan movement and checkout events in the ledger (${fmtInt(data.upgradeHistory.count)} of ${fmtInt(data.ledger.count)} events shown, newest first).`}
          >
            <EventTable events={data.upgradeHistory.events} />
          </Panel>

          <Panel title="Failed payments" note="payment_failed / payment_cancelled events, plus any event whose recorded status says failed or cancelled.">
            <EventTable events={data.failedPayments.events} />
          </Panel>

          <Panel title="Full payment ledger" note="Newest 40 events of any kind — the raw trail behind the numbers above.">
            <EventTable events={data.ledger.recent} />
          </Panel>

          <DataNotes notes={data.dataNotes} />
        </>
      ) : null}
    </AdminConsoleShell>
  )
}
