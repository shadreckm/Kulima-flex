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

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB — aligned with proxy and frontend limits
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
    all_uploaded_count: int = 0,
) -> TrustScoreBreakdown:
    """Deterministic, transparent Trust Engine score calculation.

    Scores vary naturally based on:
    - File type and naming signals (authority indicators)
    - Document content density and structured claim presence
    - Corroboration against existing brief and other uploaded documents
    - Evidence of third-party verification (auditors, regulators, certifiers)
    - Presence of contradictions or unresolved claims
    - Volume of uploaded sources (multi-document corroboration bonus)
    """
    ext = Path(filename).suffix.lower()
    name_lower = filename.lower()
    text_lower = text_content.lower() if text_content else ""
    text_len = len(text_content.strip()) if text_content else 0

    # ── 1. SOURCE RELIABILITY (35% weight) ──────────────────────────────────
    # Tiered by document authority: audited financials > board minutes > models
    # > pitch decks > program reports > surveys > generic documents.
    has_audit_ref = any(k in text_lower for k in ("audited", "audit opinion", "deloitte", "pwc", "ey ", "kpmg", "ernst & young", "grant thornton", "bdo "))
    has_regulatory = any(k in text_lower for k in ("sec filing", "regulatory approval", "central bank", "ministry of finance", "government gazette", "ofac", "rbi", "fca ", "sec "))
    has_legal = any(k in name_lower + text_lower for k in ("legal opinion", "court order", "articles of association", "certificate of incorporation", "deed of trust"))
    has_financials = any(k in text_lower for k in ("revenue", "ebitda", "gross profit", "net income", "balance sheet", "income statement", "cash flow", "arr", "mrr", "roi"))
    has_impact_metrics = any(k in text_lower for k in ("beneficiar", "indicator", "logframe", "m&e", "monitoring", "evaluation", "baseline", "outcome", "impact"))
    is_pitch = doc_type == DocumentType.PITCH_DECK or any(k in name_lower for k in ("pitch", "deck", "investor", "proposal"))
    is_financial_model = doc_type == DocumentType.FINANCIAL_MODEL or any(k in name_lower for k in ("model", "projection", "forecast", "financial"))
    is_audit_doc = any(k in name_lower for k in ("audit", "audited", "statutory", "annual_report", "annual report"))
    is_survey = ext in {".csv", ".xlsx"} or any(k in name_lower for k in ("survey", "data", "dataset", "census"))
    is_board = doc_type == DocumentType.BOARD_MINUTES or any(k in name_lower for k in ("board", "minutes", "resolution", "agm"))

    if has_audit_ref and (is_audit_doc or is_financial_model):
        source_rel = 91.0
        rel_reason = "Third-party audited financial statements — highest institutional authority"
    elif has_regulatory:
        source_rel = 88.0
        rel_reason = "Regulatory filing or government-issued document"
    elif has_legal:
        source_rel = 86.0
        rel_reason = "Legal documentation with formal institutional authority"
    elif is_financial_model and has_financials:
        source_rel = 82.0
        rel_reason = "Financial model with quantitative data — structured and verifiable"
    elif is_board:
        source_rel = 80.0
        rel_reason = "Board minutes / governance documentation"
    elif has_financials and not is_pitch:
        source_rel = 77.0
        rel_reason = "Financial data present in corporate documentation"
    elif is_pitch and has_financials:
        source_rel = 72.0
        rel_reason = "Pitch deck with financial claims — issuer-originated, single-source"
    elif is_pitch:
        source_rel = 62.0
        rel_reason = "Pitch deck — narrative document without independent verification"
    elif has_impact_metrics:
        source_rel = 74.0
        rel_reason = "M&E / program report with structured impact indicators"
    elif is_survey:
        source_rel = 70.0
        rel_reason = "Structured data export — useful but requires external validation"
    elif ext == ".txt":
        source_rel = 55.0
        rel_reason = "Plain text document — unstructured and low verifiability"
    else:
        source_rel = 65.0
        rel_reason = "Generic corporate documentation"

    # ── 2. RECENCY (15% weight) ──────────────────────────────────────────────
    # Look for year markers in the document to infer age.
    # Recent docs (current / prior year) score higher; older docs penalised.
    import re as _re
    current_year = datetime.now(timezone.utc).year
    year_mentions = [int(y) for y in _re.findall(r"\b(20\d{2})\b", text_content or "") if 2010 <= int(y) <= current_year + 1]
    if year_mentions:
        most_recent_year = max(year_mentions)
        age = current_year - most_recent_year
        if age == 0:
            recency_score = 98.0
        elif age == 1:
            recency_score = 88.0
        elif age == 2:
            recency_score = 75.0
        elif age <= 4:
            recency_score = 60.0
        else:
            recency_score = 40.0
    else:
        # No year markers — treat as current (fresh upload)
        recency_score = 90.0

    # ── 3. COMPLETENESS (25% weight) ────────────────────────────────────────
    # Based on text density, chunk count, and presence of structured sections.
    section_keywords = [
        "executive summary", "financial", "market", "team", "risk", "recommendation",
        "objective", "target", "indicator", "budget", "timeline", "methodology",
        "revenue", "cost", "customer", "product", "competition", "traction",
    ]
    section_hits = sum(1 for kw in section_keywords if kw in text_lower)

    if text_len > 8000 and chunks_count >= 6 and section_hits >= 6:
        completeness_score = 93.0
    elif text_len > 4000 and chunks_count >= 4 and section_hits >= 4:
        completeness_score = 82.0
    elif text_len > 2000 and chunks_count >= 2 and section_hits >= 2:
        completeness_score = 68.0
    elif text_len > 500:
        completeness_score = 50.0
    elif text_len > 100:
        completeness_score = 32.0
    else:
        completeness_score = 15.0

    # Bonus: third-party verification and structured tables
    if has_audit_ref:
        completeness_score = min(completeness_score + 7, 100.0)
    if has_impact_metrics:
        completeness_score = min(completeness_score + 4, 100.0)

    # ── 4. CORROBORATION (25% weight) ────────────────────────────────────────
    # Cross-references against existing brief data and other uploaded documents.
    corroboration_score = 50.0  # baseline: no context available

    if brief:
        founder_mentioned = brief.founder_name and brief.founder_name.lower() in text_lower
        startup_mentioned = brief.startup_name and brief.startup_name.lower() in text_lower
        existing_docs = len(getattr(brief, "uploaded_evidence", []) or [])

        if founder_mentioned and startup_mentioned:
            corroboration_score = 85.0
        elif founder_mentioned or startup_mentioned:
            corroboration_score = 72.0
        else:
            corroboration_score = 52.0

        # Multi-document corroboration bonus (each additional doc adds weight)
        total_docs = existing_docs + 1 + all_uploaded_count
        if total_docs >= 3:
            corroboration_score = min(corroboration_score + 10, 100.0)
        elif total_docs == 2:
            corroboration_score = min(corroboration_score + 5, 100.0)
    elif all_uploaded_count >= 1:
        # Multiple docs uploaded together without a brief context
        corroboration_score = 60.0
    else:
        corroboration_score = 48.0

    # ── CONTRADICTION PENALTY ────────────────────────────────────────────────
    # Detect internal contradictions (conflicting numbers, negating claims).
    contradiction_signals = [
        ("not profitable", "profitable"),
        ("no revenue", "revenue of"),
        ("unaudited", "audited"),
        ("no customers", "customers"),
        ("no traction", "strong traction"),
    ]
    contradiction_penalty = 0.0
    for neg, pos in contradiction_signals:
        if neg in text_lower and pos in text_lower:
            contradiction_penalty += 4.0
    contradiction_penalty = min(contradiction_penalty, 15.0)

    # ── WEIGHTED FINAL SCORE ─────────────────────────────────────────────────
    weighted = (
        (source_rel * 0.35)
        + (corroboration_score * 0.25)
        + (recency_score * 0.15)
        + (completeness_score * 0.25)
    ) - contradiction_penalty

    final_score = round(max(10.0, min(99.0, weighted)), 1)

    # Build rationale string
    rationale = (
        f"{rel_reason} (reliability {source_rel:.0f}%). "
        f"Completeness {completeness_score:.0f}% across {chunks_count} sections. "
        f"Recency {recency_score:.0f}% (document year signals). "
        f"Corroboration {corroboration_score:.0f}%."
        + (f" Contradiction penalty applied: -{contradiction_penalty:.0f} pts." if contradiction_penalty > 0 else "")
    )

    return TrustScoreBreakdown(
        source_reliability=source_rel,
        corroboration=corroboration_score,
        recency=recency_score,
        completeness=completeness_score,
        weighted_score=round(weighted + contradiction_penalty, 1),  # pre-penalty for display
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
    all_uploaded_count = len(getattr(target_brief, "uploaded_evidence", []) or []) if target_brief else 0
    trust_breakdown = _calculate_trust_engine_scores(
        filename=filename,
        doc_type=doc_type,
        text_content=extracted_text,
        chunks_count=chunks_count,
        brief=target_brief,
        all_uploaded_count=all_uploaded_count,
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
        # Indicate that this was scored deterministically (Document Intelligence Mode)
        "mode": "document_intelligence",
    }
