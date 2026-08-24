'use client'

import React from 'react'

export interface TrustGaugeProps {
  score: number | null | undefined
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  grade?: string | null
  confidencePercent?: number | null
}

export default function TrustGauge({
  score,
  size = 'md',
  showLabel = true,
  grade,
  confidencePercent,
}: TrustGaugeProps) {
  const numericScore = typeof score === 'number' && !isNaN(score) ? Math.max(0, Math.min(100, Math.round(score))) : null

  let tier: 'green' | 'amber' | 'red' | 'unknown' = 'unknown'
  let strokeColor = '#94A3B8'
  let badgeBg = '#F1F5F9'
  let badgeText = '#475569'
  let statusText = 'Pending Audit'

  if (numericScore !== null) {
    if (numericScore >= 80) {
      tier = 'green'
      strokeColor = '#12B76A'
      badgeBg = '#ECFDF3'
      badgeText = '#027A48'
      statusText = 'Verified High Trust'
    } else if (numericScore >= 60) {
      tier = 'amber'
      strokeColor = '#F79009'
      badgeBg = '#FFFAEB'
      badgeText = '#B54708'
      statusText = 'Observational Trust'
    } else {
      tier = 'red'
      strokeColor = '#F04438'
      badgeBg = '#FEF3F2'
      badgeText = '#B42318'
      statusText = 'High Risk / Low Trust'
    }
  }

  const dimensions = size === 'sm' ? 44 : size === 'lg' ? 104 : 72
  const strokeWidth = size === 'sm' ? 4.5 : size === 'lg' ? 8 : 6
  const radius = (dimensions - strokeWidth * 2) / 2
  const circumference = 2 * Math.PI * radius
  const arcLength = circumference * 0.75
  const strokeDashoffset = numericScore !== null
    ? arcLength - (arcLength * numericScore) / 100
    : arcLength

  return (
    <div className="flex items-center gap-3">
      <div className="relative flex items-center justify-center flex-shrink-0" style={{ width: dimensions, height: dimensions }}>
        <svg
          className="transform -rotate-135"
          width={dimensions}
          height={dimensions}
          viewBox={`0 0 ${dimensions} ${dimensions}`}
        >
          {/* Background Arc */}
          <circle
            cx={dimensions / 2}
            cy={dimensions / 2}
            r={radius}
            stroke="#E2E8F0"
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
            fill="none"
          />
          {/* Progress Arc */}
          <circle
            cx={dimensions / 2}
            cy={dimensions / 2}
            r={radius}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="none"
            style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(0.16, 1, 0.3, 1)' }}
          />
        </svg>

        {/* Center Display */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span
            className={`font-black tracking-tight leading-none ${
              size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-2xl' : 'text-base'
            }`}
            style={{ color: numericScore !== null ? strokeColor : '#64748B' }}
          >
            {numericScore !== null ? numericScore : '—'}
          </span>
          {size !== 'sm' ? (
            <span className="text-[9px] font-bold text-slate-400 uppercase mt-0.5 tracking-wider">
              / 100
            </span>
          ) : null}
        </div>
      </div>

      {showLabel ? (
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: strokeColor }} />
            <span className="text-xs font-bold text-slate-900 tracking-tight truncate">
              {statusText}
            </span>
          </div>

          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            <span
              className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider"
              style={{ backgroundColor: badgeBg, color: badgeText }}
            >
              {tier === 'green' ? 'High Confidence' : tier === 'amber' ? 'Moderate Trust' : tier === 'red' ? 'Critical Watch' : 'Unscored'}
            </span>
            {grade ? (
              <span className="px-1.5 py-0.5 rounded bg-slate-900 text-white text-[10px] font-bold tracking-wider">
                GRADE {grade}
              </span>
            ) : null}
            {confidencePercent != null ? (
              <span className="text-[11px] text-slate-500 font-medium">
                {confidencePercent}% conf
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
