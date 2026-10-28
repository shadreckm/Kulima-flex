"""Platform Administration verification — the /admin console and its role.

This is the mission contract for the Platform Administration Architect, executed
as one reproducible script. Groups:

  1. Route surface      — every panel endpoint exists on the FastAPI app, and the
                          only non-GET verbs are the audited operator mutations.
  2. The gate           — fail-closed, session-only, and *not* satisfied by an
                          organization role or by membership rows a customer
                          can write.
  3. Honesty            — empty denominators report NO DATA, never a zero.
  4. Panel coverage     — the mission panels expose exactly the metrics asked for.
  5. Cross-workspace    — the console reads every workspace (that is the point).
  6. Read-only + audit  — opening a panel writes nothing but its own
                          ``admin.console_viewed`` entry.
  7. Frontend surface   — eleven screens behind one platform gate, no customer
                          shell, admin link gated.
  8. Role plane         — PLATFORM_ADMIN stored in its own table, capability
                          enforcement, the eight mission capabilities, the
                          mutations' business rules, and anti-lockout.

Offline and isolated: writes go to a disposable SQLite file.

Usage: python scripts/admin_console_check.py
"""
from __future__ import annotations

import io
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["KULIMA_DB_PATH"] = _TMP_DB.name
os.environ.setdefault("NEXTAUTH_SECRET", "admin-console-check-secret")
os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = "ops-principal"
os.environ["KULIMA_ADMIN_EMAILS"] = ""
# The shipped default provisions kulimaafrica@gmail.com into the stored role. This
# probe measures the role plane from an empty roster, so the fail-closed behaviour
# below is observable rather than masked by a configured primary. The first gate
# call happens after this script has cleared the env, so bootstrap() provisions
# nobody until group 8 grants a role explicitly.
os.environ["KULIMA_PLATFORM_ADMIN_EMAILS"] = ""
os.environ["KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL"] = ""

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from kulima.core.audit.repository import AuditRepository, EVENT_TYPES, record_event  # noqa: E402
from kulima.core.billing.repository import BillingRepository  # noqa: E402
from kulima.core.orgs.platform_admins import (  # noqa: E402
    PLATFORM_ADMIN_ROLE,
    PlatformAdminRepository,
    PlatformCapability,
)
from kulima.core.orgs.models import Role  # noqa: E402
from kulima.core.orgs.repository import OrgRepository  # noqa: E402

OPERATOR = "ops-principal"
CUSTOMER = "customer-principal"
SECOND_ADMIN = "second-admin@kulima.example"
FRONTEND = ROOT / "frontend"

SECTIONS = {
    "overview": "/api/v1/admin/overview",
    "users": "/api/v1/admin/users",
    "billing": "/api/v1/admin/billing",
    "ai_health": "/api/v1/admin/ai-health",
    "outcomes": "/api/v1/admin/outcomes",
    "audit": "/api/v1/admin/audit",
    "organizations": "/api/v1/admin/organizations",
    "assessments": "/api/v1/admin/assessments",
    "reports": "/api/v1/admin/reports",
    "conversations": "/api/v1/admin/conversations",
    "access": "/api/v1/admin/access",
}

#: The console's entire write surface. Everything else is a read.
MUTATION_ROUTES = {
    "/api/v1/admin/organizations": ["post"],
    "/api/v1/admin/organizations/{org_id}": ["patch"],
    "/api/v1/admin/organizations/{org_id}/subscription": ["put"],
    "/api/v1/admin/organizations/{org_id}/account-status": ["post"],
    "/api/v1/admin/organizations/{org_id}/enterprise-activation": ["post"],
    "/api/v1/admin/access/admins": ["post"],
    "/api/v1/admin/access/admins/{identity}": ["delete"],
}

#: The capabilities the mission named, in the backend's own vocabulary.
MISSION_CAPABILITIES = {
    "view all organizations": "view_organizations",
    "view all users": "view_users",
    "manage subscriptions": "manage_subscriptions",
    "manage enterprise accounts": "manage_enterprise_accounts",
    "view billing": "view_billing",
    "view provider health": "view_provider_health",
    "access audit logs": "view_audit",
    "access platform analytics": "view_analytics",
}

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def group(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 58 - len(title)))


def token(subject: str, email: str | None = None) -> dict:
    """A backend token as our own auth chain mints it: a subject, and optionally
    the provider-verified email claim the /api/v1 proxy attaches."""
    payload = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    if email:
        payload["email"] = email
    secret = os.environ["NEXTAUTH_SECRET"]
    return {"Authorization": f"Bearer {jwt.encode(payload, secret, algorithm='HS256')}"}


def events(event_type: str) -> list[dict]:
    return [e for e in AuditRepository(os.environ["KULIMA_DB_PATH"]).list(org_id=None, limit=2000)
            if e["eventType"] == event_type]


def section(client: TestClient, key: str, suffix: str = "") -> dict:
    response = client.get(SECTIONS[key] + suffix, headers=token(OPERATOR))
    assert response.status_code == 200, (key, response.status_code, response.text[:200])
    return response.json()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def build_routes(app_dir: Path) -> set[tuple[str, ...]]:
    return {tuple(s.lower() for s in p.parent.relative_to(app_dir).parts)
            for p in app_dir.rglob("page.tsx")}


def route_exists(routes: set[tuple[str, ...]], link: str) -> bool:
    segs = tuple(s for s in link.strip("/").lower().split("/") if s)
    return segs in routes


def table_counts(path: str) -> dict[str, int]:
    conn = sqlite3.connect(path)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'audit_events'")]
        return {n: int(conn.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0]) for n in names}
    finally:
        conn.close()


def main() -> int:
    client = TestClient(app)  # no context manager: skip lifespan / job runner

    # ── 1. Route surface ─────────────────────────────────────────────────────
    group("1. Route surface")
    doc = app.openapi()["paths"]
    paths = set(doc)
    check("GET /api/v1/admin/session is registered", "/api/v1/admin/session" in paths)
    check("all eleven panel endpoints are registered",
          all(route in paths for route in SECTIONS.values()),
          str([r for r in SECTIONS.values() if r not in paths]))
    admin_verbs = {p: {m.upper() for m in verbs} for p, verbs in doc.items()
                   if p.startswith("/api/v1/admin")}
    writable = {p: sorted(m for m in verbs if m != "GET") for p, verbs in admin_verbs.items()
                if verbs - {"GET"}}
    check("the only non-GET console routes are the declared operator mutations",
          writable == {p: sorted(v.upper() for v in verbs if v.upper() != "GET")
                       for p, verbs in MUTATION_ROUTES.items()}, str(writable))
    check("every panel the mission named is reachable by a read",
          all("GET" in admin_verbs.get(SECTIONS[key], set()) for key in SECTIONS),
          str(sorted(p for p, v in admin_verbs.items() if v != {"GET"})))
    check("the write surface is confined to the two administration panels",
          all(p.startswith(("/api/v1/admin/organizations", "/api/v1/admin/access"))
              for p in writable), str(sorted(writable)))

    # ── 2. The gate ──────────────────────────────────────────────────────────
    group("2. The platform gate (PLATFORM_ADMIN ONLY)")
    unauth = {r: client.get(r).status_code for r in ["/api/v1/admin/session", *SECTIONS.values()]}
    check("every console route rejects an anonymous caller (401)",
          all(code == 401 for code in unauth.values()), str(unauth))

    saved = os.environ.get("KULIMA_PLATFORM_ADMIN_USER_IDS")
    os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = ""
    closed = client.get(SECTIONS["overview"], headers=token(OPERATOR))
    check("fail-closed: nobody gets in when no administrator is configured",
          closed.status_code == 403 and closed.json()["code"] == "PLATFORM_ADMIN_NOT_CONFIGURED",
          f"{closed.status_code} {closed.text[:120]}")
    closed_panel = client.get(SECTIONS["access"], headers=token(OPERATOR))
    check("fail-closed applies to the newest panels too, not only the original six",
          closed_panel.status_code == 403, str(closed_panel.status_code))
    if saved is not None:
        os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = saved

    repo = OrgRepository(os.environ["KULIMA_DB_PATH"])
    customer_org = repo.create_org("Customer Capital", created_by=CUSTOMER)
    repo.add_member(customer_org.id, CUSTOMER, "owner",
                    email=f"{OPERATOR}@kulima.example", display_name=OPERATOR)
    owner = client.get(SECTIONS["overview"], headers=token(CUSTOMER))
    check("an organization Owner is NOT a platform administrator",
          owner.status_code == 403 and owner.json()["role"] == "owner",
          f"{owner.status_code} {owner.text[:160]}")
    check("membership rows a customer can write (email/display name) never grant access",
          owner.status_code == 403 and owner.json()["code"] == "PLATFORM_ADMIN_REQUIRED")
    for key in ("organizations", "access"):
        refused = client.get(SECTIONS[key], headers=token(CUSTOMER))
        check(f"a workspace Owner is refused 403 on the {key} panel as well",
              refused.status_code == 403 and refused.json()["role"] == "owner",
              f"{refused.status_code} {refused.text[:120]}")
    probe = client.get("/api/v1/admin/session", headers=token(CUSTOMER)).json()
    check("the session probe never leaks the allow-list",
          probe["isPlatformAdmin"] is False and OPERATOR not in str(probe["identifiersChecked"]),
          str(probe["identifiersChecked"]))

    # ── 3. Honesty of the numbers ────────────────────────────────────────────
    group("3. NO DATA beats a fabricated zero")
    overview = section(client, "overview")
    check("follow-up completion rate is null (not 0%) with no decisions recorded",
          overview["outcomeFollowUps"]["total"] == 0
          and overview["outcomeFollowUps"]["completionRate"] is None)
    outcomes = section(client, "outcomes")
    check("followed-rate and lag are null on an empty outcome set",
          outcomes["followedRate"]["rate"] is None
          and outcomes["daysToFollowUp"]["average"] is None)
    ai = section(client, "ai_health")
    check("AI health says why it is empty instead of showing 100% uptime",
          ai["usage"]["providerHealthEvents"] == 0
          and str(ai["usage"]["emptyReason"]).startswith("NO DATA")
          and ai["fallbacks"]["fallbackRate"] is None)
    check("no trust band is called calibration below 10 completed outcomes",
          outcomes["decisionLearning"]["calibration"]["reportableBands"] == [])
    billing = section(client, "billing")
    check("revenue with no recorded amounts stays null, not KES 0",
          billing["revenue"]["collectedInWindow"] is None)
    for key in SECTIONS:
        body = section(client, key)
        bad = [n for n in body["dataNotes"] if "query failed" in n]
        check(f"{key}: every metric came from a query that ran", not bad, str(bad))

    # ── 4. Panel coverage ────────────────────────────────────────────────────
    group("4. Panel coverage (mission panels)")
    check("Phase 1 Overview: organizations, users, active users, assessments, reports, conversations, follow-ups",
          {"total", "teamWorkspaces"} <= set(overview["organizations"])
          and {"total", "activeInWindow"} <= set(overview["users"])
          and "total" in overview["assessments"] and "exportedTotal" in overview["reports"]
          and "total" in overview["conversations"] and "total" in overview["outcomeFollowUps"])
    users = section(client, "users")
    check("Phase 2 User Management: users, organizations, plans, roles, activity",
          all(k in users for k in ("users", "organizations", "plans", "roles", "activity")))
    check("Phase 3 Billing: PayChangu, plan status, upgrade history, failed payments",
          all(k in billing for k in ("paychangu", "planStatus", "upgradeHistory", "failedPayments")))
    check("Phase 4 AI Health names all five providers plus Document Intelligence",
          {p["id"] for p in ai["providers"]} == {"openai", "groq", "gemini", "openrouter", "huggingface"}
          and "documentIntelligence" in ai)
    check("Phase 4 AI Health reports usage, failures and fallbacks",
          all(k in ai for k in ("usage", "failures", "fallbacks")))
    check("Phase 5 Outcome Intelligence: follow-up completion, pending outcomes, decision learning",
          all(k in outcomes for k in ("followUpCompletion", "pendingOutcomes", "decisionLearning")))
    audit = section(client, "audit")
    check("Phase 6 Audit Logs: creation, deletes, role changes, billing buckets",
          {"assessmentCreation", "deletes", "roleChanges", "billingEvents"} <= set(audit["totals"]))
    for key, label, rows_key in (
        ("organizations", "Organizations", "organizations"),
        ("assessments", "Assessments", "assessments"),
        ("reports", "Reports", "reports"),
        ("conversations", "Conversations", "conversations"),
    ):
        body = section(client, key)
        check(f"{label} panel returns its rows, its totals and its own provenance",
              {"generatedAt", "windowDays", "totals", "dataNotes", rows_key} <= set(body),
              str(sorted(body))[:200])
    access_body = section(client, "access")
    check("the Administrators panel returns the role planes, the store state and the roster",
          {"generatedAt", "windowDays", "platformRole", "orgRoles", "store", "breakGlass",
           "roleDistribution", "admins", "dataNotes"} <= set(access_body), str(sorted(access_body)))
    org_panel = section(client, "organizations")
    check("the Organizations panel carries the subscription state an administrator acts on",
          not org_panel["organizations"]
          or {"plan", "billingStatus", "needsAttention"} <= set(org_panel["organizations"][0]),
          str(sorted(org_panel["organizations"][0]))[:200] if org_panel["organizations"] else "no rows")
    access_panel = access_body
    check("the Administrators panel shows the two role planes as separate structures",
          {r["id"] for r in access_panel["orgRoles"]} >= {"owner", "admin", "reviewer"}
          and access_panel["platformRole"]["id"] == PLATFORM_ADMIN_ROLE
          and len(access_panel["platformRole"]["capabilities"]) == len(MISSION_CAPABILITIES) + 1,
          str(access_panel["platformRole"]))
    check("no organization role grants a single platform capability",
          all(not r["platformCapabilities"] for r in access_panel["orgRoles"]),
          str([(r["id"], r["platformCapabilities"]) for r in access_panel["orgRoles"]]))

    # ── 5. Cross-workspace reading ───────────────────────────────────────────
    group("5. Platform-wide (cross-workspace) reads")
    ops_org = repo.ensure_personal_org(OPERATOR)
    record_event("assessment.created", org_id=customer_org.id, user_id=CUSTOMER)
    record_event("document.deleted", org_id=customer_org.id, user_id=CUSTOMER)
    record_event("org.role_changed", org_id=customer_org.id, user_id=CUSTOMER)
    record_event("billing.plan_changed", org_id=customer_org.id, user_id=CUSTOMER)
    record_event("report.exported", org_id=customer_org.id, user_id=CUSTOMER,
                 metadata={"reportKind": "one_pager", "format": "pdf"})
    record_event("report.exported", org_id=ops_org.id, user_id=OPERATOR,
                 metadata={"reportKind": "memo", "format": "pdf"})
    record_event("provider.health", org_id=ops_org.id, user_id=OPERATOR,
                 metadata={"provider_used": "gemini", "fallback_triggered": 0,
                           "response_time_ms": 1234})
    BillingRepository(os.environ["KULIMA_DB_PATH"]).update_subscription(
        customer_org.id, plan="professional", status="past_due", amount=49.0, currency="USD")

    overview = section(client, "overview")
    check("overview counts workspaces and users across every organization",
          overview["organizations"]["total"] >= 2 and overview["users"]["total"] >= 2,
          str(overview["organizations"]))
    users = section(client, "users")
    check("user management lists identities from more than one workspace",
          {OPERATOR, CUSTOMER} <= {u["userId"] for u in users["users"]})
    check("the billing screen surfaces a subscription that needs attention",
          any(a["orgId"] == customer_org.id and a["status"] == "past_due"
              for a in section(client, "billing")["planStatus"]["attention"]))
    ai = section(client, "ai_health")
    gemini = next(p for p in ai["providers"] if p["id"] == "gemini")
    check("a recorded provider.health event shows up as real usage",
          gemini["assessmentsUsingIt"] == 1 and gemini["avgResponseMs"] == 1234.0,
          str(gemini))
    narrowed = section(client, "audit", "?bucket=deletes")
    check("audit bucket filter narrows the page but keeps the other counts readable",
          {e["eventType"] for e in narrowed["events"]} == {"document.deleted"}
          and narrowed["totals"]["roleChanges"] >= 1
          and narrowed["count"] == narrowed["totals"]["matchingEvents"],
          str(narrowed["totals"]))
    check("an unknown bucket reports empty with a note instead of silently meaning 'all'",
          section(client, "audit", "?bucket=bogus")["count"] == 0)
    orgs_list = section(client, "organizations")
    check("the Organizations panel lists workspaces belonging to different owners",
          {customer_org.id, ops_org.id} <= {o["orgId"] for o in orgs_list["organizations"]},
          str([o["orgId"] for o in orgs_list["organizations"]]))
    check("the Organizations panel marks the workspace whose billing needs attention",
          any(o["orgId"] == customer_org.id and o["needsAttention"] for o in orgs_list["organizations"]),
          str([(o["orgId"], o.get("billingStatus")) for o in orgs_list["organizations"]]))
    reports = section(client, "reports")
    check("Reports derive from export events in every workspace, with kind and format",
          reports["totals"]["exports"] >= 2
          and {r["reportKind"] for r in reports["reports"]} >= {"one_pager", "memo"},
          str(reports["totals"]))
    check("the Reports panel states that a report is an event, not a stored file",
          "no report table" in str(reports["sourceNote"]).lower()
          or "audit event" in str(reports["sourceNote"]).lower(), str(reports["sourceNote"]))
    assessments = section(client, "assessments")
    check("the Assessments panel agrees with the overview's platform-wide count",
          assessments["totals"]["assessments"] == overview["assessments"]["total"],
          f'{assessments["totals"]["assessments"]} vs {overview["assessments"]["total"]}')
    convos = section(client, "conversations")
    check("the Conversations panel returns counts and titles, never message bodies",
          not any(k in row for row in convos["conversations"] for k in ("content", "body", "text")),
          str(sorted(convos["conversations"][0]))[:200] if convos["conversations"] else "no rows")
    bad_window = client.get(SECTIONS["overview"] + "?window_days=0", headers=token(OPERATOR))
    bad_limit = client.get(SECTIONS["audit"] + "?limit=5000", headers=token(OPERATOR))
    check("window and page-size parameters are bounded by the API",
          bad_window.status_code == 422 and bad_limit.status_code == 422,
          f"{bad_window.status_code}/{bad_limit.status_code}")

    # ── 6. Reads are safe, and they audit themselves ─────────────────────────
    group("6. Panel reads change nothing, and every read is audited")
    headers = token(OPERATOR)
    client.get("/api/v1/admin/session", headers=headers)
    for route in SECTIONS.values():  # warm-up: first read provisions + creates tables
        client.get(route, headers=headers)
    before = table_counts(os.environ["KULIMA_DB_PATH"])
    views = AuditRepository(os.environ["KULIMA_DB_PATH"])
    seen_before = len([e for e in views.list(org_id=None, limit=1000)
                       if e["eventType"] == "admin.console_viewed"])
    for route in SECTIONS.values():
        client.get(route, headers=headers)
    after = table_counts(os.environ["KULIMA_DB_PATH"])
    check("opening every panel changes no platform data",
          before == after, str({k: (before[k], after[k]) for k in before if before[k] != after.get(k)}))
    entries = [e for e in views.list(org_id=None, limit=2000) if e["eventType"] == "admin.console_viewed"]
    check("every panel view is written to the audit log",
          len(entries) - seen_before == len(SECTIONS), f"{len(entries) - seen_before} new entries")
    check("the log records which panel the administrator opened",
          {k.replace("_", "-") for k in SECTIONS} <= {e["metadata"]["section"] for e in entries},
          str({e["metadata"]["section"] for e in entries}))
    check("each entry records the grant path and capability count behind the access",
          all(e["metadata"].get("via") in ("platform_role", "env_allow_list")
              and isinstance(e["metadata"].get("capabilities"), int)
              for e in entries),
          str({(e["metadata"]["section"], e["metadata"].get("via")) for e in entries}))
    check("the console's own action is labelled for humans in the audit vocabulary",
          EVENT_TYPES.get("admin.console_viewed") == "Admin Console Opened",
          str(EVENT_TYPES.get("admin.console_viewed")))

    # ── 7. Frontend surface ──────────────────────────────────────────────────
    group("7. Frontend screens and navigation")
    app_dir = FRONTEND / "app"
    routes = build_routes(app_dir)
    pages = {
        "overview": app_dir / "admin" / "page.tsx",
        "users": app_dir / "admin" / "users" / "page.tsx",
        "billing": app_dir / "admin" / "billing" / "page.tsx",
        "ai_health": app_dir / "admin" / "ai-health" / "page.tsx",
        "outcomes": app_dir / "admin" / "outcomes" / "page.tsx",
        "audit": app_dir / "admin" / "audit" / "page.tsx",
        "organizations": app_dir / "admin" / "organizations" / "page.tsx",
        "assessments": app_dir / "admin" / "assessments" / "page.tsx",
        "reports": app_dir / "admin" / "reports" / "page.tsx",
        "conversations": app_dir / "admin" / "conversations" / "page.tsx",
        "access": app_dir / "admin" / "access" / "page.tsx",
    }
    check("every mission panel exists as a screen and resolves as a Next.js route",
          all(p.exists() for p in pages.values())
          and all(route_exists(routes, f"/admin/{'' if k == 'overview' else k.replace('_', '-')}")
                  for k in pages))
    check("the nine mission panels are all present, plus Overview and Administrators",
          {"organizations", "users", "assessments", "reports", "conversations",
           "outcomes", "billing", "ai_health", "audit"} <= set(pages), str(sorted(pages)))
    shells = read(FRONTEND / "components" / "AdminConsole" / "AdminConsoleShell.tsx")
    ui = read(FRONTEND / "components" / "AdminConsole" / "adminUi.tsx")
    lib = read(FRONTEND / "lib" / "admin.ts")
    check("every screen renders inside the platform gate",
          all("AdminConsoleShell" in read(p) for p in pages.values())
          and all(f'section="{k.replace("_", "-") if k != "overview" else k}"' in read(p)
                  for k, p in pages.items()))
    check("the gate denies on not_configured / not_allowlisted before any data renders",
          "isPlatformAdmin" in shells and "not_configured" in shells and "not_allowlisted" in shells)
    check("the gate speaks of the stored role, not an allow-list of emails",
          "PLATFORM_ADMIN" in shells and "grantedBy" in shells
          and "env_allow_list" in shells and "capabilities" in shells)
    check("each panel is declared with the capability its route requires",
          shells.count("capability: '") >= len(pages) and "hasCapability" in shells)
    check("admin screens stay out of the customer workspace shell",
          not any("PilotWorkspaceShell" in read(p) for p in pages.values()))
    check("every admin screen handles a 403 and an error before showing numbers",
          all("FetchStatus" in read(p) for p in pages.values())
          and "denied" in ui and "403" in ui)
    check("the client library reaches every console panel",
          all(f"/api/v1/admin/{name}" in lib
              for name in ("session", *tuple(SECTIONS[key].rsplit("/", 1)[-1] for key in SECTIONS))))
    lib_flat = re.sub(r"\s+", " ", lib)
    write_calls = re.findall(r"mutate\w*(?:<[^>]*>)?\(\s*'([A-Z]+)',\s*[`'\"]([^`'\"]+)", lib_flat)
    check("the client's whole write surface is the declared mutations on the two administration panels",
          len(write_calls) == len(MUTATION_ROUTES)
          and sorted({m for m, _ in write_calls}) == ["DELETE", "PATCH", "POST", "PUT"]
          and all(p.startswith("/api/v1/admin/organizations") or p.startswith("/api/v1/admin/access")
                  for _, p in write_calls), str([p for _, p in write_calls]))
    check("the read helpers stay GET-only",
          not re.search(r"call<[^>]*>\([^)]*method:", lib)
          and "cache: 'no-store'" in lib)
    writers = {k for k, p in pages.items() if "useAdminAction" in read(p)}
    check("writes exist on exactly the two operator panels, nowhere else",
          writers == {"organizations", "access"}, str(sorted(writers)))
    check("the Organizations panel sends only the fields the administrator actually changed",
          "!== before." in read(pages["organizations"])
          and "agreement" in read(pages["organizations"]).lower()
          and "reason" in read(pages["organizations"]))
    check("a null rate renders NO DATA rather than 0%",
          "NO DATA" in ui and "value === null" in ui)
    sidebar = read(FRONTEND / "components" / "NavigationSidebar" / "NavigationSidebar.tsx")
    check("the console link appears only after the backend confirms platform access",
          "usePlatformAdmin" in sidebar and "isPlatformAdmin === true" in sidebar
          and "PLATFORM_OPS_ITEM" in sidebar)
    hook = read(FRONTEND / "hooks" / "usePlatformAdmin.ts")
    check("the platform probe fails closed on a rejected request",
          ".catch(" in hook and "return null" in hook)
    check("no admin screen renders raw HTML from API payloads",
          not any("dangerouslySetInnerHTML" in read(p) for p in pages.values()))

    # ── 8. The role plane ────────────────────────────────────────────────────
    group("8. PLATFORM_ADMIN: stored role, capabilities, audited writes")
    admins = PlatformAdminRepository(os.environ["KULIMA_DB_PATH"])
    all_caps = {c.value for c in PlatformCapability}
    saved_ids = os.environ.get("KULIMA_PLATFORM_ADMIN_USER_IDS")
    org_url = f"/api/v1/admin/organizations/{customer_org.id}"

    grant = client.post("/api/v1/admin/access/admins", headers=token(OPERATOR),
                        json={"email": SECOND_ADMIN, "displayName": "Second Administrator"})
    check("an existing platform administrator grants PLATFORM_ADMIN to a peer",
          grant.status_code == 201 and grant.json()["outcome"] == "granted"
          and grant.json()["activeCount"] >= 1, f"{grant.status_code} {grant.text[:160]}")
    role_row = admins.find(email=SECOND_ADMIN)
    check("the grant is a row in platform_admins, never a membership row",
          role_row is not None and role_row.role == PLATFORM_ADMIN_ROLE
          and role_row.status == "active", str(role_row))
    check("the stored role holds exactly the platform's declared capabilities",
          role_row is not None and {c.value for c in role_row.capabilities} == all_caps
          and set(MISSION_CAPABILITIES.values()) <= all_caps,
          str(sorted(c.value for c in role_row.capabilities)) if role_row else "no row")
    check("the grant is audited under its own event type",
          bool(events("admin.platform_admin_granted")), str(sorted(
              e["eventType"] for e in events("admin.platform_admin_granted"))))

    os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = ""
    second = client.get("/api/v1/admin/session", headers=token("second-subject", email=SECOND_ADMIN))
    role_session = second.json() if second.status_code == 200 else {}
    check("the stored role opens the console with no environment configured at all",
          second.status_code == 200 and role_session.get("isPlatformAdmin") is True
          and role_session.get("grantedBy") == "platform_role",
          f"{second.status_code} {second.text[:160]}")
    check("it is matched on the session's verified email claim, not a row a customer writes",
          role_session.get("matchedVia") == "verified_email"
          and SECOND_ADMIN in role_session.get("identifiersChecked", []),
          str(role_session.get("identifiersChecked")))
    check("a stored administrator is reported as the role, not as break-glass",
          role_session.get("platformRole") == PLATFORM_ADMIN_ROLE
          and "break-glass" not in str(role_session.get("roleLabel")),
          str(role_session.get("roleLabel")))
    stored_panel = client.get(SECTIONS["access"], headers=token("second-subject", email=SECOND_ADMIN))
    roster = stored_panel.json().get("admins", []) if stored_panel.status_code == 200 else []
    check("the stored role reaches the panel that manages the role itself",
          stored_panel.status_code == 200
          and any(a.get("email") == SECOND_ADMIN and a.get("status") == "active" for a in roster)
          and stored_panel.json()["store"]["activeCount"] >= 1,
          f"{stored_panel.status_code} {stored_panel.text[:160]}")
    check("the panel names the environment variables that act as break-glass, and nothing else",
          set(stored_panel.json()["breakGlass"]["envNames"])
          == {"KULIMA_ADMIN_EMAILS", "KULIMA_PLATFORM_ADMIN_USER_IDS"},
          str(stored_panel.json()["breakGlass"]))
    glass = "glass-principal"
    os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = glass
    glass_session = client.get("/api/v1/admin/session", headers=token(glass)).json()
    glass_row = admins.find(user_id=glass)
    check("a configured identity is provisioned into the roster, so its actions are attributed to the role",
          glass_session["isPlatformAdmin"] is True and glass_row is not None
          and glass_row.source == "bootstrap"
          and glass_session["grantedBy"] == "platform_role"
          and glass_session["matchedVia"] == "session_subject", str(glass_session)[:200])
    admins.revoke(user_id=glass, revoked_by="probe isolation")
    revoked_glass = client.get("/api/v1/admin/session", headers=token(glass)).json()
    check("with its stored row revoked, the configured identity still gets in — labelled break-glass",
          revoked_glass["isPlatformAdmin"] is True
          and revoked_glass["grantedBy"] == "env_allow_list"
          and "break-glass" in str(revoked_glass["roleLabel"]), str(revoked_glass)[:200])
    check("a revoked grant is never silently re-provisioned by the next gate call",
          admins.find(user_id=glass).status == "revoked", str(admins.find(user_id=glass)))
    os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = saved_ids or ""
    if saved_ids is not None:
        os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = saved_ids

    forged = client.get(SECTIONS["overview"] + "?capability=view_audit&isPlatformAdmin=true",
                        headers=token(CUSTOMER))
    check("capability is never a request parameter — a forged one changes nothing",
          forged.status_code == 403, str(forged.status_code))
    anon_write = client.put(org_url + "/subscription", json={"plan": "enterprise"})
    owner_write = client.put(org_url + "/subscription", headers=token(CUSTOMER), json={"plan": "pro"})
    check("an anonymous write is refused before its body is interpreted",
          anon_write.status_code == 401, str(anon_write.status_code))
    check("a workspace Owner cannot change another workspace's subscription",
          owner_write.status_code == 403 and owner_write.json()["code"] == "PLATFORM_ADMIN_REQUIRED",
          f"{owner_write.status_code} {owner_write.text[:160]}")
    check("the refusal names the missing role and leaks nothing else",
          owner_write.json().get("role") == "owner"
          and SECOND_ADMIN not in str(owner_write.json())
          and "paychangu" not in str(owner_write.json()).lower(), str(owner_write.json())[:200])
    check("the denied write changed no subscription",
          BillingRepository(os.environ["KULIMA_DB_PATH"]).get_subscription(customer_org.id)["plan"]
          == "professional", str(BillingRepository(os.environ["KULIMA_DB_PATH"])
                                 .get_subscription(customer_org.id)))

    upgrade = client.put(org_url + "/subscription", headers=token(OPERATOR),
                         json={"plan": "pro", "reason": "probe upgrade"})
    check("managing a subscription reuses the customer billing engine and reports before/after",
          upgrade.status_code == 200 and upgrade.json()["after"]["plan"] == "pro"
          and upgrade.json()["planResult"]["changed"] is True
          and upgrade.json()["before"]["plan"] == "professional",
          f"{upgrade.status_code} {upgrade.text[:200]}")
    check("the platform sees the change on the very next read",
          any(o["orgId"] == customer_org.id and o["plan"] == "pro"
              for o in section(client, "organizations")["organizations"]),
          str([(o["orgId"], o["plan"]) for o in section(client, "organizations")["organizations"]]))
    check("a platform subscription change is audited on both planes",
          bool(events("admin.subscription_updated")) and bool(events("billing.plan_changed")))
    field_refused = client.put(org_url + "/subscription", headers=token(OPERATOR),
                               json={"paychanguRef": "forged-tx"})
    check("an undeclared field in a mutation body is refused by name, never dropped",
          field_refused.status_code == 422 and "paychanguRef" in str(field_refused.json()),
          str(field_refused.json())[:200])
    ent_refused = client.put(org_url + "/subscription", headers=token(OPERATOR),
                             json={"plan": "enterprise"})
    check("the Enterprise gate survives the platform path — activation first, always",
          ent_refused.status_code == 422
          and ent_refused.json()["code"] == "ENTERPRISE_ACTIVATION_REQUIRED",
          str(ent_refused.json())[:200])
    agree_refused = client.post(org_url + "/enterprise-activation", headers=token(OPERATOR),
                                json={"action": "approve", "agreementAccepted": False})
    approved = client.post(org_url + "/enterprise-activation", headers=token(OPERATOR),
                           json={"action": "approve", "agreementAccepted": True,
                                 "contact": SECOND_ADMIN})
    check("approving an enterprise account requires the agreement to be ticked explicitly",
          agree_refused.status_code == 422
          and agree_refused.json()["code"] == "AGREEMENT_REQUIRED"
          and approved.status_code == 200 and approved.json()["after"] == "approved"
          and approved.json()["checkoutAllowed"] is True,
          f"{agree_refused.status_code}/{approved.status_code} {approved.text[:160]}")
    suspended = client.post(org_url + "/account-status", headers=token(OPERATOR),
                            json={"status": "suspended", "reason": "probe suspension"})
    reactivated = client.post(org_url + "/account-status", headers=token(OPERATOR),
                              json={"status": "active", "reason": "probe end"})
    check("suspending and reactivating an account use the billing engine's own transitions",
          suspended.status_code == 200 and suspended.json()["after"]["status"] == "suspended"
          and reactivated.status_code == 200 and reactivated.json()["after"]["status"] == "active",
          f"{suspended.status_code}/{reactivated.status_code}")
    check("each account transition writes its own audit event with before/after state",
          bool(events("admin.account_suspended")) and bool(events("admin.account_reactivated"))
          and any(e["metadata"].get("before") and e["metadata"].get("after")
                  for e in events("admin.account_suspended")),
          str([sorted(e["metadata"]) for e in events("admin.account_suspended")][:1]))

    renamed = client.patch(org_url, headers=token(OPERATOR),
                           json={"name": "Customer Capital Ltd", "reason": "probe rename"})
    check("renaming a workspace is audited and lands on the organization row",
          renamed.status_code == 200 and renamed.json()["name"] == "Customer Capital Ltd"
          and repo.get_org(customer_org.id).name == "Customer Capital Ltd"
          and any(e["metadata"].get("after", {}).get("name") == "Customer Capital Ltd"
                  for e in events("admin.org_updated")),
          str(renamed.json())[:160])
    provisioned = client.post("/api/v1/admin/organizations", headers=token(OPERATOR),
                              json={"name": "Probe Provisioning", "plan": "free",
                                    "intendedOwnerEmail": "not-signed-in@kulima.example"})
    new_org = provisioned.json().get("organization", {}) if provisioned.status_code == 201 else {}
    check("a platform administrator can provision a workspace for the platform",
          provisioned.status_code == 201 and new_org.get("name") == "Probe Provisioning"
          and bool(new_org.get("orgId")), f"{provisioned.status_code} {provisioned.text[:160]}")
    ghost_owner = client.post("/api/v1/admin/organizations", headers=token(OPERATOR),
                              json={"name": "Nowhere Co", "ownerUserId": "never-signed-in"})
    check("an owner id that has never signed in is refused instead of stranding the account",
          ghost_owner.status_code == 422 and ghost_owner.json()["code"] == "OWNER_NOT_SIGNED_IN",
          str(ghost_owner.json())[:160])
    conn = sqlite3.connect(os.environ["KULIMA_DB_PATH"])
    try:
        members = conn.execute("SELECT COUNT(*) FROM organization_members WHERE org_id = ?",
                               (new_org.get("orgId"),)).fetchone()[0]
    finally:
        conn.close()
    check("a typed email at provisioning is a note, never a membership row",
          members == 1, str(members))

    third = "third-admin@kulima.example"
    client.post("/api/v1/admin/access/admins", headers=token(OPERATOR), json={"email": third})
    dropped = client.delete(f"/api/v1/admin/access/admins/{third}", headers=token(OPERATOR),
                            params={"reason": "probe cleanup"})
    revoked_row = admins.find(email=third)
    check("revocation is accepted while more than one administrator remains",
          dropped.status_code == 200 and dropped.json()["revoked"] is True
          and dropped.json()["activeCount"] >= 1,
          f"{dropped.status_code} {dropped.text[:160]}")
    check("a revoked grant stays in history as a revoked row instead of being deleted",
          revoked_row is not None and revoked_row.status == "revoked"
          and bool(events("admin.platform_admin_revoked")), str(revoked_row))
    check("revocation carries the reason the administrator typed into the audit event",
          any(e["metadata"].get("reason") == "probe cleanup"
              for e in events("admin.platform_admin_revoked")),
          str([e["metadata"] for e in events("admin.platform_admin_revoked")])[:200])

    # Reduce the roster to exactly one stored administrator so the anti-lockout
    # rule is observable whatever else the environment happened to provision.
    for extra in [a for a in admins.list_admins() if (a.email or "") != SECOND_ADMIN]:
        client.delete(f"/api/v1/admin/access/admins/{extra.email or extra.user_id}",
                      headers=token(OPERATOR), params={"reason": "probe isolation"})
    check("the roster can be reduced to a single stored administrator",
          admins.count_active() == 1, str(admins.count_active()))
    last = client.delete(f"/api/v1/admin/access/admins/{SECOND_ADMIN}", headers=token(OPERATOR))
    check("the last stored administrator cannot be revoked — the platform cannot lock itself out",
          last.status_code >= 400 and last.json()["code"] == "LAST_ADMIN",
          f"{last.status_code} {last.text[:160]}")
    check("a refused revocation leaves the role fully working",
          admins.find(email=SECOND_ADMIN).status == "active"
          and client.get(SECTIONS["users"],
                         headers=token("second-subject", email=SECOND_ADMIN)).status_code == 200)
    nameless = client.post("/api/v1/admin/access/admins", headers=token(OPERATOR),
                           json={"displayName": "Nobody At All"})
    check("a grant with no provable identity is refused rather than stored as a display name",
          nameless.status_code == 422 and nameless.json()["code"] == "IDENTITY_REQUIRED",
          str(nameless.json())[:160])
    check("no roster row exists without an email or a user id to match a session against",
          all(a.email or a.user_id for a in admins.list_admins(include_revoked=True)),
          str([(a.principal, a.email, a.user_id) for a in admins.list_admins(include_revoked=True)]))
    check("PLATFORM_ADMIN is not a value any membership endpoint can write",
          PLATFORM_ADMIN_ROLE not in {r.value for r in Role},
          str(sorted(r.value for r in Role)))
    if saved_ids is not None:
        os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = saved_ids

    # ── Result ───────────────────────────────────────────────────────────────
    total = len(PASSED) + len(FAILED)
    print("\n" + "=" * 62)
    print(f"Platform Administration checks passed: {len(PASSED)}/{total}")
    if FAILED:
        print("FAILED:")
        for name in FAILED:
            print(f"  - {name}")
        print("VERDICT: ADMIN_CONSOLE_BLOCKED")
        print("=" * 62)
        return 1
    print("VERDICT: ADMIN_CONSOLE_READY")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
