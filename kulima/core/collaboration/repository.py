"""SQLite persistence for collaboration features (Phase 10).

This repository implements the storage for comments, notes, and review requests
that enable team collaboration on assessments.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from kulima.config import get_settings
from .models import Comment, CommentAnchorType, ReviewRequest, ReviewRequestKind, ReviewRequestStatus

_log = logging.getLogger(__name__)


COLLABORATION_SCHEMA = """
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
"""


class CollaborationRepository:
    """CRUD operations for collaboration features."""

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
            conn.executescript(COLLABORATION_SCHEMA)
            conn.commit()

    # ── Comments ─────────────────────────────────────────────────────────

    def save_comment(self, comment: Comment) -> Comment:
        """Insert or update a comment with org validation."""
        if not comment.org_id:
            raise ValueError("org_id is required for comment creation")
        # Validate case belongs to org
        from kulima.core.cases.repository import CaseRepository
        case_repo = CaseRepository(self.db_path)
        case = case_repo.get(comment.case_id, org_id=comment.org_id)
        if case is None:
            _log.warning("save_comment: case %s not found in org %s", comment.case_id, comment.org_id)
            raise ValueError("Case not found or not in organization")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO comments (
                        id, org_id, case_id, author_id, body, anchor_type, anchor_id,
                        parent_id, created_at, edited_at, deleted_at, deleted_by, mentions_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        comment.id,
                        comment.org_id,
                        comment.case_id,
                        comment.author_id,
                        comment.body,
                        comment.anchor_type.value,
                        comment.anchor_id,
                        comment.parent_id,
                        comment.created_at.isoformat(),
                        comment.edited_at.isoformat() if comment.edited_at else None,
                        comment.deleted_at.isoformat() if comment.deleted_at else None,
                        comment.deleted_by,
                        json.dumps(comment.mentions, default=str),
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return comment

    def get_comment(self, comment_id: str) -> Optional[Comment]:
        """Load a comment by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_comment(row)

    def list_comments_for_case(
        self,
        case_id: str,
        org_id: str | None = None,
        include_deleted: bool = False,
        anchor_type: CommentAnchorType | None = None,
        anchor_id: str | None = None,
    ) -> list[Comment]:
        """List comments for a case with org validation, optionally filtered by anchor."""
        # Validate case belongs to org if org_id provided
        if org_id is not None:
            from kulima.core.cases.repository import CaseRepository
            case_repo = CaseRepository(self.db_path)
            case = case_repo.get(case_id, org_id=org_id)
            if case is None:
                _log.warning("list_comments_for_case: case %s not found in org %s", case_id, org_id)
                return []

        query = "SELECT * FROM comments WHERE case_id = ?"
        params = [case_id]

        if not include_deleted:
            query += " AND deleted_at IS NULL"

        if anchor_type is not None:
            query += " AND anchor_type = ?"
            params.append(anchor_type.value)

        if anchor_id is not None:
            query += " AND anchor_id = ?"
            params.append(anchor_id)

        query += " ORDER BY created_at ASC"

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_comment(row) for row in rows]

    def list_comments_for_anchor(
        self,
        anchor_type: CommentAnchorType,
        anchor_id: str,
        include_deleted: bool = False,
    ) -> list[Comment]:
        """List comments for a specific anchor (document, evidence node, etc.)."""
        query = "SELECT * FROM comments WHERE anchor_type = ? AND anchor_id = ?"
        params = [anchor_type.value, anchor_id]

        if not include_deleted:
            query += " AND deleted_at IS NULL"

        query += " ORDER BY created_at ASC"

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_comment(row) for row in rows]

    def edit_comment(self, comment_id: str, new_body: str, editor_id: str) -> Optional[Comment]:
        """Edit a comment's body."""
        comment = self.get_comment(comment_id)
        if comment is None:
            return None

        comment.body = new_body
        comment.edited_at = datetime.now(timezone.utc)
        return self.save_comment(comment)

    def soft_delete_comment(self, comment_id: str, deleter_id: str) -> Optional[Comment]:
        """Soft delete a comment (recoverable)."""
        comment = self.get_comment(comment_id)
        if comment is None:
            return None

        comment.deleted_at = datetime.now(timezone.utc)
        comment.deleted_by = deleter_id
        return self.save_comment(comment)

    def hard_delete_comment(self, comment_id: str) -> bool:
        """Permanently remove a comment."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
            conn.commit()
            return bool(cur.rowcount)

    # ── Review Requests ───────────────────────────────────────────────────

    def save_review_request(self, request: ReviewRequest, org_id: str | None = None) -> ReviewRequest:
        """Insert or update a review request with org validation."""
        # Validate case belongs to org if org_id provided
        if org_id is not None:
            from kulima.core.cases.repository import CaseRepository
            case_repo = CaseRepository(self.db_path)
            case = case_repo.get(request.case_id, org_id=org_id)
            if case is None:
                _log.warning("save_review_request: case %s not found in org %s", request.case_id, org_id)
                raise ValueError("Case not found or not in organization")

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_requests (
                    id, case_id, kind, requested_by, requested_from, status,
                    resolution_note, created_at, resolved_at, resolved_by, due_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.id,
                    request.case_id,
                    request.kind.value,
                    request.requested_by,
                    request.requested_from,
                    request.status.value,
                    request.resolution_note,
                    request.created_at.isoformat(),
                    request.resolved_at.isoformat() if request.resolved_at else None,
                    request.resolved_by,
                    request.due_at.isoformat() if request.due_at else None,
                ),
            )
            conn.commit()
        return request

    def get_review_request(self, request_id: str) -> Optional[ReviewRequest]:
        """Load a review request by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM review_requests WHERE id = ?", (request_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_review_request(row)

    def list_review_requests_for_case(self, case_id: str, org_id: str | None = None) -> list[ReviewRequest]:
        """List all review requests for a case with optional org validation."""
        # Validate case belongs to org if org_id provided
        if org_id is not None:
            from kulima.core.cases.repository import CaseRepository
            case_repo = CaseRepository(self.db_path)
            case = case_repo.get(case_id, org_id=org_id)
            if case is None:
                _log.warning("list_review_requests_for_case: case %s not found in org %s", case_id, org_id)
                return []

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM review_requests WHERE case_id = ? ORDER BY created_at DESC",
                (case_id,),
            ).fetchall()
        return [self._row_to_review_request(row) for row in rows]

    def list_pending_reviews_for_user(self, user_id: str) -> list[ReviewRequest]:
        """List pending review requests assigned to a user."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM review_requests
                WHERE requested_from = ? AND status IN ('pending', 'in_progress')
                ORDER BY created_at ASC
                """,
                (user_id,),
            ).fetchall()
        return [self._row_to_review_request(row) for row in rows]

    def resolve_review_request(
        self,
        request_id: str,
        status: ReviewRequestStatus,
        resolver_id: str,
        resolution_note: str = "",
    ) -> Optional[ReviewRequest]:
        """Resolve a review request (approve/reject/cancel)."""
        request = self.get_review_request(request_id)
        if request is None:
            return None

        request.status = status
        request.resolved_at = datetime.now(timezone.utc)
        request.resolved_by = resolver_id
        request.resolution_note = resolution_note
        return self.save_review_request(request)

    def delete_review_request(self, request_id: str) -> bool:
        """Permanently remove a review request."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM review_requests WHERE id = ?", (request_id,))
            conn.commit()
            return bool(cur.rowcount)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_comment(row: sqlite3.Row) -> Comment:
        """Convert database row to Comment model."""
        def _load_json(column: str, default):
            try:
                return json.loads(row[column]) if row[column] else default
            except Exception:
                return default

        return Comment(
            id=row["id"],
            org_id=row["org_id"],
            case_id=row["case_id"],
            author_id=row["author_id"],
            body=row["body"],
            anchor_type=CommentAnchorType(row["anchor_type"]),
            anchor_id=row["anchor_id"],
            parent_id=row["parent_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            edited_at=datetime.fromisoformat(row["edited_at"]) if row["edited_at"] else None,
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
            deleted_by=row["deleted_by"],
            mentions=_load_json("mentions_json", []),
        )

    @staticmethod
    def _row_to_review_request(row: sqlite3.Row) -> ReviewRequest:
        """Convert database row to ReviewRequest model."""
        return ReviewRequest(
            id=row["id"],
            case_id=row["case_id"],
            kind=ReviewRequestKind(row["kind"]),
            requested_by=row["requested_by"],
            requested_from=row["requested_from"],
            status=ReviewRequestStatus(row["status"]),
            resolution_note=row["resolution_note"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            resolved_by=row["resolved_by"],
            due_at=datetime.fromisoformat(row["due_at"]) if row["due_at"] else None,
        )
