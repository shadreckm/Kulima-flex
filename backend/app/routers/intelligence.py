from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

import logging

from kulima.core.audit import record_event
from kulima.core.billing.service import BillingBlocked, assert_feature
from kulima.core.cases.adapters import from_investment_brief
from kulima.core.orgs.models import Permission
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
from kulima.decision import build_decision_view
from kulima.models import InvestmentBrief
from kulima.portfolio_intelligence import build_pilot_analytics_metrics
from kulima.signals.models import Signal, SignalCategory, SignalLevel
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.signals_summary import (
    build_domain_overviews,
    count_signals_by_level,
    display_domain,
    highest_priority_signals,
)

from ..core.auth import OrgContext, require_permission
from ..core.rate_limit import check_rate_limit
from ..schemas.dtos import (
    DecisionSnapshot,
    DomainSignals,
    IntelligenceCreateRequest,
    IntelligenceCreateResponse,
    IntelligenceStatusResponse,
    SignalItem,
    SignalsSummary,
)
from ..services import assessment_adapter
from ..services.assessment_adapter import AssessmentError
from ..services.orchestrator_adapter import get_brief_for_run, get_run_status, start_intelligence_run
from ..services.run_repository import RunRepository

router = APIRouter()

_log = logging.getLogger(__name__)

_signals_orchestrator = SignalsOrchestrator()
_brief_repo = IntelligenceRepository()
_live_run_repo = RunRepository()


def _is_demo_run(run_id: str | int) -> bool:
    s = str(run_id).lower()
    return s.startswith("ostx-") or s.startswith("pilot-") or not s.isdigit()

def _load_brief_model(run_id: str | int, user_id: str | None = None, org_id: str | None = None) -> InvestmentBrief:
    """Load a stored brief, workspace-scoped when org_id is provided."""
    run_str = str(run_id)
    if run_str.isdigit():
        db_id = int(run_str)
        stored_row = (
            _brief_repo.get_run(db_id, org_id=org_id)
            if org_id is not None
            else _brief_repo.get_run(db_id, user_id=user_id)
        )
        if stored_row is None and user_id is not None and org_id is None:
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


# Report kinds gated behind the PRO/Enterprise "enterprise_reports" feature
# (pass-through while KULIMA_BILLING_ENFORCEMENT is disabled).
_ENTERPRISE_REPORT_KINDS = {"memo", "report", "due-diligence", "one-pager"}


def _raise_billing_block(exc: BillingBlocked) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


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
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    check_rate_limit(current.user_id, "intelligence:runs_live")
    member_ids = current.member_ids()
    rows = _live_run_repo.list_runs(limit=limit * 3)
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
            if not row.get("user_id") or row.get("user_id") in member_ids
        ][:limit]
    }


@router.get("/runs")
async def list_run_history(
    limit: int = Query(default=50, ge=1, le=200),
    include_archived: bool = Query(default=True),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    check_rate_limit(current.user_id, "intelligence:runs_history")
    rows = _brief_repo.recent_runs(
        limit=limit,
        include_archived=include_archived,
        org_id=current.org_id,
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
async def get_runs_analytics(current: OrgContext = Depends(require_permission(Permission.VIEW))):
    check_rate_limit(current.user_id, "intelligence:runs_analytics")
    summary_rows = _brief_repo.recent_runs(
        limit=100,
        include_archived=True,
        org_id=current.org_id,
        include_shared=False,
    )
    full_rows = []
    for r in summary_rows:
        run_id = r.get("id")
        if run_id is not None:
            full_row = _brief_repo.get_run(int(run_id), org_id=current.org_id)
            full_rows.append(full_row if full_row is not None else r)
        else:
            full_rows.append(r)
    return build_pilot_analytics_metrics(full_rows)


@router.post("/{run_id}/archive")
async def archive_run(run_id: str, current: OrgContext = Depends(require_permission(Permission.ASSESS))):
    check_rate_limit(current.user_id, "intelligence:archive")
    if _is_demo_run(run_id):
        raise HTTPException(status_code=400, detail="Demo cases are read-only and cannot be archived")
    if not run_id.isdigit() or not _brief_repo.archive_run(int(run_id), org_id=current.org_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "runId": run_id, "archived": True}


@router.post("/{run_id}/reopen")
async def reopen_run(run_id: str, current: OrgContext = Depends(require_permission(Permission.ASSESS))):
    check_rate_limit(current.user_id, "intelligence:reopen")
    if _is_demo_run(run_id):
        raise HTTPException(status_code=400, detail="Demo cases are read-only and cannot be modified")
    if not run_id.isdigit() or not _brief_repo.reopen_run(int(run_id), org_id=current.org_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "runId": run_id, "archived": False}


@router.delete("/{run_id}")
async def delete_run(run_id: str, current: OrgContext = Depends(require_permission(Permission.DELETE_DATA))):
    check_rate_limit(current.user_id, "intelligence:delete")
    if _is_demo_run(run_id):
        raise HTTPException(status_code=400, detail="Demo cases are read-only and cannot be deleted")
    if not run_id.isdigit() or not _brief_repo.delete_run(int(run_id), org_id=current.org_id):
        raise HTTPException(status_code=404, detail="run not found")
    record_event(
        "assessment.deleted",
        org_id=current.org_id,
        user_id=current.user_id,
        run_id=run_id,
        metadata={"mode": "run_only", "runId": run_id},
    )
    return {"ok": True, "runId": run_id, "deleted": True}


@router.get("/{run_id}/brief/full")
async def get_full_brief(run_id: str, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    check_rate_limit(current.user_id, "intelligence:full_brief")
    brief = _load_brief_model(run_id, current.user_id, org_id=current.org_id)
    return brief.model_dump(mode="json")


@router.get("/{run_id}/reports/{report_kind}")
async def download_report(
    run_id: str,
    report_kind: str,
    format: str = Query(default="pdf"),
    current: OrgContext = Depends(require_permission(Permission.EXPORT)),
):
    check_rate_limit(current.user_id, f"intelligence:report:{report_kind}")
    kind = report_kind.lower().strip()
    if kind in _ENTERPRISE_REPORT_KINDS:
        try:
            assert_feature(current.org_id, "enterprise_reports")
        except BillingBlocked as exc:
            _raise_billing_block(exc)
    brief = _load_brief_model(run_id, current.user_id, org_id=current.org_id)
    body, media_type, ext = _report_payload(brief, report_kind, format)
    filename_map = {
        "memo": f"Kulima_IC_Memo_{run_id}.{ext}",
        "report": f"Kulima_Full_IC_Report_{run_id}.{ext}",
        "signals": f"Kulima_Signals_Report_{run_id}.{ext}",
        "due-diligence": f"Kulima_Due_Diligence_Summary_{run_id}.{ext}",
        "one-pager": f"Kulima_Executive_One_Pager_{run_id}.{ext}",
    }
    record_event(
        "report.exported",
        org_id=current.org_id,
        user_id=current.user_id,
        run_id=run_id,
        metadata={"reportKind": kind, "format": ext},
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename_map[kind]}"'}
    return Response(content=body, media_type=media_type, headers=headers)


@router.get("/feedback/all")
async def list_all_feedback(
    limit: int = Query(default=100, ge=1, le=500),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Admin/reviewer view: list all feedback entries visible to this user."""
    check_rate_limit(current.user_id, "intelligence:feedback_list")
    records = _brief_repo.list_all_feedback(limit=limit, user_id=current.user_id)
    return {
        "feedback": [
            {
                "id": row.get("id"),
                "runId": row.get("run_id"),
                "userName": row.get("user_name"),
                "rating": row.get("rating"),
                "comment": row.get("comment"),
                "createdAt": row.get("created_at"),
                "startupName": row.get("startup_name"),
                "founderName": row.get("founder_name"),
                "recommendation": row.get("recommendation"),
                "trustScore": row.get("trust_score"),
                "integrityGrade": row.get("integrity_grade"),
            }
            for row in records
        ],
        "total": len(records),
    }


@router.get("/{run_id}/feedback")
async def get_run_feedback(
    run_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Get all feedback entries for a specific run."""
    check_rate_limit(current.user_id, "intelligence:feedback_get")
    if not run_id.isdigit():
        return {"feedback": [], "total": 0, "runId": run_id}
    records = _brief_repo.get_feedback_for_run(int(run_id), user_id=current.user_id)
    return {
        "feedback": [
            {
                "id": row.get("id"),
                "runId": row.get("run_id"),
                "userName": row.get("user_name"),
                "rating": row.get("rating"),
                "comment": row.get("comment"),
                "createdAt": row.get("created_at"),
            }
            for row in records
        ],
        "total": len(records),
        "runId": run_id,
    }


@router.post("/{run_id}/feedback")
async def save_run_feedback(
    run_id: str,
    payload: dict = Body(...),
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    check_rate_limit(current.user_id, "intelligence:feedback")
    user_name = str(payload.get("userName") or payload.get("user_name") or current.user_id or "Pilot User")
    comment = str(payload.get("comment") or "")
    try:
        rating = int(payload.get("rating") or 0)
    except Exception:
        rating = 0
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="rating must be between 1 and 5")
    db_id = int(run_id) if run_id.isdigit() else 36
    try:
        feedback_id = _brief_repo.save_feedback(db_id, user_name, rating, comment, user_id=current.user_id)
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
    current: OrgContext = Depends(require_permission(Permission.ASSESS)),
):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "intelligence:create")

    # Single-intake flow: when an assessmentId is supplied the run identity is
    # resolved from the shared Assessment Context (auto-extracted from the
    # uploaded documents), so the user never re-enters founder/startup again.
    if req.assessmentId:
        try:
            result = assessment_adapter.start_assessment_run(
                req.assessmentId, current.user_id, org_id=current.org_id
            )
        except BillingBlocked as exc:
            _raise_billing_block(exc)
        except AssessmentError as exc:
            status = 404 if exc.code == "assessment_not_found" else 400
            raise HTTPException(status_code=status, detail={"error": True, "message": str(exc)})
        return JSONResponse(content={"runId": result["runId"], "status": result.get("status", "running")})

    if not req.founder:
        raise HTTPException(status_code=400, detail="founder is required")
    run_id = start_intelligence_run(req.founder, req.startup or "", current.user_id, org_id=current.org_id)
    return JSONResponse(content={"runId": run_id, "status": "running"})


@router.get("/{run_id}", response_model=IntelligenceStatusResponse)
async def get_intelligence(run_id: str, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "intelligence:get")

    info = get_run_status(run_id, current.user_id)
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
async def get_decision_snapshot(run_id: str, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    """Return a compact Decision Snapshot for the given run.

    This derives the same fields shown in the Streamlit Decision Snapshot
    from the stored InvestmentBrief and EvidenceIntegrity surfaces.
    """

    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "intelligence:brief")

    info = get_run_status(run_id, current.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    brief_json = get_brief_for_run(run_id, current.user_id)
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

    # ── Expanded Decision Engine (Step 7) ────────────────────────────────
    # The composite decision consumes Evidence + Trust, Risk, Opportunity,
    # Market, Funding, Climate, Environment, Tourism and Community Impact
    # domains instead of only trust + risk. Best-effort: legacy behaviour is
    # preserved when signal generation fails.
    decision_score = None
    decision_band = None
    decision_rationale = None
    domain_scores = None
    try:
        case = from_investment_brief(brief, case_id=run_id, created_by=current.user_id)
        decision_signals = _signals_orchestrator.generate(case, sort=True)
        evidence_score = float(ei.integrity_score) if ei is not None else None
        view = build_decision_view(
            decision_signals,
            evidence_score=evidence_score,
            trust_score=float(brief.trust_score) if brief.trust_score else None,
        )
        decision_score = float(view["score"])
        decision_band = str(view["band"])
        decision_rationale = list(view["rationale"])
        domain_scores = {
            entry["domain"]: {
                "label": entry["label"],
                "score": entry["score"],
                "weight": entry["weight"],
                "impact": entry["impact"],
            }
            for entry in view["contributions"]
        }
    except Exception as _decision_exc:  # noqa: BLE001
        _log.warning("Expanded decision view unavailable for run %s: %s", run_id, _decision_exc)

    return DecisionSnapshot(
        verdict=verdict,
        confidencePercent=confidence_percent,
        confidenceLabel=str(confidence_label) if confidence_label is not None else None,
        reliabilityGrade=str(reliability_grade) if reliability_grade is not None else None,
        reliabilityScore=reliability_score,
        topReasons=top_reasons,
        topRisks=top_risks,
        nextAction=next_action,
        decisionScore=decision_score,
        decisionBand=decision_band,
        decisionRationale=decision_rationale,
        domainScores=domain_scores,
    )


@router.get("/{run_id}/signals", response_model=SignalsSummary)
async def get_signals_summary(run_id: str, current: OrgContext = Depends(require_permission(Permission.VIEW))):
    """Return a summary of Signals for the given run.

    This reuses the SignalsOrchestrator and summary helpers to surface
    counts and top risks/opportunities for the web ContextPanel.
    """

    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(current.user_id, "intelligence:signals")

    info = get_run_status(run_id, current.user_id)
    if not info:
        raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})

    brief_json = get_brief_for_run(run_id, current.user_id)
    if brief_json is None:
        raise HTTPException(status_code=404, detail="brief not found")

    brief = InvestmentBrief.model_validate(brief_json) if isinstance(brief_json, dict) else brief_json

    # Wrap brief in a Case envelope and generate Signals
    case = from_investment_brief(brief, case_id=run_id, created_by=current.user_id)
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
            evidenceRefs=list(getattr(s, "evidence_refs", []) or []),
            evidenceSummary=getattr(s, "evidence_summary", ""),
            timeHorizon=getattr(s, "time_horizon", None),
            metadata=dict(getattr(s, "metadata", {}) or {}),
        )

    all_mapped = [_map_signal(s) for s in signals]

    # Group into the 9 dashboard domains (Step 6): Trust, Risk, Opportunity,
    # Market, Funding, Climate, Environment, Tourism, Community. Every domain
    # carries a score, summary and recommendation. COMPETITIVE and legacy
    # monitoring categories fold into their closest dashboard domain (see
    # kulima.signals.signals_summary) so no signal becomes invisible.
    overviews = build_domain_overviews(signals)

    groups: dict[str, list[SignalItem]] = {key: [] for key in overviews}
    for item in all_mapped:
        try:
            domain = display_domain(SignalCategory(item.category))
        except ValueError:
            domain = None
        if domain is not None:
            groups[domain.value].append(item)

    domains_dict: dict[str, DomainSignals] = {}
    for dom_key, overview in overviews.items():
        matching = groups.get(dom_key, [])
        domains_dict[dom_key] = DomainSignals(
            domain=dom_key,
            label=str(overview.get("label") or dom_key),
            count=len(matching),
            riskCount=int(overview.get("risk_count") or 0),
            opportunityCount=int(overview.get("opportunity_count") or 0),
            score=int(overview.get("score") or 50),
            summary=str(overview.get("summary") or ""),
            recommendation=str(overview.get("recommendation") or ""),
            signals=matching,
        )

    return SignalsSummary(
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        topRisks=[_map_signal(s) for s in top_risks],
        topOpportunities=[_map_signal(s) for s in top_opps],
        domains=domains_dict,
        allSignals=all_mapped,
    )
