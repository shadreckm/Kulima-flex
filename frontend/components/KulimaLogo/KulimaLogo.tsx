'use client'

/**
 * KulimaLogo — canonical brand logo component.
 *
 * Master asset: /public/kulima-logo.png
 * Natural dimensions: ~660×580 px, aspect ratio ≈ 1.138 : 1 (w:h)
 * Background: light cream (#f1ece1) — not transparent.
 *
 * On dark backgrounds (sidebar): the logo is mounted inside a white
 * rounded pill so the cream background blends correctly and the logo
 * remains legible.
 *
 * On light backgrounds (header, reports, dashboard): no container —
 * the cream background merges with the white surface naturally.
 *
 * Variants and their default heights:
 *   sidebar  — 36 px  (dark bg pill)
 *   header   — 30 px  (light bg, top bar)
 *   report   — 44 px  (white card / report page)
 *   hero     — 60 px  (dashboard landing hero)
 */

import React from 'react'
import Image from 'next/image'

export type LogoVariant = 'sidebar' | 'header' | 'report' | 'hero'

type Spec = { height: number; darkBg: boolean }

const SPEC: Record<LogoVariant, Spec> = {
  sidebar: { height: 36, darkBg: true },
  header:  { height: 30, darkBg: false },
  report:  { height: 44, darkBg: false },
  hero:    { height: 60, darkBg: false },
}

/* Logo natural ratio: width / height */
const LOGO_RATIO = 660 / 580 // ≈ 1.138

type KulimaLogoProps = {
  variant?: LogoVariant
  /** Override height (px). Width computed from natural ratio. */
  height?: number
  className?: string
}

export default function KulimaLogo({
  variant = 'header',
  height: heightOverride,
  className = '',
}: KulimaLogoProps) {
  const { height: defaultH, darkBg } = SPEC[variant]
  const h = heightOverride ?? defaultH
  const w = Math.round(h * LOGO_RATIO)

  const img = (
    <div className="relative flex-shrink-0" style={{ height: h, width: w }}>
      <Image
        src="/kulima-logo.png"
        alt="Kulima Africa"
        fill
        sizes={`${w}px`}
        className="object-contain"
        priority
      />
    </div>
  )

  if (darkBg) {
    /* Wrap in a white pill — makes cream logo background invisible on dark sidebar */
    return (
      <div
        className={`flex-shrink-0 rounded-lg bg-white px-2 py-1 flex items-center justify-center ${className}`}
        style={{ lineHeight: 0 }}
      >
        {img}
      </div>
    )
  }

  return (
    <div className={`flex-shrink-0 ${className}`}>
      {img}
    </div>
  )
}
