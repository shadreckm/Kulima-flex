import os
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi import HTTPException

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
)

app = FastAPI(title="Kulima FLEX API", version="2.0.0")

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
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(governance.router, prefix="/api/v1/governance", tags=["governance"])

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
    return JSONResponse(status_code=exc.status_code, content={"error": True, "message": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": True, "message": "Validation error", "details": exc.errors()})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": True, "message": str(exc)})
