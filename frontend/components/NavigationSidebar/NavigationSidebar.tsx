'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { loadRecentRuns, type RecentRun } from '../../lib/run-history'

type SidebarProps = {
  type: 'flex' | 'signals'
  runId?: string | null
  status?: string | null
}

function getNavItems(type: 'flex' | 'signals') {
  return [
    { label: 'Run Status', href: '#run-status' },
    { label: 'Documents', href: '#documents' },
    { label: 'Signals', href: type === 'signals' ? '#signals' : '/signals#signals' },
    { label: 'Decision Snapshot', href: '#decision-snapshot' },
  ]
}

export default function NavigationSidebar({ type, runId, status }: SidebarProps) {
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([])

  useEffect(() => {
    setRecentRuns(loadRecentRuns())
  }, [runId, status])

  const pageLabel = useMemo(() => {
    return type === 'flex' ? 'Kulima FLEX' : 'Kulima SIGNALS'
  }, [type])

  return (
    <aside className="bg-white p-4 rounded shadow border border-gray-100 h-fit sticky top-6">
      <div className="mb-4">
        <div className="text-xs uppercase tracking-wide text-gray-500">Kulima OS</div>
        <div className="text-lg font-semibold text-gray-900">{pageLabel}</div>
        <div className="text-xs text-gray-500 mt-1">Pilot workspace navigation</div>
      </div>

      <div className="rounded-lg bg-gray-50 p-3 mb-4 border border-gray-100">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Run Status</div>
        {runId ? (
          <>
            <div className="text-sm font-medium text-gray-900 break-all">{runId}</div>
            <div className="text-xs text-gray-600 mt-1">{status ?? 'running'}</div>
          </>
        ) : (
          <div className="text-xs text-gray-600">No active run yet.</div>
        )}
      </div>

      <div className="mb-4">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Navigation</div>
        <div className="flex flex-col gap-2 text-sm">
          {getNavItems(type).map(item => (
            <a key={item.label} href={item.href} className="text-blue-700 hover:text-blue-900 hover:underline">
              {item.label}
            </a>
          ))}
        </div>
      </div>

      <div className="mb-4">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Workspace</div>
        <div className="flex flex-col gap-2 text-sm">
          <Link href="/flex" className={type === 'flex' ? 'font-semibold text-gray-900' : 'text-gray-700 hover:text-gray-900'}>
            Flex
          </Link>
          <Link href="/signals" className={type === 'signals' ? 'font-semibold text-gray-900' : 'text-gray-700 hover:text-gray-900'}>
            Signals
          </Link>
        </div>
      </div>

      <div>
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Recent Runs</div>
        <div className="space-y-2">
          {recentRuns.length === 0 ? (
            <div className="text-xs text-gray-500">Run an analysis to populate recent runs.</div>
          ) : (
            recentRuns.map(item => (
              <div key={item.runId} className="rounded-md border border-gray-100 bg-gray-50 p-2">
                <div className="text-xs font-medium text-gray-900 break-all">{item.startup}</div>
                <div className="text-[11px] text-gray-600">{item.founder}</div>
                <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-gray-500">
                  <span>{item.status}</span>
                  <span>{new Date(item.createdAt).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  )
}
