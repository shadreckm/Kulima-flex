'use client'

import React, { useCallback, useEffect, useState } from 'react'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import {
  cancelSubscription,
  confirmDemoCheckout,
  downgradePlan,
  getBillingHistory,
  getBillingPlans,
  getBillingStatus,
  reactivateSubscription,
  startCheckout,
  type BillingPlan,
  type BillingStatusPayload,
  type PaymentEventRecord,
} from '../../lib/enterprise'

const PLAN_ORDER: Record<string, number> = { free: 0, pro: 1, enterprise: 2 }

function formatMoney(amount: number, currency: string): string {
  if (amount === 0) return 'Free'
  return `${currency} ${amount.toFixed(0)}/month`
}

function formatWhen(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: 'bg-[#EAF7EF] text-[#0B5D3B] border-[#C9EBD8]',
    grace: 'bg-[#FFF7EB] text-[#B54708] border-[#F5DEB8]',
    past_due: 'bg-[#FFF7EB] text-[#B54708] border-[#F5DEB8]',
    suspended: 'bg-[#FEF3F2] text-[#B42318] border-[#FDA29B]',
    canceled: 'bg-[#F5F8FC] text-slate-600 border-[#DDE6F0]',
  }
  const cls = styles[status] || styles.active
  return (
    <span className={`px-2.5 py-1 rounded-md border text-[10px] font-black uppercase tracking-wider ${cls}`}>
      {status.replace('_', ' ')}
    </span>
  )
}

export default function BillingPage() {
  const { status: authStatus } = useSession()
  const [plans, setPlans] = useState<BillingPlan[]>([])
  const [billing, setBilling] = useState<BillingStatusPayload | null>(null)
  const [history, setHistory] = useState<PaymentEventRecord[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [demoTx, setDemoTx] = useState<{ txRef: string; plan: string } | null>(null)

  const load = useCallback(async () => {
    const [plansRes, statusRes, historyRes] = await Promise.all([
      getBillingPlans(),
      getBillingStatus(),
      getBillingHistory(),
    ])
    setPlans(plansRes.plans)
    setBilling(statusRes)
    setHistory(historyRes.events)
  }, [])

  useEffect(() => {
    if (authStatus === 'authenticated') {
      load().catch(err => setError(String(err)))
    }
  }, [authStatus, load])

  async function run(label: string, fn: () => Promise<string | null>) {
    setBusy(label)
    setError(null)
    setNotice(null)
    try {
      const message = await fn()
      if (message) setNotice(message)
      await load()
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(null)
    }
  }

  const handleChoose = (planId: string) =>
    run(`choose-${planId}`, async () => {
      const current = billing?.planId || 'free'
      if ((PLAN_ORDER[planId] ?? 0) < (PLAN_ORDER[current] ?? 0) && planId !== 'free') {
        await downgradePlan(planId)
        return `Downgrade to ${planId} scheduled.`
      }
      const result = await startCheckout(planId)
      if (result.demoMode && result.txRef) {
        setDemoTx({ txRef: result.txRef, plan: planId })
        return 'PayChangu is not configured on this deployment — demo checkout prepared.'
      }
      if (result.checkoutUrl) {
        window.location.href = result.checkoutUrl
        return null
      }
      if (result.status === 'applied') {
        return 'Plan change applied.'
      }
      return 'Checkout started.'
    })

  const handleConfirmDemo = () =>
    run('confirm-demo', async () => {
      if (!demoTx) return null
      const result = await confirmDemoCheckout(demoTx.txRef, demoTx.plan)
      setDemoTx(null)
      return `Demo payment confirmed — plan is now ${result.planId}.`
    })

  const handleDowngradeFree = () =>
    run('downgrade-free', async () => {
      const result = await downgradePlan('free')
      const scheduled = (result.result as { effective?: string })?.effective
      return scheduled === 'period_end'
        ? `Downgrade to Free scheduled for ${formatWhen(result.status.periodEnd)}.`
        : 'Downgrade to Free applied.'
    })

  const handleCancel = () =>
    run('cancel', async () => {
      await cancelSubscription()
      return 'Subscription set to cancel at the end of the current period.'
    })

  const handleReactivate = () =>
    run('reactivate', async () => {
      await reactivateSubscription()
      return 'Subscription reactivated. All features restored.'
    })

  if (authStatus === 'loading') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">
        Checking session…
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
        <button
          onClick={() => signIn()}
          className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm"
        >
          Sign in
        </button>
      </div>
    )
  }

  const canManage = billing?.canManageBilling ?? false

  return (
    <PilotWorkspaceShell
      workspace="Billing"
      title="Plan & Billing"
      description="Subscription status, plan catalogue and payment history. Billing never blocks access to your data."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div>
      ) : null}
      {notice ? (
        <div className="p-4 bg-[#EAF7EF] text-[#0B5D3B] rounded-[12px] border border-[#C9EBD8] text-sm font-medium">{notice}</div>
      ) : null}

      {billing ? (
        <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#DDE6F0]">
            <div>
              <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Current Plan</div>
              <div className="flex items-center gap-2.5 mt-1">
                <span className="text-xl font-black text-slate-900">{billing.planName}</span>
                <StatusBadge status={billing.status} />
                {billing.cancelAtPeriodEnd ? (
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 bg-[#FFF7EB] px-2 py-1 rounded-md border border-[#F5DEB8]">
                    Cancels {formatWhen(billing.periodEnd)}
                  </span>
                ) : null}
                {billing.pendingPlan ? (
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 bg-[#F5F8FC] px-2 py-1 rounded-md border border-[#DDE6F0]">
                    {billing.pendingPlan} scheduled
                  </span>
                ) : null}
              </div>
            </div>
            <div className="text-right text-xs text-slate-500">
              <div>{billing.orgName}</div>
              <div className="mt-0.5">
                Current period: {formatWhen(billing.periodStart)} → {formatWhen(billing.periodEnd)}
              </div>
            </div>
          </div>

          {billing.status === 'suspended' ? (
            <div className="mt-3 p-3 bg-[#FEF3F2] border border-[#FDA29B] rounded-lg text-xs text-[#B42318] font-semibold">
              This workspace is suspended — new assessments are blocked. Your data remains readable and exportable.
              Reactivate or complete payment to resume.
            </div>
          ) : null}
          {billing.inGrace ? (
            <div className="mt-3 p-3 bg-[#FFF7EB] border border-[#F5DEB8] rounded-lg text-xs text-[#B54708] font-semibold">
              A recent payment failed. Grace period ends {formatWhen(billing.graceUntil)} — then new assessments pause
              until payment is resolved.
            </div>
          ) : null}

          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Assessments this month</div>
              <div className="text-xl font-black text-slate-900 mt-1">
                {billing.usage.assessmentsThisMonth}
                <span className="text-xs text-slate-400 font-bold">
                  {billing.usage.unlimited ? ' / unlimited' : ` / ${billing.usage.assessmentQuota}`}
                </span>
              </div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Quota remaining</div>
              <div className="text-xl font-black text-slate-900 mt-1">{billing.usage.unlimited ? '∞' : billing.usage.remaining}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Currency</div>
              <div className="text-xl font-black text-slate-900 mt-1">{billing.currency}</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Enforcement</div>
              <div className="text-xl font-black text-slate-900 mt-1">{billing.enforcementEnabled ? 'On' : 'Pilot (off)'}</div>
            </div>
          </div>

          {!canManage ? (
            <p className="mt-3 text-[11px] text-slate-400">
              Plan changes require the manage-billing permission (Owner). You can still view the plan and history.
            </p>
          ) : null}
        </section>
      ) : null}

      {demoTx ? (
        <section className="p-5 bg-[#EFF8FF] rounded-[12px] border border-[#D6E8FF] shadow-saas">
          <div className="text-sm font-extrabold text-[#004085]">Demo checkout pending</div>
          <p className="mt-1 text-xs text-[#004085]/80">
            PayChangu is not configured on this deployment. Transaction reference <span className="font-mono font-bold">{demoTx.txRef}</span> for
            the <span className="font-bold uppercase">{demoTx.plan}</span> plan. Confirm below to simulate a successful payment.
          </p>
          <button
            onClick={handleConfirmDemo}
            disabled={busy !== null}
            className="mt-3 px-4 py-2 rounded-lg bg-[#004085] text-white text-xs font-bold hover:bg-[#003266] transition disabled:opacity-50"
          >
            {busy === 'confirm-demo' ? 'Confirming…' : 'Confirm demo payment'}
          </button>
        </section>
      ) : null}

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {plans.map(plan => {
          const isCurrent = billing?.planId === plan.planId
          return (
            <div
              key={plan.planId}
              className={`p-5 bg-white rounded-[12px] border shadow-saas flex flex-col ${
                isCurrent ? 'border-[#0B5D3B] ring-1 ring-[#0B5D3B]/20' : 'border-[#DDE6F0]'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">{plan.name}</div>
                {isCurrent ? (
                  <span className="text-[10px] font-black uppercase tracking-wider text-[#0B5D3B] bg-[#EAF7EF] border border-[#C9EBD8] px-2 py-0.5 rounded">
                    Current
                  </span>
                ) : null}
              </div>
              <div className="mt-2 text-lg font-black text-slate-900">{formatMoney(plan.monthlyPrice, plan.currency)}</div>
              <p className="mt-2 text-xs text-slate-500 leading-relaxed">{plan.description}</p>
              <div className="mt-3 space-y-1.5 text-[11px] text-slate-600 flex-1">
                <div className="font-bold text-slate-700">{plan.assessmentQuotaLabel}</div>
                <div className="font-bold text-slate-700">{plan.memberQuotaLabel}</div>
                {plan.featureLabels.map(feature => (
                  <div key={feature} className="flex items-start gap-1.5">
                    <span className="text-[#12B76A] font-black">✓</span>
                    <span>{feature}</span>
                  </div>
                ))}
              </div>
              {canManage ? (
                <button
                  onClick={() => handleChoose(plan.planId)}
                  disabled={isCurrent || busy !== null}
                  className={`mt-4 px-4 py-2 rounded-lg text-xs font-bold transition ${
                    isCurrent
                      ? 'bg-[#F5F8FC] text-slate-400 border border-[#DDE6F0] cursor-default'
                      : plan.planId === 'free'
                        ? 'border border-[#DDE6F0] text-slate-700 hover:bg-[#F5F8FC]'
                        : 'bg-[#0B5D3B] text-white hover:bg-[#08482E]'
                  } disabled:opacity-60`}
                >
                  {isCurrent
                    ? 'Active plan'
                    : busy === `choose-${plan.planId}`
                      ? 'Working…'
                      : plan.planId === 'free'
                        ? 'Schedule downgrade'
                        : (PLAN_ORDER[plan.planId] ?? 0) < (PLAN_ORDER[billing?.planId || 'free'] ?? 0)
                          ? `Downgrade to ${plan.name}`
                          : `Upgrade to ${plan.name}`}
                </button>
              ) : null}
            </div>
          )
        })}
      </section>

      {canManage && billing && billing.planId !== 'free' ? (
        <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[220px]">
            <div className="text-sm font-extrabold text-slate-900">Manage subscription</div>
            <p className="text-xs text-slate-500 mt-0.5">
              Downgrades apply at period end. Cancelling never deletes data — the workspace simply returns to Free at the end of the paid period.
            </p>
          </div>
          <div className="flex gap-2">
            {billing.planId !== 'free' && !billing.cancelAtPeriodEnd ? (
              <button
                onClick={handleDowngradeFree}
                disabled={busy !== null}
                className="px-3 py-2 rounded-lg border border-[#DDE6F0] text-xs font-bold text-slate-700 hover:bg-[#F5F8FC] transition disabled:opacity-50"
              >
                {busy === 'downgrade-free' ? 'Scheduling…' : 'Downgrade to Free'}
              </button>
            ) : null}
            {!billing.cancelAtPeriodEnd ? (
              <button
                onClick={handleCancel}
                disabled={busy !== null}
                className="px-3 py-2 rounded-lg border border-[#FDA29B] text-xs font-bold text-[#B42318] hover:bg-[#FEF3F2] transition disabled:opacity-50"
              >
                {busy === 'cancel' ? 'Cancelling…' : 'Cancel at period end'}
              </button>
            ) : (
              <button
                onClick={handleReactivate}
                disabled={busy !== null}
                className="px-3 py-2 rounded-lg bg-[#0B5D3B] text-xs font-bold text-white hover:bg-[#08482E] transition disabled:opacity-50"
              >
                {busy === 'reactivate' ? 'Reactivating…' : 'Reactivate subscription'}
              </button>
            )}
          </div>
        </section>
      ) : null}

      {billing?.status === 'suspended' && canManage ? (
        <section className="p-5 bg-[#FEF3F2] rounded-[12px] border border-[#FDA29B] shadow-saas flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[220px]">
            <div className="text-sm font-extrabold text-[#B42318]">Account suspended</div>
            <p className="text-xs text-[#B42318]/80 mt-0.5">
              Complete a payment for a paid plan or reactivate to restore assessment creation. Reading and exporting always remain available.
            </p>
          </div>
          <button
            onClick={handleReactivate}
            disabled={busy !== null}
            className="px-4 py-2 rounded-lg bg-[#B42318] text-white text-xs font-bold hover:bg-[#912018] transition disabled:opacity-50"
          >
            {busy === 'reactivate' ? 'Reactivating…' : 'Reactivate workspace'}
          </button>
        </section>
      ) : null}

      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">
          Payment History
        </h2>
        {history.length === 0 ? (
          <div className="text-sm text-slate-500 font-semibold py-2">No payment events recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-slate-400 border-b border-[#DDE6F0]">
                  <th className="py-2 pr-4 font-bold">When</th>
                  <th className="py-2 pr-4 font-bold">Event</th>
                  <th className="py-2 pr-4 font-bold">Plan</th>
                  <th className="py-2 pr-4 font-bold">Amount</th>
                  <th className="py-2 pr-4 font-bold">Status</th>
                  <th className="py-2 font-bold">Reference</th>
                </tr>
              </thead>
              <tbody>
                {history.map(event => (
                  <tr key={event.id} className="border-b border-[#EEF3F9] last:border-b-0">
                    <td className="py-2.5 pr-4 text-slate-500 whitespace-nowrap">{formatWhen(event.createdAt)}</td>
                    <td className="py-2.5 pr-4 font-bold text-slate-800">{event.eventType.replace(/_/g, ' ')}</td>
                    <td className="py-2.5 pr-4 text-slate-600 uppercase">{event.plan || '—'}</td>
                    <td className="py-2.5 pr-4 text-slate-600">
                      {event.amount != null ? `${event.currency || billing?.currency || 'USD'} ${Number(event.amount).toFixed(2)}` : '—'}
                    </td>
                    <td className="py-2.5 pr-4 text-slate-600">{event.status || '—'}</td>
                    <td className="py-2.5 font-mono text-[10px] text-slate-400">{event.txRef || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="p-4 bg-[#F5F8FC] rounded-[12px] border border-[#DDE6F0] text-[11px] text-slate-500 leading-relaxed">
        Payments are processed by PayChangu. Failed payments enter a {billing?.gracePeriodDays ?? 7}-day grace period before the
        workspace pauses new assessments. Your data is never held hostage: reading, exporting and deleting always remain available.
        See the <a className="font-bold text-[#0B5D3B] hover:underline" href="/legal/terms-of-use">Terms of Use</a> and{' '}
        <a className="font-bold text-[#0B5D3B] hover:underline" href="/legal/data-retention">Data Retention Policy</a>.
      </section>
    </PilotWorkspaceShell>
  )
}
