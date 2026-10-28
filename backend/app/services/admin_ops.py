"""Read-only platform aggregates for the internal Admin Console.

Everything here is a *query* over tables the platform already writes during
normal operation — no new stores, no new columns, no writes. Where a metric
has no underlying data it returns ``None`` (rendered as NO DATA) instead of
zero, so an empty pilot is never misread as a measured failure.

Cross-workspace by design: this is the operator view, so the workspace
filters that protect customer data (``org_id`` scoping) are deliberately not
applied. Access to these functions is gated by
``backend.app.core.admin_access.require_platform_admin``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from kulima.config import get_settings

_log = logging.getLogger(__name__)

_PAID_STATUSES = {"active", "grace", "past_due"}
_FAILED_EVENT_TYPES = ("payment_failed", "payment_cancelled")
_UPGRADE_EVENT_TYPES = (
    "plan_changed",
    "payment_success",
    "downgrade_scheduled",
    "enterprise_activation_requested",
    "enterprise_agreement_approved",
    "checkout_initiated",
)
_OUTCOME_SETTLED = {"Completed", "Successful", "Partially Successful", "Unsuccessful"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _since(days: int) -> str:
    return _iso(_now() - timedelta(days=max(1, int(days))))


def _parse_dt(value: object) -> datetime | None:
    """Parse a stored ISO timestamp into an aware datetime; None when unusable.

    Older rows carry no offset, so a naive value is read as UTC rather than
    compared against the aware clock (which would raise).
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _rate(numerator: int, denominator: int) -> float | None:
    """Percentage, or None when there is nothing to divide by (NO DATA)."""
    if not denominator:
        return None
    return round(numerator / denominator * 100.0, 1)


def _round_or_none(value: float | None, digits: int = 1) -> float | None:
    """Round a nullable number (ms, ratings, percentages) — None stays None."""
    return None if value is None else round(value, digits)


def _money(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_settings().db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class Reader:
    """Defensive query helper: absent tables degrade to empty, never to 500."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.notes: list[str] = []
        self._tables: set[str] | None = None
        self._cols: dict[str, set[str]] = {}

    def tables(self) -> set[str]:
        if self._tables is None:
            self._tables = {
                r["name"]
                for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        return self._tables

    def has(self, table: str) -> bool:
        return table in self.tables()

    def col(self, table: str, column: str) -> bool:
        if table not in self._cols:
            if not self.has(table):
                return False
            self._cols[table] = {
                r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")
            }
        return column in self._cols[table]

    def rows(self, sql: str, params: tuple | dict = (), *, requires: tuple[str, ...] = ()) -> list[dict]:
        for table in requires:
            if not self.has(table):
                self.notes.append(f"table '{table}' does not exist yet — section reported empty")
                return []
        try:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]
        except sqlite3.Error as exc:  # noqa: BLE001
            _log.warning("admin_ops query failed: %s", exc)
            self.notes.append(f"query failed: {str(exc)[:160]}")
            return []

    def one(self, sql: str, params: tuple | dict = (), *, requires: tuple[str, ...] = ()) -> dict | None:
        rows = self.rows(sql, params, requires=requires)
        return rows[0] if rows else None

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        if not self.has(table):
            self.notes.append(f"table '{table}' does not exist yet — counted as 0")
            return 0
        sql = f"SELECT COUNT(*) AS c FROM {table}"
        if where:
            sql += f" WHERE {where}"
        try:
            row = self.conn.execute(sql, params).fetchone()
        except sqlite3.Error as exc:  # noqa: BLE001
            self.notes.append(f"count({table}) failed: {str(exc)[:160]}")
            return 0
        return int(row["c"]) if row else 0

    def value(self, table: str, sql: str, params: tuple = ()) -> float | None:
        """Single numeric value (SUM/AVG) or None when unavailable."""
        if not self.has(table):
            return None
        try:
            row = self.conn.execute(sql, params).fetchone()
        except sqlite3.Error:  # noqa: BLE001
            return None
        if not row:
            return None
        raw = row[0]
        return None if raw is None else float(raw)

    def org_names(self, fk: str) -> tuple[str, str]:
        """(select fragment, join fragment) for an organization display name.

        ``organizations`` can be absent in a database that has never served an
        authenticated request; without this the join would fail and take the
        whole billing/audit section down with it. Falling back to NULL leaves
        the rows themselves intact — an operator sees unnamed workspaces rather
        than an empty screen.
        """
        if not self.has("organizations"):
            note = ("table 'organizations' does not exist yet — workspaces are listed without names")
            if note not in self.notes:
                self.notes.append(note)
            return "NULL AS orgName", ""
        return "o.name AS orgName", f"LEFT JOIN organizations o ON o.id = {fk}"


# ── Phase 1 — Overview ───────────────────────────────────────────────────────

def overview(window_days: int = 30) -> dict:
    since = _since(window_days)
    with _connect() as conn:
        r = Reader(conn)
        org_row = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN personal = 0 THEN 1 ELSE 0 END) AS teams,
                   SUM(CASE WHEN personal = 1 THEN 1 ELSE 0 END) AS personal_workspaces,
                   SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS created_in_window
            FROM organizations
            """,
            (since,),
            requires=("organizations",),
        ) or {}
        plan_rows = r.rows(
            "SELECT plan, COUNT(*) AS c FROM organizations GROUP BY plan ORDER BY c DESC",
            requires=("organizations",),
        )
        user_row = r.one(
            """
            SELECT COUNT(DISTINCT user_id) AS total,
                   COUNT(DISTINCT CASE WHEN created_at >= ? THEN user_id END) AS joined_in_window
            FROM organization_members
            """,
            (since,),
            requires=("organization_members",),
        ) or {}
        active_row = r.one(
            """
            SELECT COUNT(DISTINCT user_id) AS active, MAX(created_at) AS last_event_at,
                   COUNT(*) AS events_in_window
            FROM audit_events WHERE created_at >= ? AND user_id IS NOT NULL
            """,
            (since,),
            requires=("audit_events",),
        ) or {}
        assess_status = r.rows(
            "SELECT status, COUNT(*) AS c FROM assessment_contexts GROUP BY status ORDER BY c DESC",
            requires=("assessment_contexts",),
        )
        report_rows = r.rows(
            """
            SELECT json_extract(metadata_json, '$.reportKind') AS kind, COUNT(*) AS c
            FROM audit_events WHERE event_type = 'report.exported'
            GROUP BY kind ORDER BY c DESC
            """,
            requires=("audit_events",),
        )
        reports_total = r.count("audit_events", "event_type = 'report.exported'")
        reports_window = r.count("audit_events", "event_type = 'report.exported' AND created_at >= ?", (since,))
        followup_row = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN followup_status = 'answered' THEN 1 ELSE 0 END) AS answered,
                   SUM(CASE WHEN followup_status != 'answered' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN followup_status != 'answered' AND followup_due_at <= ? THEN 1 ELSE 0 END) AS due_now
            FROM decision_records
            """,
            (_iso(_now()),),
            requires=("decision_records",),
        ) or {}
        conv_row = r.one(
            """
            SELECT (SELECT COUNT(*) FROM analyst_conversations) AS conversations,
                   (SELECT COUNT(*) FROM analyst_messages) AS messages,
                   (SELECT COUNT(*) FROM analyst_messages WHERE role = 'user' AND created_at >= ?) AS questions_in_window
            """,
            (since,),
            requires=("analyst_conversations", "analyst_messages"),
        ) or {}
        doc_row = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END) AS active,
                   COALESCE(SUM(CASE WHEN deleted_at IS NULL THEN size_bytes ELSE 0 END), 0) AS storage_bytes
            FROM documents
            """,
            requires=("documents",),
        ) or {}

        assessments_total = r.count("assessment_contexts")
        assessments_window = r.count("assessment_contexts", "created_at >= ?", (since,))
        runs_total = r.count(
            "intelligence_runs",
            "archived_at IS NULL" if r.col("intelligence_runs", "archived_at") else "1=1",
        )
        failed_runs = r.count("api_runs", "status = 'failed'")

        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "organizations": {
                "total": int(org_row.get("total") or 0),
                "teamWorkspaces": int(org_row.get("teams") or 0),
                "personalWorkspaces": int(org_row.get("personal_workspaces") or 0),
                "createdInWindow": int(org_row.get("created_in_window") or 0),
                "byPlan": {(p["plan"] or "unknown"): int(p["c"]) for p in plan_rows},
            },
            "users": {
                "total": int(user_row.get("total") or 0),
                "joinedInWindow": int(user_row.get("joined_in_window") or 0),
                "activeInWindow": int(active_row.get("active") or 0),
                "activityDefinition": (
                    f"Distinct users with at least one audit event in the last {window_days} days "
                    "(logins, uploads, assessments, exports, decisions)."
                ),
            },
            "assessments": {
                "total": assessments_total,
                "createdInWindow": assessments_window,
                "byStatus": {(s["status"] or "unknown"): int(s["c"]) for s in assess_status},
                "completedBriefs": runs_total,
            },
            "documents": {
                "total": int(doc_row.get("total") or 0),
                "active": int(doc_row.get("active") or 0),
                "storageBytes": int(doc_row.get("storage_bytes") or 0),
            },
            "reports": {
                "exportedTotal": reports_total,
                "exportedInWindow": reports_window,
                "byKind": {(k["kind"] or "unknown"): int(k["c"]) for k in report_rows},
            },
            "conversations": {
                "total": int(conv_row.get("conversations") or 0),
                "messages": int(conv_row.get("messages") or 0),
                "questionsInWindow": int(conv_row.get("questions_in_window") or 0),
            },
            "outcomeFollowUps": {
                "total": int(followup_row.get("total") or 0),
                "answered": int(followup_row.get("answered") or 0),
                "pending": int(followup_row.get("pending") or 0),
                "overdueNow": int(followup_row.get("due_now") or 0),
                "completionRate": _rate(int(followup_row.get("answered") or 0), int(followup_row.get("total") or 0)),
            },
            "pipelineHealth": {
                "auditEventsTotal": r.count("audit_events"),
                "auditEventsInWindow": int(active_row.get("events_in_window") or 0),
                "lastEventAt": active_row.get("last_event_at"),
                "failedRuns": failed_runs,
                "topEventTypes": [
                    {"eventType": e["event_type"], "count": int(e["c"])}
                    for e in r.rows(
                        "SELECT event_type, COUNT(*) AS c FROM audit_events WHERE created_at >= ? "
                        "GROUP BY event_type ORDER BY c DESC LIMIT 8",
                        (since,),
                        requires=("audit_events",),
                    )
                ],
            },
            "dataNotes": r.notes,
        }


# ── Phase 2 — User management (users · orgs · plans · roles · activity) ──────

def user_management(search: str = "", limit: int = 100, window_days: int = 30) -> dict:
    since = _since(window_days)
    like = f"%{search.strip()}%" if search.strip() else None
    with _connect() as conn:
        r = Reader(conn)
        sql = """
            SELECT m.user_id AS userId,
                   MAX(m.display_name) AS displayName,
                   MAX(m.email) AS email,
                   COUNT(DISTINCT m.org_id) AS orgCount,
                   MIN(m.created_at) AS joinedAt,
                   GROUP_CONCAT(DISTINCT m.role) AS roles
            FROM organization_members m
        """
        params: list = []
        if like:
            sql += " WHERE LOWER(m.user_id) LIKE LOWER(?) OR LOWER(COALESCE(m.email,'')) LIKE LOWER(?) OR LOWER(COALESCE(m.display_name,'')) LIKE LOWER(?)"
            params.extend([like, like, like])
        sql += " GROUP BY m.user_id ORDER BY joinedAt DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        users = r.rows(sql, tuple(params), requires=("organization_members",))

        activity = {
            a["user_id"]: a
            for a in r.rows(
                """
                SELECT user_id, MAX(created_at) AS lastActivityAt, COUNT(*) AS events
                FROM audit_events WHERE user_id IS NOT NULL GROUP BY user_id
                """,
                requires=("audit_events",),
            )
        }
        assessed = {
            a["user_id"]: int(a["c"])
            for a in r.rows(
                "SELECT user_id, COUNT(*) AS c FROM assessment_contexts GROUP BY user_id",
                requires=("assessment_contexts",),
            )
        }
        for user in users:
            act = activity.get(user["userId"]) or {}
            user["lastActivityAt"] = act.get("lastActivityAt")
            user["auditEvents"] = int(act.get("events") or 0)
            user["assessments"] = assessed.get(user["userId"], 0)
            user["active"] = bool(act.get("lastActivityAt")) and str(act["lastActivityAt"]) >= since
            user["roles"] = sorted({x for x in str(user.get("roles") or "").split(",") if x})

        # Every enrichment is a correlated subquery into a table that may not
        # exist in a freshly-created database, so the SELECT list is composed
        # from the tables actually present. Missing columns are filled with the
        # same defaults below, keeping the payload shape stable.
        enrichments = (
            ("organization_members",
             "(SELECT COUNT(*) FROM organization_members m WHERE m.org_id = o.id) AS members"),
            ("assessment_contexts",
             "(SELECT COUNT(*) FROM assessment_contexts a WHERE a.org_id = o.id) AS assessments"),
            ("documents",
             "(SELECT COUNT(*) FROM documents d WHERE d.org_id = o.id AND d.deleted_at IS NULL) AS documents"),
            ("audit_events",
             "(SELECT MAX(e.created_at) FROM audit_events e WHERE e.org_id = o.id) AS lastActivityAt"),
            ("subscriptions",
             "(SELECT s.status FROM subscriptions s WHERE s.org_id = o.id) AS billingStatus, "
             "(SELECT s.activation_state FROM subscriptions s WHERE s.org_id = o.id) AS activationState"),
        )
        columns = [
            "o.id", "o.name", "o.slug", "o.plan", "o.personal",
            "o.created_by AS createdBy", "o.created_at AS createdAt",
        ]
        columns += [expr for table, expr in enrichments if r.has(table)]
        orgs = r.rows(
            f"SELECT {', '.join(columns)} FROM organizations o ORDER BY o.created_at DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
            requires=("organizations",),
        )
        for org in orgs:
            org.setdefault("members", 0)
            org.setdefault("assessments", 0)
            org.setdefault("documents", 0)
            org.setdefault("lastActivityAt", None)
            org.setdefault("billingStatus", None)
            org.setdefault("activationState", None)
        role_rows = r.rows(
            "SELECT role, COUNT(*) AS c FROM organization_members GROUP BY role ORDER BY c DESC",
            requires=("organization_members",),
        )
        recent = r.rows(
            """
            SELECT id, event_type AS eventType, org_id AS orgId, user_id AS userId,
                   created_at AS createdAt, metadata_json
            FROM audit_events ORDER BY id DESC LIMIT 25
            """,
            requires=("audit_events",),
        )
        for event in recent:
            try:
                event["metadata"] = json.loads(event.pop("metadata_json") or "{}")
            except Exception:  # noqa: BLE001
                event["metadata"] = {}

        plan_counts = r.rows(
            "SELECT plan, COUNT(*) AS c FROM organizations GROUP BY plan ORDER BY c DESC",
            requires=("organizations",),
        )
        # Memberships per plan need the members table; without it the plan is
        # still known, only the seat count is not.
        memberships: dict[str, int] = {}
        if r.has("organization_members"):
            memberships = {
                str(row["plan"] or "unknown"): int(row["m"])
                for row in r.rows(
                    """
                    SELECT o.plan AS plan, COUNT(*) AS m
                    FROM organizations o
                    JOIN organization_members m ON m.org_id = o.id
                    GROUP BY o.plan
                    """
                )
            }
        plan_rows_out = [
            {
                "planId": p["plan"] or "unknown",
                "organizations": int(p["c"]),
                "memberships": memberships.get(str(p["plan"] or "unknown"), 0),
            }
            for p in plan_counts
        ]

        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "search": search or None,
            "users": users,
            "userCount": len(users),
            "organizations": orgs,
            "roles": {(row["role"] or "unknown"): int(row["c"]) for row in role_rows},
            "plans": plan_rows_out,
            "activity": recent,
            "dataNotes": r.notes,
        }


# ── Phase 3 — Billing (PayChangu · plan status · upgrades · failures) ────────

def billing_health(window_days: int = 30) -> dict:
    from kulima.core.billing.paychangu import DEFAULT_BASE_URL, PayChanguConfig
    from kulima.core.billing.plans import all_plans
    from kulima.core.billing.repository import (
        STATUS_ACTIVE, STATUS_CANCELED, STATUS_GRACE, STATUS_PAST_DUE, STATUS_SUSPENDED,
    )
    from kulima.core.billing.service import (
        demo_mode_enabled, enforcement_enabled, grace_period_days, link_autoconfirm_enabled,
    )

    settings = get_settings()
    config = PayChanguConfig(
        secret_key=settings.paychangu_secret_key,
        webhook_secret=settings.paychangu_webhook_secret,
        currency=settings.paychangu_currency,
    )
    since = _since(window_days)
    with _connect() as conn:
        r = Reader(conn)
        name_col, org_join = r.org_names("s.org_id")
        subs = r.rows(
            f"""
            SELECT s.org_id AS orgId, {name_col},
                   {'o.personal AS personal,' if org_join else 'NULL AS personal,'}
                   s.plan, s.status, s.currency, s.amount, s.billing_cycle AS billingCycle,
                   s.current_period_start AS currentPeriodStart,
                   s.current_period_end AS currentPeriodEnd,
                   s.grace_until AS graceUntil,
                   s.cancel_at_period_end AS cancelAtPeriodEnd,
                   s.pending_plan AS pendingPlan, s.paychangu_ref AS paychanguRef,
                   s.activation_state AS activationState, s.last_error AS lastError,
                   s.updated_at AS updatedAt
            FROM subscriptions s
            {org_join}
            ORDER BY s.updated_at DESC LIMIT 300
            """,
            requires=("subscriptions",),
        )
        by_status: dict[str, int] = {}
        by_plan: dict[str, int] = {}
        for sub in subs:
            by_status[sub["status"] or "unknown"] = by_status.get(sub["status"] or "unknown", 0) + 1
            by_plan[sub["plan"] or "unknown"] = by_plan.get(sub["plan"] or "unknown", 0) + 1

        org_count = r.count("organizations")
        subscribed = r.count("subscriptions")
        ledger_name, ledger_join = r.org_names("p.org_id")
        ledger = r.rows(
            f"""
            SELECT p.id, p.org_id AS orgId, {ledger_name}, p.tx_ref AS txRef,
                   p.event_type AS eventType, p.plan, p.amount, p.currency, p.status,
                   p.created_at AS createdAt, p.payload_json AS payloadJson
            FROM payment_events p
            {ledger_join}
            ORDER BY p.id DESC LIMIT 400
            """,
            requires=("payment_events",),
        )
        upgrades = [e for e in ledger if e["eventType"] in _UPGRADE_EVENT_TYPES]
        failures = [
            e for e in ledger
            if e["eventType"] in _FAILED_EVENT_TYPES
            or str(e.get("status") or "").lower() in {"failed", "cancelled", "canceled"}
        ]
        for event in ledger:
            try:
                payload = json.loads(event.pop("payloadJson", None) or "{}")
            except Exception:  # noqa: BLE001
                payload = {}
            event["previousPlan"] = payload.get("previousPlan")
        collected = r.value(
            "payment_events",
            "SELECT SUM(amount) FROM payment_events WHERE event_type IN ('payment_success','payment_received') AND created_at >= ?",
            (since,),
        )
        collected_count = r.count(
            "payment_events", "event_type IN ('payment_success','payment_received') AND created_at >= ?", (since,),
        )
        outstanding = r.value(
            "subscriptions",
            "SELECT SUM(amount) FROM subscriptions "
            "WHERE status IN ('active','grace','past_due') AND plan != 'free'",
        )
        paid_active = [s for s in subs if s["plan"] != "free" and s["status"] in _PAID_STATUSES]
        amount_unknown = sum(1 for s in paid_active if s.get("amount") in (None, 0))

        def _slim(events: list[dict], cap: int) -> list[dict]:
            out = []
            for e in events[:cap]:
                out.append({
                    "id": e["id"], "orgId": e["orgId"], "orgName": e.get("orgName"),
                    "txRef": e.get("txRef"), "eventType": e["eventType"], "plan": e.get("plan"),
                    "amount": e.get("amount"), "currency": e.get("currency"),
                    "status": e.get("status"), "previousPlan": e.get("previousPlan"),
                    "createdAt": e["createdAt"],
                })
            return out

        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "paychangu": {
                "mode": "hosted-payment-links" if not config.secret_key else "api",
                "apiSecretConfigured": bool(config.secret_key),
                "webhookSecretConfigured": bool(config.webhook_secret),
                "currency": config.currency,
                "baseUrl": config.base_url or DEFAULT_BASE_URL,
                "paymentLinks": [
                    {"planId": p.plan_id, "name": p.name, "link": p.payment_link or None,
                     "requiresApproval": p.requires_approval, "priceLabel": p.display_price}
                    for p in all_plans()
                ],
                "enforcementEnabled": enforcement_enabled(),
                "demoMode": demo_mode_enabled(),
                "linkAutoconfirm": link_autoconfirm_enabled(),
                "gracePeriodDays": grace_period_days(),
                "modeNote": (
                    "Hosted links complete on PayChangu's page; activation trusts the return "
                    "redirect when no API secret is configured. The webhook stays authoritative "
                    "when a webhook secret is set."
                ),
            },
            "planStatus": {
                "subscriptions": subscribed,
                "organizations": org_count,
                "withoutSubscriptionRow": max(0, org_count - subscribed),
                "byStatus": by_status,
                "byPlan": by_plan,
                "attention": [
                    {
                        "orgId": s["orgId"], "orgName": s.get("orgName"), "plan": s["plan"],
                        "status": s["status"], "graceUntil": s.get("graceUntil"),
                        "lastError": s.get("lastError"), "pendingPlan": s.get("pendingPlan"),
                        "activationState": s.get("activationState"),
                    }
                    for s in subs
                    if s["status"] in {STATUS_PAST_DUE, STATUS_GRACE, STATUS_SUSPENDED, STATUS_CANCELED}
                    or (s.get("lastError") or "").strip()
                    or s.get("activationState") == "requested"
                ][:40],
                "knownStatuses": [STATUS_ACTIVE, STATUS_GRACE, STATUS_PAST_DUE, STATUS_SUSPENDED, STATUS_CANCELED],
            },
            "revenue": {
                "collectedInWindow": _money(collected),
                "collectedEventCount": collected_count,
                "windowDays": window_days,
                "recurringActivePaid": _money(outstanding),
                "paidActiveSubscriptions": len(paid_active),
                "paidWithoutAmount": amount_unknown,
                "currency": config.currency,
                "note": (
                    "Amounts are what the payment ledger recorded. Hosted-link payments without an "
                    "amount carry NULL — those subscriptions are counted but never monetised here."
                ),
            },
            "upgradeHistory": {"count": len(upgrades), "events": _slim(upgrades, 60)},
            "failedPayments": {"count": len(failures), "events": _slim(failures, 60)},
            "ledger": {"count": len(ledger), "recent": _slim(ledger, 40)},
            "dataNotes": r.notes,
        }


# ── Phase 4 — AI health (providers · usage · failures · fallbacks) ───────────

def ai_health(window_days: int = 30) -> dict:
    from kulima.providers import AIProviderManager

    settings = get_settings()
    since = _since(window_days)
    tiers = [
        ("openai", "OpenAI", settings.openai_api_key, settings.openai_model),
        ("groq", "Groq", settings.groq_api_key, settings.groq_model),
        ("gemini", "Gemini", settings.gemini_api_key, settings.gemini_model),
        ("openrouter", "OpenRouter", settings.openrouter_api_key, settings.openrouter_model),
        ("huggingface", "HuggingFace", settings.huggingface_api_key, settings.huggingface_model),
    ]
    manager = AIProviderManager.instance()
    chain = list(getattr(manager, "chain", []) or [])
    disabled = {str(p).lower() for p in getattr(manager, "_disabled_providers", set())}

    with _connect() as conn:
        r = Reader(conn)
        grouped = r.rows(
            """
            SELECT json_extract(metadata_json, '$.provider_used') AS providerUsed,
                   COUNT(*) AS events,
                   SUM(CASE WHEN json_extract(metadata_json, '$.fallback_triggered') = 1
                            THEN 1 ELSE 0 END) AS fallbacks,
                   SUM(CASE WHEN json_extract(metadata_json, '$.failure_reason') IS NOT NULL
                            THEN 1 ELSE 0 END) AS hardFailures,
                   CAST(AVG(json_extract(metadata_json, '$.response_time_ms')) AS REAL) AS avgMs,
                   MAX(created_at) AS lastUsedAt
            FROM audit_events
            WHERE event_type = 'provider.health' AND created_at >= ?
            GROUP BY providerUsed
            """,
            (since,),
            requires=("audit_events",),
        )
        stats = {
            (g["providerUsed"] or "unknown"): g for g in grouped
        }
        latencies = sorted(
            float(x["ms"]) for x in r.rows(
                """
                SELECT json_extract(metadata_json, '$.response_time_ms') AS ms
                FROM audit_events
                WHERE event_type = 'provider.health' AND created_at >= ?
                  AND json_extract(metadata_json, '$.fallback_triggered') != 1
                """,
                (since,),
                requires=("audit_events",),
            )
            if x["ms"] is not None
        )

        def _percentile(values: list[float], pct: float) -> float | None:
            if not values:
                return None
            idx = min(len(values) - 1, int(round((pct / 100.0) * (len(values) - 1))))
            return round(values[idx], 1)

        health_events = sum(int(g["events"]) for g in stats.values())
        fallback_events = sum(int(g["fallbacks"]) for g in stats.values())
        di_events = int((stats.get("document_intelligence_fallback") or {}).get("events") or 0)
        research_degraded = r.count(
            "audit_events",
            "event_type = 'research.triggered' AND json_extract(metadata_json, '$.provider') = 'document_intelligence'",
        )
        run_status = {
            (s["status"] or "unknown"): int(s["c"])
            for s in r.rows("SELECT status, COUNT(*) AS c FROM api_runs GROUP BY status",
                            requires=("api_runs",))
        }
        failed_runs = r.rows(
            """
            SELECT run_id AS runId, status, error_message AS errorMessage, created_at AS createdAt,
                   completed_at AS completedAt, org_id AS orgId
            FROM api_runs WHERE status = 'failed' ORDER BY created_at DESC LIMIT 15
            """,
            requires=("api_runs",),
        )
        for run in failed_runs:
            run["errorMessage"] = str(run.get("errorMessage") or "")[:220]
        analyst_questions = r.count(
            "analyst_messages", "role = 'user' AND created_at >= ?", (since,),
        )
        assessments_started = r.count(
            "audit_events", "event_type = 'assessment.started' AND created_at >= ?", (since,),
        )
        last = getattr(manager, "last_result", None)

        providers = []
        for key, label, api_key, model in tiers:
            used = stats.get(key) or {}
            providers.append({
                "id": key,
                "label": label,
                "configured": bool(api_key),
                "model": model,
                "inChain": key in chain,
                "disabledNow": key in disabled,
                "assessmentsUsingIt": int(used.get("events") or 0),
                "fallbacksFromIt": int(used.get("fallbacks") or 0),
                "lastUsedAt": used.get("lastUsedAt"),
                "avgResponseMs": _round_or_none(used.get("avgMs")),
            })

        configured_tiers = [t[0] for t in tiers if t[2]]
        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "providers": providers,
            "chain": {
                "activeOrder": chain,
                "configuredByEnv": list(settings.provider_order or ()),
                "configuredTiers": configured_tiers,
                "unconfiguredTiers": [t[0] for t in tiers if not t[2]],
                "disabledInProcess": sorted(disabled),
                "note": (
                    "The active chain is read from the live provider manager in this backend "
                    "process, so it reflects the environment (and any test-mode disables) at "
                    "the time this request is served."
                ),
            },
            "usage": {
                "providerHealthEvents": health_events,
                "assessmentsStartedInWindow": assessments_started,
                "analystQuestionsInWindow": analyst_questions,
                "perProvider": {
                    k: {"events": int(v["events"]), "fallbacks": int(v["fallbacks"])}
                    for k, v in stats.items()
                },
                "emptyReason": None if health_events else (
                    "NO DATA — no provider.health events recorded yet. One is written per "
                    "completed assessment, so this stays empty until a real assessment runs here."
                ),
            },
            "latency": {
                "samples": len(latencies),
                "medianMs": _percentile(latencies, 50),
                "p95Ms": _percentile(latencies, 95),
                "llmTimeoutSeconds": settings.llm_timeout_seconds,
            },
            "failures": {
                "runsByStatus": run_status,
                "failedRuns": int(run_status.get("failed") or 0),
                "runningRuns": int(run_status.get("running") or 0),
                "recentFailedRuns": failed_runs,
                "hardFailureEvents": sum(int(v.get("hardFailures") or 0) for v in stats.values()),
            },
            "fallbacks": {
                "fallbackEvents": fallback_events,
                "fallbackRate": _rate(fallback_events, health_events),
                "documentIntelligenceActivations": di_events,
                "documentIntelligenceRate": _rate(di_events, health_events),
                "researchDegradedToDocuments": research_degraded,
                "definition": (
                    "fallback_triggered = an assessment that did not complete on its first "
                    "provider tier. Document Intelligence Mode = every provider failed and the "
                    "brief was built deterministically from uploaded documents only."
                ),
            },
            "documentIntelligence": {
                "activations": di_events,
                "lastActivationAt": (stats.get("document_intelligence_fallback") or {}).get("lastUsedAt"),
                "modeLabel": "Document Intelligence Mode",
                "explanation": (
                    "The deterministic degradation path: no live model call, output derived from "
                    "this assessment's own documents, trust layer and any research that succeeded."
                ),
            },
            "externalResearch": {
                "provider": "tavily",
                "configured": bool(settings.tavily_api_key),
                "allowedFieldsOnly": True,
                "maxResults": settings.max_research_results,
            },
            "processSnapshot": {
                "lastResult": None if last is None else {
                    "provider": last.provider,
                    "model": last.model,
                    "fallbackTriggered": last.fallback_triggered,
                    "fallbackCount": last.fallback_count,
                    "responseTimeMs": round(last.response_time * 1000, 1),
                    "analysisMode": last.analysis_mode,
                },
                "note": (
                    "Last generation observed by THIS worker process. Multi-instance deployments "
                    "hold one manager per process, so this is a spot check, not a platform total — "
                    "the audit-derived numbers above are authoritative."
                ),
            },
            "dataNotes": r.notes,
        }


# ── Phase 5 — Outcome intelligence ──────────────────────────────────────────

def outcome_intelligence(window_days: int = 30) -> dict:
    from kulima.db import IntelligenceRepository

    now = _now()
    now_iso = _iso(now)
    since = _since(window_days)
    with _connect() as conn:
        r = Reader(conn)
        totals = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN followup_status = 'answered' THEN 1 ELSE 0 END) AS answered,
                   SUM(CASE WHEN followup_status != 'answered' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN followup_status != 'answered' AND followup_due_at <= ? THEN 1 ELSE 0 END) AS due_now,
                   SUM(CASE WHEN followup_status = 'answered' AND answered_at >= ? THEN 1 ELSE 0 END) AS answered_in_window
            FROM decision_records
            """,
            (now_iso, since),
            requires=("decision_records",),
        ) or {}
        taken = {
            (t["decision_taken"] or "unknown"): int(t["c"])
            for t in r.rows(
                "SELECT decision_taken, COUNT(*) AS c FROM decision_records "
                "WHERE followup_status = 'answered' GROUP BY decision_taken",
                requires=("decision_records",),
            )
        }
        followed_rows = r.rows(
            "SELECT recommendation_followed AS f, COUNT(*) AS c FROM decision_records "
            "WHERE followup_status = 'answered' GROUP BY recommendation_followed",
            requires=("decision_records",),
        )
        decidable = sum(int(x["c"]) for x in followed_rows if x["f"] in ("fully", "partially", "no"))
        followed = sum(
            int(x["c"]) for x in followed_rows if x["f"] in ("fully", "partially")
        )
        lag_rows = r.rows(
            """
            SELECT decision_snapshot_at AS snap, answered_at AS ans
            FROM decision_records
            WHERE followup_status = 'answered' AND answered_at IS NOT NULL
              AND decision_snapshot_at IS NOT NULL
            LIMIT 1000
            """,
            requires=("decision_records",),
        )

        def _days(a: str | None, b: str | None) -> float | None:
            start, end = _parse_dt(a), _parse_dt(b)
            if start is None or end is None:
                return None
            return max(0.0, (end - start).total_seconds() / 86400.0)

        lags = sorted(x for x in (_days(row["snap"], row["ans"]) for row in lag_rows) if x is not None)
        avg_lag = round(sum(lags) / len(lags), 1) if lags else None
        median_lag = round(lags[len(lags) // 2], 1) if lags else None

        pending_name, pending_join = r.org_names("d.org_id")
        pending_detail = r.rows(
            f"""
            SELECT d.run_id AS runId, d.entity_name AS entityName, d.recommendation,
                   d.trust_score AS trustScore, d.integrity_grade AS integrityGrade,
                   d.followup_due_at AS followupDueAt, d.created_at AS createdAt,
                   d.org_id AS orgId, {pending_name}
            FROM decision_records d
            {pending_join}
            WHERE d.followup_status != 'answered'
            ORDER BY d.followup_due_at ASC LIMIT 50
            """,
            requires=("decision_records",),
        )
        # Every unanswered follow-up is listed — an operator needs to see the
        # ones that are simply not due yet, not only the overdue ones. Each row
        # carries a signed day offset so "due in 12 days" reads differently from
        # "18 days overdue".
        overdue = 0
        for row in pending_detail:
            due = _parse_dt(row.get("followupDueAt"))
            if due is None:
                row["daysOverdue"] = None
                row["dueState"] = "unknown"
                continue
            offset = (now - due).total_seconds() / 86400.0
            if offset >= 0:
                overdue += 1
                row["daysOverdue"] = int(offset)
                row["dueState"] = "overdue"
            else:
                row["daysOverdue"] = 0
                row["dueState"] = f"due_in_{int(-offset)}_days"

        outcome_status = {
            (s["outcome_status"] or "unknown"): int(s["c"])
            for s in r.rows(
                "SELECT outcome_status, COUNT(*) AS c FROM decision_outcomes GROUP BY outcome_status",
                requires=("decision_outcomes",),
            )
        }
        lessons = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN what_happened IS NOT NULL AND TRIM(what_happened) != '' THEN 1 ELSE 0 END) AS with_what_happened,
                   SUM(CASE WHEN what_worked IS NOT NULL AND TRIM(what_worked) != '' THEN 1 ELSE 0 END) AS with_lessons
            FROM decision_outcomes
            """,
            requires=("decision_outcomes",),
        ) or {}
        feedback = r.one(
            """
            SELECT COUNT(*) AS ratings, AVG(rating) AS avg_rating,
                   SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) AS positive
            FROM run_feedback
            """,
            requires=("run_feedback",),
        ) or {}

        # Decision learning reuses the exact calibration engine the customer-facing
        # outcomes page uses, unscoped (user_id=None) — one definition, two audiences.
        learning_raw = IntelligenceRepository(db_path=get_settings().db_path).compute_outcome_intelligence(
            user_id=None
        )
        learning = {
            key: value
            for key, value in learning_raw.items()
            if key not in {"decisions", "calibration"}
        }
        calibration = dict(learning_raw.get("calibration") or {})
        calibration["bins"] = calibration.pop("calibration_bins", [])
        # Minimum-sample honesty: a band is reportable only with real completions.
        calibration["reportableBands"] = [
            b for b in calibration.get("bins", []) if int(b.get("completed_count") or 0) >= 10
        ]
        calibration["bandNote"] = (
            "Bands with fewer than 10 completed outcomes are shown as observations, never as "
            "calibration — the platform does not treat a handful of outcomes as a rate."
        )

        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "followUpCompletion": {
                "total": int(totals.get("total") or 0),
                "answered": int(totals.get("answered") or 0),
                "pending": int(totals.get("pending") or 0),
                "overdueNow": int(totals.get("due_now") or 0),
                "answeredInWindow": int(totals.get("answered_in_window") or 0),
                "completionRate": _rate(int(totals.get("answered") or 0), int(totals.get("total") or 0)),
                "cadenceDays": 30,
            },
            "decisionTaken": {
                "byAnswer": taken,
                "decidedYes": int(taken.get("yes") or 0),
                "decisionRate": _rate(int(taken.get("yes") or 0), int(totals.get("answered") or 0)),
            },
            "followedRate": {
                "followed": followed,
                "decidable": decidable,
                "rate": _rate(followed, decidable),
                "definition": (
                    "fully + partially ÷ answered records that state follow-through. 'not_yet' and "
                    "'unknown' answers are excluded from the denominator, never counted as failures."
                ),
            },
            "daysToFollowUp": {
                "samples": len(lags),
                "average": avg_lag,
                "median": median_lag,
                "definition": "decision_snapshot_at → answered_at, in days.",
            },
            "pendingOutcomes": {
                "count": len(pending_detail),
                "overdue": overdue,
                "rows": pending_detail,
                "definition": (
                    "Every assessment whose 30-day follow-up is still unanswered, oldest due date "
                    "first. 'overdue' counts the ones already past their due date."
                ),
                "outcomeStatuses": outcome_status,
                "outcomeRowsWithLessons": int(lessons.get("with_lessons") or 0),
                "outcomeRowsTotal": int(lessons.get("total") or 0),
            },
            "decisionLearning": {
                "summary": learning,
                "calibration": calibration,
                "feedback": {
                    "ratings": int(feedback.get("ratings") or 0),
                    "average": _round_or_none(feedback.get("avg_rating"), 2),
                    "positive": int(feedback.get("positive") or 0),
                },
                "settledOutcomes": sum(
                    int(v) for k, v in outcome_status.items() if k in _OUTCOME_SETTLED
                ),
            },
            "dataNotes": r.notes,
        }


# ── Phase 6 — Audit log (creation · deletes · role changes · billing) ────────

_DELETE_EVENTS = (
    "document.deleted", "assessment.deleted", "conversation.deleted",
    "comment.deleted", "case.deleted",
)
_ROLE_EVENTS = (
    "org.role_changed", "org.member_added", "org.member_removed",
    "assessment.collaborator_invited", "assessment.collaborator_removed",
    # Platform-plane role changes are role changes too. An operator granting or
    # revoking PLATFORM_ADMIN must surface in the same bucket the audit panel
    # already exposes, or the most privileged writes on the platform would be
    # the hardest ones to find.
    "admin.platform_admin_granted", "admin.platform_admin_revoked",
    "admin.platform_role_claimed",
)
_CREATION_EVENTS = ("assessment.created", "assessment.started", "document.uploaded")

# The four buckets the console exposes as one server-side filter each. Keeping
# the vocabulary here means the UI never re-declares event types (and can never
# drift into showing a different set than the counts report). Billing is a
# prefix match because every billing event shares the ``billing.`` namespace.
_BUCKETS: dict[str, tuple[str, list]] = {
    "creation": (f"event_type IN ({','.join('?' for _ in _CREATION_EVENTS)})", list(_CREATION_EVENTS)),
    "deletes": (f"event_type IN ({','.join('?' for _ in _DELETE_EVENTS)})", list(_DELETE_EVENTS)),
    "roles": (f"event_type IN ({','.join('?' for _ in _ROLE_EVENTS)})", list(_ROLE_EVENTS)),
    "billing": ("event_type LIKE ?", ["billing.%"]),
}


def audit_logs(
    event_types: list[str] | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
    window_days: int | None = None,
    limit: int = 200,
    bucket: str | None = None,
) -> dict:
    from kulima.core.audit.repository import event_category, event_label

    # Each filter is a (sql, params) pair so bucket counts can re-compose the
    # exact same WHERE clause the event page used.
    base_predicates: list[tuple[str, list]] = []
    if event_types:
        type_clause = f"event_type IN ({','.join('?' for _ in event_types)})"
        base_predicates.append((type_clause, list(event_types)))
    if org_id:
        base_predicates.append(("org_id = ?", [org_id]))
    if user_id:
        base_predicates.append(("user_id = ?", [user_id]))
    if window_days:
        base_predicates.append(("created_at >= ?", [_since(window_days)]))

    # The bucket narrows the event page only. The four bucket counts stay
    # navigable: if they were narrowed too, selecting one bucket would report
    # zero for the other three and the cards would stop being a filter control.
    bucket_key = str(bucket).strip().lower() if bucket else None
    bucket_predicate: tuple[str, list] | None = None
    if bucket_key:
        clause = _BUCKETS.get(bucket_key)
        if clause is None:
            bucket_predicate = ("event_type = ?", ["__unknown_bucket__"])
        else:
            bucket_predicate = clause

    predicates: list[tuple[str, list]] = list(base_predicates)
    if bucket_predicate:
        predicates.append(bucket_predicate)

    def _where(prefix: str = "") -> tuple[str, tuple]:
        sql = [f"{prefix}{clause}" for clause, _ in predicates]
        params = [value for _, values in predicates for value in values]
        return (" AND " + " AND ".join(sql) if sql else "", tuple(params))

    where, params = _where("e.")

    with _connect() as conn:
        r = Reader(conn)
        if bucket_key is not None and bucket_key not in _BUCKETS:
            r.notes.append(f"unknown audit bucket '{bucket_key}' — reported as no matching events")
        event_name, event_join = r.org_names("e.org_id")
        rows = r.rows(
            f"""
            SELECT e.id, e.event_type AS eventType, e.org_id AS orgId, e.user_id AS userId,
                   e.run_id AS runId, e.assessment_id AS assessmentId, e.document_id AS documentId,
                   e.metadata_json AS metadataJson, e.created_at AS createdAt,
                   {event_name}
            FROM audit_events e
            {event_join}
            WHERE 1=1{where}
            ORDER BY e.id DESC LIMIT ?
            """,
            (*params, max(1, min(int(limit), 1000))),
            requires=("audit_events",),
        )
        events = []
        for row in rows:
            try:
                metadata = json.loads(row.pop("metadataJson", None) or "{}")
            except Exception:  # noqa: BLE001
                metadata = {}
            row["metadata"] = metadata
            row["label"] = event_label(row["eventType"])
            row["category"] = event_category(row["eventType"])
            events.append(row)

        # Bucket counts run over the same organization/user/window filters as the
        # event page, but not over the selected bucket itself.
        def _query_count(clauses: list[str], clause_params: list) -> int:
            # No clauses means "no filters" — the whole log matches, not nothing.
            sql = "SELECT COUNT(*) AS c FROM audit_events"
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            try:
                row = conn.execute(sql, tuple(clause_params)).fetchone()
            except sqlite3.Error as exc:  # noqa: BLE001
                r.notes.append(f"event count failed: {str(exc)[:120]}")
                return 0
            return int(row["c"]) if row else 0

        def _count(types: tuple[str, ...] = (), like: str | None = None) -> int:
            clauses: list[str] = []
            clause_params: list = []
            if types:
                clauses.append(f"event_type IN ({','.join('?' for _ in types)})")
                clause_params.extend(types)
            if like:
                clauses.append("event_type LIKE ?")
                clause_params.append(like)
            for clause, values in base_predicates:
                clauses.append(clause)
                clause_params.extend(values)
            return _query_count(clauses, clause_params)

        by_category: dict[str, int] = {}
        event_totals: dict[str, int] = {}
        for event in events:
            by_category[event["category"]] = by_category.get(event["category"], 0) + 1
            event_totals[event["eventType"]] = event_totals.get(event["eventType"], 0) + 1

        return {
            "generatedAt": _iso(_now()),
            "filters": {
                "eventTypes": event_types or None,
                "bucket": bucket_key,
                "orgId": org_id,
                "userId": user_id,
                "windowDays": window_days,
                "limit": limit,
            },
            "count": len(events),
            "events": events,
            "totals": {
                "assessmentCreation": _count(_CREATION_EVENTS),
                "deletes": _count(_DELETE_EVENTS),
                "roleChanges": _count(_ROLE_EVENTS),
                "billingEvents": _count(like="billing.%"),
                "loginEvents": _count(("user.login",)),
                "reportExports": _count(("report.exported",)),
                "providerHealth": _count(("provider.health",)),
                "adminConsoleViews": _count(("admin.console_viewed",)),
                "matchingEvents": _query_count(
                    [clause for clause, _ in predicates],
                    [value for _, values in predicates for value in values],
                ),
                "totalEvents": r.count("audit_events"),
            },
            "byCategory": by_category,
            "byEventType": event_totals,
            "distinctOrgs": len({e["orgId"] for e in events if e["orgId"]}),
            "distinctUsers": len({e["userId"] for e in events if e["userId"]}),
            "dataNotes": r.notes,
        }


# ── Platform panel — Organizations (the management view) ─────────────────────
#
# ``user_management`` answers "who is on the platform". This answers "what
# would an operator act on": each workspace carries the subscription state an
# operator manages, the activation state an enterprise account is stuck in, and
# the usage that makes a plan change a considered decision instead of a guess.

def organizations(
    *,
    search: str = "",
    plan: str | None = None,
    status: str | None = None,
    limit: int = 200,
    window_days: int = 30,
) -> dict:
    since = _since(window_days)
    with _connect() as conn:
        r = Reader(conn)
        enrichments = (
            ("organization_members",
             "(SELECT COUNT(*) FROM organization_members m WHERE m.org_id = o.id) AS members, "
             "(SELECT m.user_id FROM organization_members m WHERE m.org_id = o.id AND m.role = 'owner'"
             " ORDER BY m.created_at ASC LIMIT 1) AS primaryOwnerUserId"),
            ("assessment_contexts",
             "(SELECT COUNT(*) FROM assessment_contexts a WHERE a.org_id = o.id) AS assessments, "
             "(SELECT COUNT(*) FROM assessment_contexts a WHERE a.org_id = o.id AND a.created_at >= :since)"
             " AS assessmentsInWindow"),
            ("documents",
             "(SELECT COUNT(*) FROM documents d WHERE d.org_id = o.id AND d.deleted_at IS NULL) AS documents, "
             "(SELECT COALESCE(SUM(d.size_bytes), 0) FROM documents d"
             " WHERE d.org_id = o.id AND d.deleted_at IS NULL) AS storageBytes"),
            ("audit_events",
             "(SELECT MAX(e.created_at) FROM audit_events e WHERE e.org_id = o.id) AS lastActivityAt, "
             "(SELECT COUNT(*) FROM audit_events e WHERE e.org_id = o.id AND e.event_type = 'report.exported')"
             " AS reportExports"),
            ("subscriptions",
             "s.plan AS subscriptionPlan, s.status AS billingStatus, s.amount AS amount, s.currency AS currency,"
             " s.billing_cycle AS billingCycle, s.current_period_end AS currentPeriodEnd,"
             " s.cancel_at_period_end AS cancelAtPeriodEnd, s.pending_plan AS pendingPlan,"
             " s.activation_state AS activationState, s.last_error AS lastError, s.updated_at AS subscriptionUpdatedAt"),
        )
        columns = [
            "o.id AS orgId", "o.name AS name", "o.slug AS slug", "o.plan AS plan",
            "o.personal AS personal", "o.created_by AS createdBy", "o.created_at AS createdAt",
        ]
        joins = ""
        by_table = dict(enrichments)
        if r.has("subscriptions"):
            # The subscription block already qualifies its own columns (s.*), so
            # it is appended verbatim once the join exists.
            joins = "LEFT JOIN subscriptions s ON s.org_id = o.id"
            columns.append(by_table["subscriptions"])
        columns += [expr for table, expr in enrichments if r.has(table) and table != "subscriptions"]

        # Named bindings, deliberately: most of the columns above exist only
        # when their table exists, so a positional parameter list would have to
        # guess which of them survived — on a database without
        # ``assessment_contexts`` the count subquery (and with it ``since``) is
        # gone, and the whole panel would fail to bind. A name binds to the
        # fragment that declares it, no matter what else is in the SELECT.
        predicates: list[str] = []
        params: dict[str, object] = {"since": since, "limit": max(1, min(int(limit), 500))}
        if search:
            predicates.append("(o.name LIKE :search OR o.slug LIKE :search OR o.id LIKE :search)")
            params["search"] = f"%{search}%"
        if plan:
            predicates.append("o.plan = :plan")
            params["plan"] = str(plan).strip().lower()
        if status and r.has("subscriptions"):
            predicates.append("s.status = :status")
            params["status"] = str(status).strip().lower()
        elif status:
            r.notes.append("no subscriptions table yet — status filter cannot be applied")
        sql = f"SELECT {', '.join(columns)} FROM organizations o {joins}"
        if predicates:
            sql += " WHERE " + " AND ".join(predicates)
        sql += " ORDER BY o.created_at DESC LIMIT :limit"

        rows = r.rows(sql, params, requires=("organizations",))
        for row in rows:
            for key, default in (
                ("members", 0), ("primaryOwnerUserId", None), ("assessments", 0),
                ("assessmentsInWindow", 0), ("documents", 0), ("storageBytes", 0),
                ("lastActivityAt", None), ("reportExports", 0), ("billingStatus", None),
                ("subscriptionPlan", None), ("amount", None), ("currency", None),
                ("billingCycle", None), ("currentPeriodEnd", None), ("pendingPlan", None),
                ("activationState", None), ("lastError", None), ("subscriptionUpdatedAt", None),
            ):
                row.setdefault(key, default)
            row["personal"] = bool(row.get("personal"))
            row["cancelAtPeriodEnd"] = bool(row.get("cancelAtPeriodEnd") or 0)
            row["needsAttention"] = _needs_attention(row, since)

        totals_row = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN personal = 0 THEN 1 ELSE 0 END) AS teams,
                   SUM(CASE WHEN personal = 1 THEN 1 ELSE 0 END) AS personalWorkspaces,
                   SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS createdInWindow
            FROM organizations
            """,
            (since,),
            requires=("organizations",),
        ) or {}
        subs = r.one(
            """
            SELECT COUNT(*) AS rows_,
                   SUM(CASE WHEN status = 'suspended' THEN 1 ELSE 0 END) AS suspended,
                   SUM(CASE WHEN status = 'past_due' THEN 1 ELSE 0 END) AS pastDue,
                   SUM(CASE WHEN status = 'grace' THEN 1 ELSE 0 END) AS grace,
                   SUM(CASE WHEN plan = 'enterprise' THEN 1 ELSE 0 END) AS enterprise,
                   SUM(CASE WHEN activation_state = 'requested' THEN 1 ELSE 0 END) AS activationRequested,
                   SUM(CASE WHEN pending_plan IS NOT NULL THEN 1 ELSE 0 END) AS scheduledChanges
            FROM subscriptions
            """,
            requires=("subscriptions",),
        ) or {}
        if r.has("subscriptions") and r.has("organizations"):
            without = r.count(
                "organizations", "id NOT IN (SELECT org_id FROM subscriptions)"
            )
            if without:
                r.notes.append(
                    f"{without} workspace(s) have no subscription row — they bill as 'free' by default and "
                    "appear here as withoutSubscriptionRow rather than as a paid plan"
                )
        else:
            without = 0

        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "filters": {"search": search or None, "plan": plan, "status": status, "limit": limit},
            "totals": {
                "organizations": int(totals_row.get("total") or 0),
                "teamWorkspaces": int(totals_row.get("teams") or 0),
                "personalWorkspaces": int(totals_row.get("personalWorkspaces") or 0),
                "createdInWindow": int(totals_row.get("createdInWindow") or 0),
                "listed": len(rows),
                "withoutSubscriptionRow": int(without),
                "suspended": int(subs.get("suspended") or 0),
                "pastDue": int(subs.get("pastDue") or 0),
                "inGrace": int(subs.get("grace") or 0),
                "enterprise": int(subs.get("enterprise") or 0),
                "activationRequested": int(subs.get("activationRequested") or 0),
                "scheduledChanges": int(subs.get("scheduledChanges") or 0),
                "needsAttention": sum(1 for row in rows if row["needsAttention"]),
            },
            "organizations": rows,
            "attentionDefinition": (
                "A workspace needs attention when it is suspended, past due, in grace, has an "
                "expired billing period, or has an Enterprise activation waiting to be approved."
            ),
            "dataNotes": r.notes,
        }


def _needs_attention(row: dict, since: str) -> bool:
    """One definition of 'an operator should look at this account'."""
    if str(row.get("billingStatus") or "") in {"suspended", "past_due", "grace"}:
        return True
    if str(row.get("activationState") or "") == "requested":
        return True
    period_end = row.get("currentPeriodEnd")
    parsed = _parse_dt(period_end)
    if parsed is not None and parsed < _now() and not row.get("pendingPlan"):
        return True
    return False


# ── Platform panel — Assessments ─────────────────────────────────────────────

def assessments_panel(
    *,
    status: str | None = None,
    org_id: str | None = None,
    search: str = "",
    limit: int = 100,
    window_days: int = 30,
) -> dict:
    since = _since(window_days)
    with _connect() as conn:
        r = Reader(conn)
        event_name, event_join = r.org_names("a.org_id")
        predicates = ["1=1"]
        # The list itself is not window-filtered — an operator searching for an
        # older assessment expects it to appear, while `windowDays` scopes the
        # counts above it. Only the declared filters bind here.
        params: list[object] = []
        if status:
            predicates.append("a.status = ?")
            params.append(str(status).strip().lower())
        if org_id:
            predicates.append("a.org_id = ?")
            params.append(org_id)
        if search:
            predicates.append("(a.assessment_id LIKE ? OR a.run_id LIKE ? OR a.user_id LIKE ?)")
            params += [f"%{search}%"] * 3
        rows = r.rows(
            f"""
            SELECT a.assessment_id AS assessmentId, a.run_id AS runId, a.assessment_type AS assessmentType,
                   a.status AS status, a.user_id AS userId, a.org_id AS orgId, {event_name},
                   a.created_at AS createdAt, a.updated_at AS updatedAt
            FROM assessment_contexts a {event_join}
            WHERE {' AND '.join(predicates)}
            ORDER BY a.created_at DESC LIMIT ?
            """,
            tuple(params) + (max(1, min(int(limit), 500)),),
            requires=("assessment_contexts",),
        )
        by_status = r.rows(
            "SELECT status, COUNT(*) AS c FROM assessment_contexts GROUP BY status ORDER BY c DESC",
            requires=("assessment_contexts",),
        )
        totals_row = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS createdInWindow,
                   SUM(CASE WHEN run_id IS NULL THEN 1 ELSE 0 END) AS neverRun
            FROM assessment_contexts
            """,
            (since,),
            requires=("assessment_contexts",),
        ) or {}
        run_row = r.one(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed
            FROM api_runs
            """,
            requires=("api_runs",),
        ) or {}
        failures = r.rows(
            """
            SELECT run_id AS runId, status AS status, error_message AS errorMessage,
                   user_id AS userId, org_id AS orgId, created_at AS createdAt, completed_at AS completedAt
            FROM api_runs WHERE status = 'failed' ORDER BY created_at DESC LIMIT 25
            """,
            requires=("api_runs",),
        )
        duration = r.value(
            "api_runs",
            "SELECT AVG((julianday(completed_at) - julianday(created_at)) * 86400.0)"
            " FROM api_runs WHERE completed_at IS NOT NULL AND status = 'completed'",
        )
        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "filters": {"status": status, "orgId": org_id, "search": search or None, "limit": limit},
            "totals": {
                "assessments": int(totals_row.get("total") or 0),
                "createdInWindow": int(totals_row.get("createdInWindow") or 0),
                "neverRun": int(totals_row.get("neverRun") or 0),
                "listed": len(rows),
                "pipelineRuns": int(run_row.get("total") or 0),
                "failedRuns": int(run_row.get("failed") or 0),
                "runningNow": int(run_row.get("running") or 0),
                "completedRuns": int(run_row.get("completed") or 0),
                "failureRate": _rate(int(run_row.get("failed") or 0), int(run_row.get("total") or 0)),
                "averageRunSeconds": _round_or_none(duration, 1),
            },
            "byStatus": {(s["status"] or "unknown"): int(s["c"]) for s in by_status},
            "assessments": rows,
            "recentFailures": failures,
            "dataNotes": r.notes,
        }


# ── Platform panel — Reports ─────────────────────────────────────────────────

def reports_panel(*, org_id: str | None = None, limit: int = 150, window_days: int = 30) -> dict:
    """Report exports, read from the audit stream.

    There is no ``reports`` table: a report exists as the event that records it
    was produced. Saying so here keeps the panel from implying a store that
    protects nothing, and keeps the numbers reconcilable with the audit log.
    """
    since = _since(window_days)
    with _connect() as conn:
        r = Reader(conn)
        event_name, event_join = r.org_names("e.org_id")
        predicates = ["e.event_type = 'report.exported'"]
        params: list[object] = []
        if org_id:
            predicates.append("e.org_id = ?")
            params.append(org_id)
        rows = r.rows(
            f"""
            SELECT e.id AS eventId, e.org_id AS orgId, {event_name}, e.user_id AS userId,
                   e.assessment_id AS assessmentId, e.created_at AS createdAt, e.metadata_json
            FROM audit_events e {event_join}
            WHERE {' AND '.join(predicates)}
            ORDER BY e.id DESC LIMIT ?
            """,
            tuple(params) + (max(1, min(int(limit), 500)),),
            requires=("audit_events",),
        )
        for row in rows:
            try:
                meta = json.loads(row.pop("metadata_json") or "{}")
            except Exception:  # noqa: BLE001
                meta = {}
            row.pop("metadata_json", None)
            row["reportKind"] = meta.get("reportKind") or meta.get("kind") or "unknown"
            row["format"] = meta.get("format") or "unknown"
            row["fileName"] = meta.get("fileName") or meta.get("filename")
        in_window = r.count("audit_events", "event_type = 'report.exported' AND created_at >= ?", (since,))
        total = r.count("audit_events", "event_type = 'report.exported'")
        kinds: dict[str, int] = {}
        formats: dict[str, int] = {}
        for row in rows:
            kinds[row["reportKind"]] = kinds.get(row["reportKind"], 0) + 1
            formats[row["format"]] = formats.get(row["format"], 0) + 1
        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "filters": {"orgId": org_id, "limit": limit},
            "totals": {
                "exports": total,
                "exportsInWindow": in_window,
                "listed": len(rows),
                "distinctOrgs": len({row["orgId"] for row in rows if row["orgId"]}),
                "distinctUsers": len({row["userId"] for row in rows if row["userId"]}),
            },
            "byKind": kinds,
            "byFormat": formats,
            "reports": rows,
            "sourceNote": (
                "Derived from 'report.exported' audit events — the platform has no report table, "
                "so a report is only as durable as its audit entry."
            ),
            "dataNotes": r.notes,
        }


# ── Platform panel — Conversations ───────────────────────────────────────────

def conversations_panel(*, org_id: str | None = None, limit: int = 100, window_days: int = 30) -> dict:
    since = _since(window_days)
    with _connect() as conn:
        r = Reader(conn)
        event_name, event_join = r.org_names("c.org_id")
        predicates = ["1=1"]
        # Same contract as the assessments panel: the list honours the filters,
        # the window scopes the counts. Binding an unused `since` here would
        # break every conversation query the moment real data existed.
        params: list[object] = []
        if org_id:
            predicates.append("c.org_id = ?")
            params.append(org_id)
        rows = r.rows(
            f"""
            SELECT c.conversation_id AS conversationId, c.assessment_id AS assessmentId,
                   c.run_id AS runId, c.user_id AS userId, c.org_id AS orgId, {event_name},
                   c.title AS title, c.is_default AS isDefault, c.created_at AS createdAt,
                   c.updated_at AS updatedAt,
                   (SELECT COUNT(*) FROM analyst_messages m WHERE m.conversation_id = c.conversation_id) AS messages,
                   (SELECT COUNT(*) FROM analyst_messages m WHERE m.conversation_id = c.conversation_id
                    AND m.role = 'user') AS questions,
                   (SELECT MAX(m.created_at) FROM analyst_messages m WHERE m.conversation_id = c.conversation_id)
                   AS lastMessageAt
            FROM analyst_conversations c {event_join}
            WHERE {' AND '.join(predicates)}
            ORDER BY c.updated_at DESC LIMIT ?
            """,
            tuple(params) + (max(1, min(int(limit), 500)),),
            requires=("analyst_conversations", "analyst_messages"),
        )
        totals_row = r.one(
            """
            SELECT (SELECT COUNT(*) FROM analyst_conversations) AS conversations,
                   (SELECT COUNT(*) FROM analyst_messages) AS messages,
                   (SELECT COUNT(*) FROM analyst_conversations WHERE created_at >= ?) AS createdInWindow,
                   (SELECT COUNT(*) FROM analyst_conversations WHERE assessment_id IS NULL) AS unlinked,
                   (SELECT COUNT(*) FROM analyst_messages WHERE role = 'user' AND created_at >= ?) AS questionsInWindow
            """,
            (since, since),
            requires=("analyst_conversations", "analyst_messages"),
        ) or {}
        top = sorted(rows, key=lambda c: int(c.get("messages") or 0), reverse=True)[:5]
        return {
            "generatedAt": _iso(_now()),
            "windowDays": window_days,
            "filters": {"orgId": org_id, "limit": limit},
            "totals": {
                "conversations": int(totals_row.get("conversations") or 0),
                "messages": int(totals_row.get("messages") or 0),
                "createdInWindow": int(totals_row.get("createdInWindow") or 0),
                "questionsInWindow": int(totals_row.get("questionsInWindow") or 0),
                "withoutAssessment": int(totals_row.get("unlinked") or 0),
                "listed": len(rows),
            },
            "conversations": rows,
            "busiest": [
                {"conversationId": c["conversationId"], "title": c.get("title"),
                 "orgName": c.get("orgName"), "messages": int(c.get("messages") or 0)}
                for c in top
            ],
            "dataNotes": r.notes,
        }


# ── Platform panel — Access (the role architecture itself) ───────────────────

def _last_seen(user_id: str | None) -> str | None:
    """Read from the audit stream: the console stores no presence column."""
    if not user_id:
        return None
    try:
        from kulima.core.audit.repository import AuditRepository

        events = AuditRepository().list(
            org_id=None, user_id=user_id, event_types=["admin.console_viewed"], limit=1,
        )
        return str(events[0]["createdAt"]) if events else None
    except Exception:  # noqa: BLE001 — presence is decorative, never fatal
        return None


def platform_access(panel_window: int = 30) -> dict:
    """The two planes side by side, plus the roster the operator manages.

    Nothing here is secret except the identities of *other* operators, which the
    roster legitimately shows to an administrator (they can grant that access
    anyway). The break-glass environment lists are reported as counts only.
    """
    from kulima.core.orgs.platform_admins import (
        ORG_ROLE_PLATFORM_CAPABILITIES,
        PLATFORM_ADMIN_ROLE,
        PLATFORM_ADMIN_ROLE_LABEL,
        PLATFORM_ROLE_CAPABILITIES,
        CAPABILITY_LABELS,
        get_repo,
    )
    from kulima.core.orgs.models import ROLE_LABELS, Role

    settings = get_settings()
    try:
        repo = get_repo()
        admins = repo.list_admins(include_revoked=True)
        active = repo.count_active()
        store_error = None
    except Exception as exc:  # noqa: BLE001 — the screen must render even if the store is broken
        admins, active = [], 0
        store_error = f"platform_admins store unavailable: {str(exc)[:160]}"

    capabilities = [
        {"id": c.value, "label": CAPABILITY_LABELS.get(c.value, c.value)}
        for c in sorted(PLATFORM_ROLE_CAPABILITIES[PLATFORM_ADMIN_ROLE], key=lambda x: x.value)
    ]
    with _connect() as conn:
        r = Reader(conn)
        role_rows = r.rows(
            "SELECT role, COUNT(*) AS c FROM organization_members GROUP BY role ORDER BY c DESC",
            requires=("organization_members",),
        )
    since = _since(panel_window)
    return {
        "generatedAt": _iso(_now()),
        "windowDays": panel_window,
        "platformRole": {
            "id": PLATFORM_ADMIN_ROLE,
            "label": PLATFORM_ADMIN_ROLE_LABEL,
            "capabilities": capabilities,
            "note": (
                "A platform principal, stored in its own table. It is not a value in the "
                "organization role enum, because membership rows are written by customers."
            ),
        },
        "orgRoles": [
            {
                "id": role.value,
                "label": ROLE_LABELS.get(role.value, role.value.title()),
                "platformCapabilities": ORG_ROLE_PLATFORM_CAPABILITIES.get(role.value, []),
            }
            for role in Role
        ],
        "roleDistribution": {(row["role"] or "unknown"): int(row["c"]) for row in role_rows},
        "store": {
            "configured": active > 0,
            "activeCount": active,
            "rowCount": len(admins),
            "primaryEmail": settings.platform_admin_primary_email or None,
            "bootstrappedFrom": sorted(set(settings.platform_admin_emails) | set(settings.admin_emails)),
            "error": store_error,
        },
        "breakGlass": {
            "configured": bool(settings.admin_emails or settings.platform_admin_user_ids),
            "size": len({str(e).strip().lower() for e in settings.admin_emails if str(e).strip()}
                        | {str(e).strip().lower() for e in settings.platform_admin_user_ids if str(e).strip()}),
            "envNames": ("KULIMA_ADMIN_EMAILS", "KULIMA_PLATFORM_ADMIN_USER_IDS"),
            "note": (
                "Environment identities grant access when the role store cannot, and are labelled "
                "'break-glass' in every audit event they produce."
            ),
        },
        "admins": [
            {**a.to_payload(),
             "isPrimary": repo.is_primary(a) if store_error is None else False,
             "lastSeenAt": _last_seen(a.user_id),
             "activeSinceWindow": bool(a.granted_at and str(a.granted_at) >= since)}
            for a in admins
        ],
        "dataNotes": [n for n in ([store_error] if store_error else [])],
    }
