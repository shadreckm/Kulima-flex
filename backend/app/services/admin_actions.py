"""Platform mutations for the Admin Console: subscriptions, enterprise
accounts and the PLATFORM_ADMIN roster.

``admin_ops`` answers "what is happening on the platform" and stays read-only.
Everything that *changes* platform state lives here, for one reason: a write
that crosses workspaces has to be auditable on its own terms, and an operator
looking at a number should be able to tell whether the number they are reading
was produced by a query or by a decision someone made.

Three rules every function here obeys:

1. **Reuse the customer-visible engine.** A plan change goes through
   ``kulima.core.billing.service``, not a bespoke UPDATE, so the upgrade is
   immediate, the downgrade schedules at period end, ``organizations.plan``
   mirrors, and the payment event lands in the same history the customer sees.
   One definition of "change plan", two audiences.
2. **Never skip a gate the customer cannot skip.** Enterprise still needs an
   approved agreement before it can be applied, even when an operator clicks the
   button — the operator approves the agreement explicitly, which is itself
   audited.
3. **Record before and after, and how the actor got in.** A mutation performed
   through break-glass env access is labelled as such in the audit trail.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from kulima.core.audit.repository import record_event
from kulima.core.billing import service as billing
from kulima.core.billing.plans import get_plan
from kulima.core.billing.repository import (
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_GRACE,
    STATUS_PAST_DUE,
    STATUS_SUSPENDED,
    BillingRepository,
)
from kulima.core.orgs.platform_admins import PlatformAdminRepository, get_repo
from kulima.core.orgs.repository import OrgRepository

_log = logging.getLogger(__name__)

VALID_STATUSES = (STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_GRACE, STATUS_SUSPENDED, STATUS_CANCELED)
#: Fields an operator may set directly. ``plan`` is handled through the service
#: so plan semantics are never bypassed, and identity/period columns that belong
#: to the payment flow (``paychangu_ref``, ``tx`` data) are not patchable here.
PATCHABLE_FIELDS = (
    "status",
    "currency",
    "amount",
    "billing_cycle",
    "grace_until",
    "cancel_at_period_end",
    "current_period_end",
    "last_error",
)
ACTIVATION_ACTIONS = ("request", "approve", "reset")


class AdminActionError(Exception):
    """Domain failure for a platform mutation, mapped to HTTP by the router."""

    def __init__(self, code: str, message: str, *, status_code: int = 422):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message or code)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _billing_repo() -> BillingRepository:
    """The billing engine's own repository, never a second instance.

    A platform mutation reads the subscription, hands the change to
    ``kulima.core.billing.service``, then reads it back to record before/after.
    If those reads used a repository built from the current configuration while
    the engine used its import-time singleton, the two could sit on different
    files and a successful change would be reported as "nothing changed".
    """
    return billing.get_repository()


def _orgs() -> OrgRepository:
    return OrgRepository()


def _subscription_snapshot(org_id: str) -> dict[str, Any]:
    sub = _billing_repo().get_subscription(org_id) or _billing_repo().ensure_subscription(org_id)
    return {
        "orgId": org_id,
        "plan": sub.get("plan"),
        "status": sub.get("status"),
        "currency": sub.get("currency"),
        "amount": sub.get("amount"),
        "billingCycle": sub.get("billing_cycle"),
        "currentPeriodEnd": sub.get("current_period_end"),
        "graceUntil": sub.get("grace_until"),
        "cancelAtPeriodEnd": bool(sub.get("cancel_at_period_end")),
        "pendingPlan": sub.get("pending_plan"),
        "activationState": sub.get("activation_state"),
        "updatedAt": sub.get("updated_at"),
    }


def _audit(event_type: str, *, operator: Any, org_id: str | None, metadata: dict) -> None:
    """Audit the mutation. Never fails the operation it is describing."""
    try:
        decision = getattr(operator, "admin_decision", None)
        via = getattr(decision, "granted_by", None) or "unknown"
        record_event(
            event_type,
            org_id=org_id,
            user_id=getattr(operator, "user_id", None),
            metadata={"actorOrgId": getattr(operator, "org_id", None), "via": via, **metadata},
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("platform mutation audit failed (%s): %s", event_type, exc)


# ── Subscriptions ────────────────────────────────────────────────────────────

def update_subscription(
    *,
    operator: Any,
    org_id: str,
    plan: str | None = None,
    fields: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict:
    """Change one workspace's plan and/or subscription fields.

    ``plan`` goes through the billing service (upgrade now, downgrade at period
    end, plan mirrored onto the organization, payment event recorded). Field
    patches are limited to ``PATCHABLE_FIELDS`` so an operator cannot rewrite
    payment provenance through this door.
    """
    repo = _billing_repo()
    existing = repo.get_subscription(org_id) or repo.ensure_subscription(org_id)
    before = _subscription_snapshot(org_id)
    if not _orgs().get_org(org_id):
        raise AdminActionError("ORG_NOT_FOUND", f"No organization '{org_id}'.", status_code=404)

    patch = {k: v for k, v in (fields or {}).items() if v is not None}
    illegal = sorted(set(fields or {}) - set(PATCHABLE_FIELDS))
    if illegal:
        raise AdminActionError(
            "FIELD_NOT_PATCHABLE",
            f"These subscription fields cannot be set from the console: {', '.join(illegal)}.",
        )
    if "status" in patch and str(patch["status"]) not in VALID_STATUSES:
        raise AdminActionError(
            "INVALID_STATUS",
            f"Status must be one of: {', '.join(VALID_STATUSES)}.",
        )

    plan_result: dict[str, Any] | None = None
    target = str(plan or "").strip().lower()
    if target:
        if target not in {"free", "pro", "enterprise"}:
            raise AdminActionError("UNKNOWN_PLAN", f"Unknown plan '{target}'.")
        spec = get_plan(target)
        if spec.requires_approval and not billing.enterprise_checkout_allowed(org_id):
            raise AdminActionError(
                "ENTERPRISE_ACTIVATION_REQUIRED",
                (
                    "Enterprise cannot be applied until the custom agreement is "
                    "approved for this organization. Approve the activation first."
                ),
            )
        try:
            plan_result = billing.change_plan(org_id, target)
        except ValueError as exc:
            raise AdminActionError("PLAN_CHANGE_FAILED", str(exc)) from exc

    if patch:
        normalized = dict(patch)
        if "cancel_at_period_end" in normalized:
            normalized["cancel_at_period_end"] = 1 if normalized["cancel_at_period_end"] in (True, 1, "true", "1", "yes") else 0
        repo.update_subscription(org_id, **normalized)

    after = _subscription_snapshot(org_id)
    changed = after != before
    _audit(
        "admin.subscription_updated",
        operator=operator,
        org_id=org_id,
        metadata={
            "before": before,
            "after": after,
            "plan": target or None,
            "fields": sorted(patch) if patch else [],
            "planChanged": bool(plan_result and plan_result.get("changed")),
            "pendingPlan": after.get("pendingPlan"),
            "reason": reason or None,
        },
    )
    return {"changed": changed, "before": before, "after": after, "planResult": plan_result, "auditedAt": _now()}


def set_account_status(*, operator: Any, org_id: str, status: str, reason: str | None = None) -> dict:
    """Suspend or reactivate a workspace using the service's own transitions."""
    target = str(status or "").strip().lower()
    before = _subscription_snapshot(org_id)
    if target == STATUS_SUSPENDED:
        _billing_repo().get_subscription(org_id) or _billing_repo().ensure_subscription(org_id)
        billing.suspend(org_id, reason=reason or "platform_admin")
        event = "admin.account_suspended"
    elif target == STATUS_ACTIVE:
        _billing_repo().get_subscription(org_id) or _billing_repo().ensure_subscription(org_id)
        billing.reactivate(org_id)
        event = "admin.account_reactivated"
    else:
        return update_subscription(operator=operator, org_id=org_id, fields={"status": target}, reason=reason)
    after = _subscription_snapshot(org_id)
    _audit(event, operator=operator, org_id=org_id,
           metadata={"before": before, "after": after, "reason": reason or None})
    return {"changed": after != before, "before": before, "after": after, "auditedAt": _now()}


# ── Enterprise accounts ──────────────────────────────────────────────────────

def provision_organization(
    *,
    operator: Any,
    name: str,
    plan: str = "free",
    owner_user_id: str | None = None,
    intended_owner_email: str | None = None,
) -> dict:
    """Create a team workspace on behalf of a customer.

    The new organization is never left unowned: the acting operator holds Owner
    until a real principal is attached. An email the operator *typed* is not a
    principal — memberships are only created for user ids that already exist in
    ``organization_members`` (i.e. someone who has signed in), so a typo can't
    strand an account against an identity nobody controls.
    """
    cleaned = str(name or "").strip()
    if not cleaned:
        raise AdminActionError("NAME_REQUIRED", "An organization needs a name.")
    target = str(plan or "free").strip().lower()
    if target not in {"free", "pro", "enterprise"}:
        raise AdminActionError("UNKNOWN_PLAN", f"Unknown plan '{target}'.")

    orgs = _orgs()
    if owner_user_id and owner_user_id not in orgs.distinct_user_ids():
        raise AdminActionError(
            "OWNER_NOT_SIGNED_IN",
            "That user id has never signed in, so it cannot be attached. Create the "
            "workspace now and add the owner from the Users panel once they sign in.",
        )
    org = orgs.create_org(cleaned, created_by=owner_user_id or operator.user_id, personal=False, plan=target)
    orgs.add_member(org.id, owner_user_id or operator.user_id, "owner")
    _billing_repo().ensure_subscription(org.id, plan=target)
    if target == "enterprise":
        billing.request_enterprise_activation(org.id, org_name=cleaned, contact=intended_owner_email)

    snapshot = _subscription_snapshot(org.id)
    _audit(
        "admin.org_created",
        operator=operator,
        org_id=org.id,
        metadata={
            "name": org.name,
            "plan": target,
            "ownerUserId": owner_user_id or operator.user_id,
            "ownerIsOperator": owner_user_id is None,
            "intendedOwnerEmail": intended_owner_email or None,
            "activationState": snapshot.get("activationState"),
        },
    )
    return {
        "organization": {"orgId": org.id, "name": org.name, "slug": org.slug, "plan": org.plan,
                         "personal": org.personal, "createdAt": org.created_at},
        "subscription": snapshot,
        "ownerUserId": owner_user_id or operator.user_id,
        "pendingOwnerEmail": intended_owner_email or None,
        "auditedAt": _now(),
    }


def update_organization(*, operator: Any, org_id: str, name: str | None = None,
                        reason: str | None = None) -> dict:
    """Rename a workspace (slug is regenerated by the repository)."""
    orgs = _orgs()
    org = orgs.get_org(org_id)
    if org is None:
        raise AdminActionError("ORG_NOT_FOUND", f"No organization '{org_id}'.", status_code=404)
    cleaned = str(name or "").strip()
    if not cleaned:
        raise AdminActionError("NAME_REQUIRED", "An organization needs a name.")
    orgs.rename_org(org_id, cleaned)
    updated = orgs.get_org(org_id)
    _audit("admin.org_updated", operator=operator, org_id=org_id,
           metadata={"before": {"name": org.name, "slug": org.slug},
                     "after": {"name": updated.name if updated else cleaned,
                               "slug": updated.slug if updated else None},
                     "reason": reason or None})
    return {"orgId": org_id, "name": updated.name if updated else cleaned,
            "slug": updated.slug if updated else None, "auditedAt": _now()}


def set_enterprise_activation(*, operator: Any, org_id: str, action: str,
                              agreement_accepted: bool = False,
                              contact: str | None = None) -> dict:
    """Drive the Enterprise activation sequence from the platform side.

    ``approve`` requires an explicit agreement acceptance. If the customer never
    requested activation, the operator's own request is recorded first — the
    sequence stays two steps, both of them attributed.
    """
    repo = _billing_repo()
    repo.get_subscription(org_id) or repo.ensure_subscription(org_id)
    verb = str(action or "").strip().lower()
    if verb not in ACTIVATION_ACTIONS:
        raise AdminActionError("UNKNOWN_ACTION", f"Activation action must be one of: {', '.join(ACTIVATION_ACTIONS)}.")
    before = billing.enterprise_activation_status(org_id)

    if verb == "request":
        org = _orgs().get_org(org_id)
        billing.request_enterprise_activation(org_id, org_name=org.name if org else None, contact=contact)
    elif verb == "approve":
        if not agreement_accepted:
            raise AdminActionError(
                "AGREEMENT_REQUIRED",
                "The custom Enterprise agreement must be explicitly accepted before approval.",
            )
        if before is None:
            billing.request_enterprise_activation(org_id, contact=contact)
        try:
            billing.approve_enterprise_activation(org_id, agreement_accepted=True)
        except ValueError as exc:
            raise AdminActionError("ACTIVATION_FAILED", str(exc)) from exc
    else:
        repo.update_subscription(org_id, activation_state=None)

    after = billing.enterprise_activation_status(org_id)
    _audit("admin.enterprise_activation_changed", operator=operator, org_id=org_id,
           metadata={"action": verb, "before": before, "after": after,
                     "agreementAccepted": bool(agreement_accepted), "contact": contact})
    return {"orgId": org_id, "before": before, "after": after,
            "checkoutAllowed": billing.enterprise_checkout_allowed(org_id), "auditedAt": _now()}


# ── The PLATFORM_ADMIN roster ────────────────────────────────────────────────
#
# The roster *read* lives in ``admin_ops.platform_access`` — this module only
# changes who is on it, so a grant and a revocation are the only writes here.

def grant_platform_admin(*, operator: Any, email: str | None = None, user_id: str | None = None,
                        display_name: str | None = None) -> dict:
    repo: PlatformAdminRepository = get_repo()
    admin, outcome = repo.grant(email=email, user_id=user_id, display_name=display_name,
                               granted_by=operator.user_id)
    if outcome == "invalid_identity":
        raise AdminActionError(
            "IDENTITY_REQUIRED",
            "Granting PLATFORM_ADMIN needs a user id or an email — an address the "
            "person can actually sign in with, not a name.",
        )
    if outcome == "invalid_email":
        raise AdminActionError("INVALID_EMAIL", "That does not look like an email address.")
    if outcome == "conflict":
        raise AdminActionError("CONFLICT", "That identity is already recorded for another principal.",
                               status_code=409)
    assert admin is not None
    _audit("admin.platform_admin_granted", operator=operator, org_id=operator.org_id,
           metadata={"outcome": outcome, "principal": admin.principal, "email": admin.email,
                     "userId": admin.user_id, "activeCount": repo.count_active()})
    return {"admin": admin.to_payload(), "outcome": outcome,
            "activeCount": repo.count_active(), "auditedAt": _now()}


def revoke_platform_admin(*, operator: Any, email: str | None = None, user_id: str | None = None,
                          reason: str | None = None) -> dict:
    repo: PlatformAdminRepository = get_repo()
    ok, outcome = repo.revoke(email=email, user_id=user_id, revoked_by=operator.user_id)
    if not ok:
        if outcome == "not_found":
            raise AdminActionError("NOT_FOUND", "No platform administrator row matches that identity.",
                                   status_code=404)
        if outcome == "already_revoked":
            raise AdminActionError("ALREADY_REVOKED", "That principal's access is already revoked.",
                                   status_code=409)
        if outcome == "last_admin":
            raise AdminActionError(
                "LAST_ADMIN",
                "This is the only active platform administrator. Revoking it would lock "
                "everyone out of the console permanently — remove another admin first, or "
                "change KULIMA_PLATFORM_ADMIN_EMAILS on the deployment.",
            )
        if outcome == "primary_admin":
            raise AdminActionError(
                "PRIMARY_ADMIN",
                "The primary platform administrator cannot be revoked from the console. "
                "Change KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL / KULIMA_PLATFORM_ADMIN_EMAILS "
                "on the deployment to move the root account.",
            )
        raise AdminActionError("REVOKE_FAILED", outcome, status_code=500)
    _audit("admin.platform_admin_revoked", operator=operator, org_id=operator.org_id,
           metadata={"email": email, "userId": user_id, "reason": reason or None,
                     "activeCount": repo.count_active()})
    return {"revoked": True, "identity": {"email": email, "userId": user_id},
            "activeCount": repo.count_active(), "auditedAt": _now()}
