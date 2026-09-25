const API_BASE = typeof window === 'undefined' ? process.env.NEXT_PUBLIC_API_URL || '' : ''

function withAuth(headers: HeadersInit = {}): HeadersInit {
  const base: Record<string, string> = {}
  if (headers instanceof Headers) {
    headers.forEach((value, key) => {
      base[key] = value
    })
  } else if (Array.isArray(headers)) {
    for (const [k, v] of headers) {
      base[k] = v as string
    }
  } else {
    Object.assign(base, headers as Record<string, string>)
  }
  return base
}

async function readResponseText(res: Response): Promise<string> {
  try {
    return await res.text()
  } catch {
    return ''
  }
}

/** Extract the backend diagnostic code (SESSION_MISSING, SESSION_INVALID,
 *  RBAC_DENIED, ORG_CONTEXT_MISSING, …) from a 401/403 JSON body. */
export function diagnosticCode(raw: string): string | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    const code = typeof parsed?.code === 'string' ? parsed.code : null
    return code || null
  } catch {
    return null
  }
}

/** Human-readable explanation for auth failure codes. */
function authFailureHint(code: string | null): string {
  switch (code) {
    case 'SESSION_MISSING':
      return 'Your session has expired. Please sign in again.'
    case 'SESSION_INVALID':
      return 'Session could not be verified — the deployment secrets are mismatched (contact support).'
    case 'SESSION_EXPIRED':
      return 'Your session has expired. Please sign in again.'
    case 'FRONTEND_SECRET_MISSING':
      return 'Server authentication is not configured (contact support).'
    case 'BACKEND_AUTH_FAILED':
      return 'Authentication failed unexpectedly (contact support).'
    case 'ORG_CONTEXT_MISSING':
      return 'Your workspace could not be resolved (contact support).'
    case 'RBAC_DENIED':
      return 'Your role does not have permission for this action.'
    default:
      return ''
  }
}

function describeFailure(res: Response, raw: string, context: string): string {
  const code = diagnosticCode(raw)
  const hint = authFailureHint(code)
  if (code && hint) return `${context} failed: ${res.status} [${code}] ${hint}`
  return `${context} failed: ${res.status} ${raw.slice(0, 400)}`
}

async function parseJsonResponse<T>(res: Response, context: string): Promise<T> {
  const raw = await readResponseText(res)
  if (!raw) {
    throw new Error(`${context} returned an empty response`)
  }

  try {
    return JSON.parse(raw) as T
  } catch {
    const preview = raw.length > 500 ? `${raw.slice(0, 500)}…` : raw
    throw new Error(`${context} returned non-JSON response: ${preview}`)
  }
}

export type RunStatus = {
  runId: string;
  status: string;
  dbId?: number | null;
  createdAt?: string | null;
  completedAt?: string | null;
  error?: string | null;
}

export type DecisionSnapshot = {
  verdict: string;
  confidencePercent: number | null;
  confidenceLabel: string | null;
  reliabilityGrade: string | null;
  reliabilityScore: number | null;
  topReasons: string[];
  topRisks: string[];
  nextAction: string;
  // Expanded decision engine (evidence + trust + risk + climate + environment
  // + tourism + community impact) — optional for backward compatibility.
  decisionScore?: number | null;
  decisionBand?: string | null;
  decisionRationale?: string[] | null;
  domainScores?: Record<string, { label: string; score: number; weight: number; impact: number }> | null;
}

export type SignalItem = {
  id: string;
  level: string;
  category: string;
  direction: string;
  title: string;
  description: string;
  recommendedAction: string;
  confidence: number;
  evidenceRefs?: string[];
  evidenceSummary?: string;
  timeHorizon?: string | null;
  metadata?: Record<string, any>;
}

export type DomainSignals = {
  domain: string;
  label: string;
  count: number;
  riskCount: number;
  opportunityCount: number;
  signals: SignalItem[];
  // Per-domain rollup (Step 6): score 0–100, higher = healthier.
  score?: number;
  summary?: string;
  recommendation?: string;
}

export type SignalsSummary = {
  critical: number;
  high: number;
  medium: number;
  low: number;
  topRisks: SignalItem[];
  topOpportunities: SignalItem[];
  domains?: Record<string, DomainSignals>;
  allSignals?: SignalItem[];
}

export type CreateRunPayload = {
  founder: string
  startup?: string
  /** When present the run identity is resolved from the shared Assessment Context. */
  assessmentId?: string
  /** Entity type for display purposes — passed through to backend when supported */
  entityType?: string
  /** Additional entity metadata forwarded to backend */
  entityMeta?: Record<string, string>
}

export async function createRun(founder: string, startup?: string, extra?: Omit<CreateRunPayload, 'founder' | 'startup'>): Promise<{ runId: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/`, {
    method: 'POST',
    headers: withAuth({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ founder, startup, ...extra }),
  })
  if (!res.ok) throw new Error(`createRun failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ runId: string; status: string }>(res, 'createRun')
}

// ── Assessment Context (single intake engine) ─────────────────────────────
// The landing page uploads documents once; the backend extracts entity
// fields and returns the shared context reused by every workspace.

export type AssessmentFieldPayload = {
  value: string
  confidence: number
  source: string
}

export type AssessmentContextPayload = {
  assessmentId: string
  assessmentType: string
  assessmentTypeLabel: string
  status: string
  runId?: string | null
  requiresConfirmation: boolean
  confidenceThreshold: number
  displayEntity: string
  organizationName: string
  startupName: string
  founderName: string
  sector: string
  country: string
  website: string
  team: string
  problemStatement: string
  confidence: number
  extraction: {
    confidence: number
    textAvailable: boolean
    fields: Record<string, AssessmentFieldPayload>
  }
  documentIds: string[]
  uploadedDocuments: Array<Record<string, any>>
  documentCount: number
  extractedTextPreview: string
  extractedTextLength: number
  trustScore?: number | null
  signals: string[]
  decision: Record<string, any>
  createdAt: string
  updatedAt: string
}

export type AssessmentIntakeHints = {
  entityName?: string
  founderName?: string
  organizationName?: string
  sector?: string
  country?: string
  keywords?: string
  website?: string
}

/**
 * Create the shared Assessment Context: uploads documents once, runs the
 * evidence pipeline + auto extraction, and returns everything every other
 * workspace needs (no duplicate data entry).
 */
export async function createAssessment(
  files: File[],
  assessmentType: string,
  hints: AssessmentIntakeHints = {},
): Promise<AssessmentContextPayload> {
  const form = new FormData()
  files.forEach(file => form.append('files', file))
  form.append('assessmentType', assessmentType)
  if (hints.entityName) form.append('entityName', hints.entityName)
  if (hints.founderName) form.append('founderName', hints.founderName)
  if (hints.organizationName) form.append('organizationName', hints.organizationName)
  if (hints.sector) form.append('sector', hints.sector)
  if (hints.country) form.append('country', hints.country)
  if (hints.keywords) form.append('keywords', hints.keywords)
  if (hints.website) form.append('website', hints.website)
  const res = await fetch(`${API_BASE}/api/v1/assessments/`, {
    method: 'POST',
    headers: withAuth(),
    body: form,
  })
  if (!res.ok) throw new Error(describeFailure(res, await readResponseText(res), 'createAssessment'))
  return parseJsonResponse<AssessmentContextPayload>(res, 'createAssessment')
}

/**
 * Single-source-of-truth read for the whole Assessment workspace.
 * Every tab (Overview, Evidence, Research, Signals, Decision, Reports,
 * Activity, Feedback) consumes this instead of re-deriving state locally.
 */
export type AssessmentWorkspacePayload = AssessmentContextPayload

export async function getActiveAssessment(): Promise<AssessmentWorkspacePayload> {
  const res = await fetch(`${API_BASE}/api/v1/assessment-workspace/active`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getActiveAssessment failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<AssessmentWorkspacePayload>(res, 'getActiveAssessment')
}

export async function getAssessmentWorkspace(assessmentId: string): Promise<AssessmentWorkspacePayload> {
  const res = await fetch(`${API_BASE}/api/v1/assessment-workspace/${encodeURIComponent(assessmentId)}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getAssessmentWorkspace failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<AssessmentWorkspacePayload>(res, 'getAssessmentWorkspace')
}

// ── Auth chain diagnostic (release engineering) ─────────────────────────
// Proxies through the SAME chain as every protected endpoint. A 200 here
// proves the full chain (cookie → getToken → mint → backend validate → org)
// works; the error code tells you exactly which stage broke.
export async function authDiagnostic(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/v1/auth/diagnostic`, {
    headers: withAuth(),
  })
  const raw = await readResponseText(res)
  if (!res.ok) throw new Error(describeFailure(res, raw, 'authDiagnostic'))
  return parseJsonResponse<Record<string, unknown>>(res, 'authDiagnostic')
}

export async function getAssessment(assessmentId: string): Promise<AssessmentContextPayload> {
  const res = await fetch(`${API_BASE}/api/v1/assessments/${encodeURIComponent(assessmentId)}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getAssessment failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<AssessmentContextPayload>(res, 'getAssessment')
}

export async function getAssessmentByRun(runId: string | number): Promise<AssessmentContextPayload> {
  const res = await fetch(`${API_BASE}/api/v1/assessments/by-run/${encodeURIComponent(String(runId))}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getAssessmentByRun failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<AssessmentContextPayload>(res, 'getAssessmentByRun')
}

export async function patchAssessmentContext(
  assessmentId: string,
  patch: {
    assessmentType?: string
    entityName?: string
    founderName?: string
    organizationName?: string
    sector?: string
    country?: string
  },
): Promise<AssessmentContextPayload> {
  const res = await fetch(`${API_BASE}/api/v1/assessments/${encodeURIComponent(assessmentId)}`, {
    method: 'PATCH',
    headers: withAuth({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`patchAssessmentContext failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<AssessmentContextPayload>(res, 'patchAssessmentContext')
}

/**
 * Start (or reuse) the intelligence run grounded in the Assessment Context.
 * Tavily research is driven by the extracted entity — the user never
 * re-enters founder or organisation names.
 */
export async function startAssessmentRun(
  assessmentId: string,
): Promise<{ assessmentId: string; runId: string; status: string; reused?: boolean }> {
  const res = await fetch(`${API_BASE}/api/v1/assessments/${encodeURIComponent(assessmentId)}/start`, {
    method: 'POST',
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`startAssessmentRun failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ assessmentId: string; runId: string; status: string; reused?: boolean }>(res, 'startAssessmentRun')
}

export async function getRunStatus(runId: string): Promise<RunStatus> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(runId)}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getRunStatus failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<RunStatus>(res, 'getRunStatus')
}

export async function getDecisionSnapshot(runId: string): Promise<DecisionSnapshot> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(runId)}/brief`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getDecisionSnapshot failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<DecisionSnapshot>(res, 'getDecisionSnapshot')
}

export async function getSignalsSummary(runId: string): Promise<SignalsSummary> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(runId)}/signals`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getSignalsSummary failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<SignalsSummary>(res, 'getSignalsSummary')
}

export async function askIC(runId: string, question: string, history: Array<any> = []): Promise<{ answer: string }> {
  const res = await fetch(`${API_BASE}/api/v1/ask/ic`, {
    method: 'POST',
    headers: withAuth({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ runId, question, history }),
  })
  if (!res.ok) throw new Error(`askIC failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ answer: string }>(res, 'askIC')
}

export function askICStream(runId: string, question: string, history: Array<any> = []) {
  const url = `${API_BASE}/api/v1/ask/ic/stream`
  const controller = new AbortController()
  const listeners: { [k: string]: Array<(ev: any) => void> } = { delta: [], complete: [], error: [] }
  let closed = false

  queueMicrotask(async () => {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: withAuth({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ runId, question, history }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const text = await res.text()
        listeners.error.forEach(fn => fn(new Error(`stream failed: ${res.status} ${text}`)))
        return
      }
      const reader = res.body!.getReader()
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        let idx = buf.indexOf('\n\n')
        while (idx !== -1) {
          const raw = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          const lines = raw.split(/\r?\n/)
          let ev: string | null = null
          let data = ''
          for (const line of lines) {
            if (line.startsWith('event:')) ev = line.slice(6).trim()
            else if (line.startsWith('data:')) data += line.slice(5)
          }
          if (ev) {
            listeners[ev]?.forEach(fn => fn({ data }))
          }
          idx = buf.indexOf('\n\n')
        }
      }
      // finished
      listeners.complete.forEach(fn => fn({ data: '{}' }))
    } catch (err) {
      if (!closed) listeners.error.forEach(fn => fn(err))
    }
  })

  return {
    addEventListener: (name: string, handler: (ev: any) => void) => {
      if (!listeners[name]) listeners[name] = []
      listeners[name].push(handler)
    },
    close: () => {
      closed = true
      controller.abort()
    },
  }
}

export async function askSignals(runId: string, question: string, history: Array<any> = []): Promise<{ answer: string }> {
  const res = await fetch(`${API_BASE}/api/v1/ask/signals`, {
    method: 'POST',
    headers: withAuth({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ runId, question, history }),
  })
  if (!res.ok) throw new Error(`askSignals failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ answer: string }>(res, 'askSignals')
}

export function askSignalsStream(runId: string, question: string, history: Array<any> = []) {
  const url = `${API_BASE}/api/v1/ask/signals/stream`
  const controller = new AbortController()
  const listeners: { [k: string]: Array<(ev: any) => void> } = { delta: [], complete: [], error: [] }
  let closed = false

  queueMicrotask(async () => {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: withAuth({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ runId, question, history }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const text = await res.text()
        listeners.error.forEach(fn => fn(new Error(`stream failed: ${res.status} ${text}`)))
        return
      }
      const reader = res.body!.getReader()
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        let idx = buf.indexOf('\n\n')
        while (idx !== -1) {
          const raw = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          const lines = raw.split(/\r?\n/)
          let ev: string | null = null
          let data = ''
          for (const line of lines) {
            if (line.startsWith('event:')) ev = line.slice(6).trim()
            else if (line.startsWith('data:')) data += line.slice(5)
          }
          if (ev) {
            listeners[ev]?.forEach(fn => fn({ data }))
          }
          idx = buf.indexOf('\n\n')
        }
      }
      listeners.complete.forEach(fn => fn({ data: '{}' }))
    } catch (err) {
      if (!closed) listeners.error.forEach(fn => fn(err))
    }
  })

  return {
    addEventListener: (name: string, handler: (ev: any) => void) => {
      if (!listeners[name]) listeners[name] = []
      listeners[name].push(handler)
    },
    close: () => {
      closed = true
      controller.abort()
    },
  }
}

export async function uploadDocument(file: File, runId?: string | null): Promise<{ id: string; name: string; url: string; trustScore?: number; evidenceStatus?: string; signals?: string[] }> {
  const form = new FormData()
  form.append('file', file)
  if (runId) form.append('runId', runId)
  const res = await fetch(`${API_BASE}/api/v1/documents/`, {
    method: 'POST',
    headers: withAuth(),
    body: form,
  })
  if (!res.ok) throw new Error(`uploadDocument failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ id: string; name: string; url: string; trustScore?: number; evidenceStatus?: string; signals?: string[] }>(res, 'uploadDocument')
}

export type LiveRunRecord = {
  runId: string
  status: string
  createdAt?: string | null
  completedAt?: string | null
  dbId?: number | null
  error?: string | null
  userId?: string | null
}

export type StoredRunRecord = {
  runId: number | string
  createdAt: string
  founderName: string
  startupName: string
  sector?: string | null
  geography?: string | null
  stage?: string | null
  overallScore?: number | null
  founderScore?: number | null
  trustScore?: number | null
  recommendation?: string | null
  confidence?: number | null
  integrityScore?: number | null
  integrityGrade?: string | null
  archivedAt?: string | null
  userId?: string | null
}

export type PilotAnalyticsMetrics = Record<string, number | string | boolean>

export type FullBrief = Record<string, any>

export type RunFeedbackPayload = {
  userName?: string
  rating: number
  comment?: string
}

export async function listLiveRuns(limit = 50): Promise<{ runs: LiveRunRecord[] }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/runs/live?limit=${encodeURIComponent(String(limit))}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(describeFailure(res, await readResponseText(res), 'listLiveRuns'))
  return parseJsonResponse<{ runs: LiveRunRecord[] }>(res, 'listLiveRuns')
}

export async function listStoredRuns(limit = 50, includeArchived = true): Promise<{ runs: StoredRunRecord[] }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/runs?limit=${encodeURIComponent(String(limit))}&include_archived=${includeArchived ? 'true' : 'false'}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`listStoredRuns failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ runs: StoredRunRecord[] }>(res, 'listStoredRuns')
}

export async function getPilotAnalytics(): Promise<PilotAnalyticsMetrics> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/runs/analytics`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getPilotAnalytics failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<PilotAnalyticsMetrics>(res, 'getPilotAnalytics')
}

export async function getFullBrief(runId: number | string): Promise<FullBrief> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(String(runId))}/brief/full`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getFullBrief failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<FullBrief>(res, 'getFullBrief')
}

export async function archiveRun(runId: number | string): Promise<{ ok: boolean; runId: number | string; archived: boolean }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(String(runId))}/archive`, {
    method: 'POST',
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`archiveRun failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ ok: boolean; runId: number | string; archived: boolean }>(res, 'archiveRun')
}

export async function reopenRun(runId: number | string): Promise<{ ok: boolean; runId: number | string; archived: boolean }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(String(runId))}/reopen`, {
    method: 'POST',
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`reopenRun failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ ok: boolean; runId: number | string; archived: boolean }>(res, 'reopenRun')
}

export async function deleteRun(runId: number | string): Promise<{ ok: boolean; runId: number | string; deleted: boolean }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(String(runId))}`, {
    method: 'DELETE',
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`deleteRun failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ ok: boolean; runId: number | string; deleted: boolean }>(res, 'deleteRun')
}

export async function submitRunFeedback(runId: number | string, payload: RunFeedbackPayload): Promise<{ ok: boolean; runId: number | string; rating: number }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(String(runId))}/feedback`, {
    method: 'POST',
    headers: withAuth({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`submitRunFeedback failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ ok: boolean; runId: number | string; rating: number }>(res, 'submitRunFeedback')
}

export function reportDownloadHref(runId: number | string, reportKind: 'memo' | 'report' | 'signals' | 'due-diligence' | 'one-pager', format: 'pdf' | 'txt' = 'pdf') {
  return `/api/v1/intelligence/${encodeURIComponent(String(runId))}/reports/${reportKind}?format=${format}`
}

// ── Feedback ─────────────────────────────────────────────────────────────────

export type FeedbackRecord = {
  id: number
  runId: number | string
  userName: string
  rating: number
  comment: string
  createdAt: string
  // present in list_all_feedback
  startupName?: string | null
  founderName?: string | null
  recommendation?: string | null
  trustScore?: number | null
  integrityGrade?: string | null
}

export async function getRunFeedback(runId: number | string): Promise<{ feedback: FeedbackRecord[]; total: number; runId: string }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/${encodeURIComponent(String(runId))}/feedback`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getRunFeedback failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ feedback: FeedbackRecord[]; total: number; runId: string }>(res, 'getRunFeedback')
}

export async function listAllFeedback(limit = 100): Promise<{ feedback: FeedbackRecord[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/v1/intelligence/feedback/all?limit=${encodeURIComponent(String(limit))}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`listAllFeedback failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ feedback: FeedbackRecord[]; total: number }>(res, 'listAllFeedback')
}

// ── Outcome Tracking & Decision Learning ─────────────────────────────────────

export type OutcomeUpdatePayload = {
  outcome_status: string
  outcome_date?: string | null
  outcome_notes?: string
  what_happened?: string
  what_was_predicted?: string
  what_was_missed?: string
  what_worked?: string
  what_failed?: string
}

export async function getDecisionHistory(limit = 50): Promise<{ decisions: Record<string, any>[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/v1/outcomes/history?limit=${limit}`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getDecisionHistory failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ decisions: Record<string, any>[]; total: number }>(res, 'getDecisionHistory')
}

export async function getOutcome(runId: number | string): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/api/v1/outcomes/${encodeURIComponent(String(runId))}/outcome`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getOutcome failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<Record<string, any>>(res, 'getOutcome')
}

export async function saveOutcome(runId: number | string, payload: OutcomeUpdatePayload): Promise<{ outcome_id: number; run_id: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/outcomes/${encodeURIComponent(String(runId))}/outcome`, {
    method: 'POST',
    headers: withAuth({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`saveOutcome failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<{ outcome_id: number; run_id: number; status: string }>(res, 'saveOutcome')
}

export async function getOutcomeIntelligence(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/api/v1/outcomes/intelligence`, {
    headers: withAuth(),
  })
  if (!res.ok) throw new Error(`getOutcomeIntelligence failed: ${res.status} ${await readResponseText(res)}`)
  return parseJsonResponse<Record<string, any>>(res, 'getOutcomeIntelligence')
}

