"""Tests for the shared Assessment Context (single-intake refactor, Steps 1–9).

Covers:
- deterministic document extraction (Step 3)
- extraction confidence blending + confirmation threshold (Steps 4–5)
- run identity resolution reused by Tavily research (Steps 5 & 9)
- nine-domain signal overviews with score / summary / recommendation (Step 6)
- expanded decision engine consuming all domains + evidence (Step 7)
"""

import pytest

from kulima.core.assessment.extraction import (
    extract_assessment_fields,
    extract_from_documents,
    merge_extractions,
)
from kulima.core.assessment.models import (
    AssessmentContext,
    AssessmentExtraction,
    AssessmentStatus,
    AssessmentType,
    ExtractedField,
)
from kulima.core.assessment.service import (
    apply_extraction,
    coerce_assessment_type,
    extraction_failed,
    manual_patch,
    resolve_run_identity,
    sector_hint,
)
from kulima.decision import build_decision_view
from kulima.signals.models import Signal, SignalCategory, SignalLevel
from kulima.signals.signals_summary import DISPLAY_DOMAINS, build_domain_overviews

PITCH_DECK_TEXT = (
    "Company: AgriNova CleanTech Ltd\n"
    "Founder & CEO: Dr. Chim Phiri\n"
    "AgriNova deploys solar-powered irrigation for smallholder farmers across Malawi.\n"
    "Website: https://agrinova.mw\n"
    "Our team of 24 engineers and agronomists works with 5,000 smallholder farmers.\n"
    "Problem: Smallholder farmers lose up to 40% of their harvest due to lack of cold storage.\n"
)


# ── Step 3: auto extraction ───────────────────────────────────────────────


def test_extraction_from_pitch_deck_text():
    extraction = extract_assessment_fields(
        PITCH_DECK_TEXT,
        AssessmentType.STARTUP,
        filename="AgriNova_Pitch_Deck.pdf",
    )

    assert extraction.field_value("organization_name") == "AgriNova CleanTech Ltd"
    assert extraction.field_value("startup_name") == "AgriNova CleanTech Ltd"
    assert extraction.field_value("founder_name") == "Chim Phiri"
    assert extraction.field_value("sector") == "AgriTech"
    assert extraction.field_value("country") == "Malawi"
    assert extraction.field_value("website") == "https://agrinova.mw"
    assert extraction.field_value("team") == "Team of 24"
    assert "Smallholder farmers lose" in extraction.field_value("problem_statement")

    # Provenance is recorded per field.
    assert extraction.organization_name.source == "document_label"
    assert extraction.founder_name.source == "document_label"

    # High-quality document extract is trusted without asking the user again.
    assert 0.7 <= extraction.confidence <= 0.95
    assert extraction_failed(AssessmentType.STARTUP, extraction) is False


def test_extraction_filename_fallback_flags_low_confidence():
    extraction = extract_assessment_fields(
        "This report contains no identities.",
        AssessmentType.NGO,
        filename="GreenLink_Foods_Final_Proposal.pdf",
    )

    # Filename-derived fallback is honest about its weak signal.
    assert extraction.field_value("organization_name") == "GreenLink Foods"
    assert extraction.organization_name.source == "filename"
    assert extraction.organization_name.confidence == pytest.approx(0.55)

    # Organisation type still needs confirmation because confidence is low.
    assert extraction_failed(AssessmentType.NGO, extraction) is True
    # Startup additionally requires a founder name.
    assert extraction_failed(AssessmentType.STARTUP, extraction) is True


def test_extraction_unreadable_document_yields_zero_confidence():
    extraction = extract_assessment_fields("tiny", AssessmentType.STARTUP)

    assert extraction.text_available is False
    assert extraction.confidence == 0.0
    assert extraction_failed(AssessmentType.STARTUP, extraction) is True


def test_merge_extractions_keeps_best_field_per_document():
    doc_a = (
        "Company: AgriNova CleanTech\n"
        "Founder: Chim Phiri\n"
        "Solar irrigation for Malawi.\n"
    )
    doc_b = (
        "Company: AgriNova CleanTech Limited\n"
        "Website: https://agrinova.mw\n"
        "Overview of the venture.\n"
    )

    merged = extract_from_documents(
        [("AgriNova_Pitch.pdf", doc_a), ("AgriNova_Legal.pdf", doc_b)],
        AssessmentType.STARTUP,
    )

    # Equal confidence -> the longer (fuller legal) name wins.
    assert merged.field_value("organization_name") == "AgriNova CleanTech Limited"
    # The founder only exists in doc A and survives the merge.
    assert merged.field_value("founder_name") == "Chim Phiri"
    assert merged.field_value("website") == "https://agrinova.mw"
    assert merged.text_available is True
    assert merged.confidence > 0


# ── Steps 4–5: confirmation rule + corrections ────────────────────────────


def test_coerce_assessment_type_aliases():
    assert coerce_assessment_type("startup") == AssessmentType.STARTUP
    assert coerce_assessment_type("NGO") == AssessmentType.NGO
    assert coerce_assessment_type("government program") == AssessmentType.GOVERNMENT_PROGRAM
    assert coerce_assessment_type("development") == AssessmentType.DEVELOPMENT_PROGRAM
    assert coerce_assessment_type("tourism sme") == AssessmentType.TOURISM_SME
    assert coerce_assessment_type("hospitality") == AssessmentType.TOURISM_SME
    assert coerce_assessment_type("unknown-garbage") == AssessmentType.STARTUP
    assert coerce_assessment_type(AssessmentType.GOVERNMENT_PROGRAM) == AssessmentType.GOVERNMENT_PROGRAM


def _field(value: str, confidence: float = 0.9) -> ExtractedField:
    return ExtractedField(value=value, confidence=confidence, source="document_label")


def test_confirmation_rule_distinguishes_startup_and_org_types():
    # Startup with entity but no founder -> must still ask.
    partial = AssessmentExtraction(
        organization_name=_field("SolarHarvest Cooperative"),
        confidence=0.7,
    )
    assert extraction_failed(AssessmentType.STARTUP, partial) is True

    # Startup identity complete and confident -> never ask again.
    complete = AssessmentExtraction(
        organization_name=_field("SolarHarvest Cooperative"),
        founder_name=_field("Maya Banda"),
        confidence=0.85,
    )
    assert extraction_failed(AssessmentType.STARTUP, complete) is False

    # Organisation types only need the entity name.
    org_only = AssessmentExtraction(
        organization_name=_field("Ministry of Agriculture Programme"),
        confidence=0.6,
    )
    assert extraction_failed(AssessmentType.GOVERNMENT_PROGRAM, org_only) is False

    # Low overall confidence still triggers one confirming question.
    weak = AssessmentExtraction(
        organization_name=_field("GreenLink Foods", confidence=0.55),
        confidence=0.4,
    )
    assert extraction_failed(AssessmentType.NGO, weak) is True


def test_apply_extraction_sets_status_and_mirrors_fields():
    ctx = AssessmentContext(assessment_id="asm-1", assessment_type=AssessmentType.STARTUP)
    extraction = extract_assessment_fields(PITCH_DECK_TEXT, AssessmentType.STARTUP)

    apply_extraction(ctx, extraction)

    assert ctx.status == AssessmentStatus.READY
    assert ctx.requires_confirmation is False
    # Flat convenience mirrors populated for the rest of the platform.
    assert ctx.organization_name == "AgriNova CleanTech Ltd"
    assert ctx.founder_name == "Chim Phiri"
    assert ctx.sector == "AgriTech"
    assert ctx.country == "Malawi"

    weak_ctx = AssessmentContext(assessment_id="asm-2", assessment_type=AssessmentType.STARTUP)
    weak = AssessmentExtraction(text_available=True, confidence=0.1)
    apply_extraction(weak_ctx, weak)
    assert weak_ctx.status == AssessmentStatus.NEEDS_CONFIRMATION
    assert weak_ctx.requires_confirmation is True


def test_manual_patch_recovers_from_failed_extraction():
    ctx = AssessmentContext(assessment_id="asm-3", assessment_type=AssessmentType.STARTUP)
    apply_extraction(ctx, AssessmentExtraction(text_available=True, confidence=0.0))
    assert ctx.status == AssessmentStatus.NEEDS_CONFIRMATION

    manual_patch(ctx, entity_name="SolarHarvest", founder_name="Maya Banda")

    assert ctx.status == AssessmentStatus.READY
    assert ctx.requires_confirmation is False
    assert ctx.extraction.startup_name.value == "SolarHarvest"
    assert ctx.extraction.startup_name.confidence == 1.0
    assert ctx.extraction.startup_name.source == "user"
    assert ctx.extraction.founder_name.value == "Maya Banda"
    # Flat mirrors refreshed from the corrected extraction.
    assert ctx.startup_name == "SolarHarvest"
    assert ctx.founder_name == "Maya Banda"


# ── Steps 5 & 9: run identity drives Tavily without re-asking ─────────────


def test_resolve_run_identity_startup_vs_org_types():
    startup_ctx = AssessmentContext(assessment_id="asm-4", assessment_type=AssessmentType.STARTUP)
    apply_extraction(startup_ctx, extract_assessment_fields(PITCH_DECK_TEXT, AssessmentType.STARTUP))

    # Startup: founder drives Tavily research, entity is the venture name.
    assert resolve_run_identity(startup_ctx) == ("Chim Phiri", "AgriNova CleanTech Ltd")
    assert sector_hint(startup_ctx) == "AgriTech"

    # Organisation types: the entity itself is carried in the founder slot
    # (legacy run convention shared with stored runs and reports).
    ngo_ctx = AssessmentContext(assessment_id="asm-5", assessment_type=AssessmentType.NGO)
    apply_extraction(ngo_ctx, extract_assessment_fields(PITCH_DECK_TEXT, AssessmentType.NGO))
    founder, startup = resolve_run_identity(ngo_ctx)
    assert founder == "AgriNova CleanTech Ltd"
    assert startup == "AgriNova CleanTech Ltd"

    # Fallbacks are type-aware instead of blank forms.
    empty_startup = AssessmentContext(assessment_id="asm-6", assessment_type=AssessmentType.STARTUP)
    assert resolve_run_identity(empty_startup) == ("Founding Team", "Unnamed Venture")

    empty_tourism = AssessmentContext(assessment_id="asm-7", assessment_type=AssessmentType.TOURISM_SME)
    assert resolve_run_identity(empty_tourism) == (
        "Unnamed Tourism Business",
        "Unnamed Tourism Business",
    )


# ── Step 6: nine-domain score / summary / recommendation ──────────────────


def _signal(
    category: SignalCategory,
    level: SignalLevel,
    direction: str,
    *,
    confidence: float = 0.8,
    action: str = "",
) -> Signal:
    return Signal(
        id=f"sig-{category.value}-{direction}-{level.value}",
        case_id="case-assessment-test",
        level=level,
        category=category,
        title=f"{category.value} {direction} signal",
        description=f"Observed {direction} signal in the {category.value} domain.",
        direction=direction,
        evidence_summary="Grounded in uploaded documents and Tavily OSINT.",
        recommended_action=action or f"Act on the {category.value} signal.",
        confidence=confidence,
    )


def test_nine_domain_overviews_with_score_summary_recommendation():
    signals = [
        _signal(SignalCategory.CLIMATE, SignalLevel.HIGH, "opportunity", action="Double down on clean irrigation."),
        _signal(SignalCategory.ENVIRONMENTAL, SignalLevel.MEDIUM, "risk"),
        _signal(SignalCategory.TOURISM, SignalLevel.MEDIUM, "opportunity"),
        _signal(SignalCategory.COMMUNITY_IMPACT, SignalLevel.HIGH, "opportunity"),
        # Legacy key folds into the Opportunity display domain.
        _signal(SignalCategory.COMPETITIVE, SignalLevel.LOW, "opportunity"),
    ]

    overviews = build_domain_overviews(signals)

    # Exactly the nine dashboard domains, in display order.
    assert list(overviews.keys()) == [d.value for d in DISPLAY_DOMAINS]
    assert len(overviews) == 9

    for entry in overviews.values():
        assert isinstance(entry["score"], int) and 0 <= entry["score"] <= 100
        assert isinstance(entry["summary"], str) and entry["summary"]
        assert isinstance(entry["recommendation"], str)

    # Deterministic scores: base 50, opportunity +level*0.75, risk -level.
    assert overviews["climate"]["score"] == 63
    assert overviews["environmental"]["score"] == 40
    assert overviews["tourism"]["score"] == 57
    assert overviews["community_impact"]["score"] == 63
    assert overviews["climate"]["recommendation"] == "Double down on clean irrigation."
    assert overviews["environmental"]["risk_count"] == 1

    # Legacy COMPETITIVE signals surface under Opportunity.
    assert overviews["opportunity"]["signal_count"] == 1

    # Empty domain is honest about having no data.
    assert overviews["trust"]["signal_count"] == 0
    assert overviews["trust"]["score"] == 50
    assert overviews["trust"]["summary"] == "No signals generated for this domain yet."

    # Display labels match the dashboard spec.
    assert overviews["environmental"]["label"] == "Environment"
    assert overviews["community_impact"]["label"] == "Community"


# ── Step 7: expanded decision engine ──────────────────────────────────────


def test_decision_view_consumes_all_domains_and_evidence():
    signals = [
        _signal(SignalCategory.TRUST, SignalLevel.HIGH, "opportunity"),
        _signal(SignalCategory.RISK, SignalLevel.CRITICAL, "risk"),
        _signal(SignalCategory.OPPORTUNITY, SignalLevel.HIGH, "opportunity"),
        _signal(SignalCategory.MARKET, SignalLevel.MEDIUM, "opportunity"),
        _signal(SignalCategory.FUNDING, SignalLevel.LOW, "opportunity"),
        _signal(SignalCategory.CLIMATE, SignalLevel.HIGH, "opportunity"),
        _signal(SignalCategory.ENVIRONMENTAL, SignalLevel.MEDIUM, "risk"),
        _signal(SignalCategory.TOURISM, SignalLevel.MEDIUM, "opportunity"),
        _signal(SignalCategory.COMMUNITY_IMPACT, SignalLevel.HIGH, "opportunity"),
    ]

    view = build_decision_view(signals, evidence_score=80.0, trust_score=75.0)

    assert 0 <= view["score"] <= 100
    assert view["band"] in {"proceed", "proceed_with_conditions", "review_required", "decline"}
    assert view["recommendation"] in {"Invest", "Observe", "Review Required", "Pass"}
    assert view["summary"]
    assert isinstance(view["rationale"], list)

    # All nine domains are reported with score/summary/recommendation each.
    assert set(view["domains"].keys()) == {d.value for d in DISPLAY_DOMAINS}

    # Contributors cover every populated domain; evidence is blended in.
    contribution_domains = {c["domain"] for c in view["contributions"]}
    assert contribution_domains == {d.value for d in DISPLAY_DOMAINS}
    for c in view["contributions"]:
        assert c["label"]
        assert 0 <= c["score"] <= 100
        assert 0 < c["weight"] < 1

    # Live trust score overrides the trust signal heuristic.
    trust_entry = next(c for c in view["contributions"] if c["domain"] == "trust")
    assert trust_entry["score"] == 75

    # Impact keeps its sign: risks drag, opportunities uplift.
    env_entry = next(c for c in view["contributions"] if c["domain"] == "environmental")
    climate_entry = next(c for c in view["contributions"] if c["domain"] == "climate")
    assert env_entry["impact"] < 0
    assert climate_entry["impact"] > 0

    # Ranked by impact, strongest drivers first.
    impacts = [c["impact"] for c in view["contributions"]]
    assert impacts == sorted(impacts, reverse=True)

    # Evidence + nine populated domains -> full coverage.
    assert view["coverage"] == 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
