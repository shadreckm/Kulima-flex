/**
 * Entity-based evaluation intake types.
 * Kulima FLEX evaluates any organisation type, not just startups.
 *
 * The canonical assessment types collected by the single intake engine
 * (landing page) are, NGO-first: NGO, Development Program (primary), then
 * Government Program, Tourism SME and Startup (grouped behind "Advanced
 * Assessment Types"). `accelerator` is retained as a legacy alias so contexts
 * stored before Tourism SME existed keep loading.
 */

export type EntityType =
  | 'startup'
  | 'ngo'
  | 'government_program'
  | 'development_program'
  | 'tourism_sme'
  | 'accelerator' // legacy alias (kept for backward compatibility)

export type EntityConfig = {
  type: EntityType
  label: string
  /** The two fields to collect for this entity type */
  fields: {
    primary: { key: string; label: string; placeholder: string }
    secondary: { key: string; label: string; placeholder: string }
  }
  /** Short description shown below the entity-type selector */
  description: string
  /** True for legacy aliases that must not appear in the intake selector */
  legacy?: boolean
  /** Guidance on what documents to upload for this entity type */
  uploadGuidance: string
  /** Label for the primary score (e.g., Investment Readiness, Programme Readiness) */
  scoreLabel: string
  /** The decision this workflow supports — shown at intake so the user knows
   *  they are in the right workflow before anything runs. */
  decisionQuestion: string
  /** Canonical title of the review this assessment produces (mirrors kulima/export.py). */
  reportTitle: string
}

// PRIMARY EXPERIENCE: NGO and Development Programme configurations prioritized for V1
export const ENTITY_CONFIGS: EntityConfig[] = [
  {
    type: 'ngo',
    label: 'NGO',
    description: 'Non-governmental organisation under programme review or donor evaluation.',
    fields: {
      primary:   { key: 'entityName',    label: 'NGO Name',      placeholder: 'e.g. AfriCare Malawi' },
      secondary: { key: 'programName',   label: 'Programme Name',  placeholder: 'e.g. Food Security Initiative' },
    },
    uploadGuidance: 'Upload monitoring reports, impact assessments, donor reports, financial statements, annual reports',
    scoreLabel: 'Programme Readiness',
    decisionQuestion: 'Can this organisation deliver its programme, and prove its impact?',
    reportTitle: 'Institutional Capacity Review',
  },
  {
    type: 'development_program',
    label: 'Development Programme',
    description: 'Development finance programme under DFI or bilateral-agency evaluation.',
    fields: {
      primary:   { key: 'entityName',    label: 'Organisation',  placeholder: 'e.g. USAID East Africa' },
      secondary: { key: 'programName',   label: 'Programme Name',  placeholder: 'e.g. Resilient Food Systems' },
    },
    uploadGuidance: 'Upload programme frameworks, beneficiary reports, monitoring data, financial statements, theory of change',
    scoreLabel: 'Programme Performance',
    decisionQuestion: 'Is the programme performing against its theory of change?',
    reportTitle: 'Programme Performance Review',
  },
  {
    type: 'government_program',
    label: 'Government Programme',
    description: 'Government agency programme under SPARC, parliamentary, or donor review.',
    fields: {
      primary:   { key: 'entityName',    label: 'Agency',        placeholder: 'e.g. Ministry of Agriculture, Tanzania' },
      secondary: { key: 'programName',   label: 'Programme Name',  placeholder: 'e.g. National Irrigation Strategy' },
    },
    uploadGuidance: 'Upload programme proposals, budget allocations, implementation reports, impact evaluations, policy documents',
    scoreLabel: 'Programme Performance',
    decisionQuestion: 'Are public funds being implemented and governed as planned?',
    reportTitle: 'Governance Review',
  },
  {
    type: 'tourism_sme',
    label: 'Tourism SME',
    description: 'Tourism, hospitality, or destination business under impact and viability review.',
    fields: {
      primary:   { key: 'entityName',    label: 'Business Name', placeholder: 'e.g. Lakeshore Eco Lodge' },
      secondary: { key: 'programName',   label: 'Owner / Lead',  placeholder: 'e.g. Grace Banda' },
    },
    uploadGuidance: 'Upload visitor statistics, sustainability reports, destination impact data, business licenses, financial statements',
    scoreLabel: 'Tourism Resilience',
    decisionQuestion: 'Is this tourism enterprise resilient and ready for investment?',
    reportTitle: 'Tourism Resilience Report',
  },
  {
    type: 'startup',
    label: 'Startup',
    description: 'Early-stage to growth-stage venture seeking investment or evaluation.',
    fields: {
      primary:   { key: 'founderName',   label: 'Founder Name',  placeholder: 'e.g. Amara Diallo' },
      secondary: { key: 'entityName',    label: 'Startup Name',  placeholder: 'e.g. AgroTech East Africa' },
    },
    uploadGuidance: 'Upload pitch deck, financial projections, market analysis, team bios, product roadmap',
    scoreLabel: 'Investment Readiness',
    decisionQuestion: 'Is this venture ready for an investment committee decision?',
    reportTitle: 'Investment Committee Report',
  },
  {
    type: 'accelerator',
    label: 'Accelerator',
    legacy: true,
    description: 'Accelerator or incubator programme under portfolio or impact review.',
    fields: {
      primary:   { key: 'entityName',    label: 'Accelerator Name', placeholder: 'e.g. MEST Africa' },
      secondary: { key: 'programName',   label: 'Programme / Cohort', placeholder: 'e.g. Cohort 12 — AgriTech' },
    },
    uploadGuidance: 'Upload cohort reports, startup pitch decks, programme metrics, portfolio summaries, impact reports',
    scoreLabel: 'Portfolio Impact',
    decisionQuestion: 'How is the portfolio and cohort performing?',
    // This profile has no report title of its own in the backend map, so it
    // inherits the institutional review — never the startup template.
    reportTitle: 'Institutional Capacity Review',
  },
]

/** The canonical assessment types shown in the landing-page intake. */
// PRIMARY EXPERIENCE: NGOs and Development Programs are the primary customer
// segment for V1. Secondary types stay fully supported but are grouped behind
// an "Advanced Assessment Types" disclosure so the default UX path is NGO-first.
export const PRIMARY_INTAKE_ENTITY_TYPES: EntityType[] = [
  'ngo',                    // Primary customer — first
  'development_program',    // Primary customer — second
]

export const ADVANCED_INTAKE_ENTITY_TYPES: EntityType[] = [
  'government_program',     // Secondary customer
  'tourism_sme',            // Secondary customer
  'startup',                // Secondary customer
]

export const INTAKE_ENTITY_TYPES: EntityType[] = [
  ...PRIMARY_INTAKE_ENTITY_TYPES,
  ...ADVANCED_INTAKE_ENTITY_TYPES,
]

export function getEntityConfig(type: EntityType): EntityConfig {
  return ENTITY_CONFIGS.find(c => c.type === type) ?? ENTITY_CONFIGS[0]
}

/**
 * Maps an entity type to the backend AssessmentType value used by the
 * shared Assessment Context API (/api/v1/assessments).
 */
export function entityToAssessmentType(entityType: EntityType): string {
  return entityType
}

/**
 * Derives the two legacy fields expected by the backend createRun API.
 * The API still accepts `founder` + `startup`; we map entity fields into those.
 */
export function entityToRunParams(
  entityType: EntityType,
  primaryValue: string,
  secondaryValue: string,
): { founder: string; startup: string; entityType: EntityType; entityMeta: Record<string, string> } {
  const cfg = getEntityConfig(entityType)

  let founder: string
  let startup: string

  if (entityType === 'startup') {
    founder = primaryValue || 'Unknown founder'
    startup = secondaryValue || 'Unnamed startup'
  } else {
    // For non-startup entities, the "entity name" maps to startup and "program" to founder
    // This keeps the backend signature unchanged while surfacing the right display name
    founder = primaryValue || 'Unknown entity'
    startup = secondaryValue ? `${primaryValue} — ${secondaryValue}` : primaryValue || 'Unnamed entity'
  }

  return {
    founder,
    startup,
    entityType,
    entityMeta: {
      [cfg.fields.primary.key]: primaryValue,
      [cfg.fields.secondary.key]: secondaryValue,
    },
  }
}

/**
 * Returns a human-readable display label for the run context panel.
 */
export function entityDisplayLabel(entityType: EntityType | undefined, primaryValue: string, secondaryValue: string): string {
  if (!entityType || entityType === 'startup') return primaryValue || secondaryValue || 'Unnamed venture'
  const cfg = getEntityConfig(entityType)
  if (secondaryValue) return `${primaryValue} — ${secondaryValue}`
  return primaryValue || cfg.label
}
