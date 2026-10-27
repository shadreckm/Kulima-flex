"""Phase 6 — NGO / Development Programme focus validation.

Deterministic (no LLM, no network) verification that the visible product paths
produce NGO / development-programme-focused outputs for the primary customers,
while Startup reasoning is retained for Startup selections.

It "uploads" the six NGO artefacts the mission calls for — Annual Report,
Proposal, Budget, M&E Report, Workplan, Theory of Change — and verifies the
Evidence → Trust → Signals → Decision → Report → AI Analyst chain is NGO-first.

Run:  python scripts/validate_ngo_focus.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running both as a script and from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp437/cp1252; force UTF-8 so the em dashes and
# accented characters in the checks and report output print cleanly.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

from kulima.core.cases.models import Case, CaseSubject, CaseType, WorkspaceType
from kulima.models import ConfidenceLevel, InvestmentBrief, Recommendation, TrustGraph
from kulima.signals.models import SignalCategory
from kulima.signals.rules import generate_signals_from_case
from kulima.signals.signals_summary import DISPLAY_DOMAINS, DOMAIN_LABELS, build_domain_overviews
from kulima.decision import DOMAIN_WEIGHTS, ENTITY_DOMAIN_WEIGHTS, build_decision_view
from kulima.ask_ic import build_ask_ic_context
from kulima.intelligence.entity_profile import (
    classify_entity,
    entity_report_title,
    entity_research_queries,
    entity_signal_domains,
)
from kulima.intelligence.report_quality import (
    detect_entity_type,
    entity_report_title as rq_entity_report_title,
)


# ── Result collection ──────────────────────────────────────────────────────

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


# ── The six primary-customer documents ─────────────────────────────────────

NGO_DOCS = [
    {
        "id": "annual-report", "filename": "AfriCare_Malawi_Annual_Report_2025.pdf",
        "raw_summary": "Annual report summarising programmes, beneficiaries reached, audited financial statements and donor funding.",
        "evidence_items": ["Reached 42,000 households", "Board governance and audit readiness", "Donor funding diversification"],
        "signals_generated": ["Trust: audited annual report"], "trust_breakdown": {"final_trust_score": 90.0},
    },
    {
        "id": "proposal", "filename": "Food_Security_Initiative_Proposal.pdf",
        "raw_summary": "Project proposal with theory of change, logframe, results framework and budget narrative.",
        "evidence_items": ["Theory of change", "Logframe indicators and targets", "Three-year budget"],
        "signals_generated": ["Programme Delivery proposal"], "trust_breakdown": {"final_trust_score": 85.0},
    },
    {
        "id": "budget", "filename": "FY2026_Programme_Budget.xlsx",
        "raw_summary": "Detailed budget with expenditure by activity, cost effectiveness and donor cost-share.",
        "evidence_items": ["Budget integrity", "Cost per beneficiary", "Donor cost share"],
        "signals_generated": ["Funding sustainability"], "trust_breakdown": {"final_trust_score": 80.0},
    },
    {
        "id": "m-and-e", "filename": "MAndE_Report_Q3.pdf",
        "raw_summary": "Monitoring and evaluation report: indicator definitions, baseline and endline data, verification and learning.",
        "evidence_items": ["M&E indicator tracking", "Baseline and endline verification", "MEAL learning loop"],
        "signals_generated": ["Monitoring Quality"], "trust_breakdown": {"final_trust_score": 88.0},
    },
    {
        "id": "workplan", "filename": "Implementation_Workplan_2026.pdf",
        "raw_summary": "Workplan with milestones, implementation schedule and targets versus actuals per activity.",
        "evidence_items": ["Milestones and workplan", "Targets vs actuals", "Deliverables schedule"],
        "signals_generated": ["Programme Delivery progress"], "trust_breakdown": {"final_trust_score": 82.0},
    },
    {
        "id": "theory-of-change", "filename": "Theory_of_Change_and_Logframe.pdf",
        "raw_summary": "Theory of change linking activities to outcomes and impact with a logical framework of indicators.",
        "evidence_items": ["Theory of change", "Logical framework", "Results pathway"],
        "signals_generated": ["Programme Delivery architecture"], "trust_breakdown": {"final_trust_score": 84.0},
    },
]

NGO_TEXT = (
    "AfriCare Malawi is a non-governmental organisation running a donor-funded food security "
    "programme. Governance board, audited annual report, theory of change, logframe, M&E "
    "monitoring and evaluation, beneficiaries and community reach, donor funding sustainability."
)


def _make_ngo_case() -> Case:
    subject = CaseSubject(
        name="AfriCare Malawi", secondary_name="Food Security Initiative",
        sector="Agriculture / Humanitarian", region="Malawi",
    )
    payload = {
        "entity_profile": {"type": "ngo", "label": "NGO"},
        "investment_brief": {
            "startup_name": "AfriCare Malawi",
            "founder_name": "Grace Banda",
            "uploaded_evidence": NGO_DOCS,
            "executive_summary": NGO_TEXT,
        },
    }
    return Case(
        id="case-ngo-focus", case_type=CaseType.INVESTMENT,
        workspace_type=WorkspaceType.STARTUP, subject=subject,
        sources=[], trust_graph=TrustGraph(trust_score=82.0, density=0.4),
        payload=payload,
    )


def _make_brief(entity: str, *, text: str) -> InvestmentBrief:
    return InvestmentBrief(
        founder_name="Grace Banda" if entity != "startup" else "Amara Diallo",
        startup_name="AfriCare Malawi" if entity != "startup" else "PayZen Africa",
        sector="Humanitarian" if entity != "startup" else "Fintech",
        geography="Southern Africa", stage="Programme" if entity != "startup" else "Series A",
        recommendation=Recommendation.INVEST, overall_score=80.0, founder_score=82.0,
        startup_score=78.0, market_score=76.0, trust_score=74.0, risk_score=28.0,
        growth_potential=72.0, investment_readiness=70.0, confidence=0.82,
        confidence_level=ConfidenceLevel.HIGH, executive_summary=text,
        founder_assessment=text, startup_assessment=text, market_assessment=text,
        risk_assessment=text, investment_recommendation=text,
        next_steps=["Verify milestones"], explainability=["Evidence-grounded"],
        red_flags=[], sources=[], evidence_integrity=None,
    )


def main() -> int:
    print("\n=== PHASE 6 · NGO / DEVELOPMENT PROGRAMME FOCUS VALIDATION ===\n")

    # 1 · Entity classification ------------------------------------------------
    print("[Evidence · Entity classification]")
    cls = classify_entity(None, document_text=NGO_TEXT)
    check("unknown entity defaults away from startup", cls.entity_type != "startup",
          f"detected='{cls.entity_type}'")
    check("NGO narrative classified as ngo/development",
          cls.entity_type in ("ngo", "development_program"), f"detected='{cls.entity_type}'")

    # 2 · Signals --------------------------------------------------------------
    print("\n[Signals · NGO-first domains]")
    order = [DOMAIN_LABELS[d] for d in DISPLAY_DOMAINS]
    print(f"  display order: {order}")
    check("Community is the lead signal domain", order[0] == "Community", order[0])
    check("Programme Delivery domain exists",
          SignalCategory.PROGRAM_DELIVERY in DISPLAY_DOMAINS)
    for lead in ("Community", "Trust", "Funding", "Programme Delivery"):
        check(f"'{lead}' ranks ahead of Market/Tourism",
              order.index(lead) < min(order.index("Market"), order.index("Tourism")))

    signals = generate_signals_from_case(_make_ngo_case(), None, None)
    cats = {s.category for s in signals}
    check("Programme Delivery signals generated from NGO documents",
          SignalCategory.PROGRAM_DELIVERY in cats)
    check("Community Impact signals generated", SignalCategory.COMMUNITY_IMPACT in cats)
    check("Funding signals generated", SignalCategory.FUNDING in cats)

    # 3 · Decision -------------------------------------------------------------
    print("\n[Decision · programme-shaped weighting]")
    top_weighted = sorted(DOMAIN_WEIGHTS.items(), key=lambda kv: -kv[1])[:2]
    check("default decision weights lead with community/trust/delivery",
          {k for k, _ in top_weighted} & {"community_impact", "trust", "program_delivery"} != set(),
          str(top_weighted))
    ngo_w = ENTITY_DOMAIN_WEIGHTS["ngo"]
    check("NGO profile weights community + delivery > market + tourism",
          ngo_w["community_impact"] + ngo_w["program_delivery"] > ngo_w["market"] + ngo_w["tourism"])
    overviews = build_domain_overviews(signals)
    check("decision/overview surfaces Programme Delivery domain",
          "program_delivery" in overviews)
    view = build_decision_view(signals, evidence_score=80.0, trust_score=75.0)
    check("decision view built without error", isinstance(view.get("score"), (int, float)))

    # 4 · Reports --------------------------------------------------------------
    print("\n[Report · NGO defaults, IC gated to Startup]")
    check("NGO default report is Institutional Capacity Review",
          entity_report_title("ngo") == "Institutional Capacity Review")
    check("Development default report is Programme Performance Review",
          entity_report_title("development_program") == "Programme Performance Review")
    check("Startup report stays Investment Committee Report",
          entity_report_title("startup") == "Investment Committee Report")
    check("unspecified entity does NOT default to IC report",
          rq_entity_report_title(None) == "Institutional Capacity Review",
          rq_entity_report_title(None))

    # 5 · Research prompts -----------------------------------------------------
    print("\n[Research · NGO-first prompts, no startup assumptions]")
    ngo_q = " | ".join(entity_research_queries("ngo", "AfriCare Malawi", "Food Security", "Malawi"))
    print(f"  ngo queries: {ngo_q}")
    check("NGO research queries lead with annual report / donors",
          "annual report" in ngo_q.lower() and "donor" in ngo_q.lower())
    check("NGO research queries reference programme documents",
          any(k in ngo_q.lower() for k in ("theory of change", "logframe", "workplan", "monitoring")))
    check("NGO research queries drop VC jargon (funding round / traction / competitors)",
          not any(k in ngo_q.lower() for k in ("funding round", "traction", "competitors")))
    unknown_q = " ".join(entity_research_queries("mystery_type", "X", "Y", "Z")).lower()
    check("unknown entity research does NOT default to startup queries",
          "funding round investment" not in unknown_q)

    # 6 · AI Analyst reasoning frame ------------------------------------------
    print("\n[AI Analyst · entity-aware context, NGO default]")
    ngo_ctx = build_ask_ic_context(_make_brief("ngo", text=NGO_TEXT),
                                   assessment_context={"entityType": "ngo"})
    check("AI Analyst labels NGO as organisation/programme (not startup)",
          "Organisation / programme" in ngo_ctx and "Founder:" not in ngo_ctx)
    check("AI Analyst uses funding & delivery readiness wording for NGO",
          "Funding & delivery readiness" in ngo_ctx)
    venture_ctx = build_ask_ic_context(_make_brief("startup",
        text="venture seed round series a traction ARR pitch deck term sheet"),
        assessment_context={"entityType": "startup"})
    check("AI Analyst keeps Startup/VC framing for Startup runs",
          "Investment readiness" in venture_ctx and "Founder:" in venture_ctx)

    # 7 · Reasoning framework dimensions ----------------------------------------
    print("\n[AI Analyst · six-dimension NGO reasoning framework]")
    dims = entity_signal_domains("ngo")
    print(f"  NGO dimensions: {list(dims)}")
    expected_dims = {"Institutional Capacity", "Programme Performance", "Community Reach",
                     "Funding Sustainability", "Partnership Strength", "Monitoring Quality"}
    check("NGO framework exposes the six required dimensions", expected_dims <= set(dims))

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(PASSED) + len(FAILED)
    print(f"\n=== RESULT: {len(PASSED)}/{total} checks passed, {len(FAILED)} failed ===")
    if FAILED:
        print("FAILED CHECKS:")
        for name in FAILED:
            print(f"  - {name}")
        return 1
    print("NGO_FIRST_V1_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
