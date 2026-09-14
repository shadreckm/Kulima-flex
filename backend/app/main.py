from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import HTTPException
import os

from .core.rate_limit import RateLimitMiddleware
from .routers import intelligence, ask_ic, ask_signals, documents, outcomes

app = FastAPI(title="Kulima OS API", version="0.1.0")

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
app.include_router(intelligence.router, prefix="/api/v1/intelligence", tags=["intelligence"])
app.include_router(ask_ic.router, prefix="/api/v1/ask", tags=["ask_ic"])
app.include_router(ask_signals.router, prefix="/api/v1/ask", tags=["ask_signals"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(outcomes.router, prefix="/api/v1/outcomes", tags=["outcomes"])

# Serve uploaded files from backend/uploads via /uploads.
# Must match document_adapter.UPLOAD_DIR (backend/uploads), not repo-root uploads/.
uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
uploads_dir = os.path.abspath(uploads_dir)
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


@app.get("/")
async def root():
    return {"service": "Kulima OS API", "version": "0.1.0", "status": "ok", "docs": "/docs"}


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
