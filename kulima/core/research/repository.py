"""SQLite persistence for research packs (Phase 2).

This repository implements the research pack store that enables auto-launched
research from document extraction, creating a unified evidence graph.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from kulima.config import get_settings
from .models import ResearchPack, ResearchStatus

_log = logging.getLogger(__name__)


RESEARCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_packs (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    assessment_id TEXT,
    status TEXT NOT NULL,
    queries_json TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    founder_name TEXT,
    startup_name TEXT,
    organization_name TEXT,
    sector TEXT,
    country TEXT,
    research_summary TEXT,
    key_findings_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_research_case_id ON research_packs(case_id);
CREATE INDEX IF NOT EXISTS idx_research_assessment_id ON research_packs(assessment_id);
CREATE INDEX IF NOT EXISTS idx_research_status ON research_packs(status);
"""


class ResearchRepository:
    """CRUD operations for research pack records."""

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
            conn.executescript(RESEARCH_SCHEMA)
            conn.commit()

    def save(self, pack: ResearchPack) -> ResearchPack:
        """Insert or update a research pack."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO research_packs (
                        id, case_id, assessment_id, status, queries_json, sources_json,
                        attempt_count, max_attempts, started_at, completed_at, error_message,
                        created_at, updated_at, founder_name, startup_name, organization_name,
                        sector, country, research_summary, key_findings_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pack.id,
                        pack.case_id,
                        pack.assessment_id,
                        pack.status.value,
                        json.dumps(pack.queries, default=str),
                        json.dumps(pack.sources, default=str),
                        pack.attempt_count,
                        pack.max_attempts,
                        pack.started_at.isoformat() if pack.started_at else None,
                        pack.completed_at.isoformat() if pack.completed_at else None,
                        pack.error_message,
                        pack.created_at.isoformat(),
                        pack.updated_at.isoformat(),
                        pack.founder_name,
                        pack.startup_name,
                        pack.organization_name,
                        pack.sector,
                        pack.country,
                        pack.research_summary,
                        json.dumps(pack.key_findings, default=str),
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return pack

    def get(self, pack_id: str) -> Optional[ResearchPack]:
        """Load a research pack by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM research_packs WHERE id = ?", (pack_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_pack(row)

    def get_by_case(self, case_id: str) -> Optional[ResearchPack]:
        """Load the research pack for a given case."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_packs WHERE case_id = ? ORDER BY created_at DESC LIMIT 1",
                (case_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_pack(row)

    def get_by_assessment(self, assessment_id: str) -> Optional[ResearchPack]:
        """Load the research pack for a given assessment."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_packs WHERE assessment_id = ? ORDER BY created_at DESC LIMIT 1",
                (assessment_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_pack(row)

    def list_for_org(self, org_id: str, limit: int = 100) -> list[ResearchPack]:
        """List research packs for an organization via case linkage."""
        # This requires joining with cases table - simplified for now
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.* FROM research_packs r
                JOIN cases c ON r.case_id = c.id
                WHERE c.org_id = ?
                ORDER BY r.created_at DESC
                LIMIT ?
                """,
                (org_id, limit),
            ).fetchall()
        return [self._row_to_pack(row) for row in rows]

    def update_status(
        self,
        pack_id: str,
        new_status: ResearchStatus,
        error_message: str | None = None,
    ) -> Optional[ResearchPack]:
        """Update the status of a research pack."""
        pack = self.get(pack_id)
        if pack is None:
            return None

        pack.status = new_status
        pack.updated_at = datetime.now(timezone.utc)

        if new_status == ResearchStatus.RUNNING and pack.started_at is None:
            pack.started_at = datetime.now(timezone.utc)
        elif new_status in (ResearchStatus.COMPLETED, ResearchStatus.FAILED):
            pack.completed_at = datetime.now(timezone.utc)

        if error_message:
            pack.error_message = error_message

        return self.save(pack)

    def add_sources(self, pack_id: str, sources: list[dict[str, any]]) -> Optional[ResearchPack]:
        """Add research sources to a pack."""
        pack = self.get(pack_id)
        if pack is None:
            return None

        pack.sources.extend(sources)
        pack.updated_at = datetime.now(timezone.utc)
        return self.save(pack)

    def delete(self, pack_id: str) -> bool:
        """Permanently remove a research pack."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM research_packs WHERE id = ?", (pack_id,))
            conn.commit()
            return bool(cur.rowcount)

    @staticmethod
    def _row_to_pack(row: sqlite3.Row) -> ResearchPack:
        """Convert database row to ResearchPack model."""
        def _load_json(column: str, default):
            try:
                return json.loads(row[column]) if row[column] else default
            except Exception:
                return default

        return ResearchPack(
            id=row["id"],
            case_id=row["case_id"],
            assessment_id=row["assessment_id"],
            status=ResearchStatus(row["status"]),
            queries=_load_json("queries_json", []),
            sources=_load_json("sources_json", []),
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            founder_name=row["founder_name"] or "",
            startup_name=row["startup_name"] or "",
            organization_name=row["organization_name"] or "",
            sector=row["sector"] or "",
            country=row["country"] or "",
            research_summary=row["research_summary"] or "",
            key_findings=_load_json("key_findings_json", []),
        )
