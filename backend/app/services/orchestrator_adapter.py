from __future__ import annotations

import threading
import uuid
import logging
from typing import Dict, Any, Optional

from kulima.agents.orchestrator import IntelligenceOrchestrator
from kulima.core.audit import record_event
from kulima.core.cases.adapters import from_investment_brief
from kulima.db import IntelligenceRepository
from kulima.models import InvestmentBrief
from kulima.signals.ask_signals import answer_ask_signals_question
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.signals_summary import build_domain_overviews
from .run_repository import RunRepository

# Phase 4 Enterprise: Import job system for durable processing
try:
    from kulima.core.jobs.models import Job, JobKind, JobStatus
    from kulima.core.jobs.repository import JobRepository
    from kulima.core.cases.service import CaseService
    from kulima.core.cases.models import CaseLifecycleStatus
    from kulima.core.orgs.models import Role
    JOBS_AVAILABLE = True
except ImportError:
    JOBS_AVAILABLE = False

_log = logging.getLogger(__name__)

_orchestrator: IntelligenceOrchestrator | None = None
_signals_orchestrator = SignalsOrchestrator()
_repo = IntelligenceRepository()
_run_repo = RunRepository()

# Phase 4 Enterprise: Job and case services
_job_repo: JobRepository | None = None
_case_service: CaseService | None = None


def get_orchestrator() -> IntelligenceOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IntelligenceOrchestrator()
    return _orchestrator


def is_openai_unavailable(exc: BaseException) -> bool:
    """Identify unavailable OpenAI requests through wrapped pipeline errors."""
    current: BaseException | None = exc
    seen: set[int] = set()
    unavailable_statuses = {401, 408, 429, 500, 502, 503, 504}
    unavailable_names = {
        "apiconnectionerror",
        "apiauthenticationerror",
        "authenticationerror",
        "ratelimiterror",
        "apitimeouterror",
        "internalservererror",
    }
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        error_name = type(current).__name__.lower()
        error_module = type(current).__module__.lower()
        status_code = getattr(current, "status_code", None)
        error_code = str(getattr(current, "code", "") or "").lower()
        message = str(current).lower()
        if (
            error_name in unavailable_names
            or (error_module.startswith("openai") and status_code in unavailable_statuses)
            or status_code in unavailable_statuses
            or error_code in {"insufficient_quota", "rate_limit_exceeded"}
            or "insufficient_quota" in message
            # Missing/invalid credentials surface as a plain RuntimeError from
            # the LLM client rather than an openai SDK error — the deployment
            # still cannot complete an LLM stage, so Document Intelligence
            # Mode must engage instead of failing the whole run.
            or "missing openai credentials" in message
            or ("openai_api_key" in message and "environment variable" in message)
        ):
            return True
        current = current.__cause__ or current.__context__ or getattr(current, "cause", None)
    return False


def build_document_intelligence_fallback(
    founder: str,
    startup: str,
    *,
    user_id: str | None,
    org_id: str | None,
    assessment_id: str | None,
    sector_hint: str,
    research_bundle: dict[str, list] | None,
    failure: BaseException,
) -> tuple[InvestmentBrief, dict[str, Any], list[str]]:
    """Build a cautious brief only from this assessment's documents and research."""
    from statistics import mean

    from kulima.core.assessment.repository import AssessmentRepository
    from kulima.core.cases.adapters import from_investment_brief
    from kulima.core.cases.service import ASSESSMENT_TO_WORKSPACE
    from kulima.core.documents.models import Document
    from kulima.models import (
        ConfidenceLevel,
        Recommendation,
        SourceAttribution,
        TrustEdge,
        TrustGraph,
        TrustNode,
        TrustScoreBreakdown,
        UploadedEvidenceRecord,
    )
    from kulima.research import ResearchEngine
    from kulima.scoring import clamp

    bundle = research_bundle or {}
    external_sources = [
        source
        for group in bundle.values()
        if isinstance(group, list)
        for source in group
        if isinstance(source, SourceAttribution)
    ]
    context = (
        AssessmentRepository().get(assessment_id, user_id=user_id, org_id=org_id)
        if assessment_id
        else None
    )
    documents = list(context.uploaded_documents) if context else []
    document_sources = [
        SourceAttribution(
            title=document.name,
            url=document.url or f"document://{document.id}",
            snippet=document.raw_summary or " ".join(document.evidence_items),
            relevance=1.0,
            source_type="document",
            confidence_score=clamp((document.trust_score or 50.0) / 100, 0.05, 0.95),
        )
        for document in documents
    ]
    sources = ResearchEngine._dedupe(document_sources + external_sources, limit=100)
    document_scores = [float(doc.trust_score) for doc in documents if doc.trust_score is not None]
    trust_score = round(mean(document_scores), 1) if document_scores else 0.0
    extracted_text = context.extracted_text if context else ""
    evidence_text = " ".join(
        [extracted_text]
        + [doc.raw_summary for doc in documents]
        + [snippet for snippet in (source.snippet for source in external_sources)]
    ).lower()
    risk_terms = ("fraud", "lawsuit", "litigation", "sanction", "misconduct", "breach", "non-compliance")
    risk_markers = [term for term in risk_terms if term in evidence_text]
    risk_score = clamp(42 + len(risk_markers) * 8 + max(0, 50 - trust_score) * 0.35, 0, 85)
    evidence_coverage = min(len(documents), 5) * 10 + min(len(external_sources), 10) * 2
    startup_score = clamp(trust_score, 0, 100)
    founder_score = clamp(25 + min(len(bundle.get("founder", [])), 5) * 4, 0, 45)
    market_score = clamp(25 + min(len(bundle.get("market", [])), 8) * 4, 0, 57)
    investment_readiness = clamp(evidence_coverage, 0, 50)
    overall_score = round(clamp(
        founder_score * 0.20
        + startup_score * 0.25
        + market_score * 0.20
        + trust_score * 0.20
        + investment_readiness * 0.15,
        0,
        100,
    ), 1)
    entity_name = (
        (context.organization_name or context.startup_name) if context else startup
    ) or startup or "Assessment"
    assessment_type = (
        getattr(context.assessment_type, "value", str(context.assessment_type))
        if context
        else "assessment"
    )
    evidence_gaps = []
    if not documents:
        evidence_gaps.append("No uploaded documents were available to the fallback analysis.")
    if not external_sources:
        evidence_gaps.append("No external research sources were returned; independent validation is still required.")
    if not document_scores:
        evidence_gaps.append("No document trust scores were available.")
    if risk_markers:
        evidence_gaps.append("Potential risk language requires human verification: " + ", ".join(risk_markers) + ".")

    uploaded_evidence = []
    for document in documents:
        breakdown = TrustScoreBreakdown.model_validate(document.trust_breakdown or {})
        uploaded_evidence.append(UploadedEvidenceRecord(
            id=document.id,
            filename=document.name,
            source=f"Document Ingestion Pipeline ({document.name})",
            upload_date=document.upload_date,
            file_type=document.file_type or "DOCUMENT",
            uploader=user_id or "Assessment Reviewer",
            trust_breakdown=breakdown,
            evidence_status=document.evidence_status or "INSUFFICIENT_EVIDENCE",
            evidence_items=list(document.evidence_items),
            signals_generated=list(document.signals),
            decision_impact=document.decision_impact or "Supporting evidence; manual review required.",
            audit_trail=["Extracted and scored by the local document intelligence pipeline."],
            raw_summary=document.raw_summary,
        ))

    source_lines = [f"{source.title}: {source.snippet[:220]}" for source in sources[:8]]
    research_summary = (
        f"Document Intelligence Mode completed for {entity_name}: "
        f"{len(documents)} uploaded document(s), {len(external_sources)} external research source(s)."
    )
    if source_lines:
        research_summary += " Research: " + " | ".join(source_lines)
    if evidence_gaps:
        research_summary += " Evidence gaps: " + " ".join(evidence_gaps)

    graph_nodes = [
        TrustNode(id="founder", label=founder or "Founder / lead not provided", node_type="founder", weight=1.0),
        TrustNode(id="startup", label=entity_name, node_type="company", weight=1.0),
    ]
    graph_edges = [TrustEdge(source="founder", target="startup", relation="assessment_subject")]
    brief = InvestmentBrief(
        founder_name=founder or (context.founder_name if context else "Not provided"),
        startup_name=entity_name,
        sector=(context.sector if context else "") or sector_hint,
        geography=context.country if context else "",
        stage="Not assessed",
        executive_summary=(
            "OpenAI is unavailable. Document Intelligence Mode used uploaded-document extraction, "
            "document trust scores, available Tavily sources, and deterministic signals. "
            "This is a preliminary evidence summary, not an AI-validated investment recommendation."
        ),
        founder_assessment=(
            "Founder identity came from the Assessment Context. OpenAI-based founder credibility "
            "analysis was unavailable; verify identity and track record independently."
        ),
        startup_assessment=(
            f"Rule-based intake includes {len(documents)} document(s) for the {assessment_type} assessment. "
            "Claims are limited to extracted document text and recorded metadata."
        ),
        market_assessment=(
            f"{len(external_sources)} external research source(s) were available. "
            "Market sizing and competitive claims require analyst verification."
        ),
        risk_assessment=(
            f"Rule-based risk score: {risk_score:.0f}/100. "
            + ("Potential risk terms found in evidence: " + ", ".join(risk_markers) + ". " if risk_markers else "No explicit high-risk terms were detected in the available text. ")
            + "This does not replace a full diligence review."
        ),
        investment_recommendation="Review Required — OpenAI was unavailable; do not make an investment decision from this fallback alone.",
        next_steps=[
            "Verify primary operating and financial claims with the organization.",
            "Review every uploaded document and source citation.",
            "Repeat the full AI-assisted assessment when OpenAI is available.",
        ],
        recommendation=Recommendation.REVIEW_REQUIRED,
        overall_score=overall_score,
        founder_score=founder_score,
        startup_score=startup_score,
        market_score=market_score,
        trust_score=trust_score,
        risk_score=risk_score,
        growth_potential=0.0,
        investment_readiness=investment_readiness,
        confidence=0.30,
        confidence_level=ConfidenceLevel.LOW,
        red_flags=[],
        trust_graph=TrustGraph(
            nodes=graph_nodes,
            edges=graph_edges,
            trust_score=trust_score,
            explanation="Rule-based document trust aggregate; AI relationship inference was not run.",
        ),
        sources=sources,
        explainability=[
            "OpenAI unavailable; deterministic Document Intelligence Mode was used.",
            f"Trust score is the mean of {len(document_scores)} stored document trust score(s).",
            f"Research sources: {len(external_sources)}; uploaded documents: {len(documents)}.",
            "Recommendation is Review Required until an analyst verifies the evidence.",
        ],
        uploaded_evidence=uploaded_evidence,
    )
    workspace_type = (
        ASSESSMENT_TO_WORKSPACE.get(context.assessment_type)
        if context
        else None
    )
    case = from_investment_brief(
        brief,
        case_id=assessment_id or f"fallback-{user_id or 'local'}",
        workspace_type=workspace_type,
    )
    generated_signals = _signals_orchestrator.generate(case, sort=True)
    signal_titles = [
        f"{signal.category.value}: {signal.title} ({signal.direction})"
        for signal in generated_signals
    ]
    brief.explainability.append(f"Deterministic rule engine generated {len(signal_titles)} domain signal(s).")

    research_payload = {
        "status": "completed",
        "mode": "document_intelligence",
        "openaiStatus": "unavailable",
        "message": "OpenAI unavailable — Document Intelligence Mode active.",
        "summary": research_summary,
        "progress": 100,
        "sourceCount": len(external_sources),
        "documentCount": len(documents),
        "sources": [source.model_dump(mode="json") for source in sources],
        "tavily_findings": [source.snippet for source in external_sources if source.snippet],
        "entities": [{"name": entity_name, "label": assessment_type}],
        "evidenceGaps": evidence_gaps,
        "failureType": type(failure).__name__,
    }
    return brief, research_payload, signal_titles


def start_intelligence_run(
    founder: str,
    startup: str,
    user_id: str | None = None,
    *,
    assessment_id: str | None = None,
    document_ids: list[str] | None = None,
    sector_hint: str = "",
    org_id: str | None = None,
) -> str:
    """Start the intelligence run (Tavily OSINT + agents).

    The keyword arguments are additive: callers that only pass founder/startup
    behave exactly as before. When ``assessment_id`` is supplied the run is
    grounded in the shared Assessment Context — extracted sector sharpens the
    Tavily market queries, intake documents are bound to the stored run, and
    pipeline outputs (trust, signals, decision) are written back onto the
    context when the run completes.

    Enterprise Trust: ``org_id`` binds the run to its workspace and the
    external-research trigger is recorded in the audit log (Phase 4).

    Phase 4 Enterprise: When job system is available, enqueues durable jobs
    instead of spawning daemon threads for better restart recovery.
    """
    run_id = str(uuid.uuid4())
    # Persist run record so it survives restarts
    _run_repo.create_run(run_id, status="running", user_id=user_id, org_id=org_id)
    # Audit: an external (Tavily) research pass is about to be triggered. The
    # payload never includes document content — only public metadata fields.
    record_event(
        "research.triggered",
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        assessment_id=assessment_id,
        metadata={"provider": "tavily", "founder": founder, "startup": startup, "mode": "metadata_only"},
    )

    # Phase 4 Enterprise: Use job queue if available, otherwise fall back to threads
    if JOBS_AVAILABLE and assessment_id and org_id:
        return _enqueue_intelligence_job(
            run_id, founder, startup, user_id, assessment_id, document_ids, sector_hint, org_id
        )

    # Legacy: Use daemon thread for backward compatibility
    def _worker(rid: str, founder: str, startup: str, owner_id: str | None) -> None:
        try:
            _log.info("Orchestrator: starting analysis for %s / %s", founder, startup)
            orchestrator = get_orchestrator()
            brief: InvestmentBrief = orchestrator.analyze(
                founder, startup, user_id=owner_id, sector_hint=sector_hint
            )
            # Persist to DB (synchronous)
            db_id = _repo.save_brief(brief, user_id=owner_id, org_id=org_id)
            # Mark run completed in persistent store
            _run_repo.update_run_completed(rid, db_id=db_id)
            _sync_assessment(assessment_id, document_ids, db_id, brief, org_id=org_id)
            _log.info("Orchestrator: analysis complete — run_id=%s db_id=%s", rid, db_id)
        except Exception as exc:  # noqa: BLE001
            # Reliability contract: the workflow must NEVER dead-end because of
            # OpenAI / Tavily / network / key failures. Engage deterministic
            # Document Intelligence Mode for ANY pipeline failure — the brief
            # is built only from this assessment's own documents, trust layer,
            # and whatever research succeeded. Demo seed data is never used.
            _log.warning("Orchestrator live analysis failed (%s) — activating Document Intelligence Mode.", exc)
            try:
                brief, research_payload, fallback_signal_titles = build_document_intelligence_fallback(
                    founder,
                    startup,
                    user_id=owner_id,
                    org_id=org_id,
                    assessment_id=assessment_id,
                    sector_hint=sector_hint,
                    research_bundle=None,
                    failure=exc,
                )
                db_id = _repo.save_brief(brief, user_id=owner_id, org_id=org_id)
                _run_repo.update_run_completed(rid, db_id=db_id)
                _sync_assessment(
                    assessment_id,
                    document_ids,
                    db_id,
                    brief,
                    org_id=org_id,
                    research=research_payload,
                    generated_signal_titles=fallback_signal_titles,
                )
                _log.info("Orchestrator: Document Intelligence fallback complete — run_id=%s db_id=%s", rid, db_id)
            except Exception as fallback_exc:  # noqa: BLE001
                _log.exception("Orchestrator Document Intelligence fallback also failed: %s", fallback_exc)
                _run_repo.update_run_failed(rid, error_message=str(exc))
                _mark_assessment_failed(assessment_id, str(exc))

    t = threading.Thread(target=_worker, args=(run_id, founder, startup, user_id), daemon=True)
    t.start()
    return run_id


def _enqueue_intelligence_job(
    run_id: str,
    founder: str,
    startup: str,
    user_id: str | None,
    assessment_id: str,
    document_ids: list[str] | None,
    sector_hint: str,
    org_id: str,
) -> str:
    """Phase 4 Enterprise: Enqueue intelligence run as durable job."""
    global _job_repo, _case_service
    if _job_repo is None:
        _job_repo = JobRepository()
    if _case_service is None:
        _case_service = CaseService()

    # Get or create case for this assessment
    case = _case_service.get_case_by_assessment(assessment_id, org_id=org_id)
    if case is None:
        # Create case from assessment context
        from kulima.core.assessment.repository import AssessmentRepository
        from kulima.core.assessment.models import AssessmentType
        from kulima.core.cases.models import CaseSubject

        ctx = AssessmentRepository().get(assessment_id, org_id=org_id)
        if ctx:
            entity_name = ctx.extraction.display_entity() if ctx.extraction else ""
            subject = CaseSubject(
                name=entity_name or startup,
                secondary_name=founder,
                sector=ctx.sector or sector_hint,
                region=ctx.country,
            )
            case = _case_service.create_case(
                assessment_id=assessment_id,
                assessment_type=ctx.assessment_type,
                subject=subject,
                org_id=org_id,
                created_by=user_id or "system",
            )
            # Transition to PROCESSING
            from kulima.core.orgs.models import Role
            _case_service.transition_lifecycle(
                case.id, CaseLifecycleStatus.PROCESSING, user_id or "system", Role.ADMIN, org_id=org_id
            )

    if case is None:
        _log.warning("Could not create case for assessment %s, falling back to thread", assessment_id)
        # Fall back to thread-based execution
        return start_intelligence_run(
            founder, startup, user_id,
            assessment_id=assessment_id,
            document_ids=document_ids,
            sector_hint=sector_hint,
            org_id=org_id,
        )

    # Enqueue research job
    from datetime import datetime, timezone
    import hashlib

    idempotency_key = hashlib.sha256(
        f"{case.id}:{founder}:{startup}:{sector_hint}".encode()
    ).hexdigest()

    # Check if job already exists
    existing_job = _job_repo.get_by_idempotency_key(idempotency_key)
    if existing_job and existing_job.status in (JobStatus.SUCCEEDED, JobStatus.RUNNING):
        _log.info("Job already exists with idempotency key %s, status %s", idempotency_key, existing_job.status.value)
        return run_id

    # Create and enqueue job
    job = Job(
        id=str(uuid.uuid4()),
        case_id=case.id,
        kind=JobKind.RESEARCH,
        status=JobStatus.QUEUED,
        payload={
            "founder": founder,
            "startup": startup,
            "sector_hint": sector_hint,
            "user_id": user_id,
            "org_id": org_id,
            "assessment_id": assessment_id,
            "document_ids": document_ids,
            "run_id": run_id,
        },
        idempotency_key=idempotency_key,
        created_at=datetime.now(timezone.utc),
    )

    _job_repo.enqueue(job)
    _log.info("Enqueued intelligence job %s for case %s", job.id, case.id)

    return run_id


def _sync_assessment(
    assessment_id: str | None,
    document_ids: list[str] | None,
    db_id: int,
    brief: InvestmentBrief | None,
    *,
    org_id: str | None = None,
    research: dict[str, Any] | None = None,
    generated_signal_titles: list[str] | None = None,
) -> None:
    """Bind intake documents + pipeline outputs back to the Assessment Context.

    Best-effort: failures are logged and never affect the completed run.
    """
    try:
        if document_ids:
            from kulima.core.documents.repository import DocumentRepository

            doc_repo = DocumentRepository()
            doc_repo.link_documents_to_run(document_ids, db_id)
            if assessment_id:
                doc_repo.link_documents_to_assessment(document_ids, assessment_id, org_id=org_id)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Could not link intake documents to run %s: %s", db_id, exc)

    if not assessment_id:
        return
    try:
        from kulima.core.assessment.models import AssessmentStatus
        from kulima.core.assessment.repository import AssessmentRepository
        from kulima.models import UploadedEvidenceRecord, TrustScoreBreakdown, SourceAttribution
        from datetime import datetime, timezone

        ctx = AssessmentRepository().get(assessment_id, org_id=org_id)

        trust_score: float | None = None
        decision: dict = {}
        signals: list[str] = []

        if ctx and brief is not None:
            existing_doc_ids = {r.id for r in getattr(brief, "uploaded_evidence", []) or []}
            brief_updated = False
            for doc in ctx.uploaded_documents:
                # Add signals from document
                if doc.signals:
                    signals.extend(doc.signals)
                # Bridge to brief.uploaded_evidence
                if doc.id not in existing_doc_ids:
                    tb = TrustScoreBreakdown()
                    if doc.trust_breakdown:
                        try:
                            tb = TrustScoreBreakdown.model_validate(doc.trust_breakdown)
                        except Exception:
                            pass
                    evidence_record = UploadedEvidenceRecord(
                        id=doc.id,
                        filename=doc.name,
                        source=f"Document Ingestion Pipeline ({doc.name})",
                        upload_date=doc.upload_date or datetime.now(timezone.utc).isoformat(),
                        file_type=doc.file_type or "DOCUMENT",
                        uploader=ctx.created_by or "Assessment Reviewer",
                        trust_breakdown=tb,
                        evidence_status=doc.evidence_status or "CORROBORATED",
                        evidence_items=list(doc.evidence_items or []),
                        signals_generated=list(doc.signals or []),
                        decision_impact=doc.decision_impact or "Supporting Evidence Attribution",
                        audit_trail=[f"Document attached to run: {doc.name}"],
                        raw_summary=doc.raw_summary or "",
                    )
                    brief.uploaded_evidence.append(evidence_record)
                    brief.sources.append(SourceAttribution(
                        title=f"Uploaded Document: {doc.name}",
                        url=doc.url or f"/uploads/{doc.id}",
                        snippet=doc.raw_summary[:250] if doc.raw_summary else f"Uploaded dossier component {doc.name}",
                        relevance=0.95,
                        source_type="document",
                        confidence_score=round((doc.trust_score or 75.0) / 100.0, 2),
                    ))
                    brief_updated = True
            if brief_updated:
                try:
                    _repo.update_brief(db_id, brief)
                except Exception as b_err:
                    _log.warning("Could not persist bridged evidence to brief: %s", b_err)

        if brief is not None:
            trust_score = float(brief.trust_score or 0.0) or None
            decision = {
                "recommendation": getattr(brief.recommendation, "value", str(brief.recommendation)),
                "overallScore": brief.overall_score,
                "riskScore": brief.risk_score,
                "confidence": brief.confidence,
            }
            for record in getattr(brief, "uploaded_evidence", []) or []:
                signals.extend(getattr(record, "signals_generated", []) or [])
        signals.extend(generated_signal_titles or [])

        # Deduplicate signals
        seen_sig = set()
        dedup_signals = []
        for s in signals:
            if s and s not in seen_sig:
                seen_sig.add(s)
                dedup_signals.append(s)

        AssessmentRepository().update_outputs(
            assessment_id,
            trust_score=trust_score,
            signals=dedup_signals or None,
            decision=decision or None,
            status=AssessmentStatus.COMPLETE,
            research=research or {
                "status": "completed",
                "mode": "ai_assisted",
                "sourceCount": len(brief.sources) if brief else 0,
                "documentCount": len(documents) if ctx else 0,
                "sources": [source.model_dump(mode="json") for source in brief.sources] if brief else [],
                "tavily_findings": [source.snippet for source in brief.sources if source.snippet] if brief else [],
                "entities": [{"name": ctx.organization_name or ctx.startup_name, "label": ctx.type_label()}] if ctx else [],
                "summary": brief.executive_summary if brief else "Research completed.",
                "progress": 100,
            },
        )

        record_event(
            "research.completed",
            org_id=org_id,
            run_id=db_id,
            assessment_id=assessment_id,
            metadata={
                "mode": (research or {}).get("mode", "ai_assisted"),
                "sources": len((research or {}).get("sources", brief.sources if brief else [])),
            },
        )

        # Audit (Phase 4): signals + decision generation per assessment.
        if signals:
            record_event(
                "signals.generated",
                org_id=org_id,
                run_id=db_id,
                assessment_id=assessment_id,
                metadata={"count": len(signals), "sample": signals[:5]},
            )
        if decision:
            record_event(
                "decision.generated",
                org_id=org_id,
                run_id=db_id,
                assessment_id=assessment_id,
                metadata=decision,
            )
    except Exception as exc:  # noqa: BLE001
        _log.warning("Could not sync assessment %s outputs: %s", assessment_id, exc)


def _mark_assessment_failed(assessment_id: str | None, message: str) -> None:
    if not assessment_id:
        return
    try:
        from kulima.core.assessment.models import AssessmentStatus
        from kulima.core.assessment.repository import AssessmentRepository

        AssessmentRepository().update_outputs(
            assessment_id,
            decision={"error": message},
            status=AssessmentStatus.FAILED,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("Could not mark assessment %s failed: %s", assessment_id, exc)


# NOTE: The legacy OSTX/AgriNova seed-dataset offline fallback was REMOVED
# (reliability phase). Every offline run now uses the deterministic
# Document Intelligence Mode built from the assessment's own documents.



def _resolve_run_record(run_id: str, user_id: str | None = None, org_id: str | None = None) -> Optional[Dict[str, Any]]:
    """Resolve a live api_runs row, including shared demo rows (user_id NULL)."""
    if org_id is not None:
        info = _run_repo.get_run(run_id, org_id=org_id)
    else:
        info = _run_repo.get_run(run_id, user_id=user_id)
        if info is None and user_id is not None:
            legacy = _run_repo.get_run(run_id)
            if legacy is not None and legacy.get("user_id") is None:
                info = legacy
    if info is not None:
        return info

    # Allow Flex/Signals URL sync with stored intelligence run integer IDs.
    if str(run_id).isdigit():
        db_id = int(run_id)
        row = _repo.get_run(db_id, user_id=user_id, org_id=org_id)
        if row is None and org_id is None and user_id is not None:
            legacy_row = _repo.get_run(db_id)
            if legacy_row is not None and legacy_row.get("user_id") is None:
                row = legacy_row
        if row is not None:
            return {
                "run_id": str(run_id),
                "status": "completed",
                "created_at": row.get("created_at"),
                "completed_at": row.get("created_at"),
                "db_id": db_id,
                "error_message": None,
                "user_id": row.get("user_id"),
            }
    return None


def get_run_status(run_id: str, user_id: str | None = None, org_id: str | None = None) -> Optional[Dict[str, Any]]:
    return _resolve_run_record(run_id, user_id=user_id, org_id=org_id)


def get_brief_for_run(run_id: str, user_id: str | None = None, org_id: str | None = None) -> Optional[InvestmentBrief | dict]:
    info = _resolve_run_record(run_id, user_id=user_id, org_id=org_id)
    if not info:
        return None
    db_id = info.get("db_id")
    if db_id:
        # Workspace isolation: only load the brief when the stored run belongs
        # to the caller's workspace (or is a shared legacy/demo row).
        row = _repo.get_run(int(db_id), user_id=user_id, org_id=org_id) if org_id is not None or user_id is not None else _repo.get_run(int(db_id))
        if row is None:
            return None
        brief = _repo.load_brief(int(db_id))
        if brief:
            try:
                return brief.model_dump(mode="json")
            except Exception:
                return None
    return None


def ask_ic(
    run_id: str,
    question: str,
    history: list[dict] | None = None,
    user_id: str | None = None,
) -> str:
    # Lazy-load brief
    brief_json = get_brief_for_run(run_id, user_id=user_id)
    if brief_json is None:
        raise RuntimeError("Run not complete or not found")
    # Rehydrate into InvestmentBrief if needed
    from kulima.models import InvestmentBrief

    if isinstance(brief_json, dict):
        brief = InvestmentBrief.model_validate(brief_json)
    else:
        # If already an InvestmentBrief object (unlikely), return directly
        brief = brief_json
    from kulima.ask_ic import answer_ask_ic_question

    # Ground Ask IC in the shared Assessment Context (Step 9): assessment type,
    # organisation, founder, uploaded documents, trust score, and the nine
    # domain signals — without asking the user again. Best-effort: legacy runs
    # without a context behave exactly as before.
    assessment_context = None
    domain_overviews = None
    try:
        from .assessment_adapter import resolve_assessment_for_brief, serialize_context

        ctx = resolve_assessment_for_brief(
            brief.founder_name, brief.startup_name, run_id=run_id, user_id=user_id
        )
        if ctx is not None:
            assessment_context = serialize_context(ctx)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Ask IC assessment grounding unavailable: %s", exc)

    try:
        case = from_investment_brief(brief, case_id=str(run_id or brief.startup_name))
        domain_overviews = build_domain_overviews(_signals_orchestrator.generate(case, sort=True))
    except Exception as exc:  # noqa: BLE001
        _log.warning("Ask IC domain signal grounding unavailable: %s", exc)

    try:
        return answer_ask_ic_question(
            brief,
            question,
            history,
            run_id=None,
            user_id=user_id,
            assessment_context=assessment_context,
            domain_overviews=domain_overviews,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("Ask IC live failed (%s) — answering from stored assessment data.", exc)
        from .demo_chat import doc_intelligence_ask_ic_answer

        return doc_intelligence_ask_ic_answer(
            brief,
            question,
            assessment_context=assessment_context,
        )


def ask_signals(
    run_id: str,
    question: str,
    history: list[dict] | None = None,
    user_id: str | None = None,
) -> str:
    # Signals handler mirrors ask_ic but routes to signals logic.
    # Rebuild the Case envelope expected by the SIGNALS analyst from the
    # stored InvestmentBrief without changing the signal methodology.
    brief_json = get_brief_for_run(run_id, user_id=user_id)
    if brief_json is None:
        raise RuntimeError("Run not complete or not found")

    if isinstance(brief_json, dict):
        brief = InvestmentBrief.model_validate(brief_json)
    else:
        brief = brief_json

    case = from_investment_brief(brief, case_id=run_id)
    signals = _signals_orchestrator.generate(case, sort=True)
    try:
        return answer_ask_signals_question(case, signals, question, history, user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Ask Signals live failed (%s) — answering from stored signals and evidence.", exc)
        from .demo_chat import doc_intelligence_ask_signals_answer

        return doc_intelligence_ask_signals_answer(case, signals, question)
