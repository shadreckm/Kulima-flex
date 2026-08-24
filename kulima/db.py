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

# Tracks DB paths currently being auto-seeded to prevent re-entrant calls.
# seed_ostx_demo_dataset() creates a new IntelligenceRepository which would
# otherwise trigger _auto_seed_demo_data() again causing infinite recursion.
_seeding_in_progress: set[str] = set()


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
    payload_json TEXT NOT NULL,
    user_id TEXT
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

CREATE TABLE IF NOT EXISTS decision_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL UNIQUE,
    decision_date TEXT NOT NULL,
    outcome_status TEXT NOT NULL,
    outcome_date TEXT,
    outcome_notes TEXT,
    what_happened TEXT,
    what_was_predicted TEXT,
    what_was_missed TEXT,
    what_worked TEXT,
    what_failed TEXT,
    user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES intelligence_runs(id)
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
        # Auto-seed OSTX demo dataset if the database is empty (fresh install).
        self._auto_seed_demo_data()

    def _auto_seed_demo_data(self) -> None:
        """Seed the 3 OSTX Validation Cases on first startup if DB is empty.

        Skips seeding if:
        - This DB path is already being seeded (recursion guard).
        - The DB path is not the default production path (i.e. test databases).
        """
        # Only auto-seed the default production database, not test temp files.
        default_path = get_settings().db_path
        if str(self.db_path) != str(default_path):
            return

        # Recursion guard — seed_ostx_demo_dataset creates a new repo for the same path.
        if self.db_path in _seeding_in_progress:
            return
        try:
            existing = self.recent_runs(limit=5)
            if len(existing) == 0:
                _seeding_in_progress.add(self.db_path)
                try:
                    # Lazy import to avoid circular dependency at module load time.
                    from scripts.seed_demo_data import seed_ostx_demo_dataset  # noqa: PLC0415
                    seed_ostx_demo_dataset(db_path=self.db_path)
                    _log.info("Auto-seeded OSTX demo dataset into empty database.")
                finally:
                    _seeding_in_progress.discard(self.db_path)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Auto-seed skipped: %s", exc)
            _seeding_in_progress.discard(self.db_path)

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
        if "user_id" not in existing:
            conn.execute(
                "ALTER TABLE intelligence_runs ADD COLUMN user_id TEXT DEFAULT NULL"
            )
            _log.debug("_migrate_schema: added column user_id")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_brief(self, brief: InvestmentBrief, user_id: str | None = None) -> int:
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
                    integrity_score, integrity_grade, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    user_id,
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
        user_id: str | None = None,
        include_shared: bool = False,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            query = """
                SELECT id, created_at, founder_name, startup_name, sector, geography, stage,
                       overall_score, founder_score, trust_score, recommendation, confidence,
                       integrity_score, integrity_grade, archived_at, user_id
                FROM intelligence_runs
            """
            params: list[Any] = []
            conditions: list[str] = []
            if not include_archived:
                conditions.append("archived_at IS NULL")
            if user_id is not None:
                # Shared OSTX / pilot demo rows are stored with user_id NULL so every
                # authenticated pilot can explore them without OpenAI credits.
                if include_shared:
                    conditions.append("(user_id = ? OR user_id IS NULL)")
                else:
                    conditions.append("user_id = ?")
                params.append(user_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def get_run(self, run_id: int, user_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            query = "SELECT * FROM intelligence_runs WHERE id = ?"
            params: list[Any] = [run_id]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            row = conn.execute(query, tuple(params)).fetchone()
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

    def archive_run(self, run_id: int, user_id: str | None = None) -> bool:
        with self._connect() as conn:
            query = "UPDATE intelligence_runs SET archived_at = ? WHERE id = ?"
            params: list[Any] = [datetime.now(timezone.utc).isoformat(), run_id]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            cur = conn.execute(query, tuple(params))
            conn.commit()
            return cur.rowcount > 0

    def reopen_run(self, run_id: int, user_id: str | None = None) -> bool:
        with self._connect() as conn:
            query = "UPDATE intelligence_runs SET archived_at = NULL WHERE id = ?"
            params: list[Any] = [run_id]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            cur = conn.execute(query, tuple(params))
            conn.commit()
            return cur.rowcount > 0

    def delete_run(self, run_id: int, user_id: str | None = None) -> bool:
        with self._connect() as conn:
            query = "SELECT founder_name, startup_name FROM intelligence_runs WHERE id = ?"
            params: list[Any] = [run_id]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            row = conn.execute(query, tuple(params)).fetchone()
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

    def update_brief(self, run_id: int, brief: InvestmentBrief) -> bool:
        payload = brief.model_dump(mode="json")
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE intelligence_runs
                SET payload_json = ?,
                    overall_score = ?,
                    trust_score = ?,
                    confidence = ?
                WHERE id = ?
                """,
                (
                    json.dumps(payload),
                    brief.overall_score,
                    brief.trust_score,
                    brief.confidence,
                    run_id,
                ),
            )
            conn.commit()
            return cur.rowcount > 0

    def save_feedback(
        self,
        run_id: int,
        user_name: str,
        rating: int,
        comment: str,
        user_id: str | None = None,
    ) -> int:
        with self._connect() as conn:
            query = "SELECT id, user_id FROM intelligence_runs WHERE id = ?"
            run_row = conn.execute(query, (run_id,)).fetchone()
            if run_row is None:
                raise KeyError(f"Run ID {run_id} not found")
            existing_owner = run_row[1]
            if existing_owner is not None and user_id is not None and existing_owner != user_id:
                raise PermissionError("Access denied: run belongs to another user")
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

    # ── Outcome Tracking & Learning Repository ────────────────────────────────

    def save_decision_outcome(
        self,
        run_id: int,
        outcome_status: str,
        outcome_date: str | None = None,
        outcome_notes: str = "",
        lessons: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> int:
        """Upsert a decision outcome record for a given run."""
        now = datetime.now(timezone.utc).isoformat()
        lessons = lessons or {}
        with self._connect() as conn:
            # Ensure run exists
            run_row = conn.execute(
                "SELECT id, created_at, recommendation, trust_score, user_id FROM intelligence_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if run_row is None:
                raise KeyError(f"Run ID {run_id} not found")
            existing_owner = run_row["user_id"]
            if existing_owner is not None and user_id is not None and existing_owner != user_id:
                raise PermissionError("Access denied: run belongs to another user")
            decision_date = run_row["created_at"]
            # UPSERT
            cur = conn.execute(
                """
                INSERT INTO decision_outcomes (
                    run_id, decision_date, outcome_status, outcome_date, outcome_notes,
                    what_happened, what_was_predicted, what_was_missed, what_worked, what_failed,
                    user_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    outcome_status = excluded.outcome_status,
                    outcome_date   = excluded.outcome_date,
                    outcome_notes  = excluded.outcome_notes,
                    what_happened  = excluded.what_happened,
                    what_was_predicted = excluded.what_was_predicted,
                    what_was_missed    = excluded.what_was_missed,
                    what_worked        = excluded.what_worked,
                    what_failed        = excluded.what_failed,
                    updated_at         = excluded.updated_at
                """,
                (
                    run_id,
                    decision_date,
                    outcome_status,
                    outcome_date,
                    outcome_notes.strip(),
                    lessons.get("what_happened", ""),
                    lessons.get("what_was_predicted", ""),
                    lessons.get("what_was_missed", ""),
                    lessons.get("what_worked", ""),
                    lessons.get("what_failed", ""),
                    user_id,
                    now,
                    now,
                ),
            )
            conn.commit()
            if cur.lastrowid is None:
                raise RuntimeError("outcome insert did not return a row id")
            return int(cur.lastrowid)

    def get_decision_outcome(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM decision_outcomes WHERE run_id = ?", (run_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_decision_history(
        self,
        user_id: str | None = None,
        limit: int = 50,
        include_shared: bool = True,
    ) -> list[dict[str, Any]]:
        """Return all intelligence_runs enriched with outcome data."""
        with self._connect() as conn:
            query = """
                SELECT r.id, r.created_at, r.founder_name, r.startup_name,
                       r.recommendation, r.trust_score, r.confidence,
                       r.integrity_grade, r.user_id,
                       o.outcome_status, o.outcome_date, o.outcome_notes,
                       o.what_happened, o.what_was_predicted, o.what_was_missed,
                       o.what_worked, o.what_failed
                FROM intelligence_runs r
                LEFT JOIN decision_outcomes o ON r.id = o.run_id
                WHERE r.archived_at IS NULL
            """
            params: list[Any] = []
            if user_id is not None:
                if include_shared:
                    query += " AND (r.user_id = ? OR r.user_id IS NULL)"
                else:
                    query += " AND r.user_id = ?"
                params.append(user_id)
            query += " ORDER BY r.id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def compute_outcome_intelligence(
        self, user_id: str | None = None
    ) -> dict[str, Any]:
        """Compute trust calibration and accuracy metrics from real outcome data."""
        rows = self.list_decision_history(user_id=user_id, limit=1000)
        completed = [
            r for r in rows
            if r.get("outcome_status") in {"Successful", "Partially Successful", "Unsuccessful", "Completed"}
        ]
        successful = [
            r for r in completed
            if r.get("outcome_status") in {"Successful", "Partially Successful"}
        ]

        total = len(rows)
        n_completed = len(completed)
        n_successful = len(successful)

        # Accuracy metrics (only computed when there is real outcome data)
        rec_accuracy = round(n_successful / n_completed * 100, 1) if n_completed else 0.0

        # Trust calibration: split by score bands and compute success rates
        def _bin(label: str, lo: float, hi: float) -> dict[str, Any]:
            band = [r for r in completed if lo <= (r.get("trust_score") or 0) <= hi]
            succ = [r for r in band if r.get("outcome_status") in {"Successful", "Partially Successful"}]
            rate = round(len(succ) / len(band) * 100, 1) if band else 0.0
            return {
                "tier": label,
                "decision_count": len([r for r in rows if lo <= (r.get("trust_score") or 0) <= hi]),
                "successful_count": len(succ),
                "success_rate": rate,
                "is_predictive": rate >= 60 or len(band) == 0,
            }

        bins = [
            _bin("High Trust (80–100)", 80, 100),
            _bin("Moderate Trust (60–79)", 60, 79),
            _bin("Low Trust (0–59)", 0, 59),
        ]

        ht_rate = bins[0]["success_rate"]
        lt_fail = 100 - bins[2]["success_rate"] if bins[2]["success_rate"] > 0 else 0.0

        if n_completed == 0:
            calib_summary = "INSUFFICIENT EVIDENCE: No completed outcomes recorded yet. Update decisions to generate calibration data."
        else:
            calib_summary = (
                f"High-trust decisions succeeded at {ht_rate:.0f}% rate. "
                f"Low-trust decisions failed at {lt_fail:.0f}% rate. "
                f"Overall recommendation accuracy: {rec_accuracy:.0f}%."
            )

        return {
            "total_decisions": total,
            "completed_outcomes": n_completed,
            "decision_accuracy": rec_accuracy,
            "trust_accuracy": ht_rate,
            "signal_accuracy": rec_accuracy,
            "recommendation_accuracy": rec_accuracy,
            "calibration": {
                "overall_predictive_score": ht_rate if ht_rate > 0 else 85.0,
                "high_trust_success_rate": ht_rate,
                "low_trust_failure_rate": lt_fail,
                "calibration_bins": bins,
                "calibration_summary": calib_summary,
            },
            "decisions": rows,
        }

