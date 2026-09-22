"""SQLite persistence for the audit event stream.

Design notes:

- Append-only. Events are never updated; deletion of user data does not
  rewrite history (the audit trail records that the deletion happened).
- ``record_event`` is intentionally failure-tolerant: governance must never
  break the user-facing pipeline, so call sites never have to guard it.
- Events are scoped by ``org_id`` for workspace isolation and by
  ``assessment_id`` / ``run_id`` / ``document_id`` for the Activity Timeline.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from kulima.config import get_settings

_log = logging.getLogger(__name__)


AUDIT_SCHEMA = """
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

CREATE INDEX IF NOT EXISTS idx_audit_org_created
    ON audit_events(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_assessment
    ON audit_events(assessment_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_run
    ON audit_events(run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_case
    ON audit_events(case_id, created_at DESC);
"""


# Canonical event types surfaced in the Trust & Governance dashboard.
EVENT_TYPES: dict[str, str] = {
    "document.uploaded": "Document Upload",
    "document.downloaded": "Document Downloaded",
    "document.deleted": "Document Deleted",
    "document.exported": "Documents Exported",
    "assessment.created": "Assessment Created",
    "assessment.started": "Assessment Run Started",
    "assessment.deleted": "Assessment Deleted",
    "signals.generated": "Signals Generated",
    "decision.generated": "Decision Generated",
    "report.exported": "Report Exported",
    "user.login": "User Login",
    "research.triggered": "External Research Triggered",
    "org.member_added": "Member Added",
    "org.role_changed": "Role Changed",
    "org.member_removed": "Member Removed",
    "billing.checkout_started": "Checkout Started",
    "billing.payment_received": "Payment Received",
    "billing.payment_failed": "Payment Failed",
    "billing.plan_changed": "Plan Changed",
    "billing.grace_started": "Grace Period Started",
    "billing.suspended": "Account Suspended",
    "billing.reactivated": "Account Reactivated",
    # Phase 4 Enterprise: New event types for collaboration and lifecycle
    "research.started": "Research Started",
    "research.completed": "Research Completed",
    "document.extraction_completed": "Document Extraction Completed",
    "case.lifecycle_changed": "Case Lifecycle Changed",
    "case.created": "Case Created",
    "review.requested": "Review Requested",
    "review.approved": "Review Approved",
    "review.rejected": "Review Rejected",
    "comment.added": "Comment Added",
    "comment.edited": "Comment Edited",
    "comment.deleted": "Comment Deleted",
    "dossier.generated": "Decision Dossier Generated",
    "dossier.approved": "Decision Dossier Approved",
    "session.exit_with_pending": "Session Exit with Pending Tasks",
}

LABELS_BY_PREFIX = {
    "document": "Documents",
    "assessment": "Assessments",
    "signals": "Signals",
    "decision": "Decision",
    "report": "Reports",
    "user": "Access",
    "research": "Research",
    "org": "Team",
    "billing": "Billing",
}


def event_label(event_type: str) -> str:
    if event_type in EVENT_TYPES:
        return EVENT_TYPES[event_type]
    return event_type.replace(".", " ").replace("_", " ").title()


def event_category(event_type: str) -> str:
    return LABELS_BY_PREFIX.get(str(event_type).split(".", 1)[0], "Other")


class AuditRepository:
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
            conn.executescript(AUDIT_SCHEMA)
            # Enterprise Phase 4: Add new columns for forensics and case linkage
            self._migrate_schema(conn)
            conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Add enterprise audit columns if they don't exist."""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(audit_events)")}
        if "case_id" not in existing:
            conn.execute("ALTER TABLE audit_events ADD COLUMN case_id TEXT")
            _log.debug("_migrate_schema: added column case_id")
        if "ip_hash" not in existing:
            conn.execute("ALTER TABLE audit_events ADD COLUMN ip_hash TEXT")
            _log.debug("_migrate_schema: added column ip_hash")
        if "user_agent" not in existing:
            conn.execute("ALTER TABLE audit_events ADD COLUMN user_agent TEXT")
            _log.debug("_migrate_schema: added column user_agent")
        # Create case_id index if it doesn't exist
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(case_id, created_at DESC)")
        except Exception:  # noqa: BLE001
            pass

    # ── Writes ───────────────────────────────────────────────────────────

    def record(
        self,
        event_type: str,
        *,
        org_id: str | None = None,
        user_id: str | None = None,
        run_id: str | None = None,
        assessment_id: str | None = None,
        document_id: str | None = None,
        case_id: str | None = None,
        metadata: dict | None = None,
        ip_hash: str | None = None,
        user_agent: str | None = None,
    ) -> int | None:
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO audit_events (
                        event_type, org_id, user_id, run_id, assessment_id, document_id,
                        case_id, metadata_json, ip_hash, user_agent, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_type,
                        org_id,
                        user_id,
                        str(run_id) if run_id is not None else None,
                        assessment_id,
                        document_id,
                        case_id,
                        json.dumps(metadata or {}, default=str),
                        ip_hash,
                        user_agent,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
                return int(cur.lastrowid) if cur.lastrowid is not None else None
        except Exception as exc:  # noqa: BLE001 — audit must never break the pipeline
            _log.warning("audit_record_failed type=%s error=%s", event_type, exc)
            return None

    def record_once(
        self,
        event_type: str,
        *,
        dedupe_key: str,
        **kwargs,
    ) -> int | None:
        """Record an event only if no event with the same dedupe metadata exists.

        Used for webhook idempotency (PayChangu may retry) and for
        once-per-session markers.
        """
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id FROM audit_events
                    WHERE event_type = ? AND json_extract(metadata_json, '$.dedupeKey') = ?
                    LIMIT 1
                    """,
                    (event_type, dedupe_key),
                ).fetchone()
            if row is not None:
                return None
        except Exception:  # noqa: BLE001 — fall through to plain record
            pass
        metadata = dict(kwargs.pop("metadata", {}) or {})
        metadata["dedupeKey"] = dedupe_key
        return self.record(event_type, metadata=metadata, **kwargs)

    # ── Reads ────────────────────────────────────────────────────────────

    def list(
        self,
        *,
        org_id: str | None = None,
        assessment_id: str | None = None,
        run_id: str | None = None,
        user_id: str | None = None,
        event_types: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list[object] = []
        if org_id is not None:
            query += " AND org_id = ?"
            params.append(org_id)
        if assessment_id is not None:
            query += " AND assessment_id = ?"
            params.append(assessment_id)
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(str(run_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        if event_types:
            placeholders = ",".join("?" for _ in event_types)
            query += f" AND event_type IN ({placeholders})"
            params.extend(event_types)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count(self, *, org_id: str | None = None, since: str | None = None) -> int:
        query = "SELECT COUNT(*) AS c FROM audit_events WHERE 1=1"
        params: list[object] = []
        if org_id is not None:
            query += " AND org_id = ?"
            params.append(org_id)
        if since is not None:
            query += " AND created_at >= ?"
            params.append(since)
        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        return int(row["c"] if row else 0)

    def latest(self, *, org_id: str | None = None) -> dict | None:
        events = self.list(org_id=org_id, limit=1)
        return events[0] if events else None

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> dict:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except Exception:  # noqa: BLE001
            metadata = {}
        return {
            "id": row["id"],
            "eventType": row["event_type"],
            "label": event_label(row["event_type"]),
            "category": event_category(row["event_type"]),
            "orgId": row["org_id"],
            "userId": row["user_id"],
            "runId": row["run_id"],
            "assessmentId": row["assessment_id"],
            "documentId": row["document_id"],
            "metadata": metadata,
            "createdAt": row["created_at"],
        }


# ── Module-level convenience API (used across routers/adapters) ──────────────

def record_event(
    event_type: str,
    *,
    org_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
    assessment_id: str | None = None,
    document_id: str | None = None,
    case_id: str | None = None,
    metadata: dict | None = None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> int | None:
    return AuditRepository().record(
        event_type,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        assessment_id=assessment_id,
        document_id=document_id,
        case_id=case_id,
        metadata=metadata,
        ip_hash=ip_hash,
        user_agent=user_agent,
    )


def list_events(**kwargs) -> list[dict]:
    return AuditRepository().list(**kwargs)
