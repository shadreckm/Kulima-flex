"""Internal platform operations console (Admin Console V1).

NOT a customer feature. Every endpoint below reads *across* workspaces, so the
whole router sits behind ``require_platform_admin`` — an explicit operator
allow-list, not an organization role. ``/session`` is the only route that any
signed-in user may call: it tells the frontend whether to show the console at
all, and it returns nothing but the caller's own identity plus a yes/no.

The console is read-only. No endpoint creates, mutates or deletes platform
data; the single write it performs is the audit entry recording that an
operator opened a section.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from kulima.core.audit.repository import record_event

from ..core.admin_access import decision_for, require_platform_admin
from ..core.auth import OrgContext, get_current_org
from ..services import admin_ops

router = APIRouter()
_log = logging.getLogger(__name__)


def _note(section: str, current: OrgContext, params: dict | None = None) -> None:
    """Audit the operator's access. Never fails the request it is annotating."""
    try:
        record_event(
            "admin.console_viewed",
            org_id=current.org_id,
            user_id=current.user_id,
            metadata={"section": section, **(params or {})},
        )
    except Exception as exc:  # noqa: BLE001 — auditing must not break the console
        _log.warning("admin console audit note failed: %s", exc)


@router.get("/session")
async def admin_session(current: OrgContext = Depends(get_current_org)):
    """Am I a platform operator? Identity data is the caller's own, so this
    stays open to any authenticated user — the allow-list itself is never
    returned."""
    decision = decision_for(current)
    return {
        **decision.to_payload(),
        "identity": current.to_payload(),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/overview")
async def admin_overview(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_admin),
):
    """Phase 1 — organizations, users, active users, assessments, reports,
    conversations and outcome follow-ups in one platform-wide snapshot."""
    _note("overview", current, {"windowDays": window_days})
    return admin_ops.overview(window_days=window_days)


@router.get("/users")
async def admin_users(
    search: str | None = Query(None, max_length=120),
    limit: int = Query(100, ge=1, le=500),
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_admin),
):
    """Phase 2 — users, organizations, plans, roles and recent activity."""
    _note("users", current, {"search": search, "limit": limit})
    return admin_ops.user_management(search=search or "", limit=limit, window_days=window_days)


@router.get("/billing")
async def admin_billing(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_admin),
):
    """Phase 3 — PayChangu configuration, plan status, upgrade history and
    failed payments."""
    _note("billing", current, {"windowDays": window_days})
    return admin_ops.billing_health(window_days=window_days)


@router.get("/ai-health")
async def admin_ai_health(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_admin),
):
    """Phase 4 — provider chain health: usage, latency, failures, fallbacks
    and Document Intelligence Mode activations."""
    _note("ai-health", current, {"windowDays": window_days})
    return admin_ops.ai_health(window_days=window_days)


@router.get("/outcomes")
async def admin_outcomes(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_admin),
):
    """Phase 5 — follow-up completion, pending outcomes and decision learning."""
    _note("outcomes", current, {"windowDays": window_days})
    return admin_ops.outcome_intelligence(window_days=window_days)


@router.get("/audit")
async def admin_audit(
    event_types: str | None = Query(None, max_length=400),
    org_id: str | None = Query(None, max_length=120),
    user_id: str | None = Query(None, max_length=120),
    window_days: int | None = Query(None, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
    bucket: str | None = Query(None, max_length=40),
    current: OrgContext = Depends(require_platform_admin),
):
    """Phase 6 — the platform-wide audit log with creation / deletion /
    role-change / billing buckets."""
    types = [t.strip() for t in (event_types or "").split(",") if t.strip()] or None
    _note("audit", current, {"eventTypes": types, "orgId": org_id, "userId": user_id, "bucket": bucket})
    return admin_ops.audit_logs(
        event_types=types,
        org_id=org_id,
        user_id=user_id,
        window_days=window_days,
        limit=limit,
        bucket=bucket,
    )
