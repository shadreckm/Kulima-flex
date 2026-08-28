'use client'

import React, { useState } from 'react'
import {
  ENTITY_CONFIGS,
  type EntityType,
  getEntityConfig,
  entityToRunParams,
} from '../../lib/entity-types'

type Props = {
  /** Called with derived { founder, startup, entityType, entityMeta } when form is submitted */
  onSubmit: (params: ReturnType<typeof entityToRunParams>) => Promise<void>
  /** Optional error message to display under the form */
  error?: string | null
  /** Label for the submit button */
  submitLabel?: string
  /** Title shown at the top of the card */
  title?: string
  /** Subtitle shown below the title */
  subtitle?: string
}

export default function EntityIntakeForm({
  onSubmit,
  error,
  submitLabel = 'Start Evaluation',
  title = 'Start Evaluation',
  subtitle = 'Select the entity type, then enter the required fields.',
}: Props) {
  const [entityType, setEntityType] = useState<EntityType>('startup')
  const [primaryValue, setPrimaryValue] = useState('')
  const [secondaryValue, setSecondaryValue] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const cfg = getEntityConfig(entityType)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!primaryValue.trim()) return
    setSubmitting(true)
    try {
      const params = entityToRunParams(entityType, primaryValue.trim(), secondaryValue.trim())
      await onSubmit(params)
    } finally {
      setSubmitting(false)
    }
  }

  function handleEntityTypeChange(type: EntityType) {
    setEntityType(type)
    setPrimaryValue('')
    setSecondaryValue('')
  }

  return (
    <div className="p-6 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
      {/* Header */}
      <div className="pb-4 mb-4 border-b border-[#DDE6F0]">
        <h3 className="text-base font-extrabold text-slate-900">{title}</h3>
        <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Entity Type Selector */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
            Entity Type
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {ENTITY_CONFIGS.map((c) => (
              <button
                key={c.type}
                type="button"
                onClick={() => handleEntityTypeChange(c.type)}
                className={`px-3 py-2.5 rounded-lg border text-xs font-bold transition text-left leading-tight ${
                  entityType === c.type
                    ? 'bg-[#061C14] border-[#0B5D3B] text-white shadow-sm'
                    : 'border-[#DDE6F0] text-slate-700 hover:bg-[#F5F8FC] hover:border-[#0B5D3B]'
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">{cfg.description}</p>
        </div>

        {/* Primary Field */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
            {cfg.fields.primary.label}
            <span className="text-red-500 ml-0.5">*</span>
          </label>
          <input
            value={primaryValue}
            onChange={(e) => setPrimaryValue(e.target.value)}
            placeholder={cfg.fields.primary.placeholder}
            required
            className="w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 focus:outline-none focus:border-[#0B5D3B] focus:bg-white transition"
          />
        </div>

        {/* Secondary Field */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
            {cfg.fields.secondary.label}
            <span className="text-slate-400 ml-1 font-normal normal-case tracking-normal">(optional)</span>
          </label>
          <input
            value={secondaryValue}
            onChange={(e) => setSecondaryValue(e.target.value)}
            placeholder={cfg.fields.secondary.placeholder}
            className="w-full p-2.5 border border-[#DDE6F0] rounded-lg bg-[#F5F8FC] text-sm text-slate-900 focus:outline-none focus:border-[#0B5D3B] focus:bg-white transition"
          />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-1">
          <button
            type="submit"
            disabled={submitting || !primaryValue.trim()}
            className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white text-xs font-extrabold uppercase tracking-wider hover:bg-[#08482E] transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Creating evaluation…' : submitLabel}
          </button>
          <button
            type="button"
            onClick={() => { setPrimaryValue(''); setSecondaryValue('') }}
            className="px-4 py-2.5 rounded-lg border border-[#DDE6F0] text-xs font-semibold text-slate-600 hover:bg-[#F5F8FC] transition"
          >
            Clear
          </button>
        </div>

        {error ? (
          <div className="p-3 bg-red-50 text-red-700 rounded-lg border border-red-200 text-xs font-medium">
            {error}
          </div>
        ) : null}
      </form>
    </div>
  )
}
