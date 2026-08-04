export type RecentRun = {
  runId: string
  founder: string
  startup: string
  status: string
  createdAt: string
  route: 'flex' | 'signals'
}

const RECENT_RUNS_KEY = 'kulima_recent_runs'
const MAX_RECENT_RUNS = 5

export function loadRecentRuns(): RecentRun[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(RECENT_RUNS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveRecentRun(run: RecentRun) {
  if (typeof window === 'undefined') return
  const runs = loadRecentRuns()
  const next = [run, ...runs.filter(item => item.runId !== run.runId)].slice(0, MAX_RECENT_RUNS)
  window.localStorage.setItem(RECENT_RUNS_KEY, JSON.stringify(next))
}

export function updateRecentRunStatus(runId: string, status: string) {
  if (typeof window === 'undefined') return
  const runs = loadRecentRuns()
  const next = runs.map(item => item.runId === runId ? { ...item, status } : item)
  window.localStorage.setItem(RECENT_RUNS_KEY, JSON.stringify(next))
}
