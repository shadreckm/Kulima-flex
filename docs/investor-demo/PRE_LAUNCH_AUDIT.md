# Pre-Launch Deployment & Public Demo Validation

**Date:** 2026-08-15  
**Product:** Kulima OS  
**Scope:** Deploy readiness only — no new features, no UI redesign, no methodology changes.

---

## PART 1 — Deployment Readiness Audit

### Backend checklist

| Check | Result | Notes |
|---|---|---|
| Environment variables complete | PASS* | Documented in `backend/.env.example` + `docs/deployment.md`. `*`Must be set on Render. |
| No local-path dependencies | PASS* | Fixed: root `Dockerfile` packages `kulima/` + `scripts/`. Old `backend/Dockerfile` alone FAIL. |
| No hardcoded localhost in prod paths | PASS* | Defaults are localhost for dev; production uses `ALLOWED_ORIGINS` / `KULIMA_DB_PATH`. |
| No missing packages | PASS* | Added `pandas`, `tenacity` to `backend/requirements.txt`. |
| No missing migrations | PASS | Schema + `_migrate_schema()` on startup. |
| SQLite startup safe | PASS* | Safe if `KULIMA_DB_PATH` on persistent disk. Ephemeral disk = data loss risk. |
| Demo seed script available | PASS | `scripts/seed_demo_data.py --refresh --prepare-demo` |
| Offline mode enabled | PASS | Orchestrator falls back to OSTX template on live analysis failure. |

### Frontend checklist

| Check | Result | Notes |
|---|---|---|
| Build passes | PASS | `npm run build` exit 0 (Next 13.5.4). CSR deopt warnings on `/evidence`, `/reports` only. |
| Vercel compatible | PASS | Root Directory = `frontend`. No `vercel.json` required. |
| No localhost references | PASS* | Proxy defaults to `127.0.0.1` only when `NEXT_PUBLIC_API_URL` unset — must set on Vercel. |
| No broken routes | PASS | `/dashboard` `/runs` `/flex` `/signals` `/evidence` `/reports` `/analytics` `/feedback` `/settings` build. |
| Navigation shell consistent | PASS | Shared `NavigationSidebar` across pilot workspaces. |
| Report downloads work | PASS | Proxy streams PDF/TXT attachments. |
| Analytics metrics display | PASS | Evidence/Signal coverage from stored payloads. |

**Part 1 verdict:** Conditional PASS after Render uses root Dockerfile + env parity.

---

## PART 2 — Render Validation

| Item | Status | Exact fix |
|---|---|---|
| Start command | FIXED | Root `Dockerfile` → `uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}` |
| Health endpoint | PASS | `GET /api/v1/health` → `{status: ok}` |
| Environment variables | ACTION | Set `NEXTAUTH_SECRET`, `KULIMA_DB_PATH=/data/kulima.db`, `ALLOWED_ORIGINS`, optional OpenAI/Tavily |
| CORS | PASS* | Set `ALLOWED_ORIGINS` to Vercel domain(s). Browser mostly uses Next proxy (same-origin). |
| Auth callback URLs | N/A (FE) | OAuth callbacks are on Vercel, not Render. Secrets must match. |
| Database initialization | PASS | `IntelligenceRepository.initialize()` + auto-seed if empty |
| Startup sequence | PASS* | Requires `PYTHONPATH=/app` and `kulima`/`scripts` in image (root Dockerfile) |
| Persistent disk | ACTION | Mount `/data` via `render.yaml` or dashboard |
| Legacy backend-only Docker | FAIL if used | Do not deploy `backend/Dockerfile` alone |

**Blockers if ignored:** missing `kulima` imports, wiped SQLite on restart, mismatched JWT secret → 401s.

---

## PART 3 — Vercel Validation

| Item | Status | Notes |
|---|---|---|
| Build config | PASS | Root = `frontend`, `npm run build` |
| API proxy | PASS | `app/api/v1/[...path]/route.ts` mints JWT + streams files/SSE |
| NextAuth flow | PASS* | Google + Azure AD providers live on `kulima-flex.vercel.app/api/auth/providers`. Requires valid client secrets. |
| Route handlers | PASS | Auth + proxy force-dynamic |
| Report download handling | PASS | Binary passthrough for PDF/TXT |
| Environment variables | ACTION | Confirm `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, OAuth keys, `NEXT_PUBLIC_API_URL` point at live Render API |
| Live URL | CAUTION | `https://kulima-flex.vercel.app` returns 200; homepage redirects to `/dashboard` (session gate). HTML probe showed intermittent `__next_error__` shell — treat as **verify after backend URL is confirmed**. |

---

## PART 4 — Public Test Mode (no OpenAI credits)

Assumes: user can log in + backend has seeded OSTX dataset.

| Step | Status |
|---|---|
| 1. Login | PASS* (OAuth required — no guest mode) |
| 2. Browse demo runs | PASS (shared `user_id=NULL` rows) |
| 3. Open AgriNova Malawi | PASS |
| 4. Open GreenLink Foods | PASS |
| 5. Open SolarHarvest Cooperative | PASS |
| 6. View Signals | PASS (from stored brief) |
| 7. View Evidence | PASS |
| 8. View Analytics | PASS |
| 9. Download Reports | PASS |
| 10. Submit Feedback | PASS |

**Gaps:** No anonymous browse. Ask IC chat needs model credits. Fresh “Run Intelligence” without keys uses offline fallback (banner), not a crash — acceptable for demo if narrated.

---

## PART 5 — Investor Experience Audit

### Confusion / friction found
1. OAuth wall before any value (no guest tour)
2. “Checking session…” blank screen with no demo teaser
3. Flex vs Runs vs Evidence — first action unclear
4. Run IDs look technical (`ostx-…` / numeric) without human labels in sidebar “Current Run”
5. Dashboard doesn’t pin “Start here: AgriNova”
6. Settings page is thin / underwhelming for investors
7. Offline fallback banner may look like an error if not explained
8. Streamlit app still mentioned in root README — dual surface confusion
9. Feedback form lacks role / recommend fields (template provided externally)
10. No one-line product promise above the fold after login

### Top 10 minimal-effort credibility improvements
1. Pin three OSTX cards on Dashboard with one-click deep links  
2. Add one-line hero: “Evidence-gated Invest / Observe / Pass for African dealflow”  
3. Default Runs sort/filter to highlight AgriNova / GreenLink / SolarHarvest  
4. Replace empty session screen with “Sign in to explore OSTX validation cases” + case names  
5. Prefill Feedback comment template with Role / Impression / Recommend  
6. Hide or relabel Settings until it has substance  
7. Add “Demo dataset — no credits required” badge on Analytics / Runs  
8. Align root README to Web deploy (Vercel+Render), not only Streamlit  
9. Confirm production `NEXT_PUBLIC_API_URL` before sharing link widely  
10. Prepare printed / linked 5-min script from `docs/investor-demo/DEMO_SCRIPT.md`

---

## PART 6 — OSTX Presentation Mode Alignment

| OSTX workstream | Platform alignment | Overstatement risk |
|---|---|---|
| Customer Discovery | Investor-first OS, diligence bottleneck | Do not claim founder self-serve product |
| Market Study | Africa-first thesis + corridor cases | Do not claim global data coverage parity with PitchBook |
| Product Planning | Evidence Integrity + Syndicate + IC exports | Do not claim fully autonomous IC decisions |
| Current Platform | Seeded INVEST/OBSERVE/PASS differentiation | Do not imply live OSINT always-on without keys |

**Do not overstate:**
- Real-time OSINT without API keys  
- Guest/public access without login  
- Enterprise SSO / SOC2 readiness  
- Replacement of human analysts  
- Perfect coverage metrics on sparse Africa data (sparse-mode is a feature — say so)

---

## PART 7 — Public Feedback Collection

See: `docs/investor-demo/BETA_FEEDBACK_FORM.md`

Captures: role, first impression, confusion, favorite feature, recommendation (+ optional depth).

In-product: `/feedback` rating + comment (use comment template).

---

## PART 8 — Can you share https://kulima-flex.vercel.app today?

**Conditional NO-GO for broad public sharing until backend env is verified.**

| Audience | Share now? |
|---|---|
| Internal team / dry-run | YES (with known OAuth accounts) |
| OSTX mentors (controlled) | YES if login works + demo runs visible |
| Judges (panel day) | YES only after smoke checklist passes on production |
| NGOs / investors / accelerators (cold link) | NO until Render API + seed + downloads verified end-to-end |

---

## Final scores

| Score | Value |
|---|---|
| Deployment readiness | **72 / 100** |
| Backend readiness | **78 / 100** |
| Frontend readiness | **86 / 100** |
| Public testing readiness | **70 / 100** |
| Investor readiness | **80 / 100** |

### Top 5 deployment risks
1. Render built from `backend/` only → missing `kulima`/`scripts`  
2. No persistent disk → demo DB wiped on restart  
3. `NEXTAUTH_SECRET` mismatch → total 401  
4. `NEXT_PUBLIC_API_URL` unset/wrong → proxy to localhost on Vercel  
5. OAuth misconfigured → login wall, zero product access  

### Top 5 credibility improvements
1. Dashboard OSTX starter cards  
2. Clear “demo needs login, not credits” messaging  
3. README dual-surface cleanup  
4. Feedback role/recommend capture  
5. Confirmed production smoke before cold outreach  

### Final recommendation
**NO-GO for unrestricted public sharing today.**  
**GO for controlled OSTX / investor demos** after completing the Render root-Docker deploy + Vercel env parity + smoke checklist (≈ hours, not weeks).
