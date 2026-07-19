"""SQLite persistence for investment intelligence runs."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from kulima.config import get_settings
from kulima.models import InvestmentBrief


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
"""


class IntelligenceRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

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
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO intelligence_runs (
                    created_at, founder_name, startup_name, sector, geography, stage,
                    overall_score, founder_score, startup_score, market_score, trust_score,
                    risk_score, growth_potential, investment_readiness, confidence,
                    recommendation, executive_summary, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            return int(cur.lastrowid)

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, founder_name, startup_name, overall_score,
                       founder_score, trust_score, recommendation, confidence
                FROM intelligence_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM intelligence_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            return dict(row) if row else None
