export type CurrentRunState = {
  runId: string
  storedRunId?: string
  startupName?: string
  founderName?: string
  recommendation?: string
  trustScore?: number | null
  status?: string
}

const STORAGE_KEY = 'kulima_current_run'

export const OSTX_CASES = [
  {
    startupName: 'AgriNova Malawi',
    founderName: 'Dr. Chimwemwe Phiri',
    liveRunId: 'ostx-agrinova-malawi',
    recommendation: 'Invest',
    trustScore: 88,
    outcome: 'INVEST',
    summary: 'Strong market, founder, and Grade-A evidence integrity.',
  },
  {
    startupName: 'GreenLink Foods',
    founderName: 'Kondwani Banda',
    liveRunId: 'ostx-greenlink-foods',
    recommendation: 'Observe',
    trustScore: 64,
    outcome: 'OBSERVE',
    summary: 'Mixed evidence with contract conflict and power-grid risk.',
  },
  {
    startupName: 'SolarHarvest Cooperative',
    founderName: 'Blessings Mtonga',
    liveRunId: 'ostx-solarharvest-cooperative',
    recommendation: 'Pass',
    trustScore: 32,
    outcome: 'PASS',
    summary: 'Grade-F integrity with unverified concession claims.',
  },
] as const

export function findOstxCase(runId: string) {
  return OSTX_CASES.find(c => c.liveRunId === runId || String(c.liveRunId) === String(runId))
}

export function loadCurrentRun(): CurrentRunState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY) || window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.runId) return null

    const ostxMatch = findOstxCase(parsed.runId)
    if (ostxMatch) {
      return {
        ...parsed,
        startupName: parsed.startupName || ostxMatch.startupName,
        founderName: parsed.founderName || ostxMatch.founderName,
        recommendation: parsed.recommendation || ostxMatch.recommendation,
        trustScore: parsed.trustScore ?? ostxMatch.trustScore,
        status: parsed.status || 'completed',
      }
    }
    return parsed as CurrentRunState
  } catch {
    return null
  }
}

export function saveCurrentRun(run: CurrentRunState) {
  if (typeof window === 'undefined') return
  const ostxMatch = findOstxCase(run.runId)
  const fullRun: CurrentRunState = ostxMatch ? {
    ...run,
    startupName: run.startupName || ostxMatch.startupName,
    founderName: run.founderName || ostxMatch.founderName,
    recommendation: run.recommendation || ostxMatch.recommendation,
    trustScore: run.trustScore ?? ostxMatch.trustScore,
    status: run.status || 'completed',
  } : run

  const jsonStr = JSON.stringify(fullRun)
  try { window.localStorage.setItem(STORAGE_KEY, jsonStr) } catch {}
  try { window.sessionStorage.setItem(STORAGE_KEY, jsonStr) } catch {}
  window.dispatchEvent(new CustomEvent('kulima-current-run-changed', { detail: fullRun }))
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

