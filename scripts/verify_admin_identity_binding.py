"""End-to-end check of the PLATFORM_ADMIN identity binding, over real shapes.

Runs the *production* authorization stack — ``/api/v1/orgs/me`` (sign-in binding),
``/api/v1/admin/session`` (the gate the sidebar probes) and every console panel —
against the identifier shapes the deployed auth chain actually mints, so the
answer comes from the HTTP layer rather than from a reading of the code.

The database is a COPY. A granted session whose row is unbound writes the binding
into the store it resolved, and that write must land in a disposable file, never
in the live workspace database. Live stores are only ever read to locate them.

    python scripts/verify_admin_identity_binding.py [email]

Exit code is 0 only when every assertion passes.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EMAIL = (sys.argv[1] if len(sys.argv) > 1 else "kulimaafrica@gmail.com").strip().lower()

# The capabilities this mission requires the primary administrator to hold.
REQUIRED_CAPABILITIES = [
    "view_users",
    "view_billing",
    "view_provider_health",
    "view_audit",
    "manage_subscriptions",
    "manage_enterprise_accounts",
    "manage_platform_admins",
]

PANELS = {
    "overview": "/api/v1/admin/overview",
    "users": "/api/v1/admin/users",
    "organizations": "/api/v1/admin/organizations",
    "assessments": "/api/v1/admin/assessments",
    "reports": "/api/v1/admin/reports",
    "conversations": "/api/v1/admin/conversations",
    "billing": "/api/v1/admin/billing",
    "ai-health": "/api/v1/admin/ai-health",
    "outcomes": "/api/v1/admin/outcomes",
    "audit": "/api/v1/admin/audit",
    "access": "/api/v1/admin/access",
}

_failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        _failures.append(label)


def read_secret() -> str:
    for candidate in (ROOT / "frontend" / ".env.local", ROOT / "backend" / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("NEXTAUTH_SECRET="):
                value = line.partition("=")[2].strip().strip('"').strip("'")
                if value:
                    return value
    return os.environ.get("NEXTAUTH_SECRET", "")


def resolve_live_db() -> Path:
    """The file the running backend opens, resolved exactly as kulima.config does."""
    for env_file in (ROOT / "backend" / ".env", ROOT / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("KULIMA_DB_PATH=") and not line.strip().startswith("#"):
                    os.environ.setdefault("KULIMA_DB_PATH", line.partition("=")[2].strip().strip('"'))
    raw = os.environ.get("KULIMA_DB_PATH", "founders.db")
    return Path(raw) if os.path.isabs(raw) else (Path.cwd() / raw)


def token_for(secret: str, subject: str, email: str | None = None) -> dict:
    import jwt

    payload = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    if email:
        payload["email"] = email
    return {"Authorization": f"Bearer {jwt.encode(payload, secret, algorithm='HS256')}"}


def main() -> int:
    live = resolve_live_db()
    secret = read_secret()
    print(f"Live database : {live} (exists={live.exists()})")
    print(f"Auth secret   : {'loaded' if secret else 'MISSING'}")
    if not live.exists() or not secret:
        print("Cannot verify without the live store and NEXTAUTH_SECRET.")
        return 2

    # The subject the deployed Google login actually produced, if the store shows one
    # that is not an email address — that is the shape the fix has to survive.
    with sqlite3.connect(live) as conn:
        conn.row_factory = sqlite3.Row
        subjects = [
            str(r["user_id"]) for r in conn.execute(
                "SELECT DISTINCT user_id FROM organization_members"
                " WHERE user_id IS NOT NULL AND user_id NOT LIKE '%@%'"
            )
        ]
        rows = [dict(r) for r in conn.execute(
            "SELECT principal, user_id, email, status FROM platform_admins WHERE email = ?", (EMAIL,))]
    provider_subject = subjects[0] if subjects else None
    print(f"Role rows for : {rows}")
    print(f"Provider sub  : {provider_subject or 'NONE (using a stand-in account id)'}")

    tmp = Path(tempfile.mkdtemp(prefix="kulima_bind_verify_")) / "copy.db"
    shutil.copyfile(live, tmp)
    os.environ["KULIMA_DB_PATH"] = str(tmp)
    os.environ["NEXTAUTH_SECRET"] = secret
    print(f"Test database : {tmp} (copy; the live file is never written)\n")

    from backend.app.core import admin_access
    from backend.app.main import app
    from fastapi.testclient import TestClient
    from kulima.core.orgs import platform_admins

    client = TestClient(app)
    admin_access._bound_subjects.clear()

    def roster() -> dict:
        with sqlite3.connect(tmp) as conn:
            conn.row_factory = sqlite3.Row
            found = conn.execute("SELECT * FROM platform_admins WHERE email = ?", (EMAIL,)).fetchone()
            return dict(found) if found else {}

    # ── 1. Sign-in binding with a provider account id and no email claim yet ──
    print("1. Sign-in binding — GET /api/v1/orgs/me")
    subject = provider_subject or "114064591648239230885"
    whoami = client.get("/api/v1/orgs/me", headers=token_for(secret, subject, EMAIL))
    check("whoami resolves the session", whoami.status_code == 200, str(whoami.status_code))
    check("whoami reports this subject", whoami.json().get("userId") == subject, str(whoami.json().get("userId")))
    bound = roster().get("user_id")
    check("platform_admins.user_id is populated on login", bound == subject, f"user_id={bound!r}")

    # ── 2. The console probe the sidebar depends on ──────────────────────────
    print("\n2. Gate probe — GET /api/v1/admin/session")
    session = client.get("/api/v1/admin/session", headers=token_for(secret, subject)).json()
    check("isPlatformAdmin is true with no email claim", session["isPlatformAdmin"] is True,
          f"reason={session['reason']} matchedVia={session['matchedVia']}")
    check("access came from the stored role, not break-glass", session["grantedBy"] == "platform_role",
          str(session["grantedBy"]))
    check("resolved on the bound subject", session["matchedVia"] == "session_subject", str(session["matchedVia"]))
    check("identity reported as bound", session["identityBound"] == "already_bound", str(session["identityBound"]))
    missing = [c for c in REQUIRED_CAPABILITIES if c not in session["capabilities"]]
    check("all seven required capabilities present", not missing,
          f"missing={missing} held={len(session['capabilities'])}")

    # ── 3. Every panel loads, and user management returns real rows ──────────
    print("\n3. Panels — 11 screens behind the gate")
    for name, route in PANELS.items():
        response = client.get(route, headers=token_for(secret, subject))
        check(f"{name} returns 200", response.status_code == 200,
              f"{response.status_code} {str(response.text)[:90]}")
    users = client.get("/api/v1/admin/users", headers=token_for(secret, subject)).json()
    check("user management lists platform users", users.get("userCount", 0) > 0,
          f"userCount={users.get('userCount')} notes={users.get('dataNotes')}")
    overview = client.get("/api/v1/admin/overview", headers=token_for(secret, subject)).json()
    check("platform analytics report a non-empty denominator",
          overview["organizations"]["total"] > 0,
          f"organizations={overview['organizations']['total']} users={overview['users']['total']}")

    # ── 4. An address-shaped subject with no email claim resolves too ────────
    print("\n4. Second identity shape — subject is the address, no email claim")
    second = client.get("/api/v1/admin/session", headers=token_for(secret, EMAIL)).json()
    check("granted", second["isPlatformAdmin"] is True,
          f"reason={second['reason']} matchedVia={second['matchedVia']}")
    check("matched on the subject-as-address or the binding",
          second["matchedVia"] in ("subject_email", "session_subject"), str(second["matchedVia"]))

    # ── 5. Ordinary users still get nothing ─────────────────────────────────
    print("\n5. Negative cases — the gate still refuses")
    customer = client.get("/api/v1/admin/users", headers=token_for(secret, "some-customer-subject")).json()
    check("a non-admin is refused", customer.get("code") == "PLATFORM_ADMIN_REQUIRED", str(customer)[:120])
    anonymous = client.get("/api/v1/admin/overview")
    check("an anonymous caller is refused", anonymous.status_code == 401, str(anonymous.status_code))
    typed = client.get("/api/v1/admin/overview",
                       headers=token_for(secret, "customer-subject-with-no-claim"))
    check("a session with neither the bound subject nor the address claim grants nothing",
          typed.status_code == 403, str(typed.status_code))
    check("the non-admin probe reports the denial reason, not a crash",
          client.get("/api/v1/admin/session",
                     headers=token_for(secret, "plain-customer")).json()["isPlatformAdmin"] is False)

    # ── 6. The binding is auditable ─────────────────────────────────────────
    print("\n6. Audit trail")
    with sqlite3.connect(tmp) as conn:
        conn.row_factory = sqlite3.Row
        claims = [dict(r) for r in conn.execute(
            "SELECT user_id, metadata_json FROM audit_events WHERE event_type = 'admin.platform_role_claimed'")]
    check("the link is recorded as admin.platform_role_claimed", bool(claims),
          str([c["user_id"] for c in claims]))
    check("roster size unchanged by binding", platform_admins.get_repo(str(tmp)).count_active() == 1,
          str(platform_admins.get_repo(str(tmp)).count_active()))

    print("\n" + "=" * 72)
    if _failures:
        print(f"FAILED ({len(_failures)}): " + "; ".join(_failures))
        return 1
    print("All identity-binding assertions passed. The live database was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
