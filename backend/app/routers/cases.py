"""API router for enterprise Case management (Phase 4).

This router provides endpoints for case lifecycle management, work queues,
and workspace operations.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from kulima.core.cases.service import CaseService
from kulima.core.cases.models import Case, CaseLifecycleStatus, WorkspaceType, CaseSubject
from kulima.core.orgs.models import Role

# Import auth dependencies conditionally to avoid startup issues
try:
    from backend.app.core.auth import get_current_user, get_org_context
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    # Provide fallback dependencies for testing only
    import os
    if os.getenv("KULIMA_SKIP_AUTH") == "true":
        def get_current_user():
            return {"user_id": "test_user"}
        def get_org_context():
            return {"org_id": "test_org", "role": "admin"}
    else:
        # If auth not available and not explicitly skipped, raise error
        raise ImportError("Auth module required unless KULIMA_SKIP_AUTH=true")

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
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> CaseResponse:
    """Create a new case from an assessment context."""
    user_id = current_user.get("user_id")
    org_id = org_context.get("org_id")
    user_role = Role(org_context.get("role", "viewer"))

    # Check permissions (only skip if explicitly allowed for testing)
    if not (not AUTH_AVAILABLE and os.getenv("KULIMA_SKIP_AUTH") == "true"):
        from kulima.core.orgs.models import Permission, role_has_permission
        if not role_has_permission(user_role, Permission.ASSESS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to create cases",
            )

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
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> CaseResponse:
    """Get a case by ID."""
    org_id = org_context.get("org_id")
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
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> CaseResponse:
    """Get the case for a given assessment."""
    org_id = org_context.get("org_id")
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
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> CaseResponse:
    """Transition a case to a new lifecycle status."""
    user_id = current_user.get("user_id")
    org_id = org_context.get("org_id")
    user_role = Role(org_context.get("role", "viewer"))

    case_service = CaseService()

    try:
        new_status = CaseLifecycleStatus(request.new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lifecycle status: {request.new_status}",
        )

    # Only skip role check if explicitly allowed for testing
    if not (not AUTH_AVAILABLE and os.getenv("KULIMA_SKIP_AUTH") == "true"):
        case = case_service.transition_lifecycle(
            case_id=case_id,
            new_status=new_status,
            actor_id=user_id,
            actor_role=user_role,
            org_id=org_id,
        )
    else:
        # Bypass role check only for testing with explicit flag
        case = case_service.get_case(case_id, org_id=org_id)
        if case:
            case.lifecycle_status = new_status
            case = case_service.repo.save(case)

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
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> CaseResponse:
    """Assign a case to a different user."""
    user_id = current_user.get("user_id")
    org_id = org_context.get("org_id")
    user_role = Role(org_context.get("role", "viewer"))

    case_service = CaseService()

    # Only skip role check if explicitly allowed for testing
    if not (not AUTH_AVAILABLE and os.getenv("KULIMA_SKIP_AUTH") == "true"):
        case = case_service.assign_case(
            case_id=case_id,
            assignee_id=request.assignee_id,
            actor_id=user_id,
            actor_role=user_role,
            org_id=org_id,
        )
    else:
        # Bypass role check only for testing with explicit flag
        case = case_service.get_case(case_id, org_id=org_id)
        if case:
            case.assignee_id = request.assignee_id
            case = case_service.repo.save(case)

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
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> CaseResponse:
    """Set the reviewer for a case in REVIEW state."""
    user_id = current_user.get("user_id")
    org_id = org_context.get("org_id")
    user_role = Role(org_context.get("role", "viewer"))

    case_service = CaseService()

    # Only skip role check if explicitly allowed for testing
    if not (not AUTH_AVAILABLE and os.getenv("KULIMA_SKIP_AUTH") == "true"):
        case = case_service.set_reviewer(
            case_id=case_id,
            reviewer_id=request.reviewer_id,
            actor_id=user_id,
            actor_role=user_role,
            org_id=org_id,
        )
    else:
        # Bypass role check only for testing with explicit flag
        case = case_service.get_case(case_id, org_id=org_id)
        if case:
            case.reviewer_id = request.reviewer_id
            case = case_service.repo.save(case)

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case not found or reviewer assignment not allowed: {case_id}",
        )

    return _case_to_response(case)


@router.get("/queues/my-work", response_model=list[CaseResponse])
def get_my_work(
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> list[CaseResponse]:
    """Get cases assigned to the current user in DRAFT or PROCESSING states."""
    user_id = current_user.get("user_id")
    org_id = org_context.get("org_id")

    case_service = CaseService()
    cases = case_service.list_my_work(user_id, org_id)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/team-work", response_model=list[CaseResponse])
def get_team_work(
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> list[CaseResponse]:
    """Get cases assigned to other team members (not archived)."""
    user_id = current_user.get("user_id")
    org_id = org_context.get("org_id")

    case_service = CaseService()
    cases = case_service.list_team_work(user_id, org_id)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/pending-reviews", response_model=list[CaseResponse])
def get_pending_reviews(
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
) -> list[CaseResponse]:
    """Get cases in REVIEW state awaiting the user or Manager+."""
    user_id = current_user.get("user_id")
    org_id = org_context.get("org_id")
    user_role = Role(org_context.get("role", "viewer"))

    case_service = CaseService()
    cases = case_service.list_pending_reviews(user_id, org_id, user_role)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/completed", response_model=list[CaseResponse])
def get_completed(
    org_context: dict = Depends(get_org_context),
) -> list[CaseResponse]:
    """Get cases in DECISION_READY or EXPORTED states."""
    org_id = org_context.get("org_id")

    case_service = CaseService()
    cases = case_service.list_completed(org_id)

    return [_case_to_response(case) for case in cases]


@router.get("/queues/archived", response_model=list[CaseResponse])
def get_archived(
    org_context: dict = Depends(get_org_context),
) -> list[CaseResponse]:
    """Get archived cases."""
    org_id = org_context.get("org_id")

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
