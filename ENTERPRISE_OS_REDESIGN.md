# Kulima FLEX — Enterprise Decision Management System Redesign

**Author:** Chief Product Architect
**Date:** 2026-09-22
**Status:** Design for review — no code changed
**Scope:** Operating-system layer only. No UI redesign from scratch. No existing functionality removed.

---

## 0. Executive Summary

Kulima FLEX already has the hardest primitives: a shared `AssessmentContext` intake record, org-scoped tenancy with a 4-role RBAC matrix, an append-only audit event stream, encrypted document storage with a registry, a threaded background orchestrator, Tavily research, signals, and decision engines. What is missing is the **transaction and case layer** that turns those primitives into a bank-grade case management system:

1. A first-class **Assessment lifecycle state machine** (Draft → Processing → Review → Decision Ready → Exported → Archived).
2. A durable **job/transaction store** so work survives process restarts (today's runs live in daemon threads).
3. An **auto-research pipeline** fused into document ingestion (Research Status: Pending / Running / Completed).
4. **Work queues, pending-task checks, and resume-on-login** built on top of the lifecycle.
5. **Collaboration primitives** (comments, review/approval requests) and a **Decision Dossier** as the single source of truth.

The single most important structural decision: **promote `kulima/core/cases/models.py::Case` from an unused foundation abstraction into the enterprise aggregate root**, and hang the transaction lifecycle, workspaces, collaboration, and dossier off it. The existing `AssessmentContext` remains the intake record — it becomes *part of* the Case, not a replacement for it.

---

## 1. Current State (audited 2026-09-22)

| Capability | Exists? | Where | Gap |
|---|---|---|---|
| Multi-document intake | Partial | `AssessmentContext.document_ids` + `documents.assessment_id` | No per-document status/trust contribution surfaced; no "unlimited" enforcement |
| Background processing | Partial | `orchestrator_adapter.start_intelligence_run` (daemon `threading.Thread`) | Dies on process restart; no durable job queue; no resume semantics |
| Research engine | Yes | `kulima/research.py::ResearchEngine` (Tavily) | Triggered as separate step; not auto-launched from extraction; no Research Status entity |
| Tenancy / RBAC | Yes | `kulima/core/orgs/models.py` — Owner/Admin/Reviewer/Viewer + `ROLE_PERMISSIONS` | Roles not enforced on assessment-level workflow actions (review queues) |
| Audit trail | Yes | `kulima/core/audit/repository.py` — append-only, scoped by org/assessment/run/document | Covers ~20 event types; missing collaboration + lifecycle-transition events |
| Case abstraction | Foundation only | `kulima/core/cases/models.py::Case`, `CaseType`, `CaseSubject` | Not persisted, not wired to anything — the natural home for the transaction layer |
| Document security | Yes | `backend/app/main.py` guarded `/uploads` serving, at-rest encryption | Good; extend retention to Case archive |
| Billing | Yes | `kulima/core/billing/*`, `backend/app/routers/billing.py` | Enforce per-workspace quotas on background jobs |
| Lifecycle statuses | No | `AssessmentStatus` = intake/needs_confirmation/ready/running/complete/failed | This is a *pipeline* status, not an enterprise *transaction* status |

---

## 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Next.js, unchanged look)              │
│  Work Queues │ Assessment Workspace │ Timeline │ Dossier │ Review    │
└──────────────┬──────────────────────────────────────────────────────┘
               │ /api/v1/*
┌──────────────▼──────────────────────────────────────────────────────┐
│                     FASTAPI SERVICE LAYER (existing routers)         │
│  + NEW: cases router · tasks router · comments router · dossier      │
└──────────────┬──────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────────┐
│                  ENTERPRISE OS LAYER  (NEW MODULES)                  │
│                                                                      │
│  ┌────────────┐   ┌──────────────┐   ┌───────────────────────────┐  │
│  │ CaseService │  │ JobRunner     │  │ CollaborationService       │  │
│  │ (lifecycle │   │ (durable txn) │  │ (comments/notes/requests)  │  │
│  │  state m/c)│   │ resume-on-boot│  │                            │  │
│  └─────┬──────┘   └──────┬───────┘   └─────────────┬──────────────┘  │
│        │                 │                       │                 │
│  ┌─────▼─────────────────▼───────────────────────▼──────────────┐  │
│  │              EvidenceGraphService  (NEW)                       │  │
│  │   Documents + OpenAI extraction + Tavily → ONE evidence graph  │  │
│  └─────┬────────────────────────────────────────────────────────┘  │
│        │                                                             │
│  ┌─────▼──────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐ │
│  │ AssessmentSvc  │  │ DocumentSvc  │  │ Signals  │  │ Decision  │ │
│  │ (existing)     │  │ (existing)   │  │ (existing)│  │ (existing)│ │
│  └────────────────┘  └──────────────┘  └──────────┘  └───────────┘ │
│        (all existing engines are reused untouched)                   │
└──────────────────────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────────┐
│  SQLite (today) → Postgres (pilot gate). New tables: cases, case_    │
│  events, jobs, research_packs, comments, review_requests, dossiers   │
└──────────────────────────────────────────────────────────────────────┘
```

### Core principle

The pipeline stays exactly as it is (Upload → AI + Research → Signals → Decision → Report). Every phase of the brief is implemented by **adding a state machine, a durable job queue, and read-models over the existing audit/event tables** — never by rewriting the engines.

---

## 3. Phase-by-Phase Design

### Phase 1 — Multi-Document Assessments

**What changes:** `AssessmentContext` already stores `document_ids: List[str]`. Make it truly unlimited and observable.

- Remove any single-document assumptions in `backend/app/routers/documents.py::upload_document` (today uploads bind to a `run_id`; extend to accept `assessment_id` and append, not replace).
- Per-document view model (already 80% present in `AssessmentDocument`): add explicit `status` (uploaded / extracting / extracted / failed), `doc_type` (exists: `DocumentType`), `trust_contribution` (float, delta this document adds to assessment trust), `evidence_count`.
- **Trust contribution** = recomputed assessment trust with the document minus without it (leave-one-out, cached on ingestion). Computed by `EvidenceGraphService`, stored denormalized on `assessment_documents` view.

**Files:** `kulima/core/assessment/models.py` (extend `AssessmentDocument`), `backend/app/routers/documents.py`, new `backend/app/routers/cases.py`.

### Phase 2 — Research + Document Fusion (Evidence Graph)

**What changes:** one `evidence_graph` per assessment unifying three source families with identical `SourceAttribution` shape (the bridge type `DocumentSource` in `kulima/core/documents/models.py` already exists for exactly this).

New flow (no separate forms):

```
Document uploaded → extraction (existing) → entity resolution
    → auto-launch ResearchPack(founder, startup/org, sector, country)
    → Research Status: Pending → Running → Completed
    → all sources (doc chunks + OpenAI claims + Tavily) → evidence_nodes
      (kind: 'document' | 'analysis' | 'research', edges: supports/contradicts)
```

- `ResearchPack` = new entity: `id, assessment_id, query_set, status(pending|running|completed|failed), sources[] , started_at, completed_at, attempt_count`.
- Reuses `kulima/research.py::ResearchEngine.research_bundle` unchanged; the pack just calls it with auto-derived queries.
- Dedup/rank via existing `_rank_sources` / `_dedupe`.
- Every Tavily source and every document chunk becomes a node keyed by `SourceAttribution` — Evidence Integrity and Trust Graph then run over the *merged* set (this is the fusion: one graph, not two lists).

**Files:** new `kulima/core/evidence/graph.py`, `kulima/core/research/models.py` + `repository.py`; `backend/app/services/orchestrator_adapter.py` (auto-launch hook after extraction completes).

### Phase 3 — Assessment Workspaces

**What changes:** Workspaces = **org + assessment_type lens over the Case aggregate**, not a new container.

- Promote `Case` (`kulima/core/cases/models.py`) to a persisted aggregate: `cases(id, org_id, case_type, workspace_type, subject_json, assessment_id, lifecycle_status, assignee_id, created_by, created_at, updated_at)`.
- Workspace types map 1:1 to the existing `AssessmentType` enum (startup / ngo / tourism_sme / government_program / development_program) — the landing-page types *become* the workspace templates.
- Each workspace view (`/workspace/startup`, `/workspace/tourism` …) renders the same six tabs: Documents · Research · Evidence · Signals · Decision · Reports + Activity (audit feed).
- No data moves. The workspace is a **read model** joining `documents`, `research_packs`, `evidence_nodes`, `signals`, `decision`, `audit_events` by `assessment_id`.

**Files:** `kulima/core/cases/models.py` (extend with lifecycle + workspace fields), new `kulima/core/cases/repository.py`, new `kulima/core/cases/service.py`.

### Phase 4 — Transaction System (the heart of the redesign)

**Status state machine** (stored on `cases.lifecycle_status`):

```
DRAFT ──upload──▶ PROCESSING ──engines done──▶ REVIEW
   ▲                  │  ▲                        │  reviewer approves
   └── user edits ────┘  └── any engine re-run ───┤
                          (automatic re-entry)     ▼
ARCHIVED ◀──archive── EXPORTED ◀──export── DECISION_READY
   │                                            │
   └── reopen (audit-logged)                    └── changes → back to DRAFT
```

**Durable JobRunner** — replaces bare daemon threads:

- New `jobs` table: `id, case_id, kind(research|extraction|signals|decision|export), status(queued|running|succeeded|failed|dead), payload_json, attempts, max_attempts, run_after, lease_owner, lease_expires_at, created_at, updated_at`.
- Runner = a single background loop (asyncio task started in `backend/app/main.py` lifespan) that claims due jobs with `UPDATE ... WHERE lease_expires_at < now RETURNING` (SQLite-safe with `BEGIN IMMEDIATE`).
- **Survives restarts:** on boot, runner re-queues jobs stuck in `running` whose lease expired. This is what makes "user leaves, returns tomorrow, sees progress" true even across deploys — the current `threading.Thread(daemon=True)` approach loses everything on restart.
- Existing `start_intelligence_run` thread is reimplemented as *enqueue one pipeline job*; the worker body is the current `_worker` function, unchanged.
- Idempotency: each job declares an idempotency key; re-running a completed stage is a no-op unless the case is back in DRAFT (then version bumps invalidate downstream stages).

**Resume Assessment on login:** `/api/v1/tasks/pending` returns active cases for the user (PROCESSING or REVIEW owned by/assigned to them). Frontend banner on `frontend/app/dashboard/page.tsx`: "You have N active assessments — Resume?".

**Files:** new `kulima/core/jobs/{models,repository,runner}.py`; `backend/app/main.py` (lifespan startup); `backend/app/services/orchestrator_adapter.py` (enqueue instead of spawn thread); `backend/app/routers/cases.py`.

### Phase 5 — Pending Tasks Engine

- `GET /api/v1/tasks/pending` computes from durable state (no in-memory tracking): running research packs, cases in REVIEW awaiting the user, failed extractions, cases in DECISION_READY not yet exported.
- Frontend: `beforeunload` guard on workspace pages (only a *prompt*, never blocks) + a persistent banner component, **not** a blocking modal. "Save & Exit" is the default anyway because every stage commits durably — the prompt is advisory.
- Audit event `session.exit_with_pending` recorded for governance analytics.

**Files:** new `backend/app/routers/tasks.py`; `frontend/components/PendingBanner.tsx`.

### Phase 6 — Work Queues

Dashboard sections are **filtered views over `cases`** (no new storage):

| Queue | Filter |
|---|---|
| My Work | `assignee_id = me AND lifecycle_status IN (DRAFT, PROCESSING)` |
| Team Work | `org_id = my org AND assignee_id != me AND status != ARCHIVED` |
| Pending Reviews | `lifecycle_status = REVIEW AND (reviewer_id = me OR role ≥ Manager)` |
| Completed | `lifecycle_status = DECISION_READY` |
| Archived | `lifecycle_status = ARCHIVED` |

Viewer role sees only `DECISION_READY` + `EXPORTED` rows, and only the dossier/report tab (enforced server-side via existing `role_has_permission`).

**Files:** `frontend/app/dashboard/page.tsx` (extend sections); `backend/app/routers/cases.py` (queue endpoints).

### Phase 7 — Role-Based Workflow

Map the existing `ROLE_PERMISSIONS` onto lifecycle transitions:

| Action | Owner | Admin/Manager | Reviewer | Viewer |
|---|---|---|---|---|
| Create/upload (DRAFT) | ✓ | ✓ | ✓ | – |
| Trigger/re-run engines | ✓ | ✓ | ✓ | – |
| Approve REVIEW → DECISION_READY | ✓ | ✓ | – | – |
| Export | ✓ | ✓ | ✓ | – |
| Archive/reopen | ✓ | ✓ | – | – |
| View final dossier/report | ✓ | ✓ | ✓ | ✓ |
| Manage members/billing | ✓ | ✓ | – | – |

Enforcement point: a single dependency `require_permission(Permission.X)` in `backend/app/core/auth.py` checked at every mutating route, plus lifecycle-transition guard in `CaseService.transition(case, to, actor)` which is the *only* legal way to change status.

### Phase 8 — Assessment Timeline

Zero new storage: timeline = `audit_events WHERE assessment_id = ? ORDER BY created_at`, already scoped and indexed (`idx_audit_assessment`). Add missing event types to `EVENT_TYPES`: `research.started`, `research.completed`, `document.extraction_completed`, `case.lifecycle_changed`, `review.requested`, `review.approved`, `comment.added`, `dossier.generated`.

Render as vertical timeline in the workspace Activity tab. Each node: actor (from `user_id`), timestamp, label, metadata payload.

**Files:** `kulima/core/audit/repository.py` (event types only); `frontend/app/flex/page.tsx` (Activity tab).

### Phase 9 — Activity Log

The append-only stream already answers who/what/when. Gaps to close:

1. Wire `record_event` into every **new** surface (case transitions, review approvals, comments, dossier generation, export).
2. Add `ip_hash` + `user_agent` columns to `audit_events` for enterprise forensics (privacy-safe: store salted hash, per existing Privacy Layer posture).
3. Governance page gets org-wide filter (exists) + per-assessment deep link (new).

### Phase 10 — Collaboration

New tables (single design covers all four asks):

```
comments(id, org_id, case_id, author_id, body, anchor_type, anchor_id, created_at, edited_at, deleted_at)
review_requests(id, case_id, kind(review|approval), requested_by, requested_from, status, resolution_note, created_at, resolved_at)
```

- Comments anchored to documents, evidence nodes, signals, or the case itself (`anchor_type/anchor_id`).
- A Review Request moves a case into `REVIEW` and assigns `reviewer_id`; approval moves it to `DECISION_READY` and stamps `approved_by/at` on the dossier.
- All four actions emit audit events (Phase 8/9).

**Files:** new `kulima/core/collaboration/{models,repository,service}.py`; `backend/app/routers/comments.py`.

### Phase 11 — Decision Dossier

`dossiers` table: `case_id (unique), version, scores_json, recommendation, research_summary, executive_summary, generated_at, generated_by, approved_by, approved_at, pdf_path`.

- `scores_json` = the seven canonical scores (Evidence, Trust, Risk, Climate, Tourism, Community, Opportunity) + recommendation — assembled by a `DossierService` that reads existing engines' outputs. No new scoring logic in the dossier layer; it is a **projection**.
- Dossier is immutable once approved; regeneration creates `version+1`. This is what makes it the single source of truth.
- Export (existing `kulima/export.py`) renders the approved dossier version to PDF. `report.exported` audit event links the dossier version.

### Phase 12 — Tourism Intelligence

Tourism SME assessments get a `tourism_profile` block on the dossier with the six dimensions (Tourism Contribution, Visitor Economy Impact, Local Employment Potential, Cultural Preservation, Environmental Sustainability, Destination Growth Potential). The Tourism Signals engine already exists; this phase is a **scoring profile + UI section**, not a new engine: `kulima/signals/rules.py` gains a tourism rule pack producing the six sub-scores from existing signals, and the workspace template renders them.

### Phase 13 — Investment Readiness

Startup dossiers automatically include: Investment Readiness Score (exists as `investment_readiness` on the run), plus four sub-scores — Founder / Market / Traction / Due-Diligence Readiness — derived from existing founder/startup/market agent outputs and the EIE report. `Funding Recommendation` = existing `recommendation` field. Delivered as a `readiness_json` block in the dossier for `workspace_type = startup`.

### Phase 14 — Workflow Goal

Satisfied by Phases 2–5 combined: upload once (multi-doc, auto-research) → durable jobs process without the user → resume banner on return → export approved dossier → archive. **Acceptance test for the pilot:** kill the backend mid-processing, restart, and confirm the case reaches DECISION_READY without human intervention.

### Phase 15 — Final UX Goal

The 5-second story is the existing landing flow; the enterprise layer adds a **queue-first dashboard** (My Work on top) and a per-assessment workspace header showing lifecycle chip + research status chip + "last updated by" — visible in 5 seconds, like a bank statement list.

---

## 4. Database Changes

All migrations follow the established idempotent pattern (`PRAGMA table_info` guard + `ALTER TABLE`, as in `db.py::_migrate_schema`). New module `kulima/core/migrations.py` owns ordering.

**New tables:**

```sql
cases(id TEXT PK, org_id, workspace_type, case_type, subject_json, assessment_id UNIQUE,
      lifecycle_status, assignee_id, reviewer_id, version INTEGER DEFAULT 1,
      created_by, created_at, updated_at);

jobs(id TEXT PK, case_id, kind, status, payload_json, idempotency_key UNIQUE,
     attempts, max_attempts, run_after, lease_owner, lease_expires_at,
     created_at, updated_at);

research_packs(id TEXT PK, case_id, assessment_id, status, queries_json,
               sources_json, attempt_count, started_at, completed_at, error);

evidence_nodes(id TEXT PK, case_id, kind, source_json, document_id, claims_json, created_at);
evidence_edges(id TEXT PK, case_id, from_node, to_node, relation, weight);

comments(id TEXT PK, org_id, case_id, author_id, body, anchor_type, anchor_id,
         created_at, edited_at, deleted_at);
review_requests(id TEXT PK, case_id, kind, requested_by, requested_from,
                status, resolution_note, created_at, resolved_at);

dossiers(id TEXT PK, case_id UNIQUE, version, scores_json, recommendation,
         research_summary, executive_summary, generated_at, generated_by,
         approved_by, approved_at, pdf_path);
```

**Altered tables:**

- `assessment_contexts`: none (payload model extends, JSON is forgiving). Backfill `run_id` linkage into `cases.assessment_id`.
- `intelligence_runs`: add `case_id TEXT` (indexed; nullable during migration, backfilled by matching `assessment_contexts.run_id`).
- `audit_events`: add `ip_hash TEXT`, `user_agent TEXT`; extend `EVENT_TYPES`.
- `documents`: no schema change; add `assessment_id` backfill for legacy rows where only `run_id` is set.

**Pilot gate:** migrate SQLite → Postgres before organizational pilots. The lease-claim job runner and concurrent org access are built for it; SQLite remains dev-only. (This is the single biggest infra item.)

## 5. Migration Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **In-flight daemon threads lost on restart** — current behavior silently drops running assessments | **High** | JobRunner (Phase 4) is the prerequisite for *every* other phase; ship it first, behind the existing run endpoints |
| `payload_json` schema drift in stored `AssessmentContext`s (old rows fail `model_validate`) | High | Pydantic `model_validate` already tolerates added fields with defaults; add version stamp to payload; migration test with production `founders.db` snapshot |
| Backfilling `case_id` onto legacy `intelligence_runs` (nullable until claimed) | Medium | Follow the proven `claim_legacy_data` pattern from `OrgRepository`; idempotent, runs on first boot |
| Evidence-graph fusion changes Trust scores (leave-one-out + merged sources) vs. pilot expectations set by current UI | Medium | Freeze current scores as `scores_v0` on the dossier; run A/B for one sprint before cutover |
| SQLite write contention once JobRunner + audit + collaboration write concurrently | Medium | Move to Postgres at pilot gate; add `BEGIN IMMEDIATE` everywhere in interim |
| Role enforcement (Phase 7) may lock out pilot users used to full access | Medium | Default all existing org members to their current effective role; audit-only mode for 2 weeks (`transition()` logs would-be denials) before enforcing |
| Auto-launched Tavily research multiplies API cost per upload | Low | Per-plan quotas in `kulima/core/billing/plans.py`; debounce (one ResearchPack per case in flight) |
| Retention/encryption of new tables (Privacy Layer) | Low | New tables carry `org_id`; dossier PDFs reuse encrypted storage path; comments support soft-delete (audit retains) |

## 6. Build Order (suggested sprints)

1. **S1:** JobRunner + `jobs` table + rewire `orchestrator_adapter` (Phase 4 core). *Unblocks everything.*
2. **S2:** `cases` aggregate + lifecycle state machine + role enforcement (Phases 3, 4, 7).
3. **S3:** Auto ResearchPack + evidence graph fusion (Phase 2) + multi-doc polish (Phase 1).
4. **S4:** Work queues + pending tasks + resume banner (Phases 5, 6, 14).
5. **S5:** Collaboration + timeline event coverage (Phases 8, 9, 10).
6. **S6:** Decision dossier + tourism/investment profiles + export binding (Phases 11, 12, 13).

## 7. Final Verdict

**BLOCKERS REMAIN — but they are exactly two, and both are known quantities:**

1. **No durable transaction layer.** Background work lives in daemon threads; a process restart silently loses in-flight assessments. For an enterprise decision system this is the difference between a toy and a bank. (Fix: Phase 4 JobRunner — S1.)
2. **No lifecycle/role enforcement on assessments.** Anyone in an org can effectively do anything to any run; there is no review gate, no approval, no queue. (Fix: Phases 4 + 7 — S2.)

Everything else in the brief — multi-doc, fusion, workspaces, pending tasks, queues, timeline, activity log, collaboration, dossier, tourism and investment profiles — is **additive work over existing, working engines** with low architectural risk.

**Verdict: BLOCKERS REMAIN (2). Target READY FOR ORGANIZATIONAL PILOTS after Sprint 2 completes, full brief coverage by Sprint 6.** The design does not touch the UI paradigm or remove any functionality; it puts a banking-grade case-management chassis under the analysis engine you already have.
