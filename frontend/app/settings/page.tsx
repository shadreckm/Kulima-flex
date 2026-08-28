'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn, signOut } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { listStoredRuns, type StoredRunRecord } from '../../lib/api'

export default function SettingsPage() {
  const { status: authStatus, data: session } = useSession()
  const [runs, setRuns] = useState<StoredRunRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [origin, setOrigin] = useState<string>('')

  useEffect(() => {
    setOrigin(window.location.origin)
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadRuns() {
      const res = await listStoredRuns(20, true)
      if (!cancelled) setRuns(res.runs)
    }
    if (authStatus === 'authenticated') {
      loadRuns().catch(err => setError(String(err)))
    }
    return () => { cancelled = true }
  }, [authStatus])

  if (authStatus === 'loading') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">
        Checking session…
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima OS</div>
        <button
          onClick={() => signIn()}
          className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm"
        >
          Sign in
        </button>
      </div>
    )
  }

  return (
    <PilotWorkspaceShell
      workspace="Settings"
      title="Platform Settings"
      description="Manage your authenticated session and platform configuration."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">
          {error}
        </div>
      ) : null}

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas space-y-3">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider pb-2.5 border-b border-[#DDE6F0]">Session</h2>
          <div className="text-sm text-slate-700">
            <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">User</span>
            <div className="font-semibold text-slate-900 mt-0.5">{session?.user?.name || session?.user?.email || 'Signed-in user'}</div>
          </div>
          <div className="text-sm text-slate-700">
            <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Origin</span>
            <div className="font-semibold text-slate-900 mt-0.5 break-all text-xs">{origin || '—'}</div>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: '/' })}
            className="px-4 py-2 rounded-lg border border-[#DDE6F0] text-sm font-semibold text-slate-700 hover:bg-[#F5F8FC] transition"
          >
            Sign out
          </button>
        </div>

        <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas space-y-3">
          <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider pb-2.5 border-b border-[#DDE6F0]">Platform Summary</h2>
          <div className="space-y-2 text-sm text-slate-700">
            <div className="flex justify-between">
              <span className="text-slate-400">Stored evaluations:</span>
              <span className="font-semibold text-slate-900">{runs.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Active:</span>
              <span className="font-semibold text-slate-900">{runs.filter(run => !run.archivedAt).length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Archived:</span>
              <span className="font-semibold text-slate-900">{runs.filter(run => run.archivedAt).length}</span>
            </div>
          </div>
          <p className="text-xs text-slate-400 pt-1">Report downloads and feedback use the authenticated proxy route.</p>
        </div>
      </section>

      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">Workspace Links</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Runs', href: '/runs' },
            { label: 'AI Analyst Workspace', href: '/flex' },
            { label: 'Signals', href: '/signals' },
            { label: 'Evidence', href: '/evidence' },
            { label: 'Decision', href: '/decision' },
            { label: 'Outcomes', href: '/outcomes' },
            { label: 'Reports', href: '/reports' },
            { label: 'Analytics', href: '/analytics' },
            { label: 'Feedback', href: '/feedback' },
          ].map(({ label, href }) => (
            <Link
              key={label}
              href={href}
              className="p-3 border border-[#DDE6F0] rounded-lg text-xs font-semibold text-slate-700 hover:bg-[#F5F8FC] hover:border-[#0B5D3B] hover:text-[#0B5D3B] transition"
            >
              {label}
            </Link>
          ))}
        </div>
      </section>

      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3 pb-2.5 border-b border-[#DDE6F0]">About Platform</h2>
        <div className="space-y-4">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Decision Intelligence Pipeline</div>
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold">
              {['Information', 'Evidence', 'Trust', 'Signals', 'Decision', 'Outcome', 'Learning'].map((stage, idx, arr) => (
                <React.Fragment key={stage}>
                  <span className="px-2.5 py-1 rounded-md bg-[#F5F8FC] border border-[#DDE6F0] text-slate-700">{stage}</span>
                  {idx < arr.length - 1 && <span className="text-slate-300 font-bold">→</span>}
                </React.Fragment>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs text-slate-600">
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="font-bold text-slate-700 mb-0.5">Platform</div>
              <div>Kulima OS v2.0</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="font-bold text-slate-700 mb-0.5">Engine</div>
              <div>Core Intelligence Engine</div>
            </div>
            <div className="p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
              <div className="font-bold text-slate-700 mb-0.5">Entity Types</div>
              <div>Startup · NGO · Dev. Program · Accelerator · Gov. Program</div>
            </div>
          </div>
          <p className="text-xs text-slate-400">
            Kulima OS is a white-label decision intelligence platform for investment committees, development finance institutions, NGOs, accelerators, and government program evaluators.
          </p>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
