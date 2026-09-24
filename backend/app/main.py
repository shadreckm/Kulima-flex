import os
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi import HTTPException
from contextlib import asynccontextmanager

from kulima.core.documents.repository import DocumentRepository
from kulima.core.security.encryption import decrypt_bytes, is_encrypted

from .core.rate_limit import RateLimitMiddleware
from .routers import (
    intelligence,
    ask_ic,
    ask_signals,
    documents,
    outcomes,
    assessments,
    orgs,
    billing,
    governance,
    cases,
    tasks,
    auth_diagnostics,
)

# Phase 4 Enterprise: Import job runner
try:
    from kulima.core.jobs.runner import JobRunner
    JOB_RUNNER_AVAILABLE = True
except ImportError:
    JOB_RUNNER_AVAILABLE = False

# Phase 4 Enterprise: Job runner instance
_job_runner: JobRunner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for enterprise features."""
    # Startup
    global _job_runner
    if JOB_RUNNER_AVAILABLE:
        try:
            _job_runner = JobRunner()
            import asyncio
            # Properly await startup to ensure initialization
            await _job_runner.start()
            # Give it a moment to initialize worker loop
            await asyncio.sleep(0.1)
            print("Enterprise JobRunner started successfully")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to start JobRunner: {exc}")
            _job_runner = None

    yield

    # Shutdown
    if _job_runner:
        try:
            import asyncio
            # Properly await shutdown
            await _job_runner.stop()
            print("Enterprise JobRunner stopped successfully")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to stop JobRunner: {exc}")


app = FastAPI(title="Kulima FLEX API", version="2.0.0", lifespan=lifespan)

environment = os.environ.get("ENVIRONMENT", "development").strip().lower()
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if environment != "production":
    for local_origin in ("http://localhost:3000", "http://localhost:3001"):
        if local_origin not in allowed_origins:
            allowed_origins.append(local_origin)
elif not allowed_origins:
    raise RuntimeError("ALLOWED_ORIGINS must be configured in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

# Mount routers at API prefixes
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["assessments"])
app.include_router(intelligence.router, prefix="/api/v1/intelligence", tags=["intelligence"])
app.include_router(ask_ic.router, prefix="/api/v1/ask", tags=["ask_ic"])
app.include_router(ask_signals.router, prefix="/api/v1/ask", tags=["ask_signals"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(outcomes.router, prefix="/api/v1/outcomes", tags=["outcomes"])
app.include_router(orgs.router, prefix="/api/v1/orgs", tags=["orgs"])
app.include_router(auth_diagnostics.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(governance.router, prefix="/api/v1/governance", tags=["governance"])

# Phase 4 Enterprise: case workspace + task queues (self-prefixed routers)
app.include_router(cases.router, tags=["cases"])
app.include_router(tasks.router, tags=["tasks"])

# ── Guarded upload serving (Phase 5 — Document Security) ────────────────────
# Replaces the previous StaticFiles mount. Every served file is validated:
#   1. filename must be a plain basename matching a strict allow-list pattern;
#   2. the resolved path must stay inside the uploads directory;
#   3. soft-deleted documents return 404, expired documents return 410;
#   4. at-rest encrypted documents are decrypted in-memory before serving;
#   5. legacy pre-registry files remain reachable (capability-URL semantics).
# Must match document_adapter.UPLOAD_DIR (backend/uploads), not repo-root uploads/.
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
os.makedirs(uploads_dir, exist_ok=True)

_SAFE_UPLOAD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,180}$")
_doc_repo_singleton: DocumentRepository | None = None


def _document_registry() -> DocumentRepository:
    global _doc_repo_singleton
    if _doc_repo_singleton is None:
        _doc_repo_singleton = DocumentRepository()
    return _doc_repo_singleton


@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    if not _SAFE_UPLOAD_NAME.match(filename) or ".." in filename or filename != os.path.basename(filename):
        raise HTTPException(status_code=404, detail={"error": True, "message": "File not found"})

    target = os.path.realpath(os.path.join(uploads_dir, filename))
    root = os.path.realpath(uploads_dir)
    if not target.startswith(root + os.sep):
        raise HTTPException(status_code=404, detail={"error": True, "message": "File not found"})

    registry = None
    try:
        registry = _document_registry().find_by_storage_path(filename)
    except Exception:  # noqa: BLE001 — registry failure must not break legacy serving
        registry = None

    if registry is not None:
        if registry.get("deletedAt"):
            raise HTTPException(status_code=404, detail={"error": True, "message": "File not found"})
        if DocumentRepository.is_expired(registry):
            raise HTTPException(
                status_code=410,
                detail={"error": True, "message": "This document has passed its retention window and is no longer available."},
            )
        media_type = registry.get("mimeType") or "application/octet-stream"
        if is_encrypted(registry.get("encryption")):
            if not os.path.isfile(target):
                raise HTTPException(status_code=404, detail={"error": True, "message": "File not found"})
            try:
                with open(target, "rb") as handle:
                    blob = decrypt_bytes(handle.read())
            except Exception:  # noqa: BLE001 — wrong key / corrupt blob
                raise HTTPException(
                    status_code=503,
                    detail={"error": True, "message": "This document could not be decrypted. Check the storage encryption key."},
                )
            return Response(
                content=blob,
                media_type=media_type,
                headers={"Cache-Control": "private, no-store"},
            )

    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail={"error": True, "message": "File not found"})
    return FileResponse(target, media_type=None, headers={"Cache-Control": "private, no-store"})


@app.get("/")
async def root():
    return {"service": "Kulima FLEX API", "version": "2.0.0", "status": "ok", "docs": "/docs"}


@app.get("/health")
@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


# Structured error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # FastAPI may carry the diagnostic payload as a dict (auth/rbac/billing
    # paths) or a plain string. Flatten dicts so `code`/`required`/`role`
    # surface at the TOP level — a nested "message": {...} hides the code
    # from the browser and turns every 401 into an undiagnosable blob.
    detail = exc.detail
    if isinstance(detail, dict):
        content = {"error": True, **detail}
        if "message" not in content:
            content["message"] = "Request failed"
    else:
        content = {"error": True, "message": detail}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": True, "message": "Validation error", "details": exc.errors()})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": True, "message": str(exc)})
