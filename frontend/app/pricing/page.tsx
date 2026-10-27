import Link from 'next/link'
import KulimaLogo from '../../components/KulimaLogo/KulimaLogo'

// Public pricing page (Billing Phase 1). Plans mirror the backend catalog in
// kulima/core/billing/plans.py — Professional and Enterprise pay via PayChangu
// hosted links (SC-GDDYA0 / SC-MBXJF6) wired through /billing.

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    price: '$0',
    period: 'forever free',
    target: 'Students · Researchers · Small NGOs',
    features: [
      '3 assessments per month',
      '1 user',
      'Document Intelligence Mode',
      'Basic signals',
      'Basic reports',
      'Community signals',
      'Assessment history (30 days)',
    ],
    cta: 'Start free',
    href: '/auth/signin',
  },
  {
    id: 'pro',
    name: 'Professional',
    price: '$49',
    period: 'per month',
    target: 'NGOs · Development Programs · Tourism SMEs · Consultants',
    features: [
      'Unlimited assessments',
      'AI Analyst',
      'Advanced signals',
      'Reports',
      'Conversation history',
      'Collaboration',
      'Research Intelligence',
      'Priority support',
    ],
    cta: 'Upgrade to Professional',
    href: '/billing',
    featured: true,
    paychangu: 'pay.paychangu.com/SC-GDDYA0',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'Custom',
    period: 'minimum $250 equivalent onboarding',
    target: 'Governments · DFIs · Universities · Donors · Large NGOs',
    features: [
      'Organization approval & custom agreement',
      'Enterprise activation workflow',
      'API Access',
      'Role-Based Access Control (RBAC)',
      'Trust & Governance Dashboard',
      'Custom Reports',
      'Dedicated Workspace',
      'Advanced Tourism Intelligence',
      'Advanced Climate Intelligence',
      'Multi-Organization Support',
    ],
    cta: 'Activate Enterprise',
    href: '/billing',
    paychangu: 'pay.paychangu.com/SC-MBXJF6',
  },
]

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-white text-[#101828]">
      <header className="border-b border-[#EAECF0]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-10">
          <Link href="/" aria-label="Kulima FLEX home"><KulimaLogo variant="header" /></Link>
          <nav className="flex items-center gap-6 text-sm font-medium text-[#667085]">
            <Link href="/" className="hover:text-[#101828]">Home</Link>
            <Link href="/flex" className="hover:text-[#101828]">Workspace</Link>
            <Link href="/billing" className="rounded-lg bg-[#101828] px-4 py-2 text-sm font-bold text-white hover:bg-[#1D2939]">Sign in to manage billing</Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-7xl px-6 pb-6 pt-16 lg:px-10">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#159A62]">Plans &amp; Pricing</p>
          <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-[-0.035em]">Decision intelligence that scales with your mission.</h1>
          <p className="mt-4 max-w-2xl text-base text-[#667085]">
            Start free with document intelligence. Upgrade when your team needs unlimited assessments, the AI Analyst and enterprise governance.
            Payments are processed securely by PayChangu.
          </p>
        </section>

        <section className="mx-auto grid max-w-7xl gap-5 px-6 py-12 lg:grid-cols-3 lg:px-10">
          {PLANS.map(plan => (
            <div
              key={plan.id}
              className={`flex flex-col rounded-2xl border p-7 ${
                plan.featured ? 'border-[#159A62] bg-[#F0FBF4] shadow-[0_20px_50px_-24px_rgba(21,154,98,0.5)]' : 'border-[#D0D5DD] bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold">{plan.name}</h2>
                {plan.featured ? (
                  <span className="rounded-full bg-[#159A62] px-3 py-1 text-[10px] font-black uppercase tracking-wider text-white">Most popular</span>
                ) : null}
              </div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-4xl font-semibold tracking-tight">{plan.price}</span>
                <span className="text-sm text-[#667085]">{plan.period}</span>
              </div>
              <p className="mt-3 text-xs font-bold uppercase tracking-wider text-[#667085]">Built for: {plan.target}</p>
              <ul className="mt-6 flex-1 space-y-2.5 text-sm text-[#344054]">
                {plan.features.map(feature => (
                  <li key={feature} className="flex items-start gap-2">
                    <span className="mt-0.5 font-black text-[#159A62]">✓</span>
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={plan.href}
                className={`mt-8 inline-block rounded-xl px-5 py-3 text-center text-sm font-bold transition ${
                  plan.featured
                    ? 'bg-[#159A62] text-white hover:bg-[#117A4B]'
                    : 'border border-[#D0D5DD] text-[#344054] hover:border-[#159A62] hover:text-[#117A4B]'
                }`}
              >
                {plan.cta} →
              </Link>
              {plan.paychangu ? (
                <p className="mt-3 text-center text-[10px] text-[#98A2B3]">Secure checkout via PayChangu · {plan.paychangu}</p>
              ) : null}
            </div>
          ))}
        </section>

        <section className="border-t border-[#EAECF0] bg-[#F9FAFB]">
          <div className="mx-auto max-w-3xl px-6 py-12 text-center">
            <h2 className="text-xl font-semibold tracking-tight">Questions about plans or billing?</h2>
            <p className="mt-2 text-sm text-[#667085]">
              Existing subscribers manage their plan, payment history and renewal from the{' '}
              <Link href="/billing" className="font-bold text-[#117A4B] hover:underline">Billing settings</Link>.
              Downgrades and cancellations always keep your data readable and exportable.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#EAECF0]">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-8 text-sm text-[#667085] sm:flex-row sm:items-center sm:justify-between lg:px-10">
          <div className="flex items-center gap-3"><KulimaLogo variant="header" /><span>© 2026 Kulima FLEX</span></div>
          <div className="flex gap-5"><Link href="/">Home</Link><Link href="/billing">Billing</Link><Link href="/flex">Workspace</Link></div>
        </div>
      </footer>
    </div>
  )
}
