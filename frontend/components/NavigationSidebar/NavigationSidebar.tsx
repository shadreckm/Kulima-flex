'use client'

import React, { useMemo } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import TrustGauge from '../TrustGauge/TrustGauge'
import { usePlatformAdmin } from '../../hooks/usePlatformAdmin'
import type { EntityType } from '../../lib/entity-types'
import { ENTITY_CONFIGS } from '../../lib/entity-types'
import KulimaLogo from '../KulimaLogo/KulimaLogo'

/** Assessment-type labels come from lib/entity-types — one vocabulary everywhere. */
const ENTITY_LABELS = Object.fromEntries(
  ENTITY_CONFIGS.map(c => [c.type, c.label]),
) as Record<EntityType, string>

type SidebarProps = {
  workspace: string
  runId?: string | number | null
  status?: string | null
  startupName?: string | null
  recommendation?: string | null
  trustScore?: number | null
  /** Canonical entity type from the shared Assessment Context. */
  entityType?: EntityType | null
  onCloseMobile?: () => void
}

const PIPELINE_STEPS = [
  { label: 'Dashboard',   href: '/dashboard' },
  { label: 'Assessments', href: '/assessments' },
]

// The assessment hierarchy, in the order the product actually builds it:
// Research → Evidence → Signals → Decision → Reports → Outcomes. (The numbered
// chain itself is drawn in the workspace header, which also shows stage state.)
const PIPELINE_ITEMS = [
  { label: 'Research',  href: '/research' },
  { label: 'Evidence',  href: '/evidence' },
  { label: 'Signals',   href: '/signals' },
  { label: 'Decision',  href: '/decision' },
  { label: 'Reports',   href: '/reports' },
  { label: 'Outcomes',  href: '/outcomes' },
]

// The analyst is an assistant to the pipeline, not the product itself — the
// workspace must read as an assessment workspace, never as a chat application.
const ANALYST_ITEMS = [{ label: 'AI Analyst', href: '/flex' }]

const SECONDARY_ITEMS = [
  { label: 'Feedback',         href: '/feedback' },
  { label: 'Trust & Governance', href: '/trust' },
  { label: 'Settings',         href: '/settings' },
  { label: 'Billing & Plan',   href: '/billing' },
]

// Internal tooling, never shown to a customer. Visibility is decided by the
// backend PLATFORM_ADMIN role check (/api/v1/admin/session), not by an
// organization role — an Org Owner sees nothing here.
const PLATFORM_OPS_ITEM = { label: 'Admin Console', href: '/admin' }

type NavItem = { label: string; href: string; step?: string }

function NavGroup({
  label,
  items,
  pathname,
  onCloseMobile,
}: {
  label: string
  items: NavItem[]
  pathname: string | null
  onCloseMobile?: () => void
}) {
  return (
    <div>
      <div className="text-[10px] font-bold text-emerald-500/60 uppercase tracking-widest px-3 mb-1.5">
        {label}
      </div>
      <div className="flex flex-col gap-0.5">
        {items.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(`${item.href}/`)
          // Assessment-centric navigation — every route reads the shared
          // Assessment Context on arrival; no legacy ?run= URL parameters.
          return (
            <Link
              key={item.label}
              href={item.href}
              onClick={onCloseMobile}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
                active
                  ? 'bg-[#174836] text-white shadow-sm border border-[#1E6047]'
                  : 'text-[#C8D8CC] hover:bg-[#0E2E22] hover:text-white'
              }`}
            >
              {item.step ? (
                <span
                  className={`w-4 shrink-0 text-[9px] font-bold tabular-nums ${
                    active ? 'text-white/70' : 'text-emerald-500/50'
                  }`}
                  aria-hidden="true"
                >
                  {item.step}
                </span>
              ) : null}
              <span>{item.label}</span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

export default function NavigationSidebar({
  workspace,
  runId,
  status,
  startupName,
  recommendation,
  trustScore,
  entityType,
  onCloseMobile,
}: SidebarProps) {
  const pathname = usePathname()
  const { isPlatformAdmin } = usePlatformAdmin()

  const platformOpsItems = useMemo(
    () => (isPlatformAdmin === true ? [PLATFORM_OPS_ITEM] : []),
    [isPlatformAdmin],
  )

  const currentStatus = useMemo(() => status || 'idle', [status])
  const displayStartup = startupName
  const displayRec = recommendation
  const displayTrust = trustScore

  return (
    <aside className="bg-[#061C14] text-white p-5 rounded-[12px] border border-[#0E3627] flex flex-col h-full overflow-y-auto shadow-saas-elevated select-none">
      <div className="flex flex-col gap-0 flex-1 min-h-0">
        {/* Brand Header */}
        <div className="mb-5 pb-4 border-b border-[#0E3627]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <KulimaLogo variant="sidebar" />
              <div className="min-w-0">
                <div className="text-[11px] font-semibold text-emerald-400 leading-tight mt-0.5">Decision Intelligence</div>
              </div>
            </div>
            {onCloseMobile ? (
              <button
                type="button"
                onClick={onCloseMobile}
                className="lg:hidden text-emerald-400 hover:text-white p-1 text-sm font-bold"
                aria-label="Close Sidebar"
              >
                ✕
              </button>
            ) : null}
          </div>
        </div>

        {/* Active Evaluation Capsule */}
        <div className="rounded-[10px] bg-[#0A261C] p-3 mb-5 border border-[#124231]">
          <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
            <span>Active Assessment</span>
            <span className={`w-2 h-2 rounded-full ${currentStatus === 'completed' || currentStatus === 'complete' ? 'bg-[#12B76A]' : 'bg-[#F79009] animate-pulse'}`} />
          </div>
          {runId ? (
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <div className="text-xs font-bold text-white truncate leading-tight">{displayStartup || 'Active Assessment'}</div>
                {entityType ? (
                  <span className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">
                    {ENTITY_LABELS[entityType] || entityType}
                  </span>
                ) : null}
              </div>
              {displayRec ? (
                <div className="text-[11px] text-emerald-200 mt-1">
                  Decision: <span className="font-bold text-white uppercase">{displayRec}</span>
                </div>
              ) : null}
              {displayTrust != null ? (
                <div className="mt-2 pt-2 border-t border-[#124231]">
                  <TrustGauge score={displayTrust} size="sm" showLabel={false} />
                </div>
              ) : null}
              <div className="text-[10px] text-emerald-300/80 mt-1 capitalize">Status: {currentStatus}</div>
            </div>
          ) : (
            <div className="text-[11px] text-emerald-300/60 italic">No active assessment selected.</div>
          )}
        </div>

        {/* Navigation Groups */}
        <nav className="flex flex-col gap-4">
          {/* Your work */}
          <NavGroup
            label="Your Work"
            items={PIPELINE_STEPS}
            pathname={pathname}
            onCloseMobile={onCloseMobile}
          />
          <div className="border-t border-[#0E3627]" />
          {/* The assessment hierarchy */}
          <NavGroup
            label="Assessment Pipeline"
            items={PIPELINE_ITEMS}
            pathname={pathname}
            onCloseMobile={onCloseMobile}
          />
          <div className="border-t border-[#0E3627]" />
          {/* The analyst assistant, downstream of the evidence */}
          <NavGroup
            label="Analyst"
            items={ANALYST_ITEMS}
            pathname={pathname}
            onCloseMobile={onCloseMobile}
          />
          <div className="border-t border-[#0E3627]" />
          {/* Secondary */}
          <NavGroup
            label="Platform"
            items={SECONDARY_ITEMS}
            pathname={pathname}
            onCloseMobile={onCloseMobile}
          />
          {/* Internal — only rendered when the backend confirms this identity is
              a configured platform operator. */}
          {platformOpsItems.length ? (
            <>
              <div className="border-t border-[#F79009]/30" />
              <NavGroup
                label="Platform Ops"
                items={platformOpsItems}
                pathname={pathname}
                onCloseMobile={onCloseMobile}
              />
            </>
          ) : null}
        </nav>
      </div>

      <div className="pt-4 mt-4 border-t border-[#0E3627] text-[10px] text-emerald-400/60 flex items-center justify-between flex-shrink-0">
        <span className="font-semibold">Kulima FLEX</span>
        <span className="font-mono opacity-60">v2.0</span>
      </div>
    </aside>
  )
}
