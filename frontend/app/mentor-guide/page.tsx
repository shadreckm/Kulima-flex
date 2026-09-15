import Link from 'next/link'
import KulimaLogo from '../../components/KulimaLogo/KulimaLogo'

const steps = [
  ['01', 'Choose a use case', 'Start with Startup / Investor, NGO / Donor, or Government Program. FLEX changes the evidence checklist to match the decision you need to make.'],
  ['02', 'Upload primary evidence', 'Use a report, financial model, survey, pitch deck, audit, license, or indicator table. Add a second independent document when available.'],
  ['03', 'Review the evidence', 'Check what is present, what is missing, which claims are unsupported, and whether sources agree. Missing evidence is shown before a recommendation.'],
  ['04', 'Read trust and risk', 'Evidence Score measures usefulness. Trust Score measures reliability. Risk Score highlights contradictions and warning signals. Completeness Score measures coverage.'],
  ['05', 'Choose the next action', 'Use Invest, Observe, Pass, or Review Required as a decision aid, not an automatic verdict. Open the verification checklist before acting.'],
  ['06', 'Export and learn', 'Download the decision brief or diligence report, then record the eventual outcome so future decisions can be calibrated.'],
]

export default function MentorGuidePage() {
  return (
    <main className="min-h-screen bg-[#F5F8FC] text-slate-900">
      <section className="mx-auto max-w-5xl px-5 py-8 md:px-8 md:py-12">
        <Link href="/" className="text-xs font-extrabold text-[#0B5D3B] hover:underline">Back to Evidence Review</Link>
        <div className="mt-6"><KulimaLogo variant="header" /></div>
        <div className="mt-10 max-w-3xl">
          <div className="text-xs font-black uppercase tracking-[0.2em] text-[#0B5D3B]">Mentor onboarding guide</div>
          <h1 className="mt-4 text-4xl font-black leading-tight tracking-tight text-[#061C14] md:text-5xl">Make one decision you can defend.</h1>
          <p className="mt-5 text-lg leading-8 text-slate-600">Spend five minutes moving your own documents from evidence to trust, risk, recommendation, and export. FLEX remains useful in Evidence Assessment mode when live AI services are unavailable.</p>
        </div>

        <section className="mt-10 grid gap-4 md:grid-cols-2">
          {steps.map(([number, title, description]) => (
            <div key={number} className="rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
              <div className="text-xs font-black text-[#0B5D3B]">{number}</div>
              <h2 className="mt-2 text-lg font-black text-slate-900">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
            </div>
          ))}
        </section>

        <section className="mt-10 rounded-[12px] border border-[#0E3627] bg-[#061C14] p-5 text-white shadow-saas-elevated">
          <div className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300">Five-minute walkthrough</div>
          <div className="mt-4 grid gap-4 md:grid-cols-5">
            {['Problem: decisions rely on messy evidence.', 'Platform: score evidence before opinion.', 'Workflow: inspect one case.', 'Output: export a review-ready brief.', 'Impact: act, verify, and learn.'].map((line, index) => (
              <div key={line} className="border-l border-emerald-400/40 pl-3 text-sm leading-6 text-emerald-50"><span className="font-black text-emerald-300">{index + 1}.</span> {line}</div>
            ))}
          </div>
        </section>

        <section className="mt-10 rounded-[12px] border border-[#DDE6F0] bg-white p-5 shadow-saas">
          <h2 className="text-xl font-black text-slate-900">Start with your documents</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">Upload your first pitch deck, NGO report, survey, business plan, or program report. Your assessment is built from your evidence, not a shared demo case.</p>
          <Link href="/" className="mt-4 inline-block rounded-lg bg-[#0B5D3B] px-4 py-2.5 text-xs font-extrabold text-white hover:bg-[#08482E]">Upload Evidence</Link>
        </section>
      </section>
    </main>
  )
}
