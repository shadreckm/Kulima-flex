/**
 * Lightweight localStorage persistence for the user's selected use case.
 *
 * This lets the homepage selection survive navigation so that Ask IC,
 * Signals, and Evidence workspaces automatically know the context
 * without prompting the user again.
 */

export type UseCaseSelection = {
  useCase: 'startup' | 'ngo' | 'government_program' | 'development_program' | 'tourism_sme' | 'accelerator'
  /** Human-readable label shown in context banners */
  label: string
  /** ISO timestamp when the user made the selection */
  selectedAt: string
}

const STORAGE_KEY = 'kulima_use_case'

export const USE_CASE_LABELS: Record<UseCaseSelection['useCase'], string> = {
  startup: 'Startup / Investor',
  ngo: 'NGO / Donor',
  government_program: 'Government Program',
  development_program: 'Development Program',
  tourism_sme: 'Tourism SME',
  accelerator: 'Accelerator / Incubator',
}

/** Map homepage simple IDs to entity-types used by the intake form */
export const HOME_TO_ENTITY: Record<string, UseCaseSelection['useCase']> = {
  startup: 'startup',
  ngo: 'ngo',
  government: 'government_program',
  development: 'development_program',
  tourism: 'tourism_sme',
}

export function saveUseCase(useCase: UseCaseSelection['useCase']): void {
  if (typeof window === 'undefined') return
  const selection: UseCaseSelection = {
    useCase,
    label: USE_CASE_LABELS[useCase] ?? useCase,
    selectedAt: new Date().toISOString(),
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selection))
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(selection))
  } catch {}
  window.dispatchEvent(new CustomEvent('kulima-use-case-changed', { detail: selection }))
}

export function loadUseCase(): UseCaseSelection | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as UseCaseSelection
  } catch {
    return null
  }
}

export function clearUseCase(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(STORAGE_KEY)
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {}
}

/** Returns a short context string for use in Ask IC system prompt injection */
export function useCaseContextHint(selection: UseCaseSelection | null): string {
  if (!selection) return ''
  const hints: Record<UseCaseSelection['useCase'], string> = {
    startup: 'The user is evaluating a startup or venture for investment. Focus on commercial traction, founder quality, market size, and financial evidence.',
    ngo: 'The user is reviewing an NGO or development programme for donor funding. Focus on beneficiary evidence, outcome indicators, M&E quality, and budget integrity.',
    government_program: 'The user is assessing a government programme for parliamentary or donor review. Focus on policy alignment, implementation evidence, budget utilisation, and outcome data.',
    development_program: 'The user is evaluating a development finance programme. Focus on disbursement evidence, impact metrics, partner accountability, and learning loops.',
    tourism_sme: 'The user is reviewing a tourism or hospitality SME. Focus on destination evidence, tourism contribution, cultural preservation, community impact, and climate resilience.',
    accelerator: 'The user is reviewing an accelerator or incubator portfolio. Focus on cohort outcomes, mentorship quality, graduation rates, and venture success metrics.',
  }
  return hints[selection.useCase] ?? ''
}
