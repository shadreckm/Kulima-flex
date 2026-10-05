'use client'

import React, { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useSession, signOut } from 'next-auth/react'
import { getOrgContext, type OrgOverview } from '../../lib/enterprise'

/**
 * Authenticated user header (P4).
 *
 * Replaces the plain "Login" link once a session exists. Shows the user's
 * name, workspace role and workspace name with a dropdown offering Settings
 * and Sign Out. Renders nothing while the session is unresolved and a Login
 * link when unauthenticated.
 */
export default function UserMenu() {
  const { status, data: session } = useSession()
  const [open, setOpen] = useState(false)
  const [org, setOrg] = useState<OrgOverview | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (status !== 'authenticated') return
    getOrgContext().then(setOrg).catch(() => setOrg(null))
  }, [status])

  useEffect(() => {
    if (!open) return
    function onDocClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    function onEsc(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  if (status === 'loading') return null

  if (status !== 'authenticated') {
    return (
      <Link
        href="/api/auth/signin"
        className="px-3 py-2 text-sm font-semibold text-[#344054] hover:text-[#0B5D3B] transition"
      >
        Login
      </Link>
    )
  }

  const name = session?.user?.name || session?.user?.email || 'Signed-in user'
  const roleLabel = org?.roleLabel || org?.role || ''
  const workspace = org?.orgName || ''

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-lg border border-[#DDE6F0] bg-white px-2.5 py-1.5 text-left transition hover:bg-[#F5F8FC]"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0B5D3B] text-[11px] font-extrabold text-white">
          {name.slice(0, 2).toUpperCase()}
        </span>
        <span className="hidden md:flex flex-col leading-tight">
          <span className="text-xs font-bold text-[#101828] max-w-[160px] truncate">{name}</span>
          <span className="text-[10px] font-semibold text-[#667085] max-w-[160px] truncate">
            {roleLabel ? `${roleLabel}${workspace ? ' · ' + workspace : ''}` : workspace || 'Workspace'}
          </span>
        </span>
        <span aria-hidden="true" className="text-[#667085] text-[10px]">▾</span>
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-56 rounded-xl border border-[#DDE6F0] bg-white py-2 shadow-lg"
        >
          <div className="px-4 pb-2 pt-1 border-b border-[#EAECF0]">
            <div className="text-xs font-bold text-[#101828] truncate">{name}</div>
            <div className="mt-0.5 text-[11px] font-semibold text-[#0B5D3B]">{roleLabel || 'Member'}</div>
            <div className="text-[11px] text-[#667085] truncate">{workspace || 'Personal workspace'}</div>
          </div>
          <Link
            href="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="block px-4 py-2 text-sm font-semibold text-[#344054] hover:bg-[#F5F8FC] transition"
          >
            Settings
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={() => signOut({ callbackUrl: '/' })}
            className="block w-full px-4 py-2 text-left text-sm font-semibold text-[#B42318] hover:bg-[#FEF3F2] transition"
          >
            Sign Out
          </button>
        </div>
      ) : null}
    </div>
  )
}
