/**
 * Single source of truth for the active evaluation assessment.
 *
 * After upload, the evidence pipeline result is written here.
 * Evidence, Signals, Decision, and Reports pages all read from
 * the same store rather than fetching independently.
 *
 * Sync mechanism: localStorage + CustomEvent so all open tabs
 * and components update without requiring navigation.
 */

export type AssessmentState = {
  /** The run ID this assessment belongs to */
  runId: string
  /** ISO timestamp of the most recent update */
  updatedAt: string
  /** Whether the pipeline has completed at least one upload */
  hasEvidence: boolean
  /** Latest upload result */
  lastUpload?: {
    id: string
    name: string
    trustScore: number
    evidenceStatus: string
    signals: string[]
  }
  /** Current full brief snapshot — refreshed after each upload */
  briefSnapshot?: Record<string, any> | null
  /** Pipeline status */
  pipelineStatus: 'idle' | 'uploading' | 'processing' | 'ready' | 'error'
  /** Error message if pipeline failed */
  pipelineError?: string | null
}

const STORAGE_KEY = 'kulima_assessment'
const EVENT_NAME = 'kulima-assessment-changed'

export function saveAssessment(state: AssessmentState): void {
  if (typeof window === 'undefined') return
  const json = JSON.stringify(state)
  try { localStorage.setItem(STORAGE_KEY, json) } catch {}
  try { sessionStorage.setItem(STORAGE_KEY, json) } catch {}
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: state }))
}

export function loadAssessment(): AssessmentState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as AssessmentState
  } catch {
    return null
  }
}

export function clearAssessment(): void {
  if (typeof window === 'undefined') return
  try { localStorage.removeItem(STORAGE_KEY) } catch {}
  try { sessionStorage.removeItem(STORAGE_KEY) } catch {}
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: null }))
}

export function onAssessmentChanged(handler: (state: AssessmentState | null) => void): () => void {
  if (typeof window === 'undefined') return () => {}
  const listener = (e: Event) => handler((e as CustomEvent).detail)
  window.addEventListener(EVENT_NAME, listener)
  return () => window.removeEventListener(EVENT_NAME, listener)
}

/**
 * Update only specific fields of the current assessment without overwriting
 * the entire object. Creates a new assessment for the runId if none exists.
 */
export function patchAssessment(runId: string, patch: Partial<AssessmentState>): AssessmentState {
  const current = loadAssessment()
  const base: AssessmentState = current?.runId === runId
    ? current
    : { runId, updatedAt: new Date().toISOString(), hasEvidence: false, pipelineStatus: 'idle' }

  const next: AssessmentState = {
    ...base,
    ...patch,
    runId,
    updatedAt: new Date().toISOString(),
  }
  saveAssessment(next)
  return next
}
