// Enterprise Trust & Monetization API layer (Phases 2–9).
//
// Organizations (tenancy + RBAC), Governance (audit, data ownership,
// trust dashboard) and Billing (plans, checkout, PayChangu status).
// All requests go through the authenticated Next.js proxy at /api/v1.

const API_BASE = typeof window === 'undefined' ? process.env.NEXT_PUBLIC_API_URL || '' : ''

async function readText(res: Response): Promise<string> {
  try {
    return await res.text()
  } catch {
    return ''
  }
}

async function call<T>(path: string, init: RequestInit | undefined, context: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  const raw = await readText(res)
  if (!res.ok) {
    throw new Error(`${context} failed: ${res.status} ${raw.slice(0, 400)}`)
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

function jsonInit(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
}

// ── Organizations & members (Phases 2–3) ─────────────────────────────────────

export type RoleDefinition = {
  role: string
  label: string
  permissions: string[]
}

export type OrgMemberRecord = {
  userId: string
  orgId: string
  role: string
  roleLabel: string
  email?: string | null
  displayName?: string | null
  createdAt?: string
  permissions: string[]
}

export type OrgOverview = {
  userId: string
  orgId: string
  orgName: string
  role: string
  roleLabel: string
  plan: string
  personal: boolean
  permissions: string[]
  memberCount: number
  roleDefinitions: RoleDefinition[]
}

export type OrgListItem = {
  id: string
  name: string
  slug: string
  plan: string
  personal: boolean
}

export function getOrgContext(): Promise<OrgOverview> {
  return call<OrgOverview>('/api/v1/orgs/me', undefined, 'getOrgContext')
}

export function listOrgs(): Promise<{ organizations: OrgListItem[]; activeOrgId: string }> {
  return call('/api/v1/orgs/', undefined, 'listOrgs')
}

export function renameOrg(name: string): Promise<OrgListItem> {
  return call('/api/v1/orgs/me', jsonInit('PATCH', { name }), 'renameOrg')
}

export function listOrgMembers(): Promise<{ members: OrgMemberRecord[]; roleDefinitions: RoleDefinition[]; orgId: string }> {
  return call('/api/v1/orgs/me/members', undefined, 'listOrgMembers')
}

export function addOrgMember(payload: { userId: string; role?: string; email?: string; displayName?: string }): Promise<OrgMemberRecord> {
  return call('/api/v1/orgs/me/members', jsonInit('POST', payload), 'addOrgMember')
}

export function setOrgMemberRole(userId: string, role: string): Promise<OrgMemberRecord> {
  return call(`/api/v1/orgs/me/members/${encodeURIComponent(userId)}`, jsonInit('PATCH', { role }), 'setOrgMemberRole')
}

export function removeOrgMember(userId: string): Promise<{ removed: boolean; userId: string }> {
  return call(`/api/v1/orgs/me/members/${encodeURIComponent(userId)}`, { method: 'DELETE' }, 'removeOrgMember')
}

export function claimLegacyData(): Promise<{ claimed: Record<string, number> }> {
  return call('/api/v1/orgs/claim-legacy', { method: 'POST' }, 'claimLegacyData')
}

// ── Billing & subscriptions (Phases 7–8) ─────────────────────────────────────

export type BillingPlan = {
  planId: string
  name: string
  description: string
  monthlyPrice: number
  currency: string
  assessmentQuota: number | null
  assessmentQuotaLabel: string
  memberQuota: number | null
  memberQuotaLabel: string
  features: string[]
  featureLabels: string[]
}

export type BillingUsage = {
  planId: string
  assessmentsThisMonth: number
  assessmentQuota: number | null
  remaining: number | null
  unlimited: boolean
  monthStart: string
}

export type BillingStatusPayload = {
  orgId: string
  planId: string
  planName: string
  status: string
  inGrace: boolean
  graceUntil: string | null
  periodStart: string | null
  periodEnd: string | null
  cancelAtPeriodEnd: boolean
  pendingPlan: string | null
  lastError: string | null
  currency: string
  enforcementEnabled: boolean
  gracePeriodDays: number
  demoMode: boolean
  features: string[]
  usage: BillingUsage
  canAssess: boolean
  // Added by the /status endpoint:
  featureLabels: Record<string, string>
  orgName: string
  role: string
  canManageBilling: boolean
}

export type PaymentEventRecord = {
  id: number
  orgId: string
  txRef: string | null
  eventType: string
  plan: string | null
  amount: number | null
  currency: string | null
  status: string | null
  payload: Record<string, unknown>
  createdAt: string
}

export function getBillingPlans(): Promise<{
  plans: BillingPlan[]
  currentPlan: string
  currency: string
  featureLabels: Record<string, string>
  usage: BillingUsage
  canManageBilling: boolean
}> {
  return call('/api/v1/billing/plans', undefined, 'getBillingPlans')
}

export function getBillingStatus(): Promise<BillingStatusPayload> {
  return call('/api/v1/billing/status', undefined, 'getBillingStatus')
}

export function getBillingHistory(limit = 100): Promise<{ events: PaymentEventRecord[] }> {
  return call(`/api/v1/billing/history?limit=${encodeURIComponent(String(limit))}`, undefined, 'getBillingHistory')
}

export type CheckoutResult = {
  // Live PayChangu checkout or demo-mode checkout:
  txRef?: string
  checkoutUrl?: string | null
  demoMode?: boolean
  plan?: string
  amount?: number
  currency?: string
  message?: string
  // Free-target (downgrade applied immediately):
  status?: string
  result?: Record<string, unknown>
}

export function startCheckout(plan: string, opts: { returnUrl?: string; callbackUrl?: string } = {}): Promise<CheckoutResult> {
  return call('/api/v1/billing/checkout', jsonInit('POST', { plan, ...opts }), 'startCheckout')
}

export function confirmDemoCheckout(txRef: string, plan: string): Promise<{ status: string; planId: string; txRef: string }> {
  return call('/api/v1/billing/checkout/confirm', jsonInit('POST', { txRef, plan }), 'confirmDemoCheckout')
}

export function verifyPayment(txRef: string): Promise<{ status: string; processed: boolean; planId?: string; demoMode?: boolean; reason?: string }> {
  return call(`/api/v1/billing/verify/${encodeURIComponent(txRef)}`, { method: 'POST' }, 'verifyPayment')
}

export function downgradePlan(plan: string): Promise<{ result: Record<string, unknown>; status: BillingStatusPayload }> {
  return call('/api/v1/billing/downgrade', jsonInit('POST', { plan }), 'downgradePlan')
}

export function cancelSubscription(): Promise<{ status: BillingStatusPayload }> {
  return call('/api/v1/billing/cancel', { method: 'POST' }, 'cancelSubscription')
}

export function reactivateSubscription(): Promise<{ status: BillingStatusPayload }> {
  return call('/api/v1/billing/reactivate', { method: 'POST' }, 'reactivateSubscription')
}

// ── Governance (Phases 1, 4, 9) ──────────────────────────────────────────────

export type AuditEventRecord = {
  id: number
  eventType: string
  label: string
  category: string
  orgId: string | null
  userId: string | null
  runId: string | null
  assessmentId: string | null
  documentId: string | null
  metadata: Record<string, unknown>
  createdAt: string
}

export type GovernanceSummary = {
  orgId: string
  orgName: string
  plan: string
  documents: {
    total: number
    active: number
    deleted: number
    expired: number
    storageBytes: number
    encrypted: number
    scheduledForDeletion: number
  }
  assessments: { total: number; active: number }
  audit: { totalEvents: number; lastEventAt: string | null; recent: AuditEventRecord[] }
  members: { total: number; byRole: Record<string, number> }
  retention: {
    defaultRetentionDays: number | null
    deletedPending: number
    expired: number
    policyUrl: string
    policySummary: string
  }
  security: {
    atRestScheme: string
    atRestEncryptionAvailable: boolean
    storageMetadataRecorded: boolean
    accessChecks: boolean
    softDeleteEnabled: boolean
    privateByDefault: boolean
    externalResearchGuard: {
      enabled: boolean
      mode: string
      provider: string
      allowedFields: string[]
      redactionActive: boolean
    }
  }
  billing: { planId: string; status: string; enforcementEnabled: boolean; graceUntil: string | null }
  usage: BillingUsage
  generatedAt: string
}

export function getGovernanceSummary(): Promise<GovernanceSummary> {
  return call('/api/v1/governance/summary', undefined, 'getGovernanceSummary')
}

export function getActivity(params: { assessmentId?: string; runId?: string | number; eventTypes?: string[]; limit?: number } = {}): Promise<{
  events: AuditEventRecord[]
  count: number
  scope: string
  orgId: string
}> {
  const query = new URLSearchParams()
  if (params.assessmentId) query.set('assessment_id', params.assessmentId)
  if (params.runId != null) query.set('run_id', String(params.runId))
  if (params.eventTypes?.length) query.set('event_types', params.eventTypes.join(','))
  query.set('limit', String(params.limit ?? 100))
  return call(`/api/v1/governance/activity?${query.toString()}`, undefined, 'getActivity')
}

export type DataOwnershipPayload = {
  orgId: string
  orgName: string
  role: string
  roleLabel: string
  ownership: {
    statement: string
    points: string[]
    externalResearchPolicy: {
      provider: string
      allowedFields: string[]
      statement: string
    }
  }
  custody: {
    documents: number
    documentsActive: number
    documentsDeleted: number
    storageBytes: number
    assessments: number
  }
  retention: {
    defaultRetentionDays: number | null
    policyUrl: string
    privacyPolicyUrl: string
  }
  capabilities: {
    canExportDocuments: boolean
    canDeleteDocuments: boolean
    canDeleteAssessment: boolean
    canManageUsers: boolean
    canManageBilling: boolean
  }
  generatedAt: string
}

export function getDataOwnership(): Promise<DataOwnershipPayload> {
  return call('/api/v1/governance/data-ownership', undefined, 'getDataOwnership')
}

export function recordLoginEvent(): Promise<{ recorded: boolean }> {
  return call('/api/v1/governance/login-event', { method: 'POST' }, 'recordLoginEvent')
}

