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

_log = logging.getLogger(__name__)

_orchestrator: IntelligenceOrchestrator | None = None
_signals_orchestrator = SignalsOrchestrator()
_repo = IntelligenceRepository()
_run_repo = RunRepository()


def get_orchestrator() -> IntelligenceOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IntelligenceOrchestrator()
    return _orchestrator


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
    """
    run_id = str(uuid.uuid4())
    # Persist run record so it survives restarts
    _run_repo.create_run(run_id, status="running", user_id=user_id)
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
            _log.warning("Orchestrator live analysis failed (%s) — activating offline demo fallback.", exc)
            try:
                brief = _get_offline_fallback_brief(founder, startup)
                db_id = _repo.save_brief(brief, user_id=owner_id, org_id=org_id)
                _run_repo.update_run_completed(rid, db_id=db_id)
                _sync_assessment(assessment_id, document_ids, db_id, brief, org_id=org_id)
                _log.info("Orchestrator: offline fallback complete — run_id=%s db_id=%s", rid, db_id)
            except Exception as fallback_exc:  # noqa: BLE001
                _log.exception("Orchestrator fallback also failed: %s", fallback_exc)
                _run_repo.update_run_failed(rid, error_message=str(exc))
                _mark_assessment_failed(assessment_id, str(exc))

    t = threading.Thread(target=_worker, args=(run_id, founder, startup, user_id), daemon=True)
    t.start()
    return run_id


def _sync_assessment(
    assessment_id: str | None,
    document_ids: list[str] | None,
    db_id: int,
    brief: InvestmentBrief | None,
    *,
    org_id: str | None = None,
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

        trust_score: float | None = None
        decision: dict = {}
        signals: list[str] = []
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

        AssessmentRepository().update_outputs(
            assessment_id,
            trust_score=trust_score,
            signals=signals or None,
            decision=decision or None,
            status=AssessmentStatus.COMPLETE,
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


def _get_offline_fallback_brief(founder: str, startup: str) -> InvestmentBrief:
    """Return a demo brief adapted from the OSTX seed dataset for offline mode.

    Picks the closest existing demo run from the DB (by sector/stage heuristic)
    and patches the founder/startup name + prepends the offline-mode banner to
    the executive_summary so the IC workflow can continue end-to-end.
    """
    import copy

    # Pull all completed runs; prefer the INVEST-grade one as the default demo.
    recent = _repo.recent_runs(limit=50)
    demo_run: dict | None = None
    for row in recent:
        # Prefer AgriNova Malawi (INVEST) as the flagship fallback demo.
        if "agrinova" in str(row.get("startup_name", "")).lower():
            demo_run = dict(row)
            break
    if demo_run is None and recent:
        demo_run = dict(recent[0])

    if demo_run is not None:
        db_id = demo_run.get("id")
        base_brief = _repo.load_brief(db_id) if db_id else None
    else:
        base_brief = None

    if base_brief is None:
        # Last-resort: import fresh from seed module
        from scripts.seed_demo_data import build_agrinova_malawi_brief  # noqa: PLC0415
        base_brief = build_agrinova_malawi_brief()

    # Deep-copy and patch names + offline banner
    brief_data = base_brief.model_dump(mode="json")
    brief_data["founder_name"] = founder
    brief_data["startup_name"] = startup
    offline_banner = (
        "⚡ Demo Analysis Generated — Offline Intelligence Mode Active. "
        "Live OSINT and LLM APIs are currently unavailable. "
        "The following analysis is based on the OSTX Validation Dataset template.\n\n"
    )
    brief_data["executive_summary"] = offline_banner + str(brief_data.get("executive_summary", ""))
    return InvestmentBrief.model_validate(brief_data)



def _resolve_run_record(run_id: str, user_id: str | None = None) -> Optional[Dict[str, Any]]:
    """Resolve a live api_runs row, including shared demo rows (user_id NULL)."""
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
        row = _repo.get_run(db_id, user_id=user_id)
        if row is None and user_id is not None:
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


def get_run_status(run_id: str, user_id: str | None = None) -> Optional[Dict[str, Any]]:
    return _resolve_run_record(run_id, user_id=user_id)


def get_brief_for_run(run_id: str, user_id: str | None = None) -> Optional[InvestmentBrief | dict]:
    info = _resolve_run_record(run_id, user_id=user_id)
    if not info:
        return None
    db_id = info.get("db_id")
    if db_id:
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
        _log.warning("Ask IC live failed (%s) — returning demo mode response.", exc)
        from .demo_chat import demo_ask_ic_answer

        return demo_ask_ic_answer(brief, question)


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
        _log.warning("Ask Signals live failed (%s) — returning demo mode response.", exc)
        from .demo_chat import demo_ask_signals_answer

        return demo_ask_signals_answer(case, signals, question)
