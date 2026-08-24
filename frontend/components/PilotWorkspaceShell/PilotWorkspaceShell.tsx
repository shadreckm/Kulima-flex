'use client'

import React, { useState } from 'react'
import NavigationSidebar from '../NavigationSidebar/NavigationSidebar'

type PilotWorkspaceShellProps = {
  workspace: string
  title: string
  description?: string
  runId?: string | number | null
  status?: string | null
  startupName?: string | null
  recommendation?: string | null
  trustScore?: number | null
  children: React.ReactNode
  rightRail?: React.ReactNode
}

export default function PilotWorkspaceShell({
  workspace,
  title,
  description,
  runId,
  status,
  startupName,
  recommendation,
  trustScore,
  children,
  rightRail,
}: PilotWorkspaceShellProps) {
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)

  return (
    <div className="min-h-screen bg-[#F5F8FC] flex text-[#101828]">
      {/* Desktop Persistent Sidebar (>= 1024px) */}
      <div className="hidden lg:block w-64 flex-shrink-0 p-4 sticky top-0 h-screen overflow-y-auto">
        <NavigationSidebar
          workspace={workspace}
          runId={runId}
          status={status}
          startupName={startupName}
          recommendation={recommendation}
          trustScore={trustScore}
        />
      </div>

      {/* Mobile / Tablet Slide-out Drawer */}
      {mobileDrawerOpen ? (
        <div
          className="fixed inset-0 bg-black/60 z-50 lg:hidden backdrop-blur-sm transition-opacity"
          onClick={() => setMobileDrawerOpen(false)}
        >
          <div
            className="fixed inset-y-0 left-0 w-72 z-50 p-4 bg-[#061C14] shadow-2xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <NavigationSidebar
              workspace={workspace}
              runId={runId}
              status={status}
              startupName={startupName}
              recommendation={recommendation}
              trustScore={trustScore}
              onCloseMobile={() => setMobileDrawerOpen(false)}
            />
          </div>
        </div>
      ) : null}

      {/* Main Content Workspace Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Sticky Executive Top Bar */}
        <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-[#DDE6F0] px-4 md:px-8 py-3.5 shadow-saas">
          <div className="flex items-center justify-between gap-4 max-w-7xl mx-auto">
            <div className="flex items-center gap-3 min-w-0">
              {/* Mobile / Tablet Hamburger Toggle */}
              <button
                type="button"
                onClick={() => setMobileDrawerOpen(true)}
                className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-[#DDE6F0] transition focus:outline-none"
                aria-label="Open Navigation"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>

              <div className="min-w-0">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <span>Kulima OS</span>
                  <span>/</span>
                  <span className="text-[#0B5D3B]">{workspace}</span>
                </div>
                <h1 className="text-base md:text-lg font-extrabold text-[#101828] tracking-tight truncate">
                  {title}
                </h1>
              </div>
            </div>

            {/* Run Context Quick Indicator */}
            {runId ? (
              <div className="hidden sm:flex items-center gap-2 bg-[#EAF3FF] border border-[#D6E8FF] px-3 py-1 rounded-lg text-xs">
                <span className="font-bold text-[#004085]">Run #{String(runId).slice(0, 8)}</span>
                {status ? (
                  <span className="px-1.5 py-0.5 rounded bg-white text-slate-700 text-[10px] font-extrabold uppercase border border-[#D6E8FF]">
                    {status}
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
          {description ? (
            <div className="max-w-7xl mx-auto mt-1 text-xs text-slate-500 truncate">
              {description}
            </div>
          ) : null}
        </header>

        {/* Dynamic Workspace Body */}
        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {rightRail ? (
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 items-start">
              <div className="flex flex-col gap-6 min-w-0">{children}</div>
              <aside className="flex flex-col gap-6">{rightRail}</aside>
            </div>
          ) : (
            <div className="flex flex-col gap-6">{children}</div>
          )}
        </main>
      </div>
    </div>
  )
}
