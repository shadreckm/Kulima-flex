"""Billing & access-control validation (Free / Professional / Enterprise).

Run from the repo root:

    python scripts/validate_billing.py

Covers:
  Phase 1  plan catalog (Free $0 · 3 assessments · 1 user · 30-day history /
           Professional $49 unlocks / Enterprise Custom + approval + $250 min)
  Phase 2  plan enforcement (quota + feature gates, suspension)
  Phase 3  PayChangu hosted links (SC-GDDYA0 / SC-MBXJF6) + checkout routing
           + Enterprise activation lifecycle (request → agree → activate)
  Phase 4  success handling (activate plan, org sync, billing event, renewal,
           session refresh wiring)
  Phase 5  failure handling + feature-gate audit (report kinds, research,
           conversations, collaboration, signals)
  Phase 6  admin visibility (status payload fields, payment history,
           Payment Status)
  Phase 7  validation of all plans + wiring checks (router endpoints,
           frontend pages, env examples)

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

    check("Free plan is named 'Free' and costs $0", starter.name == "Free" and starter.monthly_price == 0.0, starter.name)
    check("Free quota = 3 assessments", starter.assessment_quota == 3, str(starter.assessment_quota))
    check("Free is a single-user plan", starter.member_quota == 1, str(starter.member_quota))
    check("Free is not a paid plan", not starter.is_paid)
    check("Free has Document Intelligence Mode", "document_intelligence" in starter.features)
    check("Free has basic reports + basic signals + community signals",
          {"basic_reports", "basic_signals", "community_signals"} <= starter.features)
    check("Free assessment history window is 30 days", starter.history_window_days == 30, str(starter.history_window_days))
    check("Free lacks Conversation history + Research Intelligence",
          not {"conversation_history", "research_intelligence"} & starter.features)

    check("Professional is named 'Professional'", pro.name == "Professional", pro.name)
    check("Professional is $49/month", pro.monthly_price == 49.0 and pro.display_price.endswith("49/month"), pro.display_price)
    check("Professional is unlimited assessments", pro.assessment_quota is None)
    check("Professional is unlimited history", pro.history_window_days is None)
    check("Professional has AI Analyst / Reports / history / collaboration / priority support",
          {"ask_ic", "enterprise_reports", "assessment_history", "collaboration", "priority_support"} <= pro.features)
    check("Professional unlocks Conversation history + Research Intelligence + advanced signals",
          {"conversation_history", "research_intelligence", "climate_signals", "tourism_signals"} <= pro.features)
    check("Professional is paid", pro.is_paid)

    check("Enterprise price shows 'Custom'", ent.price_label == "Custom" and ent.display_price == "Custom", ent.display_price)
    check("Enterprise is treated as PAID despite Custom price", ent.is_paid)
    check("Enterprise requires organization approval + custom agreement", ent.requires_approval is True)
    check("Enterprise minimum onboarding value is $250 equivalent", ent.minimum_value_usd == 250.0, str(ent.minimum_value_usd))
    check("Enterprise has RBAC / audit / multi-org / API / custom reports / dedicated workspace",
          {"rbac", "audit_log", "multiple_organizations", "api_integration", "custom_reports", "dedicated_workspace", "custom_integrations"} <= ent.features)
    check("Enterprise has Trust & Governance Dashboard + advanced tourism/climate intelligence",
          {"governance_dashboard", "tourism_signals", "climate_signals"} <= ent.features)

    check("Feature relabel: ask_ic → 'AI Analyst'", FEATURE_LABELS.get("ask_ic") == "AI Analyst")
    check("Feature relabel: enterprise_reports → 'Reports'", FEATURE_LABELS.get("enterprise_reports") == "Reports")
    check("Feature labels cover the unlock lists",
          FEATURE_LABELS.get("research_intelligence") == "Research Intelligence"
          and FEATURE_LABELS.get("conversation_history") == "Conversation history"
          and FEATURE_LABELS.get("api_integration") == "API Access"
          and FEATURE_LABELS.get("custom_reports") == "Custom Reports"
          and FEATURE_LABELS.get("dedicated_workspace") == "Dedicated Workspace"
          and FEATURE_LABELS.get("multiple_organizations") == "Multi-Organization Support",
          str(FEATURE_LABELS))
    check("Catalog has exactly Free/Professional/Enterprise",
          [p.name for p in all_plans()] == ["Free", "Professional", "Enterprise"],
          str([p.name for p in all_plans()]))

    payload = plan_catalog_payload("free")
    by_id = {p["planId"]: p for p in payload["plans"]}
    check("API payload exposes paymentLink", by_id["pro"]["paymentLink"].endswith("SC-GDDYA0") and by_id["enterprise"]["paymentLink"].endswith("SC-MBXJF6"))
    check("API payload exposes isPaid / priceLabel", by_id["free"]["isPaid"] is False and by_id["enterprise"]["priceLabel"] == "Custom")
    check("API payload exposes history + approval fields",
          by_id["free"]["historyWindowDays"] == 30 and "30 days" in by_id["free"]["historyLabel"]
          and by_id["pro"]["historyWindowDays"] is None
          and by_id["enterprise"]["requiresApproval"] is True and by_id["enterprise"]["minimumValueUsd"] == 250.0)

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
        check("Free plan blocked from AI Analyst when enforcement is on",
              service.feature_check(free_org, "ask_ic")["allowed"] is False)
        check("Free plan keeps Document Intelligence",
              service.feature_check(free_org, "document_intelligence")["allowed"] is True)
        check("Professional allows AI Analyst + Reports",
              service.feature_check(org, "ask_ic")["allowed"] and service.feature_check(org, "enterprise_reports")["allowed"])
        check("Free plan history window is 30 days (enforced)",
              service.assessment_history_window_days(free_org) == 30,
              str(service.assessment_history_window_days(free_org)))
        check("Professional history is unlimited",
              service.assessment_history_window_days(org) is None,
              str(service.assessment_history_window_days(org)))
        check("Free plan gated on Conversation history + Research Intelligence",
              service.feature_check(free_org, "conversation_history")["allowed"] is False
              and service.feature_check(free_org, "research_intelligence")["allowed"] is False)
        check("Professional allowed on Conversation history + Research Intelligence + Collaboration",
              service.feature_check(org, "conversation_history")["allowed"]
              and service.feature_check(org, "research_intelligence")["allowed"]
              and service.feature_check(org, "collaboration")["allowed"])
        check("Free plan gated on Collaboration (multi-user)",
              service.feature_check(free_org, "collaboration")["allowed"] is False)
        check("Free plan gated on basic reports; Professional on custom reports",
              service.feature_check(free_org, "basic_reports")["allowed"]
              and service.feature_check(free_org, "custom_reports")["allowed"] is False
              and service.feature_check(org, "custom_reports")["allowed"] is False)
        check("API Access gated to Enterprise",
              service.feature_check(org, "api_integration")["allowed"] is False)
        check("Free quota is 3 (plan gate source)", get_plan("free").assessment_quota == 3)
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

    # ── Phase 3 / Enterprise activation lifecycle ────────────────────────────
    ent_org = "validation-org-ent"
    check("New org starts with no activation state", service.enterprise_activation_status(ent_org) is None)
    check("Enterprise checkout is gated before approval", service.enterprise_checkout_allowed(ent_org) is False)
    service.request_enterprise_activation(ent_org, org_name="Validation Enterprise", contact="ops@validation.test")
    check("Request moves activation to 'requested'",
          service.enterprise_activation_status(ent_org) == service.ACTIVATION_REQUESTED,
          str(service.enterprise_activation_status(ent_org)))
    check("Checkout still gated while only requested", service.enterprise_checkout_allowed(ent_org) is False)
    try:
        service.approve_enterprise_activation(ent_org, agreement_accepted=False)
        check("Approval without the custom agreement raises", False)
    except ValueError as exc:
        check("Approval without the custom agreement raises", str(exc) == "agreement_required", str(exc))
    service.approve_enterprise_activation(ent_org, agreement_accepted=True)
    check("Approval moves activation to 'approved'",
          service.enterprise_activation_status(ent_org) == service.ACTIVATION_APPROVED,
          str(service.enterprise_activation_status(ent_org)))
    check("Checkout unlocked after organization approval", service.enterprise_checkout_allowed(ent_org) is True)
    ent_sub = service.activate_plan(ent_org, "enterprise", amount=250.0, currency="USD",
                                    tx_ref="kulima-ent-tx1", event_type="link_payment")
    check("Payment success completes Enterprise activation",
          ent_sub["plan"] == "enterprise" and ent_sub["activation_state"] == service.ACTIVATION_ACTIVATED,
          str(ent_sub.get("activation_state")))
    ent_status = service.billing_status(ent_org)
    check("Enterprise activation events persisted in history",
          {"enterprise_activation_requested", "enterprise_agreement_approved", "link_payment"}
          <= {e["eventType"] for e in repo.list_payment_events(ent_org, limit=50)},
          str(sorted({e["eventType"] for e in repo.list_payment_events(ent_org, limit=50)})))
    check("Professional org without agreement is also gated for Enterprise",
          service.enterprise_checkout_allowed(org) is False)
    pro_sub = service.activate_plan(org, "pro", amount=49.0, currency="USD",
                                    tx_ref="kulima-pro-tx5", event_type="link_payment")
    check("activate_plan clears activation_state for non-approval plans", pro_sub.get("activation_state") is None)

    # ── Phase 6 / Payment Status (admin visibility) ──────────────────────────
    latest = service.latest_payment_status(org)
    check("latest_payment_status returns the most recent money event",
          latest is not None and latest["eventType"] == "link_payment" and latest["txRef"] == "kulima-pro-tx5",
          str(latest))
    check("Status payload exposes Payment Status + activation fields",
          {"requiresApproval", "minimumValueUsd", "activationState", "historyWindowDays", "latestPayment"} <= set(latest_status_keys := service.billing_status(org).keys()),
          str(sorted(latest_status_keys)))
    del ent_status  # informational only

    # ── Phase 5 / report-kind tiers ──────────────────────────────────────────
    from backend.app.routers.intelligence import _BASIC_REPORT_KINDS, _ENTERPRISE_REPORT_KINDS  # noqa: E402

    check("High-tier report kinds gated by enterprise_reports",
          _ENTERPRISE_REPORT_KINDS == {"report", "due-diligence", "signals"}, str(sorted(_ENTERPRISE_REPORT_KINDS)))
    check("Basic report kinds gated by basic_reports",
          _BASIC_REPORT_KINDS == {"memo", "one-pager"}, str(sorted(_BASIC_REPORT_KINDS)))

    # ── Phase 6 / admin visibility + router wiring ───────────────────────────
    from backend.app.routers import billing as billing_router  # noqa: E402

    paths = {r.path for r in billing_router.router.routes}
    check("Router exposes plans/status/history", {"/plans", "/status", "/history"} <= paths)
    check("Router exposes checkout + hosted-link return endpoint",
          {"/checkout", "/checkout/return", "/webhook", "/verify/{tx_ref}"} <= paths, str(sorted(paths)))
    check("Router exposes the Enterprise activation endpoints",
          {"/enterprise/activation", "/enterprise/activation/request", "/enterprise/activation/approve"} <= paths,
          str(sorted(paths)))
    billing_src = Path(billing_router.__file__).read_text(encoding="utf-8")
    check("Checkout + downgrade + confirm enforce ENTERPRISE_ACTIVATION_REQUIRED",
          billing_src.count("ENTERPRISE_ACTIVATION_REQUIRED") >= 3,
          str(billing_src.count("ENTERPRISE_ACTIVATION_REQUIRED")))
    status_fields = {"planName", "status", "periodEnd", "cancelAtPeriodEnd", "pendingPlan", "usage", "canAssess"}
    check("Status payload covers Current Plan / Billing Status / Renewal / Payment Status",
          status_fields <= set(status.keys()))
    check("History endpoint data source lists events", len(repo.list_payment_events(org, limit=100)) >= 5)

    # ── Phase 7 / frontend + env wiring (text checks) ────────────────────────
    fe = ROOT / "frontend"
    billing_page = (fe / "app" / "billing" / "page.tsx").read_text(encoding="utf-8")
    check("Billing page finalizes hosted-link returns", "returnFromCheckout" in billing_page)
    check("Billing page shows the four payment outcomes",
          all(word in billing_page for word in ("Payment Successful", "Payment Pending", "Payment Failed", "Payment Cancelled")))
    check("Billing page sends returnUrl for the redirect back", "returnUrl" in billing_page and "/billing" in billing_page)
    check("Billing page renders the Payment Status admin view",
          "Payment Status:" in billing_page and "latestPayment" in billing_page)
    check("Billing page hosts the Enterprise agreement flow",
          all(token in billing_page for token in (
              "approveEnterpriseActivation", "agreementChecked", "ENTERPRISE_ACTIVATION_REQUIRED",
              "custom Enterprise agreement", "Activation requested")))
    check("Phase 4: successful payment refreshes the session", "refreshSession" in billing_page)
    enterprise_lib = (fe / "lib" / "enterprise.ts").read_text(encoding="utf-8")
    check("Frontend API layer calls /checkout/return", "/api/v1/billing/checkout/return" in enterprise_lib)
    check("Frontend API layer exposes Enterprise activation calls",
          all(token in enterprise_lib for token in (
              "/api/v1/billing/enterprise/activation", "/api/v1/billing/enterprise/activation/request",
              "/api/v1/billing/enterprise/activation/approve", "latestPayment", "activationState")))
    pricing_page_path = fe / "app" / "pricing" / "page.tsx"
    check("Public /pricing page exists", pricing_page_path.exists())
    if pricing_page_path.exists():
        pricing_page = pricing_page_path.read_text(encoding="utf-8")
        check("Pricing page lists Free $0 / Professional $49 / Enterprise Custom",
              "'$0'" in pricing_page and "'$49'" in pricing_page and "Custom" in pricing_page)
        check("Pricing page references PayChangu links", "SC-GDDYA0" in pricing_page and "SC-MBXJF6" in pricing_page)
        check("Pricing page shows Phase 1/2/3 items",
              all(token in pricing_page for token in (
                  "Assessment history (30 days)", "Research Intelligence", "Conversation history",
                  "$250 equivalent", "Enterprise activation workflow", "Trust & Governance Dashboard")))
    landing = (fe / "app" / "page.tsx").read_text(encoding="utf-8")
    check("Landing PRICING aligned ($0 / $49/mo / Custom)",
          "'$0'" in landing and "$49/mo" in landing and "Custom" in landing)
    check("Landing links to /pricing", '"/pricing"' in landing)
    check("Landing copy covers the new unlock lists",
          "30-day assessment history" in landing and "Research Intelligence" in landing
          and "conversation history" in landing and "$250 equivalent" in landing)

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
    print("SUBSCRIPTION_SYSTEM_READY")
    return 0


if __name__ == "__main__":
    code = main()
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass
    sys.exit(code)
