from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from fastapi import Depends, HTTPException, Request, status

from kulima.core.orgs.models import (
    Organization,
    OrganizationMember,
    Permission,
    Role,
    coerce_permission,
    role_has_permission,
)
from kulima.core.orgs.repository import OrgRepository


def _load_nextauth_secret() -> str:
    secret = os.environ.get("NEXTAUTH_SECRET")
    if secret:
        return secret
    raise RuntimeError("NEXTAUTH_SECRET must be configured before the backend starts")


JWT_SECRET = _load_nextauth_secret()
JWT_ALG = "HS256"


class AuthenticatedUser:
    def __init__(self, user_id: str):
        self.user_id = user_id


async def get_current_user(request: Request) -> AuthenticatedUser:
    """Validate Authorization: Bearer <token> and return an AuthenticatedUser.

    This is a minimal JWT validator intended for pre-beta. It assumes
    the token was issued by NextAuth using the same NEXTAUTH_SECRET and
    that the user identifier is stored in the `sub` claim.
    """

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    token = auth.split(" ", 1)[1].strip()
    try:
        # Ensure `exp` is honoured so expired tokens are rejected with 401.
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], options={"verify_exp": True})
    except ExpiredSignatureError:
        # Explicit path for expired tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    return AuthenticatedUser(user_id=user_id)


# ── Enterprise Trust: organization context & RBAC (Phases 2–3) ──────────────

_org_repo_cache: OrgRepository | None = None


def _org_repo() -> OrgRepository:
    """Lazy singleton — created after the env-driven DB path is resolved."""
    global _org_repo_cache
    if _org_repo_cache is None:
        _org_repo_cache = OrgRepository()
    return _org_repo_cache


@dataclass
class OrgContext:
    """Acting identity for every data endpoint: user + workspace + role."""

    user: AuthenticatedUser
    org: Organization
    membership: OrganizationMember
    _member_ids: set[str] | None = field(default=None, repr=False)

    @property
    def user_id(self) -> str:
        return self.user.user_id

    @property
    def org_id(self) -> str:
        return self.org.id

    @property
    def role(self) -> Role:
        return self.membership.role

    @property
    def role_label(self) -> str:
        return self.membership.role_label

    @property
    def plan(self) -> str:
        return self.org.plan

    def has_permission(self, permission: Permission | str) -> bool:
        return role_has_permission(self.role, permission)

    def member_ids(self) -> set[str]:
        """User ids inside this workspace (workspace isolation checks)."""
        if self._member_ids is None:
            self._member_ids = _org_repo().member_user_ids(self.org_id)
        return self._member_ids

    def to_payload(self) -> dict:
        return {
            "userId": self.user_id,
            "orgId": self.org_id,
            "orgName": self.org.name,
            "role": self.role.value,
            "roleLabel": self.role_label,
            "plan": self.plan,
            "personal": self.org.personal,
            "permissions": self.membership.permissions,
        }


async def get_current_org(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> OrgContext:
    """Resolve the acting organization (auto-provisioning a personal workspace).

    Workspace selection: the primary membership by default; members of
    multiple organizations may target one with the ``X-Org-Id`` header
    (validated against their memberships — never trusting the raw value).
    """
    repo = _org_repo()
    org = repo.ensure_personal_org(user.user_id)
    membership = repo.get_membership_for_org(org.id, user.user_id)
    if membership is None:  # pragma: no cover — repaired by ensure_personal_org
        membership = repo.add_member(org.id, user.user_id, Role.OWNER)

    requested = (request.headers.get("X-Org-Id") or "").strip()
    if requested and requested != org.id:
        alt_membership = repo.get_membership_for_org(requested, user.user_id)
        if alt_membership is not None:
            alt_org = repo.get_org(requested)
            if alt_org is not None:
                org, membership = alt_org, alt_membership
    return OrgContext(user=user, org=org, membership=membership)


def require_permission(permission: Permission | str) -> Callable[..., Awaitable[OrgContext]]:
    """FastAPI dependency factory — RBAC enforced at the route boundary."""
    perm = coerce_permission(permission)
    perm_value = perm.value if perm else str(permission)

    async def _dependency(current: OrgContext = Depends(get_current_org)) -> OrgContext:
        if perm is None or not current.has_permission(perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": True,
                    "code": "PERMISSION_DENIED",
                    "message": (
                        f"Your role ({current.role_label}) does not include the "
                        f"'{perm_value}' permission. Ask an organization Owner or Admin."
                    ),
                    "required": perm_value,
                    "role": current.role.value,
                },
            )
        return current

    return _dependency
