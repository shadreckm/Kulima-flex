"""Outcome Tracking & Decision Learning API Router."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..core.auth import OrgContext, require_permission
from kulima.core.orgs.models import Permission
from kulima.db import IntelligenceRepository
from .intelligence import _load_brief_model

router = APIRouter()
_repo = IntelligenceRepository()
_log = logging.getLogger(__name__)


class OutcomeUpdateRequest(BaseModel):
    outcome_status: str
    outcome_date: Optional[str] = None
    outcome_notes: str = ""
    what_happened: str = ""
    what_was_predicted: str = ""
    what_was_missed: str = ""
    what_worked: str = ""
    what_failed: str = ""


# ── Outcome Layer V1: DecisionRecord + 30-day follow-up ──────────────────────
# Validations measure whether users actually answer; no DAS / learning / billing.

_FOLLOWUP_DECISION_VALUES = {"yes", "no", "in_progress", "unknown"}
_FOLLOWUP_FOLLOWED_VALUES = {"fully", "partially", "no", "not_yet", "unknown"}


class FollowupAnswerRequest(BaseModel):
    decisionTaken: str
    recommendationFollowed: str
    comment: str = Field(default="", max_length=2000)


def _record_payload(record: dict) -> dict:
    return {
        "runId": record.get("run_id"),
        "entityName": record.get("entity_name"),
        "recommendation": record.get("recommendation"),
        "trustScore": record.get("trust_score"),
        "integrityGrade": record.get("integrity_grade"),
        "decisionSnapshotAt": record.get("decision_snapshot_at"),
        "followupDueAt": record.get("followup_due_at"),
        "followupStatus": record.get("followup_status"),
        "decisionTaken": record.get("decision_taken"),
        "recommendationFollowed": record.get("recommendation_followed"),
        "decisionComment": record.get("decision_comment") or "",
        "answeredAt": record.get("answered_at"),
    }


@router.get("/due")
def get_due_followups(
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict:
    """DecisionRecords whose 30-day follow-up window is open and unanswered."""
    rows = _repo.list_decision_records(org_id=current.org_id, only_due=True)
    return {"followups": [_record_payload(r) for r in rows], "total": len(rows)}


@router.get("/{run_id}/decision-record")
def get_decision_record(
    run_id: int,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict:
    """The frozen DecisionRecord for one run (created on first read)."""
    if _repo.get_run(run_id, user_id=current.user_id, org_id=current.org_id) is None:
        raise HTTPException(status_code=404, detail="Run not found in your workspace")
    record = _repo.ensure_decision_record(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Decision record not found")
    return _record_payload(record)


@router.post("/{run_id}/decision-record/answer")
def post_followup_answer(
    run_id: int,
    payload: FollowupAnswerRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
) -> dict:
    """Store the two follow-up answers: was a decision taken, and was the
    recommendation followed. Idempotent — re-answering updates the record."""
    decision_taken = (payload.decisionTaken or "").strip().lower()
    followed = (payload.recommendationFollowed or "").strip().lower()
    if decision_taken not in _FOLLOWUP_DECISION_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"decisionTaken must be one of {sorted(_FOLLOWUP_DECISION_VALUES)}",
        )
    if followed not in _FOLLOWUP_FOLLOWED_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"recommendationFollowed must be one of {sorted(_FOLLOWUP_FOLLOWED_VALUES)}",
        )
    if _repo.get_run(run_id, user_id=current.user_id, org_id=current.org_id) is None:
        raise HTTPException(status_code=404, detail="Run not found in your workspace")
    comment = (payload.comment or "").strip()
    record = _repo.save_followup_answer(run_id, decision_taken, followed, comment)
    if record is None:
        raise HTTPException(status_code=404, detail="Decision record not found")
    return _record_payload(record)


@router.get("/{run_id}/outcome-review")
def download_outcome_review(
    run_id: int,
    format: str = Query("pdf", pattern="^(pdf|txt)$"),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> Response:
    """Outcome Review Report for one decision: recommendation, decision taken,
    comments, lessons. Rendered from the stored DecisionRecord only — pending
    follow-ups produce a 'still waiting' review, never an invented outcome."""
    if _repo.get_run(run_id, user_id=current.user_id, org_id=current.org_id) is None:
        raise HTTPException(status_code=404, detail="Run not found in your workspace")
    brief = _load_brief_model(run_id, user_id=current.user_id, org_id=current.org_id)
    record = _repo.ensure_decision_record(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Decision record not found")
    from kulima.export import build_outcome_review_pdf, build_outcome_review_text

    entity = str(record.get("entity_name") or brief.startup_name or "decision")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in entity).strip("_") or "decision"
    if format == "txt":
        body = build_outcome_review_text(brief, record).encode("utf-8")
        media, ext = "text/plain; charset=utf-8", "txt"
    else:
        body = build_outcome_review_pdf(brief, record)
        media, ext = "application/pdf", "pdf"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{safe}_Outcome_Review.{ext}"'},
    )


@router.get("/history")
def get_decision_history(
    limit: int = 50,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict:
    """Return all decision runs enriched with outcome data."""
    rows = _repo.list_decision_history(user_id=current.user_id, limit=limit, include_shared=True)
    return {"decisions": rows, "total": len(rows)}


@router.get("/{run_id}/outcome")
def get_outcome(
    run_id: int,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict:
    """Return outcome record for a specific run (workspace-isolated)."""
    run_row = _repo.get_run(run_id, user_id=current.user_id, org_id=current.org_id)
    if run_row is None:
        raise HTTPException(status_code=404, detail="Run not found in your workspace")
    outcome = _repo.get_decision_outcome(run_id)
    if outcome is None:
        return {"run_id": run_id, "outcome_status": "Pending", "outcome_date": None, "outcome_notes": ""}
    return outcome


@router.post("/{run_id}/outcome")
def save_outcome(
    run_id: int,
    payload: OutcomeUpdateRequest,
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
) -> dict:
    """Upsert outcome tracking record for a decision run."""
    valid_statuses = {"Pending", "In Progress", "Completed", "Successful", "Partially Successful", "Unsuccessful"}
    if payload.outcome_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid outcome_status. Must be one of: {sorted(valid_statuses)}")
    try:
        lessons = {
            "what_happened": payload.what_happened,
            "what_was_predicted": payload.what_was_predicted,
            "what_was_missed": payload.what_was_missed,
            "what_worked": payload.what_worked,
            "what_failed": payload.what_failed,
        }
        outcome_id = _repo.save_decision_outcome(
            run_id=run_id,
            outcome_status=payload.outcome_status,
            outcome_date=payload.outcome_date,
            outcome_notes=payload.outcome_notes,
            lessons=lessons,
            user_id=current.user_id,
        )
        return {"outcome_id": outcome_id, "run_id": run_id, "status": "saved"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        _log.exception("Failed to save outcome for run %s", run_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/intelligence")
def get_outcome_intelligence(
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
) -> dict:
    """Compute trust calibration and accuracy metrics from real outcome data."""
    return _repo.compute_outcome_intelligence(user_id=current.user_id)
