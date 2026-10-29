"""SQLite persistence for collection channels (Forms Integration V1).

Two planes, deliberately separated:

* **source plane** (this module) — connections, the discovered instrument
  schema, one row per collected response, one row per materialised batch.
  This is provenance and re-derivation data.
* **evidence plane** (``documents`` / ``document_chunks`` /
  ``InvestmentBrief.uploaded_evidence``) — owned by the existing pipeline.
  A batch lands there through ``save_uploaded_file`` and nothing else.

Credentials are never stored in clear text. An OAuth refresh token grants the
same access as the consent screen granted, so if the storage key is missing the
repository refuses to persist it and the connection stays ``pending_auth`` with
a visible error — the gap is reported, not papered over.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from kulima.core.security.encryption import EncryptionUnavailable, decrypt_bytes, encrypt_bytes
from kulima.config import get_settings

from .models import CollectionBatch, CollectedAnswer, CollectedResponse, ConnectionStatus, FormConnection

_log = logging.getLogger(__name__)

FORMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_connections (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    form_id TEXT,
    sheet_id TEXT,
    sheet_range TEXT,
    title TEXT,
    purpose TEXT NOT NULL DEFAULT 'evidence',
    status TEXT NOT NULL DEFAULT 'pending_auth',
    owner_user_id TEXT,
    schema_json TEXT,
    schema_hash TEXT,
    credential_json TEXT,
    credential_scheme TEXT,
    evidence_class TEXT,
    note TEXT,
    last_synced_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_form_connections_org
    ON form_connections(org_id, assessment_id);
CREATE INDEX IF NOT EXISTS idx_form_connections_form
    ON form_connections(org_id, form_id);

CREATE TABLE IF NOT EXISTS form_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    response_id TEXT NOT NULL,
    submitted_at TEXT,
    respondent_type TEXT,
    respondent_ref TEXT,
    completeness_pct REAL,
    consistency TEXT,
    verification_status TEXT,
    trust_score REAL,
    answers_json TEXT,
    batch_id TEXT,
    collected_at TEXT NOT NULL,
    UNIQUE (connection_id, response_id)
);

CREATE INDEX IF NOT EXISTS idx_form_responses_connection
    ON form_responses(connection_id, batch_id);
CREATE INDEX IF NOT EXISTS idx_form_responses_org
    ON form_responses(org_id, assessment_id, collected_at DESC);

CREATE TABLE IF NOT EXISTS form_batches (
    id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    document_id TEXT,
    run_id TEXT,
    filename TEXT,
    response_count INTEGER NOT NULL DEFAULT 0,
    window_start TEXT,
    window_end TEXT,
    trust_score REAL,
    evidence_status TEXT,
    digest_text TEXT,
    response_ids_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_form_batches_connection
    ON form_batches(connection_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_form_batches_org
    ON form_batches(org_id, assessment_id, created_at DESC);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seal_credentials(payload: dict) -> tuple[str, str]:
    """Encrypt + base64 an OAuth token set. Raises if storage cannot encrypt."""
    blob = encrypt_bytes(json.dumps(payload, default=str).encode("utf-8"))
    return base64.b64encode(blob).decode("ascii"), "aes-256-gcm"


def _open_credentials(sealed: Optional[str], scheme: Optional[str]) -> dict:
    if not sealed:
        return {}
    if scheme != "aes-256-gcm":
        _log.warning("form credentials stored with unsupported scheme %s — ignored", scheme)
        return {}
    try:
        raw = base64.b64decode(sealed)
        return json.loads(decrypt_bytes(raw).decode("utf-8"))
    except (EncryptionUnavailable, ValueError, binascii.Error, TypeError) as exc:
        _log.warning("could not decrypt stored form credentials: %s", exc)
        return {}


class FormsRepository:
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
            conn.executescript(FORMS_SCHEMA)
            conn.commit()

    # ── Connections ────────────────────────────────────────────────────────

    def save_connection(self, conn: FormConnection) -> FormConnection:
        conn.updated_at = datetime.now(timezone.utc)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT credential_json, credential_scheme FROM form_connections WHERE id = ?",
                    (conn.id,),
                ).fetchone()
                sealed = existing["credential_json"] if existing else None
                scheme = existing["credential_scheme"] if existing else None
                db.execute(
                    """
                    INSERT INTO form_connections (
                        id, org_id, assessment_id, kind, form_id, sheet_id, sheet_range,
                        title, purpose, status, owner_user_id, schema_json, schema_hash,
                        credential_json, credential_scheme, evidence_class, note,
                        last_synced_at, last_error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        kind=excluded.kind, form_id=excluded.form_id, sheet_id=excluded.sheet_id,
                        sheet_range=excluded.sheet_range, title=excluded.title,
                        purpose=excluded.purpose, status=excluded.status,
                        owner_user_id=excluded.owner_user_id, schema_json=excluded.schema_json,
                        schema_hash=excluded.schema_hash, credential_json=excluded.credential_json,
                        credential_scheme=excluded.credential_scheme,
                        evidence_class=excluded.evidence_class, note=excluded.note,
                        last_synced_at=excluded.last_synced_at, last_error=excluded.last_error,
                        updated_at=excluded.updated_at
                    """,
                    (
                        conn.id,
                        conn.org_id,
                        conn.assessment_id,
                        conn.kind,
                        conn.form_id,
                        conn.sheet_id,
                        conn.sheet_range,
                        conn.title,
                        conn.purpose,
                        conn.status,
                        conn.owner_user_id,
                        json.dumps([q.model_dump() for q in conn.questions], default=str),
                        conn.schema_hash,
                        sealed,
                        scheme,
                        conn.evidence_class,
                        conn.note,
                        conn.last_synced_at or None,
                        conn.last_error or None,
                        conn.created_at.isoformat(),
                        conn.updated_at.isoformat(),
                    ),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return conn

    def set_credentials(self, connection_id: str, token_set: dict) -> bool:
        """Store an OAuth token set encrypted. False when storage cannot encrypt."""
        try:
            sealed, scheme = _seal_credentials(token_set)
        except EncryptionUnavailable:
            _log.warning(
                "refusing to store form credentials without KULIMA_DOC_ENCRYPTION_KEY (connection %s)",
                connection_id,
            )
            return False
        with self._connect() as db:
            db.execute(
                "UPDATE form_connections SET credential_json = ?, credential_scheme = ?, updated_at = ? WHERE id = ?",
                (sealed, scheme, _now_iso(), connection_id),
            )
            db.commit()
        return True

    def get_credentials(self, connection_id: str) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT credential_json, credential_scheme FROM form_connections WHERE id = ?",
                (connection_id,),
            ).fetchone()
        if row is None:
            return {}
        return _open_credentials(row["credential_json"], row["credential_scheme"])

    def clear_credentials(self, connection_id: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE form_connections SET credential_json = NULL, credential_scheme = NULL, updated_at = ? WHERE id = ?",
                (_now_iso(), connection_id),
            )
            db.commit()

    def get_connection(self, connection_id: str, *, org_id: Optional[str] = None) -> Optional[FormConnection]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM form_connections WHERE id = ?", (connection_id,)).fetchone()
            # The conversion runs two count queries, so it must happen while the
            # connection is still open (same as find_connection_by_form/list_connections).
            if row is None or (org_id is not None and row["org_id"] != org_id):
                return None
            return self._row_to_connection(db, row)

    def find_connection_by_form(self, org_id: str, assessment_id: str, form_id: str) -> Optional[FormConnection]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM form_connections WHERE org_id = ? AND assessment_id = ? AND form_id = ? AND status != 'revoked'",
                (org_id, assessment_id, form_id),
            ).fetchone()
            return self._row_to_connection(db, row) if row else None

    def list_connections(self, org_id: str, assessment_id: Optional[str] = None) -> list[FormConnection]:
        sql = "SELECT * FROM form_connections WHERE org_id = ?"
        params: list = [org_id]
        if assessment_id:
            sql += " AND assessment_id = ?"
            params.append(assessment_id)
        sql += " ORDER BY created_at ASC"
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
            return [self._row_to_connection(db, row) for row in rows]

    def revoke_connection(self, connection_id: str, *, org_id: str) -> bool:
        with self._connect() as db:
            cur = db.execute(
                "UPDATE form_connections SET status = ?, credential_json = NULL, credential_scheme = NULL, updated_at = ? "
                "WHERE id = ? AND org_id = ?",
                (ConnectionStatus.REVOKED.value, _now_iso(), connection_id, org_id),
            )
            db.commit()
            return cur.rowcount > 0

    def _row_to_connection(self, db: sqlite3.Connection, row: sqlite3.Row) -> FormConnection:
        from .models import FormQuestion

        try:
            questions = [FormQuestion(**q) for q in json.loads(row["schema_json"] or "[]")]
        except (ValueError, TypeError):
            questions = []
        counts = db.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN batch_id IS NULL THEN 1 ELSE 0 END) AS pending, "
            "MAX(submitted_at) AS latest FROM form_responses WHERE connection_id = ?",
            (row["id"],),
        ).fetchone()
        batches = db.execute(
            "SELECT COUNT(*) AS n FROM form_batches WHERE connection_id = ?", (row["id"],)
        ).fetchone()
        return FormConnection(
            id=row["id"],
            org_id=row["org_id"],
            assessment_id=row["assessment_id"],
            kind=row["kind"],
            form_id=row["form_id"] or "",
            sheet_id=row["sheet_id"] or "",
            sheet_range=row["sheet_range"] or "",
            title=row["title"] or "",
            purpose=row["purpose"] or "evidence",
            status=row["status"] or ConnectionStatus.PENDING_AUTH.value,
            owner_user_id=row["owner_user_id"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_synced_at=row["last_synced_at"] or "",
            last_error=row["last_error"] or "",
            total_responses=int(counts["total"] or 0),
            pending_responses=int(counts["pending"] or 0),
            batch_count=int(batches["n"] or 0),
            schema_hash=row["schema_hash"] or "",
            questions=questions,
            evidence_class=row["evidence_class"] or "form",
            note=row["note"] or "",
        )

    # ── Responses ──────────────────────────────────────────────────────────

    def known_response_ids(self, connection_id: str) -> set[str]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT response_id FROM form_responses WHERE connection_id = ?", (connection_id,)
            ).fetchall()
        return {str(r["response_id"]) for r in rows}

    def save_responses(self, connection: FormConnection, responses: list[CollectedResponse]) -> int:
        """Insert new responses; duplicates are ignored (at-least-once delivery)."""
        inserted = 0
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                for r in responses:
                    cur = db.execute(
                        """
                        INSERT OR IGNORE INTO form_responses (
                            connection_id, org_id, assessment_id, response_id, submitted_at,
                            respondent_type, respondent_ref, completeness_pct, consistency,
                            verification_status, trust_score, answers_json, collected_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            connection.id,
                            connection.org_id,
                            connection.assessment_id,
                            r.response_id,
                            r.submitted_at,
                            r.respondent_type,
                            r.respondent_ref,
                            r.completeness_pct,
                            r.consistency,
                            r.verification_status,
                            r.trust_score,
                            json.dumps([a.model_dump() for a in r.answers], default=str),
                            _now_iso(),
                        ),
                    )
                    inserted += cur.rowcount or 0
                db.commit()
            except Exception:
                db.rollback()
                raise
        return inserted

    def pending_responses(self, connection_id: str) -> list[CollectedResponse]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM form_responses WHERE connection_id = ? AND batch_id IS NULL ORDER BY submitted_at ASC",
                (connection_id,),
            ).fetchall()
        return [self._row_to_response(r) for r in rows]

    def all_responses(self, connection_id: str) -> list[CollectedResponse]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM form_responses WHERE connection_id = ? ORDER BY submitted_at ASC",
                (connection_id,),
            ).fetchall()
        return [self._row_to_response(r) for r in rows]

    @staticmethod
    def _row_to_response(row: sqlite3.Row) -> CollectedResponse:
        try:
            answers = [CollectedAnswer(**a) for a in json.loads(row["answers_json"] or "[]")]
        except (ValueError, TypeError):
            answers = []
        return CollectedResponse(
            response_id=row["response_id"],
            submitted_at=row["submitted_at"] or "",
            answers=answers,
            respondent_type=row["respondent_type"] or "Unidentified respondent",
            respondent_ref=row["respondent_ref"] or "",
            completeness_pct=float(row["completeness_pct"] or 0.0),
            consistency=row["consistency"] or "NOT MEASURED",
            verification_status=row["verification_status"] or "SELF_REPORTED",
            trust_score=float(row["trust_score"] or 0.0),
        )

    def mark_batched(self, connection_id: str, response_ids: list[str], batch_id: str) -> int:
        if not response_ids:
            return 0
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                placeholders = ",".join("?" * len(response_ids))
                cur = db.execute(
                    f"UPDATE form_responses SET batch_id = ? WHERE connection_id = ? AND batch_id IS NULL "
                    f"AND response_id IN ({placeholders})",
                    [batch_id, connection_id, *response_ids],
                )
                db.commit()
                return cur.rowcount
            except Exception:
                db.rollback()
                raise

    # ── Batches ────────────────────────────────────────────────────────────

    def record_batch(self, batch: CollectionBatch) -> CollectionBatch:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO form_batches (
                    id, connection_id, org_id, assessment_id, document_id, run_id, filename,
                    response_count, window_start, window_end, trust_score, evidence_status,
                    digest_text, response_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    document_id=excluded.document_id, run_id=excluded.run_id,
                    trust_score=excluded.trust_score, evidence_status=excluded.evidence_status,
                    digest_text=excluded.digest_text
                """,
                (
                    batch.id,
                    batch.connection_id,
                    batch.org_id,
                    batch.assessment_id,
                    batch.document_id,
                    batch.run_id,
                    batch.filename,
                    batch.response_count,
                    batch.window_start,
                    batch.window_end,
                    batch.trust_score,
                    batch.evidence_status,
                    batch.digest,
                    json.dumps(batch.response_ids, default=str),
                    batch.created_at.isoformat(),
                ),
            )
            db.commit()
        return batch

    def list_batches(self, org_id: str, assessment_id: Optional[str] = None, connection_id: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM form_batches WHERE org_id = ?"
        params: list = [org_id]
        if assessment_id:
            sql += " AND assessment_id = ?"
            params.append(assessment_id)
        if connection_id:
            sql += " AND connection_id = ?"
            params.append(connection_id)
        sql += " ORDER BY created_at DESC"
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [
            {
                "id": r["id"],
                "connectionId": r["connection_id"],
                "documentId": r["document_id"] or "",
                "runId": r["run_id"] or "",
                "filename": r["filename"] or "",
                "responseCount": int(r["response_count"] or 0),
                "windowStart": r["window_start"] or "",
                "windowEnd": r["window_end"] or "",
                "trustScore": float(r["trust_score"]) if r["trust_score"] is not None else None,
                "evidenceStatus": r["evidence_status"] or "",
                "createdAt": r["created_at"],
            }
            for r in rows
        ]

    def batch_document_ids(self, org_id: str, assessment_id: str) -> set[str]:
        """Documents that came from a collection channel (primary-doc counting)."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT document_id FROM form_batches WHERE org_id = ? AND assessment_id = ? AND document_id IS NOT NULL",
                (org_id, assessment_id),
            ).fetchall()
        return {str(r["document_id"]) for r in rows if r["document_id"]}

    def same_connection_batch_count(self, connection_id: str) -> int:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS n FROM form_batches WHERE connection_id = ?", (connection_id,)
            ).fetchone()
        return int(row["n"] or 0)

    def latest_digest_text(self, connection_id: str) -> str:
        with self._connect() as db:
            row = db.execute(
                "SELECT digest_text FROM form_batches WHERE connection_id = ? ORDER BY created_at DESC LIMIT 1",
                (connection_id,),
            ).fetchone()
        return (row["digest_text"] or "") if row else ""


_repo: FormsRepository | None = None


def get_repo(db_path: str | None = None) -> FormsRepository:
    """Lazy singleton, matching ``kulima.core.orgs.platform_admins.get_repo``."""
    global _repo
    if _repo is None:
        _repo = FormsRepository(db_path)
    return _repo
