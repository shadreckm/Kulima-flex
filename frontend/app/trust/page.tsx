'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getGovernanceSummary, type AuditEventRecord, type GovernanceSummary } from '../../lib/enterprise'

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`
}

function formatWhen(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function StatCard({ label, value, hint, tone = 'default' }: { label: string; value: string; hint?: string; tone?: 'default' | 'warn' | 'good' }) {
  const toneClass = tone === 'warn' ? 'text-amber-700' : tone === 'good' ? 'text-[#0B5D3B]' : 'text-slate-900'
  return (
    <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
      <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1.5 text-2xl font-black tracking-tight ${toneClass}`}>{value}</div>
      {hint ? <div className="mt-1 text-[11px] text-slate-400">{hint}</div> : null}
    </div>
  )
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[#EEF3F9] last:border-b-0">
      <span className="text-xs text-slate-500 font-semibold">{label}</span>
      <span className={`text-xs font-bold flex items-center gap-1.5 ${ok === false ? 'text-amber-700' : 'text-slate-900'}`}>
        {ok != null ? (
          <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-[#12B76A]' : 'bg-[#F79009]'}`} />
        ) : null}
        {value}
      </span>
    </div>
  )
}

export default function TrustGovernancePage() {
  const { status: authStatus } = useSession()
  const [summary, setSummary] = useState<GovernanceSummary | null>(null)
  const [activity, setActivity] = useState<AuditEventRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const data = await getGovernanceSummary()
      if (cancelled) return
      setSummary(data)
      setActivity(data.audit.recent || [])
    }
    if (authStatus === 'authenticated') {
      load().catch(err => setError(String(err)))
    }
    return () => { cancelled = true }
  }, [authStatus])

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

  const security = summary?.security
  const retention = summary?.retention
  const documents = summary?.documents
  const byRole = summary?.members.byRole || {}

  return (
    <PilotWorkspaceShell
      workspace="Trust & Governance"
      title="Trust & Governance"
      description="Security posture, privacy controls, audit trail and data custody for this workspace."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
          <div className="mt-1 text-xs text-red-600">
            The Trust &amp; Governance dashboard requires the <span className="font-bold">view audit</span> permission (Owner or Admin role).
          </div>
        </div>
      ) : null}

      {!summary && !error ? (
        <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-sm font-semibold text-slate-500">
          Loading governance posture…
        </div>
      ) : null}

      {summary ? (
        <>
          <section className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard label="Documents Stored" value={String(documents?.total ?? 0)} hint={`${documents?.active ?? 0} active · ${formatBytes(documents?.storageBytes ?? 0)}`} />
            <StatCard label="Active Assessments" value={String(summary.assessments.active)} hint={`${summary.assessments.total} total`} />
            <StatCard label="Audit Events" value={String(summary.audit.totalEvents)} hint={`Last: ${formatWhen(summary.audit.lastEventAt)}`} />
            <StatCard label="Workspace Members" value={String(summary.members.total)} hint={`${Object.entries(byRole).map(([role, count]) => `${count} ${role}`).join(' · ') || '—'}`} />
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">
                Security Status
              </h2>
              <StatusRow
                label="Storage encryption scheme"
                value={security?.atRestScheme === 'aes-256-gcm' ? 'AES-256-GCM (application level)' : 'Provider disk encryption'}
                ok={security?.atRestEncryptionAvailable === true}
              />
              <StatusRow label="Encrypted storage metadata" value={security?.storageMetadataRecorded ? 'Recorded for every document' : 'Not recorded'} ok={security?.storageMetadataRecorded} />
              <StatusRow label="Access checks" value={security?.accessChecks ? 'Enforced on every document route' : 'Off'} ok={security?.accessChecks} />
              <StatusRow label="Workspace isolation" value="Organization-scoped queries" ok />
              <StatusRow label="Private by default" value={security?.privateByDefault ? 'Documents visible only inside the workspace' : 'Off'} ok={security?.privateByDefault} />
              <StatusRow
                label="External research guard"
                value={security?.externalResearchGuard.enabled ? `Metadata-only egress to ${security.externalResearchGuard.provider}` : 'Disabled'}
                ok={security?.externalResearchGuard.enabled}
              />
              <div className="mt-3 p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                  Fields allowed in external research
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(security?.externalResearchGuard.allowedFields || []).map(field => (
                    <span key={field} className="px-2 py-0.5 rounded-md bg-white border border-[#DDE6F0] text-[10px] font-semibold text-slate-600">
                      {field.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">
                Data Retention Status
              </h2>
              <StatusRow label="Documents pending deletion" value={retention ? String(retention.deletedPending) : '—'} ok={(retention?.deletedPending ?? 0) === 0} />
              <StatusRow label="Expired documents" value={retention ? String(retention.expired) : '—'} ok={(retention?.expired ?? 0) === 0} />
              <StatusRow
                label="Default retention window"
                value={retention?.defaultRetentionDays ? `${retention.defaultRetentionDays} days` : 'Customer-controlled (no automatic expiry)'}
              />
              <StatusRow label="Soft delete" value={security?.softDeleteEnabled ? 'Enabled (recoverable window)' : 'Disabled'} ok={security?.softDeleteEnabled} />
              <p className="mt-3 text-xs text-slate-500 leading-relaxed">{retention?.policySummary}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link href="/legal/data-retention" className="text-xs font-bold text-[#0B5D3B] hover:underline">
                  Data Retention Policy →
                </Link>
                <Link href="/privacy" className="text-xs font-bold text-[#0B5D3B] hover:underline">
                  Privacy &amp; Data Ownership →
                </Link>
                <Link href="/billing" className="text-xs font-bold text-[#0B5D3B] hover:underline">
                  Plan &amp; Billing →
                </Link>
              </div>
            </div>
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">
                User Roles
              </h2>
              <div className="space-y-2">
                {['owner', 'admin', 'reviewer', 'viewer'].map(role => (
                  <div key={role} className="flex items-center justify-between p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">{role}</span>
                    <span className="text-sm font-black text-slate-900">{byRole[role] || 0}</span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11px] text-slate-400">
                RBAC is enforced on every API route: Owner (full), Admin (user management), Reviewer (can assess), Viewer (read-only).
              </p>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">
                Recent Audit Events
              </h2>
              {activity.length === 0 ? (
                <div className="text-sm text-slate-500 font-semibold py-2">No audit events recorded yet.</div>
              ) : (
                <div className="space-y-2">
                  {activity.map(event => (
                    <div key={event.id} className="flex items-start justify-between gap-3 p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                      <div className="min-w-0">
                        <div className="text-xs font-bold text-slate-900">{event.label}</div>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          {event.category}
                          {event.assessmentId ? ` · assessment ${String(event.assessmentId).slice(0, 8)}…` : ''}
                          {event.runId ? ` · run ${String(event.runId).slice(0, 8)}…` : ''}
                        </div>
                      </div>
                      <div className="text-[10px] text-slate-400 whitespace-nowrap font-mono">{formatWhen(event.createdAt)}</div>
                    </div>
                  ))}
                </div>
              )}
              <p className="mt-3 text-[11px] text-slate-400">
                The audit trail is append-only. Deletions are recorded, never rewritten.
              </p>
            </div>
          </section>
        </>
      ) : null}
    </PilotWorkspaceShell>
  )
}
