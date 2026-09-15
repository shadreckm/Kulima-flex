'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import KulimaLogo from '../components/KulimaLogo/KulimaLogo'
import { saveUseCase, loadUseCase, HOME_TO_ENTITY } from '../lib/use-case-store'

type UseCase = 'startup' | 'ngo' | 'government'

const USE_CASES: Array<{
  id: UseCase
  label: string
  icon: string
  description: string
  documents: string
  examples: string[]
}> = [
  {
    id: 'startup',
    label: 'Startup / Investor',
    icon: '🚀',
    description: 'Fund or partnership decision for a venture.',
    documents: 'Pitch deck, financial model, customer evidence',
    examples: ['Pitch Deck PDF', 'Audited Financials', 'Customer Contracts'],
  },
  {
    id: 'ngo',
    label: 'NGO / Donor',
    icon: '🌍',
    description: 'Review whether programme outcome claims are supported.',
    documents: 'M&E report, budget, indicator table, beneficiary data',
    examples: ['M&E Report', 'Budget Breakdown', 'Beneficiary Survey'],
  },
  {
    id: 'government',
    label: 'Government Program',
    icon: '🏛️',
    description: 'Turn survey and programme records into a reviewable evidence pack.',
    documents: 'Survey CSV, implementation report, target and results data',
    examples: ['Survey CSV', 'Programme Report', 'Results Framework'],
  },
]

const STEPS = [
  { n: '01', label: 'Choose Use Case', description: 'Select what you are reviewing.' },
  { n: '02', label: 'Upload Evidence', description: 'Drop your primary document.' },
  { n: '03', label: 'Review Findings', description: 'Evidence, trust, and signals generated instantly.' },
  { n: '04', label: 'Export Decision', description: 'Download a memo or full IC report.' },
]

export default function Home() {
  const router = useRouter()
  const [useCase, setUseCase] = useState<UseCase>('startup')
  const [step, setStep] = useState<1 | 2>(1)
  const [fileName, setFileName] = useState('')
  const [dragging, setDragging] = useState(false)

  // Restore last selection
  useEffect(() => {
    const stored = loadUseCase()
    if (stored) {
      const homeId = Object.entries(HOME_TO_ENTITY).find(([, v]) => v === stored.useCase)?.[0] as UseCase | undefined
      if (homeId) setUseCase(homeId)
    }
  }, [])

  function handleUseCaseSelect(id: UseCase) {
    setUseCase(id)
    saveUseCase(HOME_TO_ENTITY[id] ?? 'startup')
    setStep(2)
  }

  function handleFileChange(file: File | null) {
    if (!file) return
    setFileName(file.name)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFileChange(file)
  }

  const selected = USE_CASES.find(u => u.id === useCase)!

  return (
    <main className="min-h-screen bg-[#F5F8FC] text-slate-900">
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-8 md:py-12">

        {/* Header */}
        <header className="flex items-center justify-between gap-4 mb-10">
          <div className="flex items-center gap-3">
            <KulimaLogo variant="header" />
            <div>
              <div className="text-xs font-black uppercase tracking-[0.2em] text-[#0B5D3B]">Kulima FLEX</div>
              <div className="text-[11px] font-semibold text-slate-400">Evidence Intelligence Platform</div>
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
            Evidence first. AI optional.
          </div>
          <h1 className="text-3xl font-black leading-tight tracking-tight text-[#061C14] md:text-5xl max-w-2xl mx-auto">
            Turn your documents into decisions you can defend.
          </h1>
          <p className="mt-4 text-base text-slate-500 max-w-xl mx-auto leading-relaxed">
            Upload a document. Get evidence scores, trust scores, risk signals, and a recommendation — in under 60 seconds.
          </p>
        </div>

        {/* 4-Step Progress Bar */}
        <div className="grid grid-cols-4 gap-2 mb-8">
          {STEPS.map((s, idx) => (
            <div
              key={s.n}
              className={`border-t-2 pt-2.5 ${idx === 0 && step >= 1 ? 'border-[#0B5D3B]' : idx === 1 && step >= 2 ? 'border-[#0B5D3B]' : 'border-[#DDE6F0]'}`}
            >
              <div className={`text-[10px] font-black ${idx < 2 ? 'text-[#0B5D3B]' : 'text-slate-300'}`}>{s.n}</div>
              <div className={`mt-0.5 text-xs font-bold ${idx < 2 ? 'text-slate-800' : 'text-slate-400'}`}>{s.label}</div>
              <div className="text-[10px] text-slate-400 mt-0.5 hidden md:block">{s.description}</div>
            </div>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-2 lg:items-start">

          {/* Step 1: Use Case Selection */}
          <section className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#DDE6F0]">
              <div>
                <div className="text-[10px] font-black uppercase tracking-wider text-[#0B5D3B]">Step 1</div>
                <h2 className="text-base font-black text-slate-900">What are you reviewing?</h2>
              </div>
              {step === 2 && (
                <span className="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-[#ECFDF3] text-[#027A48] border border-[#A6F4C5]">
                  ✓ Selected
                </span>
              )}
            </div>
            <div className="grid gap-2">
              {USE_CASES.map(item => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleUseCaseSelect(item.id)}
                  className={`flex items-start gap-3 min-h-14 rounded-lg border p-3 text-left transition group ${
                    useCase === item.id
                      ? 'border-[#0B5D3B] bg-[#ECFDF3]'
                      : 'border-[#DDE6F0] hover:border-[#0B5D3B] hover:bg-[#F5F8FC]'
                  }`}
                >
                  <span className="text-xl mt-0.5 flex-shrink-0">{item.icon}</span>
                  <div>
                    <div className="text-sm font-extrabold text-slate-900">{item.label}</div>
                    <div className="mt-0.5 text-xs text-slate-500 leading-5">{item.description}</div>
                    {useCase === item.id && (
                      <div className="mt-1 text-[10px] text-[#027A48] font-semibold">
                        Upload: {item.documents}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </section>

          {/* Step 2: Upload + CTA */}
          <div className="flex flex-col gap-4">
            <section className="rounded-[12px] border border-[#0E3627] bg-[#061C14] p-5 text-white shadow-saas-elevated">
              <div className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-300">Step 2</div>
              <h2 className="mt-2 text-xl font-black">Upload Evidence</h2>
              <p className="mt-1.5 text-xs leading-5 text-emerald-100/80">
                {selected.description} Upload: <strong className="text-white">{selected.documents}</strong>
              </p>

              {/* Drop Zone */}
              <label
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                className={`mt-4 flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 text-center transition ${
                  dragging ? 'border-emerald-300 bg-emerald-400/20' : fileName ? 'border-emerald-400 bg-emerald-400/10' : 'border-emerald-400/40 bg-[#0A261C] hover:bg-[#0E2E22]'
                }`}
              >
                {fileName ? (
                  <>
                    <span className="text-lg">📄</span>
                    <span className="mt-1 text-sm font-extrabold text-emerald-200">{fileName}</span>
                    <span className="text-[10px] text-emerald-300/70 mt-0.5">Click to change</span>
                  </>
                ) : (
                  <>
                    <span className="text-2xl">⬆️</span>
                    <span className="mt-2 text-sm font-extrabold text-white">Drop file here or click to browse</span>
                    <span className="mt-1 text-xs text-emerald-200/70">PDF, DOCX, XLSX, CSV, PPTX, TXT — up to 25 MB</span>
                    <span className="mt-1.5 text-[10px] text-emerald-300/60 font-semibold">
                      Examples: {selected.examples.join(' · ')}
                    </span>
                  </>
                )}
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.xlsx,.csv,.txt,.pptx,.json"
                  onChange={e => handleFileChange(e.target.files?.[0] ?? null)}
                />
              </label>

              {/* Primary CTA */}
              <Link
                href={
                  fileName
                    ? `/api/auth/signin?callbackUrl=${encodeURIComponent('/evidence')}`
                    : `/api/auth/signin?callbackUrl=${encodeURIComponent('/flex')}`
                }
                className="mt-4 block rounded-lg bg-[#12B76A] px-4 py-3.5 text-center text-sm font-black text-[#061C14] hover:bg-[#32D583] transition"
              >
                {fileName ? `Review Evidence for "${fileName.slice(0, 30)}${fileName.length > 30 ? '…' : ''}"` : 'Start Evidence Review →'}
              </Link>
              <div className="mt-2 text-center text-[10px] text-emerald-200/50">
                Scores generate instantly · No AI credits required for document mode
              </div>
            </section>

            {/* What you'll get */}
            <section className="rounded-[12px] border border-[#DDE6F0] bg-white p-4 shadow-saas">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 mb-3">Steps 3 & 4 — What you get</div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Evidence Score', desc: 'How much usable evidence is present.' },
                  { label: 'Trust Score', desc: 'Source reliability and corroboration.' },
                  { label: 'Risk Score', desc: 'Contradictions and warning signals.' },
                  { label: 'Recommendation', desc: 'Invest · Observe · Pass · Review Required.' },
                ].map(({ label, desc }) => (
                  <div key={label} className="p-2.5 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                    <div className="text-xs font-extrabold text-slate-900">{label}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5 leading-4">{desc}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 p-2.5 bg-[#FFFAEB] rounded-lg border border-[#FEDF89] text-[10px] text-[#7A4B00] leading-4">
                <strong>Missing evidence comes first.</strong> FLEX shows gaps before recommendations. Works fully offline.
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
