"""SQLite persistence for enterprise Case management (Phase 4).

This repository implements the durable case store that becomes the aggregate
root for transaction management, workspaces, collaboration, and decision dossiers.

Key features:
- Durable case storage with lifecycle state machine
- Workspace isolation via org_id
- Assessment context linkage
- Role-based access control support
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from kulima.config import get_settings
from .models import Case, CaseLifecycleStatus, WorkspaceType, CaseType, CaseSubject

_log = logging.getLogger(__name__)


CASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    case_type TEXT NOT NULL,
    workspace_type TEXT NOT NULL,
    subject_json TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    assessment_id TEXT UNIQUE,
    org_id TEXT,
    assignee_id TEXT,
    reviewer_id TEXT,
    version INTEGER DEFAULT 1,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_transition_at TEXT,
    last_transition_by TEXT,
    payload_json TEXT NOT NULL,
    sources_json TEXT,
    evidence_integrity_json TEXT,
    trust_graph_json TEXT,
    document_ids_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_cases_org_id ON cases(org_id);
CREATE INDEX IF NOT EXISTS idx_cases_assessment_id ON cases(assessment_id);
CREATE INDEX IF NOT EXISTS idx_cases_lifecycle_status ON cases(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_cases_assignee_id ON cases(assignee_id);
"""


class CaseRepository:
    """CRUD operations for enterprise Case records."""

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
            conn.executescript(CASE_SCHEMA)
            conn.commit()

    def save(self, case: Case) -> Case:
        """Insert or update a case record."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cases (
                        id, case_type, workspace_type, subject_json, lifecycle_status,
                        assessment_id, org_id, assignee_id, reviewer_id, version,
                        created_by, created_at, updated_at, last_transition_at, last_transition_by,
                        payload_json, sources_json, evidence_integrity_json, trust_graph_json, document_ids_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        case.id,
                        case.case_type.value,
                        case.workspace_type.value,
                        json.dumps(case.subject.model_dump(mode="json")),
                        case.lifecycle_status.value,
                        case.assessment_id,
                        case.org_id,
                        case.assignee_id,
                        case.reviewer_id,
                        case.version,
                        case.created_by,
                        case.created_at.isoformat(),
                        case.updated_at.isoformat(),
                        case.last_transition_at.isoformat() if case.last_transition_at else None,
                        case.last_transition_by,
                        json.dumps(case.payload, default=str),
                        json.dumps([s.model_dump(mode="json") for s in case.sources], default=str),
                        json.dumps(case.evidence_integrity.model_dump(mode="json") if case.evidence_integrity else None, default=str),
                        json.dumps(case.trust_graph.model_dump(mode="json") if case.trust_graph else None, default=str),
                        json.dumps(case.document_ids, default=str),
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return case

    def get(self, case_id: str, org_id: str | None = None) -> Optional[Case]:
        """Load a case, enforcing workspace scope when org_id is provided."""
        if not case_id:
            return None
        with self._connect() as conn:
            query = "SELECT * FROM cases WHERE id = ?"
            params = [case_id]
            if org_id is not None:
                query += " AND org_id = ?"
                params.append(org_id)
            row = conn.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        return self._row_to_case(row)

    def get_by_assessment_id(self, assessment_id: str, org_id: str | None = None) -> Optional[Case]:
        """Resolve the case for a given assessment context."""
        if not assessment_id:
            return None
        with self._connect() as conn:
            query = "SELECT * FROM cases WHERE assessment_id = ?"
            params = [assessment_id]
            if org_id is not None:
                query += " AND org_id = ?"
                params.append(org_id)
            row = conn.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        return self._row_to_case(row)

    def list_for_org(
        self,
        org_id: str,
        lifecycle_status: CaseLifecycleStatus | None = None,
        assignee_id: str | None = None,
        limit: int = 100,
    ) -> list[Case]:
        """List cases for an organization with optional filters."""
        query = "SELECT * FROM cases WHERE org_id = ?"
        params = [org_id]
        if lifecycle_status is not None:
            query += " AND lifecycle_status = ?"
            params.append(lifecycle_status.value)
        if assignee_id is not None:
            query += " AND assignee_id = ?"
            params.append(assignee_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_case(row) for row in rows]

    def list_active_for_user(self, user_id: str, org_id: str | None = None) -> list[Case]:
        """Return cases in PROCESSING or REVIEW states assigned to the user."""
        if org_id is None:
            _log.warning("list_active_for_user called without org_id - tenancy violation risk")
            # For backward compatibility, allow None but log warning
            # In production, this should raise an exception
        query = """
            SELECT * FROM cases
            WHERE assignee_id = ? AND lifecycle_status IN ('processing', 'review')
        """
        params = [user_id]
        if org_id is not None:
            query += " AND org_id = ?"
            params.append(org_id)
        query += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_case(row) for row in rows]

    def update_lifecycle(
        self,
        case_id: str,
        new_status: CaseLifecycleStatus,
        actor_id: str,
        org_id: str | None = None,
    ) -> Optional[Case]:
        """Transition a case to a new lifecycle status."""
        case = self.get(case_id, org_id=org_id)
        if case is None:
            return None
        case.lifecycle_status = new_status
        case.last_transition_at = datetime.now(timezone.utc)
        case.last_transition_by = actor_id
        case.updated_at = datetime.now(timezone.utc)
        return self.save(case)

    def delete(self, case_id: str, org_id: str | None = None) -> bool:
        """Permanently remove a case record."""
        query = "DELETE FROM cases WHERE id = ?"
        params = [case_id]
        if org_id is not None:
            query += " AND org_id = ?"
            params.append(org_id)
        with self._connect() as conn:
            cur = conn.execute(query, tuple(params))
            conn.commit()
            return bool(cur.rowcount)

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> Case:
        """Convert database row to Case model."""
        def _load_json(column: str, default):
            try:
                return json.loads(row[column]) if row[column] else default
            except Exception:
                return default

        subject_data = _load_json("subject_json", {})
        subject = CaseSubject(**subject_data) if subject_data else CaseSubject(name="Unknown")

        sources_data = _load_json("sources_json", [])
        from kulima.models import SourceAttribution
        sources = [SourceAttribution(**s) for s in sources_data] if sources_data else []

        evidence_data = _load_json("evidence_integrity_json", None)
        from kulima.models import EvidenceIntegrityReport
        evidence_integrity = EvidenceIntegrityReport(**evidence_data) if evidence_data else None

        trust_data = _load_json("trust_graph_json", None)
        from kulima.models import TrustGraph
        trust_graph = TrustGraph(**trust_data) if trust_data else None

        return Case(
            id=row["id"],
            case_type=CaseType(row["case_type"]),
            subject=subject,
            workspace_type=WorkspaceType(row["workspace_type"]),
            lifecycle_status=CaseLifecycleStatus(row["lifecycle_status"]),
            assessment_id=row["assessment_id"],
            org_id=row["org_id"],
            assignee_id=row["assignee_id"],
            reviewer_id=row["reviewer_id"],
            version=row["version"],
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_transition_at=datetime.fromisoformat(row["last_transition_at"]) if row["last_transition_at"] else None,
            last_transition_by=row["last_transition_by"],
            payload=_load_json("payload_json", {}),
            sources=sources,
            evidence_integrity=evidence_integrity,
            trust_graph=trust_graph,
            document_ids=_load_json("document_ids_json", []),
        )
