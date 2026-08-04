'use client'

import React, { useMemo } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

type SidebarProps = {
  workspace: string
  runId?: string | number | null
  status?: string | null
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

export default function NavigationSidebar({ workspace, runId, status }: SidebarProps) {
  const pathname = usePathname()

  const currentStatus = useMemo(() => status || 'idle', [status])

  return (
    <aside className="bg-white p-4 rounded shadow border border-gray-100 h-fit sticky top-6">
      <div className="mb-4">
        <div className="text-xs uppercase tracking-wide text-gray-500">Kulima OS</div>
        <div className="text-lg font-semibold text-gray-900">{workspace}</div>
        <div className="text-xs text-gray-500 mt-1">Pilot workspace navigation</div>
      </div>

      <div className="rounded-lg bg-gray-50 p-3 mb-4 border border-gray-100">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Current Run</div>
        {runId ? (
          <>
            <div className="text-sm font-medium text-gray-900 break-all">{String(runId)}</div>
            <div className="text-xs text-gray-600 mt-1">{currentStatus}</div>
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
            return (
              <Link
                key={item.label}
                href={item.href}
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
