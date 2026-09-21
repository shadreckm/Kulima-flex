'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import KulimaLogo from '../components/KulimaLogo/KulimaLogo'
import { saveUseCase } from '../lib/use-case-store'
import {
  INTAKE_ENTITY_TYPES,
  entityToAssessmentType,
  getEntityConfig,
  type EntityType,
} from '../lib/entity-types'
import {
  clearAssessmentContext,
  clearIntakeDraft,
  contextNeedsConfirmation,
  loadAssessmentContext,
  loadIntakeDraft,
  saveIntakeContext,
  saveIntakeDraft,
  type AssessmentContext,
} from '../lib/assessment-store'
import * as api from '../lib/api'

const TYPE_ICONS: Record<EntityType, string> = {
  startup: '🚀',
  ngo: '🌍',
  government_program: '🏛️',
  development_program: '🤝',
  tourism_sme: '🏝️',
  accelerator: '🎓',
}

const TYPE_EXAMPLES: Record<EntityType, string> = {
  startup: 'Pitch deck · Business plan · Financial statements',
  ngo: 'Program report · Proposal · M&E data',
  government_program: 'Program report · Strategy document · Budget',
  development_program: 'Proposal · Program report · Results framework',
  tourism_sme: 'Business plan · Strategy document · Financial statements',
  accelerator: 'Program report · Portfolio data · Financial statements',
}

const STEPS = [
  { n: '01', label: 'Choose Assessment Type', description: 'Startup, NGO, Government, Development, or Tourism SME.' },
  { n: '02', label: 'Upload Documents', description: 'Drop pitch decks, reports, proposals, or statements.' },
  { n: '03', label: 'Review Findings', description: 'Evidence, trust, and 9 signal domains generated instantly.' },
  { n: '04', label: 'Export Decision', description: 'Download a memo or full IC report.' },
]

const STATUS_LABELS: Record<string, string> = {
  intake: 'Draft',
  needs_confirmation: 'Needs Confirmation',
  ready: 'Ready',
  running: 'Running',
  complete: 'Complete',
  failed: 'Failed',
}

const FIELD_LABELS: Array<[string, string]> = [
  ['founderOrLead', 'Founder / Lead'],
  ['sector', 'Sector'],
  ['country', 'Country'],
  ['website', 'Website'],
  ['team', 'Team'],
  ['problemStatement', 'Problem Statement'],
]

type Phase = 'select' | 'uploading' | 'ready' | 'confirm' | 'error'

function HomeInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { status: authStatus } = useSession()

  const [assessmentType, setAssessmentType] = useState<EntityType>('startup')
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [phase, setPhase] = useState<Phase>('select')
  const [context, setContext] = useState<AssessmentContext | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Correction values — used only when extraction confidence is low (Step 4).
  const [correctionEntity, setCorrectionEntity] = useState('')
  const [correctionFounder, setCorrectionFounder] = useState('')
  const resumeHandled = useRef(false)

  const busy = phase === 'uploading'

  // Restore type selection + existing shared context (returning users).
  useEffect(() => {
    const ctx = loadAssessmentContext()
    if (!ctx) return
    setContext(ctx)
    setAssessmentType(ctx.entityType)
    setCorrectionEntity(ctx.displayEntity || ctx.entityName || '')
    setCorrectionFounder(ctx.founderOrLead || '')
    if (ctx.assessmentId) {
      setPhase(contextNeedsConfirmation(ctx) ? 'confirm' : 'ready')
    }
  }, [])

  /** Upload once → evidence pipeline + auto extraction → shared context. */
  const runIntake = useCallback(async (type: EntityType, selectedFiles: File[]) => {
    if (!selectedFiles.length) return
    setError(null)
    setPhase('uploading')
    try {
      const payload = await api.createAssessment(selectedFiles, entityToAssessmentType(type))
      const ctx = saveIntakeContext(payload)
      await clearIntakeDraft()
      setContext(ctx)
      setFiles([])
      setCorrectionEntity(payload.displayEntity || payload.organizationName || payload.startupName || '')
      setCorrectionFounder(payload.founderName || '')
      setPhase(payload.requiresConfirmation ? 'confirm' : 'ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setPhase('error')
    }
  }, [])

  // Resume after the sign-in redirect: re-upload the draft saved in IndexedDB.
  useEffect(() => {
    if (resumeHandled.current) return
    if (searchParams.get('resume') !== 'intake') return
    if (authStatus === 'loading') return
    if (authStatus !== 'authenticated') return
    resumeHandled.current = true
    void (async () => {
      const draft = await loadIntakeDraft()
      if (draft && draft.files.length) {
        setAssessmentType(draft.assessmentType)
        saveUseCase(draft.assessmentType)
        await runIntake(draft.assessmentType, draft.files)
      } else {
        setError('Your previous upload session expired. Please re-select your documents.')
        setPhase('select')
      }
      router.replace('/')
    })()
  }, [authStatus, searchParams, router, runIntake])

  function selectType(type: EntityType) {
    setAssessmentType(type)
    saveUseCase(type)
  }

  function addFiles(incoming: FileList | null) {
    if (!incoming?.length) return
    const next = [...files]
    for (const file of Array.from(incoming)) {
      if (!next.some(f => f.name === file.name && f.size === file.size)) next.push(file)
    }
    setFiles(next)
    setError(null)
    setPhase('select')
  }

  function removeFile(index: number) {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  async function handlePrimary() {
    if (busy) return
    if (!files.length) {
      // No new documents — continue with the existing shared context.
      if (context?.assessmentId) router.push('/signals')
      return
    }
    if (authStatus === 'authenticated') {
      await runIntake(assessmentType, files)
      return
    }
    // Uploads happen after sign-in; keep the picked files in IndexedDB so the
    // flow resumes automatically (collect once — never re-select).
    setError(null)
    await saveIntakeDraft(assessmentType, files)
    router.push(`/api/auth/signin?callbackUrl=${encodeURIComponent('/?resume=intake')}`)
  }

  async function handleConfirmDetails() {
    if (!context?.assessmentId || busy) return
    setError(null)
    setPhase('uploading')
    try {
      const payload = await api.patchAssessmentContext(context.assessmentId, {
        assessmentType: entityToAssessmentType(assessmentType),
        entityName: correctionEntity.trim() || undefined,
        founderName: correctionFounder.trim() || undefined,
      })
      const ctx = saveIntakeContext(payload)
      setContext(ctx)
      setPhase(payload.requiresConfirmation ? 'confirm' : 'ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setPhase('error')
    }
  }

  function startNewAssessment() {
    clearAssessmentContext()
    setContext(null)
    setFiles([])
    setError(null)
    setPhase('select')
  }

  const selectedConfig = getEntityConfig(assessmentType)
  const uploadedDocs = context?.uploadedDocuments ?? []
  const showSummary = Boolean(context?.assessmentId) && (phase === 'ready' || phase === 'confirm')
  const statusKey = String(context?.status || 'intake')

  return (
    <main className="min-h-screen bg-[#F5F8FC] text-slate-900">
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-8 md:py-12">

        {/* Header */}
        <header className="flex items-center justify-between gap-4 mb-10">
          <div className="flex items-center gap-3">
            <KulimaLogo variant="header" />
            <div>
              <div className="text-xs font-black uppercase tracking-[0.2em] text-[#0B5D3B]">Kulima FLEX</div>
              <div className="text-[11px] font-semibold text-slate-400">Decision Intelligence Platform</div>
            </div>
          </div>
          <Link
            href="/dashboard"
            className="text-xs font-extrabold text-[#0B5D3B] hover:underline hidden sm:block"
          >
            Open Dashboard →
          </Link>
        </header>

        {/* Hero */}
        <div className="text-center mb-10">
          <div className="inline-flex rounded-full border border-[#A6F4C5] bg-[#ECFDF3] px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-[#027A48] mb-4">
            Collect once. Reuse everywhere.
          </div>
          <h1 className="text-3xl font-black leading-tight tracking-tight text-[#061C14] md:text-5xl max-w-2xl mx-auto">
            One assessment. Every decision surface.
          </h1>
          <p className="mt-4 text-base text-slate-500 max-w-xl mx-auto leading-relaxed">
            Choose your assessment type and upload your documents once. FLEX extracts the organisation,
            founder, and sector automatically — then drives Evidence, Signals, Decision, Reports, and Ask IC
            from the same shared context.
          </p>
        </div>

        {/* 4-Step Progress Bar */}
        <div className="grid grid-cols-4 gap-2 mb-8">
          {STEPS.map((s, idx) => {
            const active = showSummary ? idx <= 2 : idx === 0 || (idx === 1 && files.length > 0)
            return (
              <div key={s.n} className={`border-t-2 pt-2.5 ${active ? 'border-[#0B5D3B]' : 'border-[#DDE6F0]'}`}>
                <div className={`text-[10px] font-black ${idx < 2 || showSummary ? 'text-[#0B5D3B]' : 'text-slate-300'}`}>{s.n}</div>
                <div className={`mt-0.5 text-xs font-bold ${idx < 2 || showSummary ? 'text-slate-800' : 'text-slate-400'}`}>{s.label}</div>
                <div className="text-[10px] text-slate-400 mt-0.5 hidden md:block">{s.description}</div>
              </div>
            )
          })}
        </div>

        <div className="grid gap-6 lg:grid-cols-2 lg:items-start">

          {/* Step 1: Assessment Type (single intake — the only place type is chosen) */}
          <section className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#DDE6F0]">
              <div>
                <div className="text-[10px] font-black uppercase tracking-wider text-[#0B5D3B]">Step 1</div>
                <h2 className="text-base font-black text-slate-900">What are you assessing?</h2>
              </div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]">
                {selectedConfig.label}
              </span>
            </div>
            <div className="grid gap-2">
              {INTAKE_ENTITY_TYPES.map(type => {
                const cfg = getEntityConfig(type)
                const selected = assessmentType === type
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => selectType(type)}
                    className={`flex items-start gap-3 min-h-14 rounded-lg border p-3 text-left transition ${
                      selected
                        ? 'border-[#0B5D3B] bg-[#ECFDF3]'
                        : 'border-[#DDE6F0] hover:border-[#0B5D3B] hover:bg-[#F5F8FC]'
                    }`}
                  >
                    <span className="text-xl mt-0.5 flex-shrink-0">{TYPE_ICONS[type]}</span>
                    <div>
                      <div className="text-sm font-extrabold text-slate-900">{cfg.label}</div>
                      <div className="mt-0.5 text-xs text-slate-500 leading-5">{cfg.description}</div>
                      {selected && (
                        <div className="mt-1 text-[10px] text-[#027A48] font-semibold">
                          Upload: {TYPE_EXAMPLES[type]}
                        </div>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </section>

          {/* Step 2: Upload + Extraction + CTA */}
          <div className="flex flex-col gap-4">
            <section className="rounded-[12px] border border-[#0E3627] bg-[#061C14] p-5 text-white shadow-saas-elevated">
              <div className="flex items-center justify-between">
                <div className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-300">Step 2</div>
                {busy && (
                  <span className="text-[10px] font-bold text-emerald-300 animate-pulse">
                    {phase === 'uploading' ? 'Uploading & extracting…' : 'Processing…'}
                  </span>
                )}
              </div>
              <h2 className="mt-2 text-xl font-black">Upload Documents</h2>
              <p className="mt-1.5 text-xs leading-5 text-emerald-100/80">
                {selectedConfig.description} Examples: <strong className="text-white">{TYPE_EXAMPLES[assessmentType]}</strong>
              </p>

              {/* Drop Zone — multiple documents */}
              <label
                onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
                onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                className={`mt-4 flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 py-4 text-center transition ${
                  dragging ? 'border-emerald-300 bg-emerald-400/20' : files.length ? 'border-emerald-400 bg-emerald-400/10' : 'border-emerald-400/40 bg-[#0A261C] hover:bg-[#0E2E22]'
                }`}
              >
                <span className="text-2xl">{files.length ? '📄' : '⬆️'}</span>
                <span className="mt-2 text-sm font-extrabold text-white">
                  {files.length ? `${files.length} document${files.length > 1 ? 's' : ''} selected` : 'Drop files here or click to browse'}
                </span>
                <span className="mt-1 text-xs text-emerald-200/70">PDF, DOCX, XLSX, CSV, PPTX, TXT — multiple files supported</span>
                <input
                  type="file"
                  multiple
                  className="hidden"
                  accept=".pdf,.docx,.xlsx,.csv,.txt,.pptx,.json"
                  onChange={e => { addFiles(e.target.files); e.target.value = '' }}
                />
              </label>

              {/* Selected file pills */}
              {files.length > 0 && (
                <div className="mt-3 flex flex-col gap-1.5">
                  {files.map((file, index) => (
                    <div key={`${file.name}-${index}`} className="flex items-center justify-between gap-2 rounded-lg bg-[#0A261C] border border-[#124231] px-3 py-2">
                      <span className="text-[11px] font-semibold text-emerald-100 truncate">{file.name}</span>
                      <span className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-[10px] text-emerald-300/70">{(file.size / 1024).toFixed(0)} KB</span>
                        <button type="button" onClick={() => removeFile(index)} className="text-emerald-300/70 hover:text-white text-[11px] font-bold">✕</button>
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Primary CTA */}
              <button
                type="button"
                onClick={handlePrimary}
                disabled={busy || (!files.length && !context?.assessmentId)}
                className="mt-4 w-full rounded-lg bg-[#12B76A] px-4 py-3.5 text-center text-sm font-black text-[#061C14] hover:bg-[#32D583] transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {busy
                  ? 'Creating assessment context…'
                  : files.length
                    ? `Create Assessment & Extract ${files.length > 1 ? `${files.length} Documents` : ''} →`
                    : context?.assessmentId
                      ? 'Open Signals Dashboard →'
                      : 'Upload documents to begin'}
              </button>
              <div className="mt-2 text-center text-[10px] text-emerald-200/50">
                {authStatus === 'authenticated'
                  ? 'Context persists once · Reused across Signals, AI Analyst, Evidence, Decision & Ask IC'
                  : 'You will sign in before upload · Your selected files are kept securely in this browser'}
              </div>

              {error && (
                <div className="mt-3 rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-[11px] font-medium text-red-200">
                  {error}
                </div>
              )}
            </section>

            {/* Shared Assessment Context — extraction is already done (Step 3–4) */}
            {showSummary && context && (
              <section className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#DDE6F0]">
                  <div className="text-[10px] font-black uppercase tracking-wider text-[#0B5D3B]">Assessment Context</div>
                  <span className={`text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded border ${
                    phase === 'confirm'
                      ? 'bg-[#FFFAEB] text-[#7A4B00] border-[#FEDF89]'
                      : 'bg-[#ECFDF3] text-[#027A48] border-[#A6F4C5]'
                  }`}>
                    {STATUS_LABELS[statusKey] || statusKey}
                  </span>
                </div>

                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
                  <dt className="text-slate-400 font-semibold">Assessment</dt>
                  <dd className="text-slate-900 font-extrabold">{context.displayEntity || context.entityName || 'Pending extraction'}</dd>
                  <dt className="text-slate-400 font-semibold">Type</dt>
                  <dd className="text-slate-900 font-bold">{context.assessmentTypeLabel || context.entityLabel}</dd>
                  <dt className="text-slate-400 font-semibold">Status</dt>
                  <dd className="text-slate-900 font-bold">{STATUS_LABELS[statusKey] || statusKey}</dd>
                  {context.confidence != null && (
                    <>
                      <dt className="text-slate-400 font-semibold">Extraction</dt>
                      <dd className="text-slate-900 font-bold">{Math.round(context.confidence * 100)}% confidence</dd>
                    </>
                  )}
                  {context.trustScore != null && (
                    <>
                      <dt className="text-slate-400 font-semibold">Trust</dt>
                      <dd className="text-slate-900 font-bold">{Math.round(context.trustScore)}/100</dd>
                    </>
                  )}
                  <dt className="text-slate-400 font-semibold">Documents</dt>
                  <dd className="text-slate-900 font-bold">
                    {uploadedDocs.length || context.documentCount || 0} uploaded
                  </dd>
                </dl>

                {/* Extracted fields — already populated, no user re-entry */}
                <div className="mt-3 pt-3 border-t border-[#DDE6F0] grid grid-cols-2 gap-2">
                  {FIELD_LABELS.map(([key, label]) => {
                    const value = (context as unknown as Record<string, string | undefined>)[key]
                    if (!value) return null
                    const fieldConfidence = context.extraction?.fields?.[key]?.confidence
                    return (
                      <div key={key} className="p-2 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                        <div className="text-[9px] font-black uppercase tracking-wider text-slate-400">
                          {label}
                          {fieldConfidence != null && <span className="ml-1 text-[#027A48] normal-case tracking-normal">{Math.round(fieldConfidence * 100)}%</span>}
                        </div>
                        <div className="text-[11px] font-bold text-slate-800 mt-0.5 leading-4 break-words">{value}</div>
                      </div>
                    )
                  })}
                </div>

                {/* Uploaded document list */}
                {uploadedDocs.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-[#DDE6F0]">
                    <div className="text-[9px] font-black uppercase tracking-wider text-slate-400 mb-1.5">Uploaded documents</div>
                    <div className="flex flex-col gap-1">
                      {uploadedDocs.map((doc, index) => (
                        <div key={doc.id || index} className="flex items-center justify-between gap-2 text-[11px]">
                          <span className="font-semibold text-slate-700 truncate">{doc.name}</span>
                          {doc.trust_score != null && (
                            <span className="text-slate-400 flex-shrink-0">Trust {Math.round(doc.trust_score)}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Low-confidence fallback: ask ONLY for what extraction missed */}
                {phase === 'confirm' && (
                  <div className="mt-3 pt-3 border-t border-[#DDE6F0]">
                    <div className="rounded-lg border border-[#FEDF89] bg-[#FFFAEB] p-3">
                      <div className="text-[11px] font-extrabold text-[#7A4B00]">
                        Extraction confidence is low — confirm the assessment identity once.
                      </div>
                      <div className="mt-2 grid gap-2">
                        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-600">
                          Entity / Organisation
                          <input
                            value={correctionEntity}
                            onChange={e => setCorrectionEntity(e.target.value)}
                            placeholder="e.g. AgriNova Malawi Ltd"
                            className="mt-1 w-full rounded-lg border border-[#DDE6F0] bg-white p-2 text-xs font-semibold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
                          />
                        </label>
                        {assessmentType === 'startup' && (
                          <label className="text-[10px] font-bold uppercase tracking-wider text-slate-600">
                            Founder Name
                            <input
                              value={correctionFounder}
                              onChange={e => setCorrectionFounder(e.target.value)}
                              placeholder="e.g. Chimwemwe Phiri"
                              className="mt-1 w-full rounded-lg border border-[#DDE6F0] bg-white p-2 text-xs font-semibold text-slate-900 focus:outline-none focus:border-[#0B5D3B]"
                            />
                          </label>
                        )}
                        <button
                          type="button"
                          onClick={handleConfirmDetails}
                          disabled={busy || !correctionEntity.trim()}
                          className="mt-1 rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-xs font-extrabold uppercase tracking-wider text-white hover:bg-[#08482E] transition disabled:opacity-50"
                        >
                          {busy ? 'Saving…' : 'Confirm & Continue'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {phase === 'ready' && (
                  <div className="mt-4 flex items-center justify-between gap-3">
                    <Link
                      href="/signals"
                      className="flex-1 rounded-lg bg-[#0B5D3B] px-4 py-3 text-center text-xs font-black uppercase tracking-wider text-white hover:bg-[#08482E] transition"
                    >
                      Open Signals & Continue →
                    </Link>
                    <button
                      type="button"
                      onClick={startNewAssessment}
                      className="rounded-lg border border-[#DDE6F0] px-3 py-3 text-[11px] font-bold text-slate-500 hover:bg-[#F5F8FC] transition"
                    >
                      New assessment
                    </button>
                  </div>
                )}
              </section>
            )}

            {/* What you'll get */}
            <section className="rounded-[12px] border border-[#DDE6F0] bg-white p-4 shadow-saas">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 mb-3">Steps 3 & 4 — What you get</div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Evidence Score', desc: 'How much usable evidence is present.' },
                  { label: 'Trust Score', desc: 'Source reliability and corroboration.' },
                  { label: '9 Signal Domains', desc: 'Trust · Risk · Opportunity · Market · Funding · Climate · Environment · Tourism · Community.' },
                  { label: 'Recommendation', desc: 'Proceed · Review · Observe · Decline.' },
                ].map(({ label, desc }) => (
                  <div key={label} className="p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                    <div className="text-xs font-extrabold text-slate-900">{label}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5 leading-4">{desc}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 p-2.5 bg-[#FFFAEB] rounded-lg border border-[#FEDF89] text-[10px] text-[#7A4B00] leading-4">
                <strong>Collected once, reused everywhere.</strong> Signals, Evidence, Decision, Reports, and Ask IC
                all run on this single assessment context — no repeated forms.
              </div>
            </section>
          </div>
        </div>

        {/* Footer links */}
        <div className="mt-8 flex items-center justify-center gap-6 text-xs text-slate-400">
          <Link href="/dashboard" className="hover:text-[#0B5D3B] font-semibold transition">Dashboard</Link>
          <Link href="/flex?run=ostx-agrinova-malawi" className="hover:text-[#0B5D3B] font-semibold transition">Demo Case (AgriNova)</Link>
          <Link href="/flex?run=pilot-healthbridge-lagos" className="hover:text-[#0B5D3B] font-semibold transition">Demo Case (HealthBridge)</Link>
        </div>
      </div>
    </main>
  )
}

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">Loading…</div>}>
      <HomeInner />
    </Suspense>
  )
}
