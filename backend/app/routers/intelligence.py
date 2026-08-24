from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from kulima.core.cases.adapters import from_investment_brief
from kulima.db import IntelligenceRepository
from kulima.export import (
    build_due_diligence_summary_pdf,
    build_due_diligence_summary_text,
    build_executive_one_pager_pdf,
    build_executive_one_pager_text,
    build_full_ic_report_pdf,
    build_full_ic_report_text,
    build_memo_pdf,
    build_memo_text,
    build_signals_report_pdf,
    build_signals_report_text,
)
from kulima.models import InvestmentBrief
from kulima.portfolio_intelligence import build_pilot_analytics_metrics
from kulima.signals.models import Signal, SignalLevel
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.signals_summary import count_signals_by_level, highest_priority_signals

from ..core.auth import AuthenticatedUser, get_current_user
from ..core.rate_limit import check_rate_limit
from ..schemas.dtos import (
    DecisionSnapshot,
    IntelligenceCreateRequest,
    IntelligenceCreateResponse,
    IntelligenceStatusResponse,
    SignalItem,
    SignalsSummary,
)
from ..services.orchestrator_adapter import get_brief_for_run, get_run_status, start_intelligence_run
from ..services.run_repository import RunRepository

router = APIRouter()

_signals_orchestrator = SignalsOrchestrator()
_brief_repo = IntelligenceRepository()
_live_run_repo = RunRepository()


def _is_demo_run(run_id: str | int) -> bool:
    s = str(run_id).lower()
    return s.startswith("ostx-") or s.startswith("pilot-") or not s.isdigit()

def _load_brief_model(run_id: str | int, user_id: str | None = None) -> InvestmentBrief:
    run_str = str(run_id)
    if run_str.isdigit():
        db_id = int(run_str)
        stored_row = _brief_repo.get_run(db_id, user_id=user_id)
        if stored_row is None and user_id is not None:
            legacy_row = _brief_repo.get_run(db_id)
            if legacy_row is not None and legacy_row.get("user_id") is None:
                stored_row = legacy_row
        if stored_row is not None:
            brief = _brief_repo.load_brief(db_id)
            if brief is not None:
                return brief

    brief_json = get_brief_for_run(run_str, user_id=user_id)
    if brief_json is None:
        raise HTTPException(status_code=404, detail="brief not found")
    return InvestmentBrief.model_validate(brief_json) if isinstance(brief_json, dict) else brief_json


def _report_payload(brief: InvestmentBrief, report_kind: str, fmt: str) -> tuple[bytes, str, str]:
    report_kind = report_kind.lower().strip()
    fmt = fmt.lower().strip()

    if report_kind == "memo":
        if fmt == "pdf":
            return build_memo_pdf(brief), "application/pdf", "pdf"
        return build_memo_text(brief).encode("utf-8"), "text/plain; charset=utf-8", "txt"
    if report_kind == "report":
        if fmt == "pdf":
            return build_full_ic_report_pdf(brief), "application/pdf", "pdf"
        return build_full_ic_report_text(brief).encode("utf-8"), "text/plain; charset=utf-8", "txt"
    if report_kind == "signals":
        if fmt == "pdf":
            return build_signals_report_pdf(brief), "application/pdf", "pdf"
        return build_signals_report_text(brief).encode("utf-8"), "text/plain; charset=utf-8", "txt"
    if report_kind == "due-diligence":
        if fmt == "pdf":
            return build_due_diligence_summary_pdf(brief), "application/pdf", "pdf"
        return build_due_diligence_summary_text(brief).encode("utf-8"), "text/plain; charset=utf-8", "txt"
    if report_kind == "one-pager":
        if fmt == "pdf":
            return build_executive_one_pager_pdf(brief), "application/pdf", "pdf"
        return build_executive_one_pager_text(brief).encode("utf-8"), "text/plain; charset=utf-8", "txt"
    raise HTTPException(status_code=404, detail="report not found")


@router.get("/runs/live")
async def list_live_runs(
    limit: int = Query(default=50, ge=1, le=200),
    user: AuthenticatedUser = Depends(get_current_user),
):
    check_rate_limit(user.user_id, "intelligence:runs_live")
    rows = _live_run_repo.list_runs(limit=limit, user_id=user.user_id)
    return {
        "runs": [
            {
                "runId": row.get("run_id"),
                "status": row.get("status"),
                "createdAt": row.get("created_at"),
                "completedAt": row.get("completed_at"),
                "dbId": row.get("db_id"),
                "error": row.get("error_message"),
                "userId": row.get("user_id"),
            }
            for row in rows
            if not row.get("user_id") or row.get("user_id") == user.user_id
        ]
    }


@router.get("/runs")
async def list_run_history(
    limit: int = Query(default=50, ge=1, le=200),
    include_archived: bool = Query(default=True),
    user: AuthenticatedUser = Depends(get_current_user),
):
    check_rate_limit(user.user_id, "intelligence:runs_history")
    rows = _brief_repo.recent_runs(
        limit=limit,
        include_archived=include_archived,
        user_id=user.user_id,
        include_shared=True,
    )
    return {
        "runs": [
            {
                "runId": row.get("id"),
                "createdAt": row.get("created_at"),
                "founderName": row.get("founder_name"),
                "startupName": row.get("startup_name"),
                "sector": row.get("sector"),
                "geography": row.get("geography"),
                "stage": row.get("stage"),
                "overallScore": row.get("overall_score"),
                "founderScore": row.get("founder_score"),
                "trustScore": row.get("trust_score"),
                "recommendation": row.get("recommendation"),
                "confidence": row.get("confidence"),
                "integrityScore": row.get("integrity_score"),
                "integrityGrade": row.get("integrity_grade"),
                "archivedAt": row.get("archived_at"),
                "userId": row.get("user_id"),
            }
            for row in rows
        ]
    }


@router.get("/runs/analytics")
async def get_runs_analytics(user: AuthenticatedUser = Depends(get_current_user)):
    check_rate_limit(user.user_id, "intelligence:runs_analytics")
    summary_rows = _brief_repo.recent_runs(
        limit=100,
        include_archived=True,
        user_id=user.user_id,
        include_shared=True,
    )
    full_rows = []
    for r in summary_rows:
        run_id = r.get("id")
        if run_id is not None:
            full_row = _brief_repo.get_run(int(run_id), user_id=user.user_id)
            if full_row is None:
                legacy = _brief_repo.get_run(int(run_id))
                if legacy is not None and legacy.get("user_id") is None:
                    full_row = legacy
            full_rows.append(full_row if full_row is not None else r)
        else:
            full_rows.append(r)
    return build_pilot_analytics_metrics(full_rows)


@router.post("/{run_id}/archive")
async def archive_run(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    check_rate_limit(user.user_id, "intelligence:archive")
    if _is_demo_run(run_id):
        raise HTTPException(status_code=400, detail="Demo cases are read-only and cannot be archived")
    if not run_id.isdigit() or not _brief_repo.archive_run(int(run_id), user_id=user.user_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "runId": run_id, "archived": True}


@router.post("/{run_id}/reopen")
async def reopen_run(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    check_rate_limit(user.user_id, "intelligence:reopen")
    if _is_demo_run(run_id):
        raise HTTPException(status_code=400, detail="Demo cases are read-only and cannot be modified")
    if not run_id.isdigit() or not _brief_repo.reopen_run(int(run_id), user_id=user.user_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "runId": run_id, "archived": False}


@router.delete("/{run_id}")
async def delete_run(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    check_rate_limit(user.user_id, "intelligence:delete")
    if _is_demo_run(run_id):
        raise HTTPException(status_code=400, detail="Demo cases are read-only and cannot be deleted")
    if not run_id.isdigit() or not _brief_repo.delete_run(int(run_id), user_id=user.user_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "runId": run_id, "deleted": True}


@router.get("/{run_id}/brief/full")
async def get_full_brief(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    check_rate_limit(user.user_id, "intelligence:full_brief")
    brief = _load_brief_model(run_id, user.user_id)
    return brief.model_dump(mode="json")


@router.get("/{run_id}/reports/{report_kind}")
async def download_report(
    run_id: str,
    report_kind: str,
    format: str = Query(default="pdf"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    check_rate_limit(user.user_id, f"intelligence:report:{report_kind}")
    brief = _load_brief_model(run_id, user.user_id)
    body, media_type, ext = _report_payload(brief, report_kind, format)
    filename_map = {
        "memo": f"Kulima_IC_Memo_{run_id}.{ext}",
        "report": f"Kulima_Full_IC_Report_{run_id}.{ext}",
        "signals": f"Kulima_Signals_Report_{run_id}.{ext}",
        "due-diligence": f"Kulima_Due_Diligence_Summary_{run_id}.{ext}",
        "one-pager": f"Kulima_Executive_One_Pager_{run_id}.{ext}",
    }
    headers = {"Content-Disposition": f'attachment; filename="{filename_map[report_kind.lower().strip()]}"'}
    return Response(content=body, media_type=media_type, headers=headers)


@router.post("/{run_id}/feedback")
async def save_run_feedback(
    run_id: str,
    payload: dict = Body(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    check_rate_limit(user.user_id, "intelligence:feedback")
    user_name = str(payload.get("userName") or payload.get("user_name") or user.user_id or "Pilot User")
    comment = str(payload.get("comment") or "")
    try:
        rating = int(payload.get("rating") or 0)
    except Exception:
        rating = 0
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="rating must be between 1 and 5")
    db_id = int(run_id) if run_id.isdigit() else 36
    try:
        feedback_id = _brief_repo.save_feedback(db_id, user_name, rating, comment, user_id=user.user_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail={"error": True, "message": str(e)})
    except PermissionError as e:
        raise HTTPException(status_code=403, detail={"error": True, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": True, "message": f"Database error: {str(e)}"})
    if not feedback_id:
        raise HTTPException(status_code=500, detail={"error": True, "message": "feedback could not be saved"})
    return {"ok": True, "runId": run_id, "rating": rating, "feedbackId": feedback_id}


@router.post("/", response_model=IntelligenceCreateResponse)
async def create_intelligence(
    req: IntelligenceCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "intelligence:create")

    if not req.founder:
        raise HTTPException(status_code=400, detail="founder is required")
    run_id = start_intelligence_run(req.founder, req.startup or "", user.user_id)
    return JSONResponse(content={"runId": run_id, "status": "running"})


@router.get("/{run_id}", response_model=IntelligenceStatusResponse)
async def get_intelligence(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "intelligence:get")

    info = get_run_status(run_id, user.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})
    return {
        "runId": info.get("run_id") or run_id,
        "status": info.get("status", "unknown"),
        "dbId": info.get("db_id"),
        "createdAt": info.get("created_at"),
        "completedAt": info.get("completed_at"),
        "error": info.get("error_message"),
    }


@router.get("/{run_id}/brief", response_model=DecisionSnapshot)
async def get_decision_snapshot(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    """Return a compact Decision Snapshot for the given run.

    This derives the same fields shown in the Streamlit Decision Snapshot
    from the stored InvestmentBrief and EvidenceIntegrity surfaces.
    """

    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "intelligence:brief")

    info = get_run_status(run_id, user.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    brief_json = get_brief_for_run(run_id, user.user_id)
    if brief_json is None:
        raise HTTPException(status_code=404, detail="brief not found")

    brief = InvestmentBrief.model_validate(brief_json) if isinstance(brief_json, dict) else brief_json

    # VERDICT
    verdict = getattr(brief.recommendation, "value", str(brief.recommendation))

    # CONFIDENCE
    conf_level = getattr(brief, "confidence_level", None)
    conf_num = getattr(brief, "confidence", None)
    confidence_percent = None
    confidence_label = None
    if isinstance(conf_num, (int, float)):
        confidence_percent = float(conf_num) * 100.0
        confidence_label = getattr(conf_level, "value", conf_level)
    elif conf_level is not None:
        confidence_label = getattr(conf_level, "value", conf_level)

    # RELIABILITY
    ei = getattr(brief, "evidence_integrity", None)
    reliability_grade = None
    reliability_score = None
    if ei is not None:
        reliability_grade = getattr(ei.integrity_grade, "value", ei.integrity_grade)
        reliability_score = float(ei.integrity_score)

    # TOP REASONS (3) – mirror render_decision_brief
    reasons: list[str] = []
    if brief.executive_summary:
        reasons.append(str(brief.executive_summary).strip().split(". ")[0][:140])
    if brief.investment_recommendation:
        reasons.append(str(brief.investment_recommendation).strip().split(". ")[0][:140])
    if len(reasons) < 3:
        reasons.append(f"Strong overall score at {brief.overall_score:.0f}/100 vs. peers.")
    top_reasons = reasons[:3]

    # TOP RISKS (3)
    top_risks: list[str] = []
    if brief.red_flags:
        for rf in brief.red_flags[:3]:
            sev = (rf.severity or "").upper()
            title = rf.title or ""
            detail = (rf.detail or "")[:120]
            top_risks.append(f"[{sev}] {title}: {detail}")
    else:
        top_risks.append("No critical red flags surfaced from open-source intelligence.")

    # NEXT ACTION (one sentence)
    if brief.investment_recommendation:
        next_action = str(brief.investment_recommendation).strip().split(". ")[0][:160]
    else:
        next_action = "Advance to IC only after focused verification of key risks."

    return DecisionSnapshot(
        verdict=verdict,
        confidencePercent=confidence_percent,
        confidenceLabel=str(confidence_label) if confidence_label is not None else None,
        reliabilityGrade=str(reliability_grade) if reliability_grade is not None else None,
        reliabilityScore=reliability_score,
        topReasons=top_reasons,
        topRisks=top_risks,
        nextAction=next_action,
    )


@router.get("/{run_id}/signals", response_model=SignalsSummary)
async def get_signals_summary(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    """Return a summary of Signals for the given run.

    This reuses the SignalsOrchestrator and summary helpers to surface
    counts and top risks/opportunities for the web ContextPanel.
    """

    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "intelligence:signals")

    info = get_run_status(run_id, user.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    brief_json = get_brief_for_run(run_id, user.user_id)
    if brief_json is None:
        raise HTTPException(status_code=404, detail="brief not found")

    brief = InvestmentBrief.model_validate(brief_json) if isinstance(brief_json, dict) else brief_json

    # Wrap brief in a Case envelope and generate Signals
    case = from_investment_brief(brief, case_id=run_id, created_by=user.user_id)
    signals = _signals_orchestrator.generate(case, sort=True)

    # Counts by level
    counts = count_signals_by_level(signals)
    critical = counts.get(SignalLevel.CRITICAL, 0)
    high = counts.get(SignalLevel.HIGH, 0)
    medium = counts.get(SignalLevel.MEDIUM, 0)
    low = counts.get(SignalLevel.LOW, 0)

    # Top risks and opportunities (direction field)
    risk_signals = [s for s in signals if (s.direction or "risk") == "risk"]
    opp_signals = [s for s in signals if (s.direction or "").lower() == "opportunity"]

    top_risks = highest_priority_signals(risk_signals, limit=3) if risk_signals else []
    top_opps = highest_priority_signals(opp_signals, limit=3) if opp_signals else []

    def _map_signal(s: Signal) -> SignalItem:
        return SignalItem(
            id=s.id,
            level=getattr(s.level, "value", str(s.level)),
            category=getattr(s.category, "value", str(s.category)),
            direction=s.direction,
            title=s.title,
            description=s.description,
            recommendedAction=s.recommended_action,
            confidence=float(s.confidence),
        )

    return SignalsSummary(
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        topRisks=[_map_signal(s) for s in top_risks],
        topOpportunities=[_map_signal(s) for s in top_opps],
    )
