"""Organization tenancy & role-based access control (Enterprise Trust Phase 2–3).

Every Kulima FLEX user belongs to at least one Organization. Personal
organizations are auto-provisioned on first authenticated request so the
existing single-user workflows keep working unchanged, while multi-member
organizations get workspace isolation and role enforcement.
"""

from .models import (
    ROLE_LABELS,
    ROLE_PERMISSIONS,
    Organization,
    OrganizationMember,
    Permission,
    Role,
    role_has_permission,
)
from .repository import OrgRepository

__all__ = [
    "ROLE_LABELS",
    "ROLE_PERMISSIONS",
    "Organization",
    "OrganizationMember",
    "Permission",
    "Role",
    "role_has_permission",
    "OrgRepository",
]
