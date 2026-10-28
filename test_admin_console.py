"""Admin Console — the operator gate and its read-only surfaces.

These tests are the contract for the part of Kulima that reads *across*
every workspace:

  * the console is unreachable unless an operator is configured (fail-closed);
  * an organization role — even Owner — never grants it;
  * database rows an organization can write (member email, display name) never
    grant it either, so a customer cannot invite themselves into the console;
  * every section here only reads, and the only write is the audit entry that an
    operator looked.

The stored PLATFORM_ADMIN role and the console's mutation surface are covered in
``test_platform_admin_role.py``; this file keeps the read contract honest, using
the break-glass environment path where the role store is deliberately empty.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The backend auth module requires NEXTAUTH_SECRET at import time.
os.environ.setdefault("NEXTAUTH_SECRET", "local-pytest-secret")

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.core import admin_access  # noqa: E402
from backend.app.core import auth as auth_module  # noqa: E402
from backend.app.core.auth import AuthenticatedUser, OrgContext  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.services.conversation_repository import ConversationRepository  # noqa: E402
from kulima.config import get_settings  # noqa: E402
from kulima.core.assessment.repository import AssessmentRepository  # noqa: E402
from kulima.core.audit.repository import AuditRepository, EVENT_TYPES, record_event  # noqa: E402
from kulima.core.billing.repository import BillingRepository  # noqa: E402
from kulima.core.orgs import platform_admins  # noqa: E402
from kulima.core.orgs.repository import OrgRepository  # noqa: E402

OPERATOR = "operator-principal"
CUSTOMER = "customer-principal"

SECTIONS = {
    "overview": "/api/v1/admin/overview",
    "users": "/api/v1/admin/users",
    "billing": "/api/v1/admin/billing",
    "ai_health": "/api/v1/admin/ai-health",
    "outcomes": "/api/v1/admin/outcomes",
    "audit": "/api/v1/admin/audit",
}

# The panels the PLATFORM_ADMIN mission added. They read, like the six above;
# the console's write surface is tested in test_platform_admin_role.py.
PANEL_SECTIONS = {
    "organizations": "/api/v1/admin/organizations",
    "assessments": "/api/v1/admin/assessments",
    "reports": "/api/v1/admin/reports",
    "conversations": "/api/v1/admin/conversations",
    "access": "/api/v1/admin/access",
}

ALL_SECTIONS = {**SECTIONS, **PANEL_SECTIONS}


def _token(subject: str) -> dict:
    payload = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return {"Authorization": f"Bearer {jwt.encode(payload, os.environ['NEXTAUTH_SECRET'], algorithm='HS256')}"}


@pytest.fixture()
def db_path(monkeypatch, tmp_path: Path):
    """A disposable database plus a console with OPERATOR allow-listed.

    The stored PLATFORM_ADMIN role is deliberately left unprovisioned here
    (``KULIMA_PLATFORM_ADMIN_EMAILS=""``): these tests are the console's read
    contract and the break-glass environment path. The role itself is tested in
    ``test_platform_admin_role.py``.
    """
    path = tmp_path / "admin_console.db"
    monkeypatch.setenv("KULIMA_DB_PATH", str(path))
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", OPERATOR)
    monkeypatch.setenv("KULIMA_ADMIN_EMAILS", "")
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_EMAILS", "")
    # The org repository is a lazy singleton keyed on the env DB path.
    monkeypatch.setattr(auth_module, "_org_repo_cache", None)
    platform_admins.reset_cache()
    yield path
    monkeypatch.setattr(auth_module, "_org_repo_cache", None)
    platform_admins.reset_cache()


@pytest.fixture()
def client(db_path):
    return TestClient(app)


def _seed_workspace(path: Path, subject: str, org_name: str, *, email: str | None = None) -> str:
    repo = OrgRepository(str(path))
    org = repo.create_org(org_name, created_by=subject)
    repo.add_member(org.id, subject, "owner", email=email, display_name=org_name)
    return org.id


# ── Route surface ────────────────────────────────────────────────────────────

def test_console_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/v1/admin/session" in paths
    for route in ALL_SECTIONS.values():
        assert route in paths, route


def test_session_is_open_to_any_signed_in_user(client):
    body = client.get("/api/v1/admin/session", headers=_token(CUSTOMER)).json()
    assert body["isPlatformAdmin"] is False
    assert body["reason"] == "not_allowlisted"
    # The caller learns their own identity (so an operator can ask for it) and
    # nothing about who else is on the allow-list.
    assert body["identity"]["userId"] == CUSTOMER
    assert body["allowListConfigured"] is True
    assert body["allowListSize"] == 1
    assert OPERATOR not in str(body["identity"])


@pytest.mark.parametrize("route", ["/api/v1/admin/session", *ALL_SECTIONS.values()])
def test_every_route_requires_a_session(client, route):
    assert client.get(route).status_code == 401


# ── The gate ─────────────────────────────────────────────────────────────────

def test_fail_closed_when_no_operator_is_configured(client, monkeypatch):
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", "")
    response = client.get(SECTIONS["overview"], headers=_token(OPERATOR))
    assert response.status_code == 403
    assert response.json()["code"] == "PLATFORM_ADMIN_NOT_CONFIGURED"


def test_unconfigured_reason_is_reported_on_session(client, monkeypatch):
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", "")
    body = client.get("/api/v1/admin/session", headers=_token(OPERATOR)).json()
    assert body["isPlatformAdmin"] is False
    assert body["reason"] == "not_configured"
    assert body["allowListConfigured"] is False


def test_organization_owner_is_not_a_platform_admin(client, db_path):
    _seed_workspace(db_path, CUSTOMER, "Customer Capital")
    response = client.get(SECTIONS["overview"], headers=_token(CUSTOMER))
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "PLATFORM_ADMIN_REQUIRED"
    # Proves the 403 came from a resolved Owner session, not a missing one.
    assert body["role"] == "owner"


def test_writable_membership_rows_never_grant_access(client, db_path, monkeypatch):
    """An org Admin controls organization_members.email.

    Allow-listing an address must not let a customer reach the console by
    inviting their own user id with that address attached.
    """
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", "")
    monkeypatch.setenv("KULIMA_ADMIN_EMAILS", "invited-address@kulima.africa")
    repo = OrgRepository(str(db_path))
    org = repo.create_org("Hijacked Workspace", created_by=CUSTOMER)
    repo.add_member(org.id, CUSTOMER, "owner", email="invited-address@kulima.africa")
    response = client.get(SECTIONS["overview"], headers=_token(CUSTOMER))
    assert response.status_code == 403
    assert response.json()["code"] == "PLATFORM_ADMIN_REQUIRED"


def test_session_subject_is_the_only_identity_consulted(db_path):
    candidates = dict(admin_access.identity_candidates(
        user_id="someone", verified_email=None,
    ))
    assert list(candidates) == ["session_subject"]


def test_email_allow_list_matches_when_the_subject_is_that_email(client, monkeypatch):
    """NextAuth uses the verified provider email as the subject when no name id
    exists, so allow-listing that address works through the session subject."""
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", "")
    monkeypatch.setenv("KULIMA_ADMIN_EMAILS", "Ops@Kulima.Africa")
    headers = _token("ops@kulima.africa")
    response = client.get(SECTIONS["overview"], headers=headers)
    assert response.status_code == 200
    body = client.get("/api/v1/admin/session", headers=headers).json()
    assert body["isPlatformAdmin"] is True
    assert body["matchedVia"] == "session_subject"


def test_allow_list_matching_is_case_insensitive(db_path, monkeypatch):
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", "Operator-Principal")
    repo = OrgRepository(str(db_path))
    org = repo.create_org("Kulima Operations", created_by="OPERATOR-PRINCIPAL")
    membership = repo.add_member(org.id, "OPERATOR-PRINCIPAL", "owner")
    ctx = OrgContext(user=AuthenticatedUser("OPERATOR-PRINCIPAL"), org=org, membership=membership)
    decision = admin_access.decision_for(ctx)
    assert decision.allowed is True
    assert decision.matched_via == "session_subject"


# ── Sections ─────────────────────────────────────────────────────────────────

def test_operator_reads_every_section(client):
    expected = {
        "overview": ("organizations", "users", "assessments", "reports", "conversations", "outcomeFollowUps"),
        "users": ("users", "organizations", "plans", "roles", "activity"),
        "billing": ("paychangu", "planStatus", "upgradeHistory", "failedPayments"),
        "ai_health": ("providers", "usage", "failures", "fallbacks", "documentIntelligence"),
        "outcomes": ("followUpCompletion", "pendingOutcomes", "decisionLearning"),
        "audit": ("events", "totals", "byCategory"),
        "organizations": ("totals", "organizations", "attentionDefinition"),
        "assessments": ("totals", "byStatus", "assessments", "recentFailures"),
        "reports": ("totals", "byKind", "reports", "sourceNote"),
        "conversations": ("totals", "conversations", "busiest"),
        "access": ("platformRole", "orgRoles", "store", "breakGlass", "admins"),
    }
    for key, route in ALL_SECTIONS.items():
        response = client.get(route, headers=_token(OPERATOR))
        assert response.status_code == 200, (key, response.text[:300])
        body = response.json()
        for field in expected[key]:
            assert field in body, (key, field)
        # A fresh database legitimately reports "table does not exist yet", but
        # never a broken query — that would be a bug in the console, not in the
        # environment.
        assert not [n for n in body["dataNotes"] if "query failed" in n], (key, body["dataNotes"])


def test_provider_tiers_are_all_reported(client):
    body = client.get(SECTIONS["ai_health"], headers=_token(OPERATOR)).json()
    ids = {p["id"] for p in body["providers"]}
    assert ids == {"openai", "groq", "gemini", "openrouter", "huggingface"}
    for provider in body["providers"]:
        assert set(provider) >= {"configured", "inChain", "assessmentsUsingIt", "fallbacksFromIt"}


def test_audit_buckets_cover_the_four_required_categories(client):
    body = client.get(SECTIONS["audit"], headers=_token(OPERATOR)).json()
    assert set(body["totals"]) >= {
        "assessmentCreation", "deletes", "roleChanges", "billingEvents", "totalEvents",
    }


def test_audit_bucket_filter_narrows_the_page_not_the_counts(client, db_path):
    org = _seed_workspace(db_path, OPERATOR, "Kulima Operations")
    record_event("assessment.created", org_id=org, user_id=OPERATOR)
    record_event("document.deleted", org_id=org, user_id=OPERATOR)
    record_event("org.role_changed", org_id=org, user_id=OPERATOR)
    record_event("billing.plan_changed", org_id=org, user_id=OPERATOR)

    unfiltered = client.get(SECTIONS["audit"], headers=_token(OPERATOR)).json()
    assert unfiltered["filters"]["bucket"] is None
    assert unfiltered["count"] >= 4

    deletes = client.get(SECTIONS["audit"] + "?bucket=deletes", headers=_token(OPERATOR)).json()
    assert {e["eventType"] for e in deletes["events"]} == {"document.deleted"}
    # Bucket counts stay a navigation aid: selecting one bucket must not zero out
    # the other three, or the cards stop being usable as filters.
    assert deletes["totals"]["deletes"] == unfiltered["totals"]["deletes"]
    assert deletes["totals"]["assessmentCreation"] >= 1
    assert deletes["count"] == deletes["totals"]["matchingEvents"]


def test_unknown_audit_bucket_reports_empty_with_a_note(client):
    body = client.get(SECTIONS["audit"] + "?bucket=nonsense", headers=_token(OPERATOR)).json()
    assert body["count"] == 0
    assert any("unknown audit bucket" in n for n in body["dataNotes"])


# ── Cross-workspace reading ──────────────────────────────────────────────────

def test_console_sees_every_workspace(client, db_path):
    operator_org = _seed_workspace(db_path, OPERATOR, "Kulima Operations")
    customer_org = _seed_workspace(db_path, CUSTOMER, "Customer Capital")
    BillingRepository(str(db_path)).update_subscription(
        customer_org, plan="professional", status="active", amount=49.0, currency="USD",
    )
    # The customer did something in their own workspace; the console sees it
    # without being able to be pointed at a workspace by id.
    record_event("assessment.created", org_id=customer_org, user_id=CUSTOMER,
                 metadata={"assessmentId": "a-1"})

    body = client.get(SECTIONS["overview"], headers=_token(OPERATOR)).json()
    assert body["organizations"]["total"] == 2
    assert body["users"]["total"] == 2

    users = client.get(SECTIONS["users"], headers=_token(OPERATOR)).json()
    seen = {u["userId"] for u in users["users"]}
    assert {OPERATOR, CUSTOMER} <= seen

    billing = client.get(SECTIONS["billing"], headers=_token(OPERATOR)).json()
    assert billing["planStatus"]["organizations"] == 2
    assert billing["planStatus"]["withoutSubscriptionRow"] == 1

    audit = client.get(SECTIONS["audit"], headers=_token(OPERATOR)).json()
    assert audit["distinctOrgs"] == 2

    # The operator's own workspace id is never a filter — the console has no
    # way to ask "only my organization" through these routes.
    assert operator_org and customer_org


# ── Honesty of the numbers ───────────────────────────────────────────────────

def test_panels_list_rows_when_the_platform_has_data(client, db_path):
    """A panel that can only count is not a panel.

    Guards the binding contract in ``admin_ops``: the list queries and their
    filter parameters must line up, because a mismatched bind silently returns
    an empty page over a database full of work.
    """
    org = _seed_workspace(db_path, CUSTOMER, "Customer Capital")
    now = datetime.now(timezone.utc).isoformat()

    AssessmentRepository(str(db_path))          # provisions the table it owns
    ConversationRepository(str(db_path))
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO assessment_contexts (assessment_id, run_id, assessment_type, status,"
            " user_id, org_id, payload_json, created_at, updated_at)"
            " VALUES ('asm-1','run-1','venture','complete',?,?, '{}', ?,?)",
            (CUSTOMER, org, now, now),
        )
        conn.execute(
            "INSERT INTO analyst_conversations (conversation_id, assessment_id, run_id, user_id,"
            " org_id, title, is_default, created_at, updated_at)"
            " VALUES ('conv-1','asm-1','run-1',?,?, 'Ask IC',0,?,?)",
            (CUSTOMER, org, now, now),
        )
        conn.execute(
            "INSERT INTO analyst_messages (conversation_id, role, content, created_at)"
            " VALUES ('conv-1','user','What is the market size?',?)", (now,),
        )
        conn.commit()

    assessments = client.get(PANEL_SECTIONS["assessments"], headers=_token(OPERATOR)).json()
    assert assessments["totals"]["listed"] == 1
    assert [a["assessmentId"] for a in assessments["assessments"]] == ["asm-1"]
    assert assessments["assessments"][0]["orgName"] == "Customer Capital"

    conversations = client.get(PANEL_SECTIONS["conversations"], headers=_token(OPERATOR)).json()
    assert [c["conversationId"] for c in conversations["conversations"]] == ["conv-1"]
    assert conversations["conversations"][0]["messages"] == 1
    assert conversations["conversations"][0]["questions"] == 1

    # Filters bind too — a filter that matches nothing must return nothing, not
    # the whole page.
    filtered = client.get(PANEL_SECTIONS["assessments"], headers=_token(OPERATOR),
                          params={"status": "running"}).json()
    assert filtered["totals"]["listed"] == 0
    other = client.get(PANEL_SECTIONS["assessments"], headers=_token(OPERATOR),
                       params={"search": "asm-1"}).json()
    assert other["totals"]["listed"] == 1

    for panel in ("assessments", "conversations"):
        body = client.get(PANEL_SECTIONS[panel], headers=_token(OPERATOR)).json()
        assert not [n for n in body["dataNotes"] if "query failed" in n], body["dataNotes"]


def test_metrics_without_data_are_none_not_zero(client):
    overview = client.get(SECTIONS["overview"], headers=_token(OPERATOR)).json()
    assert overview["outcomeFollowUps"]["total"] == 0
    assert overview["outcomeFollowUps"]["completionRate"] is None

    outcomes = client.get(SECTIONS["outcomes"], headers=_token(OPERATOR)).json()
    assert outcomes["followUpCompletion"]["completionRate"] is None
    assert outcomes["followedRate"]["rate"] is None
    assert outcomes["daysToFollowUp"]["average"] is None

    ai = client.get(SECTIONS["ai_health"], headers=_token(OPERATOR)).json()
    assert ai["usage"]["providerHealthEvents"] == 0
    assert ai["usage"]["emptyReason"].startswith("NO DATA")
    assert ai["latency"]["medianMs"] is None
    assert ai["fallbacks"]["fallbackRate"] is None

    billing = client.get(SECTIONS["billing"], headers=_token(OPERATOR)).json()
    assert billing["revenue"]["collectedInWindow"] is None


def test_calibration_bands_need_real_volume_before_reportal(client):
    outcomes = client.get(SECTIONS["outcomes"], headers=_token(OPERATOR)).json()
    assert outcomes["decisionLearning"]["calibration"]["reportableBands"] == []
    assert "fewer than 10" in outcomes["decisionLearning"]["calibration"]["bandNote"]


# ── Read-only + audited ──────────────────────────────────────────────────────

def _table_counts(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(path))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'audit_events'"
        )]
        out = {}
        for table in tables:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            out[table] = int(row[0])
        return out
    finally:
        conn.close()


def test_console_reads_write_nothing_except_its_own_audit_entry(client, db_path):
    """The read panels are still read panels.

    The console gained a management surface with PLATFORM_ADMIN, but that
    surface is a different set of verbs; every GET below must leave the tables
    it inspects exactly as it found them.
    """
    _seed_workspace(db_path, CUSTOMER, "Customer Capital")
    headers = _token(OPERATOR)
    # Warm up: the first request provisions the operator's workspace and the
    # sections create the tables they read. Both are side effects of *reading*,
    # so the assertion is made on a second, fully-warm pass.
    client.get("/api/v1/admin/session", headers=headers)
    for route in ALL_SECTIONS.values():
        assert client.get(route, headers=headers).status_code == 200
    views_before = len([e for e in AuditRepository(str(db_path)).list(org_id=None, limit=500)
                        if e["eventType"] == "admin.console_viewed"])
    before = _table_counts(db_path)

    for route in ALL_SECTIONS.values():
        assert client.get(route, headers=headers).status_code == 200

    assert _table_counts(db_path) == before

    events = AuditRepository(str(db_path)).list(org_id=None, limit=500)
    views = [e for e in events if e["eventType"] == "admin.console_viewed"]
    assert len(views) - views_before == len(ALL_SECTIONS)
    assert {e["metadata"]["section"] for e in views} == {
        "overview", "users", "billing", "ai-health", "outcomes", "audit",
        "organizations", "assessments", "reports", "conversations", "access",
    }


def test_console_view_is_a_known_event_type():
    assert "admin.console_viewed" in EVENT_TYPES
    assert EVENT_TYPES["admin.console_viewed"] == "Admin Console Opened"


def test_filters_are_bounded(client):
    headers = _token(OPERATOR)
    assert client.get(SECTIONS["overview"], headers=headers, params={"window_days": 0}).status_code == 422
    assert client.get(SECTIONS["overview"], headers=headers, params={"window_days": 999}).status_code == 422
    assert client.get(SECTIONS["users"], headers=headers, params={"limit": 5000}).status_code == 422
    body = client.get(SECTIONS["audit"], headers=headers, params={"org_id": "no-such-org"}).json()
    assert body["count"] == 0


def test_settings_expose_the_operator_allow_list(monkeypatch):
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", "a@b.co, ,ops-2")
    assert get_settings().platform_admin_user_ids == ("a@b.co", "ops-2")
