# Render + Supabase Migration Readiness

## Recommendation

The Next.js frontend is technically compatible with Render as a native Node web service. The frontend deployment configuration is staged in `render.yaml`, including a shared NextAuth secret and private backend routing.

The complete target architecture is **not ready to cut over**. Supabase configuration and service classes exist, but the application still persists its production data in SQLite and uploaded files on the backend filesystem. Do not set `USE_SUPABASE=true` yet. Keep the current Vercel + Render deployment until the database and storage migrations below are implemented and validated.

## Current Request Flow

1. NextAuth v4 issues a JWT-backed session cookie after Google or Azure AD sign-in.
2. The Next.js `/api/v1/*` Node route calls `getToken()` with `NEXTAUTH_SECRET`, extracts the authenticated subject, and mints an HS256 bearer JWT.
3. FastAPI validates that bearer token with its startup-loaded `NEXTAUTH_SECRET`.
4. `get_current_org()` provisions or resolves the user's personal organization; the assessment route enforces `ASSESS`.
5. The intake API creates one Assessment Context. Its documents are ingested, then the context is reused by Research, Evidence, Signals, Decision, Reports, Activity, and Feedback.
6. Research and intelligence work run in backend workers/jobs. Repositories persist assessment, run, audit, signal, report and organization data through direct SQLite connections; upload/download paths use the backend filesystem.

The local runtime returned a valid `/api/auth/session`, but the proxied assessment request returned `SESSION_INVALID`. The frontend had decoded the session subject and forwarded Authorization; backend JWT verification failed before organization resolution. A shared Render environment group removes the cross-service secret drift, but production auth still needs a staging smoke test before cutover.

Before syncing the generated `kulima-auth` group onto an existing production backend, seed the group with the chosen verified secret if existing sessions should remain valid. Otherwise, treat the generated value as an intentional key rotation and expect users to sign in again. Never copy a secret into this repository.

## Feasibility

1. **Next.js on Render:** Yes, as a Node web service. This app uses App Router pages, NextAuth, and server route handlers, so it must not be deployed as a static site.
2. **Required changes:** Use `npm ci`, `npm run build`, and `npm start -- -p $PORT`; set the canonical `NEXTAUTH_URL`; set Google/Azure OAuth values; share one `NEXTAUTH_SECRET`; point the proxy at the Render backend over Render's private network; update OAuth callback registrations.
3. **Vercel-specific features:** No Vercel SDK or Vercel-only service is used by the app source. The proxy explicitly selects the Node runtime. `maxDuration = 60` is a Vercel-oriented route hint and has no equivalent effect on Render. The existing Vercel env example/deployment guide and NextAuth's `VERCEL_URL` fallback are the remaining Vercel references. Set `NEXTAUTH_URL` explicitly on Render.
4. **What changes at cutover:** Google/Azure callback URLs and cookie origin change, so users sign in again. Any Vercel domain, analytics, DNS or deployment integrations must be updated. Render uses a persistent Node service; it is not Vercel's per-request serverless runtime.
5. **Authentication impact:** The session cookie remains owned by NextAuth. The API proxy continues to mint a short-lived backend token. Both services must share the same secret. The Blueprint's `kulima-auth` environment group generates one value and injects it into both services.
6. **NextAuth impact:** No provider or session strategy change is needed. Set `NEXTAUTH_URL` to the Render frontend URL and add `https://<render-frontend-host>/api/auth/callback/google` (and Azure AD if enabled) to the identity provider's redirect allowlist.
7. **Build impact:** The existing frontend lockfile supports deterministic `npm ci`. Build and start it as a Node web service; do not use static export. Render injects `PORT` at runtime.

## Supabase Readiness Blockers

- `kulima/core/database.py` is not used by the domain repositories. The assessment, cases, jobs, research, collaboration, dossier, audit, documents, organizations, billing, legacy intelligence, and API run repositories still use `sqlite3` directly.
- `kulima/core/storage/storage_service.py` is not called by the active document adapter or document routes. Uploads and reads still use `backend/uploads`.
- SQLAlchemy, a PostgreSQL driver, and the Supabase Python client are absent from the backend requirements.
- The Postgres migrations in `kulima/core/migrations.py` are placeholders; the current runner is SQLite-specific. There is no tested SQLite-to-Postgres data import or rollback procedure.
- Storage bucket RLS/path rules have not been validated against the active backend service identity. The service-role key must remain backend-only.
- The current Render disk is mounted at `/data` for SQLite. The Docker image now links the existing upload path into `/data/uploads` so uploads persist during the interim SQLite phase. This is not a substitute for Supabase Storage.

Enabling `USE_SUPABASE=true` today does not redirect those active repository/storage call sites and must not be treated as a migration.

## Target Blueprint

- **Render frontend:** Native Node web service from `frontend/`; serves Next.js SSR, NextAuth, and the authenticated API proxy.
- **Render backend:** Existing root Docker service; remains the only service with OpenAI, Tavily, billing and database credentials.
- **Render private network:** Frontend proxy uses the backend's private `hostport`; browser calls remain same-origin under `/api/v1/*`.
- **Supabase Postgres:** Planned system of record after all repositories and migrations are ported. `DATABASE_URL` stays unset and `USE_SUPABASE=false` until then.
- **Supabase Storage:** Planned private document store after upload, download, export, retention, delete and signed-access paths are migrated and RLS-tested.

## Migration Sequence

1. Deploy a staging Render frontend and backend with the shared `kulima-auth` group; verify Google callback, session, `/api/v1/auth/diagnostic`, organization provisioning and `ASSESS` permission.
2. Exercise assessment create, multiple uploads, research completion, evidence, signals, decision, report export, activity events and feedback on staging. Confirm errors/logs and data isolation.
3. Add and test PostgreSQL drivers and real Postgres migrations. Migrate every direct-SQLite repository, including service-level direct queries. Run the full backend suite against both SQLite and Supabase/Postgres before enabling the flag.
4. Implement a snapshot import with row counts, ownership checks, foreign-key checks, and document checksum reconciliation. Run restore and rollback rehearsals.
5. Migrate document writes/reads/deletes/exports and retention to the private Supabase bucket. Test service-role isolation, RLS, signed URLs, large files, and failure recovery.
6. Run the full workflow suite against the migrated staging stack, monitor it, then schedule a coordinated production cutover. Rotate/reuse the shared auth secret intentionally and expect existing sessions to be invalidated if it changes.
7. Keep Vercel and the old backend/data snapshot available until post-cutover reconciliation and rollback windows close.

## Render Frontend Environment

| Variable | Value / handling |
| --- | --- |
| `NODE_VERSION` | `20.19.0` (Blueprint) |
| `NEXTAUTH_URL` | Frontend `RENDER_EXTERNAL_URL` (Blueprint reference) |
| `NEXTAUTH_SECRET` | Generated once in shared `kulima-auth` group; same value on frontend and backend |
| `GOOGLE_CLIENT_ID` | Existing Google OAuth client ID; copy to Render, keep secret values out of Git |
| `GOOGLE_CLIENT_SECRET` | Existing Google OAuth client secret |
| `AZURE_AD_CLIENT_ID` | Optional; only if Azure AD is enabled |
| `AZURE_AD_CLIENT_SECRET` | Optional secret; only if Azure AD is enabled |
| `AZURE_AD_TENANT_ID` | Optional; only if Azure AD is enabled |
| `KULIMA_BACKEND_HOSTPORT` | Render private service reference to `kulima-os-api` |
| `KULIMA_BACKEND_URL` | Optional absolute URL override; normally unset |
| `NEXT_PUBLIC_API_URL` | Legacy/local fallback; normally unset on Render |
| `PORT` | Supplied by Render; do not hardcode |

## Render Backend Environment

| Variable | Value / handling |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `ALLOWED_ORIGINS` | Frontend `RENDER_EXTERNAL_URL` (Blueprint reference); include custom domain if used |
| `NEXTAUTH_SECRET` | Same generated value from `kulima-auth` group |
| `OPENAI_API_KEY` | Existing secret; required for live analysis |
| `OPENAI_MODEL` | `gpt-4.1-mini` |
| `SYNDICATE_MODEL` | `gpt-4.1-mini` |
| `FUTURES_MODEL` | `gpt-4.1-mini` |
| `TAVILY_API_KEY` | Existing secret; required for live external research |
| `MAX_RESEARCH_RESULTS` | `8` |
| `AFRICA_FOCUS` | `true` |
| `KULIMA_DB_PATH` | `/data/kulima.db` during the SQLite transition only |
| `PYTHONPATH` | `/app` |
| `KULIMA_RATE_LIMIT_REQUESTS` | `60` |
| `KULIMA_RATE_LIMIT_WINDOW_SECONDS` | `60` |
| `KULIMA_BILLING_ENFORCEMENT` | `false` until explicitly enabled |
| `KULIMA_BILLING_DEMO_MODE` | `false` |
| `KULIMA_GRACE_PERIOD_DAYS` | `7` |
| `KULIMA_PLAN_CURRENCY` | `USD` |
| `KULIMA_PLAN_PRICING_JSON` | Optional; blank unless overriding prices |
| `PAYCHANGU_SECRET_KEY` | Optional payment secret |
| `PAYCHANGU_WEBHOOK_SECRET` | Optional webhook secret |
| `PAYCHANGU_CURRENCY` | `USD` |
| `PAYCHANGU_API_BASE` | `https://api.paychangu.com` |
| `KULIMA_DOC_ENCRYPTION_KEY` | Optional secret; configure only if document encryption is enabled |
| `KULIMA_DEFAULT_RETENTION_DAYS` | `0` |
| `KULIMA_ACCESS_MODE` | `pilot` |
| `KULIMA_GUEST_DAILY_LIMIT` | `3` |
| `KULIMA_ANALYST_DAILY_LIMIT` | `25` |
| `KULIMA_INVESTOR_DAILY_LIMIT` | `10` |
| `KULIMA_ADMIN_EMAILS` | Optional comma-separated admin list |
| `KULIMA_SKIP_AUTH` | `false`; never enable in production |

## Supabase Environment (Backend Only)

| Variable | Value / handling |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Public/anon key; not a substitute for a backend service credential |
| `SUPABASE_KEY` | Legacy StorageService setting; remove/standardize when the storage adapter is migrated |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret; backend only, never expose to frontend |
| `DATABASE_URL` | Supabase PostgreSQL connection string; use a supported pooler/connection mode for the Render service |
| `USE_SUPABASE` | Keep `false` until every active repository and migration is ported |
| `STORAGE_BUCKET_NAME` | `kulima-documents` |
| `SUPABASE_DOCUMENT_BUCKET` | Legacy alias; current code does not read this name |

No Supabase credentials or OAuth/API secret values are included in these templates. Values that already match the target can be copied from the current secret manager; do not commit them.

## Go / No-Go

**No-go for full migration today.** The Render frontend move is feasible and its service wiring is staged, but Supabase Postgres and Storage are not connected to the active application paths. Runtime login and assessment creation also require a staging confirmation that both services use the same `NEXTAUTH_SECRET`; the local proxy currently receives `SESSION_INVALID` from the backend. Keep Vercel + Render until the stated Supabase and auth gates pass.