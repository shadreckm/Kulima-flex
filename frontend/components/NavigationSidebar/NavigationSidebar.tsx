'use client'

import React, { useMemo } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { hrefWithRun, loadCurrentRun } from '../../lib/current-run'
import TrustGauge from '../TrustGauge/TrustGauge'
import type { EntityType } from '../../lib/entity-types'
import KulimaLogo from '../KulimaLogo/KulimaLogo'

const ENTITY_LABELS: Record<EntityType, string> = {
  startup: 'Startup',
  ngo: 'NGO',
  development_program: 'Dev. Program',
  accelerator: 'Accelerator',
  government_program: 'Gov. Program',
}

type SidebarProps = {
  workspace: string
  runId?: string | number | null
  status?: string | null
  startupName?: string | null
  recommendation?: string | null
  trustScore?: number | null
  onCloseMobile?: () => void
}

const PIPELINE_ITEMS = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Runs', href: '/runs' },
  { label: 'AI Analyst Workspace', href: '/flex' },
  { label: 'Signals', href: '/signals' },
  { label: 'Evidence', href: '/evidence' },
  { label: 'Decision', href: '/decision' },
  { label: 'Outcomes', href: '/outcomes' },
]

const INSIGHTS_ITEMS = [
  { label: 'Reports', href: '/reports' },
  { label: 'Analytics', href: '/analytics' },
]

const SYSTEM_ITEMS = [
  { label: 'Feedback', href: '/feedback' },
  { label: 'Settings', href: '/settings' },
]

function NavGroup({
  label,
  items,
  pathname,
  currentRun,
  onCloseMobile,
}: {
  label: string
  items: { label: string; href: string }[]
  pathname: string | null
  currentRun: ReturnType<typeof loadCurrentRun>
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
          const href = hrefWithRun(item.href, currentRun)
          return (
            <Link
              key={item.label}
              href={href}
              onClick={onCloseMobile}
              className={`px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
                active
                  ? 'bg-[#174836] text-white shadow-sm border border-[#1E6047]'
                  : 'text-[#C8D8CC] hover:bg-[#0E2E22] hover:text-white'
              }`}
            >
              {item.label}
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
  onCloseMobile,
}: SidebarProps) {
  const pathname = usePathname()
  const currentRun = useMemo(() => loadCurrentRun(), [runId, startupName])

  const currentStatus = useMemo(() => status || currentRun?.status || 'idle', [status, currentRun?.status])
  const displayStartup = startupName || currentRun?.startupName
  const displayRec = recommendation || currentRun?.recommendation
  const displayTrust = trustScore ?? currentRun?.trustScore

  return (
    <aside className="bg-[#061C14] text-white p-5 rounded-[12px] border border-[#0E3627] flex flex-col h-full overflow-y-auto shadow-saas-elevated select-none">
      <div className="flex flex-col gap-0 flex-1 min-h-0">
        {/* Brand Header */}
        <div className="mb-5 pb-4 border-b border-[#0E3627]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              {/* Logo — white pill container preserves cream bg on dark sidebar */}
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

        {/* Current Active Run Capsule */}
        <div className="rounded-[10px] bg-[#0A261C] p-3 mb-5 border border-[#124231]">
          <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
            <span>Active Evaluation</span>
            <span className={`w-2 h-2 rounded-full ${currentStatus === 'completed' ? 'bg-[#12B76A]' : 'bg-[#F79009] animate-pulse'}`} />
          </div>

          {runId || currentRun?.runId ? (
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <div className="text-xs font-bold text-white truncate leading-tight">{displayStartup || 'Active Venture'}</div>
                {currentRun?.entityType && currentRun.entityType !== 'startup' ? (
                  <span className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">
                    {ENTITY_LABELS[currentRun.entityType] || currentRun.entityType}
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
            <div className="text-[11px] text-emerald-300/60 italic">No active evaluation selected.</div>
          )}
        </div>

        {/* Navigation Groups */}
        <nav className="flex flex-col gap-4">
          <NavGroup
            label="Decision Pipeline"
            items={PIPELINE_ITEMS}
            pathname={pathname}
            currentRun={currentRun}
            onCloseMobile={onCloseMobile}
          />
          <div className="border-t border-[#0E3627]" />
          <NavGroup
            label="Insights & Exports"
            items={INSIGHTS_ITEMS}
            pathname={pathname}
            currentRun={currentRun}
            onCloseMobile={onCloseMobile}
          />
          <div className="border-t border-[#0E3627]" />
          <NavGroup
            label="System"
            items={SYSTEM_ITEMS}
            pathname={pathname}
            currentRun={currentRun}
            onCloseMobile={onCloseMobile}
          />
        </nav>
      </div>

      <div className="pt-4 mt-4 border-t border-[#0E3627] text-[10px] text-emerald-400/60 flex items-center justify-between flex-shrink-0">
        <span className="font-semibold">Kulima OS</span>
        <span className="font-mono opacity-60">v2.0</span>
      </div>
    </aside>
  )
}
