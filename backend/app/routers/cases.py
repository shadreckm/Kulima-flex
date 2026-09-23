"""API router for enterprise Case management (Phase 4).

This router provides endpoints for case lifecycle management, work queues,
and workspace operations.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from kulima.core.cases.service import CaseService
from kulima.core.cases.models import Case, CaseLifecycleStatus, WorkspaceType, CaseSubject
from kulima.core.orgs.models import Permission, Role, role_has_permission

from ..core.auth import AuthenticatedUser, OrgContext, get_current_org, require_permission

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


# ── Request/Response Models ──────────────────────────────────────────────

class CaseCreateRequest(BaseModel):
    """Request to create a new case from an assessment."""

    assessment_id: str
    assessment_type: str  # Will be converted to AssessmentType
    subject_name: str
    subject_secondary_name: Optional[str] = None
    subject_sector: Optional[str] = None
    subject_region: Optional[str] = None
    assignee_id: Optional[str] = None


class CaseResponse(BaseModel):
    """Response with case details."""

    id: str
    case_type: str
    workspace_type: str
    lifecycle_status: str
    assessment_id: Optional[str]
    org_id: Optional[str]
    assignee_id: Optional[str]
    reviewer_id: Optional[str]
    version: int
    created_by: Optional[str]
    created_at: str
    updated_at: str
    subject: dict
    document_count: int

    class Config:
        from_attributes = True


class CaseTransitionRequest(BaseModel):
    """Request to transition case lifecycle."""

    new_status: str  # CaseLifecycleStatus value


class CaseAssignRequest(BaseModel):
    """Request to assign a case to a user."""

    assignee_id: str


class CaseReviewerRequest(BaseModel):
    """Request to set a reviewer for a case."""

    reviewer_id: str


# ── Endpoints ───────────────────────────────────────────────────────────

@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CaseCreateRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
) -> CaseResponse:
    """Create a new case from an assessment context."""
    user_id = current.user_id
    org_id = current.org_id

    case_service = CaseService()

    # Convert assessment_type string to enum
    from kulima.core.assessment.models import AssessmentType
    try:
        assessment_type = AssessmentType(request.assessment_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid assessment type: {request.assessment_type}",
        )

    subject = CaseSubject(
        name=request.subject_name,
        secondary_name=request.subject_secondary_name,
        sector=request.subject_sector,
        region=request.subject_region,
    )

    case = case_service.create_case(
        assessment_id=request.assessment_id,
        assessment_type=assessment_type,
        subject=subject,
        org_id=org_id,
        created_by=user_id,
        assignee_id=request.assignee_id or user_id,
    )

    return _case_to_response(case)


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    current: OrgContext = Depends(get_current_org),
) -> CaseResponse:
    """Get a case by ID."""
    org_id = current.org_id
    case_service = CaseService()

    case = case_service.get_case(case_id, org_id=org_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case not found: {case_id}",
        )

    return _case_to_response(case)


@router.get("/assessment/{assessment_id}", response_model=CaseResponse)
def get_case_by_assessment(
    assessment_id: str,
    current: OrgContext = Depends(get_current_org),
) -> CaseResponse:
    """Get the case for a given assessment."""
    org_id = current.org_id
    case_service = CaseService()

    case = case_service.get_case_by_assessment(assessment_id, org_id=org_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case not found for assessment: {assessment_id}",
        )

    return _case_to_response(case)


@router.post("/{case_id}/transition", response_model=CaseResponse)
def transition_case(
    case_id: str,
    request: CaseTransitionRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
) -> CaseResponse:
    """Transition a case to a new lifecycle status."""
    user_id = current.user_id
    org_id = current.org_id
    user_role = current.role

    case_service = CaseService()

    try:
        new_status = CaseLifecycleStatus(request.new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lifecycle status: {request.new_status}",
        )

    case = case_service.transition_lifecycle(
        case_id=case_id,
        new_status=new_status,
        actor_id=user_id,
        actor_role=user_role,
        org_id=org_id,
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case not found or transition not allowed: {case_id}",
        )

    return _case_to_response(case)


@router.post("/{case_id}/assign", response_model=CaseResponse)
def assign_case(
    case_id: str,
    request: CaseAssignRequest,
    current: OrgContext = Depends(require_permission(Permission.MANAGE_USERS)),
) -> CaseResponse:
    """Assign a case to a different user."""
    user_id = current.user_id
    org_id = current.org_id
    user_role = current.role

    case_service = CaseService()

    case = case_service.assign_case(
        case_id=case_id,
        assignee_id=request.assignee_id,
        actor_id=user_id,
        actor_role=user_role,
        org_id=org_id,
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case not found or assignment not allowed: {case_id}",
        )

    return _case_to_response(case)


@router.post("/{case_id}/reviewer", response_model=CaseResponse)
def set_reviewer(
    case_id: str,
    request: CaseReviewerRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
) -> CaseResponse:
    """Set the reviewer for a case in REVIEW state."""
    user_id = current.user_id
    org_id = current.org_id
    user_role = current.role

    case_service = CaseService()

    case = case_service.set_reviewer(
        case_id=case_id,
        reviewer_id=request.reviewer_id,
        actor_id=user_id,
        actor_role=user_role,
        org_id=org_id,
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case not found or reviewer assignment not allowed: {case_id}",
        )

    return _case_to_response(case)


@router.get("/queues/my-work", response_model=list[CaseResponse])
def get_my_work(
    current: OrgContext = Depends(get_current_org),
) -> list[CaseResponse]:
    """Get cases assigned to the current user in DRAFT or PROCESSING states."""
    user_id = current.user_id
    org_id = current.org_id

    case_service = CaseService()
    cases = case_service.list_my_work(user_id, org_id)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/team-work", response_model=list[CaseResponse])
def get_team_work(
    current: OrgContext = Depends(require_permission(Permission.VIEW_AUDIT)),
) -> list[CaseResponse]:
    """Get cases assigned to other team members (not archived)."""
    org_id = current.org_id

    case_service = CaseService()
    cases = case_service.list_team_work(user_id, org_id)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/pending-reviews", response_model=list[CaseResponse])
def get_pending_reviews(
    current: OrgContext = Depends(get_current_org),
) -> list[CaseResponse]:
    """Get cases in REVIEW state awaiting the user or Manager+."""
    user_id = current.user_id
    org_id = current.org_id
    user_role = current.role

    case_service = CaseService()
    cases = case_service.list_pending_reviews(user_id, org_id, user_role)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/completed", response_model=list[CaseResponse])
def get_completed(
    current: OrgContext = Depends(get_current_org),
) -> list[CaseResponse]:
    """Get cases in DECISION_READY or EXPORTED states."""
    org_id = current.org_id

    case_service = CaseService()
    cases = case_service.list_completed(org_id)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/archived", response_model=list[CaseResponse])
def get_archived(
    current: OrgContext = Depends(get_current_org),
) -> list[CaseResponse]:
    """Get archived cases."""
    org_id = current.org_id

    case_service = CaseService()
    cases = case_service.list_archived(org_id)

    return [_case_to_response(case) for case in cases]


# ── Helpers ──────────────────────────────────────────────────────────────

def _case_to_response(case: Case) -> CaseResponse:
    """Convert Case model to API response."""
    return CaseResponse(
        id=case.id,
        case_type=case.case_type.value,
        workspace_type=case.workspace_type.value,
        lifecycle_status=case.lifecycle_status.value,
        assessment_id=case.assessment_id,
        org_id=case.org_id,
        assignee_id=case.assignee_id,
        reviewer_id=case.reviewer_id,
        version=case.version,
        created_by=case.created_by,
        created_at=case.created_at.isoformat(),
        updated_at=case.updated_at.isoformat(),
        subject=case.subject.model_dump(mode="json"),
        document_count=len(case.document_ids),
    )
