import * as React from "react"

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Card({ className = "", ...props }: CardProps) {
  return (
    <div
      className={`rounded-md border border-gray-200 bg-white shadow-sm ${className}`.trim()}
      {...props}
    />
  )
}

export function CardHeader({ className = "", ...props }: CardProps) {
  return (
    <div
      className={`px-4 py-3 border-b border-gray-200 flex items-center justify-between ${className}`.trim()}
      {...props}
    />
  )
}

export function CardTitle({ className = "", ...props }: CardProps) {
  return (
    <h3
      className={`text-sm font-semibold leading-tight ${className}`.trim()}
      {...props}
    />
  )
}

export function CardContent({ className = "", ...props }: CardProps) {
  return (
    <div
      className={`px-4 py-3 ${className}`.trim()}
      {...props}
    />
  )
}
