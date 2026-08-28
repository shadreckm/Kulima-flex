/**
 * Entity-based evaluation intake types.
 * Kulima OS evaluates any organisation type, not just startups.
 */

export type EntityType =
  | 'startup'
  | 'ngo'
  | 'development_program'
  | 'accelerator'
  | 'government_program'

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
    type: 'development_program',
    label: 'Development Program',
    description: 'Development finance program under DFI or bilateral-agency evaluation.',
    fields: {
      primary:   { key: 'entityName',    label: 'Organisation',  placeholder: 'e.g. USAID East Africa' },
      secondary: { key: 'programName',   label: 'Program Name',  placeholder: 'e.g. Resilient Food Systems' },
    },
  },
  {
    type: 'accelerator',
    label: 'Accelerator',
    description: 'Accelerator or incubator programme under portfolio or impact review.',
    fields: {
      primary:   { key: 'entityName',    label: 'Accelerator Name', placeholder: 'e.g. MEST Africa' },
      secondary: { key: 'programName',   label: 'Program / Cohort', placeholder: 'e.g. Cohort 12 — AgriTech' },
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
]

export function getEntityConfig(type: EntityType): EntityConfig {
  return ENTITY_CONFIGS.find(c => c.type === type) ?? ENTITY_CONFIGS[0]
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
