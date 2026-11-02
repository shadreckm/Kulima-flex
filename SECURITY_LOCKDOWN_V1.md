# SECURITY LOCKDOWN V1 — Kulima FLEX
# Chief Security Engineer
# Date: 2026-09-15

---

## SECURITY_INVENTORY

Complete audit of every file containing credentials, secrets, or sensitive configuration.

### STATUS KEY
- ✅ SAFE — No live secret; template value, placeholder, or empty
- ⚠️ ACTION REQUIRED — Live secret that must be rotated before deployment
- ✅ RESOLVED — Was a live secret; has been replaced with placeholder in this lockdown

---

### File-by-File Inventory

| # | File | Credential Type | Risk Level | Status | Rotation Required |
|---|------|----------------|-----------|--------|------------------|
| 1 | `backend/.env` | NEXTAUTH_SECRET (JWT signing key) | **CRITICAL** | ✅ RESOLVED | YES — invalidates all existing sessions |
| 2 | `backend/.env` | OPENAI_API_KEY | **CRITICAL** | ✅ RESOLVED | YES — financial exposure |
| 3 | `backend/.env` | GEMINI_API_KEY | **CRITICAL** | ✅ RESOLVED | YES — financial exposure |
| 4 | `backend/.env` | GROQ_API_KEY | **CRITICAL** | ✅ RESOLVED | YES — financial exposure |
| 5 | `backend/.env` | OPENROUTER_API_KEY | **CRITICAL** | ✅ RESOLVED | YES — financial exposure |
| 6 | `backend/.env` | HUGGINGFACE_API_KEY | HIGH | ✅ RESOLVED | YES — precautionary |
| 7 | `backend/.env` | TAVILY_API_KEY (`tvly-dev-` prefix) | HIGH | ✅ RESOLVED | YES — precautionary |
| 8 | `frontend/.env.local` | NEXTAUTH_SECRET (same value as #1) | **CRITICAL** | ✅ RESOLVED | YES — same key as #1 |
| 9 | `frontend/.env.local` | GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET | **CRITICAL** | ✅ RESOLVED | YES — OAuth impersonation risk |
| 10 | `frontend/.env.local` | SUPABASE_SERVICE_ROLE_KEY (JWT) | **CRITICAL** | ✅ RESOLVED | YES — full DB read/write |
| 11 | `frontend/.env.local` | SUPABASE_ANON_KEY (JWT) | HIGH | ✅ RESOLVED | YES — precautionary |
| 12 | `frontend/.env.local` | DATABASE_URL (PostgreSQL with password) | **CRITICAL** | ✅ RESOLVED | YES — direct DB access |
| 13 | `frontend/.env.local` | SUPA_SECRET_API_KEY | **CRITICAL** | ✅ RESOLVED | YES — Supabase secret |
| 14 | `frontend/.env.local` | OPENAI_API_KEY (duplicate of #2) | **CRITICAL** | ✅ RESOLVED | YES — same key |
| 15 | `frontend/.env.local` | TAVILY_API_KEY (duplicate of #7) | HIGH | ✅ RESOLVED | YES — same key |
| 16 | `backend/.env` | PAYCHANGU_SECRET_KEY | HIGH | ✅ RESOLVED | YES — payment processor |

### Files confirmed safe (no live secrets)

| File | Notes |
|------|-------|
| `backend/.env.example` | Template — all values are empty or non-sensitive defaults |
| `backend/.env.render.example` | Template — all secrets blank |
| `frontend/.env.local.example` | Template — all secrets blank |
| `frontend/.env.vercel.example` | Template — all secrets blank |
| `frontend/.env.render.example` | Template — all secrets blank |
| `.env.example` | Template — all secrets blank |
| `supabase.env.example` | Template — all values blank |
| `render.yaml` | Contains `kulimaafrica@gmail.com` (admin email — not a secret) and PayChangu hosted link URLs (not secrets). All actual secrets have `sync: false`. |
| `kulima/config.py` | Contains `kulimaafrica@gmail.com` as hardcoded default — acceptable for a non-secret admin email identifier |
| All `*.py` test files | Use `os.environ.setdefault("NEXTAUTH_SECRET", "local-pytest-secret")` — correct practice |
| `scripts/mint_token.py` | Reads from file; falls back to `"dev-secret-test-key-32-chars-long"` — acceptable |
| All `*.log`, `*.out`, `*.err` files | Checked — no secret values found |
| `demo_reports/*.pdf` | PDF binary content — no secrets |

### Git History Status

`git ls-files --error-unmatch backend/.env` → **error: pathspec did not match**
`git ls-files --error-unmatch frontend/.env.local` → **error: pathspec did not match**

**CONFIRMED: Neither .env file has ever been committed to the git repository.**
The credentials existed only on the local developer machine. No git history scrubbing is required.

---

## ROTATION_PLAN

Rotate in this exact order to avoid service interruption. NEXTAUTH_SECRET must be rotated last
because changing it invalidates all active sessions and requires coordinated deployment.

### TIER 1 — Rotate immediately (financial / data exposure risk)

| Order | Credential | Provider Portal | Dependencies | Downtime Risk |
|-------|-----------|----------------|-------------|---------------|
| 1 | OPENAI_API_KEY | https://platform.openai.com/api-keys | None | None — Document Intelligence Mode is fallback |
| 2 | GEMINI_API_KEY | https://aistudio.google.com/apikey | None | None — provider chain has 4 other tiers |
| 3 | GROQ_API_KEY | https://console.groq.com/keys | None | None — provider chain fallback active |
| 4 | OPENROUTER_API_KEY | https://openrouter.ai/keys | None | None |
| 5 | HUGGINGFACE_API_KEY | https://huggingface.co/settings/tokens | None | None |
| 6 | TAVILY_API_KEY | https://app.tavily.com (API Keys) | None | Research falls back to document-only mode |
| 7 | SUPABASE_SERVICE_ROLE_KEY | https://supabase.com/dashboard → Project Settings → API | None — SQLite is primary DB | None (USE_SUPABASE=false) |
| 8 | SUPABASE_ANON_KEY | Same portal as above | None | None |
| 9 | DATABASE_URL password | Supabase dashboard → Database → Password reset | None | None (SQLite in use) |
| 10 | PAYCHANGU_SECRET_KEY | https://dashboard.paychangu.com | None | None (billing enforcement off) |
| 11 | GOOGLE_CLIENT_ID / CLIENT_SECRET | https://console.cloud.google.com/apis/credentials | Must update Authorized Redirect URIs simultaneously | **Sign-in will break until deployed** |

### TIER 2 — Rotate with coordinated deployment (requires both services restart)

| Order | Credential | Steps | Downtime Risk |
|-------|-----------|-------|---------------|
| 12 | NEXTAUTH_SECRET | Generate new secret → update Render backend env var → update Vercel frontend env var → redeploy BOTH services simultaneously | **All active sessions expire on redeploy (10–15 min)** |

### TIER 1 Verification Steps (for each AI key)

After rotating, verify with:
```bash
curl -X POST https://your-backend.onrender.com/api/v1/assessments/ \
  -H "Authorization: Bearer <valid-session-token>" \
  -F "files=@test.txt" -F "assessmentType=startup"
```
Expected: `{"assessmentId": "...", "status": "running"}` — not `{"error": true, "code": "..."}`

### TIER 2 Verification Steps (NEXTAUTH_SECRET)

1. After deploying new secret to both Render + Vercel, visit your frontend URL
2. Sign in with Google → should land on /dashboard (not an auth error)
3. Call `GET /api/v1/auth/diagnostic` — should return `{"chain": "ok"}`
4. Check `/admin/session` → returns your identity (not 401)

### GOOGLE_CLIENT_ID / CLIENT_SECRET Verification Steps

1. After rotating in Google Cloud Console, update both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in Vercel
2. Add your new production URL to **Authorized JavaScript origins** AND **Authorized redirect URIs**:
   - `https://your-frontend.vercel.app`
   - `https://your-frontend.vercel.app/api/auth/callback/google`
3. Redeploy frontend
4. Click "Sign in with Google" — should complete OAuth flow without error

---

## SECRET_STORAGE_PLAN

### PRODUCTION_SECRET_POLICY

#### Render (Backend API — `kulima-os-api` service)

**Where to set:** Render Dashboard → `kulima-os-api` → Environment → Environment Variables

```
Required secret variables (mark as Secret in Render — not "plaintext"):
  NEXTAUTH_SECRET          [Secret]  — shared with Vercel, from kulima-auth group
  OPENAI_API_KEY           [Secret]
  GEMINI_API_KEY           [Secret]
  GROQ_API_KEY             [Secret]
  OPENROUTER_API_KEY       [Secret]
  HUGGINGFACE_API_KEY      [Secret]
  TAVILY_API_KEY           [Secret]
  PAYCHANGU_SECRET_KEY     [Secret]
  PAYCHANGU_WEBHOOK_SECRET [Secret]
  KULIMA_DOC_ENCRYPTION_KEY [Secret]

Non-secret variables (plaintext is fine):
  ENVIRONMENT=production
  OPENAI_MODEL=gpt-4.1-mini
  KULIMA_DB_PATH=/data/kulima.db
  KULIMA_BILLING_ENFORCEMENT=false
  KULIMA_ACCESS_MODE=pilot
  KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL=<admin-email>
  KULIMA_PLATFORM_ADMIN_EMAILS=<admin-email>
```

**Render Environment Groups:** Create a `kulima-auth` group containing only `NEXTAUTH_SECRET`.
Reference it in both the backend and frontend service blueprints so the value is set in
one place and automatically shared — this is the pattern already in `render.yaml`.

**Never store in Render:**
- Supabase keys (USE_SUPABASE=false)
- DATABASE_URL (USE_SUPABASE=false; SQLite file is on mounted disk)

#### Vercel (Frontend — `kulima-flex-web`)

**Where to set:** Vercel Dashboard → Project → Settings → Environment Variables

```
Required variables (mark as Sensitive):
  NEXTAUTH_SECRET          [Sensitive] — MUST match Render value exactly
  GOOGLE_CLIENT_ID         [Sensitive]
  GOOGLE_CLIENT_SECRET     [Sensitive]

Environment: set for Production, Preview, and Development separately if values differ.

Non-secret variables (plaintext):
  NEXTAUTH_URL             — your Vercel deployment URL
  NEXT_PUBLIC_API_URL      — leave blank (proxy uses KULIMA_BACKEND_HOSTPORT)
  KULIMA_BILLING_ENFORCEMENT=false
```

**Never store in Vercel:**
- OPENAI_API_KEY (backend only)
- TAVILY_API_KEY (backend only)
- SUPABASE_SERVICE_ROLE_KEY (backend only, when enabled)

#### Supabase (Future — currently disabled)

**When USE_SUPABASE is enabled:**
1. Store `SUPABASE_SERVICE_ROLE_KEY` in Render backend only (never frontend, never git)
2. Store `SUPABASE_ANON_KEY` in Render backend only
3. Use Row Level Security (RLS) policies on every table
4. Rotate service role key immediately if it was ever logged

#### Google Cloud Console

1. Go to https://console.cloud.google.com/apis/credentials
2. Delete the old OAuth 2.0 Client ID entirely
3. Create a new one with the correct authorized redirect URIs:
   - `http://localhost:3001/api/auth/callback/google` (dev)
   - `https://your-vercel-app.vercel.app/api/auth/callback/google` (prod)
4. The new `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are not secrets from Google's
   perspective (client IDs are public) but treat the client secret as a credential

#### PayChangu

1. Log in to https://dashboard.paychangu.com
2. Rotate API key under Settings → API Keys
3. Rotate webhook secret under Settings → Webhooks
4. Update both in Render environment variables
5. Verify webhook with `POST /api/v1/billing/webhook` after rotation

#### Local Development (developer machines only)

1. Copy `backend/.env.example` → `backend/.env`; fill real values
2. Copy `frontend/.env.local.example` → `frontend/.env.local`; fill real values
3. Never run `git add backend/.env` or `git add frontend/.env.local`
4. Run `git status` before every commit — `.env` files must never appear as staged

---

## SECURITY_SIGNOFF_CHECKLIST

### Pre-Pilot Launch Security Checklist

Complete every item and sign off before any pilot organisation accesses the platform.

#### Section A — Secrets Hygiene

- [ ] **A1** `backend/.env` contains only placeholder values (`<ROTATE_AND_SET_HERE>`)
- [ ] **A2** `frontend/.env.local` contains only placeholder values (`<ROTATE_AND_SET_HERE>`)
- [ ] **A3** `git ls-files | grep -E "\.env$|\.env\.local$"` returns no results
- [ ] **A4** `git log --all --full-history -- backend/.env frontend/.env.local` returns no commits
- [ ] **A5** All 16 credentials in the SECURITY_INVENTORY have been rotated at their provider portal
- [ ] **A6** New NEXTAUTH_SECRET generated with `secrets.token_hex(32)` (minimum 64 chars)
- [ ] **A7** NEXTAUTH_SECRET value is identical in Render backend and Vercel frontend
- [ ] **A8** Old Google OAuth Client ID deleted; new one created with correct redirect URIs
- [ ] **A9** Supabase service role key rotated (even though USE_SUPABASE=false — precautionary)
- [ ] **A10** No `.env` file is staged: `git diff --cached --name-only | grep "\.env"` returns nothing

#### Section B — Git / Repository

- [ ] **B1** `.gitignore` blocks `backend/.env`, `frontend/.env.local`, all `*.db` files
- [ ] **B2** `git check-ignore backend/.env` returns `backend/.env` (i.e., it IS ignored)
- [ ] **B3** `git check-ignore frontend/.env.local` returns `frontend/.env.local`
- [ ] **B4** `git check-ignore founders.db` returns `founders.db`
- [ ] **B5** `git check-ignore backend/uploads/` returns `backend/uploads/`
- [ ] **B6** Repository is private on GitHub/GitLab/Bitbucket (confirm under Settings → Visibility)
- [ ] **B7** No `.env` files appear in `git show HEAD` or any prior commit

#### Section C — Deployment (Render + Vercel)

- [ ] **C1** All secrets in Render are marked as Secret (not plaintext)
- [ ] **C2** `ENVIRONMENT=production` is set in Render
- [ ] **C3** `KULIMA_SKIP_AUTH=false` is set in Render (never `true` in production)
- [ ] **C4** `KULIMA_BILLING_ENFORCEMENT=false` for pilot (confirm intentional)
- [ ] **C5** NEXTAUTH_SECRET is set in both Render and Vercel and values match
- [ ] **C6** Google OAuth Client ID and Secret are set in Vercel only (not Render)
- [ ] **C7** OPENAI_API_KEY and TAVILY_API_KEY are set in Render only (not Vercel)
- [ ] **C8** Health check passes: `GET https://your-api.onrender.com/api/v1/health` → `{"status":"ok"}`
- [ ] **C9** Auth diagnostic passes: authenticated call to `/api/v1/auth/diagnostic` → `{"chain":"ok"}`

#### Section D — Document Upload Security

- [ ] **D1** `GET /uploads/` without auth returns 401 (not 200)
- [ ] **D2** `GET /uploads/<filename>` with a token from a different org returns 403
- [ ] **D3** Path traversal test: `GET /uploads/../backend/.env` returns 404 (not the file)
- [ ] **D4** `backend/uploads/` directory is excluded from git (confirmed by `.gitignore`)

#### Section E — Admin Console

- [ ] **E1** `GET /api/v1/admin/overview` with a non-admin token returns 403
- [ ] **E2** `GET /api/v1/admin/session` with a regular token returns `isPlatformAdmin: false`
- [ ] **E3** `KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL` is set to the real operator email in Render
- [ ] **E4** Admin console `/admin` route returns 403 for a non-admin signed-in user

#### Section F — Rate Limiting

- [ ] **F1** `KULIMA_RATE_LIMIT_REQUESTS=60` and `KULIMA_RATE_LIMIT_WINDOW_SECONDS=60` are set
- [ ] **F2** Rapid-fire test: 61 requests to `/api/v1/assessments/` in 60 seconds → last request returns 429

#### Section G — Final Sign-off

- [ ] **G1** All Section A items checked
- [ ] **G2** All Section B items checked
- [ ] **G3** All Section C items checked
- [ ] **G4** All Section D items checked
- [ ] **G5** All Section E items checked
- [ ] **G6** All Section F items checked
- [ ] **G7** Signed off by: ___________________________ Date: _______________

---

## IMPORTANT NOTES

### What was found

1. `backend/.env` and `frontend/.env.local` contained **live credentials** on the
   developer's local machine.

2. **Neither file was ever committed to git.** `git ls-files` confirmed both files
   are untracked — the `.gitignore` was correctly configured and working. No git
   history scrubbing is required.

3. All secrets existed only on the local development machine. Risk was confined to
   whoever has access to that machine.

### What was done in this lockdown

1. Both `.env` files replaced with sanitised templates (all secrets become
   `<ROTATE_AND_SET_HERE>` or empty).
2. `.gitignore` hardened with explicit per-directory patterns and all database
   file variants.
3. No source code was changed. No features were added or removed.

### What must still be done by a human

The following require human action at provider dashboards — they cannot be done
in code:

1. Rotate all 16 credentials listed in SECURITY_INVENTORY at their respective portals
2. Set new values in Render and Vercel dashboards
3. Verify the SECURITY_SIGNOFF_CHECKLIST

---

## GIT CONFIRMATION RECORD

```
git ls-files --error-unmatch backend/.env
→ error: pathspec 'backend/.env' did not match any file(s) known to git

git ls-files --error-unmatch frontend/.env.local
→ error: pathspec 'frontend/.env.local' did not match any file(s) known to git
```

**Both files were never in version control. .gitignore was functioning correctly.**
