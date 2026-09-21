"""Assessment Context adapter — the single intake engine's backend.

Implements Steps 1–5 of the "collect once, reuse everywhere" refactor:

1. Landing-page upload creates one shared Assessment Context.
2. Documents run through the existing 7-step evidence pipeline
   (``document_adapter.save_uploaded_file``) unchanged.
3. Auto extraction fills entity fields (organisation, founder, sector,
   country, website, team, problem statement) with per-field confidence.
4. The context is persisted centrally (``AssessmentRepository``) and reused by
   Signals, Flex, Decision, Reports and Ask IC.
5. Starting the run resolves the run identity from the context, so Tavily
   research is driven by the extracted entity — the user is only asked for
   confirmation when extraction confidence is low.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional, Sequence

from fastapi import UploadFile

from kulima.core.assessment.extraction import extract_assessment_fields, merge_extractions
from kulima.core.assessment.models import (
    ASSESSMENT_TYPE_LABELS,
    AssessmentContext,
    AssessmentDocument,
    AssessmentExtraction,
    AssessmentStatus,
    AssessmentType,
    ExtractedField,
)
from kulima.core.assessment.repository import AssessmentRepository
from kulima.core.assessment.service import (
    CONFIRMATION_THRESHOLD,
    apply_extraction,
    coerce_assessment_type,
    display_entity,
    manual_patch,
    resolve_run_identity,
    sector_hint,
)
from kulima.core.audit import record_event
from kulima.core.billing.service import assert_can_assess
from .document_adapter import UPLOAD_DIR, save_uploaded_file
from .orchestrator_adapter import start_intelligence_run

_log = logging.getLogger(__name__)

_repo = AssessmentRepository()

# Cap the stored extracted text so the context payload stays reasonable even
# for very large uploads (full text remains available in document chunks).
MAX_STORED_TEXT_CHARS = 200_000
PREVIEW_CHARS = 800

_EXTRACTION_FIELDS = (
    "organization_name",
    "startup_name",
    "founder_name",
    "sector",
    "country",
    "website",
    "team",
    "problem_statement",
)


class AssessmentError(Exception):
    """Raised for assessment adapter failures (mapped to HTTP by the router)."""

    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


# ── Serialisation ────────────────────────────────────────────────────────


def _field_payload(field: Optional[ExtractedField]) -> Optional[dict[str, Any]]:
    if field is None or field.is_empty:
        return None
    return {
        "value": field.value,
        "confidence": round(float(field.confidence), 3),
        "source": field.source,
    }


def serialize_context(ctx: AssessmentContext) -> dict[str, Any]:
    """API payload for an Assessment Context (camelCase, bounded size)."""
    fields = {
        name: payload
        for name in _EXTRACTION_FIELDS
        if (payload := _field_payload(getattr(ctx.extraction, name, None))) is not None
    }
    atype_value = getattr(ctx.assessment_type, "value", str(ctx.assessment_type))
    return {
        "assessmentId": ctx.assessment_id,
        "assessmentType": atype_value,
        "assessmentTypeLabel": ASSESSMENT_TYPE_LABELS.get(atype_value, "Assessment"),
        "status": getattr(ctx.status, "value", str(ctx.status)),
        "runId": ctx.run_id,
        "requiresConfirmation": ctx.requires_confirmation,
        "confidenceThreshold": CONFIRMATION_THRESHOLD,
        "displayEntity": display_entity(ctx),
        "organizationName": ctx.organization_name,
        "startupName": ctx.startup_name,
        "founderName": ctx.founder_name,
        "sector": ctx.sector,
        "country": ctx.country,
        "website": ctx.website,
        "team": ctx.team,
        "problemStatement": ctx.problem_statement,
        "confidence": round(float(ctx.extraction.confidence), 3),
        "extraction": {
            "confidence": round(float(ctx.extraction.confidence), 3),
            "textAvailable": bool(ctx.extraction.text_available),
            "fields": fields,
        },
        "documentIds": list(ctx.document_ids),
        "uploadedDocuments": [doc.model_dump(mode="json") for doc in ctx.uploaded_documents],
        "documentCount": len(ctx.uploaded_documents),
        "extractedTextPreview": (ctx.extracted_text or "")[:PREVIEW_CHARS],
        "extractedTextLength": ctx.extracted_text_length or len(ctx.extracted_text or ""),
        "trustScore": ctx.trust_score,
        "signals": list(ctx.signals),
        "decision": dict(ctx.decision),
        "createdAt": ctx.created_at,
        "updatedAt": ctx.updated_at,
    }


# ── Create (landing-page intake) ─────────────────────────────────────────


def create_assessment(
    files: Sequence[UploadFile],
    assessment_type: str | AssessmentType,
    user_id: Optional[str],
    *,
    entity_name: Optional[str] = None,
    founder_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    sector: Optional[str] = None,
    country: Optional[str] = None,
    org_id: Optional[str] = None,
) -> dict[str, Any]:
    """Ingest uploaded documents and build the shared Assessment Context.

    Documents flow through the existing evidence pipeline untouched; the
    extracted text from each document feeds the deterministic extractor and
    the merged result populates the context automatically (no re-entry).

    Enterprise Trust: the context is bound to the workspace (``org_id``),
    subscription state is checked first (suspension blocks new assessments),
    and the creation is written to the audit log.
    """
    if not files:
        raise AssessmentError("no_documents", "At least one document is required.")

    if org_id is not None:
        # Raises BillingBlocked (mapped to 402/403 by the router) when the
        # workspace is suspended or — with enforcement enabled — out of quota.
        assert_can_assess(org_id)

    atype = coerce_assessment_type(assessment_type)
    ctx = AssessmentContext(
        assessment_id=str(uuid.uuid4()),
        assessment_type=atype,
        status=AssessmentStatus.INTAKE,
        created_by=user_id,
    )

    # 1. Run each document through the existing evidence pipeline.
    texts: list[tuple[str, str]] = []
    trust_scores: list[float] = []
    for upload in files:
        payload = save_uploaded_file(
            upload,
            run_uuid=None,
            user_id=user_id,
            org_id=org_id,
            assessment_id=ctx.assessment_id,
        )
        name = str(payload.get("name") or "uploaded_document")
        extracted_text = str(payload.get("extractedText") or "")
        texts.append((name, extracted_text))
        if payload.get("trustScore") is not None:
            trust_scores.append(float(payload["trustScore"]))

        ctx.document_ids.append(str(payload.get("id") or ""))
        ctx.uploaded_documents.append(
            AssessmentDocument(
                id=str(payload.get("id") or ""),
                name=name,
                url=str(payload.get("url") or ""),
                file_type=str(payload.get("fileType") or ""),
                trust_score=float(payload["trustScore"]) if payload.get("trustScore") is not None else None,
                evidence_status=payload.get("evidenceStatus"),
                signals=list(payload.get("signals") or []),
                evidence_items=list(payload.get("evidenceItems") or []),
                decision_impact=str(payload.get("decisionImpact") or ""),
                raw_summary=str(payload.get("rawSummary") or ""),
                trust_breakdown=dict(payload.get("trustBreakdown") or {}),
                upload_date=str(payload.get("uploadDate") or ""),
            )
        )

    # 2. Auto extraction (Step 3) — no user re-entry required.
    extraction = merge_extractions(
        extract_assessment_fields(text, atype, filename=name) for name, text in texts
    )
    ctx.extracted_text = "\n\n".join(text for _, text in texts)[:MAX_STORED_TEXT_CHARS]
    ctx.extracted_text_length = sum(len(text) for _, text in texts)

    # 3. Persist extraction + lifecycle status.
    apply_extraction(ctx, extraction)

    # Optional intake hints typed on the landing page override weak extraction.
    if any([entity_name, founder_name, organization_name, sector, country]):
        manual_patch(
            ctx,
            entity_name=entity_name,
            founder_name=founder_name,
            organization_name=organization_name,
            sector=sector,
            country=country,
        )

    if trust_scores:
        ctx.trust_score = round(sum(trust_scores) / len(trust_scores), 1)

    _repo.save(ctx, org_id=org_id)
    record_event(
        "assessment.created",
        org_id=org_id,
        user_id=user_id,
        assessment_id=ctx.assessment_id,
        metadata={
            "assessmentType": getattr(atype, "value", str(atype)),
            "documents": len(ctx.uploaded_documents),
            "organizationName": ctx.organization_name,
            "sector": ctx.sector,
            "country": ctx.country,
            "trustScore": ctx.trust_score,
        },
    )
    _log.info(
        "assessment_created",
        extra={
            "assessment_id": ctx.assessment_id,
            "assessment_type": getattr(atype, "value", str(atype)),
            "documents": len(ctx.uploaded_documents),
            "confidence": ctx.extraction.confidence,
            "requires_confirmation": ctx.requires_confirmation,
        },
    )
    return serialize_context(ctx)


# ── Read / update ────────────────────────────────────────────────────────


def get_assessment(
    assessment_id: str,
    user_id: Optional[str],
    *,
    org_id: Optional[str] = None,
) -> dict[str, Any]:
    ctx = _repo.get(assessment_id, user_id=user_id, org_id=org_id)
    if ctx is None:
        raise AssessmentError("assessment_not_found", "Assessment context not found.")
    return serialize_context(ctx)


def resolve_assessment_for_brief(
    founder_name: str,
    startup_name: str,
    *,
    run_id: Optional[str] = None,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> Optional[AssessmentContext]:
    """Locate the Assessment Context that produced a run (best-effort).

    Used to ground Ask IC (Step 9). Tries the run id first, then falls back to
    matching the resolved run identity so integer-db-id navigation still works.
    """
    try:
        if run_id:
            ctx = _repo.get_by_run_id(str(run_id), user_id=user_id, org_id=org_id)
            if ctx is not None:
                return ctx
        for candidate in _repo.list_for_user(user_id, limit=25):
            cand_founder, cand_startup = resolve_run_identity(candidate)
            if cand_founder == founder_name and cand_startup == startup_name:
                return candidate
    except Exception as exc:  # noqa: BLE001
        _log.warning("Assessment lookup for grounding failed: %s", exc)
    return None


def update_assessment(
    assessment_id: str,
    user_id: Optional[str],
    patch: dict[str, Any],
    *,
    org_id: Optional[str] = None,
) -> dict[str, Any]:
    """Apply user-supplied corrections when extraction confidence is low."""
    ctx = _repo.get(assessment_id, user_id=user_id, org_id=org_id)
    if ctx is None:
        raise AssessmentError("assessment_not_found", "Assessment context not found.")

    if patch.get("assessmentType"):
        ctx.assessment_type = coerce_assessment_type(str(patch["assessmentType"]))

    manual_patch(
        ctx,
        entity_name=patch.get("entityName"),
        founder_name=patch.get("founderName"),
        organization_name=patch.get("organizationName"),
        sector=patch.get("sector"),
        country=patch.get("country"),
    )
    _repo.save(ctx)
    return serialize_context(ctx)


# ── Start run (Tavily research driven by the context) ────────────────────


def start_assessment_run(
    assessment_id: str,
    user_id: Optional[str],
    *,
    org_id: Optional[str] = None,
) -> dict[str, Any]:
    """Start (or reuse) the intelligence run grounded in the context.

    Idempotent while a run is running or complete: a second call returns the
    existing run instead of spending another Tavily research round.
    """
    ctx = _repo.get(assessment_id, user_id=user_id, org_id=org_id)
    if ctx is None:
        raise AssessmentError("assessment_not_found", "Assessment context not found.")

    if ctx.run_id and ctx.status in (AssessmentStatus.RUNNING, AssessmentStatus.COMPLETE):
        return {
            "assessmentId": ctx.assessment_id,
            "runId": ctx.run_id,
            "status": getattr(ctx.status, "value", str(ctx.status)),
            "reused": True,
        }

    if org_id is not None:
        # New runs are blocked while suspended (reuse above stays available so
        # customers can always read their existing results).
        assert_can_assess(org_id)

    founder, startup = resolve_run_identity(ctx)
    run_id = start_intelligence_run(
        founder,
        startup,
        user_id=user_id,
        assessment_id=ctx.assessment_id,
        document_ids=list(ctx.document_ids),
        sector_hint=sector_hint(ctx),
        org_id=org_id,
    )
    linked = _repo.link_run(ctx.assessment_id, run_id, status=AssessmentStatus.RUNNING)
    if linked is None:  # pragma: no cover - context vanished between calls
        raise AssessmentError("assessment_not_found", "Assessment context not found.")

    record_event(
        "assessment.started",
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        assessment_id=ctx.assessment_id,
        metadata={"founder": founder, "startup": startup, "documents": len(ctx.document_ids)},
    )

    _log.info(
        "assessment_run_started",
        extra={
            "assessment_id": ctx.assessment_id,
            "run_id": run_id,
            "founder": founder,
            "startup": startup,
        },
    )
    return {
        "assessmentId": ctx.assessment_id,
        "runId": run_id,
        "status": AssessmentStatus.RUNNING.value,
        "reused": False,
    }


# ── Complete deletion (Phase 1: customer data ownership) ─────────────────────


def purge_assessment(
    assessment_id: str,
    *,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> dict[str, Any]:
    """Permanently delete an assessment and every object it owns.

    Covers the Assessment Context, its uploaded documents (rows, chunks and
    stored files) and the linked intelligence run. Records an audit event with
    the purge summary — the deletion itself is part of the governance trail.
    """
    from kulima.core.documents.repository import DocumentRepository
    from kulima.db import IntelligenceRepository

    ctx = _repo.get(assessment_id, user_id=user_id, org_id=org_id)
    if ctx is None:
        raise AssessmentError("assessment_not_found", "Assessment context not found.")

    doc_repo = DocumentRepository()
    removed_documents = 0
    removed_files = 0

    document_ids = list(dict.fromkeys(list(ctx.document_ids or [])))
    for row in doc_repo.list_documents(assessment_id=assessment_id, org_id=org_id, include_deleted=True, limit=500):
        document_ids.append(row["id"])
    for row in doc_repo.list_documents(run_id=_int_run_id(ctx.run_id), include_deleted=True, limit=500) if ctx.run_id else []:
        document_ids.append(row["id"])

    for doc_id in dict.fromkeys(document_ids):
        doc = doc_repo.get_document(doc_id)
        if doc is None:
            continue
        storage_path = doc.get("storagePath")
        if storage_path:
            target = (UPLOAD_DIR / str(storage_path)).resolve()
            try:
                if target.is_file() and UPLOAD_DIR.resolve() in target.parents:
                    target.unlink()
                    removed_files += 1
            except OSError:
                _log.warning("purge_assessment: could not remove file %s", target)
        doc_repo.hard_delete_document(doc_id)
        removed_documents += 1

    removed_run = False
    if ctx.run_id and str(ctx.run_id).isdigit():
        removed_run = IntelligenceRepository().delete_run(int(ctx.run_id), org_id=org_id)
        try:
            from .run_repository import RunRepository

            RunRepository().delete_run(str(ctx.run_id))
        except Exception:  # noqa: BLE001
            pass

    removed_context = _repo.delete_context(assessment_id, org_id=org_id)

    summary = {
        "assessmentId": assessment_id,
        "deleted": bool(removed_context),
        "documentsPurged": removed_documents,
        "filesRemoved": removed_files,
        "runPurged": removed_run,
    }
    record_event(
        "assessment.deleted",
        org_id=org_id,
        user_id=user_id,
        run_id=ctx.run_id,
        assessment_id=assessment_id,
        metadata=summary,
    )
    return summary


def _int_run_id(run_id: Optional[str]) -> Optional[int]:
    try:
        return int(run_id) if run_id is not None and str(run_id).isdigit() else None
    except (TypeError, ValueError):  # pragma: no cover
        return None
