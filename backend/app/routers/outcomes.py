"""Outcome Tracking & Decision Learning API Router."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..core.auth import get_current_user, AuthenticatedUser
from kulima.db import IntelligenceRepository

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


@router.get("/history")
def get_decision_history(
    limit: int = 50,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Return all decision runs enriched with outcome data."""
    rows = _repo.list_decision_history(user_id=user.user_id, limit=limit, include_shared=True)
    return {"decisions": rows, "total": len(rows)}


@router.get("/{run_id}/outcome")
def get_outcome(
    run_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Return outcome record for a specific run."""
    outcome = _repo.get_decision_outcome(run_id)
    if outcome is None:
        return {"run_id": run_id, "outcome_status": "Pending", "outcome_date": None, "outcome_notes": ""}
    return outcome


@router.post("/{run_id}/outcome")
def save_outcome(
    run_id: int,
    payload: OutcomeUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
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
            user_id=user.user_id,
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
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Compute trust calibration and accuracy metrics from real outcome data."""
    return _repo.compute_outcome_intelligence(user_id=user.user_id)
