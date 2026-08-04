# Kulima OS Web — Deployment Guide (Closed Beta)

This document describes how to deploy **Kulima OS Web** with:

- **Frontend:** Next.js app on Vercel
- **Backend:** FastAPI app on Render (or any Docker host)
- **Persistence:** SQLite + uploads on a mounted volume

The guide assumes you are deploying the current codebase without changing
intelligence logic or UI.

---

## 1. Architecture Overview

High-level components:

- **Frontend (Vercel / Next.js)**
  - Next.js 13 App Router (`frontend/`)
  - Authentication with NextAuth (Google + Microsoft providers)
  - Uses `NEXT_PUBLIC_API_URL` to talk to the backend

- **Backend (Render / FastAPI)**
  - FastAPI app at `backend/app/main.py`
  - Exposes REST + SSE API under `/api/v1`:
    - `/api/v1/intelligence` — create & inspect intelligence runs
    - `/api/v1/ask/ic` and `/api/v1/ask/ic/stream` — Ask IC
    - `/api/v1/ask/signals` and `/api/v1/ask/signals/stream` — Ask SIGNALS
    - `/api/v1/documents/` — document uploads
    - `/api/v1/health` — health check
  - Authentication via JWT (NextAuth-signed) using `NEXTAUTH_SECRET`
  - Persistence:
    - SQLite DB via `KULIMA_DB_PATH`
    - Uploaded files under `uploads/` (volume-backed directory)

- **Core OS intelligence (Python packages)**
  - `kulima/` contains:
    - LLM client (OpenAI), Research (Tavily), Evidence Integrity, Trust Graph
    - InvestmentOrchestrator, SignalsOrchestrator, Ask IC, Ask SIGNALS
    - Document ingestion and repository

---

## 2. Environment Variables

### 2.1 Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in values.

Required for closed beta:

```env
NEXTAUTH_SECRET="replace-with-long-random-string"

OPENAI_API_KEY="sk-..."

# Optional but recommended for OSINT
TAVILY_API_KEY=""

# SQLite database path (inside container / host)
KULIMA_DB_PATH="/data/kulima.db"

# CORS — comma-separated list of frontend origins
ALLOWED_ORIGINS="http://localhost:3000,https://your-vercel-app.vercel.app,https://app.kulimaos.com"

# OpenAI model used by kulima.llm.LLMClient
OPENAI_MODEL="gpt-4.1-mini"
```

Notes:

- `NEXTAUTH_SECRET` **must match** the secret used by NextAuth on the frontend.
- `KULIMA_DB_PATH` should live on a persistent volume (`/data/kulima.db`).
- `ALLOWED_ORIGINS` must include your Vercel domain for CORS to work.

### 2.2 Frontend (`frontend/.env.local`)

Copy `frontend/.env.local.example` to `frontend/.env.local` and fill in values.

Required for closed beta:

```env
# URL where the frontend is reachable
NEXTAUTH_URL="https://app.kulimaos.com"   # or http://localhost:3000 for dev

# Must match backend NEXTAUTH_SECRET
NEXTAUTH_SECRET="replace-with-long-random-string"

# Google OAuth
GOOGLE_CLIENT_ID="..."
GOOGLE_CLIENT_SECRET="..."

# Azure AD / Microsoft OAuth
AZURE_AD_CLIENT_ID="..."
AZURE_AD_CLIENT_SECRET="..."
AZURE_AD_TENANT_ID="..."

# Backend base URL
NEXT_PUBLIC_API_URL="https://api.kulimaos.com"  # or http://localhost:8000 for dev
```

Notes:

- `NEXT_PUBLIC_API_URL` is now used by all API calls in `frontend/lib/api.ts`.
- You can configure either or both OAuth providers (Google, Microsoft) in NextAuth.

---

## 3. Backend on Render

These steps also apply to any Docker-based host, but examples assume Render.

### 3.1 Create a Web Service

1. Build and push a Docker image for the `backend/` folder, or let Render build from Git.
2. Use the existing `backend/Dockerfile`:

   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY ./requirements.txt /app/requirements.txt
   RUN pip install --no-cache-dir -r /app/requirements.txt
   COPY . /app
   EXPOSE 8000
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

3. Set the service to listen on port **8000**.

### 3.2 Persistent Disk Configuration

1. Create a **persistent disk** (e.g., `/data`) in the Render service.
2. Mount it into the container at `/data`.
3. Ensure `KULIMA_DB_PATH=/data/kulima.db` in the environment.
4. Ensure that `uploads/` is also on this disk. You can:
   - Either leave `backend/uploads` and mount `/app/uploads` to `/data/uploads`, or
   - Configure the container so that `uploads` is a symlink into `/data/uploads`.

SQLite DB and uploaded files will then survive restarts.

### 3.3 Environment Variables

Add the values specified in **2.1** to the Render service.

Critical ones:

- `NEXTAUTH_SECRET`
- `OPENAI_API_KEY`
- `KULIMA_DB_PATH=/data/kulima.db`
- `ALLOWED_ORIGINS="https://app.kulimaos.com,https://your-vercel-app.vercel.app"`
- `OPENAI_MODEL` (optional override)
- `TAVILY_API_KEY` (if OSINT should work)

### 3.4 Health Checks

Configure HTTP health checks against:

- Path: `/api/v1/health`
- Method: `GET`
- Success: 200 JSON `{ "status": "ok" }`

Render will automatically restart the service if health checks fail.

### 3.5 Domain & TLS

1. Assign a custom domain, e.g. `api.kulimaos.com`, to the Render service.
2. Ensure HTTPS is enabled.
3. Update `NEXT_PUBLIC_API_URL` on Vercel to `https://api.kulimaos.com`.
4. Update `ALLOWED_ORIGINS` on the backend to include the Vercel / custom frontend domain.

---

## 4. Frontend on Vercel

### 4.1 Project Setup

1. Create a new Vercel project pointing to the `frontend/` directory.
2. Confirm:
   - Build command: `npm run build` (or `yarn build` / `pnpm build` according to your lockfile).
   - Output directory: `.next` (default for Next.js).

### 4.2 Environment Variables

Set the variables from **2.2** in the Vercel project’s Environment settings:

- `NEXTAUTH_URL` — e.g. `https://app.kulimaos.com`
- `NEXTAUTH_SECRET` — same as backend
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET`, `AZURE_AD_TENANT_ID`
- `NEXT_PUBLIC_API_URL` — e.g. `https://api.kulimaos.com`

You can use different values for Preview vs. Production environments if needed.

### 4.3 Domain Configuration

1. Attach your frontend domain (e.g. `app.kulimaos.com`) to the Vercel project.
2. Ensure DNS is pointing to Vercel.
3. Ensure that `ALLOWED_ORIGINS` on the backend includes this domain.

---

## 5. CORS Configuration

Backend CORS is configured in `backend/app/main.py`:

```python
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, set `ALLOWED_ORIGINS` to include only:

- `https://app.kulimaos.com`
- Any preview domains you want to support (optional)

Example:

```env
ALLOWED_ORIGINS="https://app.kulimaos.com,https://kulimaos-preview.vercel.app"
```

---

## 6. Health Checks & Monitoring

### 6.1 Health Endpoint

- Backend: `GET /api/v1/health` — returns `{ "status": "ok" }`.
- Use this for:
  - Render health checks
  - External uptime monitors (e.g. UptimeRobot, Pingdom)

### 6.2 Logging

- Backend logs to stdout/stderr using Python’s `logging` module.
  - Document uploads are logged as `document_upload` events with metadata.
  - Rate limit hooks log `rate_limit_check` at debug level (no enforcement yet).
- Ensure Render log retention meets your beta needs.

### 6.3 Error Tracking (Recommended)

For beta you can start simple:

- Frontend:
  - Integrate a service like Sentry for client-side errors.
- Backend:
  - Optionally add Sentry or structured logging to forward errors to a central store.

These are optional and can be added without changing intelligence logic.

---

## 7. Backup Procedures

### 7.1 SQLite Database

- File: `/data/kulima.db` (as configured by `KULIMA_DB_PATH`).
- Procedure (example):
  - Schedule a job (cron / external process) to:
    - Copy `/data/kulima.db` to `/data/backups/kulima-YYYYMMDDHHMM.db`.
    - Sync backups to cloud object storage (e.g. S3, Azure Blob, GCS).

### 7.2 Uploads Directory

- Directory: `/data/uploads` (or wherever you mounted uploads).
- Procedure:
  - Periodically sync `/data/uploads` to a bucket.
  - Optionally apply lifecycle rules (e.g. move older files to cheaper storage).

### 7.3 Restore (high-level)

1. Stop the backend service.
2. Replace `/data/kulima.db` and `/data/uploads` with backup copies.
3. Restart the backend.

Always test restore procedures on a staging environment before relying on them in production.

---

## 8. End-to-End Smoke Test Checklist

After deployment:

1. **Auth**
   - Visit `https://app.kulimaos.com`.
   - Sign in with Google or Microsoft.
   - Confirm that unauthenticated users cannot access `/flex` or `/signals` workspace.

2. **FLEX Flow (Investment)**
   - Start a run on `/flex` with a founder + startup.
   - Wait for status to move from `running` to `completed`.
   - Verify:
     - ChatShell works (Ask IC responses stream or return).
     - Context panel shows Decision Snapshot from real intelligence (no mock data).

3. **SIGNALS Flow**
   - Start a run on `/signals`.
   - Verify:
     - Signals Summary panel shows counts and top risks/opportunities.
     - Ask SIGNALS responds based on generated signals.

4. **Documents**
   - Upload a PDF and a spreadsheet under 20MB.
   - Confirm no upload errors; documents appear recorded in backend logs.
   - Re-run intelligence with documents (via Streamlit UI if needed) and verify
     that Decision Snapshot / Evidence Integrity / Trust Graph reflect changes.

5. **Ownership & Security**
   - Log in as User A and create a run.
   - Log in as User B and try to access User A’s runId via the API.
   - Confirm backend returns 401 Unauthorized.

If all steps pass, Kulima OS Web is ready for a closed beta with real users.
