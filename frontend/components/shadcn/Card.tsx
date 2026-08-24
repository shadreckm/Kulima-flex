import * as React from "react"

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Card({ className = "", ...props }: CardProps) {
  return (
    <div
      className={`rounded-[12px] border border-[#DDE6F0] bg-white shadow-saas ${className}`.trim()}
      {...props}
    />
  )
}

export function CardHeader({ className = "", ...props }: CardProps) {
  return (
    <div
      className={`px-5 py-4 border-b border-[#DDE6F0] flex items-center justify-between ${className}`.trim()}
      {...props}
    />
  )
}

export function CardTitle({ className = "", ...props }: CardProps) {
  return (
    <h3
      className={`text-sm font-bold text-slate-900 leading-tight ${className}`.trim()}
      {...props}
    />
  )
}

export function CardContent({ className = "", ...props }: CardProps) {
  return (
    <div
      className={`px-5 py-4 ${className}`.trim()}
      {...props}
    />
  )
}
