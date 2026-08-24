'use client'

import React, { useMemo } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { hrefWithRun, loadCurrentRun } from '../../lib/current-run'
import TrustGauge from '../TrustGauge/TrustGauge'

type SidebarProps = {
  workspace: string
  runId?: string | number | null
  status?: string | null
  startupName?: string | null
  recommendation?: string | null
  trustScore?: number | null
  onCloseMobile?: () => void
}

const NAV_ITEMS = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Runs', href: '/runs' },
  { label: 'Flex', href: '/flex' },
  { label: 'Signals', href: '/signals' },
  { label: 'Evidence', href: '/evidence' },
  { label: 'Reports', href: '/reports' },
  { label: 'Analytics', href: '/analytics' },
  { label: 'Feedback', href: '/feedback' },
  { label: 'Settings', href: '/settings' },
]

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
    <aside className="bg-[#061C14] text-white p-5 rounded-[12px] border border-[#0E3627] flex flex-col justify-between h-full min-h-[calc(100vh-3rem)] shadow-saas-elevated select-none">
      <div>
        {/* Brand Header */}
        <div className="mb-5 pb-4 border-b border-[#0E3627]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#0B5D3B] border border-[#17855A] flex items-center justify-center font-black text-white text-base shadow-sm">
                K
              </div>
              <div>
                <div className="text-base font-extrabold text-white tracking-tight leading-none">Kulima OS</div>
                <div className="text-[11px] font-semibold text-emerald-400 mt-0.5">Decision Intelligence</div>
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
          <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-400/80 mt-3 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>Workspace: {workspace}</span>
          </div>
        </div>

        {/* Current Active Run Capsule */}
        <div className="rounded-[10px] bg-[#0A261C] p-3 mb-5 border border-[#124231]">
          <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
            <span>Current Run Context</span>
            <span className={`w-2 h-2 rounded-full ${currentStatus === 'completed' ? 'bg-[#12B76A]' : 'bg-[#F79009] animate-pulse'}`} />
          </div>

          {runId || currentRun?.runId ? (
            <div>
              <div className="text-xs font-bold text-white truncate">{displayStartup || 'Active Venture'}</div>
              {displayRec ? (
                <div className="text-[11px] text-emerald-200 mt-1">
                  Rec: <span className="font-bold text-white uppercase">{displayRec}</span>
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
            <div className="text-[11px] text-emerald-300/60 italic">No active run selected.</div>
          )}
        </div>

        {/* Navigation Item Tree */}
        <div className="space-y-1">
          <div className="text-[10px] font-bold text-emerald-500/80 uppercase tracking-wider px-3 mb-1.5">
            Navigation
          </div>
          <div className="flex flex-col gap-1 text-xs">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href || pathname?.startsWith(`${item.href}/`)
              const href = hrefWithRun(item.href, currentRun)
              return (
                <Link
                  key={item.label}
                  href={href}
                  onClick={onCloseMobile}
                  className={`px-3 py-2 rounded-lg font-medium transition-colors ${
                    active
                      ? 'bg-[#174836] text-white font-bold shadow-sm border border-[#1E6047]'
                      : 'text-emerald-100/70 hover:bg-[#0E2E22] hover:text-white'
                  }`}
                >
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-[#0E3627] text-[10px] text-emerald-400/60 flex items-center justify-between">
        <span>Kulima Africa VC Brain</span>
        <span className="font-mono">v2.0</span>
      </div>
    </aside>
  )
}
