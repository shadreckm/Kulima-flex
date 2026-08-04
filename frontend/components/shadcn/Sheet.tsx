import * as React from "react"

export interface SheetProps extends React.HTMLAttributes<HTMLDivElement> {
  open?: boolean
}

export function Sheet({ className = "", open = true, ...props }: SheetProps) {
  if (!open) return null
  return (
    <div
      className={`fixed inset-0 z-40 flex items-center justify-center bg-black/30 ${className}`.trim()}
      {...props}
    />
  )
}
