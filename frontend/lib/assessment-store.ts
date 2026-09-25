import { saveCurrentRun, loadCurrentRun } from './current-run'
import { saveUseCase, loadUseCase, USE_CASE_LABELS, type UseCaseSelection } from './use-case-store'
import type { EntityType } from './entity-types'

export type AssessmentContextStatus =
  | 'intake'
  | 'needs_confirmation'
  | 'ready'
  | 'running'
  | 'complete'
  | 'failed'
  | (string & {})

/** Per-field extraction payload (mirrors backend ExtractedField). */
export type ExtractedFieldPayload = {
  value: string
  confidence: number
  source: string
}

/** Extraction payload (mirrors backend serialize_context().extraction). */
export type ExtractionPayload = {
  confidence: number
  textAvailable: boolean
  fields: Record<string, ExtractedFieldPayload>
}

/** Uploaded document record (backend AssessmentDocument.model_dump). */
export type UploadedDocumentPayload = {
  id: string
  name: string
  url?: string
  file_type?: string
  trust_score?: number | null
  evidence_status?: string | null
  signals?: string[]
  evidence_items?: string[]
  decision_impact?: string
  raw_summary?: string
  trust_breakdown?: Record<string, any>
  upload_date?: string
}

export type AssessmentContext = {
  /** Canonical entity/assessment type (includes Tourism SME). */
  entityType: EntityType
  entityLabel: string
  entityName: string
  founderOrLead: string
  documentName?: string
  documentSize?: number
  documentType?: string
  runId: string
  createdAt: string
  hasDocument: boolean
  autoInitialized?: boolean

  // ── Shared Assessment Context (backend /api/v1/assessments) ──────────
  // Collect once on the landing page, reuse everywhere (Signals, Flex,
  // Evidence, Decision, Reports, Ask IC).
  /** Central intake record id — reused by every workspace. */
  assessmentId?: string
  assessmentType?: string
  assessmentTypeLabel?: string
  status?: AssessmentContextStatus
  requiresConfirmation?: boolean
  confidenceThreshold?: number
  displayEntity?: string
  /** Flat extracted mirrors (Step 3 auto-extraction). */
  sector?: string
  country?: string
  website?: string
  team?: string
  problemStatement?: string
  keywords?: string[]
  /** Overall extraction confidence (0–1). */
  confidence?: number
  extraction?: ExtractionPayload
  documentIds?: string[]
  uploadedDocuments?: UploadedDocumentPayload[]
  documentCount?: number
  extractedTextPreview?: string
  extractedTextLength?: number
  trustScore?: number | null
  signals?: string[]
  decision?: Record<string, any> | null
  updatedAt?: string
}

/** Mirrors kulima.core.assessment.service.CONFIRMATION_THRESHOLD. */
export const INTAKE_CONFIDENCE_THRESHOLD = 0.55

const ENTITY_TYPE_ALIASES: Record<string, EntityType> = {
  startup: 'startup',
  ngo: 'ngo',
  government: 'government_program',
  government_program: 'government_program',
  development: 'development_program',
  development_program: 'development_program',
  tourism: 'tourism_sme',
  tourism_sme: 'tourism_sme',
  accelerator: 'accelerator',
}

/** Normalize any stored/legacy entity-type string to a canonical EntityType. */
export function normalizeEntityType(value: string | undefined | null): EntityType {
  const key = String(value || '').trim().toLowerCase()
  return ENTITY_TYPE_ALIASES[key] ?? 'startup'
}

/**
 * True when the user must confirm entity details before a run starts —
 * i.e. extraction failed or fell below the confidence threshold.
 */
export function contextNeedsConfirmation(ctx: AssessmentContext | null): boolean {
  if (!ctx) return false
  if (ctx.requiresConfirmation) return true
  if (ctx.confidence != null && ctx.confidence < (ctx.confidenceThreshold ?? INTAKE_CONFIDENCE_THRESHOLD)) {
    return true
  }
  return !ctx.entityName && !ctx.founderOrLead
}

/** True when the shared context carries a usable extracted entity. */
export function contextIsReady(ctx: AssessmentContext | null): boolean {
  return Boolean(ctx?.assessmentId) && !contextNeedsConfirmation(ctx)
}

/** Display line for the intake banner: "Entity · Type". */
export function contextSummaryLine(ctx: AssessmentContext | null): string {
  if (!ctx) return ''
  const entity = ctx.displayEntity || ctx.entityName || 'Pending extraction'
  return `${entity} · ${ctx.assessmentTypeLabel || ctx.entityLabel}`
}

const CONTEXT_STORAGE_KEY = 'kulima_assessment_context'
const CONTEXT_EVENT_NAME = 'kulima-assessment-context-changed'

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

/** Safe `instanceof File` that also works in non-browser runtimes. */
function isFileLike(value: unknown): value is File {
  return typeof File !== 'undefined' && value instanceof File
}

/** Derive and initialize assessment context from landing page selection & document upload */
export function deriveAssessmentContext(
  entityTypeInput?: string,
  fileOrName?: File | string | null,
): AssessmentContext {
  const entityType = (entityTypeInput || 'startup') as AssessmentContext['entityType']
  const label = USE_CASE_LABELS[entityType] || 'Startup / Investor'
  const fileObj: File | null = isFileLike(fileOrName) ? fileOrName : null
  let fileName = typeof fileOrName === 'string' ? fileOrName : fileObj?.name || ''
  const fileSize = fileObj ? fileObj.size : undefined
  const fileType = fileObj ? fileObj.type : undefined

  let entityName = ''
  let founderOrLead = ''
  let runId = ''

  const lowerFile = fileName.toLowerCase()

  if (lowerFile.includes('agrinova')) {
    entityName = 'AgriNova Malawi'
    founderOrLead = 'Dr. Chimwemwe Phiri'
    runId = 'ostx-agrinova-malawi'
  } else if (lowerFile.includes('greenlink')) {
    entityName = 'GreenLink Foods'
    founderOrLead = 'Kondwani Banda'
    runId = 'ostx-greenlink-foods'
  } else if (lowerFile.includes('solarharvest')) {
    entityName = 'SolarHarvest Cooperative'
    founderOrLead = 'Blessings Mtonga'
    runId = 'ostx-solarharvest-cooperative'
  } else if (lowerFile.includes('healthbridge')) {
    entityName = 'HealthBridge Lagos'
    founderOrLead = 'Dr. Adaeze Okonkwo'
    runId = 'pilot-healthbridge-lagos'
  } else if (lowerFile.includes('farmstack')) {
    entityName = 'FarmStack Kenya Program Review'
    founderOrLead = 'James Kariuki'
    runId = 'pilot-farmstack-kenya'
  } else if (fileName) {
    const cleanBase = fileName
      .replace(/\.[^/.]+$/, '')
      .replace(/[_\-]+/g, ' ')
      .replace(/\b(pdf|docx|xlsx|csv|txt|pitch|deck|report|model|final|v\d+)\b/gi, '')
      .trim()
    entityName = cleanBase.length >= 3
      ? cleanBase.charAt(0).toUpperCase() + cleanBase.slice(1)
      : (entityType === 'ngo' ? 'Community Health Initiative' : entityType === 'government_program' ? 'Agricultural Support Program' : 'Venture Portfolio Co')
    founderOrLead = entityType === 'ngo' ? 'Country Director' : entityType === 'government_program' ? 'Program Coordinator' : 'Founding Team'
    runId = `run-${Date.now().toString(36)}`
  } else {
    if (entityType === 'ngo') {
      entityName = 'HealthBridge Lagos'
      founderOrLead = 'Dr. Adaeze Okonkwo'
      runId = 'pilot-healthbridge-lagos'
      fileName = 'HealthBridge_ME_Report.pdf'
    } else if (entityType === 'government_program') {
      entityName = 'FarmStack Kenya Program Review'
      founderOrLead = 'James Kariuki'
      runId = 'pilot-farmstack-kenya'
      fileName = 'FarmStack_Survey_Data.csv'
    } else {
      entityName = 'AgriNova Malawi'
      founderOrLead = 'Dr. Chimwemwe Phiri'
      runId = 'ostx-agrinova-malawi'
      fileName = 'AgriNova_PitchDeck.pdf'
    }
  }

  return {
    entityType,
    entityLabel: label,
    entityName,
    founderOrLead,
    documentName: fileName,
    documentSize: fileSize,
    documentType: fileType,
    runId,
    createdAt: new Date().toISOString(),
    hasDocument: Boolean(fileName),
  }
}

/** Persist assessment context once, updating current-run and use-case stores */
export function saveAssessmentContext(context: AssessmentContext): void {
  if (typeof window === 'undefined') return
  persistContext(context)

  // Synchronize with current run store so every workspace reuses this context
  saveCurrentRun({
    runId: context.runId,
    startupName: context.entityName,
    founderName: context.founderOrLead,
    entityType: context.entityType,
    status: 'completed',
  })

  // Synchronize with use-case store
  saveUseCase(context.entityType)

  // Synchronize with assessment store
  patchAssessment(context.runId, {
    hasEvidence: true,
    lastUpload: {
      id: context.runId,
      name: context.documentName || 'Primary Evidence Document',
      trustScore: 88,
      evidenceStatus: 'VERIFIED',
      signals: ['Assessment context initialized from document and entity selection'],
    },
  })
}

/** Write the context to storage and notify listeners (no store syncing). */
function persistContext(context: AssessmentContext): void {
  if (typeof window === 'undefined') return
  const json = JSON.stringify(context)
  try { localStorage.setItem(CONTEXT_STORAGE_KEY, json) } catch {}
  try { sessionStorage.setItem(CONTEXT_STORAGE_KEY, json) } catch {}
  window.dispatchEvent(new CustomEvent(CONTEXT_EVENT_NAME, { detail: context }))
}

/**
 * Persist a backend Assessment Context payload (serialize_context) into the
 * shared store. Called right after the landing-page upload so every workspace
 * reuses the extracted entity — no duplicate entry (Steps 2–4).
 */
export function saveIntakeContext(payload: Record<string, any>): AssessmentContext {
  const existing = loadAssessmentContext()
  const entityType = normalizeEntityType(payload.assessmentType || existing?.entityType)
  const uploaded: UploadedDocumentPayload[] = Array.isArray(payload.uploadedDocuments)
    ? (payload.uploadedDocuments as UploadedDocumentPayload[])
    : []
  const entityName = String(
    payload.displayEntity || payload.organizationName || payload.startupName || '',
  ).trim() || existing?.entityName || ''

  const ctx: AssessmentContext = {
    entityType,
    entityLabel: String(payload.assessmentTypeLabel || USE_CASE_LABELS[entityType] || 'Startup / Investor'),
    entityName,
    founderOrLead: String(payload.founderName || existing?.founderOrLead || '').trim(),
    documentName: uploaded.length ? String(uploaded[0]?.name || '') : existing?.documentName,
    documentSize: existing?.documentSize,
    documentType: existing?.documentType,
    runId: String(payload.runId || existing?.runId || ''),
    createdAt: String(payload.createdAt || existing?.createdAt || new Date().toISOString()),
    hasDocument:
      (typeof payload.documentCount === 'number' ? payload.documentCount : uploaded.length) > 0 ||
      Boolean(existing?.hasDocument),
    autoInitialized: existing?.autoInitialized,
    assessmentId: String(payload.assessmentId || existing?.assessmentId || ''),
    assessmentType: String(payload.assessmentType || existing?.assessmentType || ''),
    assessmentTypeLabel: String(payload.assessmentTypeLabel || existing?.assessmentTypeLabel || ''),
    status: String(payload.status || existing?.status || 'intake'),
    requiresConfirmation: Boolean(payload.requiresConfirmation ?? existing?.requiresConfirmation),
    confidenceThreshold:
      typeof payload.confidenceThreshold === 'number'
        ? payload.confidenceThreshold
        : existing?.confidenceThreshold ?? INTAKE_CONFIDENCE_THRESHOLD,
    displayEntity: String(payload.displayEntity || existing?.displayEntity || ''),
    sector: String(payload.sector || existing?.sector || ''),
    country: String(payload.country || existing?.country || ''),
    website: String(payload.website || existing?.website || ''),
    team: String(payload.team || existing?.team || ''),
    problemStatement: String(payload.problemStatement || existing?.problemStatement || ''),
    keywords: Array.isArray(payload.keywords)
      ? payload.keywords.map(String)
      : existing?.keywords ?? [],
    confidence: typeof payload.confidence === 'number' ? payload.confidence : existing?.confidence,
    extraction:
      payload.extraction && typeof payload.extraction === 'object'
        ? (payload.extraction as ExtractionPayload)
        : existing?.extraction,
    documentIds: Array.isArray(payload.documentIds)
      ? payload.documentIds.map(String)
      : existing?.documentIds ?? [],
    uploadedDocuments: uploaded.length ? uploaded : existing?.uploadedDocuments ?? [],
    documentCount:
      typeof payload.documentCount === 'number' ? payload.documentCount : uploaded.length,
    extractedTextPreview: String(payload.extractedTextPreview || existing?.extractedTextPreview || ''),
    extractedTextLength:
      typeof payload.extractedTextLength === 'number'
        ? payload.extractedTextLength
        : existing?.extractedTextLength,
    trustScore:
      typeof payload.trustScore === 'number' ? payload.trustScore : existing?.trustScore ?? null,
    signals: Array.isArray(payload.signals) ? payload.signals.map(String) : existing?.signals ?? [],
    decision:
      payload.decision && typeof payload.decision === 'object'
        ? (payload.decision as Record<string, any>)
        : existing?.decision ?? null,
    updatedAt: String(payload.updatedAt || new Date().toISOString()),
  }

  persistContext(ctx)
  saveUseCase(entityType)
  if (ctx.runId) {
    saveCurrentRun({
      runId: ctx.runId,
      startupName: ctx.entityName || undefined,
      founderName: ctx.founderOrLead || undefined,
      entityType: ctx.entityType,
      status: ctx.status === 'complete' ? 'completed' : ctx.status || 'running',
    })
  }
  return ctx
}

/** Load the active assessment context, falling back to current run or default benchmark */
export function loadAssessmentContext(): AssessmentContext | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(CONTEXT_STORAGE_KEY) || sessionStorage.getItem(CONTEXT_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as AssessmentContext
      if (parsed && (parsed.assessmentId || (parsed.entityName && parsed.runId))) {
        return { ...parsed, entityType: normalizeEntityType(parsed.entityType) }
      }
    }
  } catch {}

  // Fallback: build from existing run state if available
  const existingRun = loadCurrentRun()
  if (existingRun && existingRun.runId) {
    const entType = normalizeEntityType(existingRun.entityType)
    return {
      entityType: entType,
      entityLabel: USE_CASE_LABELS[entType] || 'Startup / Investor',
      entityName: existingRun.startupName || 'AgriNova Malawi',
      founderOrLead: existingRun.founderName || 'Dr. Chimwemwe Phiri',
      documentName: 'Primary Evidence Document',
      runId: existingRun.runId,
      createdAt: new Date().toISOString(),
      hasDocument: true,
      autoInitialized: true,
    }
  }

  return null
}

export function hasAssessmentContext(): boolean {
  return loadAssessmentContext() !== null
}

export function clearAssessmentContext(): void {
  if (typeof window === 'undefined') return
  try { localStorage.removeItem(CONTEXT_STORAGE_KEY) } catch {}
  try { sessionStorage.removeItem(CONTEXT_STORAGE_KEY) } catch {}
  window.dispatchEvent(new CustomEvent(CONTEXT_EVENT_NAME, { detail: null }))
}

export function onAssessmentContextChanged(handler: (ctx: AssessmentContext | null) => void): () => void {
  if (typeof window === 'undefined') return () => {}
  const listener = (e: Event) => handler((e as CustomEvent).detail)
  window.addEventListener(CONTEXT_EVENT_NAME, listener)
  return () => window.removeEventListener(CONTEXT_EVENT_NAME, listener)
}

// ── IndexedDB intake persistence ─────────────────────────────────────────
// Landing-page uploads may happen before sign-in. The picked files are kept
// in IndexedDB so the flow resumes after the auth redirect without asking
// the user to re-select or re-enter anything.

const INTAKE_DB_NAME = 'kulima_intake'
const INTAKE_DB_STORE = 'pending_uploads'
const INTAKE_DB_KEY = 'draft'

export type IntakeDraft = {
  assessmentType: EntityType
  files: File[]
  /** Assessment metadata typed on the landing page (single intake). */
  organization?: string
  founder?: string
  keywords?: string
  savedAt: string
}

function openIntakeDb(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      resolve(null)
      return
    }
    try {
      const request = window.indexedDB.open(INTAKE_DB_NAME, 1)
      request.onupgradeneeded = () => {
        const db = request.result
        if (!db.objectStoreNames.contains(INTAKE_DB_STORE)) {
          db.createObjectStore(INTAKE_DB_STORE)
        }
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

/** Persist the picked intake files so they survive the sign-in redirect. */
export async function saveIntakeDraft(
  assessmentType: EntityType,
  files: File[],
  meta: { organization?: string; founder?: string; keywords?: string } = {},
): Promise<boolean> {
  if (!files.length) return false
  const db = await openIntakeDb()
  if (!db) return false
  return new Promise<boolean>((resolve) => {
    try {
      const draft: IntakeDraft = { assessmentType, files, ...meta, savedAt: new Date().toISOString() }
      const tx = db.transaction(INTAKE_DB_STORE, 'readwrite')
      tx.objectStore(INTAKE_DB_STORE).put(draft, INTAKE_DB_KEY)
      tx.oncomplete = () => { db.close(); resolve(true) }
      tx.onerror = () => { db.close(); resolve(false) }
      tx.onabort = () => { db.close(); resolve(false) }
    } catch {
      db.close()
      resolve(false)
    }
  })
}

/** Load a previously saved intake draft (files + assessment type). */
export async function loadIntakeDraft(): Promise<IntakeDraft | null> {
  const db = await openIntakeDb()
  if (!db) return null
  return new Promise<IntakeDraft | null>((resolve) => {
    try {
      const tx = db.transaction(INTAKE_DB_STORE, 'readonly')
      const request = tx.objectStore(INTAKE_DB_STORE).get(INTAKE_DB_KEY)
      request.onsuccess = () => {
        const value = request.result as IntakeDraft | undefined
        db.close()
        if (value && Array.isArray(value.files) && value.files.length) {
          resolve(value)
        } else {
          resolve(null)
        }
      }
      request.onerror = () => { db.close(); resolve(null) }
    } catch {
      db.close()
      resolve(null)
    }
  })
}

/** Remove the intake draft once the assessment has been created. */
export async function clearIntakeDraft(): Promise<void> {
  const db = await openIntakeDb()
  if (!db) return
  return new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(INTAKE_DB_STORE, 'readwrite')
      tx.objectStore(INTAKE_DB_STORE).delete(INTAKE_DB_KEY)
      tx.oncomplete = () => { db.close(); resolve() }
      tx.onerror = () => { db.close(); resolve() }
      tx.onabort = () => { db.close(); resolve() }
    } catch {
      db.close()
      resolve()
    }
  })
}
