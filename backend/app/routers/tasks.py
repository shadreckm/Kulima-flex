"""API router for pending tasks and work queues (Phase 5).

This router provides endpoints for checking pending tasks before logout
and managing work queues for enterprise workflow.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from kulima.core.cases.service import CaseService
from kulima.core.jobs.repository import JobRepository
from kulima.core.research.repository import ResearchRepository
from kulima.core.orgs.models import Role

from ..core.auth import OrgContext, get_current_org

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ── Request/Response Models ──────────────────────────────────────────────

class PendingTasksResponse(BaseModel):
    """Response with pending tasks summary."""

    active_assessments: int
    running_research: int
    pending_reviews: int
    failed_extractions: int
    pending_decisions: int
    can_exit_safely: bool
    message: str


class TaskDetail(BaseModel):
    """Detail about a specific pending task."""

    task_type: str
    case_id: str
    case_name: str
    status: str
    created_at: str
    priority: str


class PendingTasksDetailResponse(BaseModel):
    """Response with detailed pending tasks."""

    tasks: list[TaskDetail]
    total_count: int
    can_exit_safely: bool


# ── Endpoints ───────────────────────────────────────────────────────────

@router.get("/pending", response_model=PendingTasksResponse)
def get_pending_tasks(
    current: OrgContext = Depends(get_current_org),
) -> PendingTasksResponse:
    """Get summary of pending tasks for the current user.

    This is called before logout to determine if the user has unfinished work.
    """
    user_id = current.user_id
    org_id = current.org_id

    case_service = CaseService()
    job_repo = JobRepository()
    research_repo = ResearchRepository()

    # Get active cases for the user
    active_cases = case_service.get_active_for_user(user_id, org_id=org_id)

    # Count running research packs
    try:
        running_research = 0
        for case in active_cases:
            research_pack = research_repo.get_by_case(case.id)
            if research_pack and research_pack.status.value == "running":
                running_research += 1
    except Exception:  # noqa: BLE001
        running_research = 0

    # Count pending reviews
    user_role = current.role
    pending_reviews = len(case_service.list_pending_reviews(user_id, org_id, user_role))

    # Count failed jobs (extractions, etc.)
    try:
        failed_jobs = 0
        for case in active_cases:
            jobs = job_repo.list_for_case(case.id, org_id=org_id)
            failed_jobs += sum(1 for j in jobs if j.status.value == "failed")
    except Exception:  # noqa: BLE001
        failed_jobs = 0

    # Count pending decisions (cases in DECISION_READY not yet exported)
    try:
        pending_decisions = 0
        completed_cases = case_service.list_completed(org_id)
        for case in completed_cases:
            if case.assignee_id == user_id:
                pending_decisions += 1
    except Exception:  # noqa: BLE001
        pending_decisions = 0

    total_pending = len(active_cases) + running_research + pending_reviews + failed_jobs + pending_decisions
    can_exit_safely = total_pending == 0

    if can_exit_safely:
        message = "All tasks completed. You can safely exit."
    else:
        message = f"You have {total_pending} active task(s). Consider completing them before exiting."

    return PendingTasksResponse(
        active_assessments=len(active_cases),
        running_research=running_research,
        pending_reviews=pending_reviews,
        failed_extractions=failed_jobs,
        pending_decisions=pending_decisions,
        can_exit_safely=can_exit_safely,
        message=message,
    )


@router.get("/pending/detail", response_model=PendingTasksDetailResponse)
def get_pending_tasks_detail(
    current: OrgContext = Depends(get_current_org),
) -> PendingTasksDetailResponse:
    """Get detailed list of pending tasks for the current user."""
    user_id = current.user_id
    org_id = current.org_id

    case_service = CaseService()
    job_repo = JobRepository()
    research_repo = ResearchRepository()

    tasks: list[TaskDetail] = []

    # Get active cases
    active_cases = case_service.get_active_for_user(user_id, org_id=org_id)
    for case in active_cases:
        tasks.append(
            TaskDetail(
                task_type="active_assessment",
                case_id=case.id,
                case_name=case.subject.name,
                status=case.lifecycle_status.value,
                created_at=case.created_at.isoformat(),
                priority="high",
            )
        )

    # Get running research
    for case in active_cases:
        research_pack = research_repo.get_by_case(case.id)
        if research_pack and research_pack.status.value == "running":
            tasks.append(
                TaskDetail(
                    task_type="running_research",
                    case_id=case.id,
                    case_name=case.subject.name,
                    status=research_pack.status.value,
                    created_at=research_pack.created_at.isoformat(),
                    priority="medium",
                )
            )

    # Get pending reviews
    user_role = current.role
    review_cases = case_service.list_pending_reviews(user_id, org_id, user_role)
    for case in review_cases:
        tasks.append(
            TaskDetail(
                task_type="pending_review",
                case_id=case.id,
                case_name=case.subject.name,
                status=case.lifecycle_status.value,
                created_at=case.created_at.isoformat(),
                priority="high",
            )
        )

    # Get failed jobs
    for case in active_cases:
        jobs = job_repo.list_for_case(case.id, org_id=org_id)
        for job in jobs:
            if job.status.value == "failed":
                tasks.append(
                    TaskDetail(
                        task_type=f"failed_{job.kind.value}",
                        case_id=case.id,
                        case_name=case.subject.name,
                        status=job.status.value,
                        created_at=job.created_at.isoformat(),
                        priority="high",
                    )
                )

    can_exit_safely = len(tasks) == 0

    return PendingTasksDetailResponse(
        tasks=tasks,
        total_count=len(tasks),
        can_exit_safely=can_exit_safely,
    )


@router.post("/exit-with-pending")
def exit_with_pending(
    current: OrgContext = Depends(get_current_org),
) -> dict:
    """Record that user is exiting with pending tasks (for governance analytics)."""
    user_id = current.user_id
    org_id = current.org_id

    from kulima.core.audit import record_event

    record_event(
        "session.exit_with_pending",
        org_id=org_id,
        user_id=user_id,
        metadata={"timestamp": "current"},
    )

    return {"status": "recorded", "message": "Exit with pending tasks recorded for governance analytics"}
