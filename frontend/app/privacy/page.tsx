'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import PilotWorkspaceShell from '../../components/PilotWorkspaceShell/PilotWorkspaceShell'
import { getDataOwnership, type DataOwnershipPayload } from '../../lib/enterprise'

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`
}

function Capability({ label, allowed, detail }: { label: string; allowed: boolean; detail: string }) {
  return (
    <div className={`p-3 rounded-lg border ${allowed ? 'bg-[#F0FAF4] border-[#C9EBD8]' : 'bg-[#F5F8FC] border-[#DDE6F0]'}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-slate-800">{label}</span>
        <span className={`text-[10px] font-black uppercase tracking-wider ${allowed ? 'text-[#0B5D3B]' : 'text-slate-400'}`}>
          {allowed ? 'Allowed' : 'Restricted'}
        </span>
      </div>
      <div className="text-[11px] text-slate-500 mt-1">{detail}</div>
    </div>
  )
}

export default function PrivacyOwnershipPage() {
  const { status: authStatus } = useSession()
  const [data, setData] = useState<DataOwnershipPayload | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const payload = await getDataOwnership()
      if (!cancelled) setData(payload)
    }
    if (authStatus === 'authenticated') {
      load().catch(err => setError(String(err)))
    }
    return () => { cancelled = true }
  }, [authStatus])

  if (authStatus === 'loading') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex items-center justify-center text-sm font-semibold text-slate-500">
        Checking session…
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-[#F5F8FC] flex flex-col items-center justify-center gap-4">
        <div className="text-lg font-bold text-slate-900">Sign in to use Kulima FLEX</div>
        <button
          onClick={() => signIn()}
          className="px-5 py-2.5 rounded-lg bg-[#0B5D3B] text-white font-bold hover:bg-[#08482E] transition shadow-sm"
        >
          Sign in
        </button>
      </div>
    )
  }

  return (
    <PilotWorkspaceShell
      workspace="Privacy & Data"
      title="Privacy & Data Ownership"
      description="Who owns the data in this workspace, who can see it, when it is deleted — and how external research stays safe."
    >
      {error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-[12px] border border-red-200 text-sm font-medium">{error}</div>
      ) : null}

      {!data && !error ? (
        <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas text-sm font-semibold text-slate-500">
          Loading data ownership statement…
        </div>
      ) : null}

      {data ? (
        <>
          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-[#EAF7EF] border border-[#C9EBD8] flex items-center justify-center text-[#0B5D3B] text-lg font-black shrink-0">
                §
              </div>
              <div>
                <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Our Ownership Statement</h2>
                <p className="mt-2 text-sm font-bold text-[#0B5D3B]">{data.ownership.statement}</p>
                <ul className="mt-3 space-y-1.5">
                  {data.ownership.points.map((point, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-slate-600 leading-relaxed">
                      <span className="text-[#12B76A] font-black mt-0.5">✓</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <section className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              ['Documents in custody', String(data.custody.documents), `${data.custody.documentsActive} active · ${data.custody.documentsDeleted} deleted`],
              ['Storage used', formatBytes(data.custody.storageBytes), 'Across all documents'],
              ['Assessments in workspace', String(data.custody.assessments), 'Contexts bound to this organization'],
              [
                'Retention window',
                data.retention.defaultRetentionDays ? `${data.retention.defaultRetentionDays} days` : 'Customer-controlled',
                'You decide when data is deleted',
              ],
            ].map(([label, value, hint]) => (
              <div key={label} className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
                <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{label}</div>
                <div className="mt-1.5 text-2xl font-black text-slate-900 tracking-tight">{value}</div>
                <div className="mt-1 text-[11px] text-slate-400">{hint}</div>
              </div>
            ))}
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">
                Your Controls In This Workspace
              </h2>
              <div className="space-y-2.5">
                <Capability label="Export documents & evidence bundles" allowed={data.capabilities.canExportDocuments} detail="Download a ZIP bundle with a manifest of everything held for you." />
                <Capability label="Delete documents" allowed={data.capabilities.canDeleteDocuments} detail="Soft delete first (recoverable), then permanent purge with an audited trail." />
                <Capability label="Request complete assessment deletion" allowed={data.capabilities.canDeleteAssessment} detail="Purges files, chunks, the assessment context and the linked run in one operation." />
                <Capability label="Manage users & roles" allowed={data.capabilities.canManageUsers} detail="Control who can view, assess, export or delete inside this workspace." />
                <Capability label="Manage billing & plan" allowed={data.capabilities.canManageBilling} detail="Upgrade, downgrade or cancel — data access is never held hostage by billing." />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <a
                  href="/api/v1/documents/export"
                  className="px-3 py-2 rounded-lg bg-[#0B5D3B] text-white text-xs font-bold hover:bg-[#08482E] transition"
                >
                  Export my documents
                </a>
                <Link
                  href="/evidence"
                  className="px-3 py-2 rounded-lg border border-[#DDE6F0] text-slate-700 text-xs font-bold hover:bg-[#F5F8FC] transition"
                >
                  Review evidence & delete
                </Link>
              </div>
              <p className="mt-3 text-[11px] text-slate-400">
                Deleting requires the delete-data permission (Owner or Admin). Viewers and Reviewers are read/assess only.
              </p>
            </div>

            <div className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
              <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4 pb-2.5 border-b border-[#DDE6F0]">
                External Research Policy (Tavily)
              </h2>
              <p className="text-xs text-slate-600 leading-relaxed">{data.ownership.externalResearchPolicy.statement}</p>
              <div className="mt-3 p-3 bg-[#F5F8FC] rounded-lg border border-[#DDE6F0]">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                  The only fields that ever leave the platform
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {data.ownership.externalResearchPolicy.allowedFields.map(field => (
                    <span key={field} className="px-2 py-0.5 rounded-md bg-white border border-[#DDE6F0] text-[10px] font-semibold text-slate-600">
                      {field.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
              <div className="mt-3 p-3 bg-[#FFF7EB] rounded-lg border border-[#F5DEB8]">
                <div className="text-[10px] font-bold uppercase tracking-wider text-amber-700 mb-1">Never transmitted</div>
                <ul className="text-[11px] text-amber-800 space-y-0.5">
                  <li>• Uploaded documents and extracted full text</li>
                  <li>• Financial statements, amounts and account details</li>
                  <li>• Customer data, emails and phone numbers</li>
                  <li>• Anything marked confidential</li>
                </ul>
              </div>
            </div>
          </section>

          <section className="p-5 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
            <h2 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3 pb-2.5 border-b border-[#DDE6F0]">
              Policies & Compliance Documents
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { label: 'Privacy Policy', href: '/legal/privacy-policy', hint: 'What we process and your rights' },
                { label: 'Data Retention Policy', href: '/legal/data-retention', hint: 'When and how data is deleted' },
                { label: 'Responsible AI Statement', href: '/legal/responsible-ai', hint: 'Human-in-the-loop guarantees' },
                { label: 'Evidence Transparency Policy', href: '/legal/evidence-transparency', hint: 'How conclusions are grounded' },
                { label: 'Terms of Use', href: '/legal/terms-of-use', hint: 'The platform agreement' },
                { label: 'Trust & Governance', href: '/trust', hint: 'Live security posture dashboard' },
              ].map(({ label, href, hint }) => (
                <Link
                  key={label}
                  href={href}
                  className="p-3 border border-[#DDE6F0] rounded-lg hover:bg-[#F5F8FC] hover:border-[#0B5D3B] transition"
                >
                  <div className="text-xs font-bold text-slate-800">{label}</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{hint}</div>
                </Link>
              ))}
            </div>
            <p className="mt-3 text-[11px] text-slate-400">
              Signed-in as <span className="font-semibold text-slate-600">{data.roleLabel}</span> in <span className="font-semibold text-slate-600">{data.orgName}</span>.
            </p>
          </section>
        </>
      ) : null}
    </PilotWorkspaceShell>
  )
}
