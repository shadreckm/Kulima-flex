'use client'

import Link from 'next/link'
import { useState } from 'react'
import KulimaLogo from '../components/KulimaLogo/KulimaLogo'

type UseCase = 'startup' | 'ngo' | 'government'
type ProcessingMode = 'verified' | 'evidence' | 'assisted'

const USE_CASES: Array<{ id: UseCase; label: string; description: string; documents: string }> = [
  { id: 'startup', label: 'Startup / Investor', description: 'Assess a venture before a funding or partnership decision.', documents: 'Pitch deck, financial model, customer or regulatory evidence' },
  { id: 'ngo', label: 'NGO / Donor', description: 'Review whether program and outcome claims are supported.', documents: 'M&E report, budget, indicator table, beneficiary data' },
  { id: 'government', label: 'Government Program', description: 'Turn survey and program records into a reviewable evidence pack.', documents: 'Survey CSV, implementation report, target and results data' },
]

const MODES: Array<{ id: ProcessingMode; label: string; description: string }> = [
  { id: 'verified', label: 'Verified Assessment', description: 'Evidence checked against corroborating sources and review controls.' },
  { id: 'evidence', label: 'Evidence Assessment', description: 'Deterministic document, metadata, structure, and completeness checks.' },
  { id: 'assisted', label: 'AI Assisted Assessment', description: 'Evidence checks plus optional live research and model analysis.' },
]

const SCORES = [
  ['Evidence Score', 'How much usable, decision-relevant evidence is present.'],
  ['Trust Score', 'How reliable the sources and cross-document corroboration appear.'],
  ['Risk Score', 'How many material contradictions, gaps, or warning signals require attention.'],
  ['Completeness Score', 'How many expected information categories are covered for this use case.'],
]

export default function Home() {
  const [useCase, setUseCase] = useState<UseCase>('startup')
  const [mode, setMode] = useState<ProcessingMode>('evidence')
  const [fileName, setFileName] = useState('')
  const selectedUseCase = USE_CASES.find(item => item.id === useCase)!

  return (
    <main className="min-h-screen bg-[#F5F8FC] text-slate-900">
      <section className="mx-auto max-w-7xl px-5 py-8 md:px-8 md:py-12">
        <header className="flex items-center justify-between gap-4">
          <div>
            <KulimaLogo variant="header" />
            <div className="text-xs font-black uppercase tracking-[0.2em] text-[#0B5D3B]">Kulima FLEX</div>
            <div className="mt-1 text-sm font-bold text-slate-500">Evidence Intelligence Platform</div>
          </div>
          <Link href="/dashboard" className="text-xs font-extrabold text-[#0B5D3B] hover:underline">Open Dashboard</Link>
        </header>

        <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,1fr)_420px] lg:items-start">
          <div>
            <div className="inline-flex rounded-full border border-[#A6F4C5] bg-[#ECFDF3] px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-[#027A48]">Evidence first. AI optional.</div>
            <h1 className="mt-5 max-w-3xl text-4xl font-black leading-tight tracking-tight text-[#061C14] md:text-6xl">Turn messy documents into decisions you can defend.</h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">FLEX checks reports, financials, surveys, and program data for evidence quality, missing information, contradictions, risk, and decision readiness. It remains useful when live AI services are unavailable.</p>

            <div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-6">
              {['Choose use case', 'Upload documents', 'Evidence review', 'Trust & risk', 'Recommendation', 'Export'].map((step, index) => (
                <div key={step} className="border-t-2 border-[#0B5D3B] pt-2">
                  <div className="text-[10px] font-black text-[#0B5D3B]">0{index + 1}</div>
                  <div className="mt-1 text-xs font-bold text-slate-700">{step}</div>
                </div>
              ))}
            </div>

            <section className="mt-10 rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
              <div className="flex flex-col gap-2 border-b border-[#DDE6F0] pb-4 sm:flex-row sm:items-end sm:justify-between"><div><div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Step 1</div><h2 className="mt-1 text-lg font-black text-slate-900">Choose what you are reviewing</h2></div><div className="text-xs font-semibold text-slate-500">Your checklist adapts to the use case.</div></div>
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                {USE_CASES.map(item => <button key={item.id} type="button" onClick={() => setUseCase(item.id)} className={`min-h-11 rounded-lg border p-3 text-left transition ${useCase === item.id ? 'border-[#0B5D3B] bg-[#ECFDF3]' : 'border-[#DDE6F0] hover:border-[#0B5D3B]'}`}><div className="text-sm font-extrabold text-slate-900">{item.label}</div><div className="mt-1 text-xs leading-5 text-slate-500">{item.description}</div></button>)}
              </div>
              <div className="mt-4 rounded-lg bg-[#F5F8FC] p-3 text-xs text-slate-600"><span className="font-extrabold text-slate-900">Upload next:</span> {selectedUseCase.documents}</div>
            </section>
          </div>

          <aside className="rounded-[12px] border border-[#0E3627] bg-[#061C14] p-5 text-white shadow-saas-elevated lg:sticky lg:top-6">
            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-300">Step 2</div><h2 className="mt-2 text-2xl font-black">Upload Evidence</h2><p className="mt-2 text-sm leading-6 text-emerald-100/80">Start with the strongest primary document. Add a second independent document to improve corroboration.</p>
            <label className="mt-5 flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-emerald-400/50 bg-[#0A261C] px-4 text-center hover:bg-[#0E2E22]"><span className="text-sm font-extrabold text-white">{fileName || 'Choose a report, model, survey, or deck'}</span><span className="mt-2 text-xs text-emerald-200/70">PDF, DOCX, XLSX, CSV, PPTX, TXT or JSON</span><input type="file" className="hidden" accept=".pdf,.docx,.xlsx,.csv,.txt,.pptx,.json" onChange={event => setFileName(event.target.files?.[0]?.name || '')} /></label>
            <div className="mt-5 text-[10px] font-black uppercase tracking-wider text-emerald-300">Processing mode</div><div className="mt-2 grid gap-2">{MODES.map(item => <button key={item.id} type="button" onClick={() => setMode(item.id)} className={`min-h-11 rounded-lg border px-3 py-2 text-left ${mode === item.id ? 'border-emerald-300 bg-emerald-400/15' : 'border-emerald-900 bg-[#0A261C] hover:border-emerald-600'}`}><div className="text-xs font-extrabold text-white">{item.label}</div><div className="mt-0.5 text-[11px] leading-4 text-emerald-100/70">{item.description}</div></button>)}</div>
            <Link href={fileName ? '/auth/signin?callbackUrl=%2Fevidence' : '/auth/signin?callbackUrl=%2Fflex'} className="mt-5 block rounded-lg bg-[#12B76A] px-4 py-3 text-center text-sm font-black text-[#061C14] hover:bg-[#32D583]">{fileName ? 'Open Evidence Review' : 'Upload Evidence'}</Link><div className="mt-3 text-center text-[11px] text-emerald-200/60">Selected mode: {MODES.find(item => item.id === mode)?.label}</div>
          </aside>
        </div>

        <section className="mt-14">
          <div className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas"><div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Step 3-5</div><h2 className="mt-1 text-xl font-black text-slate-900">What the review produces</h2><div className="mt-5 grid gap-3 sm:grid-cols-2">{SCORES.map(([label, explanation]) => <div key={label} className="rounded-lg border border-[#DDE6F0] bg-[#F5F8FC] p-3"><div className="text-sm font-extrabold text-slate-900">{label}</div><div className="mt-1 text-xs leading-5 text-slate-500">{explanation}</div></div>)}</div><div className="mt-4 rounded-lg border border-[#FEDF89] bg-[#FFFAEB] p-3 text-xs leading-5 text-[#7A4B00]"><span className="font-black">Missing evidence comes first.</span> FLEX shows gaps and verification questions before it presents Invest, Observe, Pass, or Review Required.</div></div>
          <div className="mt-4 rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas"><div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Step 6</div><h2 className="mt-1 text-xl font-black text-slate-900">Ready to review your evidence?</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">Upload your first pitch deck, NGO report, survey, business plan, or program report. Your assessment starts with your own documents.</p></div>
        </section>
      </section>
    </main>
  )
}
