# Engineering Backlog — Kulima FLEX

This document converts the Product Readiness Review into a prioritized engineering backlog. Each item includes Priority (P0–P3), Effort (S/M/L/XL), Dependencies, and Expected Impact.

Notes on scale:
- Priority P0 — must have before enterprise pilots or launch to paying customers.
- Priority P1 — high value and should be scheduled in the near term (quarter).
- P2/P3 — important but lower near-term priority.

---

E-1: Asynchronous orchestrator (background job queue + progress streaming)
- Priority: P0
- Effort: XL
- Description: Move long-running intelligence runs off the request cycle into a job queue (Redis/RabbitMQ) with worker processes that execute orchestrator runs, store results, and stream progress updates to the UI (progress API / websockets / server-sent events or polling endpoint).
- Dependencies: Infrastructure (Redis/RQ or Celery/Kafka), persistent storage for job outputs, authentication/session mapping, UI progress hooks, retriable task semantics.
- Expected impact: Very High — eliminates timeouts, reduces user frustration, enables reliable long-running runs and enterprise SLAs.

E-2: Tenant-scoped data storage & row-level isolation (storage refactor)
- Priority: P0
- Effort: XL
- Description: Implement tenant-aware storage strategy (row-level security or per-tenant schemas / per-tenant buckets) for briefs, exports, and session artifacts.
- Dependencies: Auth/tenant model, schema design, migration plan, backup/restore, tests.
- Expected impact: Very High — required for multi-organization and enterprise security/compliance.

E-3: SSO integration + RBAC implementation (engineering side)
- Priority: P0
- Effort: L
- Description: Implement OIDC/SAML flows, token handling, and role enforcement in APIs. Provide role mapping (admin, partner, analyst, read-only) and enforce on all endpoints and exports.
- Dependencies: Identity-provider integration (Okta/Azure/Google), tenant model, auth middleware, enterprise backlog items.
- Expected impact: Very High — enterprise adoption blocker without it.

E-4: Audit logging & export tracking (server-side)
- Priority: P0
- Effort: M
- Description: Centralize event logging for user actions (runs, exports, downloads, admin changes). Persist logs in append-only storage; add export-download records (who/what/when).
- Dependencies: Storage/ELK or cloud logging (CloudWatch/Stackdriver), timestamping, retention policies, admin UI hooks.
- Expected impact: Very High — compliance and incident investigation capability.

E-5: Unsafe HTML audit + templating enforcement
- Priority: P0
- Effort: M
- Description: Run a thorough code audit for all uses of unsafe HTML rendering, enforce templating rules (textwrap.dedent + html.escape for data values), add linter/CI checks to prevent regressions.
- Dependencies: Code owners, CI pipeline, static analysis tool (flake8 plugin or custom lint rule).
- Expected impact: Very High — reduces XSS risk and prevents reintroduction of rendering regressions.

E-6: Export pipeline — "Prepare IC Pack" (report bundling + PPTX/PDF)
- Priority: P1
- Effort: L
- Description: Implement a single, user-facing export workflow that picks memo sections, generates PDF and PPTX, bundles evidence sources, and produces one archive for download.
- Dependencies: Document generation libraries (WeasyPrint / wkhtmltopdf / python-pptx), storage for generated assets, export audit logs, UI selector.
- Expected impact: High — major product value for investor workflows.

E-7: Demo dataset mode + guided in-app tour overlay (engineering implementation)
- Priority: P1
- Effort: S
- Description: Add a demo toggle that loads a curated sample brief and wire a lightweight tour overlay (tooltips or stepper) that highlights Run, Executive summary, Ask IC, Twin Syndicate, Export.
- Dependencies: Sample dataset, UI tour library or custom overlay, test coverage.
- Expected impact: High — increases conversion for first-time users.

E-8: Mobile-critical flow polish (Run, Summary, Ask IC)
- Priority: P1
- Effort: M
- Description: Simplify responsive rendering of the critical flows. Collapse heavy charts into summarized cards on <480px, ensure FAB/drawer usability, verify chat and export flows on phones.
- Dependencies: CSS tweaks, UI QA matrix, device testing.
- Expected impact: High — mobile accessibility for on-the-go users.

E-9: Results caching & idempotency for repeated runs
- Priority: P1
- Effort: M
- Description: Implement a cache layer keyed on (founder, startup, run parameters, model versions) to avoid duplicate runs and control cost.
- Dependencies: Storage/DB, job queue integration, TTL/invalidations.
- Expected impact: Medium-High — reduces costs and speeds repeated queries.

E-10: Model client resilience & traffic shaping
- Priority: P1
- Effort: M
- Description: Add retry/backoff, circuit-breaker, and throttling for LLM/model API calls. Add per-tenant cost controls (rate limits or quotas).
- Dependencies: Model client wrapper, monitoring, job queue.
- Expected impact: High — prevents outages and runaway cost.

E-11: Usage metering surface + billing hooks
- Priority: P2
- Effort: M
- Description: Instrument usage metrics (runs, tokens, exports) and expose a billing hook / CSV output for finance or billing integration.
- Dependencies: Audit logging, tenant model, admin console.
- Expected impact: Medium — required for commercial billing.

E-12: Admin console (partial) — tenant & feature toggles
- Priority: P2
- Effort: L
- Description: Implement a minimal admin console to manage tenants, API keys, feature flags, and export logs.
- Dependencies: Tenant model, auth, audit logs.
- Expected impact: High for operational pilots.

E-13: E2E/UI automated tests for HTML rendering (regression prevention)
- Priority: P1
- Effort: M
- Description: Add Playwright/Selenium tests that render critical pages, assert that HTML blocks render (no raw HTML), and verify widget keys uniqueness.
- Dependencies: CI integration, test harness.
- Expected impact: Medium — prevents regressions after UI changes.

E-14: "App Mode" toggle (Demo vs Production)
- Priority: P2
- Effort: S
- Description: Simple switch to toggle sample/demo dataset (no production APIs invoked) for sales demos and pilot onboarding.
- Dependencies: Demo dataset, auth/feature-flag toggle.
- Expected impact: Medium — safer demos.

E-15: Export retention & purge scheduler (backend)
- Priority: P1
- Effort: M
- Description: Implement scheduled purge/retention of generated exports and artifacts per tenant policy.
- Dependencies: Storage lifecycle policies, admin config.
- Expected impact: Medium — cost control and compliance.

---

Engineering acceptance notes
- For each P0 item require a technical design doc, runbook, and test plan before implementation.
- Break XL items (E-1, E-2) into 3–6 sub-tasks and schedule them as epics.


