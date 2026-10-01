import React from 'react'
import { EntityType } from '../../lib/entity-types'
import { getEntityConfig } from '../../lib/entity-types'

type WorkspaceHeaderProps = {
  assessmentName?: string
  assessmentType?: EntityType
  organization?: string
  founder?: string
  status?: string
  documentCount?: number
  progress?: number
}

const ENTITY_LABELS: Record<EntityType, string> = {
  startup: 'Startup',
  ngo: 'NGO',
  development_program: 'Dev. Program',
  accelerator: 'Accelerator',
  government_program: 'Gov. Program',
  tourism_sme: 'Tourism SME',
}

export default function WorkspaceHeader({
  assessmentName,
  assessmentType,
  organization,
  founder,
  status,
  documentCount,
  progress,
}: WorkspaceHeaderProps) {
  const entityConfig = assessmentType ? getEntityConfig(assessmentType) : null
  const scoreLabel = entityConfig?.scoreLabel || 'Readiness'

  return (
    <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {assessmentType && assessmentType !== 'startup' && (
              <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">
                {ENTITY_LABELS[assessmentType] || assessmentType}
              </span>
            )}
            <h1 className="text-lg font-black text-slate-900 truncate">
              {assessmentName || organization || 'Active Assessment'}
            </h1>
          </div>
          
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 mt-1">
            {organization && (
              <div>
                <span className="font-semibold">Organization:</span> {organization}
              </div>
            )}
            {founder && (
              <div>
                <span className="font-semibold">Lead:</span> {founder}
              </div>
            )}
            {documentCount !== undefined && (
              <div>
                <span className="font-semibold">Documents:</span> {documentCount}
              </div>
            )}
            {status && (
              <div>
                <span className="font-semibold">Status:</span> <span className="capitalize">{status}</span>
              </div>
            )}
          </div>
        </div>

        {progress !== undefined && (
          <div className="ml-4 text-right min-w-[120px]">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Progress
            </div>
            <div className="text-2xl font-black text-[#0B5D3B]">
              {Math.round(progress)}%
            </div>
          </div>
        )}
      </div>

      {progress !== undefined && (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full bg-[#0B5D3B] transition-all duration-500 rounded-full"
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}
    </div>
  )
}
