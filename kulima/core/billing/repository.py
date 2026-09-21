"""SQLite persistence for subscriptions and payment history (Phase 7–8)."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from kulima.config import get_settings

_log = logging.getLogger(__name__)

STATUS_ACTIVE = "active"
STATUS_PAST_DUE = "past_due"
STATUS_GRACE = "grace"
STATUS_SUSPENDED = "suspended"
STATUS_CANCELED = "canceled"

BILLING_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    org_id TEXT PRIMARY KEY,
    plan TEXT NOT NULL DEFAULT 'free',
    status TEXT NOT NULL DEFAULT 'active',
    currency TEXT NOT NULL DEFAULT 'USD',
    amount REAL,
    billing_cycle TEXT NOT NULL DEFAULT 'monthly',
    current_period_start TEXT,
    current_period_end TEXT,
    grace_until TEXT,
    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
    pending_plan TEXT,
    paychangu_ref TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL,
    tx_ref TEXT,
    event_type TEXT NOT NULL,
    plan TEXT,
    amount REAL,
    currency TEXT,
    status TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payment_events_org
    ON payment_events(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_events_tx
    ON payment_events(tx_ref);
"""

_PATCHABLE = (
    "plan",
    "status",
    "currency",
    "amount",
    "billing_cycle",
    "current_period_start",
    "current_period_end",
    "grace_until",
    "cancel_at_period_end",
    "pending_plan",
    "paychangu_ref",
    "last_error",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BillingRepository:
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
            conn.executescript(BILLING_SCHEMA)
            conn.commit()

    # ── Subscriptions ────────────────────────────────────────────────────

    def ensure_subscription(self, org_id: str, plan: str = "free") -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM subscriptions WHERE org_id = ?", (org_id,)).fetchone()
            if row is None:
                now = _now()
                conn.execute(
                    """
                    INSERT INTO subscriptions (org_id, plan, status, currency, created_at, updated_at)
                    VALUES (?, ?, 'active', ?, ?, ?)
                    """,
                    (org_id, plan, "USD", now, now),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM subscriptions WHERE org_id = ?", (org_id,)).fetchone()
        return dict(row) if row else {"org_id": org_id, "plan": plan, "status": "active"}

    def get_subscription(self, org_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM subscriptions WHERE org_id = ?", (org_id,)).fetchone()
        return dict(row) if row else None

    def update_subscription(self, org_id: str, **fields) -> dict:
        patch = {k: v for k, v in fields.items() if k in _PATCHABLE}
        # Upsert semantics: guarantee the row exists before patching. Without
        # this, a first-contact transition (suspend / grace / reactivate on an
        # org with no subscription row yet) would silently UPDATE zero rows and
        # the trailing ensure_subscription() would create a fresh active row —
        # losing the state transition.
        self.ensure_subscription(org_id)
        if not patch:
            return self.ensure_subscription(org_id)
        patch["updated_at"] = _now()
        assignments = ", ".join(f"{k} = ?" for k in patch)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE subscriptions SET {assignments} WHERE org_id = ?",
                (*patch.values(), org_id),
            )
            conn.commit()
        return self.ensure_subscription(org_id)

    # ── Payment events (billing history) ─────────────────────────────────

    def record_payment_event(
        self,
        org_id: str,
        event_type: str,
        *,
        tx_ref: str | None = None,
        plan: str | None = None,
        amount: float | None = None,
        currency: str | None = None,
        status: str | None = None,
        payload: dict | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO payment_events (org_id, tx_ref, event_type, plan, amount, currency, status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    org_id,
                    tx_ref,
                    event_type,
                    plan,
                    amount,
                    currency,
                    status,
                    json.dumps(payload or {}, default=str),
                    _now(),
                ),
            )
            conn.commit()
            return int(cur.lastrowid or 0)

    def list_payment_events(self, org_id: str, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM payment_events WHERE org_id = ? ORDER BY id DESC LIMIT ?",
                (org_id, max(1, int(limit))),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def find_event_by_tx_ref(self, tx_ref: str, event_type: str | None = None) -> dict | None:
        query = "SELECT * FROM payment_events WHERE tx_ref = ?"
        params: list[object] = [tx_ref]
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY id DESC LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        return self._row_to_event(row) if row else None

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> dict:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:  # noqa: BLE001
            payload = {}
        return {
            "id": row["id"],
            "orgId": row["org_id"],
            "txRef": row["tx_ref"],
            "eventType": row["event_type"],
            "plan": row["plan"],
            "amount": row["amount"],
            "currency": row["currency"],
            "status": row["status"],
            "payload": payload,
            "createdAt": row["created_at"],
        }
