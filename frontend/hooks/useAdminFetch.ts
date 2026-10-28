'use client'

// Shared loader for Admin Console screens.
//
// Keeps three things honest: the console shows its own loading/error state
// rather than a silently empty dashboard, a 403 is surfaced as "access denied"
// instead of a data bug, and a reload genuinely re-queries (these are live
// platform aggregates, never cached reads).

import { useCallback, useEffect, useState } from 'react'
import { AdminRequestError } from '../lib/admin'

export type AdminFetchState<T> = {
  data: T | null
  busy: boolean
  error: string | null
  /** True when the backend refused the platform gate (403), not a data failure. */
  denied: boolean
  reload: () => void
}

export function useAdminFetch<T>(load: () => Promise<T>, deps: unknown[] = []): AdminFetchState<T> {
  const [data, setData] = useState<T | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [denied, setDenied] = useState(false)
  const [nonce, setNonce] = useState(0)

  const reload = useCallback(() => setNonce(n => n + 1), [])

  useEffect(() => {
    let cancelled = false
    setBusy(true)
    setError(null)
    setDenied(false)
    load()
      .then(payload => {
        if (cancelled) return
        setData(payload)
        setBusy(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        // Keep the previous payload out of view: stale platform numbers read as
        // current ones are worse than no numbers.
        setData(null)
        setDenied(err instanceof AdminRequestError && err.status === 403)
        setError(err instanceof Error ? err.message : String(err))
        setBusy(false)
      })
    return () => { cancelled = true }
    // `load` closes over the values in `deps`; re-running on those is the point.
  }, [...deps, nonce])  // eslint-disable-line react-hooks/exhaustive-deps

  return { data, busy, error, denied, reload }
}
