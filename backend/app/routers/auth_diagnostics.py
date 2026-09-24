"""Auth chain diagnostic endpoint (release engineering).

GET /api/v1/auth/diagnostic exercises the EXACT same dependency chain as the
protected endpoints (get_current_user → get_current_org) and returns either:

    {"ok": true,  "auth": ..., "org": {...}}          — full chain works
    {"ok": false, "code": "SESSION_MISSING"|"SESSION_INVALID"|"SESSION_EXPIRED"|"BACKEND_AUTH_FAILED"|"ORG_CONTEXT_MISSING", ...}

because FastAPI exception handlers (see main.http_exception_handler) now
surface the top-level `code`, the response tells the release engineer exactly
where the chain broke:
  - SESSION_MISSING          → proxy did not forward an Authorization header
                               (Vercel NEXTAUTH_SECRET missing / no session cookie)
  - SESSION_INVALID          → backend rejected the minted token →
                               **NEXTAUTH_SECRET mismatch between Vercel and Render**
  - ORG_CONTEXT_MISSING      → token valid but workspace provisioning failed
"""
from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, Depends

from ..core.auth import OrgContext, get_current_org

router = APIRouter()


@router.get("/diagnostic")
async def auth_diagnostic(current: OrgContext = Depends(get_current_org)):
    """Full-chain probe. Reaching this handler means every stage passed."""
    secret = os.environ.get("NEXTAUTH_SECRET", "")
    return {
        "ok": True,
        "auth": "bearer-jwt",
        "org": current.to_payload(),
        "secretFingerprint": hashlib.sha256(secret.encode()).hexdigest()[:16],
        "stage": "complete",
    }
