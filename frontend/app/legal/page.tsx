import React from 'react'
import Link from 'next/link'
import { LEGAL_DOCS } from '../../lib/legal-content'

export const metadata = {
  title: 'Legal & Compliance — Kulima FLEX',
  description: 'Privacy Policy, Terms of Use, Data Retention, Responsible AI and Evidence Transparency for Kulima FLEX.',
}

export default function LegalIndexPage() {
  return (
    <div className="min-h-screen bg-[#F5F8FC] py-10 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <Link href="/" className="text-xs font-bold text-[#0B5D3B] hover:underline">
            ← Back to Kulima FLEX
          </Link>
        </div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Legal &amp; Compliance</h1>
        <p className="mt-1.5 text-sm text-slate-500">
          Built-in policies that govern how Kulima FLEX handles data, decisions and evidence. These pages are part of
          the product — they are always available and versioned with the platform.
        </p>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
          {LEGAL_DOCS.map(doc => (
            <Link
              key={doc.slug}
              href={`/legal/${doc.slug}`}
              className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas hover:border-[#0B5D3B] transition"
            >
              <div className="text-sm font-extrabold text-slate-900">{doc.title}</div>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">{doc.summary}</p>
              <div className="mt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Version {doc.version} · Effective {doc.effectiveDate}
              </div>
            </Link>
          ))}
        </div>

        <p className="mt-6 text-[11px] text-slate-400">
          Data custody controls live in the product: see{' '}
          <Link href="/privacy" className="font-bold text-[#0B5D3B] hover:underline">Privacy &amp; Data Ownership</Link> and{' '}
          <Link href="/trust" className="font-bold text-[#0B5D3B] hover:underline">Trust &amp; Governance</Link>.
        </p>
      </div>
    </div>
  )
}
