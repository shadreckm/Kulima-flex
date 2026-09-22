'use client'

import React from 'react'

type PageStatusProps = {
  whatHappened: string
  whatIsHappening: string
  whatToDoNext: string
}

export default function PageStatus({ whatHappened, whatIsHappening, whatToDoNext }: PageStatusProps) {
  return (
    <div className="rounded-lg border border-[#DDE6F0] bg-[#F8FAFC] p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 text-lg">📋</div>
        <div className="flex-1 space-y-3">
          <div>
            <div className="text-xs font-bold text-[#667085] uppercase tracking-wide">What happened</div>
            <div className="mt-1 text-sm text-[#344054]">{whatHappened}</div>
          </div>
          <div>
            <div className="text-xs font-bold text-[#667085] uppercase tracking-wide">What's happening now</div>
            <div className="mt-1 text-sm text-[#344054]">{whatIsHappening}</div>
          </div>
          <div>
            <div className="text-xs font-bold text-[#667085] uppercase tracking-wide">What to do next</div>
            <div className="mt-1 text-sm text-[#0B5D3B] font-semibold">{whatToDoNext}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
