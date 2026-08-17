'use client'

import React, { useMemo } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { hrefWithRun, loadCurrentRun } from '../../lib/current-run'

type SidebarProps = {
  workspace: string
  runId?: string | number | null
  status?: string | null
  startupName?: string | null
  recommendation?: string | null
  trustScore?: number | null
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
}: SidebarProps) {
  const pathname = usePathname()
  const currentRun = useMemo(() => loadCurrentRun(), [runId, startupName])

  const currentStatus = useMemo(() => status || currentRun?.status || 'idle', [status, currentRun?.status])
  const displayStartup = startupName || currentRun?.startupName
  const displayRec = recommendation || currentRun?.recommendation
  const displayTrust = trustScore ?? currentRun?.trustScore

  return (
    <aside className="bg-white p-4 rounded shadow border border-gray-100 h-fit sticky top-6">
      <div className="mb-4 border-b border-gray-100 pb-4">
        <Image
          src="/kulima-logo.png"
          alt="Kulima Africa Logo"
          width={200}
          height={60}
          className="h-12 w-auto object-contain mb-2"
          priority
        />
        <div className="text-base font-bold text-gray-900 tracking-tight">Kulima OS</div>
        <div className="text-xs font-medium text-emerald-700">Powered by Kulima Africa</div>
        <div className="text-xs text-gray-600 mt-2 leading-snug italic">
          Mission: Food Everywhere, For Everyone, At All Times.
        </div>
        <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mt-3">{workspace}</div>
      </div>

      <div className="rounded-lg bg-gray-50 p-3 mb-4 border border-gray-100">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Current Run</div>
        {runId || currentRun?.runId ? (
          <>
            <div className="text-sm font-medium text-gray-900">{displayStartup || 'Selected run'}</div>
            {displayRec ? (
              <div className="text-xs text-gray-600 mt-1">Recommendation: <span className="font-semibold">{displayRec}</span></div>
            ) : null}
            {displayTrust != null ? (
              <div className="text-xs text-gray-600">Trust Score: <span className="font-semibold">{displayTrust}</span></div>
            ) : null}
            <div className="text-xs text-gray-600 mt-1 capitalize">Status: {currentStatus}</div>
          </>
        ) : (
          <div className="text-xs text-gray-600">No active run selected.</div>
        )}
      </div>

      <div className="mb-4">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Navigation</div>
        <div className="flex flex-col gap-2 text-sm">
          {NAV_ITEMS.map(item => {
            const active = pathname === item.href || pathname?.startsWith(`${item.href}/`)
            const href = hrefWithRun(item.href, currentRun)
            return (
              <Link
                key={item.label}
                href={href}
                className={active ? 'font-semibold text-gray-900' : 'text-blue-700 hover:text-blue-900 hover:underline'}
              >
                {item.label}
              </Link>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
