"""Billing & subscription API (Enterprise Trust Phases 7–8).

Plan catalog, quota/feature status, PayChangu checkout, webhook handling
(HMAC-verified, idempotent), payment history, downgrade/cancel/reactivate.
When ``PAYCHANGU_SECRET_KEY`` is absent the checkout endpoint returns a clean
503 unless ``KULIMA_BILLING_DEMO_MODE`` is enabled (demos & tests).
"""

from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from kulima.core.billing.paychangu import PayChanguClient, PayChanguError
from kulima.core.billing.plans import (
    FEATURE_LABELS,
    get_plan,
    plan_catalog_payload,
)
from kulima.core.billing.repository import BillingRepository
from kulima.core.billing.service import (
    activate_plan,
    billing_status,
    cancel_at_period_end,
    change_plan,
    demo_mode_enabled,
    handle_payment_failed,
    link_autoconfirm_enabled,
    reactivate,
    record_checkout,
    usage_summary,
)
from kulima.core.orgs.models import Permission

from ..core.auth import OrgContext, get_current_org, require_permission

router = APIRouter()

_repo_cache: BillingRepository | None = None


def _repo() -> BillingRepository:
    global _repo_cache
    if _repo_cache is None:
        _repo_cache = BillingRepository()
    return _repo_cache


class CheckoutRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=32)
    returnUrl: str | None = None
    callbackUrl: str | None = None


class ConfirmRequest(BaseModel):
    txRef: str = Field(min_length=1, max_length=120)
    plan: str = Field(min_length=1, max_length=32)


class LinkReturnRequest(BaseModel):
    """Outcome reported when the customer lands back from a PayChangu hosted link."""

    txRef: str = Field(min_length=1, max_length=120)
    result: str = Field(default="completed")  # completed | pending | failed | cancelled


class PlanChangeRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=32)


# ── Catalog & status ─────────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans(current: OrgContext = Depends(get_current_org)):
    """Plan catalog with configurable pricing plus the caller's usage."""
    catalog = plan_catalog_payload(current.plan)
    return {
        **catalog,
        "usage": usage_summary(current.org_id),
        "canManageBilling": current.has_permission(Permission.MANAGE_BILLING),
    }


@router.get("/status")
async def get_status(current: OrgContext = Depends(get_current_org)):
    """Subscription status, grace/suspension state and feature labels."""
    data = billing_status(current.org_id)
    data["featureLabels"] = FEATURE_LABELS
    data["orgName"] = current.org.name
    data["role"] = current.role.value
    data["canManageBilling"] = current.has_permission(Permission.MANAGE_BILLING)
    return data


@router.get("/history")
async def payment_history(current: OrgContext = Depends(get_current_org)):
    return {"events": _repo().list_payment_events(current.org_id, limit=100)}


# ── Checkout ─────────────────────────────────────────────────────────────────


def _hosted_link_redirect(link: str, return_url: str | None, tx_ref: str) -> str:
    """PayChangu hosted links accept a ``redirectUrl`` param. We tack the tx ref
    onto it so the billing page can finalize the payment outcome on return."""
    base = (return_url or "").strip()
    if not base:
        return link
    sep = "&" if "?" in base else "?"
    base = f"{base}{sep}tx={quote(tx_ref, safe='')}&payment=completed"
    link_sep = "&" if "?" in link else "?"
    return f"{link}{link_sep}redirectUrl={quote(base, safe='')}"


@router.post("/checkout")
async def start_checkout(
    payload: CheckoutRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    """Begin a PayChangu hosted checkout for a paid plan."""
    target = str(payload.plan or "").strip().lower()
    if target not in {"free", "pro", "enterprise"}:
        raise HTTPException(status_code=422, detail={"error": True, "message": "Unknown plan"})
    plan = get_plan(target)

    if not plan.is_paid:
        # Starter target = downgrade / scheduled change, never a payment.
        result = change_plan(current.org_id, target)
        return {"status": "applied", "result": result}

    tx_ref = PayChanguClient.new_tx_ref(prefix=f"kulima-{target}")
    client = PayChanguClient()

    # Phase 3 primary path: PayChangu hosted payment link (pay.paychangu.com/SC-…).
    # Simplest and most reliable — send the customer straight to the hosted page;
    # the outcome lands back on /billing and is finalized via /checkout/return.
    if plan.payment_link:
        record_checkout(
            current.org_id,
            target,
            tx_ref=tx_ref,
            amount=plan.monthly_price or None,
            currency=plan.currency,
        )
        return {
            "txRef": tx_ref,
            "checkoutUrl": _hosted_link_redirect(plan.payment_link, payload.returnUrl, tx_ref),
            "paymentLink": True,
            "plan": target,
            "amount": plan.monthly_price,
            "currency": plan.currency,
        }

    if not client.configured:
        if demo_mode_enabled():
            record_checkout(
                current.org_id,
                target,
                tx_ref=tx_ref,
                amount=plan.monthly_price,
                currency=plan.currency,
            )
            return {
                "txRef": tx_ref,
                "checkoutUrl": None,
                "demoMode": True,
                "plan": target,
                "amount": plan.monthly_price,
                "currency": plan.currency,
                "message": "PayChangu is not configured. Confirm this checkout via /api/v1/billing/checkout/confirm (demo mode).",
            }
        raise HTTPException(
            status_code=503,
            detail={
                "error": True,
                "code": "BILLING_NOT_CONFIGURED",
                "message": "PayChangu is not configured yet. Set PAYCHANGU_SECRET_KEY to enable subscriptions.",
            },
        )

    try:
        result = client.initiate_payment(
            plan.monthly_price,
            tx_ref=tx_ref,
            plan=target,
            org_id=current.org_id,
            callback_url=payload.callbackUrl or "",
            return_url=payload.returnUrl or "",
            description=f"Kulima FLEX {plan.name} plan subscription",
            currency=plan.currency,
        )
    except PayChanguError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": True, "code": "PAYCHANGU_ERROR", "message": str(exc)},
        )

    record_checkout(
        current.org_id,
        target,
        tx_ref=tx_ref,
        amount=plan.monthly_price,
        currency=plan.currency,
    )
    return {
        "txRef": tx_ref,
        "checkoutUrl": result.get("checkoutUrl"),
        "plan": target,
        "amount": plan.monthly_price,
        "currency": plan.currency,
    }


@router.post("/checkout/confirm")
async def confirm_checkout(
    payload: ConfirmRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    """Demo-mode checkout confirmation (disabled unless KULIMA_BILLING_DEMO_MODE)."""
    if not demo_mode_enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "error": True,
                "code": "DEMO_DISABLED",
                "message": "Local checkout confirmation is only available in demo mode.",
            },
        )
    target = str(payload.plan or "").strip().lower()
    plan = get_plan(target)
    event = _repo().find_event_by_tx_ref(payload.txRef)
    if event is not None and event.get("orgId") != current.org_id:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Unknown transaction reference"})
    sub = activate_plan(
        current.org_id,
        plan.plan_id,
        amount=plan.monthly_price,
        currency=plan.currency,
        tx_ref=payload.txRef,
        event_type="demo_payment",
    )
    return {"status": "active", "planId": sub.get("plan"), "txRef": payload.txRef}


@router.post("/checkout/return")
async def return_from_hosted_link(
    payload: LinkReturnRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    """Phase 4/5: finalize a PayChangu hosted-link payment when the customer is
    back on /billing. Success upgrades the plan and stores the billing event;
    failure opens the grace window; pending/cancelled leave the plan untouched."""
    event = _repo().find_event_by_tx_ref(payload.txRef)
    if event is None or event.get("orgId") != current.org_id:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Unknown transaction reference"})
    result = str(payload.result or "completed").strip().lower()
    plan = get_plan(event.get("plan") or "pro")

    if event.get("eventType") in {"payment_success", "webhook_payment", "demo_payment", "link_payment"}:
        return {"outcome": "active", "planId": plan.plan_id, "alreadyProcessed": True, "status": billing_status(current.org_id)}

    if result == "cancelled":
        _repo().record_payment_event(
            current.org_id, "payment_cancelled", tx_ref=payload.txRef, plan=plan.plan_id, status="cancelled",
        )
        return {
            "outcome": "cancelled",
            "message": "Payment cancelled. Your plan is unchanged and everything you had stays available.",
            "status": billing_status(current.org_id),
        }

    if result == "pending":
        _repo().record_payment_event(
            current.org_id, "payment_pending", tx_ref=payload.txRef, plan=plan.plan_id,
            amount=plan.monthly_price or None, currency=plan.currency, status="pending",
        )
        return {
            "outcome": "pending",
            "message": "Payment pending. We will activate your plan the moment PayChangu confirms it.",
            "status": billing_status(current.org_id),
        }

    if result == "failed":
        handle_payment_failed(current.org_id, tx_ref=payload.txRef, reason="hosted_link_failed")
        return {
            "outcome": "failed",
            "message": "Payment failed. Your workspace keeps a grace window — retry the payment to restore full access.",
            "status": billing_status(current.org_id),
        }

    # Completed: verify with PayChangu when the API is configured, otherwise
    # auto-confirm the hosted-link redirect (webhook stays authoritative).
    client = PayChanguClient()
    if client.configured:
        try:
            verified = client.verify_payment(payload.txRef)
            data = verified.get("data") or {}
            status_value = str(data.get("status") or verified.get("status") or "").lower()
            if status_value in {"success", "successful", "paid", "completed"}:
                amount = data.get("amount") or plan.monthly_price or None
                sub = activate_plan(
                    current.org_id, plan.plan_id,
                    amount=float(amount) if amount else None,
                    currency=str(data.get("currency") or plan.currency),
                    tx_ref=payload.txRef, event_type="payment_success",
                )
                return {"outcome": "active", "planId": sub.get("plan"), "status": billing_status(current.org_id)}
            if status_value in {"failed", "failure"}:
                handle_payment_failed(current.org_id, tx_ref=payload.txRef, reason="verify_failed")
                return {"outcome": "failed", "message": "Payment failed.", "status": billing_status(current.org_id)}
            return {"outcome": "pending", "message": "Payment pending.", "status": billing_status(current.org_id)}
        except PayChanguError as exc:
            if not link_autoconfirm_enabled():
                raise HTTPException(
                    status_code=502,
                    detail={"error": True, "code": "PAYCHANGU_ERROR", "message": str(exc)},
                )

    if not link_autoconfirm_enabled():
        return {
            "outcome": "pending",
            "message": "Payment pending verification. Set KULIMA_BILLING_LINK_AUTOCONFIRM=true to activate on return.",
            "status": billing_status(current.org_id),
        }

    sub = activate_plan(
        current.org_id, plan.plan_id,
        amount=plan.monthly_price or None,
        currency=plan.currency,
        tx_ref=payload.txRef,
        event_type="link_payment",
    )
    return {
        "outcome": "active",
        "planId": sub.get("plan"),
        "message": f"Welcome to {plan.name}! Your workspace is updated.",
        "status": billing_status(current.org_id),
    }


@router.post("/verify/{tx_ref}")
async def verify_checkout(
    tx_ref: str,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    """Confirm a payment with PayChangu (or locally in demo mode)."""
    event = _repo().find_event_by_tx_ref(tx_ref)
    if event is None or event.get("orgId") != current.org_id:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Unknown transaction reference"})
    if event.get("eventType") in {"payment_success", "webhook_payment", "demo_payment", "link_payment"}:
        return {"status": "active", "processed": False, "reason": "already_processed"}

    plan = get_plan(event.get("plan") or "pro")
    client = PayChanguClient()

    if not client.configured:
        if demo_mode_enabled():
            activate_plan(
                current.org_id,
                plan.plan_id,
                amount=plan.monthly_price,
                currency=plan.currency,
                tx_ref=tx_ref,
                event_type="demo_payment",
            )
            return {"status": "active", "processed": True, "demoMode": True}
        raise HTTPException(
            status_code=503,
            detail={"error": True, "code": "BILLING_NOT_CONFIGURED", "message": "PayChangu is not configured yet."},
        )

    try:
        result = client.verify_payment(tx_ref)
    except PayChanguError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": True, "code": "PAYCHANGU_ERROR", "message": str(exc)},
        )
    data = result.get("data") or {}
    status_value = str(data.get("status") or result.get("status") or "").lower()
    if status_value in {"success", "successful", "paid", "completed"}:
        amount = data.get("amount") or event.get("amount")
        currency = data.get("currency") or event.get("currency") or plan.currency
        sub = activate_plan(
            current.org_id,
            plan.plan_id,
            amount=float(amount) if amount else plan.monthly_price,
            currency=str(currency),
            tx_ref=tx_ref,
            event_type="payment_success",
        )
        return {"status": "active", "processed": True, "planId": sub.get("plan")}
    if status_value in {"failed", "failure"}:
        handle_payment_failed(current.org_id, tx_ref=tx_ref, reason="verify_failed")
        return {"status": "grace", "processed": True}
    return {"status": status_value or "pending", "processed": False}


# ── Webhook ──────────────────────────────────────────────────────────────────


@router.post("/webhook")
async def paychangu_webhook(request: Request):
    """HMAC-verified PayChangu webhook (idempotent by tx_ref)."""
    raw = await request.body()
    signature = (
        request.headers.get("Signature")
        or request.headers.get("signature")
        or request.headers.get("x-paychangu-signature")
    )
    client = PayChanguClient()
    if not client.webhook_verification_available:
        raise HTTPException(
            status_code=503,
            detail={
                "error": True,
                "code": "WEBHOOK_NOT_CONFIGURED",
                "message": "PAYCHANGU_WEBHOOK_SECRET is not configured; refusing unsigned webhooks.",
            },
        )
    if not client.verify_webhook(raw, signature):
        raise HTTPException(
            status_code=401,
            detail={"error": True, "code": "INVALID_SIGNATURE", "message": "Invalid webhook signature"},
        )
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": True, "message": "Invalid JSON body"})

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else (payload.get("meta") or {})
    tx_ref = str(data.get("tx_ref") or payload.get("tx_ref") or meta.get("txRef") or "").strip()
    event_hint = str(
        payload.get("event_type") or payload.get("event") or data.get("status") or payload.get("status") or ""
    ).lower()
    status_value = str(data.get("status") or payload.get("status") or "").lower()

    org_id = str(meta.get("orgId") or meta.get("org_id") or "").strip() or None
    plan_id = str(meta.get("plan") or "").strip() or None
    amount = data.get("amount") or payload.get("amount")
    currency = data.get("currency") or payload.get("currency")

    if not org_id and tx_ref:
        known = _repo().find_event_by_tx_ref(tx_ref)
        if known is not None:
            org_id = known.get("orgId")
            plan_id = plan_id or known.get("plan")

    if not org_id:
        # Acknowledge unknown references so PayChangu stops retrying.
        return {"received": True, "processed": False, "reason": "unknown_reference"}

    success = "success" in event_hint or status_value in {"success", "successful", "paid", "completed"}
    failed = "fail" in event_hint or status_value in {"failed", "failure"}

    if success:
        if tx_ref and _repo().find_event_by_tx_ref(tx_ref, "webhook_payment") is not None:
            return {"received": True, "processed": False, "reason": "duplicate"}
        plan = get_plan(plan_id or "pro")
        activate_plan(
            org_id,
            plan.plan_id,
            amount=float(amount) if amount else plan.monthly_price,
            currency=str(currency or plan.currency),
            tx_ref=tx_ref or None,
            event_type="webhook_payment",
        )
        return {"received": True, "processed": True, "planId": plan.plan_id}

    if failed:
        if tx_ref and _repo().find_event_by_tx_ref(tx_ref, "payment_failed") is not None:
            return {"received": True, "processed": False, "reason": "duplicate"}
        handle_payment_failed(org_id, tx_ref=tx_ref or None, reason=f"webhook_{status_value or 'failed'}")
        return {"received": True, "processed": True, "status": "grace"}

    return {"received": True, "processed": False, "reason": "unhandled_event"}


# ── Plan changes ─────────────────────────────────────────────────────────────


@router.post("/downgrade")
async def downgrade_plan(
    payload: PlanChangeRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    """Schedule (or apply) a plan change. Downgrades default to period end."""
    target = str(payload.plan or "").strip().lower()
    if target not in {"free", "pro", "enterprise"}:
        raise HTTPException(status_code=422, detail={"error": True, "message": "Unknown plan"})
    result = change_plan(current.org_id, target)
    return {"result": result, "status": billing_status(current.org_id)}


@router.post("/cancel")
async def cancel_subscription(
    current: OrgContext = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    """Cancel at period end — data stays fully accessible (never held hostage)."""
    cancel_at_period_end(current.org_id)
    return {"status": billing_status(current.org_id)}


@router.post("/reactivate")
async def reactivate_subscription(
    current: OrgContext = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    """Clear grace/suspension and resume the current plan."""
    reactivate(current.org_id)
    _repo().update_subscription(current.org_id, cancel_at_period_end=0, pending_plan=None)
    return {"status": billing_status(current.org_id)}
