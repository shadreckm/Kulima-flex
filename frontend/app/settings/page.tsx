'use client'

import React, { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn, signOut } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { listAssessments, type AssessmentWorkspacePayload } from '../../lib/api'
import {
  getOrgContext,
  listOrgMembers,
  addOrgMember,
  setOrgMemberRole,
  removeOrgMember,
  type OrgMemberRecord,
  type OrgOverview,
  type RoleDefinition,
} from '../../lib/enterprise'

export default function SettingsPage() {
  const { status: authStatus, data: session } = useSession()
  const [assessments, setAssessments] = useState<AssessmentWorkspacePayload[]>([])
  const [error, setError] = useState<string | null>(null)
  const [origin, setOrigin] = useState<string>('')
  // ── Team Members (P3) ──────────────────────────────────────────────────
  const [org, setOrg] = useState<OrgOverview | null>(null)
  const [members, setMembers] = useState<OrgMemberRecord[]>([])
  const [roleDefs, setRoleDefs] = useState<RoleDefinition[]>([])
  const [inviteId, setInviteId] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('viewer')
  const [teamMsg, setTeamMsg] = useState<string | null>(null)

  const loadTeam = useCallback(async () => {
    try {
      const ctx = await getOrgContext()
      setOrg(ctx)
      const res = await listOrgMembers()
      setMembers(res.members)
      setRoleDefs(res.roleDefinitions)
    } catch (err) {
      setTeamMsg(err instanceof Error ? err.message : 'Could not load team members.')
    }
  }, [])

  async function handleInvite() {
    if (!inviteId.trim()) {
      setTeamMsg('Enter the user ID or email of the person to invite.')
      return
    }
    setTeamMsg(null)
    try {
      await addOrgMember({
        userId: inviteId.trim(),
        email: inviteEmail.trim() || undefined,
        role: inviteRole,
      })
      setInviteId('')
      setInviteEmail('')
      setInviteRole('viewer')
      await loadTeam()
      setTeamMsg('Member added.')
    } catch (err) {
      setTeamMsg(err instanceof Error ? err.message : 'Could not add member.')
    }
  }

  async function handleRoleChange(userId: string, role: string) {
    setTeamMsg(null)
    try {
      await setOrgMemberRole(userId, role)
      await loadTeam()
      setTeamMsg('Role updated.')
    } catch (err) {
      setTeamMsg(err instanceof Error ? err.message : 'Could not update role.')
    }
  }

  async function handleRemove(userId: string) {
    setTeamMsg(null)
    try {
      await removeOrgMember(userId)
      await loadTeam()
      setTeamMsg('Member removed.')
    } catch (err) {
      setTeamMsg(err instanceof Error ? err.message : 'Could not remove member.')
    }
  }

  useEffect(() => {
    setOrigin(window.location.origin)
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadAssessments() {
      const res = await listAssessments(50)
      if (!cancelled) setAssessments(res.assessments)
    }
    if (authStatus === 'authenticated') {
      loadAssessments().catch(err => setError(String(err)))
      loadTeam()
    }
    return () => { cancelled = true }
  }, [authStatus, loadTeam])

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
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
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
              <span className="text-slate-400">Assessments:</span>
              <span className="font-semibold text-slate-900">{assessments.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Active:</span>
              <span className="font-semibold text-slate-900">{assessments.filter(a => !a.status || a.status !== 'archived').length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Archived:</span>
              <span className="font-semibold text-slate-900">{assessments.filter(a => a.status === 'archived').length}</span>
            </div>
          </div>
          <p className="text-xs text-slate-400 pt-1">Report downloads and feedback use the authenticated proxy route.</p>
        </div>
      </section>

      {/* ── Team Members (P3) ─────────────────────────────────────────────── */}
      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider pb-2.5 border-b border-[#DDE6F0]">
          Team Members{org?.orgName ? ` — ${org.orgName}` : ''}
        </h2>
        <p className="text-xs text-slate-500 mt-2">Roles: Viewer (read-only), Contributor (upload &amp; assess), Reviewer (approve), Admin (manage members).</p>

        {teamMsg ? (
          <div className="mt-3 p-3 bg-[#F5F8FC] border border-[#DDE6F0] rounded-lg text-xs font-semibold text-slate-700 break-all">{teamMsg}</div>
        ) : null}

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-slate-400">
                <th className="pb-2">User</th>
                <th className="pb-2">Role</th>
                <th className="pb-2">Status</th>
                <th className="pb-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map(m => {
                const isSelf = m.userId === org?.userId
                const isOwner = m.role === 'owner'
                return (
                  <tr key={m.userId} className="border-t border-[#EAECF0]">
                    <td className="py-2.5 pr-3">
                      <div className="font-semibold text-slate-900 max-w-[220px] truncate">{m.displayName || m.email || m.userId}</div>
                      {m.email ? <div className="text-[11px] text-slate-400 truncate">{m.email}</div> : null}
                    </td>
                    <td className="py-2.5 pr-3">
                      <select
                        value={m.role}
                        disabled={isOwner || (isSelf && !['owner', 'admin'].includes(String(org?.role || '')))}
                        onChange={e => handleRoleChange(m.userId, e.target.value)}
                        className="rounded-lg border border-[#DDE6F0] bg-white px-2 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-60"
                      >
                        {(roleDefs.length
                          ? roleDefs.map(d => d.role)
                          : ['owner', 'admin', 'reviewer', 'contributor', 'viewer']
                        ).map(r => (
                          <option key={r} value={r} disabled={r === 'owner'}>{r}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${isSelf ? 'bg-[#EAF3FF] text-[#004085]' : 'bg-[#ECFDF3] text-[#027A48]'}`}>
                        {isSelf ? 'You' : 'Active'}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <button
                        type="button"
                        disabled={isOwner || isSelf}
                        onClick={() => handleRemove(m.userId)}
                        className="rounded-lg border border-[#FECDCA] px-2.5 py-1 text-[11px] font-bold text-[#B42318] hover:bg-[#FEF3F2] transition disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                )
              })}
              {members.length === 0 ? (
                <tr><td colSpan={4} className="py-3 text-xs text-slate-400">No members loaded yet.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div className="mt-4 border-t border-[#EAECF0] pt-4">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">Invite a member</div>
          <div className="flex flex-wrap gap-2">
            <input
              value={inviteId}
              onChange={e => setInviteId(e.target.value)}
              placeholder="User ID or email"
              className="min-w-[180px] flex-1 rounded-lg border border-[#DDE6F0] px-3 py-2 text-sm"
            />
            <input
              value={inviteEmail}
              onChange={e => setInviteEmail(e.target.value)}
              placeholder="Email (optional)"
              className="min-w-[160px] flex-1 rounded-lg border border-[#DDE6F0] px-3 py-2 text-sm"
            />
            <select
              value={inviteRole}
              onChange={e => setInviteRole(e.target.value)}
              className="rounded-lg border border-[#DDE6F0] bg-white px-3 py-2 text-sm font-semibold text-slate-700"
            >
              {['viewer', 'contributor', 'reviewer', 'admin'].map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleInvite}
              className="rounded-lg bg-[#0B5D3B] px-4 py-2 text-sm font-bold text-white hover:bg-[#08482E] transition"
            >
              Invite
            </button>
          </div>
        </div>
      </section>

      <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
        <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">Workspace Links</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Assessments', href: '/assessments' },
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
              <div>Kulima FLEX v2.0</div>
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
            Kulima FLEX is a white-label evidence intelligence platform for investment committees, development finance institutions, NGOs, accelerators, and government program evaluators.
          </p>
        </div>
      </section>
    </PilotWorkspaceShell>
  )
}
