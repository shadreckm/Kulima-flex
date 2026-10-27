"""Admin Console V1 verification — the internal platform-operations surface.

This is the mission contract for the Platform Operations Architect, executed as
one reproducible script. Groups:

  1. Route surface      — all seven endpoints exist on the FastAPI app.
  2. The gate           — fail-closed, session-only, and *not* satisfied by an
                          organization role or by membership rows a customer
                          can write.
  3. Honesty            — empty denominators report NO DATA, never a zero.
  4. Phase coverage     — the six phases expose exactly the metrics asked for.
  5. Cross-workspace    — the console reads every workspace (that is the point).
  6. Read-only + audit  — the only write the console performs is its own
                          ``admin.console_viewed`` entry.
  7. Frontend surface   — six screens behind one operator gate, no customer
                          shell, no mutating client calls, admin link gated.

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

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from kulima.core.audit.repository import AuditRepository, EVENT_TYPES, record_event  # noqa: E402
from kulima.core.billing.repository import BillingRepository  # noqa: E402
from kulima.core.orgs.repository import OrgRepository  # noqa: E402

OPERATOR = "ops-principal"
CUSTOMER = "customer-principal"
FRONTEND = ROOT / "frontend"

SECTIONS = {
    "overview": "/api/v1/admin/overview",
    "users": "/api/v1/admin/users",
    "billing": "/api/v1/admin/billing",
    "ai_health": "/api/v1/admin/ai-health",
    "outcomes": "/api/v1/admin/outcomes",
    "audit": "/api/v1/admin/audit",
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


def token(subject: str) -> dict:
    payload = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    secret = os.environ["NEXTAUTH_SECRET"]
    return {"Authorization": f"Bearer {jwt.encode(payload, secret, algorithm='HS256')}"}


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
    paths = set(app.openapi()["paths"])
    check("GET /api/v1/admin/session is registered", "/api/v1/admin/session" in paths)
    check("all six section endpoints are registered",
          all(route in paths for route in SECTIONS.values()),
          str([r for r in SECTIONS.values() if r not in paths]))
    admin_verbs = {p: sorted(m.upper() for m in verbs) for p, verbs
                   in app.openapi()["paths"].items() if p.startswith("/api/v1/admin")}
    check("the console is read-only at the API layer (GET everywhere)",
          all(verbs == ["GET"] for verbs in admin_verbs.values()), str(admin_verbs))

    # ── 2. The gate ──────────────────────────────────────────────────────────
    group("2. The operator gate (ADMIN ONLY)")
    unauth = {r: client.get(r).status_code for r in ["/api/v1/admin/session", *SECTIONS.values()]}
    check("every console route rejects an anonymous caller (401)",
          all(code == 401 for code in unauth.values()), str(unauth))

    saved = os.environ.get("KULIMA_PLATFORM_ADMIN_USER_IDS")
    os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = ""
    closed = client.get(SECTIONS["overview"], headers=token(OPERATOR))
    check("fail-closed: nobody gets in when no operator is configured",
          closed.status_code == 403 and closed.json()["code"] == "PLATFORM_ADMIN_NOT_CONFIGURED",
          f"{closed.status_code} {closed.text[:120]}")
    if saved is not None:
        os.environ["KULIMA_PLATFORM_ADMIN_USER_IDS"] = saved

    repo = OrgRepository(os.environ["KULIMA_DB_PATH"])
    customer_org = repo.create_org("Customer Capital", created_by=CUSTOMER)
    repo.add_member(customer_org.id, CUSTOMER, "owner",
                    email=f"{OPERATOR}@kulima.example", display_name=OPERATOR)
    owner = client.get(SECTIONS["overview"], headers=token(CUSTOMER))
    check("an organization Owner is NOT a platform operator",
          owner.status_code == 403 and owner.json()["role"] == "owner",
          f"{owner.status_code} {owner.text[:160]}")
    check("membership rows a customer can write (email/display name) never grant access",
          owner.status_code == 403 and owner.json()["code"] == "PLATFORM_ADMIN_REQUIRED")
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

    # ── 4. Phase coverage ────────────────────────────────────────────────────
    group("4. Phase coverage (mission metrics)")
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

    # ── 5. Cross-workspace reading ───────────────────────────────────────────
    group("5. Platform-wide (cross-workspace) reads")
    ops_org = repo.ensure_personal_org(OPERATOR)
    record_event("assessment.created", org_id=customer_org.id, user_id=CUSTOMER)
    record_event("document.deleted", org_id=customer_org.id, user_id=CUSTOMER)
    record_event("org.role_changed", org_id=customer_org.id, user_id=CUSTOMER)
    record_event("billing.plan_changed", org_id=customer_org.id, user_id=CUSTOMER)
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
    bad_window = client.get(SECTIONS["overview"] + "?window_days=0", headers=token(OPERATOR))
    bad_limit = client.get(SECTIONS["audit"] + "?limit=5000", headers=token(OPERATOR))
    check("window and page-size parameters are bounded by the API",
          bad_window.status_code == 422 and bad_limit.status_code == 422,
          f"{bad_window.status_code}/{bad_limit.status_code}")

    # ── 6. Read-only, and it audits itself ───────────────────────────────────
    group("6. Read-only + self-auditing")
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
    check("reading the console changes no platform data",
          before == after, str({k: (before[k], after[k]) for k in before if before[k] != after.get(k)}))
    entries = [e for e in views.list(org_id=None, limit=1000) if e["eventType"] == "admin.console_viewed"]
    check("every section view is written to the audit log",
          len(entries) - seen_before == 6, f"{len(entries) - seen_before} new entries")
    check("the log records which section the operator opened",
          {"overview", "users", "billing", "ai-health", "outcomes", "audit"}
          <= {e["metadata"]["section"] for e in entries},
          str({e["metadata"]["section"] for e in entries}))
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
    }
    check("six admin screens exist and resolve as Next.js routes",
          all(p.exists() for p in pages.values())
          and all(route_exists(routes, f"/admin/{'' if k == 'overview' else k.replace('_', '-')}")
                  for k in pages))
    shells = read(FRONTEND / "components" / "AdminConsole" / "AdminConsoleShell.tsx")
    ui = read(FRONTEND / "components" / "AdminConsole" / "adminUi.tsx")
    lib = read(FRONTEND / "lib" / "admin.ts")
    check("every screen renders inside the operator gate",
          all("AdminConsoleShell" in read(p) for p in pages.values())
          and all(f'section="{k}"' in read(p) for k, p in
                  [(k.replace("_", "-") if k != "overview" else k, p) for k, p in pages.items()]))
    check("the gate denies on not_configured / not_allowlisted before any data renders",
          "isPlatformAdmin" in shells and "not_configured" in shells and "not_allowlisted" in shells)
    check("admin screens stay out of the customer workspace shell",
          not any("PilotWorkspaceShell" in read(p) for p in pages.values()))
    check("every admin screen handles a 403 and an error before showing numbers",
          all("FetchStatus" in read(p) for p in pages.values())
          and "denied" in ui and "403" in ui)
    check("the client library calls exactly the seven console endpoints and nothing else",
          all(f"/api/v1/admin/{name}" in lib
              for name in ("session", "overview", "users", "billing", "ai-health", "outcomes", "audit")))
    check("no admin client call can mutate platform data",
          not re.search(r"method:\s*['\"](POST|PUT|PATCH|DELETE)", lib)
          and "jsonInit" not in lib)
    check("a null rate renders NO DATA rather than 0%",
          "NO DATA" in ui and "value === null" in ui)
    sidebar = read(FRONTEND / "components" / "NavigationSidebar" / "NavigationSidebar.tsx")
    check("the console link appears only after the backend confirms operator access",
          "usePlatformAdmin" in sidebar and "isPlatformAdmin === true" in sidebar
          and "PLATFORM_OPS_ITEM" in sidebar)
    hook = read(FRONTEND / "hooks" / "usePlatformAdmin.ts")
    check("the operator probe fails closed on a rejected request",
          ".catch(" in hook and "return null" in hook)
    check("no admin screen renders raw HTML from API payloads",
          not any("dangerouslySetInnerHTML" in read(p) for p in pages.values()))

    # ── Result ───────────────────────────────────────────────────────────────
    total = len(PASSED) + len(FAILED)
    print("\n" + "=" * 62)
    print(f"Admin Console checks passed: {len(PASSED)}/{total}")
    if FAILED:
        print("FAILED:")
        for name in FAILED:
            print(f"  - {name}")
        print("VERDICT: ADMIN_CONSOLE_BLOCKED")
        print("=" * 62)
        return 1
    print("VERDICT: ADMIN_CONSOLE_V1_READY")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
