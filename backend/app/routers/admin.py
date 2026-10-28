"""The platform administration console (PLATFORM_ADMIN only).

NOT a customer feature. Every endpoint below reads *across* every workspace, so
the whole router sits behind the ``PLATFORM_ADMIN`` role
(``backend.app.core.admin_access``) — a stored platform principal that is
structurally separate from the organization roles. An Org Owner gets 403 here,
and so does everyone else. ``/session`` is the only route any signed-in user may
call: it returns the caller's own identity plus a yes/no, never the roster.

Read sections come from ``admin_ops`` and change nothing. The mutations here are
the console's *management* surface — subscriptions, enterprise accounts, the
administrator roster — each one gated on a declared platform capability and each
one recorded in the audit trail with its before/after state and how the actor
obtained access (stored role or break-glass environment).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from kulima.core.audit.repository import record_event
from kulima.core.orgs.platform_admins import PlatformCapability

from ..core.admin_access import decision_of, decision_for, require_platform_admin, require_platform_capability
from ..core.auth import OrgContext, get_current_org
from ..services import admin_actions, admin_ops
from ..services.admin_actions import AdminActionError

router = APIRouter()
_log = logging.getLogger(__name__)


class _Strict(BaseModel):
    """A platform mutation body accepts exactly the fields it declares.

    Silently ignoring an unexpected key is the wrong behaviour for a write that
    crosses workspaces: an operator who sends ``paychanguRef`` expecting to set
    payment provenance must be told that field is not settable here, not have it
    dropped on the floor and see a green "updated" toast.
    """

    model_config = ConfigDict(extra="forbid")


class SubscriptionUpdateRequest(_Strict):
    """Plan and subscription fields an operator may set for one workspace."""

    plan: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, max_length=8)
    amount: float | None = Field(default=None, ge=0, le=10_000_000)
    billingCycle: str | None = Field(default=None, max_length=32)
    graceUntil: str | None = Field(default=None, max_length=40)
    currentPeriodEnd: str | None = Field(default=None, max_length=40)
    cancelAtPeriodEnd: bool | None = None
    reason: str | None = Field(default=None, max_length=300)


class AccountStatusRequest(_Strict):
    status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=300)


class OrganizationCreateRequest(_Strict):
    name: str = Field(min_length=1, max_length=120)
    plan: str = Field(default="free", max_length=32)
    ownerUserId: str | None = Field(default=None, max_length=200)
    intendedOwnerEmail: str | None = Field(default=None, max_length=200)


class OrganizationUpdateRequest(_Strict):
    name: str = Field(min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=300)


class EnterpriseActivationRequest(_Strict):
    action: str = Field(min_length=1, max_length=20)
    agreementAccepted: bool = False
    contact: str | None = Field(default=None, max_length=200)


class PlatformAdminGrantRequest(_Strict):
    email: str | None = Field(default=None, max_length=200)
    userId: str | None = Field(default=None, max_length=200)
    displayName: str | None = Field(default=None, max_length=200)


def _note(section: str, current: OrgContext, params: dict | None = None) -> None:
    """Audit the operator's access. Never fails the request it is annotating."""
    try:
        decision = decision_of(current)
        record_event(
            "admin.console_viewed",
            org_id=current.org_id,
            user_id=current.user_id,
            metadata={
                "section": section,
                "via": decision.granted_by,
                "capabilities": len(decision.capabilities),
                **(params or {}),
            },
        )
    except Exception as exc:  # noqa: BLE001 — auditing must not break the console
        _log.warning("admin console audit note failed: %s", exc)


def _act(func, /, *, capability: PlatformCapability, current: OrgContext, **kwargs):
    """Run a platform mutation: capability already enforced by the dependency.

    ``AdminActionError`` becomes the HTTP response; anything unexpected is
    reported as a platform failure rather than leaking a stack trace to an
    operator's screen — and is still audited, because a mutation that failed
    halfway is exactly the thing an operator needs to see.
    """
    try:
        return func(operator=current, **kwargs)
    except AdminActionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": True, "code": exc.code, "message": exc.message,
                    "capability": capability.value},
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _log.exception("platform mutation failed: %s", exc)
        try:
            record_event(
                "admin.action_failed",
                org_id=current.org_id,
                user_id=current.user_id,
                metadata={"failed": True, "capability": capability.value,
                          "error": f"{type(exc).__name__}: {str(exc)[:200]}"},
            )
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(
            status_code=500,
            detail={"error": True, "code": "PLATFORM_ACTION_FAILED",
                    "message": "That platform action failed. Nothing was recorded as successful."},
        ) from exc


@router.get("/session")
async def admin_session(current: OrgContext = Depends(get_current_org)):
    """Am I a platform administrator? Identity data is the caller's own, so this
    stays open to any authenticated user — the roster is never returned here."""
    decision = decision_for(current)
    return {
        **decision.to_payload(),
        "identity": current.to_payload(),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/overview")
async def admin_overview(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_ANALYTICS)),
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
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_USERS)),
):
    """Phase 2 — users, organizations, plans, roles and recent activity."""
    _note("users", current, {"search": search, "limit": limit})
    return admin_ops.user_management(search=search or "", limit=limit, window_days=window_days)


@router.get("/billing")
async def admin_billing(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_BILLING)),
):
    """Phase 3 — PayChangu configuration, plan status, upgrade history and
    failed payments."""
    _note("billing", current, {"windowDays": window_days})
    return admin_ops.billing_health(window_days=window_days)


@router.get("/ai-health")
async def admin_ai_health(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_PROVIDER_HEALTH)),
):
    """Phase 4 — provider chain health: usage, latency, failures, fallbacks
    and Document Intelligence Mode activations."""
    _note("ai-health", current, {"windowDays": window_days})
    return admin_ops.ai_health(window_days=window_days)


@router.get("/outcomes")
async def admin_outcomes(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_ANALYTICS)),
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
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_AUDIT)),
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


# ── Organizations panel (read + management surface) ──────────────────────────

@router.get("/organizations")
async def admin_organizations(
    search: str | None = Query(None, max_length=120),
    plan: str | None = Query(None, max_length=32),
    status: str | None = Query(None, max_length=32),
    limit: int = Query(200, ge=1, le=500),
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_ORGANIZATIONS)),
):
    """Every workspace with the subscription state an operator manages."""
    _note("organizations", current, {"search": search, "plan": plan, "status": status})
    return admin_ops.organizations(
        search=search or "", plan=plan, status=status, limit=limit, window_days=window_days,
    )


@router.post("/organizations", status_code=201)
async def admin_create_organization(
    payload: OrganizationCreateRequest,
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_ENTERPRISE_ACCOUNTS)),
):
    """Provision a team workspace on a customer's behalf.

    The acting operator holds ownership until a real principal is attached, so a
    platform-provisioned account is never an orphan nobody can enter.
    """
    return _act(
        admin_actions.provision_organization,
        capability=PlatformCapability.MANAGE_ENTERPRISE_ACCOUNTS,
        current=current,
        name=payload.name,
        plan=payload.plan,
        owner_user_id=payload.ownerUserId,
        intended_owner_email=payload.intendedOwnerEmail,
    )


@router.patch("/organizations/{org_id}")
async def admin_update_organization(
    org_id: str,
    payload: OrganizationUpdateRequest,
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_ENTERPRISE_ACCOUNTS)),
):
    """Rename a workspace. Names are customer-facing, so the change is audited."""
    return _act(
        admin_actions.update_organization,
        capability=PlatformCapability.MANAGE_ENTERPRISE_ACCOUNTS,
        current=current,
        org_id=org_id,
        name=payload.name,
        reason=payload.reason,
    )


@router.put("/organizations/{org_id}/subscription")
async def admin_update_subscription(
    org_id: str,
    payload: SubscriptionUpdateRequest,
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_SUBSCRIPTIONS)),
):
    """Change plan and/or subscription fields for one workspace.

    Plan changes go through the same service the customer's own checkout uses,
    so an upgrade is immediate, a downgrade schedules at period end, and the
    payment history the customer sees tells the same story as the audit log.
    """
    fields = {
        "status": payload.status,
        "currency": payload.currency,
        "amount": payload.amount,
        "billing_cycle": payload.billingCycle,
        "grace_until": payload.graceUntil,
        "current_period_end": payload.currentPeriodEnd,
        "cancel_at_period_end": payload.cancelAtPeriodEnd,
    }
    return _act(
        admin_actions.update_subscription,
        capability=PlatformCapability.MANAGE_SUBSCRIPTIONS,
        current=current,
        org_id=org_id,
        plan=payload.plan,
        fields=fields,
        reason=payload.reason,
    )


@router.post("/organizations/{org_id}/account-status")
async def admin_account_status(
    org_id: str,
    payload: AccountStatusRequest,
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_SUBSCRIPTIONS)),
):
    """Suspend or reactivate a workspace using the billing engine's transitions."""
    return _act(
        admin_actions.set_account_status,
        capability=PlatformCapability.MANAGE_SUBSCRIPTIONS,
        current=current,
        org_id=org_id,
        status=payload.status,
        reason=payload.reason,
    )


@router.post("/organizations/{org_id}/enterprise-activation")
async def admin_enterprise_activation(
    org_id: str,
    payload: EnterpriseActivationRequest,
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_ENTERPRISE_ACCOUNTS)),
):
    """Request, approve or reset the Enterprise activation sequence.

    Approval still needs the agreement ticked: an operator cannot apply
    Enterprise through the back door that the customer-facing checkout guards.
    """
    return _act(
        admin_actions.set_enterprise_activation,
        capability=PlatformCapability.MANAGE_ENTERPRISE_ACCOUNTS,
        current=current,
        org_id=org_id,
        action=payload.action,
        agreement_accepted=payload.agreementAccepted,
        contact=payload.contact,
    )


# ── Content panels ───────────────────────────────────────────────────────────

@router.get("/assessments")
async def admin_assessments(
    status: str | None = Query(None, max_length=32),
    org_id: str | None = Query(None, max_length=120),
    search: str | None = Query(None, max_length=120),
    limit: int = Query(100, ge=1, le=500),
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_ANALYTICS)),
):
    """Every assessment on the platform, plus the pipeline state behind it."""
    _note("assessments", current, {"status": status, "orgId": org_id, "search": search})
    return admin_ops.assessments_panel(
        status=status, org_id=org_id, search=search or "", limit=limit, window_days=window_days,
    )


@router.get("/reports")
async def admin_reports(
    org_id: str | None = Query(None, max_length=120),
    limit: int = Query(150, ge=1, le=500),
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_ANALYTICS)),
):
    """Report exports. A report is an audit event, not a table — said plainly."""
    _note("reports", current, {"orgId": org_id})
    return admin_ops.reports_panel(org_id=org_id, limit=limit, window_days=window_days)


@router.get("/conversations")
async def admin_conversations(
    org_id: str | None = Query(None, max_length=120),
    limit: int = Query(100, ge=1, le=500),
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.VIEW_ANALYTICS)),
):
    """Analyst conversations and their message volume across every workspace."""
    _note("conversations", current, {"orgId": org_id})
    return admin_ops.conversations_panel(org_id=org_id, limit=limit, window_days=window_days)


# ── The role itself ──────────────────────────────────────────────────────────

@router.get("/access")
async def admin_access_panel(
    window_days: int = Query(30, ge=1, le=365),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_PLATFORM_ADMINS)),
):
    """The two role planes side by side, the capability matrix, and the roster."""
    _note("access", current)
    return admin_ops.platform_access(panel_window=window_days)


@router.post("/access/admins", status_code=201)
async def admin_grant(
    payload: PlatformAdminGrantRequest,
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_PLATFORM_ADMINS)),
):
    """Grant PLATFORM_ADMIN to a user id or an email address."""
    return _act(
        admin_actions.grant_platform_admin,
        capability=PlatformCapability.MANAGE_PLATFORM_ADMINS,
        current=current,
        email=payload.email,
        user_id=payload.userId,
        display_name=payload.displayName,
    )


@router.delete("/access/admins/{identity}")
async def admin_revoke(
    identity: str,
    reason: str | None = Query(None, max_length=300),
    current: OrgContext = Depends(require_platform_capability(PlatformCapability.MANAGE_PLATFORM_ADMINS)),
):
    """Revoke PLATFORM_ADMIN from a principal.

    The row is kept with status 'revoked' — history is not rewritten. The last
    remaining administrator and the configured primary cannot be revoked from
    here, because either action would leave the platform with no way back in.
    """
    value = str(identity or "").strip()
    is_email = "@" in value
    return _act(
        admin_actions.revoke_platform_admin,
        capability=PlatformCapability.MANAGE_PLATFORM_ADMINS,
        current=current,
        email=value if is_email else None,
        user_id=None if is_email else value,
        reason=reason,
    )
