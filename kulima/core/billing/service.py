"""Billing service — status, usage, quotas, feature gates, grace, suspension.

State machine (Phase 8):

    active ──payment failed──▶ past_due/grace ──grace expired──▶ suspended
       ▲                                                         │
       └──────────────── payment success / reactivate ◀──────────┘

Enforcement policy (pilot-safe):

- Suspension always blocks NEW assessments (read-only workspace: owners can
  still view and export their data — we never hold customer data hostage).
- Monthly quota and plan feature gates are enforced only when
  ``KULIMA_BILLING_ENFORCEMENT`` is enabled, so the pilot experience is
  unchanged until the commercial layer is switched on.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from kulima.config import get_settings
from kulima.core.audit import record_event

from .plans import get_plan, is_downgrade, is_upgrade, plan_includes_feature
from .repository import (
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_GRACE,
    STATUS_PAST_DUE,
    STATUS_SUSPENDED,
    BillingRepository,
)

_log = logging.getLogger(__name__)

DEFAULT_GRACE_DAYS = 7
PERIOD_DAYS = 30


class BillingBlocked(Exception):
    """Raised when the commercial layer must refuse an action."""

    def __init__(self, code: str, message: str, *, status_code: int = 403, feature: str | None = None):
        self.code = code
        self.status_code = status_code
        self.feature = feature
        super().__init__(message or code)

    def to_detail(self) -> dict:
        detail = {"error": True, "code": self.code, "message": str(self)}
        if self.feature:
            detail["feature"] = self.feature
        return detail


_repo = BillingRepository()


# ── Configuration ────────────────────────────────────────────────────────────

def enforcement_enabled() -> bool:
    return os.getenv("KULIMA_BILLING_ENFORCEMENT", "false").strip().lower() in {"1", "true", "yes", "on"}


def grace_period_days() -> int:
    try:
        return max(1, int(os.getenv("KULIMA_GRACE_PERIOD_DAYS", str(DEFAULT_GRACE_DAYS))))
    except ValueError:
        return DEFAULT_GRACE_DAYS


def demo_mode_enabled() -> bool:
    """When enabled, checkout can be confirmed locally (demos & tests only)."""
    return os.getenv("KULIMA_BILLING_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def _sync_org_plan(org_id: str, plan_id: str) -> None:
    """Mirror the subscription plan onto organizations.plan (OrgContext source)."""
    try:
        from kulima.core.orgs.repository import OrgRepository  # noqa: PLC0415

        OrgRepository().set_plan(org_id, plan_id)
    except Exception:  # noqa: BLE001 — org table must never break billing
        pass


# ── Usage & quotas ───────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_start() -> str:
    now = _now()
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()


def count_assessments_this_month(org_id: str) -> int:
    """Assessments created by any member of the org in the current calendar month."""
    try:
        conn = sqlite3.connect(get_settings().db_path, check_same_thread=False)
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM assessment_contexts
                WHERE org_id = ? AND created_at >= ?
                """,
                (org_id, _month_start()),
            ).fetchone()
            return int(row[0] if row else 0)
        finally:
            conn.close()
    except sqlite3.OperationalError:
        # assessment_contexts/org_id not migrated yet — treat as zero usage.
        return 0


def usage_summary(org_id: str) -> dict:
    sub = _repo.ensure_subscription(org_id)
    plan = get_plan(sub.get("plan"))
    used = count_assessments_this_month(org_id)
    quota = plan.assessment_quota
    remaining = None if quota is None else max(0, quota - used)
    return {
        "planId": plan.plan_id,
        "assessmentsThisMonth": used,
        "assessmentQuota": quota,
        "remaining": remaining,
        "unlimited": quota is None,
        "monthStart": _month_start(),
    }


def _auto_expire_grace(sub: dict) -> dict:
    """Self-healing: past-due → suspended once the grace window has elapsed."""
    if sub.get("status") not in {STATUS_PAST_DUE, STATUS_GRACE}:
        return sub
    grace_until = sub.get("grace_until")
    if not grace_until:
        return sub
    try:
        deadline = datetime.fromisoformat(str(grace_until))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
    except ValueError:
        return sub
    if _now() >= deadline:
        return suspend(sub["org_id"], reason="grace_expired")
    return sub


def billing_status(org_id: str) -> dict:
    sub = _repo.ensure_subscription(org_id)
    sub = apply_due_changes(org_id) or sub
    sub = _auto_expire_grace(sub)
    plan = get_plan(sub.get("plan"))
    status = str(sub.get("status") or STATUS_ACTIVE)
    return {
        "orgId": org_id,
        "planId": plan.plan_id,
        "planName": plan.name,
        "status": status,
        "inGrace": status == STATUS_GRACE,
        "graceUntil": sub.get("grace_until"),
        "periodStart": sub.get("current_period_start"),
        "periodEnd": sub.get("current_period_end"),
        "cancelAtPeriodEnd": bool(sub.get("cancel_at_period_end")),
        "pendingPlan": sub.get("pending_plan"),
        "lastError": sub.get("last_error"),
        "currency": sub.get("currency") or plan.currency,
        "enforcementEnabled": enforcement_enabled(),
        "gracePeriodDays": grace_period_days(),
        "demoMode": demo_mode_enabled(),
        "features": sorted(plan.features),
        "featureLabels": {},
        "usage": usage_summary(org_id),
        "canAssess": status != STATUS_SUSPENDED,
    }


# ── Gates ────────────────────────────────────────────────────────────────────

def quota_check(org_id: str) -> dict:
    summary = usage_summary(org_id)
    if summary["assessmentQuota"] is None:
        return {**summary, "allowed": True}
    return {**summary, "allowed": summary["assessmentsThisMonth"] < summary["assessmentQuota"]}


def feature_check(org_id: str, feature: str) -> dict:
    sub = _repo.ensure_subscription(org_id)
    plan = get_plan(sub.get("plan"))
    included = plan_includes_feature(plan.plan_id, feature)
    return {
        "feature": feature,
        "planId": plan.plan_id,
        "included": included,
        "enforcementEnabled": enforcement_enabled(),
        "allowed": included or not enforcement_enabled(),
    }


def assert_can_assess(org_id: str) -> None:
    """Suspension always blocks new assessments; quotas only when enforced."""
    sub = _repo.ensure_subscription(org_id)
    sub = _auto_expire_grace(sub)
    if sub.get("status") == STATUS_SUSPENDED:
        raise BillingBlocked(
            "ACCOUNT_SUSPENDED",
            "This workspace is suspended. Update billing to resume assessments. "
            "Your data stays readable and exportable.",
            status_code=403,
        )
    if not enforcement_enabled():
        return
    if sub.get("status") in {STATUS_PAST_DUE, STATUS_GRACE}:
        raise BillingBlocked(
            "PAYMENT_REQUIRED",
            "A recent payment failed and this workspace is in its grace period. "
            "Update billing to continue creating assessments.",
            status_code=402,
        )
    check = quota_check(org_id)
    if not check["allowed"]:
        raise BillingBlocked(
            "QUOTA_EXCEEDED",
            f"Your {get_plan(sub.get('plan')).name} plan includes {check['assessmentQuota']} assessments per month. "
            "Upgrade to continue.",
            status_code=402,
        )


def assert_feature(org_id: str, feature: str) -> None:
    check = feature_check(org_id, feature)
    if not check["allowed"]:
        raise BillingBlocked(
            "PLAN_FEATURE_REQUIRED",
            f"This feature requires a higher plan (current: {get_plan(check['planId']).name}).",
            status_code=403,
            feature=feature,
        )


# ── Plan lifecycle ───────────────────────────────────────────────────────────

def activate_plan(
    org_id: str,
    plan_id: str,
    *,
    amount: float | None = None,
    currency: str | None = None,
    tx_ref: str | None = None,
    period_days: int = PERIOD_DAYS,
    event_type: str = "payment_success",
) -> dict:
    """Apply a paid plan: clear grace/suspension, open a fresh billing period."""
    plan = get_plan(plan_id)
    previous = _repo.ensure_subscription(org_id)
    now = _now()
    sub = _repo.update_subscription(
        org_id,
        plan=plan.plan_id,
        status=STATUS_ACTIVE,
        currency=(currency or plan.currency),
        amount=amount,
        current_period_start=now.isoformat(),
        current_period_end=(now + timedelta(days=period_days)).isoformat(),
        grace_until=None,
        pending_plan=None,
        cancel_at_period_end=0,
        paychangu_ref=tx_ref,
        last_error=None,
    )
    _repo.record_payment_event(
        org_id,
        event_type,
        tx_ref=tx_ref,
        plan=plan.plan_id,
        amount=amount,
        currency=(currency or plan.currency),
        status=STATUS_ACTIVE,
        payload={"previousPlan": previous.get("plan")},
    )
    _sync_org_plan(org_id, plan.plan_id)
    record_event(
        "billing.plan_changed" if previous.get("plan") != plan.plan_id else "billing.payment_received",
        org_id=org_id,
        metadata={"plan": plan.plan_id, "previousPlan": previous.get("plan"), "txRef": tx_ref, "amount": amount},
    )
    return sub


def record_checkout(
    org_id: str,
    plan_id: str,
    *,
    tx_ref: str,
    amount: float | None,
    currency: str | None,
) -> dict:
    sub = _repo.update_subscription(org_id, paychangu_ref=tx_ref)
    _repo.record_payment_event(
        org_id,
        "checkout_initiated",
        tx_ref=tx_ref,
        plan=plan_id,
        amount=amount,
        currency=currency,
        status="pending",
    )
    record_event("billing.checkout_started", org_id=org_id, metadata={"plan": plan_id, "txRef": tx_ref})
    return sub


def handle_payment_failed(org_id: str, *, tx_ref: str | None = None, reason: str | None = None) -> dict:
    """Failed payment → past_due + grace window. Suspension happens on expiry."""
    days = grace_period_days()
    grace_until = (_now() + timedelta(days=days)).isoformat()
    sub = _repo.update_subscription(
        org_id,
        status=STATUS_GRACE,
        grace_until=grace_until,
        last_error=reason or "payment_failed",
    )
    _repo.record_payment_event(
        org_id,
        "payment_failed",
        tx_ref=tx_ref,
        plan=sub.get("plan"),
        status=STATUS_GRACE,
        payload={"reason": reason, "graceUntil": grace_until},
    )
    record_event(
        "billing.grace_started",
        org_id=org_id,
        metadata={"txRef": tx_ref, "reason": reason, "graceUntil": grace_until},
    )
    return sub


def start_grace(org_id: str, *, reason: str = "payment_failed", tx_ref: str | None = None) -> dict:
    return handle_payment_failed(org_id, tx_ref=tx_ref, reason=reason)


def suspend(org_id: str, *, reason: str = "grace_expired") -> dict:
    sub = _repo.update_subscription(org_id, status=STATUS_SUSPENDED, last_error=reason)
    _repo.record_payment_event(org_id, "suspended", plan=sub.get("plan"), status=STATUS_SUSPENDED, payload={"reason": reason})
    record_event("billing.suspended", org_id=org_id, metadata={"reason": reason})
    return sub


def reactivate(org_id: str) -> dict:
    sub = _repo.update_subscription(org_id, status=STATUS_ACTIVE, grace_until=None, last_error=None)
    _repo.record_payment_event(org_id, "reactivated", plan=sub.get("plan"), status=STATUS_ACTIVE)
    record_event("billing.reactivated", org_id=org_id, metadata={"plan": sub.get("plan")})
    return sub


def change_plan(org_id: str, new_plan: str, *, effective: str = "auto") -> dict:
    """Upgrade (immediate) or downgrade (applies at period end by default)."""
    target = str(new_plan or "").strip().lower()
    catalog = {"free", "pro", "enterprise"}
    if target not in catalog:
        raise ValueError("unknown_plan")
    sub = _repo.ensure_subscription(org_id)
    current = str(sub.get("plan") or "free")
    if target == current:
        return {"changed": False, "planId": current, "status": sub.get("status"), "pendingPlan": sub.get("pending_plan")}

    if is_upgrade(current, target) or effective == "immediate":
        updated = _repo.update_subscription(org_id, plan=target, status=STATUS_ACTIVE, pending_plan=None, grace_until=None)
        _repo.record_payment_event(org_id, "plan_changed", plan=target, status=STATUS_ACTIVE, payload={"previousPlan": current})
        _sync_org_plan(org_id, target)
        record_event("billing.plan_changed", org_id=org_id, metadata={"plan": target, "previousPlan": current, "effective": "immediate"})
        return {"changed": True, "planId": target, "previousPlan": current, "effective": "immediate", "status": updated.get("status")}

    # Downgrade: schedule at period end when a paid period is open, else apply now.
    period_end = sub.get("current_period_end")
    if period_end:
        updated = _repo.update_subscription(org_id, pending_plan=target)
        _repo.record_payment_event(org_id, "downgrade_scheduled", plan=target, payload={"effectiveAt": period_end})
        record_event("billing.plan_changed", org_id=org_id, metadata={"plan": target, "previousPlan": current, "effective": "period_end"})
        return {"changed": True, "planId": current, "previousPlan": current, "pendingPlan": target, "effective": "period_end", "effectiveAt": period_end}
    updated = _repo.update_subscription(org_id, plan=target, pending_plan=None)
    _repo.record_payment_event(org_id, "plan_changed", plan=target, payload={"previousPlan": current})
    _sync_org_plan(org_id, target)
    record_event("billing.plan_changed", org_id=org_id, metadata={"plan": target, "previousPlan": current, "effective": "immediate"})
    return {"changed": True, "planId": target, "previousPlan": current, "effective": "immediate", "status": updated.get("status")}


def cancel_at_period_end(org_id: str) -> dict:
    sub = _repo.update_subscription(org_id, cancel_at_period_end=1, pending_plan="free")
    record_event("billing.plan_changed", org_id=org_id, metadata={"plan": "free", "effective": "period_end", "reason": "canceled"})
    return sub


def apply_due_changes(org_id: str | None = None) -> dict | list[str] | None:
    """Apply pending downgrades whose period has ended (idempotent)."""
    if org_id is not None:
        sub = _repo.get_subscription(org_id)
        if not sub or not sub.get("pending_plan"):
            return sub
        period_end = sub.get("current_period_end")
        due = True
        if period_end:
            try:
                deadline = datetime.fromisoformat(str(period_end))
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                due = _now() >= deadline
            except ValueError:
                due = True
        if not due:
            return sub
        target = str(sub["pending_plan"])
        updated = _repo.update_subscription(
            org_id,
            plan=target,
            pending_plan=None,
            cancel_at_period_end=1 if target == "free" else 0,
            status=STATUS_ACTIVE if target != "free" else sub.get("status", STATUS_ACTIVE),
        )
        _repo.record_payment_event(org_id, "plan_changed", plan=target, payload={"effective": "period_end"})
        _sync_org_plan(org_id, target)
        record_event("billing.plan_changed", org_id=org_id, metadata={"plan": target, "effective": "period_end"})
        return updated

    applied: list[str] = []
    for sub in _repo_all_with_pending():
        result = apply_due_changes(sub["org_id"])
        applied.append(sub["org_id"])
    return applied


def _repo_all_with_pending() -> list[dict]:
    sub = _repo.ensure_subscription("__scan__")
    # Lightweight scan via repository internals kept simple: reuse SQL through list API.
    import sqlite3 as _sqlite

    with _sqlite.connect(_repo.db_path) as conn:
        conn.row_factory = _sqlite.Row
        rows = conn.execute("SELECT org_id FROM subscriptions WHERE pending_plan IS NOT NULL").fetchall()
    return [dict(r) for r in rows]


def payment_history(org_id: str, limit: int = 50) -> list[dict]:
    return _repo.list_payment_events(org_id, limit=limit)
