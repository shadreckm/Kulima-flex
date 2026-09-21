"""Trust & Governance API (Enterprise Trust Phases 1, 4, 9).

- ``/summary``        — dashboard aggregates (documents, assessments, audit,
                        members, retention, security, billing).
- ``/activity``       — audit stream; scoped to an assessment/run for the
                        Activity Timeline, or workspace-wide for owners/admins.
- ``/login-event``    — records user.login once per session (client beacon).
- ``/data-ownership`` — who owns the data, what we hold, how to remove it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from kulima.config import get_settings
from kulima.core.assessment.repository import AssessmentRepository
from kulima.core.audit.repository import AuditRepository, record_event
from kulima.core.billing.service import billing_status, enforcement_enabled, usage_summary
from kulima.core.documents.repository import DocumentRepository
from kulima.core.orgs.models import Permission
from kulima.core.orgs.repository import OrgRepository
from kulima.core.security.encryption import (
    SCHEME_AESGCM,
    SCHEME_PLAIN,
    cryptography_available,
    encryption_key_configured,
)
from kulima.core.security.tavily_guard import ALLOWED_RESEARCH_FIELDS

from ..core.auth import OrgContext, get_current_org, require_permission

router = APIRouter()

_repos: dict[str, object] = {}


def _audit() -> AuditRepository:
    if "audit" not in _repos:
        _repos["audit"] = AuditRepository()
    return _repos["audit"]  # type: ignore[return-value]


def _docs() -> DocumentRepository:
    if "docs" not in _repos:
        _repos["docs"] = DocumentRepository()
    return _repos["docs"]  # type: ignore[return-value]


def _assessments() -> AssessmentRepository:
    if "assessments" not in _repos:
        _repos["assessments"] = AssessmentRepository()
    return _repos["assessments"]  # type: ignore[return-value]


def _orgs() -> OrgRepository:
    if "orgs" not in _repos:
        _repos["orgs"] = OrgRepository()
    return _repos["orgs"]  # type: ignore[return-value]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/summary")
async def governance_summary(
    current: OrgContext = Depends(require_permission(Permission.VIEW_AUDIT)),
):
    """Trust & Governance dashboard aggregates (Phase 9)."""
    org_id = current.org_id
    doc_stats = _docs().document_stats(org_id=org_id)
    assessments = _assessments().list_for_org(org_id, user_id=current.user_id, limit=500)
    active_assessments = _assessments().count_active_for_org(org_id)
    members = _orgs().list_members(org_id)

    by_role: dict[str, int] = {}
    for member in members:
        by_role[member.role.value] = by_role.get(member.role.value, 0) + 1

    audit_total = _audit().count(org_id=org_id)
    recent_events = _audit().list(org_id=org_id, limit=8)
    last_event = recent_events[0]["createdAt"] if recent_events else None

    settings = get_settings()
    at_rest_available = cryptography_available() and encryption_key_configured()
    billing = billing_status(org_id)

    return {
        "orgId": org_id,
        "orgName": current.org.name,
        "plan": current.plan,
        "documents": doc_stats,
        "assessments": {
            "total": len(assessments),
            "active": active_assessments,
        },
        "audit": {
            "totalEvents": audit_total,
            "lastEventAt": last_event,
            "recent": recent_events,
        },
        "members": {
            "total": len(members),
            "byRole": by_role,
        },
        "retention": {
            "defaultRetentionDays": settings.default_retention_days or None,
            "deletedPending": doc_stats.get("scheduledForDeletion", 0),
            "expired": doc_stats.get("expired", 0),
            "policyUrl": "/legal/data-retention",
            "policySummary": (
                "Customer-controlled retention: documents persist until your organization "
                "deletes them or a per-document retention window (if set) elapses. "
                "Complete assessment deletion removes files, chunks and context."
            ),
        },
        "security": {
            "atRestScheme": SCHEME_AESGCM if at_rest_available else SCHEME_PLAIN,
            "atRestEncryptionAvailable": at_rest_available,
            "storageMetadataRecorded": True,
            "accessChecks": True,
            "softDeleteEnabled": True,
            "privateByDefault": True,
            "externalResearchGuard": {
                "enabled": True,
                "mode": "metadata-only",
                "provider": "tavily",
                "allowedFields": list(ALLOWED_RESEARCH_FIELDS),
                "redactionActive": True,
            },
        },
        "billing": {
            "planId": billing.get("planId"),
            "status": billing.get("status"),
            "enforcementEnabled": enforcement_enabled(),
            "graceUntil": billing.get("graceUntil"),
        },
        "usage": usage_summary(org_id),
        "generatedAt": _now_iso(),
    }


@router.get("/activity")
async def activity_timeline(
    assessment_id: str | None = None,
    run_id: str | None = None,
    event_types: str | None = None,
    limit: int = 100,
    current: OrgContext = Depends(get_current_org),
):
    """Audit stream. Assessment/run timelines need only VIEW; the
    workspace-wide governance log requires the VIEW_AUDIT permission."""
    scoped = bool(assessment_id or run_id)
    if not scoped and not current.has_permission(Permission.VIEW_AUDIT):
        raise HTTPException(
            status_code=403,
            detail={
                "error": True,
                "code": "PERMISSION_DENIED",
                "message": "The workspace-wide audit log requires the 'view_audit' permission (Owner or Admin).",
                "required": "view_audit",
                "role": current.role.value,
            },
        )
    types = [t.strip() for t in (event_types or "").split(",") if t.strip()] or None
    events = _audit().list(
        org_id=current.org_id,
        assessment_id=assessment_id,
        run_id=run_id,
        event_types=types,
        limit=min(max(1, int(limit)), 500),
    )
    return {
        "events": events,
        "count": len(events),
        "scope": "assessment" if scoped else "workspace",
        "orgId": current.org_id,
    }


@router.post("/login-event")
async def record_login(current: OrgContext = Depends(get_current_org)):
    """Client beacon after sign-in — powers the 'User Login' audit trail."""
    record_event(
        "user.login",
        org_id=current.org_id,
        user_id=current.user_id,
        metadata={"role": current.role.value, "orgName": current.org.name},
    )
    return {"recorded": True}


@router.get("/data-ownership")
async def data_ownership(current: OrgContext = Depends(get_current_org)):
    """Phase 1 & 11: who owns the data, what we hold, what the user can do."""
    docs = _docs().list_documents(org_id=current.org_id, include_deleted=True, limit=1000)
    assessments = _assessments().list_for_org(current.org_id, user_id=current.user_id, limit=500)
    settings = get_settings()

    storage_bytes = sum(int(d.get("sizeBytes") or 0) for d in docs)
    return {
        "orgId": current.org_id,
        "orgName": current.org.name,
        "role": current.role.value,
        "roleLabel": current.role_label,
        "ownership": {
            "statement": "Your documents and assessment data belong to your organization — not to Kulima FLEX.",
            "points": [
                "Documents uploaded to this workspace are owned by your organization.",
                "Kulima FLEX processes them only to produce the assessments you request.",
                "You can export any document or assessment at any time.",
                "You can delete documents individually, or request complete assessment deletion.",
                "Complete deletion removes files from storage, document chunks and the assessment context.",
                "External research (Tavily) only ever receives public entity metadata — never your documents.",
                "Every upload, assessment, export, decision and deletion is recorded in the audit trail.",
            ],
            "externalResearchPolicy": {
                "provider": "tavily",
                "allowedFields": list(ALLOWED_RESEARCH_FIELDS),
                "statement": (
                    "Only organization name, founder name, sector, country and public company "
                    "information are ever sent to the research provider. Uploaded documents, "
                    "financial statements and contact details never leave the platform."
                ),
            },
        },
        "custody": {
            "documents": len(docs),
            "documentsActive": sum(1 for d in docs if not d.get("deletedAt")),
            "documentsDeleted": sum(1 for d in docs if d.get("deletedAt")),
            "storageBytes": storage_bytes,
            "assessments": len(assessments),
        },
        "retention": {
            "defaultRetentionDays": settings.default_retention_days or None,
            "policyUrl": "/legal/data-retention",
            "privacyPolicyUrl": "/legal/privacy-policy",
        },
        "capabilities": {
            "canExportDocuments": current.has_permission(Permission.EXPORT),
            "canDeleteDocuments": current.has_permission(Permission.DELETE_DATA),
            "canDeleteAssessment": current.has_permission(Permission.DELETE_DATA),
            "canManageUsers": current.has_permission(Permission.MANAGE_USERS),
            "canManageBilling": current.has_permission(Permission.MANAGE_BILLING),
        },
        "generatedAt": _now_iso(),
    }
