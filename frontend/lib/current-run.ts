import type { EntityType } from './entity-types'

export type CurrentRunState = {
  runId: string
  storedRunId?: string
  /** Entity display name (startup name, NGO name, agency, etc.) */
  startupName?: string
  /** Founder name, program lead, or primary contact */
  founderName?: string
  recommendation?: string
  trustScore?: number | null
  status?: string
  /** Entity type — defaults to 'startup' for backward compat */
  entityType?: EntityType
  /** Secondary label: program name, cohort, etc. (non-startup entities) */
  programName?: string
}

const STORAGE_KEY = 'kulima_current_run'

export function findOstxCase(runId: string) {
  return null
}

export function isDemoRunRecord(run: { runId: number | string; startupName?: string; userId?: string | null }): boolean {
  if (run.userId === null || run.userId === undefined) return true
  return false
}

export function loadCurrentRun(): CurrentRunState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY) || window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.runId) return null
    return parsed as CurrentRunState
  } catch {
    return null
  }
}

export function saveCurrentRun(run: CurrentRunState) {
  if (typeof window === 'undefined') return
  const jsonStr = JSON.stringify(run)
  try { window.localStorage.setItem(STORAGE_KEY, jsonStr) } catch {}
  try { window.sessionStorage.setItem(STORAGE_KEY, jsonStr) } catch {}
  window.dispatchEvent(new CustomEvent('kulima-current-run-changed', { detail: run }))
}

export function clearCurrentRun() {
  if (typeof window === 'undefined') return
  try { window.localStorage.removeItem(STORAGE_KEY) } catch {}
  try { window.sessionStorage.removeItem(STORAGE_KEY) } catch {}
  window.dispatchEvent(new CustomEvent('kulima-current-run-changed', { detail: null }))
}

export function effectiveStoredRunId(run: CurrentRunState | null | undefined): string {
  if (!run) return ''
  return String(run.storedRunId || run.runId || '')
}

export function hrefWithRun(path: string, run: CurrentRunState | null | undefined): string {
  const runId = run?.runId
  if (!runId) return path
  const join = path.includes('?') ? '&' : '?'
  return `${path}${join}run=${encodeURIComponent(runId)}`
}

export function resolveStoredRunId<T extends { runId: number | string; startupName?: string }>(
  records: T[],
  requestedRunId: string,
  storedRun: CurrentRunState | null,
): string {
  if (records.some(record => String(record.runId) === String(requestedRunId))) {
    return requestedRunId
  }

  const expectedName = storedRun?.startupName
  const matchingRecord = expectedName
    ? records.find(record => String(record.startupName || '').toLowerCase() === expectedName.toLowerCase())
    : undefined

  return String(matchingRecord?.runId || storedRun?.storedRunId || records[0]?.runId || '')
}

