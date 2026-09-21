"""Tests for the 9 Signal Domains and Document/Tavily Extraction."""

import pytest
from kulima.core.cases.models import Case, CaseSubject, CaseType
from kulima.models import SourceAttribution, TrustGraph
from kulima.signals.models import SignalCategory, SignalLevel
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.rules import generate_signals_from_case


def _create_sample_case(sources=None, uploaded_evidence=None, trust_score=85.0):
    subject = CaseSubject(name="AgriNova CleanTech", secondary_name="Dr. Chim Phiri", sector="AgriTech", region="Malawi")
    payload = {
        "investment_brief": {
            "startup_name": "AgriNova CleanTech",
            "founder_name": "Dr. Chim Phiri",
            "uploaded_evidence": uploaded_evidence or [],
            "executive_summary": "AgriNova deploys solar-powered cold storage and irrigation for smallholder farmers.",
        }
    }
    graph = TrustGraph(trust_score=trust_score, density=0.4)
    return Case(
        id="case-test-domain-signals",
        case_type=CaseType.INVESTMENT,
        subject=subject,
        sources=sources or [],
        trust_graph=graph,
        payload=payload,
    )


def test_nine_domains_generated():
    case = _create_sample_case()
    orch = SignalsOrchestrator()
    signals = orch.generate(case)

    categories = {s.category for s in signals}
    # Verify all 9 requested domains are present
    expected_domains = {
        SignalCategory.TRUST,
        SignalCategory.RISK,
        SignalCategory.MARKET,
        SignalCategory.FUNDING,
        SignalCategory.COMPETITIVE,
        SignalCategory.CLIMATE,
        SignalCategory.ENVIRONMENTAL,
        SignalCategory.TOURISM,
        SignalCategory.COMMUNITY_IMPACT,
    }
    for dom in expected_domains:
        assert dom in categories, f"Missing domain {dom} in generated signals"


def test_climate_signals_from_uploaded_document():
    doc = {
        "id": "doc-climate-01",
        "filename": "Solar_Irrigation_Feasibility_Report.pdf",
        "raw_summary": "Document details off-grid solar installation and carbon offset certification.",
        "evidence_items": ["Solar irrigation units installed across 40 cooperatives", "Carbon emissions reduced by 400MT CO2e"],
        "signals_generated": ["Opportunity: Verified clean energy deployment"],
        "trust_breakdown": {"final_trust_score": 92.0},
    }
    case = _create_sample_case(uploaded_evidence=[doc])
    signals = generate_signals_from_case(case, None, None)

    climate_signals = [s for s in signals if s.category == SignalCategory.CLIMATE]
    assert len(climate_signals) >= 1
    sig = climate_signals[0]
    assert sig.direction == "opportunity"
    assert any("DOC:" in r for r in sig.evidence_refs)
    assert sig.metadata.get("source_type") == "document"


def test_tourism_signals_from_tavily_research():
    tavily_source = SourceAttribution(
        title="Lake Malawi Eco-Tourism and Agro-Travel Corridors",
        url="https://techcabal.com/2025/lake-malawi-eco-tourism",
        snippet="Agro-tourism and hospitality lodges in Malawi source fresh produce directly from local solar cold hubs.",
        relevance=0.88,
        source_type="web",
        confidence_score=0.82,
    )
    case = _create_sample_case(sources=[tavily_source])
    signals = generate_signals_from_case(case, None, None)

    tourism_signals = [s for s in signals if s.category == SignalCategory.TOURISM]
    assert len(tourism_signals) >= 1
    sig = tourism_signals[0]
    assert sig.direction == "opportunity"
    assert any("TAVILY:" in r for r in sig.evidence_refs)
    assert sig.metadata.get("source_type") == "tavily"


def test_community_impact_signals_from_smallholders():
    tavily_source = SourceAttribution(
        title="Smallholder Farmer Yield Improvement",
        url="https://disrupt-africa.com/agrinova-smallholders",
        snippet="Over 2,500 smallholder farmers, 60% female, improved household income by 35% through cooperative membership.",
        relevance=0.9,
        source_type="web",
        confidence_score=0.85,
    )
    case = _create_sample_case(sources=[tavily_source])
    signals = generate_signals_from_case(case, None, None)

    impact_signals = [s for s in signals if s.category == SignalCategory.COMMUNITY_IMPACT]
    assert len(impact_signals) >= 1
    sig = impact_signals[0]
    assert sig.direction == "opportunity"
    assert sig.level in (SignalLevel.HIGH, SignalLevel.MEDIUM)
