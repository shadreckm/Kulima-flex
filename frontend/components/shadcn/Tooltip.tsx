import * as React from "react"

export interface TooltipProps {
  content: React.ReactNode
  children: React.ReactNode
}

export function Tooltip({ content, children }: TooltipProps) {
  // Simple non-interactive tooltip placeholder
  return (
    <span className="relative inline-block group">
      {children}
      <span className="pointer-events-none absolute z-50 bottom-full left-1/2 mb-1 -translate-x-1/2 rounded bg-black px-2 py-1 text-[10px] font-medium text-white opacity-0 group-hover:opacity-100 transition-opacity">
        {content}
      </span>
    </span>
  )
}
