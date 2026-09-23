"""SQLite persistence for durable job queue (Phase 4).

This repository implements the job store that makes background work survive
process restarts and enables resume-on-login functionality.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Optional

from kulima.config import get_settings
from .models import Job, JobKind, JobStatus

_log = logging.getLogger(__name__)


JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    run_after TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT,
    result_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_case_id ON jobs(case_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_lease_expires ON jobs(lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_jobs_run_after ON jobs(run_after);
CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key);
"""


class JobRepository:
    """CRUD operations for durable job records."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(JOB_SCHEMA)
            conn.commit()

    def enqueue(self, job: Job) -> Job:
        """Add a job to the queue."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, case_id, kind, status, payload_json, idempotency_key,
                        attempts, max_attempts, run_after, lease_owner, lease_expires_at,
                        created_at, updated_at, error_message, result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.id,
                        job.case_id,
                        job.kind.value,
                        job.status.value,
                        json.dumps(job.payload, default=str),
                        job.idempotency_key,
                        job.attempts,
                        job.max_attempts,
                        job.run_after.isoformat() if job.run_after else None,
                        job.lease_owner,
                        job.lease_expires_at.isoformat() if job.lease_expires_at else None,
                        job.created_at.isoformat(),
                        job.updated_at.isoformat(),
                        job.error_message,
                        json.dumps(job.result, default=str) if job.result else None,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return job

    def claim_job(self, worker_id: str, lease_duration_seconds: int = 300) -> Optional[Job]:
        """Claim a due job with a lease for exclusive processing.

        Uses SQLite-safe UPDATE with RETURNING pattern for lease claiming.
        """
        now = datetime.now(timezone.utc)
        lease_expires = now + timedelta(seconds=lease_duration_seconds)

        with self._connect() as conn:
            # Use BEGIN IMMEDIATE for write safety and concurrency control
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Find a job that is:
                # - QUEUED and past run_after (if set), OR
                # - RUNNING with expired lease (recovery)
                # - Not already leased to another worker
                row = conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'running',
                        lease_owner = ?,
                        lease_expires_at = ?,
                        attempts = attempts + 1,
                        updated_at = ?
                    WHERE id = (
                        SELECT id FROM jobs
                        WHERE (status = 'queued' AND (run_after IS NULL OR run_after <= ?))
                           OR (status = 'running' AND lease_expires_at < ?)
                        ORDER BY created_at ASC
                        LIMIT 1
                    )
                    RETURNING *
                    """,
                    (
                        worker_id,
                        lease_expires.isoformat(),
                        now.isoformat(),
                        now.isoformat(),
                        now.isoformat(),
                    ),
                ).fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        if row is None:
            return None
        return self._row_to_job(row)

    def complete_job(self, job_id: str, result: dict[str, Any]) -> Optional[Job]:
        """Mark a job as successfully completed."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = datetime.now(timezone.utc)
                cur = conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'succeeded',
                        result_json = ?,
                        lease_owner = NULL,
                        lease_expires_at = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (json.dumps(result, default=str), now.isoformat(), job_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
            except Exception:
                conn.rollback()
                raise
        return self.get(job_id)

    def fail_job(self, job_id: str, error_message: str, is_dead: bool = False) -> Optional[Job]:
        """Mark a job as failed or dead."""
        with self._connect() as conn:
            now = datetime.now(timezone.utc)
            status = "dead" if is_dead else "failed"
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    error_message = ?,
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (status, error_message, now.isoformat(), job_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        return self.get(job_id)

    def get(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Job]:
        """Check if a job with this idempotency key already exists."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def list_for_case(self, case_id: str, org_id: str | None = None) -> list[Job]:
        """List all jobs for a case with optional org validation."""
        # Get the case first to validate org membership
        if org_id is not None:
            from kulima.core.cases.repository import CaseRepository
            case_repo = CaseRepository(self.db_path)
            case = case_repo.get(case_id, org_id=org_id)
            if case is None:
                _log.warning("list_for_case: case %s not found or not in org %s", case_id, org_id)
                return []

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE case_id = ? ORDER BY created_at DESC",
                (case_id,),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def list_running(self) -> list[Job]:
        """List all currently running jobs (for recovery)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'running' ORDER BY lease_expires_at ASC"
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def list_pending(self) -> list[Job]:
        """List all jobs that are queued or due to run."""
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'queued' AND (run_after IS NULL OR run_after <= ?)
                ORDER BY created_at ASC
                """,
                (now.isoformat(),),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def recover_stalled_jobs(self) -> int:
        """Reset jobs that have been running too long (lease expired)."""
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = 'queued',
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE status = 'running' AND lease_expires_at < ?
                """,
                (now.isoformat(), now.isoformat()),
            )
            conn.commit()
            return cur.rowcount

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        """Convert database row to Job model."""
        def _load_json(column: str, default):
            try:
                return json.loads(row[column]) if row[column] else default
            except Exception:
                return default

        return Job(
            id=row["id"],
            case_id=row["case_id"],
            kind=JobKind(row["kind"]),
            status=JobStatus(row["status"]),
            payload=_load_json("payload_json", {}),
            idempotency_key=row["idempotency_key"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            run_after=datetime.fromisoformat(row["run_after"]) if row["run_after"] else None,
            lease_owner=row["lease_owner"],
            lease_expires_at=datetime.fromisoformat(row["lease_expires_at"]) if row["lease_expires_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error_message=row["error_message"],
            result=_load_json("result_json", None),
        )
