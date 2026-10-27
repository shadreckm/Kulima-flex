// Kulima FLEX — Platform Operations Console client (Admin Console V1).
//
// Internal tooling, not a customer feature. Every endpoint below except
// `getAdminSession` reads aggregates across *all* workspaces and is gated by a
// configured platform-operator allow-list on the backend (see
// backend/app/core/admin_access.py). A 403 here is the intended behaviour for
// every ordinary user — organization roles, including Owner, do not grant
// access. All requests go through the authenticated Next.js proxy at /api/v1.

const API_BASE = typeof window === 'undefined'
  ? process.env.KULIMA_BACKEND_URL
    || (process.env.KULIMA_BACKEND_HOSTPORT ? `http://${process.env.KULIMA_BACKEND_HOSTPORT}` : '')
    || process.env.NEXT_PUBLIC_API_URL
    || ''
  : ''

async function readText(res: Response): Promise<string> {
  try {
    return await res.text()
  } catch {
    return ''
  }
}

async function call<T>(path: string, context: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: 'no-store' })
  const raw = await readText(res)
  if (!res.ok) {
    throw new AdminRequestError(context, res.status, raw)
  }
  if (!raw) {
    throw new Error(`${context} returned an empty response`)
  }
  try {
    return JSON.parse(raw) as T
  } catch {
    throw new Error(`${context} returned non-JSON response: ${raw.slice(0, 200)}`)
  }
}

/**
 * Carries the HTTP status so a screen can tell "you are not an operator" (403)
 * apart from a genuine data failure. The backend's error detail is a structured
 * object with `code` and `message`, never a dump of other users' data.
 */
export class AdminRequestError extends Error {
  status: number
  code: string
  constructor(context: string, status: number, raw: string) {
    let code = ''
    let message = ''
    try {
      const parsed = JSON.parse(raw)
      const detail = parsed?.detail ?? parsed
      code = String(detail?.code || '')
      message = String(detail?.message || '')
    } catch {
      message = raw.slice(0, 200)
    }
    super(`${context} failed: ${status} ${message || code || raw.slice(0, 200)}`)
    this.name = 'AdminRequestError'
    this.status = status
    this.code = code
  }
}

function qs(entries: Record<string, string | number | undefined | null>): string {
  const params = new URLSearchParams()
  Object.entries(entries).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  })
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

// ── Session probe (the only route open to any signed-in user) ────────────────

export type AdminIdentity = {
  userId: string
  orgId: string
  orgName: string
  role: string
  roleLabel: string
  plan: string
  personal: boolean
  permissions: string[]
}

export type AdminSession = {
  isPlatformAdmin: boolean
  reason: string                 // 'granted' | 'not_configured' | 'not_allowlisted'
  matchedVia: string | null      // 'session_subject' | 'verified_email' | null
  identifiersChecked: string[]   // the caller's own identifiers only
  allowListConfigured: boolean
  allowListSize: number
  identity: AdminIdentity
  generatedAt: string
}

export function getAdminSession(): Promise<AdminSession> {
  return call<AdminSession>('/api/v1/admin/session', 'getAdminSession')
}

// ── Shared shapes ────────────────────────────────────────────────────────────

/** Counts keyed by a backend label (status, plan, event type, …). */
export type CountMap = Record<string, number>

export type DataNotes = string[]

// ── Phase 1 — Overview ───────────────────────────────────────────────────────

export type AdminOverview = {
  generatedAt: string
  windowDays: number
  organizations: {
    total: number
    teamWorkspaces: number
    personalWorkspaces: number
    createdInWindow: number
    byPlan: CountMap
  }
  users: {
    total: number
    joinedInWindow: number
    activeInWindow: number
    activityDefinition: string
  }
  assessments: {
    total: number
    createdInWindow: number
    byStatus: CountMap
    completedBriefs: number
  }
  documents: { total: number; active: number; storageBytes: number }
  reports: { exportedTotal: number; exportedInWindow: number; byKind: CountMap }
  conversations: { total: number; messages: number; questionsInWindow: number }
  outcomeFollowUps: {
    total: number
    answered: number
    pending: number
    overdueNow: number
    completionRate: number | null
  }
  pipelineHealth: {
    auditEventsTotal: number
    auditEventsInWindow: number
    lastEventAt: string | null
    failedRuns: number
    topEventTypes: { eventType: string; count: number }[]
  }
  dataNotes: DataNotes
}

export function getAdminOverview(windowDays = 30): Promise<AdminOverview> {
  return call(`/api/v1/admin/overview${qs({ window_days: windowDays })}`, 'getAdminOverview')
}

// ── Phase 2 — User management ────────────────────────────────────────────────

export type AdminUserRow = {
  userId: string
  displayName: string | null
  email: string | null
  orgCount: number
  joinedAt: string | null
  lastActivityAt: string | null
  auditEvents: number
  assessments: number
  active: boolean
  roles: string[]
}

export type AdminOrgRow = {
  id: string
  name: string
  slug: string
  plan: string
  personal: boolean
  createdBy: string | null
  createdAt: string | null
  members: number
  assessments: number
  documents: number
  lastActivityAt: string | null
  billingStatus: string | null
  activationState: string | null
}

export type AdminActivityEvent = {
  id: number
  eventType: string
  orgId: string | null
  userId: string | null
  createdAt: string | null
  metadata: Record<string, unknown>
}

export type AdminUsers = {
  generatedAt: string
  windowDays: number
  search: string | null
  users: AdminUserRow[]
  userCount: number
  organizations: AdminOrgRow[]
  roles: CountMap
  plans: { planId: string; organizations: number; memberships: number }[]
  activity: AdminActivityEvent[]
  dataNotes: DataNotes
}

export function getAdminUsers(opts: { search?: string; limit?: number; windowDays?: number } = {}): Promise<AdminUsers> {
  return call(
    `/api/v1/admin/users${qs({
      search: opts.search,
      limit: opts.limit ?? 100,
      window_days: opts.windowDays ?? 30,
    })}`,
    'getAdminUsers',
  )
}

// ── Phase 3 — Billing ────────────────────────────────────────────────────────

export type AdminPaymentEvent = {
  id: number
  orgId: string
  orgName: string | null
  txRef: string | null
  eventType: string
  plan: string | null
  amount: number | null
  currency: string | null
  status: string | null
  previousPlan: string | null
  createdAt: string
}

export type AdminBilling = {
  generatedAt: string
  windowDays: number
  paychangu: {
    mode: string
    apiSecretConfigured: boolean
    webhookSecretConfigured: boolean
    currency: string
    baseUrl: string
    paymentLinks: {
      planId: string
      name: string
      link: string | null
      requiresApproval: boolean
      priceLabel: string
    }[]
    enforcementEnabled: boolean
    demoMode: boolean
    linkAutoconfirm: boolean
    gracePeriodDays: number
    modeNote: string
  }
  planStatus: {
    subscriptions: number
    organizations: number
    withoutSubscriptionRow: number
    byStatus: CountMap
    byPlan: CountMap
    attention: {
      orgId: string
      orgName: string | null
      plan: string
      status: string
      graceUntil: string | null
      lastError: string | null
      pendingPlan: string | null
      activationState: string | null
    }[]
    knownStatuses: string[]
  }
  revenue: {
    collectedInWindow: number | null
    collectedEventCount: number
    windowDays: number
    recurringActivePaid: number | null
    paidActiveSubscriptions: number
    paidWithoutAmount: number
    currency: string
    note: string
  }
  upgradeHistory: { count: number; events: AdminPaymentEvent[] }
  failedPayments: { count: number; events: AdminPaymentEvent[] }
  ledger: { count: number; recent: AdminPaymentEvent[] }
  dataNotes: DataNotes
}

export function getAdminBilling(windowDays = 30): Promise<AdminBilling> {
  return call(`/api/v1/admin/billing${qs({ window_days: windowDays })}`, 'getAdminBilling')
}

// ── Phase 4 — AI health ──────────────────────────────────────────────────────

export type AdminProviderTier = {
  id: string
  label: string
  configured: boolean
  model: string
  inChain: boolean
  disabledNow: boolean
  assessmentsUsingIt: number
  fallbacksFromIt: number
  lastUsedAt: string | null
  avgResponseMs: number | null
}

export type AdminAiHealth = {
  generatedAt: string
  windowDays: number
  providers: AdminProviderTier[]
  chain: {
    activeOrder: string[]
    configuredByEnv: string[]
    configuredTiers: string[]
    unconfiguredTiers: string[]
    disabledInProcess: string[]
    note: string
  }
  usage: {
    providerHealthEvents: number
    assessmentsStartedInWindow: number
    analystQuestionsInWindow: number
    perProvider: Record<string, { events: number; fallbacks: number }>
    emptyReason: string | null
  }
  latency: {
    samples: number
    medianMs: number | null
    p95Ms: number | null
    llmTimeoutSeconds: number
  }
  failures: {
    runsByStatus: CountMap
    failedRuns: number
    runningRuns: number
    recentFailedRuns: {
      runId: string
      status: string
      errorMessage: string
      createdAt: string | null
      completedAt: string | null
      orgId: string | null
    }[]
    hardFailureEvents: number
  }
  fallbacks: {
    fallbackEvents: number
    fallbackRate: number | null
    documentIntelligenceActivations: number
    documentIntelligenceRate: number | null
    researchDegradedToDocuments: number
    definition: string
  }
  documentIntelligence: {
    activations: number
    lastActivationAt: string | null
    modeLabel: string
    explanation: string
  }
  externalResearch: {
    provider: string
    configured: boolean
    allowedFieldsOnly: boolean
    maxResults: number
  }
  processSnapshot: {
    lastResult: {
      provider: string
      model: string
      fallbackTriggered: boolean
      fallbackCount: number
      responseTimeMs: number
      analysisMode: string
    } | null
    note: string
  }
  dataNotes: DataNotes
}

export function getAdminAiHealth(windowDays = 30): Promise<AdminAiHealth> {
  return call(`/api/v1/admin/ai-health${qs({ window_days: windowDays })}`, 'getAdminAiHealth')
}

// ── Phase 5 — Outcome intelligence ───────────────────────────────────────────

export type AdminPendingOutcome = {
  runId: string
  entityName: string | null
  recommendation: string | null
  trustScore: number | null
  integrityGrade: string | null
  followupDueAt: string | null
  createdAt: string | null
  orgId: string | null
  orgName: string | null
  daysOverdue: number | null
  dueState: string
}

// Trust bands from the shared calibration engine (kulima/db.py
// compute_outcome_intelligence) — one definition, customer and operator views.
export type CalibrationBin = {
  tier: string
  decision_count: number
  completed_count: number
  successful_count: number
  success_rate: number
  is_predictive: boolean
}

export type AdminOutcomeLearning = {
  summary: {
    total_decisions: number
    completed_outcomes: number
    decision_accuracy: number | null
    trust_accuracy: number | null
    signal_accuracy: number | null
    recommendation_accuracy: number | null
    [key: string]: unknown
  }
  calibration: {
    overall_predictive_score: number | null
    high_trust_success_rate: number | null
    low_trust_failure_rate: number | null
    calibration_summary: string
    bins: CalibrationBin[]
    reportableBands: CalibrationBin[]
    bandNote: string
    [key: string]: unknown
  }
  feedback: { ratings: number; average: number | null; positive: number }
  settledOutcomes: number
}

export type AdminOutcomes = {
  generatedAt: string
  windowDays: number
  followUpCompletion: {
    total: number
    answered: number
    pending: number
    overdueNow: number
    answeredInWindow: number
    completionRate: number | null
    cadenceDays: number
  }
  decisionTaken: { byAnswer: CountMap; decidedYes: number; decisionRate: number | null }
  followedRate: { followed: number; decidable: number; rate: number | null; definition: string }
  daysToFollowUp: { samples: number; average: number | null; median: number | null; definition: string }
  pendingOutcomes: {
    count: number
    overdue: number
    rows: AdminPendingOutcome[]
    definition: string
    outcomeStatuses: CountMap
    outcomeRowsWithLessons: number
    outcomeRowsTotal: number
  }
  decisionLearning: AdminOutcomeLearning
  dataNotes: DataNotes
}

export function getAdminOutcomes(windowDays = 30): Promise<AdminOutcomes> {
  return call(`/api/v1/admin/outcomes${qs({ window_days: windowDays })}`, 'getAdminOutcomes')
}

// ── Phase 6 — Audit logs ─────────────────────────────────────────────────────

export type AdminAuditEvent = {
  id: number
  eventType: string
  label: string
  category: string
  orgId: string | null
  orgName: string | null
  userId: string | null
  runId: string | null
  assessmentId: string | null
  documentId: string | null
  metadata: Record<string, unknown>
  createdAt: string | null
}

export type AdminAuditFilters = {
  eventTypes?: string[]
  bucket?: AdminAuditBucket
  orgId?: string
  userId?: string
  windowDays?: number
  limit?: number
}

export type AdminAuditBucket = 'creation' | 'deletes' | 'roles' | 'billing'

export type AdminAudit = {
  generatedAt: string
  filters: {
    eventTypes: string[] | null
    bucket: AdminAuditBucket | null
    orgId: string | null
    userId: string | null
    windowDays: number | null
    limit: number
  }
  count: number
  events: AdminAuditEvent[]
  totals: {
    assessmentCreation: number
    deletes: number
    roleChanges: number
    billingEvents: number
    loginEvents: number
    reportExports: number
    providerHealth: number
    adminConsoleViews: number
    matchingEvents: number
    totalEvents: number
  }
  byCategory: CountMap
  byEventType: CountMap
  distinctOrgs: number
  distinctUsers: number
  dataNotes: DataNotes
}

// The four buckets the console is asked to surface. Each is one word: the event
// types behind it live on the server (admin_ops._BUCKETS) so this screen can
// never list a different set than the count reports.
export const AUDIT_BUCKETS: { id: AdminAuditBucket; label: string; totalKey: keyof AdminAudit['totals'] }[] = [
  { id: 'creation', label: 'Assessment Creation', totalKey: 'assessmentCreation' },
  { id: 'deletes', label: 'Deletes', totalKey: 'deletes' },
  { id: 'roles', label: 'Role Changes', totalKey: 'roleChanges' },
  { id: 'billing', label: 'Billing Events', totalKey: 'billingEvents' },
]

export function getAdminAudit(filters: AdminAuditFilters = {}): Promise<AdminAudit> {
  const types = filters.eventTypes && filters.eventTypes.length ? filters.eventTypes.join(',') : undefined
  return call(
    `/api/v1/admin/audit${qs({
      event_types: types,
      bucket: filters.bucket,
      org_id: filters.orgId,
      user_id: filters.userId,
      window_days: filters.windowDays,
      limit: filters.limit ?? 200,
    })}`,
    'getAdminAudit',
  )
}
