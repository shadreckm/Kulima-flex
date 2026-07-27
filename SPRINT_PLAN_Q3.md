# SPRINT_PLAN_Q3 — Kulima FLEX (Chief Engineering Manager)

Date: 2026-07-27
Sprints: 4 × 2-week sprints (Sprint 1 … Sprint 4)
Team assumption (recommended): 3 engineers (backend/front), 1 frontend engineer, 1 product manager, 1 designer (shared), 1 security engineer (part-time). Velocity assumed ≈ 30 story points / sprint.

Purpose: convert all P0 items from the Engineering / Product / Security / Enterprise backlogs into sprint-sized stories, estimate story points and effort, and provide a 4-sprint plan focused on Launch Readiness and Enterprise readiness.

---

## Executive summary

This plan focuses on eliminating the primary operational and security blockers that prevent reliable pilot and enterprise adoption while preserving product momentum (demo conversion and the export workflow). The first two sprints concentrate on quick wins and runtime stability: demo dataset + guided tour, asynchronous orchestrator MVP, export bundling, and the unsafe-HTML audit. The next two sprints complete enterprise controls: tenant isolation, SSO/OIDC + RBAC, audit logging, per-tenant export storage, and encryption/KMS initialization. This schedule assumes focused work and parallelization across 3 core engineers.

Key outcomes by the end of Sprint 4
- Demo & guided tour live; one-click IC export (memo + evidence bundle)
- Long-running orchestrations run reliably via background workers with progress streaming
- Unsafe-HTML audit completed and CI checks in place
- Audit logging for runs/exports implemented and append-only store enabled
- Initial SSO (OIDC) and RBAC enforcement implemented; tenant model design complete and partially implemented
- Secrets management integrated and encryption-at-rest verification done

Before inviting enterprise pilots we recommend completing Sprint 1–3 P0 scope (see section "What to build before inviting pilots").

---

## Sprint cadence & assumptions
- Sprint length: 2 weeks
- Planned sprints: Sprint 1 … Sprint 4
- Team velocity: 30 SP/sprint (adjust as team size changes)
- Story point scale mapping: S = 2 SP, M = 5 SP, L = 8 SP, XL = 13 SP

---

## All P0 epics (source)
P0 epics consolidated from the backlogs:
- E-1: Asynchronous orchestrator (background job queue + progress streaming)
- E-2 / ER-1: Tenant-scoped storage & row-level isolation
- E-3 / ER-2 / S-4: SSO + RBAC (authorization)
- E-4 / S-8: Audit logging & export tracking (append-only)
- E-5 / S-1: Unsafe HTML audit and templating enforcement
- S-3: Secrets management & vault integration
- S-6: Encryption-at-rest verification and KMS per-tenant
- P-1: Demo dataset + guided tour
- P-2/E-6: Prepare IC Pack export pipeline MVP
- P-3 / ER-8: Pilot onboarding kit and sandbox provisioning
- E-14: App Mode toggle (Demo vs Prod)

The plan below breaks these P0 items into sprint-sized stories and groups them into four sprints.

---

## Sprint Plan (stories by sprint)

Sprint 1 (Weeks 1–2) — Quick wins, safety fixes, architecture start
Team focus: deliver demo, patch critical unsafe HTML spots, select infra and PoCs to unblock heavier work.

Stories:

S1-01 (P-1.1) Create curated demo dataset (sample brief)
- SP: 2 (S)
- Effort: S
- Dependencies: none
- Expected output: JSON fixture + brief assets + minimal evidence links

S1-02 (P-1.2) Implement demo toggle (App Mode) and wiring to load demo dataset
- SP: 2 (S)
- Effort: S
- Dependencies: S1-01
- Expected output: UI toggle to switch to demo dataset (no production API calls)

S1-03 (P-1.3) Guided tour overlay (60–90s stepper)
- SP: 3 (M)
- Effort: M
- Dependencies: S1-01, S1-02, design copy
- Expected output: stepper that highlights Run → Executive Summary → Ask IC → Twin Syndicate → Export

S1-04 (E-5 / S-1.1) Unsafe-HTML code scan (full repo automated listing)
- SP: 3 (M)
- Effort: M
- Dependencies: codebase access, security engineer
- Expected output: prioritized list of HTML injection sites and severity

S1-05 (E-5 / S-1.2) Patch critical/high-risk unsafe HTML spots (hotfixes)
- SP: 5 (L)
- Effort: L
- Dependencies: S1-04
- Expected output: fix top 5 high-risk blocks, add html.escape, dedent multilines; regression tests added

S1-06 (E-1.1) Job queue architecture design & API contract (Redis/RQ vs Celery decision)
- SP: 3 (M)
- Effort: M
- Dependencies: infra decision with DevOps
- Expected output: design doc, message schema, job lifecycle states, progress model

S1-07 (E-1.2) Provision job queue infra in dev/staging (Redis + RQ or chosen stack)
- SP: 3 (M)
- Effort: M
- Dependencies: S1-06, cloud infra
- Expected output: dev/staging queue + running supervisor; test queue connectivity

S1-08 (E-1.3) Worker skeleton & local orchestrator invocation PoC
- SP: 5 (L)
- Effort: L
- Dependencies: S1-07
- Expected output: a worker that can accept jobs and execute a minimal orchestrator run locally; logs to local storage

S1-09 (S-3.1) Secrets vault selection & integration design
- SP: 2 (S)
- Effort: S
- Dependencies: infra, security input
- Expected output: chosen secrets solution (AWS Secrets Manager / Hashicorp) and integration plan

S1-10 (E-6.1) Export library PoC (PDF generation decision + test)
- SP: 2 (S)
- Effort: S
- Dependencies: design + sample memo
- Expected output: PoC that converts memo HTML to a reliable PDF (weasyprint / wkhtmltopdf / headless Chromium)

Planned SP total Sprint 1: 30 SP (approx)

---

Sprint 2 (Weeks 3–4) — Async orchestrator MVP + Export MVP + logging foundation
Team focus: make runs asynchronous and visible to users; deliver core export; wire in logging and secrets retrieval.

Stories:

S2-01 (E-1.4) Implement enqueue endpoint (create job, return job_id)
- SP: 3 (M)
- Effort: M
- Dependencies: S1-06, S1-07, S1-08
- Expected output: /api/jobs POST endpoint that enqueues orchestrator job with parameters

S2-02 (E-1.5) Persist job outputs and retrieval API
- SP: 4 (M)
- Effort: M
- Dependencies: storage choice, S1-06
- Expected output: job results stored at predictable locations and reachable via job_id

S2-03 (E-1.6) Implement progress streaming (SSE) and fallback polling; wire to UI progress indicator
- SP: 5 (M)
- Effort: M
- Dependencies: S2-01, frontend engineer
- Expected output: live progress updates in UI and server-sent event fallback

S2-04 (E-1.7) Worker implements orchestrator invocation and writes progress/events to job channel
- SP: 5 (L)
- Effort: L
- Dependencies: S2-01, S2-02
- Expected output: worker executes orchestration, emits progress states, stores final payload

S2-05 (E-6.2) Implement PDF generation for memo and evidence bundle zip
- SP: 5 (L)
- Effort: L
- Dependencies: S1-10 PoC, storage
- Expected output: memo PDF + evidence zip generated programmatically and saved to export location

S2-06 (E-4.1) Audit logging schema and logging middleware (emit events for runs & exports)
- SP: 3 (M)
- Effort: M
- Dependencies: design doc, minimal storage
- Expected output: events for job enqueue, job complete, export created

S2-07 (S-3.2) Integrate secrets retrieval for runtime (workers and web app)
- SP: 2 (S)
- Effort: S
- Dependencies: S1-09 (vault selection)
- Expected output: secrets retrieval works in dev/staging (no plain-text tokens in repo)

S2-08 (P-2.4) Integrate export modal UI & hook into export pipeline
- SP: 3 (M)
- Effort: M
- Dependencies: S2-05, S2-06
- Expected output: UI modal to produce bundled export and show progress; export event recorded

Planned SP total Sprint 2: ~30 SP

---

Sprint 3 (Weeks 5–6) — Tenancy + SSO + RBAC + encryption
Team focus: finish core enterprise blockers: tenant model, SSO (initial OIDC), RBAC, and KMS/encryption verification.

Stories:

S3-01 (E-2/ER-1.1) Tenant model design finalization & API mapping
- SP: 3 (M)
- Effort: M
- Dependencies: product (tenant requirements), security
- Expected output: design doc, tenant_id semantics, tenant admin model

S3-02 (E-2.2) DB schema changes to add tenant_id + migration plan (safe additive changes)
- SP: 5 (L)
- Effort: L
- Dependencies: S3-01
- Expected output: migrations, backward compatibility plan, test fixtures

S3-03 (E-2.3) Implement row-level access enforcement middleware/ORM layer
- SP: 6 (L)
- Effort: L
- Dependencies: S3-02
- Expected output: all DB queries scoped by tenant_id; unauthorized access prevented

S3-04 (E-3.1) Auth model updates & role model (user, roles, tenant mapping)
- SP: 3 (M)
- Effort: M
- Dependencies: S3-01
- Expected output: schema + endpoints for roles; role enforcement hooks

S3-05 (E-3.2) Implement OIDC SSO login (Okta/Azure) prototype + session handling
- SP: 5 (M)
- Effort: M
- Dependencies: S3-04, S1-09 (secrets vault)
- Expected output: OIDC login, callback flow, session creation, test with one IdP

S3-06 (E-3.3) RBAC enforcement middleware & admin assignment UI (basic)
- SP: 4 (M)
- Effort: M
- Dependencies: S3-04, S3-05
- Expected output: ability to map IdP groups to tenant roles via admin UI

S3-07 (S-6.1) Encryption-at-rest verification and initial per-tenant KMS plan
- SP: 3 (M)
- Effort: M
- Dependencies: cloud KMS, storage
- Expected output: verified encryption at rest for existing artifacts and plan for per-tenant KMS keys

S3-08 (E-4.2) Append-only logs: implement storage configuration (immutability) and retention skeleton
- SP: 3 (M)
- Effort: M
- Dependencies: S3 or archival storage capabilities
- Expected output: logs written to append-only storage with retention policy stub

Planned SP total Sprint 3: ~32 SP

---

Sprint 4 (Weeks 7–8) — Harden, finalize enterprise features, pilot automation
Team focus: polish, compliance pack, retention, admin console primitives, metering hooks, and QA.

Stories:

S4-01 (E-2.4) Per-tenant export storage (bucket prefixing & access control)
- SP: 4 (M)
- Effort: M
- Dependencies: S3-02, S3-03
- Expected output: exports stored per-tenant with correct ACLs and access policies

S4-02 (E-2.5) Data migration scripts & verification (safe migration of existing briefs)
- SP: 5 (L)
- Effort: L
- Dependencies: S3-02, DB backups
- Expected output: scripts and dry-run logs for migrating legacy data into tenant-scoped layout

S4-03 (E-11) Usage metering instrumentation (runs, tokens, exports)
- SP: 4 (M)
- Effort: M
- Dependencies: audit logging (S2-06) and job outputs
- Expected output: per-tenant usage metrics exportable as CSV

S4-04 (E-10) Model client resilience: implement throttling, circuit breaker, and retry policies
- SP: 4 (M)
- Effort: M
- Dependencies: model client wrappers, secrets vault
- Expected output: robust model API wrapper that prevents runaway costs and degrades gracefully

S4-05 (ER-3 / E-12) Minimal Admin Console: tenant creation & sandbox provisioning script
- SP: 5 (L)
- Effort: L
- Dependencies: tenancy & SSO
- Expected output: admin can provision sandbox tenant with demo data

S4-06 (S-8) Finalize audit log immutability & retention automation (purge jobs)
- SP: 3 (M)
- Effort: M
- Dependencies: S4-01 storage setup
- Expected output: scheduled purge job, retention policy enforcement, and admin list of retained artifacts

S4-07 (ER-5) SOC2 readiness doc / compliance pack (draft)
- SP: 4 (M)
- Effort: M
- Dependencies: security deliverables completed, legal
- Expected output: gap analysis and remediation plan for SOC2

S4-08 (Quality) E2E smoke & Playwright tests for critical flows (runs, export, SSO login)
- SP: 4 (M)
- Effort: M
- Dependencies: features completed in prior sprints
- Expected output: runnable E2E suite in CI with regression guard

Planned SP total Sprint 4: ~33 SP

---

## Quick wins (deliver in Sprint 1)
- Demo dataset + guided tour (S1-01..S1-03)
- App Mode (Demo vs Prod) toggle (S1-02)
- Unsafe-HTML repo scan and critical patches (S1-04..S1-05)
- Export PDF PoC (S1-10)

These increase demo conversion and reduce security risk quickly.

## Launch blockers (must be addressed before broad customer invites)
- Asynchronous orchestrator (background job + worker + progress streaming) — otherwise long runs block UI and cause timeouts (S2-01..S2-04)
- Export pipeline MVP producing a reliable IC Pack packaged for download (S2-05..S2-08)
- Unsafe-HTML critical fixes and CI checks (S1-04..S1-05)
- Secrets management in CI and runtime (S1-09, S2-07) — prevents leakage of tokens during demos

## Enterprise blockers (must be addressed before enterprise pilot invites)
- Tenant isolation / row-level enforcement and per-tenant storage (S3-01..S3-03, S4-01..S4-02)
- SSO + RBAC (OIDC/SAML) and role mapping (S3-05..S3-06)
- Audit logs append-only & retention (S2-06, S3-08, S4-06)
- Encryption-at-rest / KMS per-tenant verification (S3-07)
- SOC2 readiness and legal DPA (S4-07)


---

## What should be built before inviting pilots (recommended)

Minimum for early functional pilots (non-enterprise, trusted partners):
- Demo dataset & guided tour (S1-01..S1-03)
- App Mode (Demo) toggle (S1-02)
- Async orchestrator MVP (S1-07..S2-04) so runs don't block UI
- Export MVP for IC Pack (S2-05..S2-08)
- Unsafe-HTML critical fixes + CI lint rule (S1-04..S1-05, S1-10)
- Secrets management configured for staging (S1-09, S2-07)
- Audit logging of runs & exports (S2-06)

Minimum for enterprise pilots (paid customers & procurement):
- All of the above, plus:
  - Tenant isolation & row-level access enforcement (S3-01..S3-03)
  - SSO (OIDC / SAML) + RBAC enforcement (S3-04..S3-06)
  - Append-only audit logs and retention (S3-08, S4-06)
  - Encryption at rest + KMS plan (S3-07)
  - Legal DPA and SOC2 readiness plan (S4-07)


---

## Risk Register

| Risk | Probability | Impact | Mitigation | Owner |
|---|---:|---:|---|---|
| Orchestrator backlog/complexity delays MVP | Medium | High | Split work into design + infra + worker pieces; early PoC; scope to run in non-blocking mode | Eng lead |
| XSS / unsafe HTML vulnerability missed in patching | High | Very High | Repo audit, CI lint rule, security sign-off, Playwright tests for rendering | Security lead |
| Model provider outages / cost overruns | Medium | High | Implement throttling/circuit-breaker, rate quotas per-tenant, usage metering | Eng lead + Ops |
| Migration complexity for tenant model causing downtime/data issues | Medium | High | Create migrations with dry-run, backups, run on staging first; migration approval gate | Eng lead + DBA |
| SSO / IdP integration quirks (SAML metadata differences) | High | Medium | Focus on OIDC first, provide manual provisioning as fallback, allocate integration buffer | Eng lead + Security |
| Compliance timeline for SOC2 longer than expected | Medium | High | Start gap analysis early (Sprint 3/4), prioritize remediation in backlog | Security + Legal |
| Inadequate test coverage causing regressions in UI/HTML rendering | Medium | Medium | Add E2E Playwright tests gated in CI | QA lead |

Each risk should have an owner assigned in the sprint planning meeting and a remediation plan documented in the relevant design doc.

---

## Success metrics (KPIs & targets for next 90 days)

Operational / delivery metrics
- Sprint delivery: complete ≥ 85% of planned story points per sprint (target)
- P0 items completed: all P0 stories completed by end of Sprint 4 (target)

Product & commercial metrics
- Demo → trial conversion rate increases by +25% within 30 days of Demo tour launch
- Mean time to generate Export IC Pack: < 2 minutes (target for exported files in production) for cached assets, < 10 minutes for first-run depending on model latency
- Orchestrator run success rate (jobs not failing): >95% within 48 hours of launch
- Median time-to-first-progress update (progress streaming): < 5 seconds after job enqueue

Security & enterprise metrics
- No high-severity security findings for unsafe HTML after remediation
- SSO+RBAC integration time for pilot IdP: < 2 weeks (target)
- Audit log coverage: 100% of job enqueue/complete and export events recorded and retained for pilot tenants

Adoption metrics
- Time to onboard pilot (1st user to first export): ≤ 3 business days (target for pilot support flow)
- Pilot-to-paid conversion (after enterprise features delivered): tracked but target 20% within 90 days of pilot

Measurement & reporting
- Build dashboards for daily sprint burndown, job queue success/failure rates, export latency percentiles, and demo->trial conversions (product analytics).

---

## Notes & next steps (execution guidance)
1. Kickoff meeting to align product, security, and engineering: review Sprint 1 scope and get infra approvals for Redis/queue and secrets vault.
2. Security should prioritize the HTML audit and CI lint rule creation in Sprint 1.
3. Engineering: block 2 engineers on orchestrator (E-1) work across Sprint 1–2; frontend engineer focused on demo/tour and export UI.
4. Product & design: finalize tour copy and export UX by end of Sprint 1.
5. Plan a checkpoint at the end of Sprint 2 to validate whether asynchronous orchestrator MVP and Export MVP meet acceptance criteria; if not, re-scope subsequent sprints.

---

If you want, I will:
- convert the Sprint entries into GitHub Issues with acceptance criteria and checklists for each story;
- produce a 2-week sprint schedule with daily standups, sprint demos, and required reviewers; and
- prepare an "invitation-to-pilot" readiness checklist document that maps the minimum deliverables to pilot types (non-enterprise vs enterprise).

