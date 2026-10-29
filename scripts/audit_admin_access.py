"""Read-only audit of the platform-admin authorization model.

Answers, from real code and real data, why a signed-in account may or may not
reach /admin. The live database is only ever SELECTed from; the authorization
evaluator runs against a temporary COPY, because a matching-but-unlinked role row
would otherwise write a bogus subject link into live data.

    python scripts/audit_admin_access.py [email]
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EMAIL = (sys.argv[1] if len(sys.argv) > 1 else "kulimaafrica@gmail.com").strip().lower()


def line(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def tables(db: Path) -> list[str]:
    with sqlite3.connect(db) as conn:
        return [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]


def dump(db: Path, sql: str, params: tuple = ()) -> list[dict]:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params)]
        except sqlite3.Error as exc:
            return [{"error": str(exc)}]


def audit_db(db: Path, label: str) -> None:
    line(f"{label}: {db}  (exists={db.exists()}, size={db.stat().st_size if db.exists() else 0} bytes)")
    if not db.exists():
        print("  -- file does not exist")
        return
    names = tables(db)
    print(f"  tables: {len(names)}")
    print(f"  platform_admins present: {'platform_admins' in names}")

    if "platform_admins" in names:
        for r in dump(db, "SELECT * FROM platform_admins ORDER BY rowid"):
            print("   ROW:", json.dumps(r, default=str))
        print("  active count:",
              dump(db, "SELECT COUNT(*) AS n FROM platform_admins WHERE status = 'active'"))

    if "organization_members" in names:
        rows = dump(db,
                    "SELECT m.org_id, o.name AS org_name, o.personal, o.created_by,"
                    " m.user_id, m.email, m.role, m.display_name FROM organization_members m"
                    " LEFT JOIN organizations o ON o.id = m.org_id"
                    " WHERE lower(m.email) = ? OR lower(o.created_by) = ? ORDER BY m.org_id",
                    (EMAIL, EMAIL))
        print(f"  workspace memberships for {EMAIL}: {len(rows)}")
        for r in rows:
            print("   ROW:", json.dumps(r, default=str))

    if "audit_events" in names:
        for r in dump(db, "SELECT * FROM audit_events"
                          " WHERE event_type LIKE 'admin.%' OR event_type LIKE 'platform.%'"
                          " ORDER BY id DESC LIMIT 8"):
            print("   EVENT:", json.dumps(r, default=str))


def main() -> int:
    line("0. ENVIRONMENT (raw, before any dotenv load)")
    for key in ("KULIMA_DB_PATH", "KULIMA_PLATFORM_ADMIN_EMAILS",
                "KULIMA_PLATFORM_ADMIN_PRIMARY_EMAIL", "KULIMA_ADMIN_EMAILS",
                "KULIMA_PLATFORM_ADMIN_USER_IDS", "USE_SUPABASE"):
        print(f"  {key:36s}: {os.getenv(key)!r}")
    print(f"  DATABASE_URL set                    : {bool(os.getenv('DATABASE_URL'))}")
    print(f"  process CWD                         : {os.getcwd()}")

    # Same resolution kulima.config uses, done here so the live file can be
    # inspected before anything is copied.
    raw_db = os.getenv("KULIMA_DB_PATH", "founders.db")
    live = Path(raw_db) if os.path.isabs(raw_db) else (Path.cwd() / raw_db)

    audit_db(live, "LIVE DATABASE (resolved from KULIMA_DB_PATH)")
    audit_db(ROOT / "founders.db", "ROOT founders.db")
    audit_db(ROOT / "backend" / "founders.db", "BACKEND founders.db")

    # Evaluate the shipped authorization code against a COPY, so a bootstrap row
    # that matches on email but has no linked subject cannot be mutated here.
    # Each case gets its OWN fresh copy: a granted email match triggers
    # _link_subject(), which would otherwise change the roster for later cases
    # and make one case's result depend on the run order.
    tmpdir = Path(tempfile.mkdtemp(prefix="kulima_admin_audit_"))
    baseline_db = tmpdir / "baseline.db"
    if live.exists():
        shutil.copyfile(live, baseline_db)
    print(f"\n  evaluator database baseline (copy): {baseline_db}")

    os.environ["KULIMA_DB_PATH"] = str(baseline_db)

    line("1. RESOLVED SETTINGS (from the copied store)")
    from kulima.config import get_settings

    settings = get_settings()
    print(f"  db_path                     : {settings.db_path}")
    print(f"  platform_admin_emails       : {settings.platform_admin_emails}")
    print(f"  platform_admin_primary      : {settings.platform_admin_primary_email}")
    print(f"  admin_emails (break-glass)  : {settings.admin_emails}")
    print(f"  platform_admin_user_ids     : {settings.platform_admin_user_ids}")

    line(f"2. PRODUCTION AUTHORIZATION EVALUATOR - identity under test: {EMAIL}")
    from backend.app.core import admin_access

    # What the /api/v1 proxy mints: subject = NextAuth token.sub, and the
    # provider-verified email claim when the JWT carries one.
    stored = dump(baseline_db, "SELECT user_id, email, status FROM platform_admins") if baseline_db.exists() else []
    print(f"  stored roster (baseline): {json.dumps(stored, default=str)}")

    cases = [
        ("A. email claim present, subject = real Google account id",
         {"user_id": "unknown-google-subject", "verified_email": EMAIL}),
        ("B. email claim present, subject = the email itself",
         {"user_id": EMAIL, "verified_email": EMAIL}),
        ("C. NO email claim in the backend token, subject = account id",
         {"user_id": "unknown-google-subject", "verified_email": None}),
        ("D. a different person, no email claim",
         {"user_id": "some-other-user", "verified_email": None}),
        ("E. NO email claim, subject = the email itself (this deployment's shape)",
         {"user_id": EMAIL, "verified_email": None}),
    ]
    for idx, (label, kwargs) in enumerate(cases):
        case_db = tmpdir / f"case{idx}.db"
        shutil.copyfile(baseline_db, case_db)
        os.environ["KULIMA_DB_PATH"] = str(case_db)
        decision = admin_access.evaluate(admin_access.identity_candidates(**kwargs))
        payload = decision.to_payload()
        print(f"\n  {label}")
        print(f"     allowed={payload['isPlatformAdmin']}  reason={payload['reason']}  "
              f"grantedBy={payload['grantedBy']}  matchedVia={payload['matchedVia']}")
        print(f"     identifiersChecked={payload['identifiersChecked']}  "
              f"roleStoreConfigured={payload['roleStoreConfigured']}  "
              f"adminCount={payload['adminCount']}  allowListSize={payload['allowListSize']}")
        print(f"     capabilities={payload['capabilities']}")
        print(f"     roster AFTER this case: {json.dumps(dump(case_db, 'SELECT user_id, email, status FROM platform_admins'), default=str)}")

    os.environ["KULIMA_DB_PATH"] = str(baseline_db)

    line("3. ADMIN SURFACE IN THE BACKEND APPLICATION")
    try:
        from backend.app.main import app

        paths = sorted(p for p in app.openapi()["paths"] if p.startswith("/api/v1/admin"))
        print(f"  /api/v1/admin* routes: {len(paths)}")
        for p in paths:
            print("   ", p)
    except Exception as exc:  # noqa: BLE001 — the route listing is a convenience
        print(f"  could not load the FastAPI app here: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
