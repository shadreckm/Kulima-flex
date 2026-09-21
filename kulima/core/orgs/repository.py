"""SQLite persistence for organizations and memberships.

Lives in the same SQLite database as the rest of Kulima (single source of
truth per environment). All migrations are idempotent and additive.

Workspace isolation contract: every data object (runs, documents, signals,
reports, decisions, audit events) is scoped to an ``org_id``. Rows created
before tenancy existed are bound to the owner's personal organization by
``claim_legacy_data`` on first authenticated request — no data loss, no
dangling owners.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from kulima.config import get_settings

from .models import Organization, OrganizationMember, Role, coerce_role

_log = logging.getLogger(__name__)


ORG_SCHEMA = """
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    personal INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organization_members (
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT,
    display_name TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_org_members_user
    ON organization_members(user_id);
"""

_SLUG_SANITIZE = re.compile(r"[^a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrgRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(ORG_SCHEMA)
            conn.commit()

    # ── Organizations ────────────────────────────────────────────────────

    def create_org(
        self,
        name: str,
        *,
        created_by: str | None = None,
        personal: bool = False,
        plan: str = "free",
        org_id: str | None = None,
    ) -> Organization:
        org = Organization(
            id=org_id or str(uuid.uuid4()),
            name=name.strip() or "Organization",
            slug=self._slugify(name),
            plan=plan,
            personal=personal,
            created_by=created_by,
            created_at=_now(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO organizations (id, name, slug, plan, personal, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (org.id, org.name, org.slug, org.plan, 1 if org.personal else 0, org.created_by, org.created_at),
            )
            conn.commit()
        return org

    def get_org(self, org_id: str) -> Organization | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        return self._row_to_org(row) if row else None

    def list_orgs_for_user(self, user_id: str) -> list[Organization]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT o.* FROM organizations o
                JOIN organization_members m ON m.org_id = o.id
                WHERE m.user_id = ?
                ORDER BY m.created_at ASC
                """,
                (user_id,),
            ).fetchall()
        return [self._row_to_org(r) for r in rows]

    def set_plan(self, org_id: str, plan: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("UPDATE organizations SET plan = ? WHERE id = ?", (plan, org_id))
            conn.commit()
            return bool(cur.rowcount)

    def rename_org(self, org_id: str, name: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE organizations SET name = ?, slug = ? WHERE id = ?",
                (name.strip() or "Organization", self._slugify(name), org_id),
            )
            conn.commit()
            return bool(cur.rowcount)

    # ── Memberships ──────────────────────────────────────────────────────

    def get_membership(self, user_id: str) -> OrganizationMember | None:
        """Primary membership: the earliest (usually the personal) organization."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM organization_members
                WHERE user_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return self._row_to_member(row) if row else None

    def get_membership_for_org(self, org_id: str, user_id: str) -> OrganizationMember | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM organization_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            ).fetchone()
        return self._row_to_member(row) if row else None

    def list_members(self, org_id: str) -> list[OrganizationMember]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM organization_members WHERE org_id = ? ORDER BY created_at ASC",
                (org_id,),
            ).fetchall()
        return [self._row_to_member(r) for r in rows]

    def member_user_ids(self, org_id: str) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM organization_members WHERE org_id = ?",
                (org_id,),
            ).fetchall()
        return {r["user_id"] for r in rows}

    def count_members(self, org_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM organization_members WHERE org_id = ?",
                (org_id,),
            ).fetchone()
        return int(row["c"] if row else 0)

    def add_member(
        self,
        org_id: str,
        user_id: str,
        role: Role | str = Role.VIEWER,
        *,
        email: str | None = None,
        display_name: str | None = None,
    ) -> OrganizationMember | None:
        role_enum = coerce_role(role)
        if role_enum is None:
            raise ValueError("invalid_role")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO organization_members (org_id, user_id, role, email, display_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(org_id, user_id) DO UPDATE SET
                    role = excluded.role,
                    email = COALESCE(excluded.email, organization_members.email),
                    display_name = COALESCE(excluded.display_name, organization_members.display_name)
                """,
                (org_id, user_id, role_enum.value, email, display_name, _now()),
            )
            conn.commit()
        return self.get_membership_for_org(org_id, user_id)

    def set_role(self, org_id: str, user_id: str, role: Role | str) -> bool:
        role_enum = coerce_role(role)
        if role_enum is None:
            raise ValueError("invalid_role")
        if role_enum != Role.OWNER:
            self._guard_last_owner(org_id, user_id)
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE organization_members SET role = ? WHERE org_id = ? AND user_id = ?",
                (role_enum.value, org_id, user_id),
            )
            conn.commit()
            return bool(cur.rowcount)

    def remove_member(self, org_id: str, user_id: str) -> bool:
        self._guard_last_owner(org_id, user_id)
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM organization_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )
            conn.commit()
            return bool(cur.rowcount)

    def _guard_last_owner(self, org_id: str, user_id: str) -> None:
        """An organization can never be left without an owner."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM organization_members WHERE org_id = ? AND role = 'owner'",
                (org_id,),
            ).fetchone()
            owners = int(row["c"] if row else 0)
            target = conn.execute(
                "SELECT role FROM organization_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            ).fetchone()
        if target and str(target["role"]) == Role.OWNER.value and owners <= 1:
            raise ValueError("last_owner")

    # ── Personal organization provisioning ───────────────────────────────

    def ensure_personal_org(
        self,
        user_id: str,
        *,
        email: str | None = None,
        display_name: str | None = None,
    ) -> Organization:
        """Idempotently provision the caller's organization + ownership.

        First call creates a personal organization, records the user as Owner,
        and claims any pre-tenancy rows (runs, assessments, documents) that
        were created by this user before organizations existed.
        """
        membership = self.get_membership(user_id)
        if membership is not None:
            org = self.get_org(membership.org_id)
            if org is not None:
                return org

        label = display_name or email or "Personal workspace"
        org = self.create_org(
            f"{label} — Workspace" if label != "Personal workspace" else "Personal Workspace",
            created_by=user_id,
            personal=True,
        )
        self.add_member(org.id, user_id, Role.OWNER, email=email, display_name=display_name)
        self.claim_legacy_data(user_id, org.id)
        _log.info("Provisioned personal organization %s for user %s", org.id, user_id)
        return org

    # ── Legacy data backfill ─────────────────────────────────────────────

    def claim_legacy_data(self, user_id: str, org_id: str) -> dict[str, int]:
        """Bind pre-tenancy rows owned by ``user_id`` to their personal org.

        Each statement is best-effort and tolerant of older databases where a
        column may not exist yet; the count map is returned for auditability.
        """
        counts: dict[str, int] = {}
        statements = (
            ("intelligence_runs", "UPDATE intelligence_runs SET org_id = ? WHERE user_id = ? AND org_id IS NULL"),
            ("assessment_contexts", "UPDATE assessment_contexts SET org_id = ? WHERE user_id = ? AND org_id IS NULL"),
            ("documents", "UPDATE documents SET org_id = ? WHERE uploaded_by = ? AND org_id IS NULL"),
            ("api_runs", "UPDATE api_runs SET org_id = ? WHERE user_id = ? AND org_id IS NULL"),
        )
        with self._connect() as conn:
            for table, sql in statements:
                try:
                    cur = conn.execute(sql, (org_id, user_id))
                    counts[table] = int(cur.rowcount or 0)
                except sqlite3.OperationalError:
                    # Table or column not present in this environment yet.
                    counts[table] = 0
            conn.commit()
        return counts

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _slugify(name: str) -> str:
        base = _SLUG_SANITIZE.sub("-", (name or "").strip().lower()).strip("-")
        return (base or "org")[:48]

    @staticmethod
    def _row_to_org(row: sqlite3.Row) -> Organization:
        return Organization(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            plan=row["plan"],
            personal=bool(row["personal"]),
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_member(row: sqlite3.Row) -> OrganizationMember:
        role = coerce_role(row["role"]) or Role.VIEWER
        return OrganizationMember(
            org_id=row["org_id"],
            user_id=row["user_id"],
            role=role,
            email=row["email"],
            display_name=row["display_name"],
            created_at=row["created_at"],
        )
