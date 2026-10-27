"""Billing & PayChangu monetization validation (Mission: Starter / Professional / Enterprise).

Run from the repo root:

    python scripts/validate_billing.py

Covers:
  Phase 1  plan catalog (Starter $0 / Professional $49 / Enterprise Custom)
  Phase 2  plan enforcement (quota + feature gates, suspension)
  Phase 3  PayChangu hosted links (SC-GDDYA0 / SC-MBXJF6) + checkout routing
  Phase 4  success handling (activate plan, org sync, billing event, renewal)
  Phase 5  failure handling (failed → grace, pending/cancelled events)
  Phase 6  admin visibility (status payload fields, payment history)
  Phase 7  wiring checks (router endpoints, frontend pages, env examples)

Uses an isolated temp SQLite DB via KULIMA_DB_PATH — never touches founders.db.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Isolate all billing state into a throwaway database BEFORE importing kulima.
_tmp_db = tempfile.NamedTemporaryFile(prefix="kulima_billing_validation_", suffix=".db", delete=False)
_tmp_db.close()
os.environ["KULIMA_DB_PATH"] = _tmp_db.name
os.environ["KULIMA_BILLING_DEMO_MODE"] = "false"
os.environ["KULIMA_BILLING_LINK_AUTOCONFIRM"] = "true"

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp437 consoles
except Exception:  # noqa: BLE001
    pass

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail and not condition else ""))


def main() -> int:
    from kulima.core.billing import service
    from kulima.core.billing.plans import (
        FEATURE_LABELS,
        all_plans,
        get_payment_link,
        get_plan,
        is_downgrade,
        is_upgrade,
        plan_catalog_payload,
    )
    from kulima.core.billing.repository import BillingRepository

    repo = BillingRepository()

    # ── Phase 1 / catalog ────────────────────────────────────────────────────
    starter = get_plan("free")
    pro = get_plan("pro")
    ent = get_plan("enterprise")

    check("Starter is named 'Starter' and costs $0", starter.name == "Starter" and starter.monthly_price == 0.0, starter.name)
    check("Starter quota = 3 assessments", starter.assessment_quota == 3, str(starter.assessment_quota))
    check("Starter is not a paid plan", not starter.is_paid)
    check("Starter has Document Intelligence Mode", "document_intelligence" in starter.features)
    check("Starter has basic reports + basic signals", {"basic_reports", "basic_signals"} <= starter.features)

    check("Professional is named 'Professional'", pro.name == "Professional", pro.name)
    check("Professional is $49/month", pro.monthly_price == 49.0 and pro.display_price.endswith("49/month"), pro.display_price)
    check("Professional is unlimited assessments", pro.assessment_quota is None)
    check("Professional has AI Analyst / Reports / history / collaboration / priority support",
          {"ask_ic", "enterprise_reports", "assessment_history", "collaboration", "priority_support"} <= pro.features)
    check("Professional is paid", pro.is_paid)

    check("Enterprise price shows 'Custom'", ent.price_label == "Custom" and ent.display_price == "Custom", ent.display_price)
    check("Enterprise is treated as PAID despite Custom price", ent.is_paid)
    check("Enterprise has RBAC / audit / multi-org / API / custom reports / dedicated workspace",
          {"rbac", "audit_log", "multiple_organizations", "api_integration", "custom_reports", "dedicated_workspace", "custom_integrations"} <= ent.features)

    check("Feature relabel: ask_ic → 'AI Analyst'", FEATURE_LABELS.get("ask_ic") == "AI Analyst")
    check("Feature relabel: enterprise_reports → 'Reports'", FEATURE_LABELS.get("enterprise_reports") == "Reports")
    check("Catalog has exactly Starter/Professional/Enterprise",
          [p.name for p in all_plans()] == ["Starter", "Professional", "Enterprise"],
          str([p.name for p in all_plans()]))

    payload = plan_catalog_payload("free")
    by_id = {p["planId"]: p for p in payload["plans"]}
    check("API payload exposes paymentLink", by_id["pro"]["paymentLink"].endswith("SC-GDDYA0") and by_id["enterprise"]["paymentLink"].endswith("SC-MBXJF6"))
    check("API payload exposes isPaid / priceLabel", by_id["free"]["isPaid"] is False and by_id["enterprise"]["priceLabel"] == "Custom")

    # ── Phase 3 / PayChangu hosted links ─────────────────────────────────────
    check("Professional hosted link is SC-GDDYA0",
          get_payment_link("pro") == "https://pay.paychangu.com/SC-GDDYA0", get_payment_link("pro"))
    check("Enterprise hosted link is SC-MBXJF6",
          get_payment_link("enterprise") == "https://pay.paychangu.com/SC-MBXJF6", get_payment_link("enterprise"))
    check("Starter has no payment link (never a payment)", get_payment_link("free") == "")

    from backend.app.routers.billing import _hosted_link_redirect  # noqa: E402

    routed = _hosted_link_redirect(pro.payment_link, "https://app.kulima.io/billing", "kulima-pro-test123")
    check("Checkout redirect targets hosted link + carries tx + payment params",
          routed.startswith("https://pay.paychangu.com/SC-GDDYA0?redirectUrl=")
          and "tx%3Dkulima-pro-test123" in routed and "payment%3Dcompleted" in routed, routed)

    # ── Phase 4 / success handling ───────────────────────────────────────────
    org = "validation-org-1"
    service.record_checkout(org, "pro", tx_ref="kulima-pro-tx1", amount=49.0, currency="USD")
    pending = repo.find_event_by_tx_ref("kulima-pro-tx1")
    check("Checkout recorded as pending billing event", pending is not None and pending["eventType"] == "checkout_initiated")

    sub = service.activate_plan(org, "pro", amount=49.0, currency="USD", tx_ref="kulima-pro-tx1", event_type="link_payment")
    check("Success upgrades plan to pro + active", sub["plan"] == "pro" and sub["status"] == "active")
    status = service.billing_status(org)
    check("Org status refreshed: planName Professional", status["planName"] == "Professional", status["planName"])
    check("Renewal status available (period end set)", bool(status["periodEnd"]))
    events = repo.list_payment_events(org, limit=50)
    check("Payment history stores checkout + payment events",
          {"checkout_initiated", "link_payment"} <= {e["eventType"] for e in events},
          str(sorted({e["eventType"] for e in events})))

    # Idempotency of the return endpoint state (already-processed detection)
    success_event = repo.find_event_by_tx_ref("kulima-pro-tx1")
    check("Already-processed events are detectable",
          success_event["eventType"] in {"payment_success", "webhook_payment", "demo_payment", "link_payment"})

    # ── Phase 5 / failure handling ───────────────────────────────────────────
    failed_sub = service.handle_payment_failed(org, tx_ref="kulima-pro-tx2", reason="validation_failure")
    check("Failed payment → grace window", failed_sub["status"] == "grace" and bool(failed_sub.get("grace_until")))
    fstatus = service.billing_status(org)
    check("Failure surfaces in billing status (inGrace)", fstatus["inGrace"])
    repo.record_payment_event(org, "payment_cancelled", tx_ref="kulima-pro-tx3", plan="pro", status="cancelled")
    repo.record_payment_event(org, "payment_pending", tx_ref="kulima-pro-tx4", plan="pro", status="pending")
    ev_types = {e["eventType"] for e in repo.list_payment_events(org, limit=50)}
    check("Cancelled + Pending statuses storable in history",
          {"payment_cancelled", "payment_pending"} <= ev_types, str(sorted(ev_types)))

    service.reactivate(org)
    check("Recovery path: reactivate returns to active", service.billing_status(org)["status"] == "active")

    # ── Phase 2 / enforcement ────────────────────────────────────────────────
    os.environ["KULIMA_BILLING_ENFORCEMENT"] = "true"
    try:
        free_org = "validation-org-free"
        service.change_plan(free_org, "free", effective="immediate")
        check("Starter blocked from AI Analyst when enforcement is on",
              service.feature_check(free_org, "ask_ic")["allowed"] is False)
        check("Starter keeps Document Intelligence",
              service.feature_check(free_org, "document_intelligence")["allowed"] is True)
        check("Professional allows AI Analyst + Reports",
              service.feature_check(org, "ask_ic")["allowed"] and service.feature_check(org, "enterprise_reports")["allowed"])
        check("Starter quota is 3 (plan gate source)", get_plan("free").assessment_quota == 3)
        suspended = service.suspend(org, reason="validation")
        check("Suspension blocks new assessments", service.billing_status(org)["canAssess"] is False)
        try:
            service.assert_can_assess(org)
            check("assert_can_assess raises when suspended", False)
        except service.BillingBlocked as exc:
            check("assert_can_assess raises when suspended", exc.code == "ACCOUNT_SUSPENDED", exc.code)
        service.reactivate(org)
        try:
            service.assert_feature(org, "ask_ic")
            check("assert_feature passes for Professional AI Analyst", True)
        except service.BillingBlocked as exc:
            check("assert_feature passes for Professional AI Analyst", False, exc.code)
        check("is_upgrade(pro→enterprise) / is_downgrade(enterprise→free)",
              is_upgrade("pro", "enterprise") and is_downgrade("enterprise", "free"))
        del suspended
    finally:
        os.environ["KULIMA_BILLING_ENFORCEMENT"] = "false"

    # ── Phase 6 / admin visibility + router wiring ───────────────────────────
    from backend.app.routers import billing as billing_router  # noqa: E402

    paths = {r.path for r in billing_router.router.routes}
    check("Router exposes plans/status/history", {"/plans", "/status", "/history"} <= paths)
    check("Router exposes checkout + hosted-link return endpoint",
          {"/checkout", "/checkout/return", "/webhook", "/verify/{tx_ref}"} <= paths, str(sorted(paths)))
    status_fields = {"planName", "status", "periodEnd", "cancelAtPeriodEnd", "pendingPlan", "usage", "canAssess"}
    check("Status payload covers Current Plan / Billing Status / Renewal", status_fields <= set(status.keys()))
    check("History endpoint data source lists events", len(repo.list_payment_events(org, limit=100)) >= 5)

    # ── Phase 7 / frontend + env wiring (text checks) ────────────────────────
    fe = ROOT / "frontend"
    billing_page = (fe / "app" / "billing" / "page.tsx").read_text(encoding="utf-8")
    check("Billing page finalizes hosted-link returns", "returnFromCheckout" in billing_page)
    check("Billing page shows the four payment outcomes",
          all(word in billing_page for word in ("Payment Successful", "Payment Pending", "Payment Failed", "Payment Cancelled")))
    check("Billing page sends returnUrl for the redirect back", "returnUrl" in billing_page and "/billing" in billing_page)
    enterprise_lib = (fe / "lib" / "enterprise.ts").read_text(encoding="utf-8")
    check("Frontend API layer calls /checkout/return", "/api/v1/billing/checkout/return" in enterprise_lib)
    pricing_page_path = fe / "app" / "pricing" / "page.tsx"
    check("Public /pricing page exists", pricing_page_path.exists())
    if pricing_page_path.exists():
        pricing_page = pricing_page_path.read_text(encoding="utf-8")
        check("Pricing page lists Starter $0 / Professional $49 / Enterprise Custom",
              "'$0'" in pricing_page and "'$49'" in pricing_page and "Custom" in pricing_page)
        check("Pricing page references PayChangu links", "SC-GDDYA0" in pricing_page and "SC-MBXJF6" in pricing_page)
    landing = (fe / "app" / "page.tsx").read_text(encoding="utf-8")
    check("Landing PRICING aligned ($0 / $49/mo / Custom)",
          "'$0'" in landing and "$49/mo" in landing and "Custom" in landing)
    check("Landing links to /pricing", '"/pricing"' in landing)

    env_backend = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    check("backend/.env.example documents payment links + autoconfirm",
          all(k in env_backend for k in ("PAYCHANGU_LINK_PRO", "PAYCHANGU_LINK_ENTERPRISE", "KULIMA_BILLING_LINK_AUTOCONFIRM")))
    render_yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")
    check("render.yaml documents payment links for deployment",
          "SC-GDDYA0" in render_yaml and "SC-MBXJF6" in render_yaml)

    # ── Summary ──────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    print("\n" + "=" * 70)
    print(f"Billing validation: {passed}/{len(RESULTS)} passed, {failed} failed")
    if failed:
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  FAILED: {name} — {detail}")
        return 1
    print("PAYMENT_SYSTEM_COMPLETE")
    return 0


if __name__ == "__main__":
    code = main()
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass
    sys.exit(code)
