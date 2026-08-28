const API_BASE = typeof window === 'undefined' ? process.env.NEXT_PUBLIC_API_URL || '' : ''

function getAuthTokenFromCookie(): string | null {
  if (typeof document === 'undefined') return null
  const cookies = document.cookie.split(';').map(c => c.trim())
  const keys = ['next-auth.session-token', '__Secure-next-auth.session-token']
  for (const key of keys) {
    const prefix = key + '='
    const match = cookies.find(c => c.startsWith(prefix))
    if (match) {
      return decodeURIComponent(match.slice(prefix.length))
    }
  }
  return null
}

function withAuth(headers: HeadersInit = {}): HeadersInit {
  const token = getAuthTokenFromCookie()
  if (!token) return headers
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
  base['Authorization'] = `Bearer ${token}`
  return base
}

async function readResponseText(res: Response): Promise<string> {
  try {
    return await res.text()
  } catch {
    return ''
  }
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
}

export type SignalsSummary = {
  critical: number;
  high: number;
  medium: number;
  low: number;
  topRisks: SignalItem[];
  topOpportunities: SignalItem[];
}

export type CreateRunPayload = {
  founder: string
  startup?: string
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

  ;(async () => {
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
  })()

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

  ;(async () => {
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
  })()

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
  if (!res.ok) throw new Error(`listLiveRuns failed: ${res.status} ${await readResponseText(res)}`)
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

