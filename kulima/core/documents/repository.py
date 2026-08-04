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
    metadata_json TEXT
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
            conn.commit()

    # ── Save operations ──────────────────────────────────────────────────

    def save_document(self, run_id: int | None, doc: Document) -> None:
        """Insert or replace a Document row.

        run_id is optional to allow documents to exist independently of a
        stored intelligence run, but FLEX will typically provide it.
        """

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    id, run_id, filename, mime_type, doc_type, uploaded_by,
                    uploaded_at, source_type, entities_json, tags_json,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    # ── Retrieval operations ─────────────────────────────────────────────

    def get_documents_for_run(self, run_id: int) -> list[Document]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE run_id = ? ORDER BY uploaded_at ASC",
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
        allowing FLEX to attach documents to specific deals.
        """
        with self._connect() as conn:
            query = """
                SELECT d.*
                FROM documents d
                JOIN intelligence_runs r ON d.run_id = r.id
                WHERE r.founder_name = ? AND r.startup_name = ?
            """
            params: list[object] = [founder, startup]
            if user_id is not None:
                query += " AND r.user_id = ?"
                params.append(user_id)
            query += " ORDER BY d.uploaded_at ASC"
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_document(r) for r in rows]

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
