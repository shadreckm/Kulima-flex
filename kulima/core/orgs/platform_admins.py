"""The PLATFORM_ADMIN role: a platform-plane principal, stored, not configured-per-request.

Why this is **not** a value in the organization ``Role`` enum
-----------------------------------------------------------------
``Role`` (owner / admin / reviewer / contributor / viewer) is a *membership*
attribute: it lives on ``organization_members.role`` and is written by
organization Owners and Admins through the normal member-management endpoints.
Anything stored there is therefore grantable by a customer.

PLATFORM_ADMIN grants read access to *every* workspace on the platform. If it
were a membership role, the endpoint that changes a colleague's role would also
be the endpoint that grants cross-tenant visibility — a customer could promote
themselves. So the role lives in its own table, ``platform_admins``, which no
customer-facing code path writes to. The two planes are separated structurally,
not by a validation rule someone might forget to call.

The same reasoning is why ``OrgRepository.add_member`` / ``set_role`` reject the
literal string ``platform_admin`` (``coerce_role`` cannot map it) and why a test
asserts it: defence in depth against a future developer adding it to the enum.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterator

from kulima.config import get_settings

_log = logging.getLogger(__name__)

PLATFORM_ADMIN_ROLE = "platform_admin"
PLATFORM_ADMIN_ROLE_LABEL = "Platform Administrator"

#: Rows created by provisioning from configuration rather than by a human.
SOURCE_BOOTSTRAP = "bootstrap"
SOURCE_GRANTED = "granted"

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"


class PlatformCapability(str, Enum):
    """What a platform principal is allowed to do.

    Declared per capability so a route states what it needs and the console can
    render only the controls an operator actually holds. Today one role holds
    all of them; the point of the enum is that the next role (e.g. a billing-only
    support agent) does not require re-architecting the gate.
    """

    VIEW_ORGANIZATIONS = "view_organizations"
    VIEW_USERS = "view_users"
    MANAGE_SUBSCRIPTIONS = "manage_subscriptions"
    MANAGE_ENTERPRISE_ACCOUNTS = "manage_enterprise_accounts"
    VIEW_BILLING = "view_billing"
    VIEW_PROVIDER_HEALTH = "view_provider_health"
    VIEW_AUDIT = "view_audit"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_PLATFORM_ADMINS = "manage_platform_admins"


CAPABILITY_LABELS: dict[str, str] = {
    PlatformCapability.VIEW_ORGANIZATIONS.value: "View all organizations",
    PlatformCapability.VIEW_USERS.value: "View all users",
    PlatformCapability.MANAGE_SUBSCRIPTIONS.value: "Manage subscriptions",
    PlatformCapability.MANAGE_ENTERPRISE_ACCOUNTS.value: "Manage enterprise accounts",
    PlatformCapability.VIEW_BILLING.value: "View billing",
    PlatformCapability.VIEW_PROVIDER_HEALTH.value: "View provider health",
    PlatformCapability.VIEW_AUDIT.value: "Access audit logs",
    PlatformCapability.VIEW_ANALYTICS.value: "Access platform analytics",
    PlatformCapability.MANAGE_PLATFORM_ADMINS.value: "Grant or revoke platform administrators",
}

# The platform plane. Organization roles are deliberately absent: an Org Owner
# holds every permission *inside one workspace* and none outside it.
PLATFORM_ROLE_CAPABILITIES: dict[str, frozenset[PlatformCapability]] = {
    PLATFORM_ADMIN_ROLE: frozenset(PlatformCapability),
}

#: A workspace role never resolves to a platform capability. Kept explicit so
#: the mapping table can be shown in the console without special-casing.
ORG_ROLE_PLATFORM_CAPABILITIES: dict[str, list[str]] = {
    "owner": [],
    "admin": [],
    "reviewer": [],
    "contributor": [],
    "viewer": [],
}


def capability_labels(capabilities) -> list[str]:
    return [CAPABILITY_LABELS.get(c.value if isinstance(c, PlatformCapability) else str(c),
                                 str(c)) for c in capabilities]


def coerce_capability(value: PlatformCapability | str) -> PlatformCapability | None:
    if isinstance(value, PlatformCapability):
        return value
    try:
        return PlatformCapability(str(value).strip().lower())
    except (ValueError, AttributeError):
        return None


def capabilities_for_role(role: str | None) -> frozenset[PlatformCapability]:
    """Capabilities granted by a *platform* role name ('' / None grants none)."""
    if not role:
        return frozenset()
    return PLATFORM_ROLE_CAPABILITIES.get(str(role).strip().lower(), frozenset())


@dataclass
class PlatformAdmin:
    principal: str
    role: str = PLATFORM_ADMIN_ROLE
    user_id: str | None = None
    email: str | None = None
    display_name: str | None = None
    status: str = STATUS_ACTIVE
    source: str = SOURCE_GRANTED
    granted_by: str | None = None
    granted_at: str | None = None
    revoked_by: str | None = None
    revoked_at: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def capabilities(self) -> frozenset[PlatformCapability]:
        return capabilities_for_role(self.role if self.is_active else None)

    def holds(self, capability: PlatformCapability | str) -> bool:
        cap = coerce_capability(capability)
        return cap is not None and cap in self.capabilities

    def to_payload(self) -> dict:
        return {
            "principal": self.principal,
            "role": self.role,
            "roleLabel": PLATFORM_ADMIN_ROLE_LABEL if self.role == PLATFORM_ADMIN_ROLE else self.role,
            "userId": self.user_id,
            "email": self.email,
            "displayName": self.display_name,
            "status": self.status,
            "source": self.source,
            "grantedBy": self.granted_by,
            "grantedAt": self.granted_at,
            "revokedBy": self.revoked_by,
            "revokedAt": self.revoked_at,
            "capabilities": sorted(c.value for c in self.capabilities),
        }


PLATFORM_ADMIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS platform_admins (
    principal TEXT PRIMARY KEY,
    user_id TEXT,
    email TEXT,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'platform_admin',
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT NOT NULL DEFAULT 'granted',
    granted_by TEXT,
    granted_at TEXT NOT NULL,
    revoked_by TEXT,
    revoked_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_admins_user
    ON platform_admins(user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_admins_email
    ON platform_admins(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_platform_admins_status
    ON platform_admins(status);
"""


def _principal_for(email: str | None = None, user_id: str | None = None) -> str:
    """Stable key: an email row can exist before that person has ever signed in
    (their ``sub`` is unknown), and a user-id row can exist for a principal with
    no email claim. One identity, one row, whichever arrived first."""
    if email:
        return f"email:{str(email).strip().lower()}"
    return f"uid:{str(user_id).strip().lower()}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformAdminRepository:
    """Store for the platform plane.

    Write paths: bootstrap from configuration, and grant/revoke by an existing
    platform admin. There is no customer-facing writer.
    """

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
            conn.executescript(PLATFORM_ADMIN_SCHEMA)
            conn.commit()

    # ── Provisioning ─────────────────────────────────────────────────────

    def bootstrap(self, *, force: bool = False) -> dict[str, object]:
        """Ensure every configured identity has an active role row.

        Idempotent, and deliberately *not* self-healing for revoked rows: if a
        platform admin revoked a bootstrap grant, a restart must not silently
        restore it. Re-granting an intentionally revoked principal is an
        explicit ``grant`` (or ``force`` from an operator who controls the env).
        """
        settings = get_settings()
        emails = {str(e).strip().lower() for e in settings.platform_admin_emails if str(e).strip()}
        emails |= {str(e).strip().lower() for e in settings.admin_emails if str(e).strip()}
        user_ids = {str(v).strip().lower() for v in settings.platform_admin_user_ids if str(v).strip()}
        created: list[str] = []
        skipped: list[str] = []
        for email in sorted(emails):
            outcome = self._ensure_row(
                principal=_principal_for(email=email),
                email=email,
                granted_by="system:bootstrap",
                source=SOURCE_BOOTSTRAP,
                force=force,
            )
            (created if outcome == "created" else skipped).append(email)
        for user_id in sorted(user_ids):
            outcome = self._ensure_row(
                principal=_principal_for(user_id=user_id),
                user_id=user_id,
                granted_by="system:bootstrap",
                source=SOURCE_BOOTSTRAP,
                force=force,
            )
            (created if outcome == "created" else skipped).append(user_id)
        return {"created": created, "skipped": skipped, "active": self.count_active()}

    def _ensure_row(self, *, principal: str, email: str | None = None,
                    user_id: str | None = None, granted_by: str, source: str,
                    force: bool = False) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM platform_admins WHERE principal = ?", (principal,)).fetchone()
            if row is not None and not force:
                return "skipped"
            if row is not None and force:
                conn.execute(
                    "UPDATE platform_admins SET status = 'active', role = ?, revoked_by = NULL, revoked_at = NULL,"
                    " granted_by = ?, granted_at = ?, source = ? WHERE principal = ?",
                    (PLATFORM_ADMIN_ROLE, granted_by, _now(), source, principal),
                )
                conn.commit()
                return "created"
            conn.execute(
                """
                INSERT INTO platform_admins (
                    principal, user_id, email, role, status, source, granted_by, granted_at
                ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (principal, user_id, email, PLATFORM_ADMIN_ROLE, source, granted_by, _now()),
            )
            conn.commit()
            return "created"

    # ── Resolution ───────────────────────────────────────────────────────

    def resolve(self, *, user_id: str | None = None, email: str | None = None) -> PlatformAdmin | None:
        """Active role row for a *session-minted* identifier.

        The caller is responsible for only passing identifiers the auth chain
        produced (JWT ``sub`` / provider-verified email). Never pass a value
        read out of ``organization_members``.
        """
        with self._connect() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT * FROM platform_admins WHERE user_id = ? AND status = 'active'",
                    (str(user_id).strip(),),
                ).fetchone()
                if row is not None:
                    return self._row_to_admin(row)
            if email:
                row = conn.execute(
                    "SELECT * FROM platform_admins WHERE email = ? AND status = 'active'",
                    (str(email).strip().lower(),),
                ).fetchone()
                if row is not None:
                    return self._row_to_admin(row)
        return None

    def get(self, principal: str) -> PlatformAdmin | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM platform_admins WHERE principal = ?", (principal,)).fetchone()
        return self._row_to_admin(row) if row else None

    def find(self, *, user_id: str | None = None, email: str | None = None) -> PlatformAdmin | None:
        """Any status, for grant/revoke bookkeeping (revoked rows must be findable)."""
        with self._connect() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT * FROM platform_admins WHERE user_id = ?", (str(user_id).strip(),),
                ).fetchone()
                if row is not None:
                    return self._row_to_admin(row)
            if email:
                row = conn.execute(
                    "SELECT * FROM platform_admins WHERE email = ?", (str(email).strip().lower(),),
                ).fetchone()
                return self._row_to_admin(row) if row else None
        return None

    def list_admins(self, *, include_revoked: bool = False) -> list[PlatformAdmin]:
        query = "SELECT * FROM platform_admins"
        if not include_revoked:
            query += " WHERE status = 'active'"
        query += " ORDER BY status ASC, granted_at ASC"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
        return [self._row_to_admin(r) for r in rows]

    def count_active(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM platform_admins WHERE status = 'active'"
            ).fetchone()
        return int(row["c"] if row else 0)

    def is_primary(self, admin: PlatformAdmin | None) -> bool:
        primary = str(get_settings().platform_admin_primary_email or "").strip().lower()
        return bool(primary and admin is not None and (admin.email or "").strip().lower() == primary)

    # ── Mutations (platform-admin-only callers; audited by the router) ────

    def grant(self, *, email: str | None = None, user_id: str | None = None,
              display_name: str | None = None, granted_by: str) -> tuple[PlatformAdmin | None, str]:
        """Grant PLATFORM_ADMIN. Returns (row, outcome).

        Outcomes: ``granted`` | ``revived`` | ``already_active`` | ``invalid_identity``
        | ``conflict``. A grant needs at least one *session-provable* identifier,
        otherwise the row could never be matched on a request.
        """
        email = str(email).strip().lower() if email and str(email).strip() else None
        user_id = str(user_id).strip() if user_id and str(user_id).strip() else None
        if not email and not user_id:
            return None, "invalid_identity"
        if email and not _looks_like_email(email):
            return None, "invalid_email"
        existing = self.find(user_id=user_id, email=email)
        if existing is not None:
            if existing.is_active:
                return existing, "already_active"
            with self._connect() as conn:
                conn.execute(
                    "UPDATE platform_admins SET status = 'active', role = ?, revoked_by = NULL,"
                    " revoked_at = NULL, granted_by = ?, granted_at = ?, display_name = COALESCE(?, display_name),"
                    " user_id = COALESCE(user_id, ?), email = COALESCE(email, ?) WHERE principal = ?",
                    (PLATFORM_ADMIN_ROLE, granted_by, _now(), display_name, user_id, email, existing.principal),
                )
                conn.commit()
            return self.get(existing.principal), "revived"
        principal = _principal_for(email=email, user_id=user_id)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO platform_admins (
                        principal, user_id, email, display_name, role, status, source, granted_by, granted_at
                    ) VALUES (?, ?, ?, ?, ?, 'active', 'granted', ?, ?)
                    """,
                    (principal, user_id, email, display_name, PLATFORM_ADMIN_ROLE, granted_by, _now()),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            return None, "conflict"
        return self.get(principal), "granted"

    def revoke(self, *, user_id: str | None = None, email: str | None = None,
               revoked_by: str | None = None) -> tuple[bool, str]:
        """Revoke access. The row is retained (status='revoked') so the roster
        shows that access existed and who removed it — history is not rewritten."""
        admin = self.find(user_id=user_id, email=email)
        if admin is None:
            return False, "not_found"
        if not admin.is_active:
            return False, "already_revoked"
        if self.count_active() <= 1:
            # Locking out the last operator would leave nobody able to grant
            # access again through the console — env is the only way back in.
            return False, "last_admin"
        if self.is_primary(admin):
            return False, "primary_admin"
        with self._connect() as conn:
            conn.execute(
                "UPDATE platform_admins SET status = 'revoked', revoked_by = ?, revoked_at = ? WHERE principal = ?",
                (revoked_by, _now(), admin.principal),
            )
            conn.commit()
        return True, "revoked"

    def attach_subject(self, *, principal: str, user_id: str) -> bool:
        """One-time link of a bootstrap email row to the subject that signed in.

        Called only after the *provider-verified email* on the session already
        matched the row — so it cannot grant anything the email match did not
        grant; it just makes the binding survive an environment where the email
        claim is later absent.
        """
        if not user_id:
            return False
        with self._connect() as conn:
            taken = conn.execute(
                "SELECT principal FROM platform_admins WHERE user_id = ? AND principal != ?",
                (str(user_id).strip(), principal),
            ).fetchone()
            if taken is not None:
                return False
            cur = conn.execute(
                "UPDATE platform_admins SET user_id = ? WHERE principal = ? AND user_id IS NULL",
                (str(user_id).strip(), principal),
            )
            conn.commit()
            return bool(cur.rowcount)

    @staticmethod
    def _row_to_admin(row: sqlite3.Row) -> PlatformAdmin:
        return PlatformAdmin(
            principal=row["principal"],
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            role=str(row["role"] or PLATFORM_ADMIN_ROLE),
            status=str(row["status"] or STATUS_ACTIVE),
            source=str(row["source"] or SOURCE_GRANTED),
            granted_by=row["granted_by"],
            granted_at=row["granted_at"],
            revoked_by=row["revoked_by"],
            revoked_at=row["revoked_at"],
        )


def _looks_like_email(value: str) -> bool:
    v = str(value).strip()
    return "@" in v and "." in v.split("@")[-1] and " " not in v


_repo: PlatformAdminRepository | None = None
_repo_db_path: str | None = None
_bootstrapped = False


def get_repo(db_path: str | None = None) -> PlatformAdminRepository:
    """Lazy singleton keyed on the env DB path, bootstrapped once per process.

    Bootstrap happens here rather than only in the app lifespan so that the role
    exists in every environment that reads it — including a TestClient that never
    runs lifespan events, and a worker whose first request is an admin request.
    """
    global _repo, _repo_db_path, _bootstrapped
    resolved = db_path or get_settings().db_path
    if _repo is None or _repo_db_path != resolved:
        _repo = PlatformAdminRepository(resolved)
        _bootstrapped = False
    if not _bootstrapped:
        _bootstrapped = True
        try:
            _repo.bootstrap()
        except Exception as exc:  # noqa: BLE001 — a broken bootstrap must not 500 a login
            _bootstrapped = False
            _log.warning("platform admin bootstrap failed: %s", exc)
    return _repo


def reset_cache() -> None:
    """Test hook: the singleton is keyed on the env DB path, which fixtures change per test."""
    global _repo, _repo_db_path, _bootstrapped
    _repo = None
    _repo_db_path = None
    _bootstrapped = False

