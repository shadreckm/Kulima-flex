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
    return <div className="min-h-screen flex items-center justify-center text-sm text-gray-600">Checking session…</div>
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-semibold">Sign in to use Kulima OS</div>
        <button onClick={() => signIn()} className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">
          Sign in
        </button>
      </div>
    )
  }

  return (
    <PilotWorkspaceShell
      workspace="Settings"
      title="Pilot Settings"
      description="View the current authenticated session, workspace origin, and pilot configuration references."
    >
      {error ? <div className="p-4 bg-red-50 text-red-700 rounded border border-red-200">{error}</div> : null}

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="p-4 bg-white rounded shadow border border-gray-100 space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Session</h2>
          <div className="text-sm text-gray-700">User: <span className="font-semibold">{session?.user?.name || session?.user?.email || 'Signed-in user'}</span></div>
          <div className="text-sm text-gray-700">Origin: <span className="font-semibold break-all">{origin || '—'}</span></div>
          <button onClick={() => signOut({ callbackUrl: '/' })} className="px-4 py-2 rounded border text-sm hover:bg-gray-50">
            Sign out
          </button>
        </div>

        <div className="p-4 bg-white rounded shadow border border-gray-100 space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Pilot Summary</h2>
          <div className="text-sm text-gray-700">Stored runs available: <span className="font-semibold">{runs.length}</span></div>
          <div className="text-sm text-gray-700">Active stored runs: <span className="font-semibold">{runs.filter(run => !run.archivedAt).length}</span></div>
          <div className="text-sm text-gray-700">Archived stored runs: <span className="font-semibold">{runs.filter(run => run.archivedAt).length}</span></div>
          <div className="text-sm text-gray-700">Report downloads and feedback use the authenticated proxy route.</div>
        </div>
      </section>

      <section className="p-4 bg-white rounded shadow border border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900">Workspace Links</h2>
        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <Link href="/dashboard" className="p-3 border rounded hover:bg-gray-50">Dashboard</Link>
          <Link href="/runs" className="p-3 border rounded hover:bg-gray-50">Runs</Link>
          <Link href="/reports" className="p-3 border rounded hover:bg-gray-50">Reports</Link>
          <Link href="/analytics" className="p-3 border rounded hover:bg-gray-50">Analytics</Link>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
