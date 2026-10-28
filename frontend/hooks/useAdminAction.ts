'use client'

// One platform mutation at a time, with its answer kept on screen.
//
// The console's writes cross workspaces, so a mutation is never fire-and-forget:
// the operator sees what the backend said, in the backend's own words, and the
// error `code` stays visible when the request was refused. `LAST_ADMIN`,
// `ENTERPRISE_ACTIVATION_REQUIRED` and `FIELD_NOT_PATCHABLE` each mean something
// specific, and a generic failure banner would throw that away.
//
// The action returns a sentence (not the raw payload) so the page decides what a
// success means in the operator's terms — "Enterprise activation approved", not
// `{after: {...}}` dumped into a toast.

import { useCallback, useState } from 'react'
import { AdminRequestError } from '../lib/admin'

export type AdminActionOutcome = {
  ok: boolean
  message: string
  code: string | null
}

export type AdminActionRunner = {
  busy: boolean
  outcome: AdminActionOutcome | null
  /** Runs the action, keeps the result, and returns whether it succeeded. */
  run: (action: () => Promise<string>) => Promise<boolean>
  clear: () => void
}

export function useAdminAction(onSettled?: () => void): AdminActionRunner {
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<AdminActionOutcome | null>(null)

  const run = useCallback(async (action: () => Promise<string>) => {
    setBusy(true)
    setOutcome(null)
    try {
      const message = await action()
      setOutcome({ ok: true, message, code: null })
      // A platform panel is an aggregate; a successful write only means
      // something once the numbers above it have been re-read.
      onSettled?.()
      return true
    } catch (err: unknown) {
      const requestError = err instanceof AdminRequestError ? err : null
      setOutcome({
        ok: false,
        message: requestError
          ? (requestError.detail || requestError.code || `The platform action failed (HTTP ${requestError.status}).`)
          : (err instanceof Error ? err.message : String(err)),
        code: requestError ? (requestError.code || `HTTP_${requestError.status}`) : null,
      })
      // Nothing was recorded as successful, but the panel may have changed
      // underneath us — re-read rather than show a stale view next to an error.
      onSettled?.()
      return false
    } finally {
      setBusy(false)
    }
    // A page passing an inline `reload` gives this callback a new identity on
    // each render, so `run` is rebuilt with it. That is harmless: the busy flag
    // and the outcome live in this hook's state, not in the callback.
  }, [onSettled])  // eslint-disable-line react-hooks/exhaustive-deps

  const clear = useCallback(() => setOutcome(null), [])

  return { busy, outcome, run, clear }
}
