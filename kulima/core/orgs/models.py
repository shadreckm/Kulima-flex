"""Tenancy models: organizations, memberships, roles and permissions.

Role matrix (Enterprise Trust Phase 3):

- Owner    — full access, including billing and data deletion.
- Admin    — user management, assessment workflow, documents, audit view.
- Reviewer — can assess (create/run assessments) and export evidence.
- Viewer   — read-only across the organization workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class Permission(str, Enum):
    VIEW = "view"                          # Read runs, signals, reports, decisions
    ASSESS = "assess"                      # Create / run / update assessments
    MANAGE_DOCUMENTS = "manage_documents"  # Upload and manage documents
    EXPORT = "export"                      # Export reports and document bundles
    MANAGE_USERS = "manage_users"          # Add / remove / re-role members
    VIEW_AUDIT = "view_audit"              # Trust & Governance dashboard, audit log
    DELETE_DATA = "delete_data"            # Delete documents / complete assessments
    MANAGE_BILLING = "manage_billing"      # Plan checkout, upgrades, downgrades


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(
        {
            Permission.VIEW,
            Permission.ASSESS,
            Permission.MANAGE_DOCUMENTS,
            Permission.EXPORT,
            Permission.MANAGE_USERS,
            Permission.VIEW_AUDIT,
            Permission.DELETE_DATA,
        }
    ),
    Role.REVIEWER: frozenset(
        {
            Permission.VIEW,
            Permission.ASSESS,
            Permission.EXPORT,
        }
    ),
    Role.VIEWER: frozenset({Permission.VIEW}),
}

ROLE_LABELS: dict[str, str] = {
    Role.OWNER.value: "Owner",
    Role.ADMIN.value: "Admin",
    Role.REVIEWER.value: "Reviewer",
    Role.VIEWER.value: "Viewer",
}


def coerce_role(value: Role | str) -> Role | None:
    """Return a Role for any supported representation, else None."""
    if isinstance(value, Role):
        return value
    try:
        return Role(str(value).strip().lower())
    except (ValueError, AttributeError):
        return None


def coerce_permission(value: Permission | str) -> Permission | None:
    if isinstance(value, Permission):
        return value
    try:
        return Permission(str(value).strip().lower())
    except (ValueError, AttributeError):
        return None


def role_has_permission(role: Role | str, permission: Permission | str) -> bool:
    """Central authorization check used by the API layer (enforcement everywhere)."""
    role_enum = coerce_role(role)
    perm_enum = coerce_permission(permission)
    if role_enum is None or perm_enum is None:
        return False
    return perm_enum in ROLE_PERMISSIONS[role_enum]


def permissions_for_role(role: Role | str) -> list[str]:
    role_enum = coerce_role(role)
    if role_enum is None:
        return []
    return sorted(p.value for p in ROLE_PERMISSIONS[role_enum])


@dataclass
class Organization:
    id: str
    name: str
    slug: str
    plan: str = "free"
    personal: bool = False
    created_by: str | None = None
    created_at: str = ""


@dataclass
class OrganizationMember:
    org_id: str
    user_id: str
    role: Role
    email: str | None = None
    display_name: str | None = None
    created_at: str = ""

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role.value, self.role.value.title())

    @property
    def permissions(self) -> list[str]:
        return permissions_for_role(self.role)

    def has_permission(self, permission: Permission | str) -> bool:
        return role_has_permission(self.role, permission)

    def to_payload(self) -> dict:
        return {
            "userId": self.user_id,
            "orgId": self.org_id,
            "role": self.role.value,
            "roleLabel": self.role_label,
            "email": self.email,
            "displayName": self.display_name,
            "createdAt": self.created_at,
            "permissions": self.permissions,
        }


@dataclass
class OrgContextData:
    """Lightweight snapshot of the acting identity for the API layer."""

    user_id: str
    org_id: str
    org_name: str
    role: Role
    personal: bool = False
    plan: str = "free"
    member_ids: set[str] = field(default_factory=set)

    def has_permission(self, permission: Permission | str) -> bool:
        return role_has_permission(self.role, permission)
