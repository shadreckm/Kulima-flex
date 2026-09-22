"""Job models for durable transaction processing (Phase 4).

These models implement the job queue that makes background work survive
process restarts and enables resume-on-login functionality.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobKind(str, Enum):
    """Types of background jobs in the transaction system."""

    RESEARCH = "research"
    EXTRACTION = "extraction"
    SIGNALS = "signals"
    DECISION = "decision"
    EXPORT = "export"
    RETENTION_CLEANUP = "retention_cleanup"


class JobStatus(str, Enum):
    """Lifecycle status of a job in the durable queue."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"  # Exceeded max attempts


class Job(BaseModel):
    """A durable background job in the transaction system.

    Jobs survive process restarts and enable the "upload once, leave platform,
    return tomorrow, see all progress" workflow.
    """

    id: str
    case_id: str
    kind: JobKind
    status: JobStatus = JobStatus.QUEUED
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str  # Prevent duplicate work
    attempts: int = 0
    max_attempts: int = 3
    run_after: datetime | None = None  # Delayed execution
    lease_owner: str | None = None  # Worker currently processing this job
    lease_expires_at: datetime | None = None  # Lease timeout for recovery
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: str | None = None
    result: dict[str, Any] | None = None  # Output of successful job
