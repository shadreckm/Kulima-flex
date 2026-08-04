from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from kulima.config import get_settings


RUN_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    db_id INTEGER,
    error_message TEXT,
    user_id TEXT
);
"""


class RunRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(RUN_SCHEMA)
            # Ensure user_id column exists for older databases
            try:
                cols = {row[1] for row in conn.execute("PRAGMA table_info(api_runs)")}
                if "user_id" not in cols:
                    conn.execute("ALTER TABLE api_runs ADD COLUMN user_id TEXT")
            except Exception:
                pass
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_run(self, run_id: str, status: str = "running", user_id: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO api_runs (run_id, status, created_at, user_id) VALUES (?, ?, ?, ?)",
                (run_id, status, now, user_id),
            )
            conn.commit()

    def update_run_completed(self, run_id: str, db_id: int | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE api_runs SET status = ?, completed_at = ?, db_id = ?, error_message = NULL WHERE run_id = ?",
                ("completed", now, db_id, run_id),
            )
            conn.commit()

    def update_run_failed(self, run_id: str, error_message: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE api_runs SET status = ?, completed_at = ?, error_message = ? WHERE run_id = ?",
                ("failed", now, error_message, run_id),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM api_runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    def list_runs(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM api_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
