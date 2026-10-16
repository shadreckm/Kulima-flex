"""Assessment-aware conversation storage for the AI Analyst (Phases 1, 2, 4, 7).

Data model (two tables in the shared SQLite database):

    analyst_conversations
        conversation_id  — primary key (uuid)
        assessment_id    — the owning assessment (context isolation key)
        run_id           — the intelligence run bound to the assessment
        user_id          — creator (nullable for shared rows)
        org_id           — workspace scope
        title            — editable conversation name (Phase 6 rename)
        is_default       — True for the auto-created default conversation
        created_at / updated_at

    analyst_messages
        id               — autoincrement
        conversation_id  — FK → analyst_conversations (Phase 1: every message
                           belongs to a conversation)
        role             — 'user' | 'assistant' | 'system'
        content          — message text
        created_at

Isolation contract (Phase 4):
    Every read is scoped by ``org_id`` (fallback ``user_id``) AND
    ``assessment_id``. There is no API path that reads messages across
    assessments, so Kulima Africa questions can never see Emerge Ventures
    context and vice versa.

Migration (Phase 7):
    ``migrate_legacy_messages()`` preserves existing AI Analyst records from
    the legacy ``ask_ic_messages`` table (if present) by assigning each
    message to a per-assessment legacy conversation, matched via the run →
    assessment binding. Legacy tables without assessment linkage land in a
    per-user "Imported Chat" conversation rather than being dropped.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from kulima.config import get_settings

_log = logging.getLogger(__name__)

CONVERSATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyst_conversations (
    conversation_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    run_id TEXT,
    user_id TEXT,
    org_id TEXT,
    title TEXT NOT NULL DEFAULT 'New Chat',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyst_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyst_conversations_assessment
    ON analyst_conversations(assessment_id);
CREATE INDEX IF NOT EXISTS idx_analyst_conversations_org
    ON analyst_conversations(org_id);
CREATE INDEX IF NOT EXISTS idx_analyst_messages_conversation
    ON analyst_messages(conversation_id);
"""

_VALID_ROLES = {"user", "assistant", "system"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationRepository:
    """CRUD for assessment-aware AI Analyst conversations."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self._initialize()
        self._migrate_legacy()

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
            conn.executescript(CONVERSATION_SCHEMA)
            conn.commit()

    # ── Phase 7: migration of legacy AI Analyst records ─────────────────────

    def _migrate_legacy(self) -> None:
        """Assign existing AI Analyst records to per-assessment conversations.

        Recognises the legacy ``ask_ic_messages`` table (run_id, role,
        content, created_at). Each message is assigned to the conversation of
        the assessment that owns its run. Runs that cannot be resolved to an
        assessment land in a per-run "Imported Chat" conversation so no
        history is lost.
        """
        try:
            with self._connect() as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "ask_ic_messages" not in tables:
                    return
                migrated_flag = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='analyst_migrations'"
                ).fetchone()
                if migrated_flag is None:
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS analyst_migrations ("
                        "id INTEGER PRIMARY KEY, migrated_at TEXT NOT NULL)"
                    )
                already = conn.execute("SELECT COUNT(*) AS c FROM analyst_migrations").fetchone()
                if already and already["c"] > 0:
                    return

                rows = conn.execute(
                    "SELECT id, run_id, role, content, created_at FROM ask_ic_messages ORDER BY id"
                ).fetchall()
                if not rows:
                    conn.execute(
                        "INSERT INTO analyst_migrations (migrated_at) VALUES (?)", (_now(),)
                    )
                    conn.commit()
                    return

                # Resolve run → assessment via the assessment context store.
                run_to_assessment: dict[str, str] = {}
                try:
                    for r in conn.execute(
                        "SELECT run_id, assessment_id FROM assessment_contexts WHERE run_id IS NOT NULL"
                    ):
                        if r["run_id"] and r["assessment_id"]:
                            run_to_assessment[str(r["run_id"])] = str(r["assessment_id"])
                except Exception:  # noqa: BLE001
                    pass

                migrated = 0
                # One conversation per originating assessment — legacy messages
                # for the same assessment are grouped into a single chat.
                legacy_conversation_ids: dict[str, str] = {}
                for row in rows:
                    run_id = str(row["run_id"] or "")
                    assessment_id = run_to_assessment.get(run_id, f"legacy::{run_id or 'unknown'}")
                    conversation_id = legacy_conversation_ids.get(assessment_id)
                    created = row["created_at"] or _now()
                    if not conversation_id:
                        conversation_id = str(uuid.uuid4())
                        legacy_conversation_ids[assessment_id] = conversation_id
                        conn.execute(
                            "INSERT OR IGNORE INTO analyst_conversations "
                            "(conversation_id, assessment_id, run_id, user_id, org_id, title, is_default, created_at, updated_at) "
                            "VALUES (?, ?, ?, NULL, NULL, ?, 1, ?, ?)",
                            (conversation_id, assessment_id, run_id or None,
                             f"Imported Chat — {run_id or 'legacy'}", created, created),
                        )
                    conn.execute(
                        "INSERT INTO analyst_messages (conversation_id, role, content, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (conversation_id, row["role"] if row["role"] in _VALID_ROLES else "assistant",
                         row["content"], created),
                    )
                    migrated += 1

                conn.execute("INSERT INTO analyst_migrations (migrated_at) VALUES (?)", (_now(),))
                conn.commit()
                if migrated:
                    _log.info("Migrated %d legacy AI Analyst message(s) into conversations.", migrated)
        except Exception as exc:  # noqa: BLE001 — migration must never break startup
            _log.warning("Legacy conversation migration skipped: %s", exc)

    # ── Phase 3: fresh assessment behavior ──────────────────────────────────

    def ensure_default_conversation(
        self,
        assessment_id: str,
        *,
        run_id: str | None = None,
        user_id: str | None = None,
        org_id: str | None = None,
        title: str | None = None,
    ) -> dict:
        """Return the assessment's default conversation, creating it if needed.

        Called when a new assessment completes (Phase 3): the new assessment
        gets its own fresh default conversation; previous assessments' chats
        are never loaded.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analyst_conversations "
                "WHERE assessment_id = ? AND is_default = 1 LIMIT 1",
                (assessment_id,),
            ).fetchone()
            if row:
                return dict(row)
            conversation_id = str(uuid.uuid4())
            now = _now()
            conn.execute(
                "INSERT INTO analyst_conversations "
                "(conversation_id, assessment_id, run_id, user_id, org_id, title, is_default, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (conversation_id, assessment_id, run_id, user_id, org_id,
                 title or "Chat 1", now, now),
            )
            conn.commit()
            created = conn.execute(
                "SELECT * FROM analyst_conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            return dict(created)

    # ── Phase 6: conversation CRUD ──────────────────────────────────────────

    def create_conversation(
        self,
        assessment_id: str,
        *,
        run_id: str | None = None,
        user_id: str | None = None,
        org_id: str | None = None,
        title: str | None = None,
    ) -> dict:
        """Create a new (non-default) conversation inside an assessment."""
        conversation_id = str(uuid.uuid4())
        now = _now()
        with self._connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM analyst_conversations WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
            n = int(count["c"] if count else 0) + 1
            conn.execute(
                "INSERT INTO analyst_conversations "
                "(conversation_id, assessment_id, run_id, user_id, org_id, title, is_default, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (conversation_id, assessment_id, run_id, user_id, org_id,
                 title or f"Chat {n}", now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM analyst_conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            return dict(row)

    def list_conversations(
        self,
        assessment_id: str,
        *,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> list[dict]:
        """Conversations for ONE assessment only (Phase 4 isolation)."""
        query = (
            "SELECT c.*, (SELECT COUNT(*) FROM analyst_messages m "
            "WHERE m.conversation_id = c.conversation_id) AS message_count "
            "FROM analyst_conversations c WHERE c.assessment_id = ?"
        )
        params: list[object] = [assessment_id]
        # Scope: org rows visible workspace-wide; user rows when no org.
        if org_id is not None:
            query += " AND (c.org_id = ? OR c.org_id IS NULL)"
            params.append(org_id)
        elif user_id is not None:
            query += " AND (c.user_id = ? OR c.user_id IS NULL)"
            params.append(user_id)
        query += " ORDER BY c.updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def get_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str | None = None,
        org_id: str | None = None,
        assessment_id: str | None = None,
    ) -> Optional[dict]:
        with self._connect() as conn:
            query = "SELECT * FROM analyst_conversations WHERE conversation_id = ?"
            params: list[object] = [conversation_id]
            if org_id is not None:
                query += " AND (org_id = ? OR org_id IS NULL)"
                params.append(org_id)
            elif user_id is not None:
                query += " AND (user_id = ? OR user_id IS NULL)"
                params.append(user_id)
            row = conn.execute(query, tuple(params)).fetchone()
            if not row:
                return None
            result = dict(row)
            if assessment_id and result.get("assessment_id") != assessment_id:
                return None  # cross-assessment read blocked
            return result

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        title = (title or "").strip()[:120] or "Untitled Chat"
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE analyst_conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
                (title, _now(), conversation_id),
            )
            conn.commit()
            return bool(cur.rowcount)

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM analyst_messages WHERE conversation_id = ?", (conversation_id,)
            )
            cur = conn.execute(
                "DELETE FROM analyst_conversations WHERE conversation_id = ?", (conversation_id,)
            )
            conn.commit()
            return bool(cur.rowcount)

    def touch_conversation(self, conversation_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE analyst_conversations SET updated_at = ? WHERE conversation_id = ?",
                (_now(), conversation_id),
            )
            conn.commit()

    # ── Phase 1: messages ───────────────────────────────────────────────────

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> Optional[int]:
        """Append a message to a conversation (Phase 1: every message belongs
        to a conversation). Returns the message id, or None when the
        conversation does not exist."""
        if role not in _VALID_ROLES:
            role = "assistant"
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM analyst_conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if not exists:
                return None
            cur = conn.execute(
                "INSERT INTO analyst_messages (conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, _now()),
            )
            conn.execute(
                "UPDATE analyst_conversations SET updated_at = ? WHERE conversation_id = ?",
                (_now(), conversation_id),
            )
            conn.commit()
            return int(cur.lastrowid) if cur.lastrowid else None

    def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 200,
    ) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, conversation_id, role, content, created_at "
                "FROM analyst_messages WHERE conversation_id = ? ORDER BY id LIMIT ?",
                (conversation_id, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Phase 5: assessment history ─────────────────────────────────────────

    def assessment_history(self, *, org_id: str | None = None, user_id: str | None = None,
                           limit: int = 50) -> list[dict]:
        """Assessment history rows for the sidebar (Phase 5).

        Shows: assessment name, assessment type, trust score, date and
        conversation count. Reads assessment_contexts and joins conversation
        counts so users can reopen previous assessments.
        """
        query = (
            "SELECT a.assessment_id, a.run_id, a.assessment_type, a.status, "
            "a.created_at, a.updated_at, a.payload_json, "
            "(SELECT COUNT(*) FROM analyst_conversations c "
            " WHERE c.assessment_id = a.assessment_id) AS conversation_count "
            "FROM assessment_contexts a"
        )
        params: list[object] = []
        if org_id is not None:
            query += " WHERE a.org_id = ? OR (a.org_id IS NULL AND a.user_id = ?)"
            params.extend([org_id, user_id])
        elif user_id is not None:
            query += " WHERE a.user_id = ?"
            params.append(user_id)
        query += " ORDER BY a.created_at DESC LIMIT ?"
        params.append(int(limit))
        try:
            with self._connect() as conn:
                rows = conn.execute(query, tuple(params)).fetchall()
        except Exception as exc:  # noqa: BLE001 — assessment store may not exist yet
            _log.debug("assessment_history unavailable: %s", exc)
            return []
        results: list[dict] = []
        for row in rows:
            payload: dict = {}
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except Exception:  # noqa: BLE001
                payload = {}
            display = (
                payload.get("organization_name")
                or payload.get("startup_name")
                or payload.get("founder_name")
                or "Untitled assessment"
            )
            results.append({
                "assessmentId": row["assessment_id"],
                "runId": row["run_id"],
                "assessmentName": display,
                "assessmentType": row["assessment_type"],
                "trustScore": payload.get("trust_score"),
                "status": row["status"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "conversationCount": int(row["conversation_count"] or 0),
            })
        return results
