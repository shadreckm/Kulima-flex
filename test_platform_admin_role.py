"""Tests for the PLATFORM_ADMIN role and the platform mutations it authorises.

The console's *read* contract lives in ``test_admin_console.py``; this file is
about the role itself:

  * PLATFORM_ADMIN is a stored platform principal, never a membership role;
  * only a *session* identifier (JWT ``sub`` / provider-verified email) can
    resolve it — not a database row a customer can write;
  * everyone else, including an organization Owner, gets 403 on every route;
  * the mutations the role is granted (subscriptions, enterprise accounts, the
    roster) reuse the customer billing engine, keep its gates, and are audited
    with before/after state.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("NEXTAUTH_SECRET", "local-pytest-secret")

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.core import auth as auth_module  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.services import admin_actions  # noqa: E402
from backend.app.services.admin_actions import AdminActionError  # noqa: E402
from kulima.config import get_settings  # noqa: E402
from kulima.core.audit.repository import EVENT_TYPES, AuditRepository, event_label  # noqa: E402
from kulima.core.billing import service as billing_service  # noqa: E402
from kulima.core.billing.repository import BillingRepository  # noqa: E402
from kulima.core.orgs import platform_admins  # noqa: E402
from kulima.core.orgs.models import Role, coerce_role  # noqa: E402
from kulima.core.orgs.platform_admins import (  # noqa: E402
    PLATFORM_ADMIN_ROLE,
    PlatformCapability,
    capabilities_for_role,
)
from kulima.core.orgs.repository import OrgRepository  # noqa: E402

PRIMARY_EMAIL = "kulimaafrica@gmail.com"
ADMIN_SUB = "primary-operator-subject"
SECOND_EMAIL = "second-operator@kulima.africa"
CUSTOMER = "customer-principal"
CUSTOMER_EMAIL = "founder@agrinova.example"

READ_SECTIONS = {
    "overview": "/api/v1/admin/overview",
    "users": "/api/v1/admin/users",
    "organizations": "/api/v1/admin/organizations",
    "assessments": "/api/v1/admin/assessments",
    "reports": "/api/v1/admin/reports",
    "conversations": "/api/v1/admin/conversations",
    "billing": "/api/v1/admin/billing",
    "ai_health": "/api/v1/admin/ai-health",
    "outcomes": "/api/v1/admin/outcomes",
    "audit": "/api/v1/admin/audit",
    "access": "/api/v1/admin/access",
}

MUTATIONS = {
    "create_org": ("post", "/api/v1/admin/organizations"),
    "rename_org": ("patch", "/api/v1/admin/organizations/org-x"),
    "subscription": ("put", "/api/v1/admin/organizations/org-x/subscription"),
    "account_status": ("post", "/api/v1/admin/organizations/org-x/account-status"),
    "activation": ("post", "/api/v1/admin/organizations/org-x/enterprise-activation"),
    "grant": ("post", "/api/v1/admin/access/admins"),
    "revoke": ("delete", "/api/v1/admin/access/admins/someone"),
}


def _token(subject: str, email: str | None = None, *, secret: str | None = None) -> dict:
    payload = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    if email:
        payload["email"] = email
    return {"Authorization": f"Bearer {jwt.encode(payload, secret or os.environ['NEXTAUTH_SECRET'], algorithm='HS256')}"}


@pytest.fixture()
def db_path(monkeypatch, tmp_path: Path):
    """A workspace DB where the stored role is the only thing granting access."""
    path = tmp_path / "platform_admin.db"
    monkeypatch.setenv("KULIMA_DB_PATH", str(path))
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_EMAILS", PRIMARY_EMAIL)
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL", PRIMARY_EMAIL)
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_USER_IDS", "")
    monkeypatch.setenv("KULIMA_ADMIN_EMAILS", "")
    monkeypatch.setattr(auth_module, "_org_repo_cache", None)
    platform_admins.reset_cache()
    # The billing engine binds its repository once, at import, so a test that
    # moves the database afterwards has to move the engine with it — otherwise
    # plan changes would be written to the developer's local DB and the
    # mutation under test would legitimately report "nothing changed".
    previous = billing_service.get_repository()
    billing_service.use_repository(BillingRepository(str(path)))
    try:
        yield path
    finally:
        billing_service.use_repository(previous)
        platform_admins.reset_cache()
        monkeypatch.setattr(auth_module, "_org_repo_cache", None)


@pytest.fixture()
def client(db_path):
    return TestClient(app)


@pytest.fixture()
def admin(db_path) -> str:
    """The primary administrator's subject, linked the way a real session links it."""
    repo = platform_admins.get_repo(str(db_path))
    row = repo.resolve(email=PRIMARY_EMAIL)
    assert row is not None and row.user_id is None
    repo.attach_subject(principal=row.principal, user_id=ADMIN_SUB)
    return ADMIN_SUB


def _seed_customer(path: Path, subject: str = CUSTOMER, name: str = "AgriNova Capital",
                   *, email: str | None = CUSTOMER_EMAIL, plan: str = "free") -> str:
    repo = OrgRepository(str(path))
    org = repo.create_org(name, created_by=subject)
    repo.add_member(org.id, subject, "owner", email=email, display_name=name)
    BillingRepository(str(path)).update_subscription(org.id, plan=plan, status="active")
    return org.id


def _events(path: Path, event_type: str) -> list[dict]:
    return [e for e in AuditRepository(str(path)).list(org_id=None, limit=500)
            if e["eventType"] == event_type]


# ── The role is a platform principal, not a membership role ──────────────────

def test_platform_admin_is_not_an_organization_role():
    assert "platform_admin" not in {r.value for r in Role}
    assert coerce_role("platform_admin") is None


def test_membership_writes_reject_the_platform_role(db_path):
    repo = OrgRepository(str(db_path))
    org = repo.create_org("Escalation Attempt", created_by=CUSTOMER)
    repo.add_member(org.id, CUSTOMER, "owner")
    with pytest.raises(ValueError) as add_exc:
        repo.add_member(org.id, "u-2", "platform_admin")
    assert str(add_exc.value) == "platform_role_not_assignable"
    with pytest.raises(ValueError) as set_exc:
        repo.set_role(org.id, CUSTOMER, "platform_admin")
    assert str(set_exc.value) == "platform_role_not_assignable"
    assert repo.get_membership_for_org(org.id, CUSTOMER).role is Role.OWNER


def test_organization_roles_grant_no_platform_capability():
    for role in Role:
        assert capabilities_for_role(role.value) == frozenset()
    assert capabilities_for_role(None) == frozenset()


def test_platform_admin_holds_every_capability():
    caps = capabilities_for_role(PLATFORM_ADMIN_ROLE)
    assert caps == frozenset(PlatformCapability)
    assert PlatformCapability.MANAGE_SUBSCRIPTIONS in caps
    assert PlatformCapability.VIEW_AUDIT in caps


def test_bootstrap_provisions_the_primary_admin(db_path):
    repo = platform_admins.get_repo(str(db_path))
    row = repo.resolve(email=PRIMARY_EMAIL)
    assert row is not None
    assert row.role == PLATFORM_ADMIN_ROLE
    assert row.source == "bootstrap"
    assert row.status == "active"
    assert repo.is_primary(row) is True


def test_bootstrap_is_idempotent_and_does_not_revive_a_revocation(db_path):
    repo = platform_admins.get_repo(str(db_path))  # the store provisions itself lazily
    assert repo.find(email=PRIMARY_EMAIL).source == "bootstrap"
    second = repo.bootstrap()
    assert second["created"] == [] and PRIMARY_EMAIL in second["skipped"]
    assert second["active"] == 1

    with repo._connect() as conn:  # direct write: simulates a deliberate revocation
        conn.execute("UPDATE platform_admins SET status = 'revoked' WHERE email = ?", (PRIMARY_EMAIL,))
        conn.commit()
    assert repo.bootstrap()["created"] == []
    assert repo.resolve(email=PRIMARY_EMAIL) is None
    assert repo.bootstrap(force=True)["created"] == [PRIMARY_EMAIL]
    assert repo.resolve(email=PRIMARY_EMAIL) is not None


# ── Who can get in ───────────────────────────────────────────────────────────

def test_verified_email_claim_grants_the_role(client, db_path):
    # No subject link yet: the provider-verified email alone must resolve it.
    session = client.get("/api/v1/admin/session", headers=_token("brand-new-subject", PRIMARY_EMAIL)).json()
    assert session["isPlatformAdmin"] is True
    assert session["grantedBy"] == "platform_role"
    assert session["matchedVia"] == "verified_email"
    assert session["platformRole"] == PLATFORM_ADMIN_ROLE
    assert PlatformCapability.VIEW_BILLING.value in session["capabilities"]
    # The first request linked the subject, so a later one resolves on it.
    assert client.get(READ_SECTIONS["overview"],
                      headers=_token("brand-new-subject", PRIMARY_EMAIL)).status_code == 200
    assert platform_admins.get_repo(str(db_path)).resolve(user_id="brand-new-subject") is not None


def test_linking_happens_once_and_does_not_change_the_roster_size(client, db_path):
    headers = _token("link-once", PRIMARY_EMAIL)
    client.get("/api/v1/admin/session", headers=headers)
    client.get("/api/v1/admin/session", headers=headers)
    repo = platform_admins.get_repo(str(db_path))
    assert repo.count_active() == 1
    assert repo.resolve(user_id="link-once") is not None


def test_subject_grants_the_role_once_linked(client, admin):
    assert client.get(READ_SECTIONS["audit"], headers=_token(admin)).status_code == 200


@pytest.mark.parametrize("route", list(READ_SECTIONS.values()) + [p for _, p in MUTATIONS.values()])
def test_every_platform_route_needs_a_session(client, route):
    """No verb on no path in the console accepts an anonymous caller."""
    verb_by_path = {p: m for m, p in MUTATIONS.values()}
    response = getattr(client, verb_by_path.get(route, "get"))(route)
    assert response.status_code == 401, route
    assert response.json()["code"] == "SESSION_MISSING"


def test_organization_owner_is_not_a_platform_admin(client, db_path, admin):
    _seed_customer(db_path)
    for route in READ_SECTIONS.values():
        response = client.get(route, headers=_token(CUSTOMER, CUSTOMER_EMAIL))
        assert response.status_code == 403, route
        body = response.json()
        assert body["code"] == "PLATFORM_ADMIN_REQUIRED"
        assert body["role"] == "owner"


def test_membership_row_carrying_the_admin_email_grants_nothing(client, db_path):
    """organization_members.email is inviter-writable; it is not a session."""
    _seed_customer(db_path, email=PRIMARY_EMAIL)
    response = client.get(READ_SECTIONS["overview"], headers=_token(CUSTOMER))
    assert response.status_code == 403
    assert response.json()["code"] == "PLATFORM_ADMIN_REQUIRED"


def test_organizations_created_by_the_admin_email_do_not_grant_access(client, db_path):
    repo = OrgRepository(str(db_path))
    org = repo.create_org("Lookalike Workspace", created_by=PRIMARY_EMAIL)
    repo.add_member(org.id, CUSTOMER, "admin", email=PRIMARY_EMAIL)
    assert org.created_by == PRIMARY_EMAIL
    assert client.get(READ_SECTIONS["users"], headers=_token(CUSTOMER)).status_code == 403


def test_email_claim_is_normalised(client, db_path):
    response = client.get(READ_SECTIONS["overview"],
                          headers=_token("case-sub", f"  {PRIMARY_EMAIL.upper()}  "))
    assert response.status_code == 200


def test_token_from_another_secret_is_rejected(client, db_path):
    headers = _token("attacker", PRIMARY_EMAIL, secret="an-unrelated-secret")
    assert client.get(READ_SECTIONS["overview"], headers=headers).status_code == 401


def test_break_glass_environment_still_grants_and_says_so(client, db_path, monkeypatch):
    monkeypatch.setenv("KULIMA_ADMIN_EMAILS", "emergency@kulima.africa")
    session = client.get("/api/v1/admin/session", headers=_token("emergency@kulima.africa")).json()
    assert session["isPlatformAdmin"] is True
    assert session["grantedBy"] == "env_allow_list"
    assert session["roleLabel"].endswith("(break-glass)")


def test_fail_closed_when_neither_the_role_nor_the_environment_names_anyone(
    client, db_path, monkeypatch,
):
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_EMAILS", "")
    platform_admins.reset_cache()
    with platform_admins.get_repo(str(db_path))._connect() as conn:
        conn.execute("DELETE FROM platform_admins")
        conn.commit()
    response = client.get(READ_SECTIONS["overview"], headers=_token(ADMIN_SUB, PRIMARY_EMAIL))
    assert response.status_code == 403
    assert response.json()["code"] == "PLATFORM_ADMIN_NOT_CONFIGURED"


def test_session_never_leaks_the_roster(client, db_path, admin):
    _seed_customer(db_path)
    body = client.get("/api/v1/admin/session", headers=_token(CUSTOMER, CUSTOMER_EMAIL)).json()
    assert body["isPlatformAdmin"] is False
    assert PRIMARY_EMAIL not in str(body)
    assert ADMIN_SUB not in str(body)
    # A count is fine; identities are not.
    assert body["adminCount"] == 1


# ── Manage subscriptions ─────────────────────────────────────────────────────

def test_plan_upgrade_uses_the_billing_engine(client, db_path, admin):
    org_id = _seed_customer(db_path, plan="free")
    response = client.put(f"/api/v1/admin/organizations/{org_id}/subscription",
                          headers=_token(admin), json={"plan": "pro", "reason": "pilot credit"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["planResult"]["changed"] is True
    assert body["after"]["plan"] == "pro"
    assert body["after"]["status"] == "active"
    assert OrgRepository(str(db_path)).get_org(org_id).plan == "pro"
    events = BillingRepository(str(db_path)).list_payment_events(org_id, limit=20)
    assert {"plan_changed"} <= {e["eventType"] for e in events}


def test_downgrade_schedules_at_period_end(client, db_path, admin):
    org_id = _seed_customer(db_path, plan="pro")
    with BillingRepository(str(db_path))._connect() as conn:
        conn.execute("UPDATE subscriptions SET amount = 49, currency = 'USD',"
                     " current_period_start = ?, current_period_end = ? WHERE org_id = ?",
                     (datetime.now(timezone.utc).isoformat(),
                      (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(), org_id))
        conn.commit()
    result = client.put(f"/api/v1/admin/organizations/{org_id}/subscription",
                        headers=_token(admin), json={"plan": "free"}).json()
    assert result["after"]["pendingPlan"] == "free"
    assert result["after"]["plan"] == "pro"


def test_enterprise_plan_still_requires_the_agreement(client, db_path, admin):
    org_id = _seed_customer(db_path, plan="pro")
    response = client.put(f"/api/v1/admin/organizations/{org_id}/subscription",
                          headers=_token(admin), json={"plan": "enterprise"})
    assert response.status_code == 422
    assert response.json()["code"] == "ENTERPRISE_ACTIVATION_REQUIRED"


def test_agreement_must_be_explicitly_accepted(client, db_path, admin):
    org_id = _seed_customer(db_path, plan="pro")
    client.post(f"/api/v1/admin/organizations/{org_id}/enterprise-activation",
                headers=_token(admin), json={"action": "request"})
    blocked = client.post(f"/api/v1/admin/organizations/{org_id}/enterprise-activation",
                          headers=_token(admin), json={"action": "approve", "agreementAccepted": False})
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "AGREEMENT_REQUIRED"
    approved = client.post(f"/api/v1/admin/organizations/{org_id}/enterprise-activation",
                           headers=_token(admin),
                           json={"action": "approve", "agreementAccepted": True})
    assert approved.status_code == 200
    assert approved.json()["after"] == "approved"
    assert approved.json()["checkoutAllowed"] is True
    applied = client.put(f"/api/v1/admin/organizations/{org_id}/subscription",
                         headers=_token(admin), json={"plan": "enterprise", "amount": 250})
    assert applied.status_code == 200
    assert applied.json()["after"]["plan"] == "enterprise"


def test_operator_cannot_patch_payment_provenance(client, db_path, admin):
    """An undeclared field is refused, and refused by name — never dropped."""
    org_id = _seed_customer(db_path)
    response = client.put(f"/api/v1/admin/organizations/{org_id}/subscription",
                          headers=_token(admin), json={"paychanguRef": "forged-tx"})
    assert response.status_code == 422
    assert "paychanguRef" in str(response.json())
    assert BillingRepository(str(db_path)).get_subscription(org_id).get("paychangu_ref") != "forged-tx"


def test_the_patchable_field_contract_is_enforced_in_the_service(db_path, admin):
    """The second wall: a caller that skips the HTTP model still cannot name
    payment provenance among the fields to patch."""
    org_id = _seed_customer(db_path)
    operator = SimpleNamespace(user_id=admin, org_id="platform", admin_decision=None)
    with pytest.raises(AdminActionError) as exc:
        admin_actions.update_subscription(operator=operator, org_id=org_id,
                                          fields={"paychangu_ref": "forged-tx"})
    assert exc.value.code == "FIELD_NOT_PATCHABLE"
    assert "paychangu_ref" in exc.value.message
    assert "paychangu_ref" not in admin_actions.PATCHABLE_FIELDS


def test_status_transitions_are_audited(client, db_path, admin):
    org_id = _seed_customer(db_path, plan="pro")
    client.post(f"/api/v1/admin/organizations/{org_id}/account-status",
                headers=_token(admin), json={"status": "suspended", "reason": "unpaid"})
    assert BillingRepository(str(db_path)).get_subscription(org_id)["status"] == "suspended"
    client.post(f"/api/v1/admin/organizations/{org_id}/account-status",
                headers=_token(admin), json={"status": "active"})
    assert BillingRepository(str(db_path)).get_subscription(org_id)["status"] == "active"
    assert len(_events(db_path, "admin.account_suspended")) == 1
    assert len(_events(db_path, "admin.account_reactivated")) == 1
    suspend = _events(db_path, "admin.account_suspended")[-1]
    assert suspend["metadata"]["before"]["status"] == "active"
    assert suspend["metadata"]["after"]["status"] == "suspended"
    assert suspend["metadata"]["reason"] == "unpaid"
    assert suspend["metadata"]["via"] == "platform_role"


def test_unknown_organization_is_a_404(client, admin):
    response = client.put("/api/v1/admin/organizations/no-such-org/subscription",
                          headers=_token(admin), json={"plan": "pro"})
    assert response.status_code == 404
    assert response.json()["code"] == "ORG_NOT_FOUND"


# ── Manage enterprise accounts ───────────────────────────────────────────────

def test_platform_provisioned_workspace_is_never_orphaned(client, db_path, admin):
    response = client.post("/api/v1/admin/organizations", headers=_token(admin),
                           json={"name": "Victoria Falls Holdings", "plan": "enterprise",
                                 "intendedOwnerEmail": "ceo@vflodge.example"})
    assert response.status_code == 201, response.text
    org_id = response.json()["organization"]["orgId"]
    repo = OrgRepository(str(db_path))
    assert repo.get_org(org_id).personal is False
    assert admin in repo.member_user_ids(org_id)
    assert response.json()["pendingOwnerEmail"] == "ceo@vflodge.example"
    assert response.json()["subscription"]["activationState"] == "requested"
    assert len(_events(db_path, "admin.org_created")) == 1


def test_an_email_someone_typed_is_not_a_principal(client, db_path, admin):
    response = client.post("/api/v1/admin/organizations", headers=_token(admin),
                           json={"name": "Ghost Org", "ownerUserId": "never-signed-in"})
    assert response.status_code == 422
    assert response.json()["code"] == "OWNER_NOT_SIGNED_IN"


def test_rename_is_audited(client, db_path, admin):
    org_id = _seed_customer(db_path)
    client.patch(f"/api/v1/admin/organizations/{org_id}", headers=_token(admin),
                 json={"name": "AgriNova Group", "reason": "rebrand"})
    assert OrgRepository(str(db_path)).get_org(org_id).name == "AgriNova Group"
    event = _events(db_path, "admin.org_updated")[-1]
    assert event["metadata"]["before"]["name"] == "AgriNova Capital"
    assert event["userId"] == admin


# ── The roster ───────────────────────────────────────────────────────────────

def test_grant_adds_an_admin_and_is_audited(client, db_path, admin):
    response = client.post("/api/v1/admin/access/admins", headers=_token(admin),
                           json={"email": SECOND_EMAIL, "displayName": "Second Ops"})
    assert response.status_code == 201, response.text
    assert response.json()["outcome"] == "granted"
    assert response.json()["activeCount"] == 2
    granted = client.get(READ_SECTIONS["overview"], headers=_token("second-sub", SECOND_EMAIL))
    assert granted.status_code == 200
    assert len(_events(db_path, "admin.platform_admin_granted")) == 1


def test_grant_needs_a_session_provable_identity(client, db_path, admin):
    response = client.post("/api/v1/admin/access/admins", headers=_token(admin),
                           json={"displayName": "Nobody"})
    assert response.status_code == 422
    assert response.json()["code"] == "IDENTITY_REQUIRED"
    bad = client.post("/api/v1/admin/access/admins", headers=_token(admin),
                      json={"email": "not-an-email"})
    assert bad.json()["code"] == "INVALID_EMAIL"


def test_revoke_removes_access_but_keeps_history(client, db_path, admin):
    client.post("/api/v1/admin/access/admins", headers=_token(admin), json={"email": SECOND_EMAIL})
    response = client.delete(f"/api/v1/admin/access/admins/{SECOND_EMAIL}", headers=_token(admin))
    assert response.status_code == 200
    assert client.get(READ_SECTIONS["overview"], headers=_token("second-sub", SECOND_EMAIL)).status_code == 403
    repo = platform_admins.get_repo(str(db_path))
    revoked = repo.find(email=SECOND_EMAIL)
    assert revoked is not None and revoked.status == "revoked"


def test_the_primary_admin_cannot_be_revoked(client, db_path, admin):
    client.post("/api/v1/admin/access/admins", headers=_token(admin), json={"email": SECOND_EMAIL})
    response = client.delete(f"/api/v1/admin/access/admins/{PRIMARY_EMAIL}", headers=_token(admin))
    assert response.status_code == 422
    assert response.json()["code"] == "PRIMARY_ADMIN"


def test_the_last_admin_cannot_be_revoked(client, db_path, monkeypatch):
    """With nobody left, only the environment could reopen the console."""
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL", "")
    platform_admins.reset_cache()
    repo = platform_admins.get_repo(str(db_path))
    with repo._connect() as conn:
        conn.execute("UPDATE platform_admins SET email = NULL, user_id = ?", (ADMIN_SUB,))
        conn.commit()
    assert repo.count_active() == 1
    response = client.delete(f"/api/v1/admin/access/admins/{ADMIN_SUB}",
                             headers=_token(ADMIN_SUB))
    assert response.status_code == 422
    assert response.json()["code"] == "LAST_ADMIN"
    assert repo.count_active() == 1


def test_revoking_a_nonexistent_principal_is_a_404(client, admin):
    response = client.delete("/api/v1/admin/access/admins/ghost@example.com", headers=_token(admin))
    assert response.status_code == 404


# ── The access panel and the audit trail ─────────────────────────────────────

def test_access_panel_shows_both_planes(client, db_path, admin):
    _seed_customer(db_path, subject="member-one", name="Member Org")
    body = client.get(READ_SECTIONS["access"], headers=_token(admin)).json()
    assert body["platformRole"]["id"] == PLATFORM_ADMIN_ROLE
    assert len(body["platformRole"]["capabilities"]) == len(PlatformCapability)
    assert all(role["platformCapabilities"] == [] for role in body["orgRoles"])
    assert {role["id"] for role in body["orgRoles"]} == {r.value for r in Role}
    assert body["store"]["configured"] is True
    assert body["store"]["primaryEmail"] == PRIMARY_EMAIL
    assert body["breakGlass"]["configured"] is False
    assert [a["email"] for a in body["admins"]] == [PRIMARY_EMAIL]
    assert body["admins"][0]["isPrimary"] is True


def test_platform_mutations_appear_in_the_role_bucket(client, db_path, admin):
    client.post("/api/v1/admin/access/admins", headers=_token(admin), json={"email": SECOND_EMAIL})
    audit = client.get(READ_SECTIONS["audit"], headers=_token(admin), params={"bucket": "roles"}).json()
    assert "admin.platform_admin_granted" in {e["eventType"] for e in audit["events"]}
    assert audit["totals"]["roleChanges"] >= 1


def test_audit_records_how_the_operator_got_in(client, db_path, admin):
    client.put(f"/api/v1/admin/organizations/{_seed_customer(db_path)}/subscription",
               headers=_token(admin), json={"plan": "pro"})
    event = _events(db_path, "admin.subscription_updated")[-1]
    assert event["metadata"]["via"] == "platform_role"
    assert event["metadata"]["before"]["plan"] == "free"
    assert event["metadata"]["after"]["plan"] == "pro"


def test_platform_events_have_labels():
    """A platform event the audit log cannot name is an event nobody can read."""
    for event_type in ("admin.subscription_updated", "admin.org_created", "admin.org_updated",
                       "admin.account_suspended", "admin.account_reactivated",
                       "admin.enterprise_activation_changed",
                       "admin.platform_admin_granted", "admin.platform_admin_revoked",
                       "admin.action_failed"):
        assert event_type in EVENT_TYPES, event_type
        assert event_label(event_type) == EVENT_TYPES[event_type]


# ── Writes are confined to the platform plane ────────────────────────────────

def _table_counts(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(path))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'audit_events'"
        )]
        return {t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in tables}
    finally:
        conn.close()


def _row_ids(path: Path) -> dict[str, set[int]]:
    """Every stored row's identity, per table — what must never go missing."""
    conn = sqlite3.connect(str(path))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )]
        return {t: {r[0] for r in conn.execute(f"SELECT rowid FROM {t}")} for t in tables}
    finally:
        conn.close()


def test_mutations_never_delete_customer_data(client, db_path, admin):
    """The console changes state; it does not remove it.

    Every mutation is run against a database holding a customer workspace, and
    afterwards every row that existed before is still there — plans move, accounts
    get suspended and renamed, an organization is created, an admin is granted,
    and no customer row disappears. History is written as new rows only.
    """
    org_id = _seed_customer(db_path)
    _seed_customer(db_path, subject="member-two", name="Second Customer")
    warm_ids = _row_ids(db_path)
    warm_members = OrgRepository(str(db_path)).member_user_ids(org_id)

    client.put(f"/api/v1/admin/organizations/{org_id}/subscription", headers=_token(admin),
               json={"plan": "pro"})
    client.post(f"/api/v1/admin/organizations/{org_id}/account-status", headers=_token(admin),
                json={"status": "suspended"})
    client.post(f"/api/v1/admin/organizations/{org_id}/account-status", headers=_token(admin),
                json={"status": "active"})
    client.patch(f"/api/v1/admin/organizations/{org_id}", headers=_token(admin),
                 json={"name": "Renamed Customer"})
    client.post("/api/v1/admin/organizations", headers=_token(admin), json={"name": "New Enterprise"})
    client.post("/api/v1/admin/access/admins", headers=_token(admin), json={"email": SECOND_EMAIL})

    after_ids = _row_ids(db_path)
    for table, ids in warm_ids.items():
        assert ids <= after_ids[table], f"rows vanished from {table}"
    assert after_ids["platform_admins"] >= warm_ids["platform_admins"]
    repo = OrgRepository(str(db_path))
    assert repo.get_org(org_id) is not None
    assert repo.member_user_ids(org_id) == warm_members
    assert len(_events(db_path, "admin.subscription_updated")) >= 1
    assert len(_events(db_path, "admin.org_updated")) == 1


def test_get_settings_exposes_the_role_configuration(monkeypatch):
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_EMAILS", "Root@Kulima.Africa, second@kulima.africa")
    monkeypatch.setenv("KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL", "ROOT@kulima.africa")
    settings = get_settings()
    assert settings.platform_admin_emails == ("root@kulima.africa", "second@kulima.africa")
    assert settings.platform_admin_primary_email == "root@kulima.africa"


def test_default_configuration_names_the_primary_admin(monkeypatch):
    monkeypatch.delenv("KULIMA_PLATFORM_ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL", raising=False)
    assert get_settings().platform_admin_emails == (PRIMARY_EMAIL,)
    assert get_settings().platform_admin_primary_email == PRIMARY_EMAIL
