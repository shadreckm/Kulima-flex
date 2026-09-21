import React from 'react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { LEGAL_DOCS, getLegalDoc } from '../../../lib/legal-content'

type LegalDocPageProps = {
  params: { slug: string }
}

export function generateStaticParams() {
  return LEGAL_DOCS.map(doc => ({ slug: doc.slug }))
}

export function generateMetadata({ params }: LegalDocPageProps) {
  const doc = getLegalDoc(params.slug)
  if (!doc) return { title: 'Legal — Kulima FLEX' }
  return {
    title: `${doc.title} — Kulima FLEX`,
    description: doc.summary,
  }
}

export default function LegalDocPage({ params }: LegalDocPageProps) {
  const doc = getLegalDoc(params.slug)
  if (!doc) {
    notFound()
  }

  return (
    <div className="min-h-screen bg-[#F5F8FC] py-10 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <Link href="/legal" className="text-xs font-bold text-[#0B5D3B] hover:underline">
            ← All legal documents
          </Link>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Version {doc.version} · Effective {doc.effectiveDate}
          </span>
        </div>

        <article className="p-6 md:p-8 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">{doc.title}</h1>
          <p className="mt-2 text-sm text-slate-500 leading-relaxed">{doc.summary}</p>

          <div className="mt-6 space-y-6">
            {doc.sections.map(section => (
              <section key={section.heading}>
                <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">{section.heading}</h2>
                {section.paragraphs?.map((paragraph, idx) => (
                  <p key={idx} className="mt-2 text-sm text-slate-600 leading-relaxed">
                    {paragraph}
                  </p>
                ))}
                {section.bullets ? (
                  <ul className="mt-2 space-y-1.5">
                    {section.bullets.map((bullet, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-slate-600 leading-relaxed">
                        <span className="text-[#12B76A] font-black mt-0.5">•</span>
                        <span>{bullet}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            ))}
          </div>
        </article>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
          {LEGAL_DOCS.filter(other => other.slug !== doc.slug).map(other => (
            <Link
              key={other.slug}
              href={`/legal/${other.slug}`}
              className="p-3 bg-white rounded-[12px] border border-[#DDE6F0] hover:border-[#0B5D3B] transition"
            >
              <div className="text-xs font-bold text-slate-800">{other.title}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">{other.summary}</div>
            </Link>
          ))}
        </div>

        <p className="mt-6 text-[11px] text-slate-400">
          Questions about this policy? Contact your workspace Owner or the platform administrator operating your deployment.
        </p>
      </div>
    </div>
  )
}
