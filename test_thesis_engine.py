"""Test suite for VC Thesis Engine (Phase 1).

Validates:
- sector matches (preferred, general, unlisted, excluded)
- exclusions enforcement (status = BLOCK, overall_match = 0%)
- stage and geography matches
- Evidence Fit derivation from EIE outputs (reliability rating, depth, consistency)
- overall match formula calculation
- portfolio aggregation with thesis metrics
- legacy compatibility (runs without pre-existing thesis data)
"""

from __future__ import annotations

import pytest

from kulima.models import (
    ConsistencyStatus,
    EvidenceDepth,
    EvidenceIntegrityReport,
    FundProfile,
    IntegrityGrade,
    InvestmentBrief,
    Recommendation,
    ThesisStatus,
)
from kulima.portfolio_intelligence import aggregate_portfolio, top_deals
from kulima.thesis import evaluate_thesis_match


@pytest.fixture
def custom_fund() -> FundProfile:
    return FundProfile(
        name="Test VC Fund",
        preferred_sectors=["FinTech", "AgTech"],
        preferred_stages=["Seed", "Series A"],
        preferred_geographies=["Nigeria", "Kenya"],
        exclusions=["Crypto", "Gambling"],
    )


def test_preferred_sector_and_matching(custom_fund):
    brief = InvestmentBrief(
        founder_name="Founder A",
        startup_name="PayFlex",
        sector="FinTech",
        stage="Seed",
        geography="Nigeria",
    )
    res = evaluate_thesis_match(brief, fund=custom_fund)

    assert res.status == ThesisStatus.PASS
    assert res.sector_fit == "High"
    assert res.stage_fit == "High"
    assert res.geography_fit == "High"
    assert res.overall_match >= 80.0


def test_exclusion_enforcement(custom_fund):
    brief = InvestmentBrief(
        founder_name="Crypto Founder",
        startup_name="ChainPay",
        sector="Crypto & Web3",
        stage="Seed",
        geography="Nigeria",
        recommendation=Recommendation.INVEST,  # High recommendation, but excluded thesis
    )
    res = evaluate_thesis_match(brief, fund=custom_fund)

    assert res.status == ThesisStatus.BLOCK
    assert res.overall_match == 0.0
    assert res.sector_fit == "Excluded"
    assert any("excluded" in note.lower() for note in res.notes)
    # INVARIANT: recommendation on brief is untouched!
    assert brief.recommendation == Recommendation.INVEST


def test_geography_and_stage_mismatch(custom_fund):
    brief = InvestmentBrief(
        founder_name="Founder B",
        startup_name="GlobalBiz",
        sector="AgTech",        # Preferred (100)
        stage="Series C",       # Non-preferred (40)
        geography="Brazil",     # Non-preferred (40)
    )
    res = evaluate_thesis_match(brief, fund=custom_fund)

    assert res.sector_fit == "High"
    assert res.stage_fit == "Low"
    assert res.geography_fit == "Low"
    # overall: 0.35*100 + 0.25*40 + 0.20*40 + 0.20*70 = 35 + 10 + 8 + 14 = 67.0%
    assert res.overall_match == 67.0
    assert res.status == ThesisStatus.WARN


def test_evidence_fit_derivation(custom_fund):
    # High evidence fit
    eie_rich = EvidenceIntegrityReport(
        integrity_score=95.0,
        integrity_grade=IntegrityGrade.A,
        evidence_depth=EvidenceDepth.RICH,
        consistency_status=ConsistencyStatus.CLEAN,
    )
    brief_rich = InvestmentBrief(
        founder_name="Founder C",
        startup_name="CleanData",
        sector="FinTech",
        stage="Seed",
        geography="Kenya",
        evidence_integrity=eie_rich,
    )
    res_rich = evaluate_thesis_match(brief_rich, fund=custom_fund)
    assert res_rich.evidence_fit == "High"

    # Low evidence fit
    eie_thin = EvidenceIntegrityReport(
        integrity_score=40.0,
        integrity_grade=IntegrityGrade.F,
        evidence_depth=EvidenceDepth.THIN,
        consistency_status=ConsistencyStatus.MAJOR_CONFLICTS,
    )
    brief_thin = InvestmentBrief(
        founder_name="Founder D",
        startup_name="RiskyData",
        sector="FinTech",
        stage="Seed",
        geography="Kenya",
        evidence_integrity=eie_thin,
    )
    res_thin = evaluate_thesis_match(brief_thin, fund=custom_fund)
    assert res_thin.evidence_fit == "Low"


def test_portfolio_aggregation_and_top_deals(custom_fund):
    rows = [
        {
            "id": 1,
            "founder_name": "F1",
            "startup_name": "S1",
            "sector": "FinTech",
            "stage": "Seed",
            "geography": "Nigeria",
            "overall_score": 85.0,
            "recommendation": "Invest",
        },
        {
            "id": 2,
            "founder_name": "F2",
            "startup_name": "S2",
            "sector": "Crypto",
            "stage": "Seed",
            "geography": "Nigeria",
            "overall_score": 80.0,
            "recommendation": "Invest",
        },
    ]

    kpis = aggregate_portfolio(rows)
    assert kpis["total_deals"] == 2
    assert "avg_thesis_match" in kpis

    # Top deals sort by thesis match
    ranked = top_deals(rows, sort_by="thesis_match", limit=2)
    assert len(ranked) == 2
    assert ranked[0]["startup_name"] == "S1"  # S1 passes thesis, S2 is crypto (blocked)


def test_legacy_compatibility():
    brief_legacy = InvestmentBrief(
        founder_name="Legacy Founder",
        startup_name="OldVenture",
    )
    # thesis_match defaults to None
    assert brief_legacy.thesis_match is None

    # Evaluate dynamically on legacy brief
    res = evaluate_thesis_match(brief_legacy)
    assert res.overall_match > 0.0
    assert res.status in (ThesisStatus.PASS, ThesisStatus.WARN)
