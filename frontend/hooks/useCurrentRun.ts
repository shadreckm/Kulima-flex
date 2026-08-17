'use client'

import { useCallback, useEffect, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import {
  clearCurrentRun,
  hrefWithRun,
  loadCurrentRun,
  saveCurrentRun,
  type CurrentRunState,
} from '../lib/current-run'

export function useCurrentRun() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [currentRun, setCurrentRunState] = useState<CurrentRunState | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const fromUrl = searchParams.get('run')
    const stored = loadCurrentRun()
    if (fromUrl) {
      const merged: CurrentRunState = {
        ...(stored || {}),
        runId: fromUrl,
        storedRunId: stored?.storedRunId || (/^\d+$/.test(fromUrl) ? fromUrl : stored?.storedRunId),
        status: stored?.status || 'completed',
      }
      setCurrentRunState(merged)
      saveCurrentRun(merged)
    } else if (stored) {
      setCurrentRunState(stored)
      // Sync URL with stored run if URL currently lacks run parameter
      const nextUrl = hrefWithRun(pathname || '/', stored)
      if (nextUrl !== pathname && typeof window !== 'undefined') {
        window.history.replaceState(null, '', nextUrl)
      }
    }
    setReady(true)
  }, [searchParams, pathname])

  useEffect(() => {
    function onChange(ev: Event) {
      const detail = (ev as CustomEvent<CurrentRunState | null>).detail
      setCurrentRunState(detail)
    }
    window.addEventListener('kulima-current-run-changed', onChange)
    return () => window.removeEventListener('kulima-current-run-changed', onChange)
  }, [])

  const setCurrentRun = useCallback(
    (run: CurrentRunState, options?: { syncUrl?: boolean }) => {
      saveCurrentRun(run)
      setCurrentRunState(run)
      if (options?.syncUrl !== false) {
        const next = hrefWithRun(pathname || '/', run)
        router.replace(next)
      }
    },
    [pathname, router],
  )

  const clearRun = useCallback(() => {
    clearCurrentRun()
    setCurrentRunState(null)
    router.replace(pathname || '/')
  }, [pathname, router])

  const linkWithRun = useCallback((path: string) => hrefWithRun(path, currentRun), [currentRun])

  return {
    currentRun,
    ready,
    setCurrentRun,
    clearRun,
    linkWithRun,
    hasCurrentRun: Boolean(currentRun?.runId),
  }
}
