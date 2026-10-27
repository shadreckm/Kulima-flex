'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import KulimaLogo from '../components/KulimaLogo/KulimaLogo'
import UserMenu from '../components/UserMenu/UserMenu'
import { saveUseCase } from '../lib/use-case-store'
import { INTAKE_ENTITY_TYPES, entityToAssessmentType, type EntityType } from '../lib/entity-types'
import { clearIntakeDraft, loadIntakeDraft, saveIntakeContext, saveIntakeDraft, type AssessmentContext } from '../lib/assessment-store'
import * as api from '../lib/api'
import type { AssessmentContextPayload } from '../lib/api'

const TYPE_LABELS: Record<EntityType, string> = {
  ngo: 'NGO', development_program: 'Development Programme', government_program: 'Government Programme', tourism_sme: 'Tourism SME', startup: 'Startup', accelerator: 'Accelerator',
}

/** Entity-aware form copy: placeholders change with the selected assessment type. */
// PRIMARY EXPERIENCE: NGO and Development Program placeholders prioritized for V1
const TYPE_PLACEHOLDERS: Record<EntityType, { organization: string; lead: string; keywords: string }> = {
  ngo: { organization: 'e.g. Emerge Livelihoods Foundation', lead: 'e.g. Executive Director', keywords: 'Livelihoods, Women & Youth, Community' },
  development_program: { organization: 'e.g. UNDP Resilience Programme', lead: 'e.g. Programme Manager', keywords: 'Outcomes, Beneficiaries, M&E' },
  government_program: { organization: 'e.g. Ministry of Agriculture Programme', lead: 'e.g. Programme Director', keywords: 'Policy, Public Services, Delivery' },
  tourism_sme: { organization: 'e.g. Savanna Trails Lodge', lead: 'e.g. Managing Director', keywords: 'Tourism, Hospitality, Destination' },
  startup: { organization: 'e.g. Kulima Africa Ltd', lead: 'e.g. CEO / Founder', keywords: 'Fintech, Marketplaces, AgriTech' },
  accelerator: { organization: 'e.g. Sahel Horizon Accelerator', lead: 'e.g. Program Lead', keywords: 'Cohorts, Mentorship, Portfolio' },
}

const FILE_TYPES = ['PDF', 'DOCX', 'PPTX', 'XLSX', 'CSV', 'TXT']

// PRIMARY EXPERIENCE: NGO and Development Program pipeline language for V1
const PIPELINE = [
  { key: 'info', label: 'Information', detail: 'Reports, budgets, evaluations, policies' },
  { key: 'evidence', label: 'Evidence', detail: 'Claims extracted and structured' },
  { key: 'trust', label: 'Trust', detail: 'Source reliability scored 0–100' },
  { key: 'signals', label: 'Signals', detail: 'Risk, opportunity, community, climate' },
  { key: 'decision', label: 'Decision', detail: 'Approve / Reassess / Reject + rationale' },
]

const PIPELINE_CARDS = [
  { label: 'Documents Uploaded', icon: '📄' },
  { label: 'Entities Extracted', icon: '🏛️' },
  { label: 'Evidence Built', icon: '🧱' },
  { label: 'Research Complete', icon: '🌐' },
  { label: 'Signals Generated', icon: '⚡' },
  { label: 'Decision Ready', icon: '🎯' },
  { label: 'Report Ready', icon: '📑' },
]

// PRIMARY EXPERIENCE: NGO and Development Program signal domains prioritized for V1
const SIGNAL_DOMAINS = [
  { label: 'Community', icon: '🤝', desc: 'Beneficiary reach and social outcomes' },
  { label: 'Trust', icon: '🛡️', desc: 'Source reliability and corroboration' },
  { label: 'Funding', icon: '💰', desc: 'Funding readiness and cost-effectiveness' },
  { label: 'Risk', icon: '⚠️', desc: 'Program risks and implementation challenges' },
  { label: 'Opportunity', icon: '🌱', desc: 'Growth and scaling opportunities' },
  { label: 'Climate', icon: '🌤️', desc: 'Climate risk and resilience alignment' },
  { label: 'Environment', icon: '🌿', desc: 'Environmental compliance and sustainability' },
  // Secondary market signals (kept but deprioritized in order)
  { label: 'Market', icon: '📈', desc: 'Size, competition, positioning' },
  { label: 'Tourism', icon: '�', desc: 'Destination impact and visitor economy' },
]

// PRIMARY EXPERIENCE: NGO and Development Program use cases prioritized for V1
const USE_CASES = [
  { title: 'NGO Programme Review', desc: 'Verify impact claims across donor reports and field data before the board sees them.' },
  { title: 'Development Programme Performance', desc: 'Turn monitoring data and theory-of-change documents into decision-ready evidence.' },
  { title: 'Monitoring & Evaluation Review', desc: 'Corroborate beneficiary outcomes against independent research intelligence.' },
  { title: 'Institutional Capacity Assessment', desc: 'Assess organizational readiness, financial health, and program delivery capacity.' },
  { title: 'Evidence & Trust Report', desc: 'Extract and verify claims from proposals, reports, and evaluations with source attribution.' },
  { title: 'Government Initiative Assessment', desc: 'Assess budget allocation, implementation progress and policy alignment in one workspace.' },
  // Secondary markets (kept but deprioritized in order)
  { title: 'Tourism Investment Readiness', desc: 'Score destination businesses on trust, sustainability and visitor-economy signals.' },
  { title: 'Startup Readiness', desc: 'Evidence-based investment screening — trust score, risk register and IC memo.' },
]

const AFTER = ['Evidence', 'Trust', 'Signals', 'Decisions', 'Reports']

/** P8: post-upload journey — replaces the old competitor-comparison table. */
const POST_UPLOAD_FLOW = [
  { label: 'Documents', desc: 'You upload PDF, DOCX, PPTX, XLSX, CSV or TXT files — one or many.' },
  { label: 'Evidence', desc: 'Every claim is extracted, structured and linked to its source page.' },
  { label: 'Trust', desc: 'Each source is reliability-scored 0–100 across four factors.' },
  { label: 'Signals', desc: 'Nine domains surface risks, opportunities, climate and community impact.' },
  { label: 'Decision', desc: 'Invest / Observe / Reassess with a defensible, evidence-backed rationale.' },
  { label: 'Report', desc: 'Export the IC memo, full report, signal register or one-pager.' },
]

// PRIMARY EXPERIENCE: NGO and Development Program reports prioritized for V1
const REPORT_KINDS = [
  { label: 'Institutional Capacity Review', live: true },
  { label: 'Program Performance Review', live: true },
  { label: 'Monitoring & Evaluation Review', live: true },
  { label: 'Evidence & Trust Report', live: true },
  { label: 'Development Decision Report', live: true },
  // Secondary markets (kept but deprioritized in order)
  { label: 'Tourism Resilience Report', live: true },
  { label: 'Investment Committee Report', live: true },
  { label: 'Governance Review', live: true },
  // Future templates
  { label: 'UNDP Templates', live: false },
  { label: 'EU Templates', live: false },
  { label: 'USAID Templates', live: false },
]

const PRICING = [
  { name: 'Starter', price: 'Free', detail: 'Run your first assessment. Limited documents per month.', cta: 'Start free' },
  { name: 'Professional', price: '$49/mo', detail: 'Unlimited assessments, all signal domains, reports, Ask AI Analyst.', cta: 'Go Professional', featured: true },
  { name: 'Enterprise', price: 'Custom', detail: 'Organizations, RBAC, audit logs, private workspace, donor templates.', cta: 'Talk to us' },
]

// REDIRECT LOOP FIX (landing side): a per-mount ref resets every time the
// loop bounces the user back to '/', so it cannot stop a redirect loop.
// This latch is module-level AND session-scoped: the landing page may only
// push /flex once per session window. /flex clears the latch once the
// Assessment Context has actually hydrated (see flex/page.tsx).
const FLEX_REDIRECT_LATCH = 'kulima:flex-redirect-latch'
const FLEX_REDIRECT_WINDOW_MS = 15_000

function mayRedirectToFlex(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const last = Number(window.sessionStorage.getItem(FLEX_REDIRECT_LATCH) || 0)
    if (last && Date.now() - last < FLEX_REDIRECT_WINDOW_MS) return false
    window.sessionStorage.setItem(FLEX_REDIRECT_LATCH, String(Date.now()))
    return true
  } catch {
    return true
  }
}

function HomeInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { status: authStatus } = useSession()
  const [assessmentType, setAssessmentType] = useState<EntityType>('startup')
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [context, setContext] = useState<AssessmentContext | null>(null)
  const [organization, setOrganization] = useState('')
  const [founderOrLead, setFounderOrLead] = useState('')
  const [keywords, setKeywords] = useState('')
  const [showEdit, setShowEdit] = useState(false)
  const resumeHandled = useRef(false)
  const [activeAssessment, setActiveAssessment] = useState<AssessmentContextPayload | null>(null)
  const activeAssessmentRef = useRef<AssessmentContextPayload | null>(null)
  const hasRedirectedRef = useRef(false)

  // Get Started UX: clicking the CTA activates Upload Mode — the page scrolls
  // to the dropzone and the CTA label transitions to reflect the upload state.
  const uploadSectionRef = useRef<HTMLElement | null>(null)
  const [uploadMode, setUploadMode] = useState(false)
  useEffect(() => {
    if (files.length > 0) setUploadMode(true)
  }, [files.length])
  function activateUploadMode() {
    setUploadMode(true)
    uploadSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const ctaLabel = busy
    ? 'Analyzing…'
    : files.length > 0
      ? 'Assessment Ready — Confirm & Analyze'
      : uploadMode
        ? 'Upload Documents Below'
        : 'Get Started'

  const runIntake = useCallback(async (
    type: EntityType,
    selectedFiles: File[],
    meta: { organization?: string; founderOrLead?: string; keywords?: string } = {},
  ) => {
    setBusy(true); setMessage(null)
    try {
      // Calculate total file size to determine upload method
      const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0)
      const FOUR_MB = 4 * 1024 * 1024

      // Use direct backend upload for files > 4MB to bypass Vercel 4.5MB proxy limit
      // Backend now supports up to 100MB
      const createFn = totalSize > FOUR_MB ? api.createAssessmentDirect : api.createAssessment

      const payload = await createFn(selectedFiles, entityToAssessmentType(type), {
        organizationName: meta.organization || undefined,
        founderName: meta.founderOrLead || undefined,
        keywords: meta.keywords || undefined,
      })
      const saved = saveIntakeContext(payload)
      setContext(saved)
      setFiles([])

      // Start run immediately
      let activeRunId = payload.runId
      if (!activeRunId && payload.assessmentId) {
        try {
          const started = await api.startAssessmentRun(payload.assessmentId)
          if (started?.runId) activeRunId = started.runId
        } catch (runErr) {
          console.warn('Auto-start run notice:', runErr)
        }
      }

      // Persist the run identity straight into the Assessment Context.
      const finalContext = { ...payload, runId: activeRunId || payload.runId || '' }
      saveIntakeContext(finalContext)

      // Redirect immediately to the workspace — the assessment is now active.
      // The useAssessmentBootstrap hook will poll for completion and refresh automatically.
      // Redirect-loop protection: only one push to /flex per session window.
      setMessage('Assessment created. Opening your workspace…')
      if (mayRedirectToFlex()) router.push('/flex')
      void clearIntakeDraft().catch(() => {})
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed. Please try again.')
    } finally { setBusy(false) }
  }, [router])

  useEffect(() => {
    if (resumeHandled.current || searchParams.get('resume') !== 'intake' || authStatus !== 'authenticated') return
    resumeHandled.current = true
    void (async () => {
      const draft = await loadIntakeDraft()
      if (draft?.files.length) {
        // runIntake pushes /flex itself — do NOT fall through to replace('/')
        // afterwards, or the user is yanked back to the landing page after
        // the assessment is created.
        await runIntake(draft.assessmentType, draft.files, {
          organization: draft.organization,
          founderOrLead: draft.founder,
          keywords: draft.keywords,
        })
        return
      }
      setMessage('Your previous upload session expired. Please select your documents again.')
      router.replace('/')
    })()
  }, [authStatus, searchParams, router, runIntake])

  // Failsafe: Check for completed assessments when authenticated
  // If the user is stranded on the landing page with a completed assessment,
  // automatically redirect to the workspace (NO BUTTON - the landing page is only for upload)
  // PROTECT AGAINST REDIRECT LOOP: Only redirect once using hasRedirectedRef
  useEffect(() => {
    if (authStatus !== 'authenticated' || hasRedirectedRef.current) return
    let cancelled = false
    void (async () => {
      try {
        const active = await api.getActiveAssessment()
        if (cancelled || !active) return
        // Check if assessment is complete or has a run
        const isComplete = active.status === 'complete' || active.status === 'completed' || active.runId
        if (isComplete) {
          setActiveAssessment(active)
          activeAssessmentRef.current = active
          hasRedirectedRef.current = true
          // Auto-redirect to workspace - NO BUTTON needed.
          // Redirect-loop protection: only one push to /flex per session window.
          if (mayRedirectToFlex()) router.push('/flex')
          else hasRedirectedRef.current = true
        }
      } catch {
        // No active assessment — this is expected on the landing page
      }
    })()
    return () => { cancelled = true }
  }, [authStatus, router])

  // Poll for assessment completion if we have an active assessment with a run
  // Automatically redirect to workspace when complete
  // PROTECT AGAINST REDIRECT LOOP: Only redirect once using hasRedirectedRef
  useEffect(() => {
    const current = activeAssessmentRef.current
    if (!current?.runId || authStatus !== 'authenticated' || hasRedirectedRef.current) return
    const status = current.status
    if (status === 'complete' || status === 'completed') return

    let cancelled = false
    const interval = setInterval(async () => {
      if (cancelled) return
      try {
        const s = await api.getRunStatus(current.runId!)
        const st = String(s?.status || '').toLowerCase()
        if (st === 'complete' || st === 'completed') {
          clearInterval(interval)
          if (!cancelled && !hasRedirectedRef.current) {
            hasRedirectedRef.current = true
            // Refresh the assessment context
            const full = await api.getAssessment(current.assessmentId!)
            if (full) {
              setActiveAssessment(full)
              activeAssessmentRef.current = full
              // Save to store (the store accepts both types)
              saveIntakeContext(full as unknown as AssessmentContext)
              // Auto-redirect to workspace (once per session window)
              if (mayRedirectToFlex()) router.push('/flex')
            }
          }
        }
      } catch {
        // Transient errors — keep polling
      }
    }, 3000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [authStatus, router])

  function addFiles(incoming: FileList | null) {
    if (!incoming?.length) return
    const selectedFiles = Array.from(incoming)
    setFiles(previous => [...previous, ...selectedFiles.filter(file => !previous.some(item => item.name === file.name && item.size === file.size))])
    setMessage(null)
  }

  async function handleUpload() {
    if (!files.length || busy) return
    saveUseCase(assessmentType)
    const meta = { organization, founderOrLead, keywords }
    if (authStatus === 'authenticated') {
      await runIntake(assessmentType, files, meta)
    } else {
      await saveIntakeDraft(assessmentType, files, {
        organization,
        founder: founderOrLead,
        keywords,
      })
      router.push(`/api/auth/signin?callbackUrl=${encodeURIComponent('/?resume=intake')}`)
    }
  }

  const hasFiles = files.length > 0

  return (
    <main className="min-h-screen bg-white text-[#101828]">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-10">
        <Link href="/" className="flex items-center gap-3" aria-label="Kulima FLEX home"><KulimaLogo variant="header" /><span className="text-sm font-bold tracking-tight">Kulima <span className="text-[#159A62]">FLEX</span></span></Link>
        <nav className="hidden items-center gap-8 text-sm font-medium text-[#667085] md:flex">
          <a href="#pipeline">Pipeline</a>
          <a href="#signals">Signals</a>
          <a href="#use-cases">Use cases</a>
          <a href="#pricing">Pricing</a>
        </nav>
        <div className="flex items-center gap-3"><UserMenu /><button type="button" onClick={activateUploadMode} className="rounded-lg bg-[#101828] px-4 py-2.5 text-sm font-bold text-white transition hover:bg-[#1D2939]">{ctaLabel}</button></div>
      </header>

      {/* ── SECTION 1: HERO — upload is the page's first act ───────────────── */}
      <section id="upload" ref={uploadSectionRef} className={`border-b scroll-mt-24 ${uploadMode ? 'border-[#B7E6CC] bg-[radial-gradient(circle_at_80%_20%,#EAF8F0_0,transparent_32%),#F7FBF8]' : 'border-[#EAECF0] bg-[radial-gradient(circle_at_80%_20%,#EAF8F0_0,transparent_32%),#fff]'}`}>
        <div className="mx-auto max-w-7xl px-6 pb-16 pt-14 lg:px-10 lg:pb-24 lg:pt-20">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-[#B7E6CC] bg-[#F0FBF4] px-3 py-1.5 text-xs font-bold uppercase tracking-[0.14em] text-[#117A4B]"><span className="size-1.5 rounded-full bg-[#159A62]" /> Africa&apos;s Decision Intelligence Platform</div>
          <h1 className="max-w-4xl text-5xl font-semibold leading-[1.02] tracking-[-0.055em] text-[#101828] sm:text-6xl lg:text-7xl">Turn information into <span className="text-[#159A62]">trusted decisions.</span></h1>
          <p className="mt-7 max-w-3xl text-lg leading-8 text-[#667085]">Upload proposals, annual reports, budgets, M&E reports, policy documents, or programme assessments. Kulima FLEX analyzes evidence, verifies trust, discovers signals, and generates decision-ready intelligence for NGOs and development programmes.</p>

          {/* Gigantic dropzone — one action, no forms initially */}
          <label
            onDrop={event => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files) }}
            onDragOver={event => { event.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            className={`mt-10 flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 text-center transition ${dragging ? 'border-[#159A62] bg-[#EAF8F0]' : 'border-[#98A2B3] bg-white hover:border-[#159A62] hover:bg-[#FAFDFB]'}`}
          >
            <span className="flex size-14 items-center justify-center rounded-full bg-[#EAF8F0] text-2xl text-[#159A62]" aria-hidden="true">↑</span>
            <span className="mt-4 text-xl font-bold text-[#101828]">Drop documents here</span>
            <span className="mt-1.5 text-sm font-semibold text-[#475467]">or click to browse — upload first, ask questions later.</span>
            <span className="mt-4 flex flex-wrap justify-center gap-2">
              {FILE_TYPES.map(t => <span key={t} className="rounded-md border border-[#EAECF0] bg-[#F9FAFB] px-2 py-1 text-[11px] font-bold text-[#667085]">{t}</span>)}
            </span>
            <input type="file" multiple accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt" className="hidden" onChange={event => { addFiles(event.target.files); event.target.value = '' }} />
          </label>

          <div className="mt-3 text-sm font-semibold text-[#475467]">Upload first. Ask questions later. <span className="font-normal text-[#667085]">Extraction and assessment-type detection happen automatically — you confirm, not re-type.</span></div>

          {message ? <div className="mt-4 rounded-lg border border-[#B7E6CC] bg-[#F0FBF4] px-4 py-3 text-sm font-semibold text-[#117A4B]">{message}</div> : null}

          {/* ── SECTION 2: AUTO DETECTION — appears after files are staged ──── */}
          {hasFiles ? (
            <div className="mt-8 rounded-2xl border border-[#D0D5DD] bg-white p-6 shadow-[0_12px_40px_-16px_rgba(16,24,40,0.18)]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#159A62]">Detected</p>
                  <h2 className="mt-1 text-xl font-semibold tracking-tight">Confirm your assessment context</h2>
                </div>
                <button type="button" onClick={() => setShowEdit(v => !v)} className="rounded-lg border border-[#D0D5DD] px-3 py-2 text-sm font-semibold text-[#344054] hover:bg-[#F9FAFB]">{showEdit ? 'Done editing' : 'Edit'}</button>
              </div>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-[#EAECF0] bg-[#F9FAFB] p-4">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[#667085]">Assessment Type</div>
                  {showEdit ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {INTAKE_ENTITY_TYPES.map(type => (
                        <button key={type} type="button" onClick={() => { setAssessmentType(type); saveUseCase(type) }} className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${assessmentType === type ? 'border-[#159A62] bg-[#EAF8F0] text-[#117A4B]' : 'border-[#D0D5DD] text-[#344054] hover:border-[#159A62]'}`}>{TYPE_LABELS[type]}</button>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-1.5 text-sm font-bold text-[#101828]">✓ {TYPE_LABELS[assessmentType]}</div>
                  )}
                </div>
                <div className="rounded-xl border border-[#EAECF0] bg-[#F9FAFB] p-4">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[#667085]">Organization</div>
                  {showEdit ? (
                    <input value={organization} onChange={e => setOrganization(e.target.value)} placeholder={TYPE_PLACEHOLDERS[assessmentType].organization} className="mt-2 w-full rounded-lg border border-[#D0D5DD] px-3 py-2 text-sm" />
                  ) : (
                    <div className="mt-1.5 text-sm font-bold text-[#101828]">✓ {organization || 'Detected from documents'}</div>
                  )}
                </div>
                <div className="rounded-xl border border-[#EAECF0] bg-[#F9FAFB] p-4">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[#667085]">Lead</div>
                  {showEdit ? (
                    <input value={founderOrLead} onChange={e => setFounderOrLead(e.target.value)} placeholder={TYPE_PLACEHOLDERS[assessmentType].lead} className="mt-2 w-full rounded-lg border border-[#D0D5DD] px-3 py-2 text-sm" />
                  ) : (
                    <div className="mt-1.5 text-sm font-bold text-[#101828]">✓ {founderOrLead || 'Detected from documents'}</div>
                  )}
                </div>
                <div className="rounded-xl border border-[#EAECF0] bg-[#F9FAFB] p-4">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[#667085]">Keywords</div>
                  {showEdit ? (
                    <input value={keywords} onChange={e => setKeywords(e.target.value)} placeholder={TYPE_PLACEHOLDERS[assessmentType].keywords} className="mt-2 w-full rounded-lg border border-[#D0D5DD] px-3 py-2 text-sm" />
                  ) : (
                    <div className="mt-1.5 text-sm font-bold text-[#101828]">✓ {keywords || 'Detected from documents'}</div>
                  )}
                </div>
              </div>
                <div className="rounded-xl border border-[#EAECF0] bg-[#F9FAFB] p-4">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[#667085]">Lead</div>
                  {showEdit ? (
                    <input value={founderOrLead} onChange={e => setFounderOrLead(e.target.value)} placeholder={TYPE_PLACEHOLDERS[assessmentType].lead} className="mt-2 w-full rounded-lg border border-[#D0D5DD] px-3 py-2 text-sm" />
                  ) : (
                    <div className="mt-1.5 text-sm font-bold text-[#101828]">✓ {founderOrLead || 'Detected from documents'}</div>
                  )}
                </div>
                <div className="rounded-xl border border-[#EAECF0] bg-[#F9FAFB] p-4">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[#667085]">Keywords</div>
                  {showEdit ? (
                    <input value={keywords} onChange={e => setKeywords(e.target.value)} placeholder={TYPE_PLACEHOLDERS[assessmentType].keywords} className="mt-2 w-full rounded-lg border border-[#D0D5DD] px-3 py-2 text-sm" />
                  ) : (
                    <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs font-semibold text-[#344054]">
                      {(keywords ? keywords.split(',').map(k => k.trim()).filter(Boolean) : ['Climate', 'Waste Management', 'Tourism', 'Agriculture']).map(k => <span key={k} className="rounded-md bg-[#EAF8F0] px-2 py-0.5 text-[#117A4B]">{k}</span>)}
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#EAECF0] pt-4">
                <div className="text-sm text-[#667085]">{files.length} document{files.length !== 1 ? 's' : ''} staged · {files.map(f => f.name).join(', ')}</div>
                <button type="button" onClick={handleUpload} disabled={busy} className="rounded-lg bg-[#159A62] px-5 py-3 text-sm font-bold text-white transition hover:bg-[#117A4B] disabled:opacity-50">
                  {busy ? 'Analyzing…' : 'Confirm & Analyze →'}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      {/* ── SECTION 3: LIVE DECISION PIPELINE ──────────────────────────────── */}
      <section id="pipeline" className="mx-auto max-w-7xl px-6 py-20 lg:px-10">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">The decision pipeline</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Every document travels the same path to a defensible decision.</h2>
        </div>
        <div className="mt-12 flex flex-col items-center gap-1 lg:flex-row lg:items-stretch lg:gap-2">
          {PIPELINE.map((step, i) => (
            <div key={step.key} className="flex w-full flex-col items-center gap-1 lg:flex-1 lg:flex-row">
              <div className="w-full rounded-xl border border-[#EAECF0] bg-[#F9FAFB] p-5">
                <div className="text-[11px] font-bold uppercase tracking-widest text-[#159A62]">0{i + 1}</div>
                <div className="mt-2 text-lg font-bold">{step.label}</div>
                <div className="mt-1 text-sm text-[#667085]">{step.detail}</div>
              </div>
              {i < PIPELINE.length - 1 ? <span className="rotate-90 text-[#98A2B3] lg:rotate-0" aria-hidden="true">→</span> : null}
            </div>
          ))}
        </div>
        <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {PIPELINE_CARDS.map((c, i) => (
            <div key={c.label} className={`rounded-xl border p-4 ${i === 6 ? 'border-[#A6F4C5] bg-[#ECFDF3]' : 'border-[#EAECF0] bg-white'}`}>
              <div className="text-xl">{c.icon}</div>
              <div className="mt-2 text-xs font-bold leading-tight">{c.label}</div>
              <div className={`mt-2 h-1 rounded-full ${i === 6 ? 'bg-[#12B76A]' : 'bg-[#EAF8F0]'}`} />
            </div>
          ))}
        </div>
      </section>

      {/* ── SECTION 4: WHAT HAPPENS AFTER UPLOAD (P8) ──────────────────── */}
      <section className="border-y border-[#EAECF0] bg-[#F8FAFC]">
        <div className="mx-auto max-w-7xl px-6 py-20 lg:px-10">
          <div className="max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">What happens after upload?</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">From documents to a defensible decision — automatically.</h2>
            <p className="mt-4 text-base leading-7 text-[#667085]">You upload once. The Assessment Context carries your documents through the whole pipeline — no re-entry, no dead ends, every stage building on the last.</p>
          </div>
          <div className="mt-12 flex flex-col items-center gap-1 lg:flex-row lg:items-stretch lg:gap-2">
            {POST_UPLOAD_FLOW.map((step, i) => (
              <div key={step.label} className="flex w-full flex-col items-center gap-1 lg:flex-1 lg:flex-row">
                <div className="w-full rounded-xl border border-[#EAECF0] bg-white p-5 transition hover:border-[#B7E6CC] hover:shadow-sm">
                  <div className="text-[11px] font-bold uppercase tracking-widest text-[#159A62]">{String(i + 1).padStart(2, '0')}</div>
                  <div className="mt-2 text-lg font-bold">{step.label}</div>
                  <div className="mt-1 text-sm text-[#667085]">{step.desc}</div>
                </div>
                {i < POST_UPLOAD_FLOW.length - 1 ? <span className="rotate-90 text-[#98A2B3] lg:rotate-0" aria-hidden="true">→</span> : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTION 5: SIGNAL DOMAINS ──────────────────────────────────────── */}
      <section id="signals" className="mx-auto max-w-7xl px-6 py-20 lg:px-10">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">Signal domains</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Nine signal domains power every decision.</h2>
          <p className="mt-4 text-base leading-7 text-[#667085]">Tourism is not a separate platform — it&apos;s a signal domain. So are Climate and Community. One assessment, nine lenses.</p>
        </div>
        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {SIGNAL_DOMAINS.map(d => (
            <div key={d.label} className="rounded-xl border border-[#EAECF0] bg-white p-5 transition hover:border-[#B7E6CC] hover:shadow-sm">
              <div className="flex items-center gap-2.5"><span className="text-xl">{d.icon}</span><span className="text-base font-bold">{d.label}</span></div>
              <div className="mt-2 text-sm text-[#667085]">{d.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── SECTION 6: WHO IT IS FOR ───────────────────────────────────────── */}
      <section id="use-cases" className="border-y border-[#EAECF0] bg-[#F8FAFC]">
        <div className="mx-auto max-w-7xl px-6 py-20 lg:px-10">
          <div className="max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">Who it&apos;s for</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Built for the people who must decide.</h2>
            <p className="mt-4 text-base leading-7 text-[#667085]">Program Managers, MEAL Coordinators, Executive Directors, NGOs, Tourism SMEs, Development and Government Programmes, Donors, and Startups.</p>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {USE_CASES.map(u => (
              <div key={u.title} className="rounded-xl border border-[#EAECF0] bg-white p-6">
                <h3 className="text-base font-bold">{u.title}</h3>
                <p className="mt-2 text-sm leading-6 text-[#667085]">{u.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTION 7: FROM SCATTERED TO DECISIONS ────────────────────── */}
      <section className="mx-auto max-w-7xl px-6 py-20 lg:px-10">
        <h2 className="max-w-2xl text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">From scattered information to decisions.</h2>
        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-[#EAECF0] bg-[#F9FAFB] p-7">
            <div className="text-xs font-bold uppercase tracking-[0.14em] text-[#667085]">Before FLEX</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {['WhatsApp', 'Email', 'Excel', 'PDFs', 'Field Reports', 'Meetings'].map(item => <span key={item} className="rounded-lg border border-[#EAECF0] bg-white px-3 py-2 text-sm font-semibold text-[#475467]">{item}</span>)}
            </div>
          </div>
          <div className="rounded-2xl border border-[#A6F4C5] bg-[#ECFDF3] p-7">
            <div className="text-xs font-bold uppercase tracking-[0.14em] text-[#117A4B]">After FLEX</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {AFTER.map(item => <span key={item} className="rounded-lg bg-white px-3 py-2 text-sm font-bold text-[#0C5132] shadow-sm">{item}</span>)}
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 8: REPORT OUTPUTS ──────────────────────────────────────── */}
      <section className="border-t border-[#EAECF0] bg-[#F8FAFC]">
        <div className="mx-auto max-w-7xl px-6 py-20 lg:px-10">
          <div className="max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">Report outputs</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Board-ready documents, generated from your evidence.</h2>
          </div>
          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {REPORT_KINDS.map(r => (
              <div key={r.label} className={`rounded-xl border p-5 ${r.live ? 'border-[#EAECF0] bg-white' : 'border-dashed border-[#D0D5DD] bg-white/60'}`}>
                <div className="text-sm font-bold">{r.label}</div>
                <div className={`mt-2 inline-block rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${r.live ? 'bg-[#EAF8F0] text-[#117A4B]' : 'bg-[#F2F4F7] text-[#667085]'}`}>{r.live ? 'Available now' : 'Coming soon'}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTION 9: PRICING ─────────────────────────────────────────────── */}
      <section id="pricing" className="border-t border-[#EAECF0] bg-[#101828] text-white">
        <div className="mx-auto max-w-7xl px-6 py-20 lg:px-10">
          <div className="max-w-xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#7BE0A9]">Simple plans</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Decision intelligence that scales with you.</h2>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {PRICING.map(plan => (
              <div key={plan.name} className={`rounded-xl border p-6 ${plan.featured ? 'border-[#159A62] bg-[#143B2B]' : 'border-[#344054] bg-[#182230]'}`}>
                <h3 className="text-lg font-bold">{plan.name}</h3>
                <div className="mt-2 text-2xl font-semibold">{plan.price}</div>
                <p className="mt-3 text-sm leading-6 text-[#D0D5DD]">{plan.detail}</p>
                <a href="#upload" className="mt-8 inline-block rounded-lg bg-white/10 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-white/20">{plan.cta} →</a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTION 10: FINAL CTA ──────────────────────────────────────────── */}
      <section className="border-t border-[#EAECF0] bg-[radial-gradient(circle_at_20%_80%,#EAF8F0_0,transparent_35%),#fff]">
        <div className="mx-auto max-w-4xl px-6 py-24 text-center lg:px-10">
          <h2 className="text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Ready to turn information into trusted decisions?</h2>
          <p className="mx-auto mt-4 max-w-xl text-base text-[#667085]">Upload your first document. No forms. No friction.</p>
          <a href="#upload" className="mt-8 inline-block rounded-xl bg-[#159A62] px-8 py-4 text-base font-bold text-white shadow-sm transition hover:bg-[#117A4B]">Upload your first document ↑</a>
        </div>
      </section>

      <footer className="border-t border-[#EAECF0]">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-8 text-sm text-[#667085] sm:flex-row sm:items-center sm:justify-between lg:px-10">
          <div className="flex items-center gap-3"><KulimaLogo variant="header" /><span>© 2026 Kulima FLEX</span></div>
          <div className="flex gap-5"><Link href="/trust">Security</Link><Link href="/dashboard">Dashboard</Link><Link href="/flex">Workspace</Link></div>
        </div>
      </footer>
    </main>
  )
}

export default function Home() { return <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-[#667085]">Loading…</div>}><HomeInner /></Suspense> }
