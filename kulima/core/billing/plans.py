"""Subscription plans (Phase 7) — configurable pricing, quotas, feature gates.

- FREE       — 5 assessments/month, basic signals.
- PRO        — unlimited assessments, advanced climate + tourism signals,
               Ask IC, enterprise reports.
- ENTERPRISE — unlimited users, RBAC, audit logs, private deployment,
               API integration, Trust & Governance dashboard.

Pricing is configurable without code changes via ``KULIMA_PLAN_PRICING_JSON``
(e.g. ``{"pro": {"monthly_price": 59, "currency": "MWK"}}``) and currency via
``KULIMA_PLAN_CURRENCY``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

FEATURE_LABELS: dict[str, str] = {
    "basic_signals": "Basic signals",
    "community_signals": "Community impact signals",
    "climate_signals": "Advanced climate signals",
    "tourism_signals": "Advanced tourism signals",
    "ask_ic": "Ask IC",
    "enterprise_reports": "Enterprise reports",
    "governance_dashboard": "Trust & Governance dashboard",
    "audit_log": "Audit logs",
    "rbac": "Role-based access control",
    "private_deployment": "Private deployment",
    "api_integration": "API integration",
    "document_security": "Encrypted storage metadata",
}

ALL_FEATURES: frozenset[str] = frozenset(FEATURE_LABELS)


@dataclass(frozen=True)
class PlanSpec:
    plan_id: str
    name: str
    description: str
    monthly_price: float
    currency: str
    assessment_quota: int | None       # None = unlimited
    member_quota: int | None           # None = unlimited
    features: frozenset[str] = field(default_factory=frozenset)

    def to_payload(self) -> dict:
        return {
            "planId": self.plan_id,
            "name": self.name,
            "description": self.description,
            "monthlyPrice": self.monthly_price,
            "currency": self.currency,
            "assessmentQuota": self.assessment_quota,
            "assessmentQuotaLabel": "Unlimited" if self.assessment_quota is None else f"{self.assessment_quota}/month",
            "memberQuota": self.member_quota,
            "memberQuotaLabel": "Unlimited users" if self.member_quota is None else f"{self.member_quota} user(s)",
            "features": sorted(self.features),
            "featureLabels": [FEATURE_LABELS.get(f, f) for f in sorted(self.features)],
        }


def _default_currency() -> str:
    return os.getenv("KULIMA_PLAN_CURRENCY", "USD").strip().upper() or "USD"


def load_plans() -> dict[str, PlanSpec]:
    """Build the plan catalog, applying env overrides (pricing configurable)."""
    currency = _default_currency()
    plans: dict[str, PlanSpec] = {
        "free": PlanSpec(
            plan_id="free",
            name="Free",
            description="Explore Kulima FLEX with basic signals on up to 5 assessments per month.",
            monthly_price=0.0,
            currency=currency,
            assessment_quota=5,
            member_quota=2,
            features=frozenset({"basic_signals", "community_signals", "document_security"}),
        ),
        "pro": PlanSpec(
            plan_id="pro",
            name="Pro",
            description="Unlimited assessments with advanced climate & tourism signals, Ask IC, and enterprise reports.",
            monthly_price=49.0,
            currency=currency,
            assessment_quota=None,
            member_quota=10,
            features=frozenset(
                {
                    "basic_signals",
                    "community_signals",
                    "climate_signals",
                    "tourism_signals",
                    "ask_ic",
                    "enterprise_reports",
                    "document_security",
                }
            ),
        ),
        "enterprise": PlanSpec(
            plan_id="enterprise",
            name="Enterprise",
            description="Unlimited users, RBAC, audit logs, private deployment and API integration for institutions.",
            monthly_price=299.0,
            currency=currency,
            assessment_quota=None,
            member_quota=None,
            features=frozenset(ALL_FEATURES),
        ),
    }

    raw = os.getenv("KULIMA_PLAN_PRICING_JSON", "").strip()
    if raw:
        try:
            overrides = json.loads(raw)
            for plan_id, patch in (overrides or {}).items():
                base = plans.get(str(plan_id).lower())
                if base is None or not isinstance(patch, dict):
                    continue
                plans[base.plan_id] = PlanSpec(
                    plan_id=base.plan_id,
                    name=str(patch.get("name", base.name)),
                    description=str(patch.get("description", base.description)),
                    monthly_price=float(patch.get("monthly_price", base.monthly_price)),
                    currency=str(patch.get("currency", base.currency)).upper(),
                    assessment_quota=patch.get("assessment_quota", base.assessment_quota),
                    member_quota=patch.get("member_quota", base.member_quota),
                    features=base.features,
                )
        except (ValueError, TypeError) as exc:
            _log.warning("Invalid KULIMA_PLAN_PRICING_JSON ignored: %s", exc)
    return plans


def get_plan(plan_id: str | None) -> PlanSpec:
    plans = load_plans()
    return plans.get(str(plan_id or "free").strip().lower(), plans["free"])


def all_plans() -> list[PlanSpec]:
    plans = load_plans()
    return [plans["free"], plans["pro"], plans["enterprise"]]


def plan_rank(plan_id: str | None) -> int:
    order = {"free": 0, "pro": 1, "enterprise": 2}
    return order.get(str(plan_id or "free").strip().lower(), 0)


def is_upgrade(current: str | None, target: str | None) -> bool:
    return plan_rank(target) > plan_rank(current)


def is_downgrade(current: str | None, target: str | None) -> bool:
    return plan_rank(target) < plan_rank(current)


def plan_includes_feature(plan_id: str | None, feature: str) -> bool:
    return feature in get_plan(plan_id).features


def plan_catalog_payload(current_plan: str | None = None) -> dict:
    return {
        "plans": [p.to_payload() for p in all_plans()],
        "currentPlan": str(current_plan or "free"),
        "currency": _default_currency(),
        "featureLabels": FEATURE_LABELS,
    }
