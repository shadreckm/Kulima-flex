"""Organization & membership API (Enterprise Trust Phases 2–3).

Every endpoint resolves the acting workspace through ``get_current_org``
(auto-provisioning a personal organization on first use) and enforces the
role matrix through ``require_permission``. Member changes are recorded in
the audit trail (org.member_added / org.role_changed / org.member_removed).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kulima.core.audit import record_event
from kulima.core.billing.plans import get_plan
from kulima.core.orgs.models import (
    ROLE_LABELS,
    Permission,
    Role,
    coerce_role,
    permissions_for_role,
)
from kulima.core.orgs.repository import OrgRepository

from ..core.auth import OrgContext, get_current_org, require_permission

router = APIRouter()

_repo_cache: OrgRepository | None = None


def _repo() -> OrgRepository:
    global _repo_cache
    if _repo_cache is None:
        _repo_cache = OrgRepository()
    return _repo_cache


class AddMemberRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=200)
    role: str = "viewer"
    email: str | None = None
    displayName: str | None = None


class SetRoleRequest(BaseModel):
    role: str


class RenameOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _role_definitions() -> list[dict]:
    return [
        {
            "role": role.value,
            "label": ROLE_LABELS.get(role.value, role.value.title()),
            "permissions": permissions_for_role(role),
        }
        for role in (Role.OWNER, Role.ADMIN, Role.REVIEWER, Role.VIEWER)
    ]


def _enforce_member_quota(org_id: str, plan_id: str) -> None:
    """Member additions respect the plan's seat limit (Phase 7–8)."""
    plan = get_plan(plan_id)
    if plan.member_quota is None:
        return
    if _repo().count_members(org_id) >= plan.member_quota:
        raise HTTPException(
            status_code=403,
            detail={
                "error": True,
                "code": "MEMBER_QUOTA_EXCEEDED",
                "message": (
                    f"Your {plan.name} plan includes up to {plan.member_quota} users. "
                    "Upgrade the workspace plan to add more members."
                ),
                "quota": plan.member_quota,
            },
        )


@router.get("/")
async def list_organizations(current: OrgContext = Depends(get_current_org)):
    """Workspaces the caller can switch between (X-Org-Id header)."""
    orgs = _repo().list_orgs_for_user(current.user_id)
    return {
        "organizations": [
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "plan": org.plan,
                "personal": org.personal,
            }
            for org in orgs
        ],
        "activeOrgId": current.org_id,
    }


@router.get("/me")
async def get_my_org(current: OrgContext = Depends(get_current_org)):
    """Acting identity: user, workspace, role, permissions and plan."""
    return {
        **current.to_payload(),
        "memberCount": _repo().count_members(current.org_id),
        "roleDefinitions": _role_definitions(),
    }


@router.patch("/me")
async def rename_org(
    payload: RenameOrgRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ok = _repo().rename_org(current.org_id, payload.name)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Organization not found"})
    org = _repo().get_org(current.org_id)
    return {"id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan}


@router.get("/me/members")
async def list_members(current: OrgContext = Depends(require_permission(Permission.VIEW))):
    members = _repo().list_members(current.org_id)
    return {
        "members": [m.to_payload() for m in members],
        "roleDefinitions": _role_definitions(),
        "orgId": current.org_id,
    }


@router.post("/me/members")
async def add_member(
    payload: AddMemberRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_USERS)),
):
    role = coerce_role(payload.role)
    if role is None:
        raise HTTPException(
            status_code=422,
            detail={"error": True, "message": "Invalid role. Use owner, admin, reviewer or viewer."},
        )
    existing = _repo().get_membership_for_org(current.org_id, payload.userId)
    if existing is None:
        _enforce_member_quota(current.org_id, current.plan)
    member = _repo().add_member(
        current.org_id,
        payload.userId,
        role,
        email=payload.email,
        display_name=payload.displayName,
    )
    if existing is None:
        record_event(
            "org.member_added",
            org_id=current.org_id,
            user_id=current.user_id,
            metadata={"targetUser": payload.userId, "role": role.value, "email": payload.email},
        )
    return member.to_payload() if member else {}


@router.patch("/me/members/{user_id}")
async def update_member_role(
    user_id: str,
    payload: SetRoleRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_USERS)),
):
    role = coerce_role(payload.role)
    if role is None:
        raise HTTPException(
            status_code=422,
            detail={"error": True, "message": "Invalid role. Use owner, admin, reviewer or viewer."},
        )
    target = _repo().get_membership_for_org(current.org_id, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Member not found in this workspace"})
    try:
        _repo().set_role(current.org_id, user_id, role)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail={
                "error": True,
                "code": "LAST_OWNER",
                "message": "An organization must always keep at least one Owner.",
            },
        )
    record_event(
        "org.role_changed",
        org_id=current.org_id,
        user_id=current.user_id,
        metadata={"targetUser": user_id, "previousRole": target.role.value, "role": role.value},
    )
    updated = _repo().get_membership_for_org(current.org_id, user_id)
    return updated.to_payload() if updated else {}


@router.delete("/me/members/{user_id}")
async def remove_member(
    user_id: str,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_USERS)),
):
    target = _repo().get_membership_for_org(current.org_id, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Member not found in this workspace"})
    try:
        removed = _repo().remove_member(current.org_id, user_id)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail={
                "error": True,
                "code": "LAST_OWNER",
                "message": "An organization must always keep at least one Owner.",
            },
        )
    if not removed:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Member not found in this workspace"})
    record_event(
        "org.member_removed",
        org_id=current.org_id,
        user_id=current.user_id,
        metadata={"targetUser": user_id, "role": target.role.value},
    )
    return {"removed": True, "userId": user_id}


@router.post("/claim-legacy")
async def claim_legacy_data(
    current: OrgContext = Depends(require_permission(Permission.MANAGE_USERS)),
):
    """Bind pre-tenancy rows (runs, assessments, documents) to this workspace."""
    counts = _repo().claim_legacy_data(current.user_id, current.org_id)
    record_event(
        "org.legacy_data_claimed",
        org_id=current.org_id,
        user_id=current.user_id,
        metadata=counts,
    )
    return {"claimed": counts}
