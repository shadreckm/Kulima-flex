"""Assessment Workspace API — Step 7.

Single endpoint that resolves the active Assessment Context (the single
source of truth, Step 9) and returns the state of every workspace section:
Overview, Evidence, Research, Signals, Decision, Reports, Activity, Feedback.

All downstream pages consume THIS shape, so they stay consistent by
construction instead of by hand-maintained parity.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import OrgContext, require_permission
from ..core.rate_limit import check_rate_limit
from ..schemas.dtos import AssessmentPatchRequest
from ..services import assessment_adapter
from ..services.assessment_adapter import AssessmentError
from ..services.document_adapter import InvalidUploadError
from kulima.core.orgs.models import Permission

_log = logging.getLogger(__name__)
router = APIRouter()


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AssessmentError):
        status = 404 if exc.code == "assessment_not_found" else 400
        return HTTPException(status_code=status, detail={"error": True, "message": str(exc)})
    if isinstance(exc, InvalidUploadError):
        msg = str(exc)
        if msg == "file_too_large":
            return HTTPException(
                status_code=400,
                detail="File too large. Maximum upload size is 25 MB. Please compress or split the document.",
            )
        return HTTPException(
            status_code=400,
            detail="Unsupported file type. Accepted: PDF, DOCX, PPTX, XLSX, CSV, TXT.",
        )
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/active")
async def get_active_assessment(
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """The most recent Assessment Context for the caller inside the workspace.

    This is the single-source-of-truth read every workspace tab uses, so
    Dashboard / Runs / Analytics / Evidence / Signals / Decision / Reports
    all render the same assessment.

    Falls back to the most recent assessment for the user if no org-scoped
    assessment exists (supports legacy assessments and new assessments before
    org association completes).
    """
    try:
        contexts = assessment_adapter._repo.list_for_org(current.org_id, user_id=current.user_id, limit=1)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)
    if not contexts:
        # Fallback: try to find the most recent assessment for this user
        try:
            user_contexts = assessment_adapter._repo.list_for_user(user_id=current.user_id, limit=1)
            if user_contexts:
                assessment_id = str(user_contexts[0].assessment_id)
                return assessment_adapter.get_assessment(assessment_id, current.user_id, org_id=current.org_id)
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(
            status_code=404,
            detail={"error": True, "message": "No assessment context found for this workspace yet."},
        )
    assessment_id = str(contexts[0].get("assessmentId") or "")
    try:
        return assessment_adapter.get_assessment(assessment_id, current.user_id, org_id=current.org_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.get("/{assessment_id}")
async def get_assessment_workspace(
    assessment_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """The shared single-source-of-truth assessment for every workspace tab."""
    try:
        return assessment_adapter.get_assessment(assessment_id, current.user_id, org_id=current.org_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.patch("/{assessment_id}")
async def patch_assessment(
    assessment_id: str,
    patch: AssessmentPatchRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Confirm or correct entity details once; every tab sees the change."""
    check_rate_limit(current.user_id, "assessments:update")
    try:
        return assessment_adapter.update_assessment(
            assessment_id,
            current.user_id,
            patch.model_dump(exclude_none=True),
            org_id=current.org_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.post("/{assessment_id}/start")
async def start_assessment_run(
    assessment_id: str,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Start (or reuse) the intelligence run — extraction, Tavily, OpenAI."""
    check_rate_limit(current.user_id, "assessments:start")
    try:
        return assessment_adapter.start_assessment_run(assessment_id, current.user_id, org_id=current.org_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.get("/run/{run_id}")
async def resolve_assessment_from_run(
    run_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Resolve the assessment_id from a run_id (numeric or UUID).

    This enables legacy run-based feedback to be resolved to the correct Assessment Context.
    """
    try:
        # Try to resolve through the assessment adapter
        result = assessment_adapter.resolve_assessment_from_run(run_id, current.user_id, org_id=current.org_id)
        if result:
            return {"assessment_id": result}
        raise HTTPException(
            status_code=404,
            detail={"error": True, "message": f"Run ID {run_id} not found or not associated with an assessment."},
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.get("/{assessment_id}/feedback")
async def get_assessment_feedback(
    assessment_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Get all feedback entries for a specific assessment."""
    check_rate_limit(current.user_id, "assessment:feedback_get")
    try:
        records = assessment_adapter.get_feedback_for_assessment(
            assessment_id, user_id=current.user_id, org_id=current.org_id
        )
        return {
            "feedback": [
                {
                    "id": r.id,
                    "runId": r.run_id,
                    "userName": r.user_name,
                    "rating": r.rating,
                    "comment": r.comment,
                    "createdAt": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ],
            "total": len(records),
            "assessmentId": assessment_id,
        }
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.post("/{assessment_id}/feedback")
async def save_assessment_feedback(
    assessment_id: str,
    payload: dict,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Save feedback for a specific assessment."""
    check_rate_limit(current.user_id, "assessment:feedback")
    rating = payload.get("rating")
    comment = payload.get("comment", "")
    user_name = payload.get("userName", current.user_id)

    if rating is None:
        raise HTTPException(status_code=400, detail={"error": True, "message": "rating is required"})

    try:
        feedback_id = assessment_adapter.save_feedback_for_assessment(
            assessment_id,
            user_name,
            rating,
            comment,
            user_id=current.user_id,
            org_id=current.org_id,
        )
        if not feedback_id:
            raise HTTPException(status_code=500, detail={"error": True, "message": "feedback could not be saved"})
        return {"ok": True, "assessmentId": assessment_id, "rating": rating, "feedbackId": feedback_id}
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


