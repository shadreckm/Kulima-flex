from __future__ import annotations

import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple

from fastapi import UploadFile
from kulima.core.documents.models import Document, DocumentChunk, DocumentType, DocumentSource
from kulima.core.documents.repository import DocumentRepository
from kulima.core.documents.ingestion import DocumentIngestionService
from kulima.models import (
    SourceAttribution,
    UploadedEvidenceRecord,
    TrustScoreBreakdown,
    InvestmentBrief,
    Claim,
    ClaimType,
)
from kulima.db import IntelligenceRepository
from .run_repository import RunRepository

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "text/tab-separated-values",
    "application/json",
}
DISALLOWED_EXTENSIONS = {".exe", ".bat", ".cmd", ".js", ".ps1", ".msi", ".sh", ".vbs"}


class InvalidUploadError(Exception):
    """Raised when an uploaded document violates security constraints."""


_doc_repo = DocumentRepository()
_run_repo = RunRepository()
_brief_repo = IntelligenceRepository()
_ingestion_service = DocumentIngestionService()


def _calculate_trust_engine_scores(
    filename: str,
    doc_type: DocumentType,
    text_content: str,
    chunks_count: int,
    brief: Optional[InvestmentBrief] = None,
) -> TrustScoreBreakdown:
    """Deterministic, transparent Trust Engine score calculation."""
    # 1. Source Reliability (0–100)
    # Direct institutional documents (audited financials, regulatory filings, formal decks) carry higher baseline
    ext = Path(filename).suffix.lower()
    if doc_type == DocumentType.FINANCIAL_MODEL or "audit" in filename.lower() or "financial" in filename.lower():
        source_rel = 88.0
        rel_reason = "Primary financial document / formal audit records"
    elif doc_type == DocumentType.PITCH_DECK or doc_type == DocumentType.BOARD_MINUTES:
        source_rel = 82.0
        rel_reason = "Primary issuer pitch / governance material"
    elif ext in {".csv", ".xlsx"}:
        source_rel = 78.0
        rel_reason = "Structured operational data export"
    else:
        source_rel = 70.0
        rel_reason = "Generic corporate documentation"

    # 2. Recency (0–100)
    # Fresh uploads receive top recency rating
    recency_score = 95.0

    # 3. Completeness (0–100)
    # Evaluates character depth, chunk count, and presence of structured facts
    text_len = len(text_content.strip())
    if text_len > 3000 and chunks_count >= 3:
        completeness_score = 90.0
    elif text_len > 1000:
        completeness_score = 75.0
    elif text_len > 200:
        completeness_score = 55.0
    else:
        completeness_score = 30.0

    # 4. Corroboration (0–100)
    # Cross-reference with existing venture context if present
    corroboration_score = 65.0
    if brief:
        founder_mentioned = brief.founder_name.lower() in text_content.lower() if brief.founder_name else False
        startup_mentioned = brief.startup_name.lower() in text_content.lower() if brief.startup_name else False
        if founder_mentioned and startup_mentioned:
            corroboration_score = 88.0
        elif founder_mentioned or startup_mentioned:
            corroboration_score = 78.0
        else:
            corroboration_score = 55.0

    # Weighted Trust Calculation: 35% Source Reliability, 25% Corroboration, 15% Recency, 25% Completeness
    weighted = (
        (source_rel * 0.35)
        + (corroboration_score * 0.25)
        + (recency_score * 0.15)
        + (completeness_score * 0.25)
    )
    final_score = round(weighted, 1)

    rationale = (
        f"{rel_reason} ({source_rel:.0f}%). "
        f"Corroboration assessed at {corroboration_score:.0f}%. "
        f"Corpus completeness measured at {completeness_score:.0f}% with {chunks_count} section chunks."
    )

    return TrustScoreBreakdown(
        source_reliability=source_rel,
        corroboration=corroboration_score,
        recency=recency_score,
        completeness=completeness_score,
        weighted_score=weighted,
        final_trust_score=final_score,
        rationale=rationale,
    )


def _extract_signals_and_evidence(
    filename: str,
    text_content: str,
    trust: TrustScoreBreakdown,
    brief: Optional[InvestmentBrief] = None,
) -> Tuple[List[str], List[str], str, str]:
    """Analyze document text to extract evidence items, signals, and decision impact."""
    text_lower = text_content.lower()
    evidence_items: List[str] = []
    signals: List[str] = []

    # 1. Check for financial / runway / revenue signals
    has_revenue = "revenue" in text_lower or "arr" in text_lower or "mrr" in text_lower or "$" in text_content or "₦" in text_content
    has_debt = "debt" in text_lower or "liability" in text_lower or "loan" in text_lower or "default" in text_lower
    has_traction = "growth" in text_lower or "customer" in text_lower or "users" in text_lower or "retention" in text_lower
    has_audit = "audited" in text_lower or "deloitte" in text_lower or "pwc" in text_lower or "ey" in text_lower or "kpmg" in text_lower

    if has_revenue:
        evidence_items.append(f"Financial disclosures identified in {filename}")
        signals.append(f"Opportunity: Commercial revenue metrics documented in {filename}")

    if has_debt:
        signals.append(f"Risk: Debt obligations or liabilities referenced in {filename}")

    if has_traction:
        evidence_items.append(f"Operational traction indicators extracted from {filename}")
        signals.append(f"Opportunity: User/Customer growth trends reported in {filename}")

    if has_audit:
        evidence_items.append("Third-party verification / audit references present")
        signals.append("High Confidence Evidence: Independent verification referenced")

    if not evidence_items:
        evidence_items.append("INSUFFICIENT EVIDENCE: No structured financial or operational claims found in body.")

    # Status classification
    if trust.final_trust_score >= 80 and len(signals) > 0:
        status = "VERIFIED"
        impact = "Positive Evidence Attribution — Increases investment confidence"
    elif trust.final_trust_score >= 60:
        status = "CORROBORATED"
        impact = "Supporting Evidence Attribution — Corroborates core thesis"
    else:
        status = "INSUFFICIENT_EVIDENCE"
        impact = "Neutral — Requires additional independent verification"

    return evidence_items, signals, status, impact


class UploadFileAdapter:
    """Wrapper to make FastAPI UploadFile compatible with DocumentIngestionService."""
    def __init__(self, filename: str, content: bytes):
        self.name = filename
        self._bytes = content

    def read(self) -> bytes:
        return self._bytes

    def getvalue(self) -> bytes:
        return self._bytes


def save_uploaded_file(file: UploadFile, run_uuid: Optional[str] = None, user_id: Optional[str] = None) -> dict:
    """Execute the complete 7-step Evidence Pipeline for uploaded files."""

    # STEP 1: Validate and Store Document
    filename = file.filename or "uploaded_document"
    ext = Path(filename).suffix.lower()
    mime_type = file.content_type or "application/octet-stream"

    if ext in DISALLOWED_EXTENSIONS:
        raise InvalidUploadError("unsupported_file_type")

    content = file.file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise InvalidUploadError("file_too_large")

    doc_id = str(uuid.uuid4())
    target_name = f"{doc_id}{ext}"
    target_path = UPLOAD_DIR / target_name

    with target_path.open("wb") as out_f:
        out_f.write(content)

    # STEP 2: Extract Metadata & Ingest Chunks
    adapter = UploadFileAdapter(filename, content)
    bundles = _ingestion_service.ingest_files([adapter], uploaded_by=user_id)
    
    extracted_text = ""
    chunks_count = 0
    doc_type = DocumentType.GENERIC
    if bundles:
        bundle = bundles[0]
        doc_type = bundle.document.doc_type
        chunks_count = len(bundle.chunks)
        extracted_text = "\n\n".join(ch.text for ch in bundle.chunks if ch.text)
        # Persist chunks
        _doc_repo.save_chunks(bundle.chunks)

    # Resolve target run
    resolved_db_id: Optional[int] = None
    target_brief: Optional[InvestmentBrief] = None

    if run_uuid:
        run_str = str(run_uuid).strip()
        if run_str.isdigit():
            resolved_db_id = int(run_str)
            target_brief = _brief_repo.load_brief(resolved_db_id)
        else:
            live_info = _run_repo.get_run(run_str)
            if live_info and live_info.get("db_id"):
                try:
                    resolved_db_id = int(live_info["db_id"])
                    target_brief = _brief_repo.load_brief(resolved_db_id)
                except Exception:
                    pass

    # STEP 3 & STEP 4: Create Evidence Record & Run Trust Engine
    trust_breakdown = _calculate_trust_engine_scores(
        filename=filename,
        doc_type=doc_type,
        text_content=extracted_text,
        chunks_count=chunks_count,
        brief=target_brief,
    )

    # STEP 5: Generate Signals
    evidence_items, signals, evidence_status, decision_impact = _extract_signals_and_evidence(
        filename=filename,
        text_content=extracted_text,
        trust=trust_breakdown,
        brief=target_brief,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_trail = [
        f"Document ingested: {filename} at {now_iso}",
        f"Trust Engine evaluated score: {trust_breakdown.final_trust_score}/100",
        f"Signals detected: {len(signals)} items",
        f"Published to Evidence Workspace: {now_iso}",
    ]

    evidence_record = UploadedEvidenceRecord(
        id=doc_id,
        filename=filename,
        source=f"Document Ingestion Pipeline ({filename})",
        upload_date=now_iso,
        file_type=ext.lstrip(".").upper() or "DOCUMENT",
        uploader=user_id or "Pilot Reviewer",
        trust_breakdown=trust_breakdown,
        evidence_status=evidence_status,
        evidence_items=evidence_items,
        signals_generated=signals,
        decision_impact=decision_impact,
        audit_trail=audit_trail,
        raw_summary=extracted_text[:400] if extracted_text else "No extractable text found in document.",
    )

    # STEP 6: Persist Document Record & Update Run Brief in Database
    doc = Document(
        id=doc_id,
        filename=filename,
        mime_type=mime_type,
        doc_type=doc_type,
        uploaded_by=user_id,
        uploaded_at=datetime.now(timezone.utc),
        source_type="document",
        metadata={
            "run_id": resolved_db_id,
            "trust_score": trust_breakdown.final_trust_score,
            "signals": signals,
        },
    )
    _doc_repo.save_document(resolved_db_id, doc)

    # STEP 7: Publish into Evidence & Reports Workspace
    if resolved_db_id and target_brief:
        # Append source attribution
        new_source = SourceAttribution(
            title=f"Uploaded Document: {filename}",
            url=f"/uploads/{target_name}",
            snippet=extracted_text[:250] if extracted_text else f"Uploaded dossier component {filename}",
            relevance=0.95,
            source_type="document",
            confidence_score=round(trust_breakdown.final_trust_score / 100.0, 2),
        )
        target_brief.sources.append(new_source)
        
        # Append evidence record
        target_brief.uploaded_evidence.append(evidence_record)
        
        # Re-save brief to database so Reports and Evidence workspaces see it immediately
        try:
            _brief_repo.update_brief(resolved_db_id, target_brief)
        except Exception as exc:
            logger.warning(f"Could not update brief in SQLite for run {resolved_db_id}: {exc}")

    logger.info(
        "document_pipeline_completed",
        extra={
            "doc_id": doc_id,
            "filename": filename,
            "resolved_db_id": resolved_db_id,
            "trust_score": trust_breakdown.final_trust_score,
            "signals_count": len(signals),
        },
    )

    return {
        "id": doc_id,
        "name": filename,
        "url": f"/uploads/{target_name}",
        "trustScore": trust_breakdown.final_trust_score,
        "evidenceStatus": evidence_status,
        "signals": signals,
    }
