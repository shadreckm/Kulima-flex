"""SQLite persistence for investment intelligence runs."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from kulima.config import get_settings
from kulima.models import InvestmentBrief

_log = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS intelligence_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    founder_name TEXT NOT NULL,
    startup_name TEXT NOT NULL,
    sector TEXT,
    geography TEXT,
    stage TEXT,
    overall_score REAL,
    founder_score REAL,
    startup_score REAL,
    market_score REAL,
    trust_score REAL,
    risk_score REAL,
    growth_potential REAL,
    investment_readiness REAL,
    confidence REAL,
    recommendation TEXT,
    executive_summary TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS founders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_name TEXT,
    startup_name TEXT,
    founder_score INTEGER,
    trust_score INTEGER
);

CREATE TABLE IF NOT EXISTS run_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
);
"""


class IntelligenceRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()
        # Non-destructive migration: add Trust Layer columns to existing databases.
        # Opens a second connection so the migration runs on a committed schema.
        with self._connect() as conn:
            self._migrate_schema(conn)
            conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Add Trust Layer flat columns to intelligence_runs if absent.

        Uses PRAGMA table_info to check for each column before issuing
        ALTER TABLE — making this guard fully idempotent.  Existing rows
        receive NULL for both new columns, which is the correct default for
        pre-EIE runs.
        """
        existing = {
            row[1]  # column name is index 1 in PRAGMA table_info rows
            for row in conn.execute("PRAGMA table_info(intelligence_runs)")
        }
        if "integrity_score" not in existing:
            conn.execute(
                "ALTER TABLE intelligence_runs ADD COLUMN integrity_score REAL DEFAULT NULL"
            )
            _log.debug("_migrate_schema: added column integrity_score")
        if "integrity_grade" not in existing:
            conn.execute(
                "ALTER TABLE intelligence_runs ADD COLUMN integrity_grade TEXT DEFAULT NULL"
            )
            _log.debug("_migrate_schema: added column integrity_grade")
        if "archived_at" not in existing:
            conn.execute(
                "ALTER TABLE intelligence_runs ADD COLUMN archived_at TEXT DEFAULT NULL"
            )
            _log.debug("_migrate_schema: added column archived_at")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_brief(self, brief: InvestmentBrief) -> int:
        payload = brief.model_dump(mode="json")
        # Extract Trust Layer flat values — both are NULL when EIE has not run.
        ei = brief.evidence_integrity
        integrity_score: float | None = ei.integrity_score if ei is not None else None
        integrity_grade: str | None = ei.integrity_grade.value if ei is not None else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO intelligence_runs (
                    created_at, founder_name, startup_name, sector, geography, stage,
                    overall_score, founder_score, startup_score, market_score, trust_score,
                    risk_score, growth_potential, investment_readiness, confidence,
                    recommendation, executive_summary, payload_json,
                    integrity_score, integrity_grade
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    brief.founder_name,
                    brief.startup_name,
                    brief.sector,
                    brief.geography,
                    brief.stage,
                    brief.overall_score,
                    brief.founder_score,
                    brief.startup_score,
                    brief.market_score,
                    brief.trust_score,
                    brief.risk_score,
                    brief.growth_potential,
                    brief.investment_readiness,
                    brief.confidence,
                    brief.recommendation.value,
                    brief.executive_summary,
                    json.dumps(payload),
                    integrity_score,
                    integrity_grade,
                ),
            )
            # Legacy compatibility table
            conn.execute(
                """
                INSERT INTO founders (founder_name, startup_name, founder_score, trust_score)
                VALUES (?, ?, ?, ?)
                """,
                (
                    brief.founder_name,
                    brief.startup_name,
                    int(brief.founder_score),
                    int(brief.trust_score),
                ),
            )
            conn.commit()
            if cur.lastrowid is None:
                raise RuntimeError("insert did not return a row id")
            return int(cur.lastrowid)

    def recent_runs(
        self,
        limit: int = 20,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            query = """
                SELECT id, created_at, founder_name, startup_name, sector, geography, stage,
                       overall_score, founder_score, trust_score, recommendation, confidence,
                       integrity_score, integrity_grade, archived_at
                FROM intelligence_runs
            """
            params: tuple[Any, ...] = (limit,)
            if include_archived:
                query += " ORDER BY id DESC LIMIT ?"
            else:
                query += " WHERE archived_at IS NULL ORDER BY id DESC LIMIT ?"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM intelligence_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            return dict(row) if row else None

    def load_brief(self, run_id: int) -> InvestmentBrief | None:
        """Reconstruct a full InvestmentBrief from a stored run.

        Deserialises the ``payload_json`` column back into a typed
        ``InvestmentBrief`` via Pydantic v2's ``model_validate``.
        Returns ``None`` — without raising — if the run does not exist
        or if the stored JSON cannot be parsed (e.g. schema drift from
        an older run).
        """
        row = self.get_run(run_id)
        if row is None:
            _log.warning("load_brief: run_id=%d not found in database.", run_id)
            return None
        try:
            data = json.loads(row["payload_json"])
            return InvestmentBrief.model_validate(data)
        except (json.JSONDecodeError, KeyError, ValueError, Exception) as exc:
            _log.error(
                "load_brief: failed to deserialise run_id=%d — %s: %s",
                run_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            return None

    def archive_run(self, run_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE intelligence_runs SET archived_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), run_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def reopen_run(self, run_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE intelligence_runs SET archived_at = NULL WHERE id = ?",
                (run_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_run(self, run_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT founder_name, startup_name FROM intelligence_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM intelligence_runs WHERE id = ?", (run_id,))
            conn.execute(
                """
                DELETE FROM founders
                WHERE id = (
                    SELECT id FROM founders
                    WHERE founder_name = ? AND startup_name = ?
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                (row["founder_name"], row["startup_name"]),
            )
            conn.commit()
            return True

    def save_feedback(
        self,
        run_id: int,
        user_name: str,
        rating: int,
        comment: str,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO run_feedback (run_id, user_name, rating, comment, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    user_name.strip() or "Pilot User",
                    int(rating),
                    comment.strip(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            if cur.lastrowid is None:
                raise RuntimeError("feedback insert did not return a row id")
            return int(cur.lastrowid)
