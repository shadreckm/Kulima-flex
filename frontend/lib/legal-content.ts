// Built-in legal & compliance documents (Phase 10).
// Single source of truth rendered by /legal and /legal/[slug].

export type LegalSection = {
  heading: string
  paragraphs?: string[]
  bullets?: string[]
}

export type LegalDoc = {
  slug: string
  title: string
  summary: string
  effectiveDate: string
  version: string
  sections: LegalSection[]
}

const EFFECTIVE_DATE = '2026-09-01'
const VERSION = '2.0'

export const LEGAL_DOCS: LegalDoc[] = [
  {
    slug: 'privacy-policy',
    title: 'Privacy Policy',
    summary: 'What personal and organizational data Kulima FLEX processes, why, and the rights you hold over it.',
    effectiveDate: EFFECTIVE_DATE,
    version: VERSION,
    sections: [
      {
        heading: '1. Who we are',
        paragraphs: [
          'Kulima FLEX is an evidence-backed decision intelligence platform operated for funds, NGOs, accelerators, development finance institutions and government programmes. This policy explains how we handle data inside your workspace.',
        ],
      },
      {
        heading: '2. What we process',
        bullets: [
          'Account data: sign-in identity (name, email, session identifiers) used to authenticate you.',
          'Workspace data: organizations, memberships and roles that define who can see what.',
          'Assessment data: documents you upload, extracted text, entity fields, evidence items, signals, decisions and reports generated for you.',
          'Audit data: an append-only record of key actions (uploads, assessments, exports, decisions, logins, payments) for governance transparency.',
          'Billing data: plan, subscription status and payment references for the plan you purchased.',
        ],
      },
      {
        heading: '3. What we never send to third parties',
        bullets: [
          'Your uploaded documents, financial statements, customer data and contact details are never transmitted to external research providers.',
          'External research (Tavily) receives only public entity metadata: organization name, founder name, sector, country and public company information.',
          'An egress guard enforces this at the single research choke point, redacting emails, phone numbers, monetary amounts, long digit sequences and sensitive financial phrases before any query leaves the platform.',
        ],
      },
      {
        heading: '4. How we use the data',
        bullets: [
          'To produce the assessments, signals, decisions and reports you request.',
          'To enforce workspace isolation and role-based access so data is only visible to authorized members of your organization.',
          'To maintain the audit trail that shows who did what, and when.',
          'To operate billing and communicate about your subscription.',
        ],
      },
      {
        heading: '5. Your rights',
        bullets: [
          'Export: download any document, evidence bundle or report at any time.',
          'Delete: soft-delete or permanently delete documents (subject to your role).',
          'Complete assessment deletion: purge an entire assessment including files, chunks and context.',
          'Access & correction: review the extracted context and correct any field.',
          'Portability: export your assessment data in open formats (JSON bundle, PDF reports).',
        ],
      },
      {
        heading: '6. Where data lives',
        paragraphs: [
          'Data is stored in your platform deployment\'s database. Stored document files carry an explicit encryption metadata envelope; at-rest application-level encryption (AES-256-GCM) is applied when configured, otherwise files rely on provider disk encryption — and the metadata records that fact explicitly, never silently.',
        ],
      },
      {
        heading: '7. Contact',
        paragraphs: [
          'For privacy requests, deletion confirmations or questions, contact your workspace Owner or the Kulima FLEX platform administrator operating your deployment.',
        ],
      },
    ],
  },
  {
    slug: 'terms-of-use',
    title: 'Terms of Use',
    summary: 'The agreement governing access to and use of the Kulima FLEX platform.',
    effectiveDate: EFFECTIVE_DATE,
    version: VERSION,
    sections: [
      {
        heading: '1. Acceptance',
        paragraphs: [
          'By accessing Kulima FLEX you agree to these terms. If you use the platform on behalf of an organization, you confirm you are authorized to bind that organization.',
        ],
      },
      {
        heading: '2. Accounts and roles',
        bullets: [
          'Each user signs in with their own identity. Sharing credentials is not permitted.',
          'Organizations assign roles: Owner (full access), Admin (user management), Reviewer (can assess), Viewer (read-only).',
          'Owners are responsible for the membership list of their workspace.',
        ],
      },
      {
        heading: '3. Acceptable use',
        bullets: [
          'Upload only documents you have the right to process.',
          'Do not attempt to access another organization\'s workspace, data or reports.',
          'Do not use the platform to produce misleading assessments or to strip evidence provenance from outputs.',
          'Do not attempt to bypass plan quotas, feature gates or billing status.',
        ],
      },
      {
        heading: '4. Subscriptions and billing',
        bullets: [
          'Plans: Free (5 assessments per month), Pro (unlimited assessments, advanced signals, Ask IC, enterprise reports), Enterprise (unlimited users, RBAC, audit logs, private deployment, API integration).',
          'Payments are processed via PayChangu. Pricing is configurable per deployment and shown in the billing workspace.',
          'Failed payments enter a grace period before suspension. Suspension blocks new assessments only — your data always remains readable and exportable.',
          'Downgrades are scheduled for the end of the paid period; upgrades apply immediately.',
        ],
      },
      {
        heading: '5. Intellectual property and data ownership',
        bullets: [
          'Your documents and assessment data belong to your organization — not to Kulima FLEX.',
          'We process your data only to deliver the assessments you request.',
          'Reports and signals produced for you are licensed to your organization for internal decision-making.',
        ],
      },
      {
        heading: '6. Disclaimers',
        paragraphs: [
          'Kulima FLEX is a decision-support platform. Assessments, signals and recommendations are evidence-backed opinions, not guarantees of outcomes, investment returns or programme results. Decisions remain the responsibility of the human decision-makers who make them.',
        ],
      },
      {
        heading: '7. Changes',
        paragraphs: [
          'We may update these terms as the platform evolves. Material changes are surfaced in the product with an updated version and effective date.',
        ],
      },
    ],
  },
  {
    slug: 'data-retention',
    title: 'Data Retention Policy',
    summary: 'How long data is kept, how deletion works, and how retention is enforced.',
    effectiveDate: EFFECTIVE_DATE,
    version: VERSION,
    sections: [
      {
        heading: '1. Principle',
        paragraphs: [
          'Retention at Kulima FLEX is customer-controlled. Data persists while your organization needs it, and deletion is real — files, chunks and context are removed, and the deletion itself is recorded in the audit trail.',
        ],
      },
      {
        heading: '2. Retention windows',
        bullets: [
          'Documents: kept until your organization deletes them. An optional per-document retention window (in days) can be set; once it elapses the document is treated as expired and served with HTTP 410 Gone.',
          'Assessments: kept until complete deletion is requested through the assessment lifecycle.',
          'Audit events: append-only and retained for governance; they record that deletions happened and are never rewritten.',
          'Payment history: retained for billing reconciliation.',
        ],
      },
      {
        heading: '3. Deletion mechanics',
        bullets: [
          'Soft delete: the document is marked deleted (deleted_at/deleted_by) and immediately excluded from listings, downloads and evidence until purged. Content stays recoverable during the soft-delete window.',
          'Hard delete: the document row, its chunks and the stored file are permanently removed.',
          'Complete assessment deletion: purges the assessment context, all documents (rows, chunks, files) and the linked intelligence run in one audited operation.',
        ],
      },
      {
        heading: '4. Audit of deletion',
        paragraphs: [
          'Every deletion records an audit event including the mode (soft/hard), the acting user, and — for complete assessment deletion — the counts of documents, files and runs purged. Deletion is part of the governance trail, not a gap in it.',
        ],
      },
      {
        heading: '5. Backups',
        paragraphs: [
          'Where the deployment operator maintains database backups, deleted data ages out of backups according to the operator\'s backup rotation schedule. Contact your platform administrator for the specific rotation of your deployment.',
        ],
      },
    ],
  },
  {
    slug: 'responsible-ai',
    title: 'Responsible AI Statement',
    summary: 'How Kulima FLEX uses AI, what it will never do, and where humans stay in the loop.',
    effectiveDate: EFFECTIVE_DATE,
    version: VERSION,
    sections: [
      {
        heading: '1. Decision support, never decision replacement',
        bullets: [
          'Kulima FLEX produces evidence-backed assessments, signals and recommendations.',
          'It does not make investment, funding or programme decisions. Every final decision remains with a human decision-maker.',
          'Recommendations always carry their reasoning: evidence references, confidence levels and the factors that drove the conclusion.',
        ],
      },
      {
        heading: '2. Evidence grounding',
        bullets: [
          'Findings are linked to sources: uploaded documents, extracted text chunks and public research attributions.',
          'Evidence integrity is graded — contradictions, unsupported claims and evidence depth are surfaced, not hidden.',
          'When evidence is thin, the system says so instead of inventing certainty.',
        ],
      },
      {
        heading: '3. Data minimization in AI pipelines',
        bullets: [
          'Large language models process the extracted content of your documents to produce assessments you requested.',
          'External research providers receive public entity metadata only — never your documents, financial statements or customer data.',
          'An egress guard redacts sensitive tokens (emails, phone numbers, monetary amounts, sensitive financial phrases) before any external query.',
        ],
      },
      {
        heading: '4. Transparency',
        bullets: [
          'Every assessment exposes how it was generated: which documents were used, which evidence was found, which signals fired.',
          'Every significant action is logged in the workspace audit trail.',
          'The Trust & Governance workspace shows the security and retention posture of your deployment at any time.',
        ],
      },
      {
        heading: '5. Human oversight and correction',
        bullets: [
          'Users can correct extracted fields when confidence is low — corrections feed the assessment.',
          'Users can record outcomes (what actually happened) so the platform can measure its own accuracy over time.',
          'Feedback on any assessment is captured and reviewable.',
        ],
      },
      {
        heading: '6. Limitations',
        paragraphs: [
          'AI outputs may contain errors, may reflect gaps or biases in the underlying documents, and may be incomplete where public information is sparse — especially for early-stage ventures and community organizations. Independent verification remains the standard.',
        ],
      },
    ],
  },
  {
    slug: 'evidence-transparency',
    title: 'Evidence Transparency Policy',
    summary: 'How evidence is captured, verified, graded and displayed — and why a recommendation exists.',
    effectiveDate: EFFECTIVE_DATE,
    version: VERSION,
    sections: [
      {
        heading: '1. The chain of evidence',
        paragraphs: [
          'Every assessment follows a visible chain: Information → Evidence → Trust → Signals → Decision → Outcome → Learning. Each stage can be inspected in the workspace, and each conclusion points back to the evidence that produced it.',
        ],
      },
      {
        heading: '2. What counts as evidence',
        bullets: [
          'Uploaded documents pass through a seven-step evidence pipeline: parsing, chunking, extraction, metadata, trust scoring, signals and storage.',
          'Public research results are attributed with title, URL and relevance — never blended in anonymously.',
          'Every claim in a report is linked to its source chunk or public attribution.',
        ],
      },
      {
        heading: '3. Evidence integrity grading',
        bullets: [
          'Each assessment receives an evidence depth rating and an integrity grade.',
          'Contradictions between sources are flagged with severity and a recommended verification action.',
          'Unsupported claims are listed explicitly — what we could not verify is as visible as what we could.',
        ],
      },
      {
        heading: '4. Why a recommendation exists',
        bullets: [
          'Every recommendation carries: the decision verdict, confidence level, reliability grade, top reasons, top risks and the next action.',
          'Domain scores (evidence, trust, risk, climate, environment, tourism, community impact) show how each factor moved the decision.',
          'The decision rationale lists the specific evidence items that drove the outcome.',
        ],
      },
      {
        heading: '5. Traceability of exports',
        paragraphs: [
          'Exported reports preserve their evidence references. Every export is recorded in the audit trail with the report kind and format, so the provenance of a document in circulation can be checked against the platform record.',
        ],
      },
      {
        heading: '6. Deletion and history',
        paragraphs: [
          'When evidence is deleted, the audit trail records the deletion. History is appended, never rewritten — assessments performed earlier remain explainable in terms of what was known at the time.',
        ],
      },
    ],
  },
]

export function getLegalDoc(slug: string): LegalDoc | undefined {
  return LEGAL_DOCS.find(doc => doc.slug === slug)
}
