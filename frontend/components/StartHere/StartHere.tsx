'use client'

/**
 * StartHere — the first-time user onboarding component.
 *
 * Renders when:
 * - The user is authenticated
 * - They have zero assessments
 *
 * Shows three states:
 * 1. EMPTY      — no upload yet (primary state for new users)
 * 2. HAS_DRAFT  — files staged on the landing page but not yet submitted
 * 3. COMPLETE   — assessment finished, redirecting to workspace
 *
 * Design goals:
 * - A user who has never seen the product must know what to do in ≤5 seconds
 * - The pipeline (Upload → Evidence → Signals → Decision → Report → Outcome)
 *   is visible but never presented as navigation yet — they are steps, not menus
 * - One CTA. No options. No confusion.
 */

import Link from 'next/link'
import React from 'react'

// The six steps shown as a linear strip. Kept here rather than imported from
// a shared config so this component renders exactly what a first-time NGO user
// needs to see — the pipeline described in their language.
const STEPS: Array<{ icon: string; label: string; detail: string }> = [
  { icon: '📄', label: 'Upload',   detail: 'Annual report, M&E data, budget, proposal' },
  { icon: '🧱', label: 'Evidence', detail: 'Every claim extracted and sourced' },
  { icon: '⚡', label: 'Signals',  detail: 'Risks, opportunities, programme gaps' },
  { icon: '🎯', label: 'Decision', detail: 'Recommendation in your institution\'s language' },
  { icon: '📑', label: 'Report',   detail: 'Board memo, donor report or one-pager' },
  { icon: '📊', label: 'Outcome',  detail: '30-day check: did it work?' },
]

type Props = {
  /** Pass a list of all known assessments — if non-empty, this component should not render. */
  assessmentCount: number
  loading?: boolean
}

export default function StartHere({ assessmentCount, loading = false }: Props) {
  // This component only renders when there are no assessments.
  // Caller is responsible for guarding, but we add a safety check.
  if (assessmentCount > 0 || loading) return null

  return (
    <section
      aria-label="Get started"
      className="flex flex-col gap-6"
    >
      {/* ── HERO CARD ─────────────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-[16px] border border-[#A6F4C5] bg-gradient-to-br from-[#F0FBF4] to-white p-6 md:p-8 shadow-saas">
        {/* Decorative corner glow */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-[#12B76A]/8"
        />

        <div className="relative">
          {/* Step label */}
          <div className="inline-flex items-center gap-2 rounded-full border border-[#A6F4C5] bg-[#ECFDF3] px-3 py-1 text-[11px] font-black uppercase tracking-widest text-[#027A48]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#12B76A]" />
            Start here
          </div>

          {/* Headline */}
          <h2 className="mt-4 text-2xl font-black leading-tight tracking-tight text-[#061C14] md:text-3xl">
            Upload your first document.
          </h2>
          <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">
            Drop in an annual report, programme evaluation, M&amp;E data file, or budget.
            Kulima FLEX reads it, structures the evidence, surfaces risks and opportunities,
            and gives you a recommendation your board can defend — with every claim tied
            to its source.
          </p>

          {/* Primary CTA */}
          <Link
            href="/"
            className="mt-6 inline-flex items-center gap-2.5 rounded-xl bg-[#0B5D3B] px-6 py-3.5 text-sm font-extrabold text-white shadow-sm hover:bg-[#08482E] transition"
          >
            <span className="text-base leading-none">↑</span>
            Upload documents to begin
          </Link>

          {/* Reassurance */}
          <p className="mt-3 text-xs text-slate-400">
            No form to fill in first. Drop any PDF, DOCX, PPTX, XLSX, CSV or TXT.
            The platform detects the organisation and assessment type automatically.
          </p>
        </div>
      </div>

      {/* ── PIPELINE STRIP ─────────────────────────────────────────────── */}
      {/* Shows the steps as a linear read — NOT as navigation. The user is
          not on any of these steps yet. This is orientation, not a menu. */}
      <div className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
        <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-4">
          What happens after you upload
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {STEPS.map((step, idx) => (
            <div key={step.label} className="flex flex-col gap-1.5">
              {/* Step number + connector */}
              <div className="flex items-center gap-1">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-[#DDE6F0] bg-[#F5F8FC] text-[9px] font-black text-slate-400">
                  {idx + 1}
                </div>
                {idx < STEPS.length - 1 ? (
                  <div className="flex-1 h-0.5 bg-[#DDE6F0] hidden lg:block" />
                ) : null}
              </div>
              {/* Icon + label */}
              <div className="text-lg leading-none">{step.icon}</div>
              <div className="text-xs font-extrabold text-slate-900">{step.label}</div>
              <div className="text-[11px] leading-4 text-slate-400">{step.detail}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── DOCUMENT TYPES STRIP ──────────────────────────────────────── */}
      <div className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
        <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-3">
          Documents that work well
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
          {[
            { label: 'Annual Report / Narrative Report',      icon: '📋', detail: 'Captures programme context and narrative claims' },
            { label: 'M&E Report / Evaluation Study',         icon: '📊', detail: 'Structured data, indicators, beneficiary results' },
            { label: 'Budget / Financial Statement',          icon: '💰', detail: 'Cost-effectiveness and resource-allocation signals' },
            { label: 'Programme Proposal / Concept Note',     icon: '📝', detail: 'Theory of change and stated objectives' },
            { label: 'Monitoring Data / Survey CSV',          icon: '📈', detail: 'Raw quantitative data for evidence grounding' },
            { label: 'Policy Document / Strategy Paper',      icon: '🏛️', detail: 'Alignment signals for government assessments' },
          ].map(doc => (
            <div key={doc.label} className="flex items-start gap-2.5 rounded-lg border border-[#DDE6F0] bg-[#F5F8FC] p-3">
              <span className="text-base leading-none shrink-0 mt-0.5">{doc.icon}</span>
              <div>
                <div className="text-xs font-bold text-slate-900 leading-tight">{doc.label}</div>
                <div className="text-[10px] text-slate-400 mt-0.5 leading-4">{doc.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
