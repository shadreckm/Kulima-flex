import * as React from "react"

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {}

export function Badge({ className = "", ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border border-gray-200 bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700 ${className}`.trim()}
      {...props}
    />
  )
}
