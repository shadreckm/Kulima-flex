'use client'

import React from 'react'
import { EntityType } from '../../lib/entity-types'

type UploadGuidanceProps = {
  entityType: EntityType
}

export default function UploadGuidance({ entityType }: UploadGuidanceProps) {
  const guidance: Record<EntityType, string> = {
    startup: 'Upload pitch deck, financial projections, market analysis, team bios, product roadmap',
    ngo: 'Upload monitoring reports, impact assessments, donor reports, financial statements, annual reports',
    government_program: 'Upload program proposals, budget allocations, implementation reports, impact evaluations, policy documents',
    development_program: 'Upload program frameworks, beneficiary reports, monitoring data, financial statements, theory of change',
    tourism_sme: 'Upload visitor statistics, sustainability reports, destination impact data, business licenses, financial statements',
    accelerator: 'Upload cohort reports, startup pitch decks, program metrics, portfolio summaries, impact reports',
  }

  return (
    <div className="mt-2 text-xs text-[#667085] italic">
      {guidance[entityType]}
    </div>
  )
}
