"""Seed script for OSTX Validation Cases + pilot exploration dataset.

Creates offline-ready InvestmentBriefs so judges, investors, and pilots can
explore Signals, Evidence, Reports, Analytics, and Decision Snapshot without
OpenAI credits.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure root workspace directory is in sys.path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from kulima.db import IntelligenceRepository
from kulima.models import (
    AgentResult,
    Claim,
    ConfidenceLevel,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    InvestmentBrief,
    InvestorVote,
    Recommendation,
    RedFlag,
    ScoreDimension,
    SourceAttribution,
    SyndicateDecision,
    ThesisMatchResult,
    ThesisStatus,
    TrustEdge,
    TrustGraph,
    TrustNode,
    UnsupportedClaim,
)

_log = logging.getLogger(__name__)

OSTX_STARTUPS = (
    "AgriNova Malawi",
    "GreenLink Foods",
    "SolarHarvest Cooperative",
)

PILOT_STARTUPS = (
    "NilePay Logistics",
    "FarmStack Kenya",
    "HealthBridge Lagos",
)

DEMO_LIVE_RUN_IDS = {
    "AgriNova Malawi": "ostx-agrinova-malawi",
    "GreenLink Foods": "ostx-greenlink-foods",
    "SolarHarvest Cooperative": "ostx-solarharvest-cooperative",
    "NilePay Logistics": "pilot-nilepay-logistics",
    "FarmStack Kenya": "pilot-farmstack-kenya",
    "HealthBridge Lagos": "pilot-healthbridge-lagos",
}


def _agent(
    name: str,
    summary: str,
    score: float,
    findings: list[str],
    confidence: float = 0.8,
) -> AgentResult:
    return AgentResult(
        agent_name=name,
        summary=summary,
        scores=[
            ScoreDimension(
                name="overall",
                score=score,
                rationale=summary,
                confidence=confidence,
            )
        ],
        findings=findings,
        confidence=confidence,
        raw_reasoning=summary,
    )


def build_agrinova_malawi_brief() -> InvestmentBrief:
    """Demo Startup A — INVEST: AgriNova Malawi (Dr. Chimwemwe Phiri)."""

    sources = [
        SourceAttribution(
            title="Malawi AgTech Sector Report 2025",
            url="https://agtech.mw/reports/2025-agrinova",
            snippet="AgriNova Malawi has onboarded 14,000 smallholder farmer cooperatives across Lilongwe and Blantyre corridors with 42% yield increase.",
            relevance=0.95,
            source_type="report",
            confidence_score=0.92,
        ),
        SourceAttribution(
            title="Dr. Chimwemwe Phiri — Leadership Profile",
            url="https://linkedin.com/in/cphiri-agrinova",
            snippet="Former Senior Agronomist at USAID Southern Africa with 12 years experience scaling solar-powered cold-chain infrastructure.",
            relevance=0.90,
            source_type="profile",
            confidence_score=0.95,
        ),
        SourceAttribution(
            title="USAID Feed the Future Partner Feature",
            url="https://feedthefuture.gov/partners/agrinova-malawi",
            snippet="Audited revenue growth of 310% YoY with $1.2M ARR in digital crop insurance and off-take agreements.",
            relevance=0.92,
            source_type="news",
            confidence_score=0.90,
        ),
        SourceAttribution(
            title="Malawi Ministry of Agriculture Cooperative Registry",
            url="https://agriculture.gov.mw/registries/agrinova",
            snippet="Registered cold-chain operator with active cooperative licenses in Central and Southern Regions.",
            relevance=0.88,
            source_type="registry",
            confidence_score=0.93,
        ),
        SourceAttribution(
            title="Airtel Money Malawi Partner Brief",
            url="https://airtel.mw/partners/agrinova-payouts",
            snippet="Live mobile-money payout integration supporting same-day farmer settlements.",
            relevance=0.84,
            source_type="partner",
            confidence_score=0.86,
        ),
    ]

    ei = EvidenceIntegrityReport(
        integrity_grade=IntegrityGrade.A,
        integrity_score=92.0,
        evidence_depth=EvidenceDepth.COMPREHENSIVE,
        consistency_status=ConsistencyStatus.CLEAN,
        integrity_summary=(
            "Comprehensive OSINT coverage verified across official USAID partner databases, "
            "Malawi Ministry of Agriculture filings, and audited financial summaries."
        ),
        contradictions=[],
        unsupported_claims=[],
        verification_checklist=[
            "Verify mobile money payout API integration with Airtel Money Malawi",
            "Confirm expansion timeline for Northern Region distribution hubs",
        ],
        claim_count=14,
        source_count=12,
        high_authority_count=5,
        web_source_count=10,
        document_source_count=2,
        sparse_mode=False,
        two_axis_label="A",
    )

    red_flags = [
        RedFlag(
            title="Corridor FX Exposure",
            detail="Local currency (MWK) devaluation risk requires structured USD export off-take hedging.",
            severity="MEDIUM",
            mitigation="Structure FX buffer via USD export contracts before Series A.",
        )
    ]

    syndicate = SyndicateDecision(
        final_recommendation=Recommendation.INVEST,
        majority_vote=Recommendation.INVEST,
        consensus_score=88.0,
        dissent_score=12.0,
        average_score=88.0,
        dissent_index=0.12,
        consensus_thesis=(
            "AgriNova exhibits outstanding founder-market fit, proven unit economics under local "
            "market stress, and a clear path to regional scale across SADC."
        ),
        blocking_concerns=["MWK FX volatility on farmer payouts"],
        votes=[
            InvestorVote(
                archetype_id="pan_af",
                investor_name="Pan-African VC Partner",
                firm="Kulima Ventures",
                persona="Pan-African VC Partner",
                decision=Recommendation.INVEST,
                vote=Recommendation.INVEST,
                confidence_score=90.0,
                key_reasoning="Strong unit economics and resilient farmer off-take contracts.",
                major_concern="FX volatility",
            ),
            InvestorVote(
                archetype_id="dfi",
                investor_name="Development Finance Officer",
                firm="Impact Fund",
                persona="Development Finance Officer",
                decision=Recommendation.INVEST,
                vote=Recommendation.INVEST,
                confidence_score=88.0,
                key_reasoning="Outstanding climate resilience impact and gender-inclusive cooperative model.",
                major_concern="Scalability across borders",
            ),
            InvestorVote(
                archetype_id="diaspora",
                investor_name="Diaspora Angel Investor",
                firm="Syndicate Angels",
                persona="Diaspora Angel Investor",
                decision=Recommendation.INVEST,
                vote=Recommendation.INVEST,
                confidence_score=85.0,
                key_reasoning="Operator credibility and deep local trust networks in Malawi.",
                major_concern="Distribution depth",
            ),
            InvestorVote(
                archetype_id="cvc",
                investor_name="Corporate VC Investor",
                firm="AgriCorp Ventures",
                persona="Corporate VC Investor",
                decision=Recommendation.CO_INVEST,
                vote=Recommendation.CO_INVEST,
                confidence_score=82.0,
                key_reasoning="Strategic distribution synergies for regional fertilizer and seed supply chains.",
                major_concern="Supply chain speed",
            ),
            InvestorVote(
                archetype_id="global",
                investor_name="Global Tier-1 VC Partner",
                firm="Global Capital",
                persona="Global Tier-1 VC Partner",
                decision=Recommendation.INVEST,
                vote=Recommendation.INVEST,
                confidence_score=86.0,
                key_reasoning="High capital efficiency with clear Series A momentum.",
                major_concern="TAM ceiling",
            ),
        ],
    )

    trust_graph = TrustGraph(
        nodes=[
            TrustNode(id="founder", label="Dr. Chimwemwe Phiri", node_type="founder", weight=1.2),
            TrustNode(id="company", label="AgriNova Malawi", node_type="company", weight=1.2),
            TrustNode(id="usaid", label="USAID Feed the Future", node_type="institution", weight=1.0),
            TrustNode(id="moa", label="Malawi Ministry of Agriculture", node_type="institution", weight=1.0),
            TrustNode(id="airtel", label="Airtel Money Malawi", node_type="investor", weight=0.9),
        ],
        edges=[
            TrustEdge(source="founder", target="company", relation="founded", strength=0.95, confidence=0.95),
            TrustEdge(source="usaid", target="company", relation="partner", strength=0.9, confidence=0.9),
            TrustEdge(source="moa", target="company", relation="licensed", strength=0.88, confidence=0.92),
            TrustEdge(source="airtel", target="company", relation="payments", strength=0.84, confidence=0.86),
        ],
        trust_score=88.0,
        density=0.72,
        explanation="Dense, high-authority institutional corroboration around founder and operating entity.",
    )

    return InvestmentBrief(
        founder_name="Dr. Chimwemwe Phiri",
        startup_name="AgriNova Malawi",
        sector="AgTech / Supply Chain",
        geography="Malawi / SADC",
        stage="Seed",
        executive_summary=(
            "AgriNova Malawi is an IC-ready AgTech platform delivering solar-powered cold chain and "
            "digital off-take solutions to 14,000+ smallholder farmers. The company demonstrates "
            "$1.2M ARR, 310% YoY revenue growth, and grade-A evidence integrity."
        ),
        founder_assessment=(
            "Dr. Chimwemwe Phiri brings 12+ years of senior agronomic and operational experience. "
            "Outstanding digital footprint and high trust score across regional agricultural networks."
        ),
        startup_assessment=(
            "Validated B2B2C business model with high farmer retention rates, unit-positive margin "
            "structure, and clear competitive moat in solar cold storage."
        ),
        market_assessment=(
            "Addressing a $4.2B post-harvest loss market in Southern Africa, with strong tailwinds "
            "from climate-adaptation financing."
        ),
        risk_assessment=(
            "Low regulatory risk in Malawi; primary risk is MWK currency volatility, mitigated by "
            "planned regional export corridors."
        ),
        investment_recommendation=(
            "INVEST — Allocate $350K Seed check. AgriNova is the lead candidate in the OSTX AgTech cohort."
        ),
        next_steps=[
            "Finalize term sheet for $350K Seed allocation",
            "Complete technical audit of solar cold-storage telemetry hardware",
            "Structure FX buffer mechanism for cross-border revenues",
        ],
        recommendation=Recommendation.INVEST,
        overall_score=86.0,
        founder_score=90.0,
        startup_score=87.0,
        market_score=89.0,
        trust_score=88.0,
        risk_score=22.0,
        growth_potential=88.0,
        investment_readiness=90.0,
        confidence=0.89,
        confidence_level=ConfidenceLevel.HIGH,
        red_flags=red_flags,
        sources=sources,
        evidence_integrity=ei,
        syndicate=syndicate,
        trust_graph=trust_graph,
        thesis_match=ThesisMatchResult(
            overall_match=91.0,
            sector_fit="High",
            stage_fit="High",
            geography_fit="High",
            evidence_fit="High",
            status=ThesisStatus.PASS,
            notes=[
                "AgTech + Seed stage aligns with Kulima thesis",
                "Malawi / SADC geography is priority corridor",
                "Evidence integrity Grade A supports conviction",
            ],
        ),
        explainability=[
            "Trust Score 88 driven by multi-source institutional corroboration",
            "INVEST consensus from 4 of 5 syndicate archetypes",
            "Evidence Integrity Grade A with zero contradictions",
            "Founder score 90 reflects verified USAID operating track record",
        ],
        agent_results={
            "founder": _agent(
                "Founder Intelligence Agent",
                "Strong leadership track record; former USAID agronomy director.",
                90.0,
                [
                    "12+ years senior agronomy and cold-chain ops",
                    "Verified institutional network across SADC",
                    "High digital footprint integrity",
                ],
                0.93,
            ),
            "startup": _agent(
                "Startup Intelligence Agent",
                "Validated market traction with 14,000 smallholders.",
                87.0,
                [
                    "$1.2M ARR with 310% YoY growth",
                    "14,000 cooperative farmers onboarded",
                    "Unit-positive cold-chain economics",
                ],
                0.90,
            ),
            "diligence": _agent(
                "Due Diligence Agent",
                "Clean compliance and verified financial records.",
                88.0,
                [
                    "Ministry registry status confirmed",
                    "USAID partner feature corroborates traction",
                    "Mobile-money payout rails live",
                ],
                0.91,
            ),
            "risk": _agent(
                "Risk Assessment Agent",
                "Low market risk; manageable currency exposure.",
                78.0,
                [
                    "Primary residual risk is MWK FX volatility",
                    "Regulatory exposure remains low",
                    "Hedging path identified via USD off-take",
                ],
                0.86,
            ),
            "memo": _agent(
                "Investment Memo Agent",
                "Partner-grade IC memo complete with recommendation to Invest.",
                86.0,
                [
                    "IC pack ready for $350K Seed allocation",
                    "Clear next-step diligence checklist",
                    "Thesis match 91%",
                ],
                0.89,
            ),
        },
    )


def build_greenlink_foods_brief() -> InvestmentBrief:
    """Demo Startup B — OBSERVE: GreenLink Foods (Kondwani Banda)."""

    sources = [
        SourceAttribution(
            title="GreenLink Foods Company Website",
            url="https://greenlinkfoods.com/about",
            snippet="GreenLink Foods operates urban hydroponic farms in Lusaka, claiming supply agreements with 30 supermarket chains.",
            relevance=0.85,
            source_type="website",
            confidence_score=0.70,
        ),
        SourceAttribution(
            title="Zambia Agribusiness Directory 2024",
            url="https://agrizambia.org/directory/greenlink",
            snippet="Registered agribusiness entity in Lusaka; operational since 2022.",
            relevance=0.80,
            source_type="directory",
            confidence_score=0.75,
        ),
        SourceAttribution(
            title="Lusaka Fresh Produce Market Scan",
            url="https://zamstats.gov.zm/reports/fresh-produce-2024",
            snippet="Urban leafy greens demand rising; controlled-environment growers remain sub-scale.",
            relevance=0.74,
            source_type="report",
            confidence_score=0.72,
        ),
        SourceAttribution(
            title="Founder Interview — Kondwani Banda",
            url="https://techzambia.news/greenlink-banda",
            snippet="Founder cites diesel generator spend as the largest operating cost after labor.",
            relevance=0.78,
            source_type="news",
            confidence_score=0.68,
        ),
    ]

    ei = EvidenceIntegrityReport(
        integrity_grade=IntegrityGrade.C,
        integrity_score=68.0,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=ConsistencyStatus.CONFLICTS,
        integrity_summary=(
            "Moderate evidence depth. Discrepancy detected between self-reported supermarket partner "
            "count (30) and verified distributor listings (12)."
        ),
        contradictions=[
            Contradiction(
                claim_a=Claim(
                    value_raw="30 retail supermarket contracts",
                    source_title="GreenLink Deck",
                    source_url="https://greenlinkfoods.com",
                ),
                claim_b=Claim(
                    value_raw="12 active retail locations",
                    source_title="Zambia Agribusiness Registry",
                    source_url="https://agrizambia.org",
                ),
                severity=ContradictionSeverity.MEDIUM,
                description=(
                    "Claimed 30 retail supermarket contracts; public partner registry lists 12 active "
                    "retail locations."
                ),
                recommended_action="Request signed retail off-take master agreements during diligence.",
            )
        ],
        unsupported_claims=[
            UnsupportedClaim(
                description="Proprietary nutrient solution yield claims lack independent agronomic validation.",
                recommended_action="Obtain third-party lab testing report for crop yields.",
            )
        ],
        verification_checklist=[
            "Verify signed retail contracts with Shoprite and Pick n Pay Zambia",
            "Audit electricity backup infrastructure costs under Lusaka load-shedding",
        ],
        claim_count=12,
        source_count=6,
        high_authority_count=2,
        web_source_count=5,
        document_source_count=1,
        sparse_mode=False,
        two_axis_label="C",
    )

    red_flags = [
        RedFlag(
            title="Power Grid Vulnerability",
            detail="Hydroponic operations highly sensitive to Lusaka electrical load-shedding without solar hybrid backup.",
            severity="HIGH",
            mitigation="Require solar hybrid install milestone before investment.",
        ),
        RedFlag(
            title="Customer Concentration",
            detail="Top 2 buyers account for 65% of monthly produce revenue.",
            severity="MEDIUM",
            mitigation="Expand retail and institutional offtake beyond top two buyers.",
        ),
    ]

    syndicate = SyndicateDecision(
        final_recommendation=Recommendation.OBSERVE,
        majority_vote=Recommendation.OBSERVE,
        consensus_score=62.0,
        dissent_score=28.0,
        average_score=62.0,
        dissent_index=0.28,
        consensus_thesis=(
            "Promising urban agriculture model, but operational risks and customer concentration "
            "require 6 months of observed execution before commitment."
        ),
        blocking_concerns=[
            "Unverified retail contract count",
            "Power reliability / diesel cost drag",
        ],
        votes=[
            InvestorVote(
                archetype_id="pan_af",
                investor_name="Pan-African VC Partner",
                firm="Kulima Ventures",
                persona="Pan-African VC Partner",
                decision=Recommendation.OBSERVE,
                vote=Recommendation.OBSERVE,
                confidence_score=65.0,
                key_reasoning="Margin compression from diesel generator costs under power cuts.",
                major_concern="Power grid load-shedding",
            ),
            InvestorVote(
                archetype_id="dfi",
                investor_name="Development Finance Officer",
                firm="Impact Fund",
                persona="Development Finance Officer",
                decision=Recommendation.INVEST,
                vote=Recommendation.INVEST,
                confidence_score=75.0,
                key_reasoning="Strong urban food security impact.",
                major_concern="Sub-scale production",
            ),
            InvestorVote(
                archetype_id="diaspora",
                investor_name="Diaspora Angel Investor",
                firm="Syndicate Angels",
                persona="Diaspora Angel Investor",
                decision=Recommendation.OBSERVE,
                vote=Recommendation.OBSERVE,
                confidence_score=60.0,
                key_reasoning="Needs proof of scaling beyond initial Lusaka facilities.",
                major_concern="Single city risk",
            ),
            InvestorVote(
                archetype_id="cvc",
                investor_name="Corporate VC Investor",
                firm="AgriCorp Ventures",
                persona="Corporate VC Investor",
                decision=Recommendation.OBSERVE,
                vote=Recommendation.OBSERVE,
                confidence_score=62.0,
                key_reasoning="Retail supply agreements require formal verification.",
                major_concern="Unverified retail contracts",
            ),
            InvestorVote(
                archetype_id="global",
                investor_name="Global Tier-1 VC Partner",
                firm="Global Capital",
                persona="Global Tier-1 VC Partner",
                decision=Recommendation.PASS,
                vote=Recommendation.PASS,
                confidence_score=70.0,
                key_reasoning="Limited total addressable market in current single-city footprint.",
                major_concern="TAM constraint",
            ),
        ],
    )

    return InvestmentBrief(
        founder_name="Kondwani Banda",
        startup_name="GreenLink Foods",
        sector="Urban Agriculture / AgTech",
        geography="Zambia",
        stage="Pre-Seed",
        executive_summary=(
            "GreenLink Foods operates commercial hydroponic farms supplying fresh produce in Zambia. "
            "While the revenue model is active, evidence contradictions in retail distribution and "
            "energy cost sensitivity place the deal in OBSERVE status."
        ),
        founder_assessment=(
            "Kondwani Banda has solid local operator experience in fresh produce logistics, but lacks "
            "formal venture scaling background."
        ),
        startup_assessment=(
            "Controlled-environment agriculture model with potential high yield, but currently "
            "constrained by power grid reliability in Lusaka."
        ),
        market_assessment=(
            "Addressing $120M urban fresh produce market in Zambia with expansion potential into DRC "
            "mining corridors."
        ),
        risk_assessment=(
            "High operational exposure to power grid instability and moderate evidence inconsistency "
            "regarding retail off-take numbers."
        ),
        investment_recommendation=(
            "OBSERVE — Place on 6-month watch milestone list. Track solar transition and retail "
            "contract expansion."
        ),
        next_steps=[
            "Set 90-day tracking milestone for solar hybrid installation",
            "Re-evaluate upon submission of audited 2025 H1 financial statements",
        ],
        recommendation=Recommendation.OBSERVE,
        overall_score=62.0,
        founder_score=65.0,
        startup_score=60.0,
        market_score=66.0,
        trust_score=64.0,
        risk_score=48.0,
        growth_potential=65.0,
        investment_readiness=58.0,
        confidence=0.72,
        confidence_level=ConfidenceLevel.MEDIUM,
        red_flags=red_flags,
        sources=sources,
        evidence_integrity=ei,
        syndicate=syndicate,
        trust_graph=TrustGraph(
            nodes=[
                TrustNode(id="founder", label="Kondwani Banda", node_type="founder", weight=0.9),
                TrustNode(id="company", label="GreenLink Foods", node_type="company", weight=0.9),
                TrustNode(id="registry", label="Zambia Agribusiness Registry", node_type="institution", weight=0.8),
            ],
            edges=[
                TrustEdge(source="founder", target="company", relation="founded", strength=0.8, confidence=0.75),
                TrustEdge(source="registry", target="company", relation="listed", strength=0.7, confidence=0.72),
            ],
            trust_score=64.0,
            density=0.41,
            explanation="Moderate graph density with unresolved retail partner conflict.",
        ),
        thesis_match=ThesisMatchResult(
            overall_match=74.0,
            sector_fit="High",
            stage_fit="High",
            geography_fit="Medium",
            evidence_fit="Medium",
            status=ThesisStatus.WARN,
            notes=[
                "Sector fit is strong, but evidence conflicts reduce conviction",
                "Watch milestones required before capital commitment",
            ],
        ),
        explainability=[
            "OBSERVE driven by retail contract contradiction and power risk",
            "Trust Score 64 reflects mixed corroboration quality",
            "Syndicate dissent 28% — DFI bullish, Global Tier-1 cautious",
            "Integrity Grade C blocks INVEST until verification closes",
        ],
        agent_results={
            "founder": _agent(
                "Founder Intelligence Agent",
                "Operator with local distribution experience.",
                65.0,
                ["Local logistics credibility", "Limited venture scaling track record"],
                0.70,
            ),
            "startup": _agent(
                "Startup Intelligence Agent",
                "Hydroponic production active; power grid dependent.",
                60.0,
                ["Active Lusaka production", "Diesel cost drag under load-shedding"],
                0.68,
            ),
            "diligence": _agent(
                "Due Diligence Agent",
                "Contract verification gaps in retail off-take.",
                62.0,
                ["30 vs 12 retail partner conflict", "Need signed offtake agreements"],
                0.71,
            ),
            "risk": _agent(
                "Risk Assessment Agent",
                "Moderate-high risk from power reliability and revenue concentration.",
                52.0,
                ["Top-2 buyers = 65% revenue", "Grid instability is structural"],
                0.74,
            ),
            "memo": _agent(
                "Investment Memo Agent",
                "Recommendation to Observe pending operational milestones.",
                62.0,
                ["6-month watchlist", "Solar hybrid is gating milestone"],
                0.72,
            ),
        },
    )


def build_solarharvest_cooperative_brief() -> InvestmentBrief:
    """Demo Startup C — PASS: SolarHarvest Cooperative (Blessings Mtonga)."""

    sources = [
        SourceAttribution(
            title="Single Page Promo Deck",
            url="https://drive.google.com/solarharvest-deck",
            snippet="SolarHarvest claims $3M seed valuation and exclusive government mini-grid contracts across rural Mozambique.",
            relevance=0.60,
            source_type="deck",
            confidence_score=0.40,
        ),
        SourceAttribution(
            title="ARENE Public Gazette Search Result",
            url="https://arene.gov.mz/gazette",
            snippet="No mini-grid concession registration found matching SolarHarvest Cooperative.",
            relevance=0.88,
            source_type="registry",
            confidence_score=0.85,
        ),
    ]

    ei = EvidenceIntegrityReport(
        integrity_grade=IntegrityGrade.F,
        integrity_score=34.0,
        evidence_depth=EvidenceDepth.THIN,
        consistency_status=ConsistencyStatus.MAJOR_CONFLICTS,
        integrity_summary=(
            "Sparse evidence corpus. Unverified claims regarding government mini-grid concessions "
            "and missing corporate regulatory filings."
        ),
        contradictions=[
            Contradiction(
                claim_a=Claim(
                    value_raw="Exclusive government mini-grid concession in Mozambique",
                    source_title="SolarHarvest Pitch Deck",
                    source_url="https://drive.google.com/solarharvest-deck",
                ),
                claim_b=Claim(
                    value_raw="No mini-grid concession registration found for SolarHarvest",
                    source_title="ARENE Public Gazette 2025",
                    source_url="https://arene.gov.mz/gazette",
                ),
                severity=ContradictionSeverity.HIGH,
                description=(
                    "Government mini-grid concession claim could not be corroborated in Mozambique "
                    "Energy Regulatory Authority (ARENE) public gazette."
                ),
                recommended_action="Require certified ARENE concession license document.",
            )
        ],
        unsupported_claims=[
            UnsupportedClaim(
                description="Claimed 5,000 active prepaid solar pump subscribers cannot be verified via public or partner channels.",
                recommended_action="Conduct direct site audit of subscriber base.",
            ),
            UnsupportedClaim(
                description="Unverified financial statements and lack of independent auditor review.",
                recommended_action="Require external CPA financial audit.",
            ),
        ],
        verification_checklist=[
            "Request official ARENE concession license documentation",
            "Perform legal search on corporate entity registration status",
        ],
        claim_count=10,
        source_count=2,
        high_authority_count=1,
        web_source_count=2,
        document_source_count=0,
        sparse_mode=True,
        two_axis_label="D",
    )

    red_flags = [
        RedFlag(
            title="Unverified Concession Claims",
            detail="Core asset (government mini-grid concession) is absent from official regulatory records.",
            severity="CRITICAL",
            mitigation="Do not proceed without certified concession documents.",
        ),
        RedFlag(
            title="Corporate Registration Gap",
            detail="Entity operates without verified commercial registry status in primary jurisdiction.",
            severity="CRITICAL",
            mitigation="Require full corporate registry package before any further review.",
        ),
        RedFlag(
            title="Severe Evidence Integrity Deficit",
            detail="Reliability rating Grade F (34/100) indicates high risk of fabricated traction metrics.",
            severity="HIGH",
            mitigation="Independent site and document audit required.",
        ),
    ]

    syndicate = SyndicateDecision(
        final_recommendation=Recommendation.PASS,
        majority_vote=Recommendation.PASS,
        consensus_score=28.0,
        dissent_score=5.0,
        average_score=28.0,
        dissent_index=0.05,
        consensus_thesis=(
            "Unanimous PASS recommendation due to unverified regulatory concessions, severe evidence "
            "gaps, and high risk profile."
        ),
        blocking_concerns=[
            "Missing ARENE concession",
            "Unverified corporate registration",
            "Grade F evidence integrity",
        ],
        votes=[
            InvestorVote(
                archetype_id="pan_af",
                investor_name="Pan-African VC Partner",
                firm="Kulima Ventures",
                persona="Pan-African VC Partner",
                decision=Recommendation.PASS,
                vote=Recommendation.PASS,
                confidence_score=85.0,
                key_reasoning="Unverified regulatory concessions pose fatal execution risk.",
                major_concern="Unverified concession license",
            ),
            InvestorVote(
                archetype_id="dfi",
                investor_name="Development Finance Officer",
                firm="Impact Fund",
                persona="Development Finance Officer",
                decision=Recommendation.PASS,
                vote=Recommendation.PASS,
                confidence_score=90.0,
                key_reasoning="Governance and registration gaps prevent institutional participation.",
                major_concern="Regulatory compliance gap",
            ),
            InvestorVote(
                archetype_id="diaspora",
                investor_name="Diaspora Angel Investor",
                firm="Syndicate Angels",
                persona="Diaspora Angel Investor",
                decision=Recommendation.PASS,
                vote=Recommendation.PASS,
                confidence_score=80.0,
                key_reasoning="Lack of verifiable local footprint.",
                major_concern="Uncorroborated footprint",
            ),
            InvestorVote(
                archetype_id="cvc",
                investor_name="Corporate VC Investor",
                firm="AgriCorp Ventures",
                persona="Corporate VC Investor",
                decision=Recommendation.PASS,
                vote=Recommendation.PASS,
                confidence_score=82.0,
                key_reasoning="Unsubstantiated partnership claims.",
                major_concern="Fake partnerships",
            ),
            InvestorVote(
                archetype_id="global",
                investor_name="Global Tier-1 VC Partner",
                firm="Global Capital",
                persona="Global Tier-1 VC Partner",
                decision=Recommendation.PASS,
                vote=Recommendation.PASS,
                confidence_score=88.0,
                key_reasoning="Fails basic diligence and compliance thresholds.",
                major_concern="Diligence failure",
            ),
        ],
    )

    return InvestmentBrief(
        founder_name="Blessings Mtonga",
        startup_name="SolarHarvest Cooperative",
        sector="CleanEnergy / Off-Grid",
        geography="Mozambique",
        stage="Pre-Seed",
        executive_summary=(
            "SolarHarvest Cooperative purports to operate rural solar mini-grids in Mozambique. Due "
            "to critical evidence gaps, unverified concession licenses, and Grade F reliability, the "
            "investment committee recommendation is PASS."
        ),
        founder_assessment=(
            "Founder background cannot be independently verified across regional operator databases "
            "or professional registries."
        ),
        startup_assessment=(
            "Unsubstantiated subscriber and revenue metrics; lacks physical hardware telemetry validation."
        ),
        market_assessment=(
            "Off-grid energy market opportunity is significant, but startup lacks verified license to operate."
        ),
        risk_assessment="Critical governance, legal, and evidence integrity risks.",
        investment_recommendation="PASS — Decline deal. Critical verification failures and unverified concessions.",
        next_steps=[
            "Issue formal pass notification",
            "Archive deal in intelligence repository under PASS status",
        ],
        recommendation=Recommendation.PASS,
        overall_score=28.0,
        founder_score=30.0,
        startup_score=26.0,
        market_score=45.0,
        trust_score=32.0,
        risk_score=78.0,
        growth_potential=35.0,
        investment_readiness=22.0,
        confidence=0.45,
        confidence_level=ConfidenceLevel.LOW,
        red_flags=red_flags,
        sources=sources,
        evidence_integrity=ei,
        syndicate=syndicate,
        trust_graph=TrustGraph(
            nodes=[
                TrustNode(id="founder", label="Blessings Mtonga", node_type="founder", weight=0.4),
                TrustNode(id="company", label="SolarHarvest Cooperative", node_type="company", weight=0.4),
                TrustNode(id="arene", label="ARENE Gazette", node_type="institution", weight=1.0),
            ],
            edges=[
                TrustEdge(source="founder", target="company", relation="claims_founded", strength=0.3, confidence=0.35),
                TrustEdge(source="arene", target="company", relation="no_concession_found", strength=0.2, confidence=0.85),
            ],
            trust_score=32.0,
            density=0.18,
            explanation="Sparse trust graph with regulatory non-corroboration on core asset claim.",
        ),
        thesis_match=ThesisMatchResult(
            overall_match=38.0,
            sector_fit="Medium",
            stage_fit="High",
            geography_fit="Medium",
            evidence_fit="Low",
            status=ThesisStatus.BLOCK,
            notes=[
                "Evidence integrity failure blocks thesis passage",
                "Regulatory asset claim unverified",
            ],
        ),
        explainability=[
            "PASS driven by Grade F integrity and missing concession proof",
            "Trust Score 32 — below investable threshold",
            "Unanimous syndicate PASS with low dissent",
            "Sparse evidence corpus triggers limited-coverage disclosure",
        ],
        agent_results={
            "founder": _agent(
                "Founder Intelligence Agent",
                "Unverified professional background.",
                30.0,
                ["No corroborating professional registry hits", "Claims cannot be independently verified"],
                0.40,
            ),
            "startup": _agent(
                "Startup Intelligence Agent",
                "Sparse traction evidence; unverified telemetry.",
                26.0,
                ["Subscriber claims unsupported", "No hardware telemetry validation"],
                0.38,
            ),
            "diligence": _agent(
                "Due Diligence Agent",
                "Multiple critical red flags in legal and concession status.",
                25.0,
                ["ARENE concession absent", "Corporate registry gap"],
                0.42,
            ),
            "risk": _agent(
                "Risk Assessment Agent",
                "High risk across legal, regulatory, and financial dimensions.",
                22.0,
                ["Critical governance risk", "Fabrication risk elevated"],
                0.55,
            ),
            "memo": _agent(
                "Investment Memo Agent",
                "Recommendation to Pass.",
                28.0,
                ["Decline and archive", "Do not advance to IC"],
                0.45,
            ),
        },
    )


def build_nilepay_logistics_brief() -> InvestmentBrief:
    """Pilot exploration case — OBSERVE / logistics."""
    return InvestmentBrief(
        founder_name="Amina Okello",
        startup_name="NilePay Logistics",
        sector="FinTech / Logistics",
        geography="Uganda / East Africa",
        stage="Seed",
        executive_summary=(
            "NilePay Logistics digitizes SME freight payments along the Kampala–Nairobi corridor. "
            "Early traction is real but documentation depth is still building."
        ),
        founder_assessment="Operator-founder with 8 years freight brokerage experience.",
        startup_assessment="Working payments product with 180 active SME shippers.",
        market_assessment="Corridor logistics payments remain cash-heavy and high-friction.",
        risk_assessment="Moderate regulatory and partner-bank onboarding risk.",
        investment_recommendation="OBSERVE — Track bank partnership conversion over next quarter.",
        next_steps=["Confirm Tier-1 bank settlement MoU", "Expand Nairobi lane volume"],
        recommendation=Recommendation.OBSERVE,
        overall_score=58.0,
        founder_score=70.0,
        startup_score=55.0,
        market_score=72.0,
        trust_score=61.0,
        risk_score=44.0,
        growth_potential=68.0,
        investment_readiness=54.0,
        confidence=0.66,
        confidence_level=ConfidenceLevel.MEDIUM,
        sources=[
            SourceAttribution(
                title="NilePay Product Page",
                url="https://nilepay.ug",
                snippet="Corridor SME freight payments with mobile settlement.",
                relevance=0.8,
                source_type="website",
                confidence_score=0.7,
            )
        ],
        evidence_integrity=EvidenceIntegrityReport(
            integrity_grade=IntegrityGrade.B,
            integrity_score=74.0,
            evidence_depth=EvidenceDepth.MODERATE,
            consistency_status=ConsistencyStatus.CLEAN,
            integrity_summary="Moderate corroboration; bank MoU still pending.",
            claim_count=8,
            source_count=5,
            high_authority_count=1,
        ),
        red_flags=[
            RedFlag(
                title="Bank Settlement Dependency",
                detail="Growth assumes Tier-1 bank MoU that is not yet signed.",
                severity="MEDIUM",
            )
        ],
        thesis_match=ThesisMatchResult(
            overall_match=78.0,
            sector_fit="High",
            stage_fit="High",
            geography_fit="High",
            evidence_fit="Medium",
            status=ThesisStatus.WARN,
            notes=["Strong thesis fit; waiting on bank MoU evidence"],
        ),
        explainability=[
            "Useful pilot exploration case for FinTech corridor thesis",
            "Not an OSTX validation extreme — mid-pack OBSERVE profile",
        ],
        agent_results={
            "founder": _agent("Founder Intelligence Agent", "Experienced freight operator.", 70.0, ["8 years brokerage"], 0.7),
            "startup": _agent("Startup Intelligence Agent", "180 SME shippers live.", 55.0, ["Early corridor traction"], 0.65),
            "diligence": _agent("Due Diligence Agent", "Bank MoU pending.", 58.0, ["Settlement dependency"], 0.66),
            "risk": _agent("Risk Assessment Agent", "Moderate regulatory risk.", 50.0, ["Partner-bank dependency"], 0.64),
            "memo": _agent("Investment Memo Agent", "Observe pending bank conversion.", 58.0, ["Quarterly milestone"], 0.66),
        },
    )


def build_farmstack_kenya_brief() -> InvestmentBrief:
    """Pilot exploration case — CO-INVEST / AgTech input marketplace."""
    return InvestmentBrief(
        founder_name="Grace Wanjiku",
        startup_name="FarmStack Kenya",
        sector="AgTech",
        geography="Kenya",
        stage="Seed",
        executive_summary=(
            "FarmStack Kenya aggregates farm inputs for county cooperatives with verified inventory "
            "partners and improving unit economics."
        ),
        founder_assessment="Strong Kenyan operator with prior SACCO distribution experience.",
        startup_assessment="Growing GMV with repeat cooperative buyers.",
        market_assessment="Input distribution fragmentation creates clear marketplace wedge.",
        risk_assessment="Working-capital intensity and supplier concentration are key watch items.",
        investment_recommendation="CO-INVEST — Attractive lead-follow candidate with local lead.",
        next_steps=["Validate supplier concentration", "Confirm working-capital facility terms"],
        recommendation=Recommendation.CO_INVEST,
        overall_score=74.0,
        founder_score=80.0,
        startup_score=72.0,
        market_score=78.0,
        trust_score=76.0,
        risk_score=35.0,
        growth_potential=80.0,
        investment_readiness=73.0,
        confidence=0.78,
        confidence_level=ConfidenceLevel.HIGH,
        sources=[
            SourceAttribution(
                title="FarmStack Kenya Traction Note",
                url="https://farmstack.ke/traction",
                snippet="County cooperative GMV expanding across Central and Rift.",
                relevance=0.86,
                source_type="website",
                confidence_score=0.8,
            ),
            SourceAttribution(
                title="Kenya Cooperative Alliance Directory",
                url="https://cooperative.go.ke/directory",
                snippet="Listed input aggregator serving registered cooperatives.",
                relevance=0.8,
                source_type="directory",
                confidence_score=0.82,
            ),
        ],
        evidence_integrity=EvidenceIntegrityReport(
            integrity_grade=IntegrityGrade.B,
            integrity_score=81.0,
            evidence_depth=EvidenceDepth.RICH,
            consistency_status=ConsistencyStatus.CLEAN,
            integrity_summary="Solid corroboration; working-capital terms still diligence-sensitive.",
            claim_count=10,
            source_count=7,
            high_authority_count=2,
        ),
        thesis_match=ThesisMatchResult(
            overall_match=86.0,
            sector_fit="High",
            stage_fit="High",
            geography_fit="High",
            evidence_fit="High",
            status=ThesisStatus.PASS,
            notes=["Strong Kenya AgTech thesis alignment"],
        ),
        explainability=[
            "CO-INVEST profile for syndicate follow-on narrative",
            "Useful contrast against AgriNova INVEST flagship",
        ],
        agent_results={
            "founder": _agent("Founder Intelligence Agent", "Strong SACCO distribution background.", 80.0, ["Operator credibility"], 0.82),
            "startup": _agent("Startup Intelligence Agent", "Repeat cooperative demand.", 72.0, ["GMV growth"], 0.78),
            "diligence": _agent("Due Diligence Agent", "Supplier concentration diligence open.", 74.0, ["Working capital watch"], 0.77),
            "risk": _agent("Risk Assessment Agent", "Manageable capital-intensity risk.", 62.0, ["Facility terms pending"], 0.75),
            "memo": _agent("Investment Memo Agent", "Co-invest with local lead.", 74.0, ["Follow structure preferred"], 0.78),
        },
    )


def build_healthbridge_lagos_brief() -> InvestmentBrief:
    """Pilot exploration case — PASS / thin evidence."""
    return InvestmentBrief(
        founder_name="Tunde Adeyemi",
        startup_name="HealthBridge Lagos",
        sector="HealthTech",
        geography="Nigeria",
        stage="Pre-Seed",
        executive_summary=(
            "HealthBridge Lagos claims clinic SaaS traction across Lagos Island, but public evidence "
            "is thin and clinic references are unverified."
        ),
        founder_assessment="Limited public footprint; claims are difficult to corroborate.",
        startup_assessment="Product narrative exists; customer evidence is sparse.",
        market_assessment="Clinic digitization market is large, but this case lacks proof points.",
        risk_assessment="High diligence risk due to sparse and unverified claims.",
        investment_recommendation="PASS — Insufficient evidence for IC advancement.",
        next_steps=["Request clinic reference calls", "Require usage telemetry export"],
        recommendation=Recommendation.PASS,
        overall_score=34.0,
        founder_score=40.0,
        startup_score=32.0,
        market_score=60.0,
        trust_score=36.0,
        risk_score=70.0,
        growth_potential=48.0,
        investment_readiness=30.0,
        confidence=0.42,
        confidence_level=ConfidenceLevel.LOW,
        sources=[
            SourceAttribution(
                title="HealthBridge One-Pager",
                url="https://healthbridge.ng/deck",
                snippet="Claims 120 clinics; no independent confirmation available.",
                relevance=0.55,
                source_type="deck",
                confidence_score=0.35,
            )
        ],
        evidence_integrity=EvidenceIntegrityReport(
            integrity_grade=IntegrityGrade.D,
            integrity_score=41.0,
            evidence_depth=EvidenceDepth.THIN,
            consistency_status=ConsistencyStatus.CLEAN,
            integrity_summary="Thin corpus; clinic count unsupported.",
            unsupported_claims=[
                UnsupportedClaim(
                    description="Claimed 120 clinic customers lack referenceable confirmation.",
                    recommended_action="Require signed customer references.",
                )
            ],
            claim_count=6,
            source_count=1,
            high_authority_count=0,
            sparse_mode=True,
        ),
        red_flags=[
            RedFlag(
                title="Unsupported Customer Count",
                detail="Clinic traction claim lacks independent corroboration.",
                severity="HIGH",
            )
        ],
        thesis_match=ThesisMatchResult(
            overall_match=52.0,
            sector_fit="High",
            stage_fit="High",
            geography_fit="High",
            evidence_fit="Low",
            status=ThesisStatus.BLOCK,
            notes=["Evidence depth too thin for thesis passage"],
        ),
        explainability=[
            "Second PASS example for judges beyond SolarHarvest",
            "Shows sparse-mode disclosure without regulatory contradiction drama",
        ],
        agent_results={
            "founder": _agent("Founder Intelligence Agent", "Thin public footprint.", 40.0, ["Hard to corroborate"], 0.4),
            "startup": _agent("Startup Intelligence Agent", "Claims exceed evidence.", 32.0, ["No clinic references"], 0.38),
            "diligence": _agent("Due Diligence Agent", "Insufficient diligence package.", 30.0, ["Sparse corpus"], 0.4),
            "risk": _agent("Risk Assessment Agent", "High evidence risk.", 28.0, ["Unsupported traction"], 0.45),
            "memo": _agent("Investment Memo Agent", "Pass until references arrive.", 34.0, ["Do not advance"], 0.42),
        },
    )


def _register_live_run(db_id: int, startup_name: str, db_path: str | None = None) -> str:
    """Create a stable api_runs deep-link for Flex / Signals URL sync."""
    from backend.app.services.run_repository import RunRepository

    live_id = DEMO_LIVE_RUN_IDS.get(startup_name, f"demo-{db_id}")
    run_repo = RunRepository(db_path=db_path)
    run_repo.create_run(live_id, status="completed", user_id=None)
    run_repo.update_run_completed(live_id, db_id=db_id)
    return live_id


def _delete_existing_by_names(repo: IntelligenceRepository, names: tuple[str, ...]) -> int:
    existing = repo.recent_runs(limit=500, include_archived=True)
    deleted = 0
    wanted = {n.lower().strip() for n in names}
    for row in existing:
        name = str(row.get("startup_name") or "").lower().strip()
        if name in wanted and row.get("id") is not None:
            if repo.delete_run(int(row["id"])):
                deleted += 1
    return deleted


def _archive_non_demo_runs(repo: IntelligenceRepository) -> int:
    keep = {n.lower() for n in OSTX_STARTUPS + PILOT_STARTUPS}
    archived = 0
    for row in repo.recent_runs(limit=500, include_archived=False):
        name = str(row.get("startup_name") or "").lower().strip()
        if name not in keep and row.get("id") is not None:
            if repo.archive_run(int(row["id"])):
                archived += 1
    return archived


def seed_ostx_demo_dataset(
    db_path: str | None = None,
    *,
    refresh: bool = False,
    include_pilot_pack: bool = True,
    prepare_demo: bool = False,
) -> list[int]:
    """Seed OSTX Validation Cases (and optional pilot exploration pack)."""

    repo = IntelligenceRepository(db_path=db_path)
    briefs = [
        build_agrinova_malawi_brief(),
        build_greenlink_foods_brief(),
        build_solarharvest_cooperative_brief(),
    ]
    if include_pilot_pack:
        briefs.extend(
            [
                build_nilepay_logistics_brief(),
                build_farmstack_kenya_brief(),
                build_healthbridge_lagos_brief(),
            ]
        )

    target_names = tuple(b.startup_name for b in briefs)
    if refresh:
        removed = _delete_existing_by_names(repo, target_names)
        _log.info("Refresh mode removed %d existing demo rows before re-seed.", removed)

    if prepare_demo:
        archived = _archive_non_demo_runs(repo)
        _log.info("Archived %d non-demo runs for cleaner investor analytics.", archived)

    saved_ids: list[int] = []
    existing_runs = repo.recent_runs(limit=200, include_archived=True)
    existing_startups = {str(r.get("startup_name")).lower().strip() for r in existing_runs}

    for brief in briefs:
        name_key = brief.startup_name.lower().strip()
        if name_key in existing_startups and not refresh:
            _log.info("Demo run for %s already exists — skipping duplicate insert.", brief.startup_name)
            # Still ensure live-run deep link exists for URL sync demos.
            for row in existing_runs:
                if str(row.get("startup_name")).lower().strip() == name_key and row.get("id"):
                    live_id = _register_live_run(int(row["id"]), brief.startup_name, db_path=db_path)
                    _log.info("Ensured live demo link %s -> db_id=%s", live_id, row["id"])
                    break
            continue

        run_id = repo.save_brief(brief, user_id=None)
        live_id = _register_live_run(run_id, brief.startup_name, db_path=db_path)
        saved_ids.append(run_id)
        _log.info(
            "Seeded demo run #%d (%s) as %s [%s]",
            run_id,
            brief.startup_name,
            live_id,
            brief.recommendation.value,
        )

    return saved_ids


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Seed OSTX + pilot demo dataset")
    parser.add_argument("--refresh", action="store_true", help="Replace existing demo startups")
    parser.add_argument("--prepare-demo", action="store_true", help="Archive non-demo runs for clean analytics")
    parser.add_argument("--ostx-only", action="store_true", help="Seed only the 3 OSTX validation cases")
    args = parser.parse_args()
    ids = seed_ostx_demo_dataset(
        refresh=args.refresh,
        include_pilot_pack=not args.ostx_only,
        prepare_demo=args.prepare_demo,
    )
    print(f"OSTX Demo Dataset seeded successfully! New Run IDs: {ids}")
