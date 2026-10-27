'use client'

// Admin Console chrome — the gate and the frame every operations screen shares.
//
// Deliberately NOT PilotWorkspaceShell: that shell is the customer workspace
// (active assessment capsule, pipeline tracker, org-scoped navigation). This
// console is internal tooling that reads across every workspace, so it gets its
// own frame and its own access check.
//
// The check is a real one, not decorative: the page renders data only after
// /api/v1/admin/session says this identity is a configured platform operator.
// The backend enforces the same rule on every section endpoint, so a bypassed
// UI would still get 403s.

import React, { useEffect } from 'react'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import KulimaLogo from '../KulimaLogo/KulimaLogo'
import { StateBlock } from './adminUi'
import { usePlatformAdmin, primePlatformAdminCache } from '../../hooks/usePlatformAdmin'

export type AdminSectionId = 'overview' | 'users' | 'billing' | 'ai-health' | 'outcomes' | 'audit'

export const ADMIN_SECTIONS: { id: AdminSectionId; label: string; href: string; phase: string }[] = [
  { id: 'overview', label: 'Overview', href: '/admin', phase: 'Phase 1' },
  { id: 'users', label: 'User Management', href: '/admin/users', phase: 'Phase 2' },
  { id: 'billing', label: 'Billing', href: '/admin/billing', phase: 'Phase 3' },
  { id: 'ai-health', label: 'AI Health', href: '/admin/ai-health', phase: 'Phase 4' },
  { id: 'outcomes', label: 'Outcome Intelligence', href: '/admin/outcomes', phase: 'Phase 5' },
  { id: 'audit', label: 'Audit Logs', href: '/admin/audit', phase: 'Phase 6' },
]

// The two reasons the backend says "no", mirrored from
// backend/app/core/admin_access.py (REASON_NOT_CONFIGURED / REASON_NOT_ALLOWLISTED).
const REASON_NOT_CONFIGURED = 'not_configured'
const REASON_NOT_ALLOWLISTED = 'not_allowlisted'

function denialCopy(reason: string, role: string): { title: string; body: string } {
  if (reason === REASON_NOT_CONFIGURED) {
    return {
      title: 'Console disabled in this environment',
      body: 'No platform operators are configured, so access is denied to everyone — including you. '
        + 'Set KULIMA_PLATFORM_ADMIN_USER_IDS or KULIMA_ADMIN_EMAILS on the backend to enable the console. '
        + 'The console is fail-closed on purpose: an unconfigured environment must never default to "everyone is an operator".',
    }
  }
  if (reason === REASON_NOT_ALLOWLISTED) {
    return {
      title: 'Platform operator access required',
      body: `Your account is not on the platform-operator allow-list, and your organization role ("${role || 'unknown'}") `
        + 'does not grant it. That is intentional: this console aggregates every customer workspace, so an Org Owner, '
        + 'Admin or Reviewer cannot read other organizations\' data. Ask a configured operator to add your user id to '
        + 'KULIMA_PLATFORM_ADMIN_USER_IDS if you need this access.',
    }
  }
  // An unrecognized reason is never treated as a grant.
  return {
    title: 'Platform operator access required',
    body: 'The backend refused operator access for a reason this screen does not recognise '
        + `("${reason || 'none reported'}"), so nothing was loaded. Access is denied by default — check the `
        + 'operator allow-list configuration on the backend.',
  }
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
        body="The operations console sits behind the same authentication as the customer product, then adds a platform-operator check on top. You return here after signing in."
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
    body = <StateBlock kind="loading" title="Verifying operator access…" body="Asking the backend whether this identity is a configured platform operator." />
  } else if (!session) {
    body = (
      <StateBlock
        kind="error"
        title="Could not verify operator access"
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
  } else {
    body = children
  }

  return (
    <div className="min-h-screen bg-[#F5F8FC] text-[#101828] flex flex-col lg:flex-row">
      {/* Operator rail */}
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
            return (
              <Link
                key={item.id}
                href={item.href}
                className={`shrink-0 px-3 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-[#174836] text-white border border-[#1E6047]'
                    : 'text-[#C8D8CC] hover:bg-[#0E2E22] hover:text-white'
                }`}
              >
                <span className="lg:hidden">{item.phase.replace('Phase ', 'P')} </span>
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="hidden lg:block mt-auto pt-4 border-t border-[#0E3627] text-[10px] text-emerald-300/70 leading-relaxed">
          <div className="font-bold text-emerald-400 uppercase tracking-wider mb-1">Read-only console</div>
          <p>No endpoint here creates, changes or deletes platform data. Every section you open is written to the audit log as <code className="text-emerald-200">admin.console_viewed</code>.</p>
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
                <span className="text-[#B54708]">Platform Ops</span>
                <span>/</span>
                <span className="text-[#0B5D3B]">{active.phase}</span>
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
              <span>Operator: <span className="font-mono font-bold text-slate-500">{session.identity?.userId || '—'}</span></span>
              <span>Granted via: <span className="font-bold text-slate-500">{session.matchedVia || 'session_subject'}</span></span>
              <span>Allow-list entries configured: {session.allowListSize}</span>
              <span>Generated: {session.generatedAt ? new Date(session.generatedAt).toLocaleString('en-GB') : '—'}</span>
            </footer>
          ) : null}
        </main>
      </div>
    </div>
  )
}

export default AdminConsoleShell
