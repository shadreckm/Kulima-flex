'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import KulimaLogo from '../components/KulimaLogo/KulimaLogo'
import { saveUseCase } from '../lib/use-case-store'
import { INTAKE_ENTITY_TYPES, entityToAssessmentType, getEntityConfig, type EntityType } from '../lib/entity-types'
import { clearIntakeDraft, loadIntakeDraft, saveIntakeContext, saveIntakeDraft, type AssessmentContext } from '../lib/assessment-store'
import * as api from '../lib/api'

const TYPE_LABELS: Record<EntityType, string> = {
  startup: 'Startup', ngo: 'NGO', government_program: 'Government Programme', development_program: 'Development Programme', tourism_sme: 'Tourism SME', accelerator: 'Accelerator',
}

const FLOW = [
  { number: '01', title: 'Upload Documents', detail: 'Business plans, reports, proposals, financials' },
  { number: '02', title: 'Analyze Evidence', detail: 'Extract entities, score trust, detect risks' },
  { number: '03', title: 'Research Context', detail: 'Market, climate, tourism and web signals' },
  { number: '04', title: 'Generate Decisions', detail: 'Readiness, risk assessment and action plan' },
]

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
  const resumeHandled = useRef(false)

  const runIntake = useCallback(async (type: EntityType, selectedFiles: File[]) => {
    setBusy(true); setMessage(null)
    try {
      const payload = await api.createAssessment(selectedFiles, entityToAssessmentType(type))
      setContext(saveIntakeContext(payload)); await clearIntakeDraft(); setFiles([])
      setMessage('Documents uploaded. Your decision workspace is ready.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed. Please try again.')
    } finally { setBusy(false) }
  }, [])

  useEffect(() => {
    if (resumeHandled.current || searchParams.get('resume') !== 'intake' || authStatus !== 'authenticated') return
    resumeHandled.current = true
    void (async () => {
      const draft = await loadIntakeDraft()
      if (draft?.files.length) await runIntake(draft.assessmentType, draft.files)
      else setMessage('Your previous upload session expired. Please select your documents again.')
      router.replace('/')
    })()
  }, [authStatus, searchParams, router, runIntake])

  function addFiles(incoming: FileList | null) {
    if (!incoming?.length) return
    setFiles(previous => [...previous, ...Array.from(incoming).filter(file => !previous.some(item => item.name === file.name && item.size === file.size))])
    setMessage(null)
  }

  async function handleUpload() {
    if (!files.length || busy) return
    saveUseCase(assessmentType)
    if (authStatus === 'authenticated') await runIntake(assessmentType, files)
    else { await saveIntakeDraft(assessmentType, files); router.push(`/api/auth/signin?callbackUrl=${encodeURIComponent('/?resume=intake')}`) }
  }

  return (
    <main className="min-h-screen bg-white text-[#101828]">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-10">
        <Link href="/" className="flex items-center gap-3" aria-label="Kulima FLEX home"><KulimaLogo variant="header" /><span className="text-sm font-bold tracking-tight">Kulima <span className="text-[#159A62]">FLEX</span></span></Link>
        <nav className="hidden items-center gap-8 text-sm font-medium text-[#667085] md:flex"><a href="#solutions">Solutions</a><a href="#pricing">Pricing</a><a href="#cases">Case Studies</a><a href="#about">About</a></nav>
        <div className="flex items-center gap-3"><Link href="/api/auth/signin" className="hidden px-3 py-2 text-sm font-semibold text-[#344054] sm:block">Login</Link><a href="#intake" className="rounded-lg bg-[#101828] px-4 py-2.5 text-sm font-bold text-white transition hover:bg-[#1D2939]">Get Started</a></div>
      </header>

      <section id="intake" className="border-b border-[#EAECF0] bg-[radial-gradient(circle_at_80%_20%,#EAF8F0_0,transparent_32%),#fff]">
        <div className="mx-auto grid max-w-7xl gap-14 px-6 pb-20 pt-14 lg:grid-cols-[1fr_0.86fr] lg:items-center lg:px-10 lg:pb-28 lg:pt-24">
          <div><div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#B7E6CC] bg-[#F0FBF4] px-3 py-1.5 text-xs font-bold uppercase tracking-[0.14em] text-[#117A4B]"><span className="size-1.5 rounded-full bg-[#159A62]" /> Evidence and Decision Intelligence</div><h1 className="max-w-3xl text-5xl font-semibold leading-[1.02] tracking-[-0.055em] text-[#101828] sm:text-6xl lg:text-7xl">Turn documents into <span className="text-[#159A62]">defensible decisions.</span></h1><p className="mt-7 max-w-2xl text-lg leading-8 text-[#667085]">Upload reports, proposals, business plans, financial statements, or programme documents. Kulima FLEX combines document intelligence, external research, trust scoring, climate signals, tourism intelligence, and AI analysis to generate decision-ready insights.</p><div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-semibold text-[#344054]"><span>✓ Evidence Intelligence</span><span>✓ Research Intelligence</span><span>✓ Decision Intelligence</span></div><div className="mt-9 flex flex-wrap gap-3"><a href="#intake" className="rounded-lg bg-[#159A62] px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-[#117A4B]">Get Started <span aria-hidden="true">→</span></a><a href="#how-it-works" className="rounded-lg border border-[#D0D5DD] px-5 py-3 text-sm font-bold text-[#344054] transition hover:bg-[#F9FAFB]">Watch Demo <span aria-hidden="true">▷</span></a></div></div>
          <div className="rounded-2xl border border-[#D0D5DD] bg-white p-3 shadow-[0_24px_70px_-28px_rgba(16,24,40,0.3)]"><div className="rounded-xl bg-[#F8FAFC] p-5 sm:p-7"><div className="flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-[#159A62]">Start an assessment</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">Bring the evidence.</h2></div><div className="rounded-lg border border-[#B7E6CC] bg-white px-2.5 py-1 text-[10px] font-bold text-[#117A4B]">SECURE INTAKE</div></div><label onDrop={event => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files) }} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} className={`mt-6 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-5 text-center transition ${dragging ? 'border-[#159A62] bg-[#EAF8F0]' : 'border-[#98A2B3] bg-white hover:border-[#159A62]'}`}><span className="flex size-10 items-center justify-center rounded-full bg-[#EAF8F0] text-xl text-[#159A62]" aria-hidden="true">↑</span><span className="mt-3 text-sm font-bold text-[#344054]">Drop documents here or browse</span><span className="mt-1 text-xs text-[#98A2B3]">PDF · DOCX · PPTX · XLSX</span><input type="file" multiple accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.json" className="hidden" onChange={event => { addFiles(event.target.files); event.target.value = '' }} /></label>{files.length > 0 && <div className="mt-3 flex flex-col gap-2">{files.map((file, index) => <div key={`${file.name}-${index}`} className="flex items-center justify-between rounded-lg border border-[#D0D5DD] bg-white px-3 py-2 text-xs"><span className="truncate font-semibold">{file.name}</span><button type="button" onClick={() => setFiles(previous => previous.filter((_, item) => item !== index))} className="ml-3 font-bold text-[#98A2B3] hover:text-[#D92D20]" aria-label={`Remove ${file.name}`}>×</button></div>)}</div>}<button type="button" onClick={handleUpload} disabled={!files.length || busy} className="mt-4 w-full rounded-lg bg-[#101828] px-4 py-3 text-sm font-bold text-white transition hover:bg-[#1D2939] disabled:cursor-not-allowed disabled:opacity-40">{busy ? 'Analyzing documents…' : files.length ? 'Analyze documents →' : 'Select documents to begin'}</button>{message && <p className="mt-3 text-center text-xs font-semibold text-[#117A4B]">{message}</p>}<div className="mt-7 grid grid-cols-5 gap-1 text-center">{['Uploaded','Extracted','Researched','Signals','Decision'].map((label, index) => <div key={label}><div className={`mx-auto flex size-7 items-center justify-center rounded-full text-xs font-bold ${index === 0 && files.length ? 'bg-[#159A62] text-white' : 'bg-[#E4E7EC] text-[#667085]'}`}>{index + 1}</div><p className="mt-2 text-[10px] font-semibold text-[#667085]">{label}</p></div>)}</div></div></div>
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-7xl px-6 py-20 lg:px-10"><div className="max-w-xl"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">From evidence to action</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">A clear path from document to decision.</h2></div><div className="mt-12 grid gap-0 border-y border-[#EAECF0] md:grid-cols-4">{FLOW.map((item, index) => <div key={item.number} className={`relative border-[#EAECF0] py-7 md:px-6 ${index > 0 ? 'md:border-l' : ''}`}><span className="text-xs font-bold text-[#159A62]">{item.number}</span><h3 className="mt-5 text-lg font-bold">{item.title}</h3><p className="mt-2 text-sm leading-6 text-[#667085]">{item.detail}</p></div>)}</div></section>

      <section id="solutions" className="border-y border-[#EAECF0] bg-[#F8FAFC]"><div className="mx-auto max-w-7xl px-6 py-20 lg:px-10"><div className="flex flex-col justify-between gap-8 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">Built for your context</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Choose the decision you need to make.</h2></div><p className="max-w-md text-sm leading-6 text-[#667085]">Start with a focused intake. The deeper evidence, trust, and confidence workspace comes after your documents are analyzed.</p></div><div className="mt-10 flex flex-wrap gap-3">{INTAKE_ENTITY_TYPES.filter(type => type !== 'accelerator').map(type => <button key={type} type="button" onClick={() => { setAssessmentType(type); saveUseCase(type) }} className={`rounded-full border px-4 py-2.5 text-sm font-semibold transition ${assessmentType === type ? 'border-[#159A62] bg-[#EAF8F0] text-[#117A4B]' : 'border-[#D0D5DD] bg-white text-[#344054] hover:border-[#159A62]'}`}>{TYPE_LABELS[type]}</button>)}</div></div></section>

      <section id="about" className="mx-auto grid max-w-7xl gap-14 px-6 py-20 lg:grid-cols-2 lg:px-10"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">Why FLEX</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Not just another AI summary.</h2><p className="mt-5 max-w-lg text-base leading-7 text-[#667085]">ChatGPT helps you write. Kulima FLEX helps you decide — with a transparent evidence layer built for high-consequence work.</p></div><div className="overflow-hidden rounded-2xl border border-[#D0D5DD]"><div className="grid grid-cols-2 border-b border-[#D0D5DD] bg-[#F8FAFC] text-sm font-bold"><div className="p-5 text-[#667085]">ChatGPT</div><div className="border-l border-[#D0D5DD] p-5 text-[#117A4B]">Kulima FLEX</div></div>{['Generates text', 'Summarizes documents', 'One perspective'].map((item, index) => <div key={item} className="grid grid-cols-2 border-b border-[#EAECF0] last:border-0"><div className="p-5 text-sm text-[#667085]">{item}</div><div className="border-l border-[#EAECF0] p-5 text-sm font-semibold text-[#344054]">{['Generates decisions', 'Scores evidence', 'Trust · Risk · Climate · Tourism · Impact'][index]}</div></div>)}</div></section>

      <section id="pricing" className="border-t border-[#EAECF0] bg-[#101828] text-white"><div className="mx-auto max-w-7xl px-6 py-20 lg:px-10"><div className="max-w-xl"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#7BE0A9]">Simple plans</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Decision intelligence that scales with you.</h2></div><div className="mt-10 grid gap-4 md:grid-cols-3">{[['Starter','Limited assessments'],['Professional','Advanced signals · Reports · Ask IC'],['Enterprise','Organizations · RBAC · Audit logs · Private workspace']].map(([name, detail], index) => <div key={name} className={`rounded-xl border p-6 ${index === 1 ? 'border-[#159A62] bg-[#143B2B]' : 'border-[#344054] bg-[#182230]'}`}><h3 className="text-lg font-bold">{name}</h3><p className="mt-3 text-sm leading-6 text-[#D0D5DD]">{detail}</p><a href="#intake" className="mt-8 inline-block text-sm font-bold text-[#7BE0A9]">Get started →</a></div>)}</div></div></section>

      <footer className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-8 text-sm text-[#667085] sm:flex-row sm:items-center sm:justify-between lg:px-10"><div className="flex items-center gap-3"><KulimaLogo variant="header" /><span>© 2026 Kulima FLEX</span></div><div className="flex gap-5"><Link href="/trust">Security</Link><Link href="/dashboard">Dashboard</Link><Link href="/flex?run=ostx-agrinova-malawi">Case study</Link></div></footer>
    </main>
  )
}

export default function Home() { return <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-[#667085]">Loading…</div>}><HomeInner /></Suspense> }
