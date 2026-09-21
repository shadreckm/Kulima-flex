"""Enterprise audit log (Phase 4).

Append-only event stream for governance: document uploads, assessments,
signals, decisions, report exports, logins and external research triggers.
Every event carries org/user/run/assessment/document identifiers so the
Activity Timeline can be filtered per assessment without extra queries.
"""

from .repository import (
    AUDIT_SCHEMA,
    EVENT_TYPES,
    AuditRepository,
    list_events,
    record_event,
)

__all__ = [
    "AUDIT_SCHEMA",
    "EVENT_TYPES",
    "AuditRepository",
    "list_events",
    "record_event",
]
