'use client'

import React from 'react'
import NavigationSidebar from '../NavigationSidebar/NavigationSidebar'

type PilotWorkspaceShellProps = {
  workspace: string
  title: string
  description?: string
  runId?: string | number | null
  status?: string | null
  children: React.ReactNode
  rightRail?: React.ReactNode
}

export default function PilotWorkspaceShell({
  workspace,
  title,
  description,
  runId,
  status,
  children,
  rightRail,
}: PilotWorkspaceShellProps) {
  return (
    <div className={rightRail ? 'min-h-screen p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] xl:grid-cols-[240px_1fr_360px] gap-6' : 'min-h-screen p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6'}>
      <NavigationSidebar workspace={workspace} runId={runId} status={status} />
      <main className="flex flex-col gap-4 min-w-0">
        <header className="p-4 bg-white rounded shadow border border-gray-100">
          <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
          {description ? <p className="text-sm text-gray-600 mt-1">{description}</p> : null}
        </header>
        {children}
      </main>
      {rightRail ? <aside className="flex flex-col gap-4">{rightRail}</aside> : null}
    </div>
  )
}
