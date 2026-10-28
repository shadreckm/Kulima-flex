'use client'

// Admin Console chrome — the gate and the frame every platform screen shares.
//
// Deliberately NOT PilotWorkspaceShell: that shell is the customer workspace
// (active assessment capsule, pipeline tracker, org-scoped navigation). This
// console is internal tooling that reads and manages *every* workspace, so it
// gets its own frame and its own access check.
//
// The check is a real one, not decorative: the page renders data only after
// /api/v1/admin/session says this identity holds the stored PLATFORM_ADMIN role.
// That role lives in its own table on the platform plane — it is not a value in
// the organization role enum, because organization rows are written by
// customers. The backend enforces the same rule, plus one declared capability
// per route, on every section endpoint, so a bypassed UI would still get 403s.

import React, { useEffect } from 'react'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import KulimaLogo from '../KulimaLogo/KulimaLogo'
import { StateBlock } from './adminUi'
import { usePlatformAdmin, primePlatformAdminCache } from '../../hooks/usePlatformAdmin'
import {
  ALL_CAPABILITIES,
  CAPABILITY_LABELS,
  hasCapability,
  isBreakGlass,
  type AdminCapability,
  type AdminSession,
} from '../../lib/admin'

export type AdminSectionId =
  | 'overview'
  | 'organizations'
  | 'users'
  | 'assessments'
  | 'reports'
  | 'conversations'
  | 'outcomes'
  | 'billing'
  | 'ai-health'
  | 'audit'
  | 'access'

export type AdminSection = {
  id: AdminSectionId
  label: string
  href: string
  /** Shown in the breadcrumb: what kind of platform work this panel is. */
  kind: string
  /** The capability the backend requires for this panel's primary route. */
  capability: AdminCapability
}

export const ADMIN_SECTIONS: AdminSection[] = [
  { id: 'overview', label: 'Overview', href: '/admin', kind: 'Analytics', capability: 'view_analytics' },
  { id: 'organizations', label: 'Organizations', href: '/admin/organizations', kind: 'Accounts', capability: 'view_organizations' },
  { id: 'users', label: 'Users', href: '/admin/users', kind: 'Accounts', capability: 'view_users' },
  { id: 'assessments', label: 'Assessments', href: '/admin/assessments', kind: 'Content', capability: 'view_analytics' },
  { id: 'reports', label: 'Reports', href: '/admin/reports', kind: 'Content', capability: 'view_analytics' },
  { id: 'conversations', label: 'Conversations', href: '/admin/conversations', kind: 'Content', capability: 'view_analytics' },
  { id: 'outcomes', label: 'Outcome Reviews', href: '/admin/outcomes', kind: 'Intelligence', capability: 'view_analytics' },
  { id: 'billing', label: 'Billing', href: '/admin/billing', kind: 'Revenue', capability: 'view_billing' },
  { id: 'ai-health', label: 'Provider Health', href: '/admin/ai-health', kind: 'Reliability', capability: 'view_provider_health' },
  { id: 'audit', label: 'Audit Logs', href: '/admin/audit', kind: 'Governance', capability: 'view_audit' },
  { id: 'access', label: 'Administrators', href: '/admin/access', kind: 'Governance', capability: 'manage_platform_admins' },
]

// The two reasons the backend says "no", mirrored from
// backend/app/core/admin_access.py (REASON_NOT_CONFIGURED / REASON_NOT_ALLOWLISTED).
const REASON_NOT_CONFIGURED = 'not_configured'
const REASON_NOT_ALLOWLISTED = 'not_allowlisted'

function denialCopy(reason: string, role: string): { title: string; body: string } {
  if (reason === REASON_NOT_CONFIGURED) {
    return {
      title: 'No platform administrator is provisioned',
      body: 'The console is fail-closed: the PLATFORM_ADMIN role store has no active row and no break-glass '
        + 'identity is configured, so access is denied to everyone — including you. Provision the primary '
        + 'administrator with KULIMA_PLATFORM_ADMIN_EMAILS, or set KULIMA_PLATFORM_ADMIN_USER_IDS / '
        + 'KULIMA_ADMIN_EMAILS as break-glass. An unconfigured environment must never default to "everyone is '
        + 'a platform administrator".',
    }
  }
  if (reason === REASON_NOT_ALLOWLISTED) {
    return {
      title: 'PLATFORM_ADMIN role required',
      body: `Your account does not hold the PLATFORM_ADMIN role, and your organization role ("${role || 'unknown'}") `
        + 'does not grant it. That separation is the point: this console reads and manages every customer '
        + 'workspace, so an Org Owner, Admin, Reviewer, Contributor or Viewer cannot reach it. An existing '
        + 'platform administrator can grant you the role on the Administrators panel.',
    }
  }
  // An unrecognized reason is never treated as a grant.
  return {
    title: 'PLATFORM_ADMIN role required',
    body: 'The backend refused platform access for a reason this screen does not recognise '
        + `("${reason || 'none reported'}"), so nothing was loaded. Access is denied by default — check the `
        + 'PLATFORM_ADMIN role store and the break-glass configuration on the backend.',
  }
}

/**
 * Does this payload describe capabilities at all? A session from a backend that
 * predates the capability matrix carries none, and "absent" must not be read as
 * "denied" — the route still enforces its own check, so the honest behaviour is
 * to render the panel and let the request decide.
 */
function capabilitiesReported(session: AdminSession | null): boolean {
  return Array.isArray(session?.capabilities) && (session?.capabilities.length ?? 0) > 0
}

export function AdminConsoleShell({
  section,
  title,
  description,
  toolbar,
  onReload,
  busy,
  children,
}: {
  section: AdminSectionId
  title: string
  description?: string
  toolbar?: React.ReactNode
  onReload?: () => void
  busy?: boolean
  children: React.ReactNode
}) {
  const { status: authStatus } = useSession()
  const { session, loading, refresh } = usePlatformAdmin(authStatus === 'authenticated')
  const active = ADMIN_SECTIONS.find(s => s.id === section) || ADMIN_SECTIONS[0]

  // Keep the shared probe cache warm so the sidebar affordance agrees with
  // what this page just verified.
  useEffect(() => {
    if (session) primePlatformAdminCache(session)
  }, [session])

  let body: React.ReactNode
  if (authStatus === 'loading') {
    body = <StateBlock kind="loading" title="Checking session…" body="Verifying your sign-in before the console reads any platform data." />
  } else if (authStatus === 'unauthenticated') {
    body = (
      <StateBlock
        kind="info"
        title="Sign in to open the console"
        body="The platform console sits behind the same authentication as the customer product, then adds the PLATFORM_ADMIN role check on top. You return here after signing in."
        action={(
          <Link
            href="/auth/signin?callbackUrl=%2Fadmin"
            className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-xs font-extrabold uppercase tracking-wider transition"
          >
            Sign in
          </Link>
        )}
      />
    )
  } else if (loading && !session) {
    body = <StateBlock kind="loading" title="Verifying platform administrator access…" body="Asking the backend whether this identity holds the PLATFORM_ADMIN role." />
  } else if (!session) {
    body = (
      <StateBlock
        kind="error"
        title="Could not verify platform administrator access"
        body="The backend did not answer the access probe (network or server error). No platform data has been loaded. Nothing here is cached, so retry once the service is reachable."
        action={(
          <button
            type="button"
            onClick={() => { void refresh() }}
            className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] hover:bg-[#08482E] text-white text-xs font-extrabold uppercase tracking-wider transition"
          >
            Retry
          </button>
        )}
      />
    )
  } else if (!session.isPlatformAdmin) {
    const copy = denialCopy(session.reason, session.identity?.role || '')
    body = (
      <StateBlock
        kind="denied"
        title={copy.title}
        body={copy.body}
        action={(
          <Link
            href="/dashboard"
            className="px-5 py-2.5 rounded-lg border border-[#FEDF89] bg-white text-[#B54708] text-xs font-extrabold uppercase tracking-wider hover:border-[#0B5D3B] transition"
          >
            Back to my workspace
          </Link>
        )}
      />
    )
  } else if (capabilitiesReported(session) && !hasCapability(session, active.capability)) {
    // Same role, narrower mandate: the backend would answer 403
    // PLATFORM_CAPABILITY_REQUIRED, so say so before the request rather than
    // after it — and never imply the panel does not exist.
    body = (
      <StateBlock
        kind="denied"
        title={`${active.label} requires another platform capability`}
        body={`Your PLATFORM_ADMIN role does not include "${CAPABILITY_LABELS[active.capability]}", which is the capability this panel's route declares. `
          + 'The backend enforces the same rule, so this screen would be refused even if it rendered. A platform administrator holding '
          + 'manage_platform_admins can grant the capability from the Administrators panel.'}
        action={(
          <Link
            href="/admin"
            className="px-5 py-2.5 rounded-lg border border-[#FEDF89] bg-white text-[#B54708] text-xs font-extrabold uppercase tracking-wider hover:border-[#0B5D3B] transition"
          >
            Back to Overview
          </Link>
        )}
      />
    )
  } else {
    body = children
  }

  return (
    <div className="min-h-screen bg-[#F5F8FC] text-[#101828] flex flex-col lg:flex-row">
      {/* Administrator rail */}
      <aside className="lg:w-64 lg:flex-shrink-0 lg:h-screen lg:sticky lg:top-0 bg-[#061C14] text-white p-5 flex flex-col gap-4 lg:border-r border-b lg:border-b-0 border-[#0E3627]">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <KulimaLogo variant="sidebar" />
            <div className="min-w-0">
              <div className="text-[11px] font-semibold text-emerald-400 leading-tight">Platform Operations</div>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded bg-[#B54708]/20 border border-[#F79009]/40 text-[9px] font-black uppercase tracking-widest text-[#FCD9A0]">
            Internal
          </span>
        </div>

        <nav className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible lg:gap-0.5">
          {ADMIN_SECTIONS.map(item => {
            const isActive = item.id === section
            const base = `shrink-0 px-3 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
              isActive
                ? 'bg-[#174836] text-white border border-[#1E6047]'
                : 'text-[#C8D8CC] hover:bg-[#0E2E22] hover:text-white'
            }`
            if (capabilitiesReported(session) && !hasCapability(session, item.capability)) {
              // Kept in the list on purpose: an administrator should be able to see
              // that the panel exists and that their role simply does not carry the
              // capability, rather than wonder where a screen went.
              return (
                <span
                  key={item.id}
                  title={`Your PLATFORM_ADMIN role does not include “${CAPABILITY_LABELS[item.capability]}”`}
                  className={`${base} opacity-45 cursor-not-allowed`}
                >
                  {item.label}
                  <span className="ml-1.5 text-[9px] font-black uppercase tracking-widest text-[#FCD9A0]">restricted</span>
                </span>
              )
            }
            return (
              <Link key={item.id} href={item.href} className={base}>
                <span className="lg:hidden">{item.kind} </span>
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="hidden lg:block mt-auto pt-4 border-t border-[#0E3627] text-[10px] text-emerald-300/70 leading-relaxed">
          <div className="font-bold text-emerald-400 uppercase tracking-wider mb-1">Platform administrator</div>
          <p>
            Reads aggregate across every workspace and are recorded as <code className="text-emerald-200">admin.console_viewed</code>.
            Writes exist only on Organizations and Administrators: each one is refused unless your role carries the declared
            capability, cannot delete customer data, and stores its before/after state as its own audit event.
          </p>
          {isBreakGlass(session) ? (
            <p className="mt-2 text-[#FCD9A0]">
              This session came from the break-glass environment list, not the stored role. Every action you take is
              labelled <code className="text-emerald-200">env_allow_list</code> in the audit log.
            </p>
          ) : null}
          <Link href="/dashboard" className="mt-3 inline-block text-emerald-300 hover:text-white font-bold">
            ← Customer workspace
          </Link>
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="bg-white/95 backdrop-blur border-b border-[#DDE6F0] shadow-saas sticky top-0 z-10">
          <div className="px-4 md:px-8 py-3 flex flex-wrap items-center justify-between gap-3 max-w-7xl mx-auto w-full">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <span className="text-[#0B5D3B]">Kulima FLEX</span>
                <span>/</span>
                <span className="text-[#B54708]">Platform Admin</span>
                <span>/</span>
                <span className="text-[#0B5D3B]">{active.kind}</span>
              </div>
              <h1 className="text-base font-extrabold text-[#101828] tracking-tight truncate">{title}</h1>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {toolbar}
              {onReload ? (
                <button
                  type="button"
                  onClick={onReload}
                  disabled={busy}
                  className="px-3 py-1.5 rounded-lg border border-[#DDE6F0] bg-white text-[10px] font-extrabold uppercase tracking-wider text-slate-600 hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition disabled:opacity-50"
                >
                  {busy ? 'Loading…' : 'Refresh'}
                </button>
              ) : null}
            </div>
          </div>
          {description ? (
            <div className="px-4 md:px-8 pb-2 max-w-7xl mx-auto text-xs text-slate-500 leading-relaxed">
              {description}
            </div>
          ) : null}
        </header>

        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-7xl w-full mx-auto flex flex-col gap-5">
          {body}
          {session?.isPlatformAdmin ? (
            <footer className="pt-2 text-[10px] text-slate-400 flex flex-wrap items-center gap-x-4 gap-y-1">
              <span>Administrator: <span className="font-mono font-bold text-slate-500">{session.identity?.verifiedEmail || session.identity?.userId || '—'}</span></span>
              <span>Role: <span className="font-bold text-slate-500">{session.roleLabel || 'Platform Administrator'}</span></span>
              <span>Granted by: <span className="font-bold text-slate-500">{session.grantedBy === 'env_allow_list' ? 'break-glass environment' : 'stored PLATFORM_ADMIN role'}</span></span>
              <span>Matched on: <span className="font-bold text-slate-500">{session.matchedVia || 'session_subject'}</span></span>
              <span>Capabilities: {session.capabilities?.length ?? 0}/{ALL_CAPABILITIES.length}</span>
              <span>Active administrators: {session.adminCount}</span>
              <span>Break-glass identities configured: {session.allowListSize}</span>
              <span>Generated: {session.generatedAt ? new Date(session.generatedAt).toLocaleString('en-GB') : '—'}</span>
            </footer>
          ) : null}
        </main>
      </div>
    </div>
  )
}

export default AdminConsoleShell
