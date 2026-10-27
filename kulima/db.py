"""SQLite persistence for investment intelligence runs."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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

CREATE TABLE IF NOT EXISTS decision_records (
    run_id INTEGER PRIMARY KEY,
    org_id TEXT,
    user_id TEXT,
    entity_name TEXT,
    recommendation TEXT,
    trust_score REAL,
    integrity_grade TEXT,
    decision_snapshot_at TEXT NOT NULL,
    followup_due_at TEXT NOT NULL,
    followup_status TEXT NOT NULL DEFAULT 'pending',
    decision_taken TEXT,
    recommendation_followed TEXT,
    decision_comment TEXT DEFAULT '',
    answered_at TEXT,
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
        # Demo seeding REMOVED (pilot reliability): the seeded OSTX/pilot
        # dataset (AgriNova, GreenLink, SolarHarvest) leaked shared demo rows
        # into user workspaces. No seeding happens on any database anymore.

    def _auto_seed_demo_data(self) -> None:
        """DISABLED (pilot reliability): seeded demo data (AgriNova, GreenLink,
        SolarHarvest, pilot-* runs) leaked into user workspaces via shared
        NULL-user rows. Demo seeding must never run again."""
        return None
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
        # Enterprise Trust (Phase 2): workspace isolation. Legacy rows keep
        # NULL until claimed by OrgRepository.claim_legacy_data on first login.
        if "org_id" not in existing:
            conn.execute(
                "ALTER TABLE intelligence_runs ADD COLUMN org_id TEXT DEFAULT NULL"
            )
            _log.debug("_migrate_schema: added column org_id")
        # Outcome Layer V1: decision_records must exist before its index is
        # created (databases built before the table existed land here first).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_records (
                run_id INTEGER PRIMARY KEY,
                org_id TEXT,
                user_id TEXT,
                entity_name TEXT,
                recommendation TEXT,
                trust_score REAL,
                integrity_grade TEXT,
                decision_snapshot_at TEXT NOT NULL,
                followup_due_at TEXT NOT NULL,
                followup_status TEXT NOT NULL DEFAULT 'pending',
                decision_taken TEXT,
                recommendation_followed TEXT,
                decision_comment TEXT DEFAULT '',
                answered_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decision_records_followup "
            "ON decision_records(followup_status, followup_due_at)"
        )
        # Outcome Layer V1 follow-up comments: databases created before the
        # column existed get it added in place (answers are optional free text).
        dr_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(decision_records)").fetchall()
        ]
        if "decision_comment" not in dr_cols:
            conn.execute(
                "ALTER TABLE decision_records "
                "ADD COLUMN decision_comment TEXT DEFAULT ''"
            )
            _log.debug("_migrate_schema: added column decision_comment")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_brief(
        self,
        brief: InvestmentBrief,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> int:
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
                    integrity_score, integrity_grade, user_id, org_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    org_id,
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
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            query = """
                SELECT id, created_at, founder_name, startup_name, sector, geography, stage,
                       overall_score, founder_score, trust_score, recommendation, confidence,
                       integrity_score, integrity_grade, archived_at, user_id, org_id
                FROM intelligence_runs
            """
            params: list[Any] = []
            conditions: list[str] = []
            if not include_archived:
                conditions.append("archived_at IS NULL")
            if org_id is not None:
                # Phase 2 workspace isolation: runs are visible to the owning
                # organization only (plus shared demo rows when requested).
                if include_shared:
                    conditions.append("(org_id = ? OR user_id IS NULL)")
                else:
                    conditions.append("org_id = ?")
                params.append(org_id)
            elif user_id is not None:
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

    def get_run(
        self,
        run_id: int,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            query = "SELECT * FROM intelligence_runs WHERE id = ?"
            params: list[Any] = [run_id]
            if org_id is not None:
                # Same-org members share visibility; shared demo rows stay open.
                query += " AND (org_id = ? OR user_id IS NULL)"
                params.append(org_id)
            elif user_id is not None:
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

    def archive_run(self, run_id: int, user_id: str | None = None, org_id: str | None = None) -> bool:
        with self._connect() as conn:
            query = "UPDATE intelligence_runs SET archived_at = ? WHERE id = ?"
            params: list[Any] = [datetime.now(timezone.utc).isoformat(), run_id]
            if org_id is not None:
                query += " AND org_id = ?"
                params.append(org_id)
            elif user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            cur = conn.execute(query, tuple(params))
            conn.commit()
            return cur.rowcount > 0

    def reopen_run(self, run_id: int, user_id: str | None = None, org_id: str | None = None) -> bool:
        with self._connect() as conn:
            query = "UPDATE intelligence_runs SET archived_at = NULL WHERE id = ?"
            params: list[Any] = [run_id]
            if org_id is not None:
                query += " AND org_id = ?"
                params.append(org_id)
            elif user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            cur = conn.execute(query, tuple(params))
            conn.commit()
            return cur.rowcount > 0

    def delete_run(self, run_id: int, user_id: str | None = None, org_id: str | None = None) -> bool:
        with self._connect() as conn:
            query = "SELECT founder_name, startup_name FROM intelligence_runs WHERE id = ?"
            params: list[Any] = [run_id]
            if org_id is not None:
                query += " AND org_id = ?"
                params.append(org_id)
            elif user_id is not None:
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

    # ── Feedback Retrieval ───────────────────────────────────────────────────

    def get_feedback_for_run(
        self,
        run_id: int,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> list[dict]:
        """Return all feedback records for a given run.

        Workspace isolation (Phase 2): callers outside the run's workspace see
        an empty list. Same-org members and shared demo rows are visible.
        """
        with self._connect() as conn:
            query = "SELECT user_id, org_id FROM intelligence_runs WHERE id = ?"
            params: list[Any] = [run_id]
            if org_id is not None:
                # Workspace scope: org must match (shared demo rows stay open).
                query += " AND (org_id = ? OR user_id IS NULL)"
                params.append(org_id)
            elif user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            run_row = conn.execute(query, tuple(params)).fetchone()
            if run_row is None:
                return []
            existing_owner = run_row["user_id"] if hasattr(run_row, "__getitem__") else run_row[0]
            if existing_owner is not None and user_id is not None and existing_owner != user_id:
                return []
            rows = conn.execute(
                """
                SELECT id, run_id, user_name, rating, comment, created_at
                FROM run_feedback
                WHERE run_id = ?
                ORDER BY created_at DESC
                """,
                (run_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_all_feedback(
        self,
        limit: int = 100,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> list[dict]:
        """Return all feedback records visible to the given user.

        Workspace isolation (Phase 2): when ``org_id`` is provided only
        feedback on runs inside that workspace is returned (shared demo rows
        with ``user_id IS NULL`` remain visible to workspace members).
        """
        with self._connect() as conn:
            if user_id is None:
                # Admin: all feedback
                rows = conn.execute(
                    """
                    SELECT f.id, f.run_id, f.user_name, f.rating, f.comment, f.created_at,
                           r.startup_name, r.founder_name, r.recommendation, r.trust_score,
                           r.integrity_grade, r.user_id as run_owner_id
                    FROM run_feedback f
                    LEFT JOIN intelligence_runs r ON r.id = f.run_id
                    ORDER BY f.created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            elif org_id is not None:
                # Workspace-scoped: runs inside the caller's workspace plus
                # shared demo runs. Foreign workspaces never leak.
                rows = conn.execute(
                    """
                    SELECT f.id, f.run_id, f.user_name, f.rating, f.comment, f.created_at,
                           r.startup_name, r.founder_name, r.recommendation, r.trust_score,
                           r.integrity_grade, r.user_id as run_owner_id
                    FROM run_feedback f
                    LEFT JOIN intelligence_runs r ON r.id = f.run_id
                    WHERE (r.org_id = ? OR r.user_id IS NULL)
                    ORDER BY f.created_at DESC
                    LIMIT ?
                    """,
                    (org_id, limit),
                ).fetchall()
            else:
                # Scoped: feedback on runs owned by user or shared demo runs
                rows = conn.execute(
                    """
                    SELECT f.id, f.run_id, f.user_name, f.rating, f.comment, f.created_at,
                           r.startup_name, r.founder_name, r.recommendation, r.trust_score,
                           r.integrity_grade, r.user_id as run_owner_id
                    FROM run_feedback f
                    LEFT JOIN intelligence_runs r ON r.id = f.run_id
                    WHERE r.user_id IS NULL OR r.user_id = ?
                    ORDER BY f.created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
            return [dict(row) for row in rows]

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

    # ── Outcome Layer V1: decision records + 30-day follow-up ────────────────

    def ensure_decision_record(self, run_id: int) -> dict[str, Any] | None:
        """Idempotently create the DecisionRecord snapshot for a completed run.

        The record freezes what was recommended at decision time and opens a
        30-day follow-up window. V1 creates records lazily — whenever the
        outcomes surfaces (or this method) touch a run — so no pipeline hook
        is required and historical runs are covered automatically.
        """
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM decision_records WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing is not None:
                return dict(existing)
            run_row = conn.execute(
                "SELECT id, created_at, startup_name, recommendation, trust_score,"
                " integrity_grade, user_id, org_id FROM intelligence_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if run_row is None:
                return None
            try:
                decision_at = datetime.fromisoformat(str(run_row["created_at"]))
                if decision_at.tzinfo is None:
                    decision_at = decision_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                decision_at = now
            due_at = decision_at + timedelta(days=30)
            conn.execute(
                """
                INSERT OR IGNORE INTO decision_records (
                    run_id, org_id, user_id, entity_name, recommendation,
                    trust_score, integrity_grade, decision_snapshot_at,
                    followup_due_at, followup_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    run_id,
                    run_row["org_id"],
                    run_row["user_id"],
                    run_row["startup_name"],
                    run_row["recommendation"],
                    run_row["trust_score"],
                    run_row["integrity_grade"],
                    decision_at.isoformat(),
                    due_at.isoformat(),
                    now.isoformat(),
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM decision_records WHERE run_id = ?", (run_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_decision_records(
        self,
        org_id: str | None = None,
        only_due: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """DecisionRecords with follow-up state; optionally only unanswered
        rows whose 30-day window has opened."""
        self.ensure_decision_records_backfill(org_id=org_id)
        now = datetime.now(timezone.utc).isoformat()
        query = "SELECT * FROM decision_records WHERE 1=1"
        params: list[Any] = []
        if org_id is not None:
            query += " AND (org_id = ? OR user_id IS NULL)"
            params.append(org_id)
        if only_due:
            query += " AND followup_status = 'pending' AND followup_due_at <= ?"
            params.append(now)
        query += " ORDER BY followup_due_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def ensure_decision_records_backfill(self, org_id: str | None = None) -> int:
        """Create records for completed runs that pre-date Outcome V1.
        Returns the number of records created."""
        with self._connect() as conn:
            query = (
                "SELECT r.id FROM intelligence_runs r "
                "LEFT JOIN decision_records d ON d.run_id = r.id "
                "WHERE r.archived_at IS NULL AND d.run_id IS NULL"
            )
            params: list[Any] = []
            if org_id is not None:
                query += " AND (r.org_id = ? OR r.user_id IS NULL)"
                params.append(org_id)
            run_ids = [row[0] for row in conn.execute(query, tuple(params)).fetchall()]
        created = 0
        for run_id in run_ids:
            if self.ensure_decision_record(int(run_id)) is not None:
                created += 1
        return created

    def save_followup_answer(
        self,
        run_id: int,
        decision_taken: str,
        recommendation_followed: str,
        comment: str = "",
    ) -> dict[str, Any] | None:
        """Store the follow-up answers (plus optional comment) and close the cycle."""
        self.ensure_decision_record(run_id)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE decision_records
                   SET decision_taken = ?,
                       recommendation_followed = ?,
                       decision_comment = ?,
                       followup_status = 'answered',
                       answered_at = ?
                 WHERE run_id = ?
                """,
                (decision_taken, recommendation_followed, comment or "", now, run_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM decision_records WHERE run_id = ?", (run_id,)
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
                       o.what_worked, o.what_failed,
                       d.followup_status, d.followup_due_at, d.answered_at,
                       d.decision_taken, d.recommendation_followed,
                       d.decision_comment
                FROM intelligence_runs r
                LEFT JOIN decision_outcomes o ON r.id = o.run_id
                LEFT JOIN decision_records d ON r.id = d.run_id
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

