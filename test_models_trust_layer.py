"""Sub-Task 1 regression tests — Trust Layer data models.

Validates:
1. EvidenceIntegrityReport instantiates with minimal fields (all defaults).
2. InvestmentBrief with evidence_integrity=None serialises and deserialises cleanly.
3. InvestmentBrief with a full EvidenceIntegrityReport round-trips correctly.
4. Existing stored-run JSON (no evidence_integrity key) loads via model_validate()
   with evidence_integrity defaulting to None.
5. All new enums carry the expected member values.
6. Contradiction requires claim_a and claim_b to be Claim instances.

These tests must pass without any changes to the rest of the codebase.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from kulima.errors import EvidenceIntegrityError, PipelineStageError
from kulima.models import (
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IgnoredConflict,
    IntegrityGrade,
    InvestmentBrief,
    Recommendation,
    StaleClaim,
    StalenessT,
    UnsupportedClaim,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _minimal_brief() -> InvestmentBrief:
    """Return the smallest valid InvestmentBrief (pre-EIE, no integrity field)."""
    return InvestmentBrief(founder_name="Ada Obi", startup_name="PayFast NG")


def _sample_claim(
    claim_type: ClaimType = ClaimType.FUNDING_AMOUNT,
    value_raw: str = "$2M seed",
    source_url: str = "https://techcabal.com/example",
    value_normalised: str | None = "2000000",
) -> Claim:
    return Claim(
        claim_id="c1",
        claim_type=claim_type,
        value_raw=value_raw,
        value_normalised=value_normalised,
        source_url=source_url,
        source_authority="high_authority_web",
        source_title="TechCabal",
        snippet="PayFast NG raised $2M in a seed round.",
        staleness=StalenessT.FRESH,
        confidence=0.9,
    )


def _minimal_report() -> EvidenceIntegrityReport:
    """Return a valid EvidenceIntegrityReport using only defaults."""
    return EvidenceIntegrityReport()


def _full_report() -> EvidenceIntegrityReport:
    """Return a fully-populated EvidenceIntegrityReport for round-trip testing."""
    claim_a = _sample_claim(value_raw="$2M seed", source_url="https://techcabal.com/a")
    claim_b = _sample_claim(
        value_raw="$500K pre-seed",
        value_normalised="500000",
        source_url="https://blog.example.com/b",
    )
    contradiction = Contradiction(
        contradiction_id="con1",
        claim_a=claim_a,
        claim_b=claim_b,
        severity=ContradictionSeverity.CRITICAL,
        subtype="GENUINE_CONTRADICTION",
        description="Sources disagree on funding raised by 300%.",
        recommended_action="Verify with founder or data room.",
    )
    ignored = IgnoredConflict(
        claim_a=_sample_claim(value_raw="Founded 2018"),
        claim_b=_sample_claim(value_raw="Founded 2019"),
        reason="FOUNDING_YEAR_TOLERANCE",
        subtype="TEMPORAL_DRIFT",
        description="1-year gap within Africa founding year tolerance (±2 years).",
    )
    unsupported = UnsupportedClaim(
        claim_type=ClaimType.REGULATORY_STATUS,
        description="Regulatory status not found in open sources.",
        severity=ContradictionSeverity.HIGH,
        recommended_action="Request licence number from founder.",
    )
    stale_claim = StaleClaim(
        claim=_sample_claim(value_raw="12 employees"),
        staleness=StalenessT.STALE,
        source_url="https://linkedin.com/company/payfast-ng",
        recommended_action="Confirm current headcount with founder.",
    )
    return EvidenceIntegrityReport(
        integrity_score=63.0,
        integrity_grade=IntegrityGrade.C,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=ConsistencyStatus.CONFLICTS,
        sparse_mode=False,
        claim_count=8,
        source_count=6,
        high_authority_count=3,
        contradictions=[contradiction],
        ignored_conflicts=[ignored],
        unsupported_claims=[unsupported],
        stale_claims=[stale_claim],
        corroboration_bonus=3.0,
        integrity_summary=(
            "Moderate OSINT coverage. Sources disagree on total funding raised. "
            "Recommend direct founder confirmation before IC presentation."
        ),
        extraction_notes="Claim extraction completed successfully.",
        confidence_adjusted=0.62,
        confidence_delta=-0.05,
        two_axis_label="C",
        verification_checklist=[
            "Verify funding raised directly with founder.",
            "Request latest cap table.",
        ],
        generated_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


# ── Test 1 — minimal instantiation ───────────────────────────────────────────

def test_evidence_integrity_report_minimal_instantiation() -> None:
    """EvidenceIntegrityReport must instantiate with no arguments."""
    report = _minimal_report()
    assert report.integrity_score == 100.0
    assert report.integrity_grade == IntegrityGrade.A
    assert report.evidence_depth == EvidenceDepth.THIN
    assert report.consistency_status == ConsistencyStatus.CLEAN
    assert report.sparse_mode is False
    assert report.contradictions == []
    assert report.ignored_conflicts == []
    assert report.unsupported_claims == []
    assert report.stale_claims == []
    assert report.verification_checklist == []
    assert report.generated_at is None


# ── Test 2 — InvestmentBrief without evidence_integrity round-trips ───────────

def test_investment_brief_without_integrity_round_trips() -> None:
    """InvestmentBrief with evidence_integrity=None serialises and deserialises."""
    brief = _minimal_brief()
    assert brief.evidence_integrity is None

    data = brief.model_dump(mode="json")
    assert data["evidence_integrity"] is None

    restored = InvestmentBrief.model_validate(data)
    assert restored.evidence_integrity is None
    assert restored.founder_name == "Ada Obi"
    assert restored.startup_name == "PayFast NG"


# ── Test 3 — InvestmentBrief with full report round-trips ────────────────────

def test_investment_brief_with_full_report_round_trips() -> None:
    """InvestmentBrief with a full EvidenceIntegrityReport round-trips via JSON."""
    brief = _minimal_brief()
    brief.evidence_integrity = _full_report()

    payload = json.dumps(brief.model_dump(mode="json"))
    restored = InvestmentBrief.model_validate(json.loads(payload))

    assert restored.evidence_integrity is not None
    assert restored.evidence_integrity.integrity_grade == IntegrityGrade.C
    assert restored.evidence_integrity.integrity_score == 63.0
    assert len(restored.evidence_integrity.contradictions) == 1
    assert len(restored.evidence_integrity.ignored_conflicts) == 1
    assert restored.evidence_integrity.contradictions[0].claim_a.value_raw == "$2M seed"
    assert restored.evidence_integrity.contradictions[0].severity == ContradictionSeverity.CRITICAL


# ── Test 4 — legacy JSON (no evidence_integrity key) loads correctly ──────────

def test_legacy_json_loads_with_evidence_integrity_none() -> None:
    """A stored brief JSON without evidence_integrity key must load via model_validate
    and produce evidence_integrity=None (backward compatibility guarantee)."""
    legacy_json = {
        "founder_name": "Kofi Mensah",
        "startup_name": "AgriLink GH",
        "sector": "Agritech",
        "geography": "Ghana",
        "stage": "Seed",
        "overall_score": 72.5,
        "founder_score": 68.0,
        "startup_score": 74.0,
        "market_score": 70.0,
        "trust_score": 65.0,
        "risk_score": 28.0,
        "confidence": 0.71,
        "recommendation": "Observe",
        # Note: no "evidence_integrity" key — this is a pre-EIE stored run
    }
    brief = InvestmentBrief.model_validate(legacy_json)
    assert brief.evidence_integrity is None
    assert brief.founder_name == "Kofi Mensah"
    assert brief.overall_score == 72.5


# ── Test 5 — all new enums carry correct member values ────────────────────────

def test_all_new_enums_have_correct_values() -> None:
    """Every new enum must expose the exact string values defined in the blueprint."""
    # ClaimType — 17 members
    assert ClaimType.FUNDING_AMOUNT == "funding_amount"
    assert ClaimType.FOUNDING_YEAR == "founding_year"
    assert ClaimType.EMPLOYEE_COUNT == "employee_count"
    assert ClaimType.STAGE == "stage"
    assert ClaimType.GEOGRAPHY == "geography"
    assert ClaimType.INVESTOR_IDENTITY == "investor_identity"
    assert ClaimType.REVENUE == "revenue"
    assert ClaimType.VALUATION == "valuation"
    assert ClaimType.PRODUCT_DESCRIPTION == "product_description"
    assert ClaimType.TEAM_COMPOSITION == "team_composition"
    assert ClaimType.LEGAL_STATUS == "legal_status"
    assert ClaimType.REGULATORY_STATUS == "regulatory_status"
    assert ClaimType.PARTNERSHIP == "partnership"
    assert ClaimType.MARKET_SIZE == "market_size"
    assert ClaimType.GROWTH_METRIC == "growth_metric"
    assert ClaimType.CUSTOMER_COUNT == "customer_count"
    assert ClaimType.OTHER == "other"
    assert len(ClaimType) == 17

    # StalenessT — 5 members
    assert StalenessT.FRESH == "fresh"
    assert StalenessT.AGING == "aging"
    assert StalenessT.STALE == "stale"
    assert StalenessT.VERY_STALE == "very_stale"
    assert StalenessT.UNKNOWN == "unknown"
    assert len(StalenessT) == 5

    # ContradictionSeverity — 4 members
    assert ContradictionSeverity.CRITICAL == "critical"
    assert ContradictionSeverity.HIGH == "high"
    assert ContradictionSeverity.MEDIUM == "medium"
    assert ContradictionSeverity.LOW == "low"
    assert len(ContradictionSeverity) == 4

    # IntegrityGrade — 5 members
    assert IntegrityGrade.A == "A"
    assert IntegrityGrade.B == "B"
    assert IntegrityGrade.C == "C"
    assert IntegrityGrade.D == "D"
    assert IntegrityGrade.F == "F"
    assert len(IntegrityGrade) == 5

    # EvidenceDepth — 5 members
    assert EvidenceDepth.THIN == "thin"
    assert EvidenceDepth.LIMITED == "limited"
    assert EvidenceDepth.MODERATE == "moderate"
    assert EvidenceDepth.RICH == "rich"
    assert EvidenceDepth.COMPREHENSIVE == "comprehensive"
    assert len(EvidenceDepth) == 5

    # ConsistencyStatus — 4 members
    assert ConsistencyStatus.CLEAN == "clean"
    assert ConsistencyStatus.MINOR_DIFFERENCES == "minor_differences"
    assert ConsistencyStatus.CONFLICTS == "conflicts"
    assert ConsistencyStatus.MAJOR_CONFLICTS == "major_conflicts"
    assert len(ConsistencyStatus) == 4


# ── Test 6 — Contradiction requires Claim instances ──────────────────────────

def test_contradiction_requires_claim_instances() -> None:
    """Contradiction.claim_a and claim_b must be Claim model instances."""
    claim_a = _sample_claim()
    claim_b = _sample_claim(value_raw="$500K pre-seed", source_url="https://blog.example.com/b")

    c = Contradiction(claim_a=claim_a, claim_b=claim_b)
    assert isinstance(c.claim_a, Claim)
    assert isinstance(c.claim_b, Claim)
    assert c.subtype == "GENUINE_CONTRADICTION"  # default
    assert c.severity == ContradictionSeverity.MEDIUM  # default


# ── Bonus — EvidenceIntegrityError behaves correctly ─────────────────────────

def test_evidence_integrity_error_structure() -> None:
    """EvidenceIntegrityError must format its message and chain the cause."""
    cause = ValueError("LLM timeout")
    err = EvidenceIntegrityError("Claim extraction failed", cause=cause)
    assert "[EvidenceIntegrity]" in str(err)
    assert "Claim extraction failed" in str(err)
    assert "ValueError" in str(err)
    assert err.cause is cause
    assert err.__cause__ is cause


def test_pipeline_stage_error_still_works() -> None:
    """PipelineStageError must be unmodified and continue to work."""
    err = PipelineStageError("founder_agent", "No data returned")
    assert "[founder_agent]" in str(err)
    assert err.cause is None


def test_investment_brief_existing_fields_unchanged() -> None:
    """All pre-existing InvestmentBrief fields must remain at their original positions
    and types — verified by checking a subset of critical scoring fields."""
    brief = InvestmentBrief(
        founder_name="Amara Fall",
        startup_name="SolarEase SN",
        overall_score=78.0,
        founder_score=75.0,
        startup_score=80.0,
        market_score=72.0,
        trust_score=68.0,
        risk_score=22.0,
        recommendation=Recommendation.INVEST,
        confidence=0.82,
    )
    assert brief.overall_score == 78.0
    assert brief.trust_score == 68.0
    assert brief.recommendation == Recommendation.INVEST
    # The new field must default to None and must not affect existing fields
    assert brief.evidence_integrity is None
