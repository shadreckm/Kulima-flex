/**
 * Entity-based evaluation intake types.
 * Kulima OS evaluates any organisation type, not just startups.
 *
 * The five canonical assessment types collected by the single intake engine
 * (landing page) are: Startup, NGO, Government Program, Development Program,
 * Tourism SME. `accelerator` is retained as a legacy alias so contexts stored
 * before Tourism SME existed keep loading.
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
}

export const ENTITY_CONFIGS: EntityConfig[] = [
  {
    type: 'startup',
    label: 'Startup',
    description: 'Early-stage to growth-stage venture seeking investment or evaluation.',
    fields: {
      primary:   { key: 'founderName',   label: 'Founder Name',  placeholder: 'e.g. Amara Diallo' },
      secondary: { key: 'entityName',    label: 'Startup Name',  placeholder: 'e.g. AgroTech East Africa' },
    },
  },
  {
    type: 'ngo',
    label: 'NGO',
    description: 'Non-governmental organisation under programme review or donor evaluation.',
    fields: {
      primary:   { key: 'entityName',    label: 'NGO Name',      placeholder: 'e.g. AfriCare Malawi' },
      secondary: { key: 'programName',   label: 'Program Name',  placeholder: 'e.g. Food Security Initiative' },
    },
  },
  {
    type: 'government_program',
    label: 'Government Program',
    description: 'Government agency programme under SPARC, parliamentary, or donor review.',
    fields: {
      primary:   { key: 'entityName',    label: 'Agency',        placeholder: 'e.g. Ministry of Agriculture, Tanzania' },
      secondary: { key: 'programName',   label: 'Program Name',  placeholder: 'e.g. National Irrigation Strategy' },
    },
  },
  {
    type: 'development_program',
    label: 'Development Program',
    description: 'Development finance program under DFI or bilateral-agency evaluation.',
    fields: {
      primary:   { key: 'entityName',    label: 'Organisation',  placeholder: 'e.g. USAID East Africa' },
      secondary: { key: 'programName',   label: 'Program Name',  placeholder: 'e.g. Resilient Food Systems' },
    },
  },
  {
    type: 'tourism_sme',
    label: 'Tourism SME',
    description: 'Tourism, hospitality, or destination business under impact and viability review.',
    fields: {
      primary:   { key: 'entityName',    label: 'Business Name', placeholder: 'e.g. SolarHarvest Lodge' },
      secondary: { key: 'programName',   label: 'Owner / Lead',  placeholder: 'e.g. Grace Banda' },
    },
  },
  {
    type: 'accelerator',
    label: 'Accelerator',
    legacy: true,
    description: 'Accelerator or incubator programme under portfolio or impact review.',
    fields: {
      primary:   { key: 'entityName',    label: 'Accelerator Name', placeholder: 'e.g. MEST Africa' },
      secondary: { key: 'programName',   label: 'Program / Cohort', placeholder: 'e.g. Cohort 12 — AgriTech' },
    },
  },
]

/** The five canonical assessment types shown in the landing-page intake. */
export const INTAKE_ENTITY_TYPES: EntityType[] = [
  'startup',
  'ngo',
  'government_program',
  'development_program',
  'tourism_sme',
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
