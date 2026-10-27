"""Subscription plans (Phase 7) — configurable pricing, quotas, feature gates.

- STARTER      (plan id "free")       — $0, 3 assessments/month, basic reports
                       and signals, Document Intelligence Mode.
- PROFESSIONAL (plan id "pro")        — $49/month, unlimited assessments,
                       AI Analyst, Signals, Reports, history, collaboration.
                       PayChangu hosted link: SC-GDDYA0.
- ENTERPRISE   (plan id "enterprise") — Custom price, dedicated workspace,
                       RBAC, audit logs, multiple organizations, API access,
                       custom reports. PayChangu hosted link: SC-MBXJF6.

Pricing is configurable without code changes via ``KULIMA_PLAN_PRICING_JSON``
(e.g. ``{"pro": {"monthly_price": 59, "currency": "MWK"}}``) and currency via
``KULIMA_PLAN_CURRENCY``. Payment links via ``PAYCHANGU_LINK_PRO`` /
``PAYCHANGU_LINK_ENTERPRISE``.
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
    "ask_ic": "AI Analyst",
    "enterprise_reports": "Reports",
    "basic_reports": "Basic reports",
    "document_intelligence": "Document Intelligence Mode",
    "assessment_history": "Assessment history",
    "collaboration": "Collaboration",
    "priority_support": "Priority support",
    "governance_dashboard": "Trust & Governance dashboard",
    "audit_log": "Audit logs",
    "rbac": "Role-based access control",
    "multiple_organizations": "Multiple organizations",
    "dedicated_workspace": "Dedicated workspace",
    "custom_reports": "Custom reports",
    "private_deployment": "Private deployment",
    "api_integration": "API access",
    "custom_integrations": "Custom integrations",
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
    target: str = ""                    # who the plan is built for
    payment_link: str = ""             # PayChangu hosted payment link (SC-…)
    price_label: str = ""              # overrides the numeric price display (e.g. "Custom")

    @property
    def is_paid(self) -> bool:
        """A plan that requires payment. The Starter/free plan is the only
        non-paid tier; Enterprise is paid even when its price is 'Custom'
        (monthly_price 0), so routing must key off this, not the price."""
        return self.plan_id != "free"

    @property
    def display_price(self) -> str:
        if self.price_label:
            return self.price_label
        if self.monthly_price <= 0:
            return "Free"
        return f"{self.currency} {self.monthly_price:,.0f}/month"

    def to_payload(self) -> dict:
        return {
            "planId": self.plan_id,
            "name": self.name,
            "description": self.description,
            "target": self.target,
            "monthlyPrice": self.monthly_price,
            "priceLabel": self.display_price,
            "isCustomPrice": bool(self.price_label),
            "isPaid": self.is_paid,
            "paymentLink": self.payment_link,
            "currency": self.currency,
            "assessmentQuota": self.assessment_quota,
            "assessmentQuotaLabel": "Unlimited assessments" if self.assessment_quota is None else f"{self.assessment_quota} assessments/month",
            "memberQuota": self.member_quota,
            "memberQuotaLabel": "Unlimited users" if self.member_quota is None else f"{self.member_quota} user(s)",
            "features": sorted(self.features),
            "featureLabels": [FEATURE_LABELS.get(f, f) for f in sorted(self.features)],
        }


def _default_currency() -> str:
    return os.getenv("KULIMA_PLAN_CURRENCY", "USD").strip().upper() or "USD"


def _pro_payment_link() -> str:
    return os.getenv("PAYCHANGU_LINK_PRO", "https://pay.paychangu.com/SC-GDDYA0").strip()


def _enterprise_payment_link() -> str:
    return os.getenv("PAYCHANGU_LINK_ENTERPRISE", "https://pay.paychangu.com/SC-MBXJF6").strip()


def load_plans() -> dict[str, PlanSpec]:
    """Build the plan catalog, applying env overrides (pricing configurable)."""
    currency = _default_currency()
    plans: dict[str, PlanSpec] = {
        "free": PlanSpec(
            plan_id="free",
            name="Starter",
            description="Document Intelligence for students, researchers and small NGOs — run your first assessments and export basic reports.",
            target="Students · Researchers · Small NGOs",
            monthly_price=0.0,
            currency=currency,
            assessment_quota=3,
            member_quota=1,
            features=frozenset({
                "basic_signals",
                "community_signals",
                "basic_reports",
                "document_intelligence",
                "document_security",
            }),
        ),
        "pro": PlanSpec(
            plan_id="pro",
            name="Professional",
            description="Unlimited assessments with the AI Analyst, full signals and reports, assessment history and collaboration for NGOs, programmes and consultants.",
            target="NGOs · Development Programs · Tourism SMEs · Consultants",
            monthly_price=49.0,
            currency=currency,
            assessment_quota=None,
            member_quota=10,
            features=frozenset({
                "basic_signals",
                "community_signals",
                "climate_signals",
                "tourism_signals",
                "ask_ic",
                "enterprise_reports",
                "basic_reports",
                "document_intelligence",
                "assessment_history",
                "collaboration",
                "priority_support",
                "document_security",
            }),
            payment_link=_pro_payment_link(),
        ),
        "enterprise": PlanSpec(
            plan_id="enterprise",
            name="Enterprise",
            description="Dedicated workspace with RBAC, audit logs, multiple organizations, API access and custom reports for governments, DFIs, universities and large NGOs.",
            target="Governments · DFIs · Universities · Donors · Large NGOs",
            monthly_price=0.0,
            price_label="Custom",
            currency=currency,
            assessment_quota=None,
            member_quota=None,
            features=frozenset(ALL_FEATURES),
            payment_link=_enterprise_payment_link(),
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
                    target=str(patch.get("target", base.target)),
                    monthly_price=float(patch.get("monthly_price", base.monthly_price)),
                    price_label=str(patch.get("price_label", base.price_label)),
                    currency=str(patch.get("currency", base.currency)).upper(),
                    assessment_quota=patch.get("assessment_quota", base.assessment_quota),
                    member_quota=patch.get("member_quota", base.member_quota),
                    features=base.features,
                    payment_link=str(patch.get("payment_link", base.payment_link)),
                )
        except (ValueError, TypeError) as exc:
            _log.warning("Invalid KULIMA_PLAN_PRICING_JSON ignored: %s", exc)
    return plans


def get_plan(plan_id: str | None) -> PlanSpec:
    plans = load_plans()
    return plans.get(str(plan_id or "free").strip().lower(), plans["free"])


def get_payment_link(plan_id: str | None) -> str:
    """The PayChangu hosted payment link configured for a plan (empty if none)."""
    return get_plan(plan_id).payment_link


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
