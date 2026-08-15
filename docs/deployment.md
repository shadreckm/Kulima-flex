# Kulima OS Web — Deployment Guide (Closed Beta / Public Demo)

This document describes how to deploy **Kulima OS Web** with:

- **Frontend:** Next.js app on Vercel (`frontend/`)
- **Backend:** FastAPI app on Render (repo-root Docker image)
- **Persistence:** SQLite + uploads on a mounted volume

Do not change intelligence methodology or redesign UI for deployment.

---

## 1. Architecture Overview

- **Frontend (Vercel / Next.js)**
  - App Router under `frontend/`
  - NextAuth (Google + Microsoft)
  - Browser calls same-origin `/api/v1/*`; the route handler proxies to the backend and mints a short-lived JWT using `NEXTAUTH_SECRET`

- **Backend (Render / FastAPI)**
  - Entry: `backend.app.main:app` (repo-root Docker)
  - REST + SSE under `/api/v1`
  - Health: `GET /api/v1/health`
  - SQLite via `KULIMA_DB_PATH`
  - Uploads under `backend/uploads` (mount to persistent disk in production)
  - Offline demo fallback + OSTX seed when DB is empty / LLM fails

---

## 2. Environment Variables

### 2.1 Backend (Render)

```env
NEXTAUTH_SECRET="must-match-frontend"
OPENAI_API_KEY="sk-..."          # optional for browsing seeded demos; required for live analysis
TAVILY_API_KEY=""                # optional
KULIMA_DB_PATH="/data/kulima.db"
ALLOWED_ORIGINS="https://kulima-flex.vercel.app,https://your-custom-domain.com"
OPENAI_MODEL="gpt-4.1-mini"
PYTHONPATH="/app"
```

### 2.2 Frontend (Vercel — Root Directory = `frontend`)

```env
NEXTAUTH_URL="https://kulima-flex.vercel.app"
NEXTAUTH_SECRET="must-match-backend"
GOOGLE_CLIENT_ID="..."
GOOGLE_CLIENT_SECRET="..."
AZURE_AD_CLIENT_ID="..."         # optional if Google-only
AZURE_AD_CLIENT_SECRET="..."
AZURE_AD_TENANT_ID="common"
NEXT_PUBLIC_API_URL="https://YOUR-RENDER-SERVICE.onrender.com"
```

**OAuth callback URLs to register:**
- `https://kulima-flex.vercel.app/api/auth/callback/google`
- `https://kulima-flex.vercel.app/api/auth/callback/azure-ad`

---

## 3. Backend on Render (exact)

1. Connect the GitHub repo.
2. Use **repo-root** Docker:
   - Dockerfile: `./Dockerfile`
   - Context: repository root
   - Or apply `render.yaml`
3. Attach a **persistent disk** at `/data` (SQLite survival).
4. Health check path: `/api/v1/health`
5. Set env vars from §2.1 — especially matching `NEXTAUTH_SECRET` and `ALLOWED_ORIGINS`.
6. After first boot, confirm auto-seed created OSTX cases, or run:
   ```bash
   python scripts/seed_demo_data.py --refresh --prepare-demo
   ```
   (inside a one-off shell with `PYTHONPATH=/app`)

**Do not** deploy with `backend/Dockerfile` alone — it omits `kulima/` and `scripts/`.

---

## 4. Frontend on Vercel (exact)

1. New project → Root Directory: `frontend`
2. Build: `npm run build` · Output: `.next`
3. Set env vars from §2.2
4. Redeploy after backend URL is known
5. Smoke: sign in → Dashboard → Runs → open AgriNova → Evidence / Reports / Analytics

`vercel.json` is optional for Next 13 App Router.

---

## 5. Public demo without OpenAI credits

Supported today (after login + seeded DB):

1. Browse demo runs
2. Open AgriNova / GreenLink / SolarHarvest
3. View Signals summary, Evidence, Analytics
4. Download Reports (PDF/TXT)
5. Submit Feedback

Not guaranteed offline:

- Fresh live intelligence runs (needs OpenAI; falls back to offline template if configured)
- Conversational Ask IC / Ask Signals streaming (needs model access)

---

## 6. Smoke checklist after deploy

1. `GET https://<api>/api/v1/health` → `{ "status": "ok" }`
2. Visit frontend → Sign in works
3. Runs list shows shared OSTX demos
4. Evidence loads integrity grade for AgriNova
5. Reports PDF downloads
6. Analytics shows Evidence Coverage / Signal Coverage
7. Feedback submit returns success

---

## 7. Backup

- Copy `/data/kulima.db` and `/data` uploads regularly to object storage.
- Test restore on staging before relying on it.
