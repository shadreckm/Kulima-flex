'use client'

import React from 'react'
import type { CurrentRunState } from '../../lib/current-run'

type Props = {
  run: CurrentRunState
  onClear?: () => void
  compact?: boolean
}

export default function CurrentRunBanner({ run, onClear, compact = false }: Props) {
  return (
    <section className={`bg-white rounded shadow border border-gray-100 ${compact ? 'p-3' : 'p-4'}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500">Current Run</div>
          <div className="text-lg font-semibold text-gray-900 mt-1">
            {run.startupName || 'Selected run'}
          </div>
          {run.founderName ? (
            <div className="text-sm text-gray-600">{run.founderName}</div>
          ) : null}
        </div>
        {onClear ? (
          <button
            type="button"
            onClick={onClear}
            className="text-xs text-gray-500 hover:text-gray-800 underline"
          >
            Change run
          </button>
        ) : null}
      </div>
      <div className={`mt-3 grid gap-3 ${compact ? 'grid-cols-2 md:grid-cols-4' : 'grid-cols-2 md:grid-cols-4'} text-sm`}>
        <div>
          <div className="text-xs text-gray-500">Recommendation</div>
          <div className="font-semibold text-gray-900">{run.recommendation || '—'}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Trust Score</div>
          <div className="font-semibold text-gray-900">
            {run.trustScore != null ? `${run.trustScore}` : '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Status</div>
          <div className="font-semibold text-gray-900 capitalize">{run.status || 'completed'}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Run ID</div>
          <div className="font-medium text-gray-700 break-all text-xs">{run.runId}</div>
        </div>
      </div>
    </section>
  )
}
