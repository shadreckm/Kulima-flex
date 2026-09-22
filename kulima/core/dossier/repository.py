"""SQLite persistence for decision dossiers (Phase 11).

This repository implements the storage for decision dossiers that become the
single source of truth for assessment results.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from kulima.config import get_settings
from .models import (
    DecisionDossier,
    DossierScores,
    TourismProfile,
    InvestmentReadiness,
)

_log = logging.getLogger(__name__)


DOSSIER_SCHEMA = """
CREATE TABLE IF NOT EXISTS dossiers (
    id TEXT PRIMARY KEY,
    case_id TEXT UNIQUE NOT NULL,
    version INTEGER DEFAULT 1,
    scores_json TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    research_summary TEXT NOT NULL,
    executive_summary TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    generated_by TEXT,
    approved_by TEXT,
    approved_at TEXT,
    pdf_path TEXT,
    tourism_profile_json TEXT,
    investment_readiness_json TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_dossiers_case_id ON dossiers(case_id);
CREATE INDEX IF NOT EXISTS idx_dossiers_version ON dossiers(case_id, version);
"""


class DossierRepository:
    """CRUD operations for decision dossier records."""

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
            conn.executescript(DOSSIER_SCHEMA)
            conn.commit()

    def save(self, dossier: DecisionDossier) -> DecisionDossier:
        """Insert or update a dossier (case_id is unique, so this replaces)."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO dossiers (
                    id, case_id, version, scores_json, recommendation, research_summary,
                    executive_summary, generated_at, generated_by, approved_by, approved_at,
                    pdf_path, tourism_profile_json, investment_readiness_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dossier.id,
                    dossier.case_id,
                    dossier.version,
                    json.dumps(dossier.scores.model_dump(mode="json"), default=str),
                    dossier.recommendation,
                    dossier.research_summary,
                    dossier.executive_summary,
                    dossier.generated_at.isoformat(),
                    dossier.generated_by,
                    dossier.approved_by,
                    dossier.approved_at.isoformat() if dossier.approved_at else None,
                    dossier.pdf_path,
                    json.dumps(dossier.tourism_profile.model_dump(mode="json") if dossier.tourism_profile else None, default=str),
                    json.dumps(dossier.investment_readiness.model_dump(mode="json") if dossier.investment_readiness else None, default=str),
                    json.dumps(dossier.metadata, default=str),
                ),
            )
            conn.commit()
        return dossier

    def get(self, dossier_id: str) -> Optional[DecisionDossier]:
        """Load a dossier by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dossier(row)

    def get_by_case(self, case_id: str) -> Optional[DecisionDossier]:
        """Load the dossier for a given case."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM dossiers WHERE case_id = ? ORDER BY version DESC LIMIT 1",
                (case_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dossier(row)

    def approve(self, dossier_id: str, approver_id: str) -> Optional[DecisionDossier]:
        """Approve a dossier, making it immutable."""
        dossier = self.get(dossier_id)
        if dossier is None:
            return None

        dossier.approved_by = approver_id
        dossier.approved_at = datetime.now(timezone.utc)
        return self.save(dossier)

    def create_new_version(self, case_id: str) -> DecisionDossier:
        """Create a new version of a dossier for a case."""
        existing = self.get_by_case(case_id)
        new_version = (existing.version + 1) if existing else 1

        dossier = DecisionDossier(
            id=f"{case_id}-v{new_version}",
            case_id=case_id,
            version=new_version,
            scores=existing.scores if existing else DossierScores(),
            recommendation=existing.recommendation if existing else "",
            research_summary=existing.research_summary if existing else "",
            executive_summary=existing.executive_summary if existing else "",
            generated_at=datetime.now(timezone.utc),
            generated_by=existing.generated_by if existing else None,
            # Reset approval fields for new version
            approved_by=None,
            approved_at=None,
            pdf_path=None,
            tourism_profile=existing.tourism_profile if existing else None,
            investment_readiness=existing.investment_readiness if existing else None,
            metadata=existing.metadata if existing else {},
        )
        return self.save(dossier)

    def list_for_org(self, org_id: str, limit: int = 100) -> list[DecisionDossier]:
        """List dossiers for an organization via case linkage with validation."""
        if not org_id:
            _log.warning("list_for_org called without org_id - tenancy violation risk")
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.* FROM dossiers d
                JOIN cases c ON d.case_id = c.id
                WHERE c.org_id = ?
                ORDER BY d.generated_at DESC
                LIMIT ?
                """,
                (org_id, limit),
            ).fetchall()
        return [self._row_to_dossier(row) for row in rows]

    def delete(self, dossier_id: str) -> bool:
        """Permanently remove a dossier."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM dossiers WHERE id = ?", (dossier_id,))
            conn.commit()
            return bool(cur.rowcount)

    @staticmethod
    def _row_to_dossier(row: sqlite3.Row) -> DecisionDossier:
        """Convert database row to DecisionDossier model."""
        def _load_json(column: str, default):
            try:
                return json.loads(row[column]) if row[column] else default
            except Exception:
                return default

        scores_data = _load_json("scores_json", {})
        scores = DossierScores(**scores_data) if scores_data else DossierScores()

        tourism_data = _load_json("tourism_profile_json", None)
        tourism_profile = TourismProfile(**tourism_data) if tourism_data else None

        investment_data = _load_json("investment_readiness_json", None)
        investment_readiness = InvestmentReadiness(**investment_data) if investment_data else None

        return DecisionDossier(
            id=row["id"],
            case_id=row["case_id"],
            version=row["version"],
            scores=scores,
            recommendation=row["recommendation"],
            research_summary=row["research_summary"],
            executive_summary=row["executive_summary"],
            generated_at=datetime.fromisoformat(row["generated_at"]),
            generated_by=row["generated_by"],
            approved_by=row["approved_by"],
            approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
            pdf_path=row["pdf_path"],
            tourism_profile=tourism_profile,
            investment_readiness=investment_readiness,
            metadata=_load_json("metadata_json", {}),
        )
