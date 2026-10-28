'use client'

// PLATFORM_ADMIN probe for the internal Admin Console.
//
// `/api/v1/admin/session` answers a single question — does *this* signed-in
// identity hold the stored PLATFORM_ADMIN role? — and is the only admin endpoint
// any authenticated user may call. Everything else on the console is
// cross-workspace and returns 403 for ordinary users, so the navigation affordance
// has to be driven by this probe rather than by an organization role.
//
// Results are cached briefly in module scope: the sidebar re-renders on every
// client navigation, and one round trip per minute is enough to keep the
// affordance honest without hammering the backend.

import { useEffect, useState } from 'react'
import { getAdminSession, type AdminSession } from '../lib/admin'

const TTL_MS = 60_000

let cached: { at: number; session: AdminSession } | null = null
let inflight: Promise<AdminSession | null> | null = null

async function probe(): Promise<AdminSession | null> {
  if (cached && Date.now() - cached.at < TTL_MS) return cached.session
  if (inflight) return inflight
  inflight = getAdminSession()
    .then(session => {
      cached = { at: Date.now(), session }
      return session
    })
    .catch(() => {
      // 401 (no session) and 403 (no PLATFORM_ADMIN role) both mean "no console link".
      cached = null
      return null
    })
    .finally(() => { inflight = null })
  return inflight
}

/** Feed the shared cache from a page that already holds the full session. */
export function primePlatformAdminCache(session: AdminSession): void {
  cached = { at: Date.now(), session }
}

export function clearPlatformAdminCache(): void {
  cached = null
}

export type PlatformAdminState = {
  /** undefined while the first probe is in flight — callers must not treat it as false */
  isPlatformAdmin: boolean | undefined
  session: AdminSession | null
  loading: boolean
  refresh: () => Promise<void>
}

export function usePlatformAdmin(enabled = true): PlatformAdminState {
  const [session, setSession] = useState<AdminSession | null>(cached?.session ?? null)
  const [loading, setLoading] = useState(enabled && !cached)

  const run = async () => {
    if (!enabled) return
    setLoading(true)
    cached = null  // a refresh must re-read the gate, never serve the TTL cache
    const result = await probe()
    setSession(result)
    setLoading(false)
  }

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    if (cached && Date.now() - cached.at < TTL_MS) {
      setSession(cached.session)
      setLoading(false)
      return
    }
    let active = true
    setLoading(true)
    probe().then(result => {
      if (!active) return
      setSession(result)
      setLoading(false)
    })
    return () => { active = false }
  }, [enabled])

  return {
    isPlatformAdmin: loading && session === null ? undefined : Boolean(session?.isPlatformAdmin),
    session,
    loading,
    refresh: run,
  }
}
