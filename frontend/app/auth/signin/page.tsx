'use client'

import { signIn } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import KulimaLogo from '../../../components/KulimaLogo/KulimaLogo'

export default function SignInPage() {
  const searchParams = useSearchParams()
  const callbackUrl = searchParams.get('callbackUrl') || '/dashboard'

  return (
    <main className="min-h-screen bg-[#F5F8FC] px-5 py-12 text-slate-900">
      <section className="mx-auto flex min-h-[70vh] max-w-md flex-col items-center justify-center rounded-[12px] border border-[#DDE6F0] bg-white p-8 text-center shadow-saas">
        <KulimaLogo variant="hero" />
        <div className="mt-5 text-xs font-black uppercase tracking-[0.2em] text-[#0B5D3B]">Kulima FLEX</div>
        <h1 className="mt-3 text-2xl font-black text-[#061C14]">Sign in to review your evidence</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">Use Google to access your assessments, evidence reviews, recommendations, exports, and feedback.</p>
        <button
          type="button"
          onClick={() => signIn('google', { callbackUrl })}
          className="mt-7 min-h-11 w-full rounded-lg bg-[#0B5D3B] px-5 py-3 text-sm font-extrabold text-white shadow-sm hover:bg-[#08482E]"
        >
          Continue with Google
        </button>
      </section>
    </main>
  )
}