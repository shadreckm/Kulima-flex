"""SQLite-backed repository for Document Intelligence (Phase A).

This repository is layered on top of the existing Kulima SQLite database
used by IntelligenceRepository.  It adds two tables:

- documents        — one row per logical Document
- document_chunks  — one row per DocumentChunk

The schema is intentionally minimal and tolerant of future evolution.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List

from kulima.config import get_settings
from kulima.core.documents.models import Document, DocumentChunk

_log = logging.getLogger(__name__)


DOCUMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    run_id INTEGER,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    uploaded_by TEXT,
    uploaded_at TEXT NOT NULL,
    source_type TEXT,
    entities_json TEXT,
    tags_json TEXT,
    metadata_json TEXT,
    org_id TEXT,
    assessment_id TEXT,
    storage_path TEXT,
    size_bytes INTEGER,
    sha256 TEXT,
    visibility TEXT DEFAULT 'private',
    retention_days INTEGER,
    expires_at TEXT,
    deleted_at TEXT,
    deleted_by TEXT,
    encryption_json TEXT
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    page_number INTEGER,
    section_heading TEXT,
    text TEXT NOT NULL,
    tokens INTEGER,
    metadata_json TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
"""

# Phase 5 (Document Security): columns added to pre-existing databases.
_DOCUMENT_SECURITY_COLUMNS: dict[str, str] = {
    "org_id": "TEXT",
    "assessment_id": "TEXT",
    "storage_path": "TEXT",
    "size_bytes": "INTEGER",
    "sha256": "TEXT",
    "visibility": "TEXT DEFAULT 'private'",
    "retention_days": "INTEGER",
    "expires_at": "TEXT",
    "deleted_at": "TEXT",
    "deleted_by": "TEXT",
    "encryption_json": "TEXT",
}


class DocumentRepository:
    """Persistence layer for Documents and DocumentChunks.

    Phase A focuses on basic create/read operations keyed by run_id and
    document_id.  It reuses the same SQLite database path as
    IntelligenceRepository, but does not alter the existing
    intelligence_runs schema.
    """

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
            conn.executescript(DOCUMENT_SCHEMA)
            self._migrate_schema(conn)
            conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Idempotent, additive migration for the document-security columns."""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
        for column, ddl in _DOCUMENT_SECURITY_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {column} {ddl}")
                _log.debug("documents migration: added column %s", column)
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_org ON documents(org_id);
            CREATE INDEX IF NOT EXISTS idx_documents_assessment ON documents(assessment_id);
            CREATE INDEX IF NOT EXISTS idx_documents_storage_path ON documents(storage_path);
            """
        )

    # ── Save operations ──────────────────────────────────────────────────

    def save_document(
        self,
        run_id: int | None,
        doc: Document,
        *,
        org_id: str | None = None,
        assessment_id: str | None = None,
        storage_path: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        visibility: str = "private",
        retention_days: int | None = None,
        expires_at: str | None = None,
        encryption_metadata: dict | None = None,
    ) -> None:
        """Insert or replace a Document row.

        run_id is optional to allow documents to exist independently of a
        stored intelligence run, but FLEX will typically provide it.

        Enterprise Trust (Phase 5) adds the security envelope: workspace
        binding (org_id/assessment_id), storage metadata (path, size, hash,
        encryption), visibility (private by default), retention and expiry.
        """

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    id, run_id, filename, mime_type, doc_type, uploaded_by,
                    uploaded_at, source_type, entities_json, tags_json,
                    metadata_json, org_id, assessment_id, storage_path,
                    size_bytes, sha256, visibility, retention_days, expires_at,
                    encryption_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.id,
                    run_id,
                    doc.filename,
                    doc.mime_type,
                    doc.doc_type.value,
                    doc.uploaded_by,
                    doc.uploaded_at.isoformat(),
                    doc.source_type,
                    json.dumps(doc.entities),
                    json.dumps(doc.tags),
                    json.dumps(doc.metadata),
                    org_id,
                    assessment_id,
                    storage_path,
                    size_bytes,
                    sha256,
                    visibility or "private",
                    retention_days,
                    expires_at,
                    json.dumps(encryption_metadata) if encryption_metadata else None,
                ),
            )
            conn.commit()

    def save_chunks(self, chunks: List[DocumentChunk]) -> None:
        if not chunks:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO document_chunks (
                    id, document_id, sequence, page_number, section_heading,
                    text, tokens, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        ch.id,
                        ch.document_id,
                        ch.sequence,
                        ch.page_number,
                        ch.section_heading,
                        ch.text,
                        ch.tokens,
                        json.dumps(ch.metadata),
                    )
                    for ch in chunks
                ],
            )
            conn.commit()

    def link_documents_to_run(self, document_ids: List[str], run_id: int) -> int:
        """Attach previously uploaded documents to a stored intelligence run.

        Landing-page intake uploads happen before a run exists (run_id NULL).
        Once the run is created we bind those documents so the Evidence
        workspace, Ask IC, and ``get_documents_for_subject`` can find them.

        Returns the number of rows updated.
        """
        ids = [str(d) for d in (document_ids or []) if d]
        if not ids or run_id is None:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE documents SET run_id = ? WHERE id IN ({placeholders})",
                (int(run_id), *ids),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    # ── Retrieval operations ─────────────────────────────────────────────

    def get_documents_for_run(self, run_id: int) -> list[Document]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM documents
                WHERE run_id = ? AND deleted_at IS NULL
                ORDER BY uploaded_at ASC
                """,
                (run_id,),
            ).fetchall()
        return [self._row_to_document(r) for r in rows]

    def get_chunks_for_document(self, document_id: str) -> list[DocumentChunk]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM document_chunks WHERE document_id = ? ORDER BY sequence ASC",
                (document_id,),
            ).fetchall()
        return [self._row_to_chunk(r) for r in rows]

    def get_documents_for_subject(
        self,
        founder: str,
        startup: str,
        *,
        user_id: str | None = None,
    ) -> list[Document]:
        """Return all documents associated with the given founder/startup pair.

        Association is inferred via the ``run_id`` column joined against
        ``intelligence_runs``.  This keeps the Document layer generic while
        allowing FLEX to attach documents to specific deals. Soft-deleted
        documents are excluded (Phase 5).
        """
        with self._connect() as conn:
            query = """
                SELECT d.*
                FROM documents d
                JOIN intelligence_runs r ON d.run_id = r.id
                WHERE r.founder_name = ? AND r.startup_name = ?
                  AND d.deleted_at IS NULL
            """
            params: list[object] = [founder, startup]
            if user_id is not None:
                query += " AND r.user_id = ?"
                params.append(user_id)
            query += " ORDER BY d.uploaded_at ASC"
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_document(r) for r in rows]

    # ── Enterprise Trust: security, retention & data ownership ──────────

    def get_document(self, document_id: str) -> dict | None:
        """Return the raw document row as a payload dict (None when absent)."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return self._row_to_payload(row) if row else None

    def find_by_storage_path(self, storage_path: str) -> dict | None:
        """Resolve a document by its stored filename (guarded /uploads route)."""
        if not storage_path:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE storage_path = ? ORDER BY uploaded_at DESC LIMIT 1",
                (str(storage_path),),
            ).fetchone()
        return self._row_to_payload(row) if row else None

    def list_documents(
        self,
        *,
        org_id: str | None = None,
        run_id: int | None = None,
        assessment_id: str | None = None,
        uploaded_by: str | None = None,
        include_deleted: bool = False,
        limit: int = 200,
    ) -> list[dict]:
        """Workspace-scoped document listing (Phase 1 & 5)."""
        query = "SELECT * FROM documents WHERE 1=1"
        params: list[object] = []
        if org_id is not None:
            query += " AND org_id = ?"
            params.append(org_id)
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if assessment_id is not None:
            query += " AND assessment_id = ?"
            params.append(assessment_id)
        if uploaded_by is not None:
            query += " AND uploaded_by = ?"
            params.append(uploaded_by)
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        query += " ORDER BY uploaded_at DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_payload(r) for r in rows]

    def soft_delete_document(self, document_id: str, *, deleted_by: str | None = None) -> bool:
        """Mark a document deleted. Content stays recoverable for the grace window."""
        from datetime import datetime, timezone

        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE documents SET deleted_at = ?, deleted_by = ? WHERE id = ? AND deleted_at IS NULL",
                (datetime.now(timezone.utc).isoformat(), deleted_by, document_id),
            )
            conn.commit()
            return bool(cur.rowcount)

    def hard_delete_document(self, document_id: str) -> bool:
        """Permanently purge a document row and its chunks (complete deletion)."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
            conn.commit()
            return bool(cur.rowcount)

    def link_documents_to_assessment(
        self,
        document_ids: List[str],
        assessment_id: str,
        *,
        org_id: str | None = None,
    ) -> int:
        """Bind documents to an assessment (retention/ownership bookkeeping)."""
        ids = [str(d) for d in (document_ids or []) if d]
        if not ids or not assessment_id:
            return 0
        placeholders = ",".join("?" for _ in ids)
        set_clause = "assessment_id = ?"
        params: list[object] = [assessment_id]
        if org_id is not None:
            set_clause += ", org_id = COALESCE(org_id, ?)"
            params.append(org_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE documents SET {set_clause} WHERE id IN ({placeholders})",
                (*params, *ids),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def document_stats(self, *, org_id: str | None = None) -> dict:
        """Aggregate figures for the Trust & Governance dashboard (Phase 9)."""
        from datetime import datetime, timezone

        query = "SELECT * FROM documents"
        params: list[object] = []
        if org_id is not None:
            query += " WHERE org_id = ?"
            params.append(org_id)
        with self._connect() as conn:
            rows = [self._row_to_payload(r) for r in conn.execute(query, tuple(params)).fetchall()]

        now = datetime.now(timezone.utc)
        total = len(rows)
        inactive = sum(1 for r in rows if r.get("deletedAt") or self.is_expired(r, now=now))
        deleted = sum(1 for r in rows if r.get("deletedAt"))
        expired = sum(1 for r in rows if self.is_expired(r, now=now))
        return {
            "total": total,
            "active": max(0, total - inactive),
            "deleted": deleted,
            "expired": expired,
            "storageBytes": sum(int(r.get("sizeBytes") or 0) for r in rows),
            "encrypted": sum(1 for r in rows if (r.get("encryption") or {}).get("encrypted")),
            "scheduledForDeletion": sum(
                1 for r in rows if r.get("deletedAt") and not r.get("purgedAt")
            ),
        }

    @staticmethod
    def is_expired(doc: dict, *, now=None) -> bool:
        """True when the document's retention window has elapsed (Phase 5)."""
        expires_at = doc.get("expiresAt")
        if not expires_at:
            return False
        from datetime import datetime, timezone

        try:
            deadline = datetime.fromisoformat(str(expires_at))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        return (now or datetime.now(timezone.utc)) >= deadline

    @staticmethod
    def _row_to_payload(row: sqlite3.Row) -> dict:
        """Raw row → API dict with parsed JSON columns (camelCase)."""
        keys = row.keys()

        def _load(column: str, default):
            try:
                return json.loads(row[column]) if row[column] else default
            except Exception:  # noqa: BLE001
                return default

        def _get(column: str, default=None):
            return row[column] if column in keys else default

        return {
            "id": row["id"],
            "runId": _get("run_id"),
            "filename": row["filename"],
            "mimeType": row["mime_type"],
            "docType": row["doc_type"],
            "uploadedBy": row["uploaded_by"],
            "uploadedAt": row["uploaded_at"],
            "sourceType": row["source_type"],
            "entities": _load("entities_json", []),
            "tags": _load("tags_json", []),
            "metadata": _load("metadata_json", {}),
            "orgId": _get("org_id"),
            "assessmentId": _get("assessment_id"),
            "storagePath": _get("storage_path"),
            "sizeBytes": _get("size_bytes"),
            "sha256": _get("sha256"),
            "visibility": _get("visibility") or "private",
            "retentionDays": _get("retention_days"),
            "expiresAt": _get("expires_at"),
            "deletedAt": _get("deleted_at"),
            "deletedBy": _get("deleted_by"),
            "encryption": _load("encryption_json", None),
        }

    # ── Helpers ──────────────────────────────────────────────────────────

    def _row_to_document(self, row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            filename=row["filename"],
            mime_type=row["mime_type"],
            doc_type=row["doc_type"],
            uploaded_by=row["uploaded_by"],
            uploaded_at=row["uploaded_at"],
            source_type=row["source_type"] or "user_uploaded",
            entities=json.loads(row["entities_json"] or "[]"),
            tags=json.loads(row["tags_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _row_to_chunk(self, row: sqlite3.Row) -> DocumentChunk:
        return DocumentChunk(
            id=row["id"],
            document_id=row["document_id"],
            sequence=row["sequence"],
            page_number=row["page_number"],
            section_heading=row["section_heading"],
            text=row["text"],
            tokens=row["tokens"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
