'use client'

import React, { useState } from 'react'

type ExplanationCardProps = {
  title: string
  explanation: string
  children?: React.ReactNode
}

export default function ExplanationCard({ title, explanation, children }: ExplanationCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-lg border border-[#DDE6F0] bg-[#F8FAFC] p-4">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-[#0B5D3B]">ℹ️</span>
          <span className="text-sm font-semibold text-[#344054]">{title}</span>
        </div>
        <span className="text-xs text-[#667085]">{expanded ? '−' : '+'}</span>
      </button>
      {expanded && (
        <div className="mt-3 text-xs leading-5 text-[#667085]">
          {explanation}
          {children}
        </div>
      )}
    </div>
  )
}
