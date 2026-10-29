"""Collection Sources API — Google Forms / Sheets into the existing pipeline.

Forms Integration V1, Phase 2 (user journey) and Phase 8 (outcome surveys).
The router is intentionally thin: ownership checks, rate limiting and error
mapping here; every decision lives in ``forms_adapter``.

Auth contract, identical to the rest of the API: workspace-scoped through
``OrgContext`` and ``require_permission``. The one exception is the browser
redirect target of the OAuth consent flow (``GET /oauth/callback``): a top-level
redirect from Google cannot carry an Authorization header, so that route is
bound to an HMAC-signed ``state`` that carries the connection and workspace, and
it can therefore never write to a connection it did not issue.
"""

from __future__ import annotations

import logging
from typing import Any, NoReturn, Optional
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from kulima.core.forms.client import FormsIntegrationError
from kulima.core.orgs.models import Permission

from ..core.auth import OrgContext, require_permission
from ..core.rate_limit import check_rate_limit
from ..services import forms_adapter

router = APIRouter()
_log = logging.getLogger(__name__)


class ConnectionCreateRequest(BaseModel):
    assessmentId: str
    formUrl: str = ""
    sheetUrl: str = ""
    sheetRange: str = ""
    purpose: str = "evidence"
    note: str = Field(default="", max_length=400)


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str
    redirectUri: str = ""


class SyncRequest(BaseModel):
    assessmentId: str = ""
    scheduleMinutes: int = Field(default=0, ge=0, le=10080)


def _fail(exc: FormsIntegrationError) -> NoReturn:
    """Domain errors surface with their stable code and an honest message."""
    raise HTTPException(
        status_code=exc.status,
        detail={"error": True, "code": exc.code, "message": exc.message},
    )


def _request_origin(request: Request) -> str:
    """Best-effort backend origin for the OAuth redirect URI."""
    for header in ("origin", "referer"):
        value = request.headers.get(header) or ""
        if value:
            parts = urlsplit(value)
            if parts.scheme and parts.netloc:
                return f"{parts.scheme}://{parts.netloc}"
    base = str(request.base_url or "")
    return base.rstrip("/")


def _frontend_origin(request: Request) -> str:
    """Where to land the browser after the consent redirect.

    The backend and frontend are separate origins in development and on
    Render/Vercel, so an explicit ``KULIMA_FORMS_RETURN_URL`` is the reliable
    answer; the request's own origin is the fallback.
    """
    import os

    configured = os.getenv("KULIMA_FORMS_RETURN_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return _request_origin(request) or "http://localhost:3000"


def _evidence_redirect(request: Request, params: dict[str, str]) -> RedirectResponse:
    query = urlencode(params)
    return RedirectResponse(url=f"{_frontend_origin(request)}/evidence?{query}", status_code=302)


# ── Channel availability ─────────────────────────────────────────────────────


@router.get("/status")
def channel_status(current: OrgContext = Depends(require_permission(Permission.VIEW))) -> dict[str, Any]:
    """Is this channel live on this deployment? Never a simulated green light."""
    return forms_adapter.status_payload()


@router.get("/guidance")
def entity_guidance(
    assessmentId: str = Query(..., min_length=1),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict[str, Any]:
    """Phase 6: how this entity type should use a collection channel."""
    try:
        return forms_adapter.guidance_for(
            org_id=current.org_id, assessment_id=assessmentId, user_id=current.user_id
        )
    except FormsIntegrationError as exc:
        _fail(exc)


# ── Connections ──────────────────────────────────────────────────────────────


@router.get("/connections")
def list_connections(
    assessmentId: Optional[str] = Query(default=None),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict[str, Any]:
    try:
        return forms_adapter.list_connections(
            org_id=current.org_id, assessment_id=assessmentId, user_id=current.user_id
        )
    except FormsIntegrationError as exc:
        _fail(exc)


@router.post("/connections")
def create_connection(
    payload: ConnectionCreateRequest,
    request: Request,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_DOCUMENTS)),
) -> dict[str, Any]:
    """Register a form/sheet link and return the consent URL for the owner."""
    check_rate_limit(current.user_id, "forms:connect")
    try:
        return forms_adapter.create_connection(
            org_id=current.org_id,
            user_id=current.user_id,
            assessment_id=payload.assessmentId,
            form_url=payload.formUrl,
            sheet_url=payload.sheetUrl,
            sheet_range=payload.sheetRange,
            purpose=payload.purpose,
            note=payload.note,
            request_origin=_request_origin(request),
        )
    except FormsIntegrationError as exc:
        _fail(exc)


@router.delete("/connections/{connection_id}")
def disconnect(
    connection_id: str,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_DOCUMENTS)),
) -> dict[str, Any]:
    """Revoke the external read grant. Attached evidence batches remain."""
    try:
        return forms_adapter.disconnect(connection_id=connection_id, org_id=current.org_id, user_id=current.user_id)
    except FormsIntegrationError as exc:
        _fail(exc)


# ── OAuth callback ───────────────────────────────────────────────────────────


@router.post("/oauth/callback")
def complete_authorization(
    payload: OAuthCallbackRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_DOCUMENTS)),
) -> dict[str, Any]:
    """Frontend-mediated callback: the UI posts the code with its session."""
    try:
        return forms_adapter.complete_authorization(
            code=payload.code, state=payload.state, redirect_uri=payload.redirectUri
        )
    except FormsIntegrationError as exc:
        _fail(exc)


@router.get("/oauth/callback")
def browser_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
) -> RedirectResponse:
    """Google's redirect target. Bound to the signed state, then redirects."""
    params: dict[str, str] = {"collection": "failed"}
    if error:
        params["code"] = (error or "google_denied")[:48]
        params["message"] = (error_description or "Google returned an authorisation error.")[:280]
        _log.info("Google OAuth callback refused: %s", error)
        return _evidence_redirect(request, params)
    try:
        result = forms_adapter.complete_authorization(code=code, state=state)
        conn = result.get("connection") or {}
        params = {
            "collection": "connected",
            "connection": str(conn.get("id") or ""),
            "questions": str(int(conn.get("questionCount") or 0)),
        }
        return _evidence_redirect(request, params)
    except FormsIntegrationError as exc:
        return _evidence_redirect(
            request, {"collection": "failed", "code": exc.code[:48], "message": exc.message[:280]}
        )


# ── Sync + batches ───────────────────────────────────────────────────────────


@router.post("/connections/{connection_id}/sync")
def sync_connection(
    connection_id: str,
    payload: Optional[SyncRequest] = None,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_DOCUMENTS)),
) -> dict[str, Any]:
    """Pull new responses and, when a batch is ripe, attach it as evidence."""
    check_rate_limit(current.user_id, "forms:sync")
    body = payload or SyncRequest()
    try:
        result = forms_adapter.sync_connection(
            connection_id,
            org_id=current.org_id,
            user_id=current.user_id,
            assessment_id=body.assessmentId or None,
            reason="manual",
        )
    except FormsIntegrationError as exc:
        _fail(exc)

    if body.scheduleMinutes > 0:
        try:
            result["schedule"] = forms_adapter.enqueue_sync(
                connection_id, org_id=current.org_id, user_id=current.user_id, delay_minutes=body.scheduleMinutes
            )
        except FormsIntegrationError as exc:
            result["schedule"] = {"queued": False, "message": exc.message}
    return result


@router.post("/connections/{connection_id}/schedule")
def schedule_sync(
    connection_id: str,
    minutes: int = Query(default=60, ge=1, le=10080),
    current: OrgContext = Depends(require_permission(Permission.MANAGE_DOCUMENTS)),
) -> dict[str, Any]:
    """Queue one sync on the durable job runner (opt-in scheduling)."""
    check_rate_limit(current.user_id, "forms:schedule")
    try:
        return forms_adapter.enqueue_sync(
            connection_id, org_id=current.org_id, user_id=current.user_id, delay_minutes=minutes
        )
    except FormsIntegrationError as exc:
        _fail(exc)


@router.get("/batches")
def list_batches(
    assessmentId: Optional[str] = Query(default=None),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict[str, Any]:
    """Materialised batches: one row per attached response window."""
    return forms_adapter.batches_for(org_id=current.org_id, assessment_id=assessmentId)
