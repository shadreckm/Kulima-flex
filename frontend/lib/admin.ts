// Kulima FLEX — Platform Administration Console client.
//
// Internal tooling, not a customer feature. Every endpoint below except
// `getAdminSession` reads or changes state *across* all workspaces and is gated
// on the stored PLATFORM_ADMIN role (see backend/app/core/admin_access.py). A
// 403 here is the intended behaviour for every ordinary user — organization
// roles, including Owner, do not grant access. Each admin route additionally
// declares one platform capability, so this client exposes `hasCapability` and
// the screens render only the controls the signed-in operator actually holds.
// All requests go through the authenticated Next.js proxy at /api/v1, which
// mints both the JWT subject and the provider-verified email claim the role is
// resolved against — an email typed into a form is never one of them.

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

async function call<T>(path: string, context: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: 'no-store',
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers || {}),
    },
  })
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
 * A platform mutation. The body is always sent as JSON, and an undeclared field
 * is rejected by name by the backend (`extra="forbid"`) rather than dropped — a
 * write that crosses workspaces must never look successful when it quietly
 * ignored part of the request.
 */
function mutate<T>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body: unknown, context: string): Promise<T> {
  return call<T>(path, context, { method, body: JSON.stringify(body ?? {}) })
}

/**
 * Carries the HTTP status so a screen can tell "you are not a platform
 * administrator" (403) apart from a genuine data failure, and the backend's
 * error `code` so a mutation can be explained precisely
 * (`ENTERPRISE_ACTIVATION_REQUIRED`, `LAST_ADMIN`, …). The detail is a
 * structured domain message, never a dump of other users' data.
 */
export class AdminRequestError extends Error {
  status: number
  code: string
  /** The backend's own sentence, safe to show an administrator verbatim. */
  detail: string
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
    this.detail = message
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
  /**
   * The provider-verified email claim the proxy minted from the NextAuth JWT —
   * not `organization_members.email`, which an organization Admin can type.
   * This is the identifier an email-based platform grant resolves against.
   */
  verifiedEmail: string | null
  orgId: string
  orgName: string
  role: string
  roleLabel: string
  plan: string
  personal: boolean
  permissions: string[]
}

/**
 * The nine platform capabilities a route may declare. This is a *description* of
 * the server-side enum (`kulima.core.orgs.platform_admins.PlatformCapability`),
 * never an authorization input: the backend decides what a caller holds, and a
 * client cannot ask for a capability by name.
 */
export type AdminCapability =
  | 'view_organizations'
  | 'view_users'
  | 'manage_subscriptions'
  | 'manage_enterprise_accounts'
  | 'view_billing'
  | 'view_provider_health'
  | 'view_audit'
  | 'view_analytics'
  | 'manage_platform_admins'

export const CAPABILITY_LABELS: Record<AdminCapability, string> = {
  view_organizations: 'View all organizations',
  view_users: 'View all users',
  manage_subscriptions: 'Manage subscriptions',
  manage_enterprise_accounts: 'Manage enterprise accounts',
  view_billing: 'View billing',
  view_provider_health: 'View provider health',
  view_audit: 'Access audit logs',
  view_analytics: 'Access platform analytics',
  manage_platform_admins: 'Grant or revoke platform administrators',
}

/** Every capability the platform plane defines — the denominator the console shows. */
export const ALL_CAPABILITIES = Object.keys(CAPABILITY_LABELS) as AdminCapability[]

/** How a grant was obtained. `env_allow_list` is break-glass, not the stored role. */
export type AdminGrantPath = 'platform_role' | 'env_allow_list'

export const PLATFORM_ADMIN_ROLE = 'platform_admin'
export const PLATFORM_ADMIN_ROLE_LABEL = 'Platform Administrator'

export type AdminSession = {
  isPlatformAdmin: boolean
  reason: string                 // 'granted' | 'not_configured' | 'not_allowlisted'
  matchedVia: string | null      // 'session_subject' | 'verified_email' | null
  identifiersChecked: string[]   // the caller's own identifiers only
  allowListConfigured: boolean
  allowListSize: number
  grantedBy: AdminGrantPath | null
  platformRole: string | null
  roleLabel: string | null
  capabilities: AdminCapability[]
  capabilityLabels: string[]
  roleStoreConfigured: boolean
  adminCount: number
  identity: AdminIdentity
  generatedAt: string
}

export function getAdminSession(): Promise<AdminSession> {
  return call<AdminSession>('/api/v1/admin/session', 'getAdminSession')
}

/**
 * Does this session hold one capability? Absence is the only answer that hides a
 * control; the backend enforces the same check independently, so a stale cache
 * here produces a 403 rather than an unauthorized write.
 */
export function hasCapability(session: AdminSession | null | undefined, capability: AdminCapability): boolean {
  return Boolean(session?.isPlatformAdmin && session.capabilities?.includes(capability))
}

/** True when access came from the environment rather than the stored role. */
export function isBreakGlass(session: AdminSession | null | undefined): boolean {
  return session?.grantedBy === 'env_allow_list'
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

// ── Panel — Organizations (the enterprise account surface) ───────────────────

export type AdminOrgDetailRow = {
  orgId: string
  name: string
  slug: string
  plan: string
  personal: boolean
  createdBy: string | null
  createdAt: string | null
  subscriptionPlan: string | null
  billingStatus: string | null
  amount: number | null
  currency: string | null
  billingCycle: string | null
  currentPeriodEnd: string | null
  cancelAtPeriodEnd: boolean
  pendingPlan: string | null
  activationState: string | null
  lastError: string | null
  subscriptionUpdatedAt: string | null
  members: number
  primaryOwnerUserId: string | null
  assessments: number
  assessmentsInWindow: number
  documents: number
  storageBytes: number
  lastActivityAt: string | null
  reportExports: number
  needsAttention: boolean
}

export type AdminOrganizations = {
  generatedAt: string
  windowDays: number
  filters: { search: string | null; plan: string | null; status: string | null; limit: number }
  totals: {
    organizations: number
    teamWorkspaces: number
    personalWorkspaces: number
    createdInWindow: number
    listed: number
    withoutSubscriptionRow: number
    suspended: number
    pastDue: number
    inGrace: number
    enterprise: number
    activationRequested: number
    scheduledChanges: number
    needsAttention: number
  }
  organizations: AdminOrgDetailRow[]
  attentionDefinition: string
  dataNotes: DataNotes
}

export function getAdminOrganizations(
  opts: { search?: string; plan?: string; status?: string; limit?: number; windowDays?: number } = {},
): Promise<AdminOrganizations> {
  return call(
    `/api/v1/admin/organizations${qs({
      search: opts.search,
      plan: opts.plan,
      status: opts.status,
      limit: opts.limit ?? 200,
      window_days: opts.windowDays ?? 30,
    })}`,
    'getAdminOrganizations',
  )
}

// ── Panel — Assessments ──────────────────────────────────────────────────────

export type AdminAssessmentRow = {
  assessmentId: string
  runId: string | null
  assessmentType: string | null
  status: string | null
  userId: string | null
  orgId: string | null
  orgName: string | null
  createdAt: string | null
  updatedAt: string | null
}

export type AdminFailedRunRow = {
  runId: string
  status: string | null
  errorMessage: string | null
  userId: string | null
  orgId: string | null
  createdAt: string | null
  completedAt: string | null
}

export type AdminAssessments = {
  generatedAt: string
  windowDays: number
  filters: { status: string | null; orgId: string | null; search: string | null; limit: number }
  totals: {
    assessments: number
    createdInWindow: number
    neverRun: number
    listed: number
    pipelineRuns: number
    failedRuns: number
    runningNow: number
    completedRuns: number
    failureRate: number | null
    averageRunSeconds: number | null
  }
  byStatus: CountMap
  assessments: AdminAssessmentRow[]
  recentFailures: AdminFailedRunRow[]
  dataNotes: DataNotes
}

export function getAdminAssessments(
  opts: { status?: string; orgId?: string; search?: string; limit?: number; windowDays?: number } = {},
): Promise<AdminAssessments> {
  return call(
    `/api/v1/admin/assessments${qs({
      status: opts.status,
      org_id: opts.orgId,
      search: opts.search,
      limit: opts.limit ?? 100,
      window_days: opts.windowDays ?? 30,
    })}`,
    'getAdminAssessments',
  )
}

// ── Panel — Reports ──────────────────────────────────────────────────────────

export type AdminReportRow = {
  eventId: number
  orgId: string | null
  orgName: string | null
  userId: string | null
  assessmentId: string | null
  createdAt: string | null
  reportKind: string
  format: string
  fileName: string | null
}

export type AdminReports = {
  generatedAt: string
  windowDays: number
  filters: { orgId: string | null; limit: number }
  totals: { exports: number; exportsInWindow: number; listed: number; distinctOrgs: number; distinctUsers: number }
  byKind: CountMap
  byFormat: CountMap
  reports: AdminReportRow[]
  sourceNote: string
  dataNotes: DataNotes
}

export function getAdminReports(
  opts: { orgId?: string; limit?: number; windowDays?: number } = {},
): Promise<AdminReports> {
  return call(
    `/api/v1/admin/reports${qs({
      org_id: opts.orgId,
      limit: opts.limit ?? 150,
      window_days: opts.windowDays ?? 30,
    })}`,
    'getAdminReports',
  )
}

// ── Panel — Conversations ────────────────────────────────────────────────────

export type AdminConversationRow = {
  conversationId: string
  assessmentId: string | null
  runId: string | null
  userId: string | null
  orgId: string | null
  orgName: string | null
  title: string | null
  isDefault: number | boolean | null
  createdAt: string | null
  updatedAt: string | null
  messages: number
  questions: number
  lastMessageAt: string | null
}

export type AdminConversations = {
  generatedAt: string
  windowDays: number
  filters: { orgId: string | null; limit: number }
  totals: {
    conversations: number
    messages: number
    createdInWindow: number
    questionsInWindow: number
    withoutAssessment: number
    listed: number
  }
  conversations: AdminConversationRow[]
  busiest: { conversationId: string; title: string | null; orgName: string | null; messages: number }[]
  dataNotes: DataNotes
}

export function getAdminConversations(
  opts: { orgId?: string; limit?: number; windowDays?: number } = {},
): Promise<AdminConversations> {
  return call(
    `/api/v1/admin/conversations${qs({
      org_id: opts.orgId,
      limit: opts.limit ?? 100,
      window_days: opts.windowDays ?? 30,
    })}`,
    'getAdminConversations',
  )
}

// ── Panel — Access (the role architecture itself, and the roster) ────────────

export type AdminRosterRow = {
  principal: string
  role: string
  roleLabel: string
  userId: string | null
  email: string | null
  displayName: string | null
  status: string
  source: string          // 'bootstrap' | 'granted'
  grantedBy: string | null
  grantedAt: string | null
  revokedBy: string | null
  revokedAt: string | null
  capabilities: AdminCapability[]
  isPrimary: boolean
  lastSeenAt: string | null
  activeSinceWindow: boolean
}

export type AdminAccess = {
  generatedAt: string
  windowDays: number
  platformRole: {
    id: string
    label: string
    capabilities: { id: AdminCapability; label: string }[]
    note: string
  }
  orgRoles: { id: string; label: string; platformCapabilities: string[] }[]
  roleDistribution: CountMap
  store: {
    configured: boolean
    activeCount: number
    rowCount: number
    primaryEmail: string | null
    bootstrappedFrom: string[]
    error: string | null
  }
  breakGlass: { configured: boolean; size: number; envNames: string[]; note: string }
  admins: AdminRosterRow[]
  dataNotes: DataNotes
}

export function getAdminAccess(windowDays = 30): Promise<AdminAccess> {
  return call(`/api/v1/admin/access${qs({ window_days: windowDays })}`, 'getAdminAccess')
}

// ── Platform mutations (each one is capability-gated and audited) ────────────

/** The subscription state before or after a change — the audit payload, shown plainly. */
export type AdminSubscriptionSnapshot = {
  orgId: string
  plan: string | null
  status: string | null
  currency: string | null
  amount: number | null
  billingCycle: string | null
  currentPeriodEnd: string | null
  graceUntil: string | null
  cancelAtPeriodEnd: boolean
  pendingPlan: string | null
  activationState: string | null
  updatedAt: string | null
}

export type AdminPlanResult = {
  changed: boolean
  planId: string
  previousPlan?: string
  pendingPlan?: string
  effective?: string
  effectiveAt?: string
  status?: string
}

export type AdminSubscriptionResult = {
  changed: boolean
  before: AdminSubscriptionSnapshot
  after: AdminSubscriptionSnapshot
  planResult: AdminPlanResult | null
  auditedAt: string
}

export const SUBSCRIPTION_PLANS = ['free', 'pro', 'enterprise'] as const
export const SUBSCRIPTION_STATUSES = ['active', 'past_due', 'grace', 'suspended', 'canceled'] as const

export function updateAdminSubscription(
  orgId: string,
  body: {
    plan?: string
    status?: string
    currency?: string
    amount?: number
    billingCycle?: string
    graceUntil?: string
    currentPeriodEnd?: string
    cancelAtPeriodEnd?: boolean
    reason?: string
  },
): Promise<AdminSubscriptionResult> {
  return mutate('PUT', `/api/v1/admin/organizations/${encodeURIComponent(orgId)}/subscription`, body, 'updateAdminSubscription')
}

export function setAdminAccountStatus(
  orgId: string,
  body: { status: string; reason?: string },
): Promise<AdminSubscriptionResult> {
  return mutate('POST', `/api/v1/admin/organizations/${encodeURIComponent(orgId)}/account-status`, body, 'setAdminAccountStatus')
}

export type AdminActivationResult = {
  orgId: string
  before: string | null
  after: string | null
  checkoutAllowed: boolean
  auditedAt: string
}

export function setAdminEnterpriseActivation(
  orgId: string,
  body: { action: 'request' | 'approve' | 'reset'; agreementAccepted?: boolean; contact?: string },
): Promise<AdminActivationResult> {
  return mutate(
    'POST',
    `/api/v1/admin/organizations/${encodeURIComponent(orgId)}/enterprise-activation`,
    body,
    'setAdminEnterpriseActivation',
  )
}

export type AdminOrganizationResult = {
  organization: { orgId: string; name: string; slug: string; plan: string; personal: boolean; createdAt: string | null }
  subscription: AdminSubscriptionSnapshot
  ownerUserId: string
  pendingOwnerEmail: string | null
  auditedAt: string
}

export function createAdminOrganization(body: {
  name: string
  plan?: string
  ownerUserId?: string
  intendedOwnerEmail?: string
}): Promise<AdminOrganizationResult> {
  return mutate('POST', '/api/v1/admin/organizations', body, 'createAdminOrganization')
}

export function renameAdminOrganization(
  orgId: string,
  body: { name: string; reason?: string },
): Promise<{ orgId: string; name: string; slug: string | null; auditedAt: string }> {
  return mutate('PATCH', `/api/v1/admin/organizations/${encodeURIComponent(orgId)}`, body, 'renameAdminOrganization')
}

export type AdminRosterResult = {
  admin: AdminRosterRow
  outcome: 'granted' | 'revived' | 'already_active'
  activeCount: number
  auditedAt: string
}

export function grantAdminRole(body: {
  email?: string
  userId?: string
  displayName?: string
}): Promise<AdminRosterResult> {
  return mutate('POST', '/api/v1/admin/access/admins', body, 'grantAdminRole')
}

export function revokeAdminRole(
  identity: string,
  reason?: string,
): Promise<{ revoked: boolean; identity: { email: string | null; userId: string | null }; activeCount: number; auditedAt: string }> {
  return mutate(
    'DELETE',
    `/api/v1/admin/access/admins/${encodeURIComponent(identity)}${qs({ reason })}`,
    null,
    'revokeAdminRole',
  )
}
