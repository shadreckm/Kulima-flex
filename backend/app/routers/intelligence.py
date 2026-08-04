from fastapi import APIRouter, HTTPException, Depends
from ..schemas.dtos import (
    DecisionSnapshot,
    IntelligenceCreateRequest,
    IntelligenceCreateResponse,
    IntelligenceStatusResponse,
    SignalItem,
    SignalsSummary,
)
from ..services.orchestrator_adapter import start_intelligence_run, get_run_status, get_brief_for_run
from ..core.auth import get_current_user, AuthenticatedUser
from ..core.rate_limit import check_rate_limit

router = APIRouter()


from kulima.models import InvestmentBrief
from kulima.core.cases.adapters import from_investment_brief
from kulima.signals.models import Signal, SignalLevel
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.signals_summary import count_signals_by_level, highest_priority_signals

_signals_orchestrator = SignalsOrchestrator()


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
    return {"runId": run_id, "status": "running"}


@router.get("/{run_id}", response_model=IntelligenceStatusResponse)
async def get_intelligence(run_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "intelligence:get")

    info = get_run_status(run_id)
    if not info or info.get("user_id") != user.user_id:
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

    info = get_run_status(run_id)
    if not info or info.get("user_id") != user.user_id:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    brief_json = get_brief_for_run(run_id)
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

    info = get_run_status(run_id)
    if not info or info.get("user_id") != user.user_id:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    brief_json = get_brief_for_run(run_id)
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
