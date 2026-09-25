"""Assessment Context API — the single intake engine (Steps 1–5, 9).

The landing page uploads documents here once; every downstream workspace
(Evidence, Signals, Flex, Decision, Reports, Ask IC) reads the same context
instead of asking the user to re-enter the assessment type, entity name, or
founder name.

Enterprise Trust additions:
- every context is workspace-scoped (``org_id``);
- RBAC: creating/running requires ASSESS, reading requires VIEW,
  complete deletion requires DELETE_DATA;
- suspended workspaces cannot create new assessments (BillingBlocked → 402/403)
  while existing results stay readable.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from typing import List, Optional

from kulima.core.assessment.repository import AssessmentRepository
from kulima.core.billing.service import BillingBlocked
from kulima.core.orgs.models import Permission

from ..core.auth import OrgContext, require_permission
from ..core.rate_limit import check_rate_limit
from ..schemas.dtos import AssessmentPatchRequest
from ..services import assessment_adapter
from ..services.assessment_adapter import AssessmentError
from ..services.document_adapter import InvalidUploadError

router = APIRouter()

_assessment_repo_cache: AssessmentRepository | None = None


def _assessment_repo() -> AssessmentRepository:
    global _assessment_repo_cache
    if _assessment_repo_cache is None:
        _assessment_repo_cache = AssessmentRepository()
    return _assessment_repo_cache


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, BillingBlocked):
        return HTTPException(status_code=exc.status_code, detail=exc.to_detail())
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


@router.get("/")
async def list_assessments(
    limit: int = Query(default=100, ge=1, le=500),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Workspace assessment inventory (Phase 2 isolation + Phase 9 dashboard)."""
    assessments = _assessment_repo().list_for_org(current.org_id, user_id=current.user_id, limit=limit)
    return {
        "assessments": assessments,
        "activeCount": _assessment_repo().count_active_for_org(current.org_id),
        "orgId": current.org_id,
    }


@router.post("/")
async def create_assessment(
    files: List[UploadFile] = File(...),
    assessmentType: str = Form("startup"),
    entityName: Optional[str] = Form(None),
    founderName: Optional[str] = Form(None),
    organizationName: Optional[str] = Form(None),
    sector: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Create the shared Assessment Context from uploaded documents.

    Extracts organisation / founder / sector / country / website / team /
    problem statement automatically so no downstream form asks for them again.
    """
    check_rate_limit(current.user_id, "assessments:create")
    try:
        return assessment_adapter.create_assessment(
            files,
            assessmentType,
            current.user_id,
            entity_name=entityName,
            founder_name=founderName,
            organization_name=organizationName,
            sector=sector,
            country=country,
            keywords=keywords,
            website=website,
            org_id=current.org_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.get("/by-run/{run_id}")
async def get_assessment_by_run(
    run_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Resolve the Assessment Context that produced a run (Ask IC grounding)."""
    ctx = assessment_adapter.resolve_assessment_for_brief(
        "", "", run_id=run_id, user_id=current.user_id, org_id=current.org_id
    )
    if ctx is None:
        raise HTTPException(
            status_code=404,
            detail={"error": True, "message": "No assessment context linked to this run."},
        )
    return assessment_adapter.serialize_context(ctx)


@router.get("/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    try:
        return assessment_adapter.get_assessment(assessment_id, current.user_id, org_id=current.org_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.patch("/{assessment_id}")
async def update_assessment(
    assessment_id: str,
    patch: AssessmentPatchRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Confirm or correct entity details when extraction confidence is low."""
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
    """Start the intelligence run from the context (Tavily research included).

    Idempotent while a run is running or complete.
    """
    check_rate_limit(current.user_id, "assessments:start")
    try:
        return assessment_adapter.start_assessment_run(assessment_id, current.user_id, org_id=current.org_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.post("/{assessment_id}/documents")
async def attach_assessment_documents(
    assessment_id: str,
    files: List[UploadFile] = File(...),
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    """Attach additional evidence to an existing context and re-run the chain.

    Used by the Evidence workspace tab: new documents re-trigger
    Extraction → Research → Signals → Decision automatically (no second
    upload flow, no manual launch button).
    """
    check_rate_limit(current.user_id, "assessments:create")
    try:
        return assessment_adapter.attach_documents(
            assessment_id, files, current.user_id, org_id=current.org_id
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)


@router.delete("/{assessment_id}")
async def delete_assessment(
    assessment_id: str,
    current: OrgContext = Depends(require_permission(Permission.DELETE_DATA)),
):
    """Complete assessment deletion (Phase 1): context, documents, files, run.

    The purge is recorded in the audit trail; the response summarizes exactly
    what was removed so the customer can verify their request was honoured.
    """
    check_rate_limit(current.user_id, "assessments:delete")
    try:
        return assessment_adapter.purge_assessment(
            assessment_id, user_id=current.user_id, org_id=current.org_id
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_error(exc)
