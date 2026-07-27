# ROADMAP Q3–Q4 — Kulima FLEX

Date: 2026-07-27
Author: Chief Product Strategist

This roadmap organizes the prioritized work across Q3 and Q4 into four phases. Each phase lists key epics, owners, success criteria, and risks. Timelines assume a small cross-functional team (2–4 engineers, 1 product manager, 1 designer, 1 security engineer) and should be re-estimated by engineering.

---

## Phase 1 — Launch Readiness (Q3, 0–8 weeks)
Objective: Ship demo/onboarding and stabilize core run/export experience so sales and product teams can conduct high-quality pilots.

Key epics
- Demo Dataset + Guided Tour (P-1)
  - Owner: Product + UX
  - Deliverables: demo toggle, curated sample brief, 60–90s overlay tour
  - Success criteria: demo->trial conversion +25%; demo toggle available in UI

- Unsafe HTML Audit & Templating CI (S-1 / E-5)
  - Owner: Engineering + Security
  - Deliverables: code audit report, remediation of high-risk locations, CI lint rule
  - Success criteria: All HTML injection points documented and guarded; CI prevents regressions

- Job queue spike + minimal async orchestrator (E-1 — MVP)
  - Owner: Engineering
  - Deliverables: worker prototype (enqueue/run/stream progress), minimal persistence for job outputs
  - Success criteria: 95% of long runs execute without front-end blocking; progress updates visible

- Export "Prepare IC Pack" (light MVP) (E-6 / P-2)
  - Owner: Product + Engineering
  - Deliverables: single-button export that bundles memo PDF + evidence zip; basic PPTX or placeholder slide deck option
  - Success criteria: users can produce a single packaged download in < 2 minutes; export logged

- App Mode toggle (Demo vs Production) (E-14)
  - Owner: Engineering + Product
  - Deliverables: safe demo mode for sales demos without production API use
  - Success criteria: sales can run demos without exposing production model tokens or customer data

Risks
- Background job queue/worker complexity may take longer than expected (break XL tasks into sub-epics).
- Export generation may have edge cases with fonts and PPTX libraries.

---

## Phase 2 — Enterprise Readiness (Q3 late – Q4)
Objective: Provide core enterprise-grade controls: tenancy, access, auditing, and legal artifacts to move from pilots to paid contracts.

Key epics
- Tenant model and per-tenant storage implementation (ER-1 / E-2)
  - Owner: Engineering + Security
  - Deliverables: tenancy design doc, storage separation plan, migration scripts, per-tenant artifact storage
  - Success criteria: tenant data cannot be accessed by other tenants; verified by tests and review

- SSO + RBAC (ER-2 / E-3 / S-4)
  - Owner: Engineering + Security
  - Deliverables: SAML/OIDC connectors, role mapping UI for tenants, SCIM or JIT provisioning path
  - Success criteria: pilot customer connects IdP and users map to roles; access enforcement verified

- Audit logs, export tracking, and retention policy (ER-5 / E-4 / S-8)
  - Owner: Engineering + Security + Legal
  - Deliverables: append-only export logs, admin viewer, retention settings
  - Success criteria: all export events recorded immutably and accessible to tenant admins

- Admin Console MVP (ER-3 / E-12)
  - Owner: Product + Engineering
  - Deliverables: tenant creation, user invites, feature flags, export log access
  - Success criteria: CS can onboard pilot in < 60 minutes using console

- SOC2 readiness / compliance artifacts (ER-5 / S-5)
  - Owner: Security + Legal
  - Deliverables: gap analysis, remediation backlog, DPA template
  - Success criteria: SOC2 readiness plan and timeline; DPA available for pilots

Risks
- Tenant migration complexity; backwards compatibility with existing session-state implementations.
- Third-party model provider requirements for enterprise contracts (data handling, VPC endpoints) may introduce integration work.

---

## Phase 3 — Portfolio Monitoring (Q4)
Objective: Grow product from single-run intelligence to continuous portfolio monitoring and alerts for paying customers.

Key epics
- Scheduled runs / monitoring engine
  - Owner: Product + Engineering
  - Deliverables: schedule jobs, delta detection (new evidence), notification hooks, portfolio-level dashboard
  - Success criteria: tenants can schedule recurring runs and receive digest emails / notifications

- Portfolio-level alerts & watchlists
  - Owner: Product
  - Deliverables: watchlists, alert configuration (e.g., significant trust / thesis changes), alert delivery (email or Slack)
  - Success criteria: alert volume manageable; alerts actionable by analysts

- Per-tenant dashboard & analytics (usage + health)
  - Owner: Engineering + Product
  - Deliverables: tenant dashboards for runs, usage, and reliability metrics
  - Success criteria: tenants can view usage and SLA health

Risks
- Monitoring scale & cost: running scheduled orchestrator jobs requires cost forecasting and throttling.

---

## Phase 4 — Multi-Organization Platform (Q4 → ongoing)
Objective: Scale Kulima into a secure, enterprise platform that supports multiple organizations, integrations, and compliance.

Key epics
- Full multi-tenant hardening & per-tenant KMS
  - Owner: Engineering + Security
  - Deliverables: complete per-tenant keys, data residency support, KMS integrations
  - Success criteria: pilot customers can require specific region data residency and per-tenant encryption

- Billing & metering productionization (ER-4 / E-11)
  - Owner: Product + Engineering
  - Deliverables: production metering, billing integration or billing export, seat & credit models
  - Success criteria: finance can invoice pilot customers; billing accuracy within 3% of expected usage

- Integrations & automation (Slack / Calendar / SSO advanced)
  - Owner: Product
  - Deliverables: Slack/Teams notifications, calendar-based IC scheduling, calendar invites generated from export flows
  - Success criteria: integrations available and documented for pilot tenants

- SOC2 audit and certification (if applicable)
  - Owner: Security + Legal
  - Deliverables: SOC2 audit plan, remediation, audit engagement
  - Success criteria: certification achieved or plan in progress for target customers

Risks
- Certification timeline can be long and requires organizational commitment and budget.

---

## Cross-cutting success criteria (company-level)
- Demo-to-trial conversion increases materially within 60 days of shipping the demo/tour.
- Enterprise pilots can be onboarded with SSO and tenant isolation within 2–3 weeks of request.
- No high-severity security findings from an internal audit of unsafe HTML rendering.
- Orchestrator runs reliably complete without blocking UI; user experience shows stable progress updates.

## Quick wins (first 2 weeks)
- Ship demo dataset + guided tour (Phase 1)
- App Mode toggle (Demo vs Production)
- Add export logging for new exports
- Perform a rapid code sweep for unsafe HTML injections and fix the most critical spots

---

This roadmap is intentionally pragmatic: focus Phase 1 on conversion and crash fixes, Phase 2 on enterprise controls, Phase 3 on product expansion (monitoring), and Phase 4 on scaling and hardening for broad commercial adoption.

If you'd like, I can convert these phases into sprint-level epics with story-level breakdowns and time estimates for a 2-week sprint cadence.
