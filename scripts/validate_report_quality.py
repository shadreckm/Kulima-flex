"""Issue 7 — Final validation suite for report quality.

Simulates four pilot scenarios end-to-end at the report layer (no LLM needed:
the report-quality engine is deterministic), verifying:

  1. Evidence counted (never "Claims Extracted: 0 / Sources Reviewed: 0" with documents)
  2. Market validation recognized (six categories)
  3. Founder evidence recognized ("Founder not independently verified", never "No founder information")
  4. No contradictions between recommendation statements (single recommendation)
  5. No Python errors in output
  6. Single recommendation only
  7. Correct report type per entity
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kulima.models import (
    ConfidenceLevel,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    InvestmentBrief,
    Recommendation,
    SourceAttribution,
    SyndicateDecision,
    InvestorVote,
    UploadedEvidenceRecord,
    TrustScoreBreakdown,
)

from kulima.export import (
    build_full_ic_report_text,
    build_memo_text,
    build_due_diligence_summary_text,
    build_full_ic_report_pdf,
    build_memo_pdf,
)
from kulima.intelligence.report_quality import (
    evidence_accounting,
    extract_market_validation,
    founder_evidence_status,
    single_recommendation,
    sanitize_runtime_artifacts,
    has_python_error_text,
    entity_report_title,
    detect_entity_type,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def make_doc_record(filename: str, summary: str, items: list[str]) -> UploadedEvidenceRecord:
    return UploadedEvidenceRecord(
        id=filename.replace(" ", "-").lower(),
        filename=filename,
        source=f"Document Ingestion Pipeline ({filename})",
        upload_date="2026-10-16T00:00:00Z",
        file_type="PDF",
        uploader="pilot",
        trust_breakdown=TrustScoreBreakdown(final_trust_score=78.0),
        evidence_status="CORROBORATED",
        evidence_items=items,
        signals_generated=[],
        decision_impact="Supporting evidence.",
        audit_trail=[],
        raw_summary=summary,
    )


def base_brief(**kw) -> InvestmentBrief:
    defaults = dict(
        founder_name="Amara Diallo",
        startup_name="Kulima Africa",
        sector="AgTech",
        geography="Kenya",
        stage="Seed",
        recommendation=Recommendation.REVIEW_REQUIRED,
        overall_score=48.0,
        founder_score=50.0,
        startup_score=47.0,
        market_score=55.0,
        trust_score=60.0,
        risk_score=52.0,
        growth_potential=50.0,
        investment_readiness=46.0,
        confidence=0.55,
        confidence_level=ConfidenceLevel.MEDIUM,
        executive_summary="Pilot assessment based on uploaded documents.",
        founder_assessment="Founder details documented in the uploaded pitch deck; independent verification pending.",
        startup_assessment="Product described in the deck.",
        market_assessment="Market data drawn from the deck.",
        risk_assessment="Moderate diligence risk.",
        investment_recommendation="",
        next_steps=["Verify claims with the organization."],
        explainability=[],
        sources=[],
    )
    defaults.update(kw)
    return InvestmentBrief(**defaults)


# ── Scenario 1: Emerge Ventures Deck (startup pitch deck) ────────────────────

def scenario_emerge_deck() -> None:
    print("\n=== SCENARIO 1: Emerge Ventures Deck (Startup pitch deck) ===")
    docs = [
        make_doc_record(
            "Emerge_Ventures_Deck.pdf",
            "Emerge Ventures pitch deck. Founder & CEO: Amina Bello. "
            "Customer discovery: 85 farmer interviews completed in Nakuru. "
            "Pilot: 3-pilot program with two cooperatives since Q2. "
            "Partnership: signed MOU with Safaricom Agri. "
            "Revenue: $48K ARR growing month-over-month. "
            "Traction: 1,200 active users, 22% MoM growth.",
            [
                "Customer discovery evidence: 85 farmer interviews (Emerge_Ventures_Deck.pdf)",
                "Pilot program with 2 cooperatives (Emerge_Ventures_Deck.pdf)",
                "MOU signed with Safaricom Agri (Emerge_Ventures_Deck.pdf)",
                "$48K ARR with MoM growth (Emerge_Ventures_Deck.pdf)",
                "1,200 active users (Emerge_Ventures_Deck.pdf)",
            ],
        ),
    ]
    sources = [
        SourceAttribution(title="Uploaded Document: Emerge_Ventures_Deck.pdf",
                          url="document://doc-1", snippet="Founder & CEO: Amina Bello. $48K ARR.",
                          relevance=1.0, source_type="document", confidence_score=0.9),
    ]
    ei = EvidenceIntegrityReport(
        integrity_grade=IntegrityGrade.B, integrity_score=70.0,
        evidence_depth=EvidenceDepth.LIMITED, claim_count=0, source_count=0,
        high_authority_count=0, sparse_mode=True,
    )  # deliberately zeroed EIE — the accounting fix must recover the counts
    brief = base_brief(
        startup_name="Emerge Ventures",
        uploaded_evidence=docs,
        sources=sources,
        evidence_integrity=ei,
        recommendation=Recommendation.OBSERVE,
        syndicate=SyndicateDecision(
            votes=[InvestorVote(archetype_id="a", investor_name="Twin", firm="F",
                                persona="p", title="Partner",
                                vote=Recommendation.OBSERVE, decision=Recommendation.OBSERVE,
                                confidence_score=55.0, conviction=0.55, score=55.0,
                                key_reasoning="Solid deck evidence.", major_concern="",
                                thesis="Solid deck evidence.", concerns=[], conditions=[])],
            majority_vote=Recommendation.OBSERVE, final_recommendation=Recommendation.OBSERVE,
            consensus_score=55.0, average_score=55.0, dissent_index=0.2, dissent_score=20.0,
        ),
    )

    acc = evidence_accounting(brief)
    check("S1 evidence counted: sources > 0", acc["source_count"] > 0, str(acc))
    check("S1 evidence counted: claims > 0", acc["claim_count"] > 0, str(acc))
    check("S1 documents counted", acc["document_count"] == 1)

    memo = build_memo_text(brief)
    full = build_full_ic_report_text(brief)
    dd = build_due_diligence_summary_text(brief)
    everything = memo + full + dd

    check("S1 no 'Claims Extracted: 0'", "Claims extracted: 0" not in everything)
    check("S1 no 'Sources reviewed: 0'", "Sources reviewed: 0" not in everything)

    mv = extract_market_validation(brief)
    check("S1 market validation: Customer Discovery", "Customer Discovery" in mv)
    check("S1 market validation: Pilots", "Pilots" in mv)
    check("S1 market validation: Partnerships", "Partnerships" in mv)
    check("S1 market validation: Revenue Indicators", "Revenue Indicators" in mv)
    check("S1 market validation: Traction", "Traction" in mv)
    check("S1 market validation section in full report",
          "MARKET VALIDATION" in full and "Pilots:" in full)

    check("S1 founder: 'not independently verified' present",
          "Founder not independently verified" in everything or "independently corroborated" in everything)
    check("S1 founder: no 'No founder information'",
          "No founder information" not in everything and "founder is unknown" not in everything.lower())

    # Single recommendation: count canonical recommendation statements
    canonical = single_recommendation(brief)
    check("S1 single recommendation text", "Observe" in canonical and "Pass" not in canonical)
    check("S1 memo recommendation line matches canonical",
          f"Recommendation: {canonical}" in memo)
    check("S1 no contradictory 'Review Required' in S1 report (tier is Observe)",
          "RECOMMENDATION:  Review Required" not in memo and "RECOMMENDATION:  Pass" not in memo)

    # Syndicate shows ballots, not a second "Final Recommendation"
    check("S1 no second 'Final Recommendation' line", "Final Recommendation:" not in full)
    check("S1 syndicate ballots shown", "Ballot: Observe" in full)

    check("S1 report type", "INVESTMENT COMMITTEE REPORT" in memo.upper())
    check("S1 no python errors", not has_python_error_text(everything))

    pdf1 = build_memo_pdf(brief)
    pdf2 = build_full_ic_report_pdf(brief)
    check("S1 PDFs generate", len(pdf1) > 0 and len(pdf2) > 0)


# ── Scenario 2: Kulima Africa Pitch Deck ─────────────────────────────────────

def scenario_kulima_deck() -> None:
    print("\n=== SCENARIO 2: Kulima Africa Pitch Deck ===")
    docs = [
        make_doc_record(
            "Kulima_Africa_Pitch_Deck.pdf",
            "Kulima Africa deck. Founded by Joseph Mwale. "
            "Validation: problem-solution fit validated across 12 demo days. "
            "Revenue indicators: KES 5.2M in signed contracts. "
            "Traction: 340 farmers onboarded.",
            ["Founded by Joseph Mwale (Kulima_Africa_Pitch_Deck.pdf)",
             "Validation via 12 demo days (Kulima_Africa_Pitch_Deck.pdf)",
             "KES 5.2M signed contracts (Kulima_Africa_Pitch_Deck.pdf)",
             "340 farmers onboarded (Kulima_Africa_Pitch_Deck.pdf)"],
        ),
    ]
    brief = base_brief(
        startup_name="Kulima Africa",
        uploaded_evidence=docs,
        sources=[SourceAttribution(title="Uploaded Document: Kulima_Africa_Pitch_Deck.pdf",
                                   url="document://doc-2", snippet="Founded by Joseph Mwale.",
                                   relevance=1.0, source_type="document", confidence_score=0.9)],
        evidence_integrity=EvidenceIntegrityReport(
            integrity_grade=IntegrityGrade.B, integrity_score=68.0,
            evidence_depth=EvidenceDepth.LIMITED, claim_count=0, source_count=0,
            sparse_mode=True,
        ),
        recommendation=Recommendation.REVIEW_REQUIRED,
        founder_name="Joseph Mwale",
    )
    everything = build_memo_text(brief) + build_full_ic_report_text(brief) + build_due_diligence_summary_text(brief)
    acc = evidence_accounting(brief)
    check("S2 evidence counted", acc["source_count"] > 0 and acc["claim_count"] > 0, str(acc))
    check("S2 no zero-evidence contradiction",
          "Claims extracted: 0" not in everything and "Sources reviewed: 0" not in everything)
    mv = extract_market_validation(brief)
    check("S2 Validation recognized", "Validation" in mv)
    check("S2 Revenue Indicators recognized", "Revenue Indicators" in mv)
    check("S2 Traction recognized", "Traction" in mv)
    check("S2 founder statement is verification-worded",
          founder_evidence_status(brief) == "Founder not independently verified.",
          founder_evidence_status(brief))
    check("S2 no 'No founder information'", "No founder information" not in everything)
    rec = single_recommendation(brief)
    check("S2 single rec is Review Required tier", rec.startswith("Review Required"), rec)
    check("S2 no python errors", not has_python_error_text(everything))


# ── Scenario 3: NGO annual report ────────────────────────────────────────────

def scenario_ngo() -> None:
    print("\n=== SCENARIO 3: NGO annual report ===")
    docs = [
        make_doc_record(
            "AfriCare_Annual_Report_2025.pdf",
            "AfriCare Malawi annual report. Executive Director: Grace Banda. "
            "Program delivery: 18,000 beneficiaries reached across 4 districts. "
            "Partnerships: donor consortium with three bilateral agencies. "
            "Governance: audited accounts, board of 9 trustees.",
            ["18,000 beneficiaries reached (AfriCare_Annual_Report_2025.pdf)",
             "Donor consortium partnerships (AfriCare_Annual_Report_2025.pdf)",
             "Audited accounts (AfriCare_Annual_Report_2025.pdf)"],
        ),
    ]
    brief = base_brief(
        startup_name="AfriCare Malawi",
        founder_name="Grace Banda",
        uploaded_evidence=docs,
        sources=[SourceAttribution(title="Uploaded Document: AfriCare_Annual_Report_2025.pdf",
                                   url="document://doc-3", snippet="18,000 beneficiaries reached.",
                                   relevance=1.0, source_type="document", confidence_score=0.9)],
        evidence_integrity=EvidenceIntegrityReport(
            integrity_grade=IntegrityGrade.B, integrity_score=76.0,
            evidence_depth=EvidenceDepth.MODERATE, claim_count=0, source_count=0,
        ),
        recommendation=Recommendation.OBSERVE,
        executive_summary=(
            "AfriCare Malawi is a non-governmental organisation whose annual report "
            "documents program delivery and donor partnerships."
        ),
        startup_assessment=(
            "The NGO annual report documents institutional capacity and community reach."
        ),
    )
    memo = build_memo_text(brief)
    full = build_full_ic_report_text(brief)
    everything = memo + full
    check("S3 report type = Institutional Capacity Report",
          "INSTITUTIONAL CAPACITY REPORT" in memo.upper(), memo[:400])
    check("S3 recommendation wording is NGO framework",
          single_recommendation(brief).startswith("Moderate Capacity"), single_recommendation(brief))
    check("S3 no Invest/Pass ladder in NGO report",
          "Recommendation: Invest" not in everything and "Recommendation: Pass" not in everything)
    acc = evidence_accounting(brief)
    check("S3 evidence counted", acc["claim_count"] > 0 and acc["source_count"] > 0, str(acc))
    check("S3 no python errors", not has_python_error_text(everything))


# ── Scenario 4: Tourism strategy ─────────────────────────────────────────────

def scenario_tourism() -> None:
    print("\n=== SCENARIO 4: Tourism strategy ===")
    docs = [
        make_doc_record(
            "Lakeshore_Tourism_Strategy_2026.pdf",
            "Lakeshore Lodge tourism strategy. Owner: Chimwemwe Nkhoma. "
            "Visitor economy: 6,500 visitors annually, 58% occupancy. "
            "Partnership: Malawi Tourism Association member. "
            "Climate resilience: solar water heating and flood-adapted construction.",
            ["6,500 visitors annually (Lakeshore_Tourism_Strategy_2026.pdf)",
             "58% occupancy (Lakeshore_Tourism_Strategy_2026.pdf)",
             "Tourism association partnership (Lakeshore_Tourism_Strategy_2026.pdf)"],
        ),
    ]
    brief = base_brief(
        startup_name="Lakeshore Lodge",
        founder_name="Chimwemwe Nkhoma",
        uploaded_evidence=docs,
        sources=[SourceAttribution(title="Uploaded Document: Lakeshore_Tourism_Strategy_2026.pdf",
                                   url="document://doc-4", snippet="6,500 visitors annually.",
                                   relevance=1.0, source_type="document", confidence_score=0.9)],
        evidence_integrity=EvidenceIntegrityReport(
            integrity_grade=IntegrityGrade.B, integrity_score=72.0,
            evidence_depth=EvidenceDepth.MODERATE, claim_count=0, source_count=0,
        ),
        recommendation=Recommendation.OBSERVE,
        executive_summary=(
            "Lakeshore Lodge is a tourism and hospitality business whose strategy "
            "documents the visitor economy and destination readiness."
        ),
        startup_assessment="The tourism strategy documents occupancy and seasonality.",
    )
    memo = build_memo_text(brief)
    everything = memo + build_full_ic_report_text(brief)
    check("S4 report type = Tourism Resilience Report",
          "TOURISM RESILIENCE REPORT" in memo.upper())
    check("S4 recommendation wording is tourism framework",
          single_recommendation(brief).startswith("Build Resilience"), single_recommendation(brief))
    check("S4 market validation: Partnerships", "Partnerships" in extract_market_validation(brief))
    acc = evidence_accounting(brief)
    check("S4 evidence counted", acc["claim_count"] > 0 and acc["source_count"] > 0, str(acc))
    check("S4 no python errors", not has_python_error_text(everything))


# ── Issue 5 regression: syndicate parser never raises ────────────────────────

def scenario_syndicate_parser() -> None:
    print("\n=== SCENARIO 5: Syndicate parser robustness ===")
    from kulima.breakthrough.syndicate import _parse_syndicate_decision
    hostile = [None, "", "   ", 2, 0, 1, 3.7, True, {"decision": "INVEST"},
               {"vote": "pass"}, '["Invest"]', '{"decision": {"nested": 1}}',
               "The twin votes to INVEST this round.", "PASS.", "«Observe»", object()]
    ok = True
    for case in hostile:
        try:
            result = _parse_syndicate_decision(case)
            assert result in (Recommendation.INVEST, Recommendation.OBSERVE, Recommendation.PASS)
        except Exception as exc:
            ok = False
            check(f"S5 parser handles {case!r}", False, str(exc))
    check("S5 parser never raises on hostile input", ok)


def main() -> int:
    scenario_emerge_deck()
    scenario_kulima_deck()
    scenario_ngo()
    scenario_tourism()
    scenario_syndicate_parser()

    print("\n" + "=" * 70)
    if FAILURES:
        print(f"VALIDATION FAILED — {len(FAILURES)} failing check(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL VALIDATION CHECKS PASSED — MENTOR_REVIEW_READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
