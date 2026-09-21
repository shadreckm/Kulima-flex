"""SQLite persistence for shared Assessment Contexts.

Central store for the intake record: created once when documents are uploaded
on the landing page and reused by every downstream workspace.

The table lives in the same SQLite database as the intelligence runs and
document chunks (``kulima.config.get_settings().db_path``) so there is a
single source of truth per environment.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from kulima.config import get_settings

from .models import AssessmentContext, AssessmentStatus

_log = logging.getLogger(__name__)


ASSESSMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS assessment_contexts (
    assessment_id TEXT PRIMARY KEY,
    run_id TEXT,
    assessment_type TEXT NOT NULL,
    status TEXT NOT NULL,
    user_id TEXT,
    org_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Indexes are created AFTER the legacy-column migration (see _initialize):
# a pre-Phase-2 database lacks org_id, so indexing it before the ALTER TABLE
# would abort initialization and take the whole app import down with it.
ASSESSMENT_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_assessment_contexts_run_id
    ON assessment_contexts(run_id);

CREATE INDEX IF NOT EXISTS idx_assessment_contexts_user_id
    ON assessment_contexts(user_id);

CREATE INDEX IF NOT EXISTS idx_assessment_contexts_org_id
    ON assessment_contexts(org_id);
"""


class AssessmentRepository:
    """CRUD operations for AssessmentContext records."""

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
            conn.executescript(ASSESSMENT_SCHEMA)
            # Existing databases: add the tenancy column (Phase 2 isolation).
            try:
                cols = {row[1] for row in conn.execute("PRAGMA table_info(assessment_contexts)")}
                if "org_id" not in cols:
                    conn.execute("ALTER TABLE assessment_contexts ADD COLUMN org_id TEXT DEFAULT NULL")
            except Exception:  # noqa: BLE001
                pass
            # Indexes last — org_id exists by now on both fresh and legacy DBs.
            conn.executescript(ASSESSMENT_INDEXES)
            conn.commit()

    # ── Writes ───────────────────────────────────────────────────────────

    def save(self, ctx: AssessmentContext, org_id: str | None = None) -> AssessmentContext:
        """Insert or update an assessment context.

        ``org_id`` binds the context to a workspace. When omitted the
        previously stored value is preserved (link_run/update_outputs re-save
        the same context and must not clear it).
        """
        payload = ctx.model_dump(mode="json")
        with self._connect() as conn:
            if org_id is None:
                existing = conn.execute(
                    "SELECT org_id FROM assessment_contexts WHERE assessment_id = ?",
                    (ctx.assessment_id,),
                ).fetchone()
                if existing is not None:
                    org_id = existing["org_id"]
            conn.execute(
                """
                INSERT OR REPLACE INTO assessment_contexts (
                    assessment_id, run_id, assessment_type, status, user_id, org_id,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ctx.assessment_id,
                    ctx.run_id,
                    getattr(ctx.assessment_type, "value", str(ctx.assessment_type)),
                    getattr(ctx.status, "value", str(ctx.status)),
                    ctx.created_by,
                    org_id,
                    json.dumps(payload, default=str),
                    ctx.created_at,
                    ctx.updated_at,
                ),
            )
            conn.commit()
        return ctx

    def link_run(
        self,
        assessment_id: str,
        run_id: str,
        status: AssessmentStatus = AssessmentStatus.RUNNING,
    ) -> Optional[AssessmentContext]:
        """Attach a started intelligence run to the assessment context."""
        ctx = self.get(assessment_id)
        if ctx is None:
            return None
        ctx.run_id = run_id
        ctx.status = status
        return self.save(ctx)

    def update_outputs(
        self,
        assessment_id: str,
        *,
        trust_score: Optional[float] = None,
        signals: Optional[list[str]] = None,
        decision: Optional[dict] = None,
        status: Optional[AssessmentStatus] = None,
    ) -> Optional[AssessmentContext]:
        """Record pipeline outputs (trust, signals, decision) back onto the context."""
        ctx = self.get(assessment_id)
        if ctx is None:
            return None
        if trust_score is not None:
            ctx.trust_score = float(trust_score)
        if signals is not None:
            ctx.signals = list(signals)
        if decision is not None:
            ctx.decision = dict(decision)
        if status is not None:
            ctx.status = status
        return self.save(ctx)

    # ── Reads ────────────────────────────────────────────────────────────

    def get(
        self,
        assessment_id: str,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> Optional[AssessmentContext]:
        """Load a context, enforcing ownership/workspace scope when ids are present."""
        if not assessment_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM assessment_contexts WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
        if row is None:
            return None
        if org_id is not None:
            row_org = row["org_id"]
            if row_org is not None and row_org != org_id:
                return None
            if (
                row_org is None
                and user_id is not None
                and row["user_id"] is not None
                and row["user_id"] != user_id
            ):
                # Unclaimed legacy row owned by a different user.
                return None
        elif user_id is not None and row["user_id"] is not None and row["user_id"] != user_id:
            return None
        try:
            return AssessmentContext.model_validate(json.loads(row["payload_json"]))
        except Exception as exc:  # noqa: BLE001
            _log.warning("Failed to decode assessment context %s: %s", assessment_id, exc)
            return None

    def get_by_run_id(
        self,
        run_id: str,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> Optional[AssessmentContext]:
        """Resolve the assessment context that produced a given run."""
        if not run_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT assessment_id FROM assessment_contexts WHERE run_id = ? ORDER BY updated_at DESC LIMIT 1",
                (str(run_id),),
            ).fetchone()
        if row is None:
            return None
        return self.get(row["assessment_id"], user_id=user_id, org_id=org_id)

    def list_for_user(self, user_id: str | None, limit: int = 50) -> list[AssessmentContext]:
        query = "SELECT payload_json FROM assessment_contexts"
        params: list[object] = []
        if user_id is not None:
            query += " WHERE user_id IS NULL OR user_id = ?"
            params.append(user_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        contexts: list[AssessmentContext] = []
        for row in rows:
            try:
                contexts.append(AssessmentContext.model_validate(json.loads(row["payload_json"])))
            except Exception:  # noqa: BLE001
                continue
        return contexts

    def list_for_org(
        self,
        org_id: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Workspace-scoped assessment list (Phase 2 isolation).

        Returns lightweight row dicts (id, run_id, status, type, timestamps,
        headcount of documents) for dashboards and the Trust & Governance view.
        Legacy unclaimed rows owned by the calling user are included.
        """
        query = (
            "SELECT assessment_id, run_id, assessment_type, status, user_id, org_id, "
            "created_at, updated_at, payload_json FROM assessment_contexts "
            "WHERE org_id = ?"
        )
        params: list[object] = [org_id]
        if user_id is not None:
            query += " OR (org_id IS NULL AND user_id = ?)"
            params.append(user_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        results: list[dict] = []
        for row in rows:
            payload: dict = {}
            try:
                payload = json.loads(row["payload_json"])
            except Exception:  # noqa: BLE001
                payload = {}
            results.append(
                {
                    "assessmentId": row["assessment_id"],
                    "runId": row["run_id"],
                    "assessmentType": row["assessment_type"],
                    "status": row["status"],
                    "userId": row["user_id"],
                    "orgId": row["org_id"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                    "documentCount": len(payload.get("document_ids") or []),
                    "displayEntity": (
                        payload.get("organization_name")
                        or payload.get("startup_name")
                        or payload.get("founder_name")
                        or "Untitled assessment"
                    ),
                }
            )
        return results

    def count_active_for_org(self, org_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM assessment_contexts
                WHERE org_id = ? AND status IN ('intake', 'running')
                """,
                (org_id,),
            ).fetchone()
        return int(row["c"] if row else 0)

    def delete_context(self, assessment_id: str, org_id: str | None = None) -> bool:
        """Permanently remove an assessment context (Phase 1 data ownership)."""
        query = "DELETE FROM assessment_contexts WHERE assessment_id = ?"
        params: list[object] = [assessment_id]
        if org_id is not None:
            query += " AND org_id = ?"
            params.append(org_id)
        with self._connect() as conn:
            cur = conn.execute(query, tuple(params))
            conn.commit()
            return bool(cur.rowcount)
