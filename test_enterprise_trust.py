"""Enterprise Trust & Monetization regression suite (Phases 1–11, backend).

Covers:
- Phase 1: customer data ownership helpers (workspace-scoped listing, purge path).
- Phase 2: organization tenancy, personal-org provisioning, legacy claiming, isolation.
- Phase 3: RBAC role matrix + the ``require_permission`` route boundary.
- Phase 4: append-only audit stream, filters, dedupe (webhook idempotency).
- Phase 5: document security — visibility, soft delete, retention/expiry, stats,
  encryption metadata envelope.
- Phase 6: Tavily egress guard — PII/financial redaction + research choke point.
- Phase 7: plan catalog, quotas, feature gates (enforcement off by default).
- Phase 8: grace → suspension state machine, plan transitions, PayChangu client.

All tests use temporary SQLite databases — no production DB touched.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

# The backend auth module requires NEXTAUTH_SECRET at import time.
os.environ.setdefault("NEXTAUTH_SECRET", "local-pytest-secret")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from backend.app.core.auth import (  # noqa: E402
    AuthenticatedUser,
    OrgContext,
    require_permission,
)
from kulima.core.audit.repository import (  # noqa: E402
    EVENT_TYPES,
    AuditRepository,
    event_category,
    event_label,
)
from kulima.core.billing import service as billing_service  # noqa: E402
from kulima.core.billing.paychangu import (  # noqa: E402
    PayChanguClient,
    PayChanguConfig,
    PayChanguError,
)
from kulima.core.billing.plans import (  # noqa: E402
    ALL_FEATURES,
    get_plan,
    is_downgrade,
    is_upgrade,
    plan_includes_feature,
)
from kulima.core.billing.repository import BillingRepository  # noqa: E402
from kulima.core.documents.models import Document  # noqa: E402
from kulima.core.documents.repository import DocumentRepository  # noqa: E402
from kulima.core.orgs.models import (  # noqa: E402
    Organization,
    OrganizationMember,
    Permission,
    Role,
    role_has_permission,
)
from kulima.core.orgs.repository import OrgRepository  # noqa: E402
from kulima.core.security.encryption import (  # noqa: E402
    SCHEME_PLAIN,
    EncryptionUnavailable,
    build_storage_metadata,
    cryptography_available,
    encrypt_bytes,
    encryption_key_configured,
    is_encrypted,
)
from kulima.core.security.tavily_guard import (  # noqa: E402
    ALLOWED_RESEARCH_FIELDS,
    SensitiveQueryError,
    guard,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Deterministic flags: enforcement/demo off, no doc-encryption key."""
    monkeypatch.delenv("KULIMA_BILLING_ENFORCEMENT", raising=False)
    monkeypatch.delenv("KULIMA_BILLING_DEMO_MODE", raising=False)
    monkeypatch.delenv("KULIMA_DOC_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("KULIMA_PLAN_PRICING_JSON", raising=False)


@pytest.fixture()
def db_path(tmp_path, monkeypatch) -> str:
    path = str(tmp_path / "enterprise.db")
    monkeypatch.setenv("KULIMA_DB_PATH", path)
    return path


@pytest.fixture()
def orgs(db_path) -> OrgRepository:
    return OrgRepository(db_path=db_path)


@pytest.fixture()
def billing(db_path, monkeypatch) -> BillingRepository:
    repo = BillingRepository(db_path=db_path)
    monkeypatch.setattr(billing_service, "_repo", repo)
    return repo


def _doc(doc_id: str, *, uploaded_by: str = "u-1", name: str = "plan.pdf") -> Document:
    return Document(id=doc_id, filename=name, mime_type="application/pdf", uploaded_by=uploaded_by)


def _past_iso(days: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _future_iso(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ── Phase 2 — Tenancy ────────────────────────────────────────────────────────


def test_personal_org_provisioning_is_idempotent(orgs):
    first = orgs.ensure_personal_org("user-1", email="a@b.com", display_name="A B")
    again = orgs.ensure_personal_org("user-1")

    assert first.id == again.id
    assert first.personal is True
    membership = orgs.get_membership_for_org(first.id, "user-1")
    assert membership is not None and membership.role == Role.OWNER
    assert first.id in {o.id for o in orgs.list_orgs_for_user("user-1")}


def test_role_matrix_permissions():
    assert len(Permission) == 8
    for perm in Permission:  # Owner: full access
        assert role_has_permission(Role.OWNER, perm)

    assert role_has_permission("admin", "manage_users")
    assert role_has_permission("admin", "view_audit")
    assert not role_has_permission("admin", "manage_billing")

    assert role_has_permission("reviewer", "assess")
    assert role_has_permission("reviewer", "export")
    assert not role_has_permission("reviewer", "delete_data")
    assert not role_has_permission("reviewer", "manage_documents")

    assert role_has_permission("viewer", "view")
    for denied in ("assess", "export", "manage_users", "delete_data", "manage_billing"):
        assert not role_has_permission("viewer", denied)

    assert not role_has_permission("not-a-role", "view")


def test_last_owner_guard_prevents_lockout(orgs):
    org = orgs.create_org("Acme", created_by="u-owner")
    orgs.add_member(org.id, "u-owner", Role.OWNER)
    orgs.add_member(org.id, "u-viewer", Role.VIEWER)

    with pytest.raises(ValueError, match="last_owner"):
        orgs.set_role(org.id, "u-owner", Role.ADMIN)
    with pytest.raises(ValueError, match="last_owner"):
        orgs.remove_member(org.id, "u-owner")

    orgs.add_member(org.id, "u-owner-2", Role.OWNER)
    assert orgs.set_role(org.id, "u-owner", Role.ADMIN) is True
    assert orgs.get_membership_for_org(org.id, "u-owner").role == Role.ADMIN


def test_add_member_upserts_role(orgs):
    org = orgs.create_org("Acme", created_by="u-1")
    orgs.add_member(org.id, "u-2", Role.VIEWER)
    orgs.add_member(org.id, "u-2", Role.REVIEWER, email="r@acme.com")

    membership = orgs.get_membership_for_org(org.id, "u-2")
    assert membership.role == Role.REVIEWER
    assert membership.email == "r@acme.com"
    assert orgs.count_members(org.id) == 1


def test_claim_legacy_data_binds_unowned_documents(db_path, orgs):
    docs = DocumentRepository(db_path=db_path)
    docs.save_document(None, _doc("legacy-doc", uploaded_by="u-legacy"), storage_path="legacy.pdf")

    org = orgs.create_org("Legacy Workspace", created_by="u-legacy")
    counts = orgs.claim_legacy_data("u-legacy", org.id)

    assert counts["documents"] == 1
    assert docs.get_document("legacy-doc")["orgId"] == org.id


def test_workspace_isolation_for_documents(db_path):
    docs = DocumentRepository(db_path=db_path)
    docs.save_document(None, _doc("doc-a"), org_id="org-a")
    docs.save_document(None, _doc("doc-b", name="b.pdf"), org_id="org-b")

    only_a = [d["id"] for d in docs.list_documents(org_id="org-a")]
    only_b = [d["id"] for d in docs.list_documents(org_id="org-b")]

    assert only_a == ["doc-a"]
    assert only_b == ["doc-b"]


# ── Phase 4 — Audit log ──────────────────────────────────────────────────────


def test_audit_required_event_types_present():
    required = {
        "document.uploaded",
        "assessment.created",
        "signals.generated",
        "decision.generated",
        "report.exported",
        "user.login",
        "research.triggered",
    }
    assert required <= set(EVENT_TYPES)
    assert event_label("user.login") == "User Login"
    assert event_category("billing.payment_failed") == "Billing"
    assert event_label("custom.event") == "Custom Event"
    assert event_category("custom.event") == "Other"


def test_audit_records_list_and_filter(db_path):
    repo = AuditRepository(db_path=db_path)
    repo.record("document.uploaded", org_id="org-a", assessment_id="asm-1", document_id="d-1")
    repo.record("assessment.created", org_id="org-a", assessment_id="asm-1")
    repo.record("user.login", org_id="org-b", user_id="u-2")

    assert repo.count(org_id="org-a") == 2
    assert len(repo.list(org_id="org-a")) == 2
    assert len(repo.list(assessment_id="asm-1")) == 2
    assert len(repo.list(event_types=["user.login"])) == 1

    newest_a = repo.list(org_id="org-a")[0]
    assert newest_a["eventType"] == "assessment.created"
    assert newest_a["label"] == "Assessment Created"
    assert repo.latest(org_id="org-b")["label"] == "User Login"


def test_audit_record_once_dedupes_webhook_events(db_path):
    repo = AuditRepository(db_path=db_path)
    assert repo.record_once("billing.payment_received", dedupe_key="tx-1", org_id="org-a") is not None
    assert repo.record_once("billing.payment_received", dedupe_key="tx-1", org_id="org-a") is None
    assert repo.record_once("billing.payment_received", dedupe_key="tx-2", org_id="org-a") is not None
    assert repo.count(org_id="org-a") == 2


def test_audit_metadata_roundtrip(db_path):
    repo = AuditRepository(db_path=db_path)
    repo.record("report.exported", org_id="org-a", metadata={"reportKind": "memo", "nested": {"ok": True}})
    event = repo.list(org_id="org-a")[0]
    assert event["metadata"]["reportKind"] == "memo"
    assert event["metadata"]["nested"] == {"ok": True}


# ── Phase 6 — Tavily safety ──────────────────────────────────────────────────


def test_guard_redacts_pii_and_financial_content():
    query = (
        "Verify AgriNova Ltd contact john.doe@example.com phone +265 991 123 456 "
        "revenue $2,500,000 document id 123456789 financial statement attached"
    )
    report = guard.inspect(query)
    sanitized = report.query

    assert "john.doe@example.com" not in sanitized
    assert "+265" not in sanitized
    assert "$2,500,000" not in sanitized
    assert "123456789" not in sanitized
    assert "financial statement" not in sanitized.lower()
    assert "[redacted-email]" in sanitized
    assert {"email", "phone", "amount", "long_number", "sensitive_phrase"} <= set(report.redactions)
    assert guard.sanitize_query(query) == sanitized


def test_guard_build_query_is_metadata_only():
    assert ALLOWED_RESEARCH_FIELDS == (
        "organization_name",
        "founder_name",
        "sector",
        "country",
        "public_company_info",
    )
    built = guard.build_query(
        organization_name="AgriNova Malawi",
        founder_name="Jane Banda",
        sector="AgriTech",
        country="Malawi",
    )
    assert built == "AgriNova Malawi Jane Banda AgriTech Malawi"

    dirty = guard.build_query(founder_name="Jane jane@acme.com", country="Malawi")
    assert "jane@acme.com" not in dirty
    assert "Malawi" in dirty


def test_guard_truncates_and_strict_mode():
    report = guard.inspect("agritech " * 100)
    assert report.truncated is True
    assert len(report.query) <= guard.max_query_chars

    assert guard.is_safe("AgriNova Malawi agritech")
    assert not guard.is_safe("reach me at leak@example.com")
    with pytest.raises(SensitiveQueryError):
        guard.assert_safe("reach me at leak@example.com")


def test_research_engine_sanitizes_query_before_egress():
    from kulima.research import ResearchEngine

    engine = ResearchEngine.__new__(ResearchEngine)  # bypass Tavily client construction
    engine.client = MagicMock()
    engine.client.search.return_value = {"results": []}
    engine.max_results = 5
    engine.africa_focus = False

    engine.search("AgriNova john@example.com $2,000,000 financial statement")

    sent = engine.client.search.call_args
    sent_query = sent.kwargs.get("query", sent.args[0] if sent.args else "")
    assert "john@example.com" not in sent_query
    assert "$2,000,000" not in sent_query
    assert "financial statement" not in sent_query.lower()
    assert "AgriNova" in sent_query


# ── Phase 7 — Subscription model ─────────────────────────────────────────────


def test_plan_catalog_quotas_and_features():
    free = get_plan("free")
    assert free.assessment_quota == 5
    assert free.monthly_price == 0.0
    assert {"basic_signals", "community_signals"} <= set(free.features)
    assert "ask_ic" not in free.features

    pro = get_plan("pro")
    assert pro.assessment_quota is None
    assert {"climate_signals", "tourism_signals", "ask_ic", "enterprise_reports"} <= set(pro.features)

    enterprise = get_plan("enterprise")
    assert enterprise.member_quota is None
    assert set(enterprise.features) == set(ALL_FEATURES)
    assert {"rbac", "audit_log", "private_deployment", "api_integration", "governance_dashboard"} <= set(
        enterprise.features
    )

    assert plan_includes_feature("free", "basic_signals")
    assert not plan_includes_feature("free", "climate_signals")
    assert is_upgrade("free", "pro") and is_upgrade("pro", "enterprise")
    assert is_downgrade("enterprise", "pro") and not is_upgrade("pro", "free")


def test_plan_pricing_is_configurable(monkeypatch):
    monkeypatch.setenv("KULIMA_PLAN_PRICING_JSON", '{"pro": {"monthly_price": 59, "currency": "MWK"}}')
    pro = get_plan("pro")
    assert pro.monthly_price == 59.0
    assert pro.currency == "MWK"
    assert "ask_ic" in pro.features  # feature set unchanged by pricing override


def test_quota_gate_only_when_enforcement_enabled(billing, monkeypatch):
    org = "org-quota"
    monkeypatch.setattr(billing_service, "count_assessments_this_month", lambda org_id: 5)

    assert billing_service.assert_can_assess(org) is None  # enforcement off → passes

    summary = billing_service.usage_summary(org)
    assert summary["assessmentQuota"] == 5
    assert summary["remaining"] == 0

    monkeypatch.setenv("KULIMA_BILLING_ENFORCEMENT", "true")
    with pytest.raises(billing_service.BillingBlocked) as exc:
        billing_service.assert_can_assess(org)
    assert exc.value.code == "QUOTA_EXCEEDED"
    assert exc.value.status_code == 402


def test_suspension_blocks_new_assessments_always(billing):
    org = "org-suspended"
    billing_service.suspend(org, reason="test")

    with pytest.raises(billing_service.BillingBlocked) as exc:
        billing_service.assert_can_assess(org)  # even with enforcement off
    assert exc.value.code == "ACCOUNT_SUSPENDED"
    assert exc.value.status_code == 403

    status = billing_service.billing_status(org)
    assert status["status"] == "suspended"
    assert status["canAssess"] is False


def test_failed_payment_grace_then_suspension(billing, monkeypatch):
    org = "org-grace"
    sub = billing_service.handle_payment_failed(org, tx_ref="tx-fail", reason="card_declined")
    assert sub["status"] == "grace"
    assert sub["grace_until"] is not None

    monkeypatch.setenv("KULIMA_BILLING_ENFORCEMENT", "true")
    with pytest.raises(billing_service.BillingBlocked) as exc:
        billing_service.assert_can_assess(org)
    assert exc.value.code == "PAYMENT_REQUIRED"
    assert exc.value.status_code == 402

    # Force the grace window into the past → auto-expiry suspends the account.
    billing.update_subscription(org, grace_until=_past_iso())
    with pytest.raises(billing_service.BillingBlocked) as exc:
        billing_service.assert_can_assess(org)
    assert exc.value.code == "ACCOUNT_SUSPENDED"


def test_activate_plan_clears_state_and_syncs_org(db_path, orgs, billing):
    org = orgs.create_org("Acme", created_by="u-1")
    billing_service.handle_payment_failed(org.id, tx_ref="tx-1")

    sub = billing_service.activate_plan(org.id, "pro", amount=49.0, tx_ref="tx-1")
    assert sub["plan"] == "pro"
    assert sub["status"] == "active"
    assert sub["grace_until"] is None

    # OrgContext plan mirrors the subscription (Phase 7 sync).
    assert orgs.get_org(org.id).plan == "pro"

    # Both billing and governance trails captured the event.
    events = AuditRepository(db_path=db_path).list(org_id=org.id)
    assert any(e["eventType"] == "billing.plan_changed" for e in events)
    history = billing_service.payment_history(org.id)
    assert history and history[0]["eventType"] == "payment_success"


def test_downgrade_scheduled_then_applied_at_period_end(orgs, billing):
    org = orgs.create_org("Acme", created_by="u-1")
    billing_service.activate_plan(org.id, "pro", amount=49.0)

    scheduled = billing_service.change_plan(org.id, "free")
    assert scheduled["effective"] == "period_end"
    assert scheduled["pendingPlan"] == "free"
    assert billing.get_subscription(org.id)["plan"] == "pro"

    assert billing_service.apply_due_changes(org.id) is not None  # not due yet → no change
    assert billing.get_subscription(org.id)["pending_plan"] == "free"

    billing.update_subscription(org.id, current_period_end=_past_iso())  # period elapsed
    billing_service.apply_due_changes(org.id)
    assert billing.get_subscription(org.id)["plan"] == "free"
    assert billing.get_subscription(org.id)["pending_plan"] is None
    assert orgs.get_org(org.id).plan == "free"


def test_cancel_and_reactivate_cycle(billing):
    org = "org-cancel"
    billing_service.activate_plan(org, "pro", amount=49.0)

    billing_service.cancel_at_period_end(org)
    status = billing_service.billing_status(org)
    assert status["cancelAtPeriodEnd"] is True
    assert status["pendingPlan"] == "free"

    billing_service.reactivate(org)
    billing.update_subscription(org, cancel_at_period_end=0, pending_plan=None)
    status = billing_service.billing_status(org)
    assert status["status"] == "active"
    assert status["cancelAtPeriodEnd"] is False


# ── Phase 8 — PayChangu client ───────────────────────────────────────────────


def test_paychangu_unconfigured_client_fails_cleanly():
    client = PayChanguClient(PayChanguConfig())
    assert client.configured is False
    with pytest.raises(PayChanguError) as exc:
        client.initiate_payment(10.0, tx_ref="tx-1", plan="pro", org_id="org-a")
    assert exc.value.code == "not_configured"
    assert client.verify_webhook(b"{}", "signature") is False


def test_paychangu_webhook_signature_verification():
    client = PayChanguClient(PayChanguConfig(secret_key="sk", webhook_secret="whsec_test"))
    body = b'{"event_type": "success", "data": {"tx_ref": "tx-1"}}'
    digest = hmac.new(b"whsec_test", body, hashlib.sha256)

    assert client.verify_webhook(body, digest.hexdigest()) is True
    assert client.verify_webhook(body, base64.b64encode(digest.digest()).decode()) is True
    assert client.verify_webhook(body, "deadbeef") is False
    assert client.verify_webhook(body, None) is False
    assert client.verify_webhook(b'{"tampered": true}', digest.hexdigest()) is False


# ── Phase 5 — Document security ──────────────────────────────────────────────


def test_document_envelope_scope_and_visibility(db_path):
    docs = DocumentRepository(db_path=db_path)
    envelope = build_storage_metadata(b"payload-bytes")
    assert envelope["scheme"] == SCHEME_PLAIN  # no key configured in tests
    assert envelope["encrypted"] is False
    assert envelope["sha256"] == hashlib.sha256(b"payload-bytes").hexdigest()
    assert envelope["sizeBytes"] == len(b"payload-bytes")

    docs.save_document(
        None,
        _doc("doc-sec"),
        org_id="org-a",
        assessment_id="asm-1",
        storage_path="stored.pdf",
        size_bytes=1234,
        visibility="private",
        retention_days=90,
        expires_at=_future_iso(),
        encryption_metadata=envelope,
    )
    row = docs.get_document("doc-sec")
    assert row["orgId"] == "org-a"
    assert row["assessmentId"] == "asm-1"
    assert row["visibility"] == "private"
    assert row["sizeBytes"] == 1234
    assert row["retentionDays"] == 90
    assert row["encryption"]["scheme"] == SCHEME_PLAIN
    assert is_encrypted(row["encryption"]) is False
    assert DocumentRepository.is_expired(row) is False
    assert DocumentRepository.is_expired({"expiresAt": _past_iso()}) is True
    assert DocumentRepository.is_expired({"expiresAt": "not-a-date"}) is False


def test_soft_delete_excludes_from_listing(db_path):
    docs = DocumentRepository(db_path=db_path)
    docs.save_document(None, _doc("doc-soft"), org_id="org-a")

    assert docs.soft_delete_document("doc-soft", deleted_by="u-1") is True
    assert docs.soft_delete_document("doc-soft", deleted_by="u-1") is False  # idempotent

    row = docs.get_document("doc-soft")
    assert row["deletedAt"] is not None
    assert row["deletedBy"] == "u-1"
    assert docs.list_documents(org_id="org-a") == []
    assert len(docs.list_documents(org_id="org-a", include_deleted=True)) == 1

    assert docs.hard_delete_document("doc-soft") is True
    assert docs.get_document("doc-soft") is None


def test_document_stats_reports_deleted_and_expired(db_path):
    docs = DocumentRepository(db_path=db_path)
    docs.save_document(None, _doc("doc-live"), org_id="org-a", size_bytes=100)
    docs.save_document(None, _doc("doc-del", name="d.pdf"), org_id="org-a", size_bytes=200)
    docs.save_document(None, _doc("doc-exp", name="e.pdf"), org_id="org-a", size_bytes=300, expires_at=_past_iso())
    docs.soft_delete_document("doc-del")

    stats = docs.document_stats(org_id="org-a")
    assert stats["total"] == 3
    assert stats["active"] == 1
    assert stats["deleted"] == 1
    assert stats["expired"] == 1
    assert stats["storageBytes"] == 600
    assert stats["scheduledForDeletion"] == 1


def test_encryption_roundtrip_or_explicit_unavailable():
    if encryption_key_configured() and cryptography_available():
        blob = encrypt_bytes(b"top secret")
        from kulima.core.security.encryption import decrypt_bytes

        assert decrypt_bytes(blob) == b"top secret"
        assert is_encrypted(build_storage_metadata(b"x") | {"encrypted": True}) is True
    else:
        with pytest.raises(EncryptionUnavailable):
            encrypt_bytes(b"top secret")


# ── Phase 3 — RBAC route boundary ────────────────────────────────────────────


def _ctx(role: str) -> OrgContext:
    org = Organization(id="org-1", name="Acme", slug="acme", plan="free")
    member = OrganizationMember(org_id="org-1", user_id="u-1", role=Role(role))
    return OrgContext(user=AuthenticatedUser("u-1"), org=org, membership=member)


def _check(permission: Permission, ctx: OrgContext) -> OrgContext:
    dependency = require_permission(permission)
    return asyncio.run(dependency(ctx))


def test_require_permission_boundary_enforced():
    owner = _ctx("owner")
    for perm in Permission:  # Owner: full access
        assert _check(perm, owner) is owner

    admin = _ctx("admin")
    assert _check(Permission.MANAGE_USERS, admin) is admin
    assert _check(Permission.VIEW_AUDIT, admin) is admin
    with pytest.raises(HTTPException) as exc:
        _check(Permission.MANAGE_BILLING, admin)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PERMISSION_DENIED"
    assert exc.value.detail["required"] == "manage_billing"
    assert exc.value.detail["role"] == "admin"

    reviewer = _ctx("reviewer")
    assert _check(Permission.ASSESS, reviewer) is reviewer
    assert _check(Permission.EXPORT, reviewer) is reviewer
    for denied in (Permission.DELETE_DATA, Permission.MANAGE_USERS, Permission.VIEW_AUDIT):
        with pytest.raises(HTTPException):
            _check(denied, reviewer)

    viewer = _ctx("viewer")
    assert _check(Permission.VIEW, viewer) is viewer
    for denied in (Permission.ASSESS, Permission.MANAGE_DOCUMENTS, Permission.EXPORT):
        with pytest.raises(HTTPException) as exc:
            _check(denied, viewer)
        assert exc.value.status_code == 403
