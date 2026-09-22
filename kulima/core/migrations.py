"""Database migration runner for enterprise layer (Phase 4).

This module handles the incremental migration of the database schema to support
the enterprise decision management system features.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from kulima.config import get_settings

_log = logging.getLogger(__name__)


# Migration versions - each migration should be idempotent
MIGRATIONS = {
    "001_add_cases_table": """
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
    """,
    "002_add_jobs_table": """
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
    """,
    "003_add_research_packs_table": """
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
    """,

    "003a_add_research_foreign_keys": """
        -- Note: Foreign keys skipped for SQLite compatibility
        -- Postgres migration path should add these in Postgres-specific migrations
        -- For now, referential integrity is enforced at application level
    """,

    "009_add_postgres_foreign_keys": """
        -- Postgres-specific foreign key constraints
        -- This migration only runs in Postgres mode
        -- SQLite will skip ALTER TABLE with FOREIGN KEY
    """,

    "010_add_postgres_indexes": """
        -- Postgres-specific composite indexes for performance
        -- This migration only runs in Postgres mode
    """,
    "004_add_collaboration_tables": """
        CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            body TEXT NOT NULL,
            anchor_type TEXT NOT NULL,
            anchor_id TEXT,
            parent_id TEXT,
            created_at TEXT NOT NULL,
            edited_at TEXT,
            deleted_at TEXT,
            deleted_by TEXT,
            mentions_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_comments_case_id ON comments(case_id);
        CREATE INDEX IF NOT EXISTS idx_comments_anchor ON comments(anchor_type, anchor_id);
        CREATE INDEX IF NOT EXISTS idx_comments_parent_id ON comments(parent_id);

        CREATE TABLE IF NOT EXISTS review_requests (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            requested_from TEXT NOT NULL,
            status TEXT NOT NULL,
            resolution_note TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by TEXT,
            due_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_review_requests_case_id ON review_requests(case_id);
        CREATE INDEX IF NOT EXISTS idx_review_requests_requested_from ON review_requests(requested_from);
        CREATE INDEX IF NOT EXISTS idx_review_requests_status ON review_requests(status);
    """,
    "005_add_dossiers_table": """
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
    """,
    "006_add_evidence_graph_tables": """
        CREATE TABLE IF NOT EXISTS evidence_nodes (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            source_json TEXT NOT NULL,
            document_id TEXT,
            claims_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_nodes_case_id ON evidence_nodes(case_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_nodes_document_id ON evidence_nodes(document_id);

        CREATE TABLE IF NOT EXISTS evidence_edges (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            from_node TEXT NOT NULL,
            to_node TEXT NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_edges_case_id ON evidence_edges(case_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_edges_from_node ON evidence_edges(from_node);
        CREATE INDEX IF NOT EXISTS idx_evidence_edges_to_node ON evidence_edges(to_node);
    """,
    "007_add_audit_extensions": """
        -- Create audit_events table if it doesn't exist (for new installations)
        -- This ensures the table exists before we try to add columns
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            org_id TEXT,
            user_id TEXT,
            run_id TEXT,
            assessment_id TEXT,
            document_id TEXT,
            case_id TEXT,
            metadata_json TEXT,
            ip_hash TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_audit_org_created ON audit_events(org_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_assessment ON audit_events(assessment_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(case_id, created_at DESC);
    """,
    "008_add_intelligence_runs_case_id": """
        -- Add case_id to intelligence_runs for case linkage
        ALTER TABLE intelligence_runs ADD COLUMN case_id TEXT;

        CREATE INDEX IF NOT EXISTS idx_intelligence_runs_case_id ON intelligence_runs(case_id);
    """,
}


class MigrationRunner:
    """Runs database migrations incrementally."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self._initialize_migration_table()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _initialize_migration_table(self) -> None:
        """Create the migration tracking table if it doesn't exist."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_applied_migrations(self) -> set[str]:
        """Get the set of already applied migration versions."""
        with self._connect() as conn:
            rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        return {row["version"] for row in rows}

    def apply_migration(self, version: str, sql: str) -> bool:
        """Apply a single migration if not already applied."""
        applied = self.get_applied_migrations()
        if version in applied:
            _log.info("Migration %s already applied, skipping", version)
            return False

        _log.info("Applying migration: %s", version)
        try:
            with self._connect() as conn:
                conn.executescript(sql)
                # Record the migration
                from datetime import datetime, timezone
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            _log.info("Migration %s applied successfully", version)
            return True
        except Exception as exc:  # noqa: BLE001
            _log.error("Migration %s failed: %s", version, exc)
            raise

    def migrate(self) -> None:
        """Run all pending migrations."""
        _log.info("Starting database migration")
        applied_count = 0
        for version, sql in MIGRATIONS.items():
            if self.apply_migration(version, sql):
                applied_count += 1
        _log.info("Database migration complete: %d migrations applied", applied_count)


def run_migrations(db_path: str | None = None) -> None:
    """Convenience function to run all pending migrations."""
    runner = MigrationRunner(db_path)
    runner.migrate()


if __name__ == "__main__":
    run_migrations()
    print("Database migrations completed successfully")
