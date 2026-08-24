"""Shared domain models for the Kulima Investment Intelligence OS."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Recommendation(str, Enum):
    INVEST = "Invest"
    OBSERVE = "Observe"
    PASS = "Pass"
    CO_INVEST = "Co-Invest"
    FOLLOW_ON_WATCH = "Follow-On Watch"


class ConfidenceLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    VERY_HIGH = "Very High"


class SourceAttribution(BaseModel):
    title: str
    url: str
    snippet: str = ""
    relevance: float = 0.0
    source_type: str = "web"
    confidence_score: float = Field(ge=0, le=1, default=0.5)


class ScoreDimension(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)
    rationale: str
    confidence: float = Field(ge=0, le=1, default=0.6)
    evidence_ids: list[int] = Field(default_factory=list)


class RedFlag(BaseModel):
    severity: str  # critical | high | medium | low
    title: str
    detail: str
    mitigation: str = ""
    confidence: float = Field(ge=0, le=1, default=0.7)


class AgentResult(BaseModel):
    agent_name: str
    summary: str
    scores: list[ScoreDimension] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    sources: list[SourceAttribution] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.5)
    raw_reasoning: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrustNode(BaseModel):
    id: str
    label: str
    node_type: str  # founder | company | investor | institution | media | market
    weight: float = 1.0


class TrustEdge(BaseModel):
    source: str
    target: str
    relation: str
    strength: float = Field(ge=0, le=1, default=0.5)
    # Origin of this relationship in the evidence corpus: e.g. "web", "document",
    # or "llm_inferred". Defaults to "web" for backwards compatibility.
    source_type: str = "web"
    # Confidence in this edge as a trust signal (0–1). Existing edges default to 0.5.
    confidence: float = Field(ge=0, le=1, default=0.5)


class TrustGraph(BaseModel):
    nodes: list[TrustNode] = Field(default_factory=list)
    edges: list[TrustEdge] = Field(default_factory=list)
    trust_score: float = 0.0
    density: float = 0.0
    explanation: str = ""


class InvestorVote(BaseModel):
    archetype_id: str
    investor_name: str
    firm: str
    persona: str
    title: str = ""
    # Hackathon ballot fields
    decision: Recommendation = Recommendation.OBSERVE
    confidence_score: float = Field(ge=0, le=100, default=50)
    key_reasoning: str = ""
    major_concern: str = ""
    # Backward-compatible aliases used elsewhere in the OS
    vote: Recommendation = Recommendation.OBSERVE
    conviction: float = Field(ge=0, le=1, default=0.5)
    score: float = Field(ge=0, le=100, default=50)
    thesis: str = ""
    concerns: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)


class SyndicateDecision(BaseModel):
    votes: list[InvestorVote]
    majority_vote: Recommendation
    average_score: float
    dissent_index: float
    # Explicit hackathon committee metrics
    consensus_score: float = 0.0
    final_recommendation: Recommendation = Recommendation.OBSERVE
    dissent_score: float = 0.0
    debate_transcript: str = ""
    consensus_thesis: str = ""
    blocking_concerns: list[str] = Field(default_factory=list)


class TrajectoryScenario(BaseModel):
    name: str
    emoji: str = ""
    # Hackathon Continental Futures fields
    success_probability: float = Field(ge=0, le=100, default=50)
    revenue_growth_outlook: str = ""
    investor_attractiveness_score: float = Field(ge=0, le=100, default=50)
    major_risks: list[str] = Field(default_factory=list)
    key_opportunities: list[str] = Field(default_factory=list)
    # Legacy / complementary fields (kept for charts & EV)
    probability: float = 0.0
    revenue_36m_usd: float = 0.0
    valuation_36m_usd: float = 0.0
    survival_probability: float = 0.0
    narrative: str = ""
    key_drivers: list[str] = Field(default_factory=list)


class FutureSimulation(BaseModel):
    scenarios: list[TrajectoryScenario]
    expected_value_usd: float = 0.0
    downside_case: str = ""
    upside_case: str = ""
    africa_risk_premium: float = 0.0
    simulation_notes: str = ""
    most_likely_case: str = ""
    africa_conditions_summary: str = ""


# ── Trust Layer / Evidence Integrity Engine models ───────────────────────────
# All fields carry None-safe defaults so existing stored briefs continue to
# round-trip cleanly through InvestmentBrief.model_validate().


class ClaimType(str, Enum):
    """The type of factual claim extracted from a source."""

    FUNDING_AMOUNT = "funding_amount"
    FOUNDING_YEAR = "founding_year"
    EMPLOYEE_COUNT = "employee_count"
    STAGE = "stage"
    GEOGRAPHY = "geography"
    INVESTOR_IDENTITY = "investor_identity"
    REVENUE = "revenue"
    VALUATION = "valuation"
    PRODUCT_DESCRIPTION = "product_description"
    TEAM_COMPOSITION = "team_composition"
    LEGAL_STATUS = "legal_status"
    REGULATORY_STATUS = "regulatory_status"
    PARTNERSHIP = "partnership"
    MARKET_SIZE = "market_size"
    GROWTH_METRIC = "growth_metric"
    CUSTOMER_COUNT = "customer_count"
    OTHER = "other"


class StalenessT(str, Enum):
    """How fresh a piece of extracted evidence is."""

    FRESH = "fresh"          # ≤ 12 months old
    AGING = "aging"          # 12–24 months old
    STALE = "stale"          # 24–48 months old
    VERY_STALE = "very_stale"  # > 48 months old
    UNKNOWN = "unknown"      # No date signal found


class ContradictionSeverity(str, Enum):
    """How materially significant a detected contradiction is."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IntegrityGrade(str, Enum):
    """Letter grade summarising the overall evidence integrity score."""

    A = "A"  # ≥ 90 — strong, consistent evidence base
    B = "B"  # ≥ 75 — good evidence, minor noise
    C = "C"  # ≥ 60 — moderate evidence, conflicts present
    D = "D"  # ≥ 45 — weak evidence or significant conflicts
    F = "F"  # < 45  — serious integrity concerns


class EvidenceDepth(str, Enum):
    """How much evidence was found (the confidence/depth axis)."""

    THIN = "thin"                    # 1–2 sources, few facts  ●○○○○
    LIMITED = "limited"              # 3–4 sources              ●●○○○
    MODERATE = "moderate"            # 5–7 sources              ●●●○○
    RICH = "rich"                    # 8–11 sources             ●●●●○
    COMPREHENSIVE = "comprehensive"  # 12+ sources              ●●●●●


class ConsistencyStatus(str, Enum):
    """Whether extracted claims from different sources agree."""

    CLEAN = "clean"                            # No material conflicts found
    MINOR_DIFFERENCES = "minor_differences"    # Terminology gaps only
    CONFLICTS = "conflicts"                    # ≥ 1 GENUINE contradiction
    MAJOR_CONFLICTS = "major_conflicts"        # ≥ 3 GENUINE contradictions


class Claim(BaseModel):
    """A single factual claim extracted from one source."""

    claim_id: str = ""
    claim_type: ClaimType = ClaimType.OTHER
    value_raw: str = ""                       # Verbatim text from source
    value_normalised: str | None = None       # Normalised for comparison (USD, ISO year, …)
    source_url: str = ""
    source_authority: str = "web"             # e.g. "high_authority_web", "web", "social"
    source_title: str = ""
    snippet: str = ""                         # Short verbatim extract
    staleness: StalenessT = StalenessT.UNKNOWN
    confidence: float = Field(ge=0, le=1, default=0.5)


class Contradiction(BaseModel):
    """A genuine, material conflict between two independent claims."""

    contradiction_id: str = ""
    claim_a: Claim
    claim_b: Claim
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    # Subtype: GENUINE_CONTRADICTION | TEMPORAL_DRIFT | CURRENCY_ARTEFACT
    # Only GENUINE_CONTRADICTION generates deductions; the other two are stored
    # as IgnoredConflict objects.
    subtype: str = "GENUINE_CONTRADICTION"
    description: str = ""
    recommended_action: str = ""


class IgnoredConflict(BaseModel):
    """A conflict that was evaluated and deliberately suppressed.

    Stored for IC auditability — the investor can see what was considered
    and why it was dismissed.  Generates no score deductions and no UI
    warnings.
    """

    claim_a: Claim
    claim_b: Claim
    # reason: e.g. "FOUNDING_YEAR_TOLERANCE", "CURRENCY_ARTEFACT",
    #              "TEMPORAL_DRIFT", "STAGE_VOCABULARY", "EMPLOYEE_TERMINOLOGY"
    reason: str = ""
    subtype: str = ""
    description: str = ""


class UnsupportedClaim(BaseModel):
    """A claim type expected for this sector that was not found in open sources.

    In SPARSE_EVIDENCE_MODE these generate information notes only (no
    deductions).  In full-corpus mode, CRITICAL and HIGH unsupported claims
    carry small deductions.
    """

    claim_type: ClaimType = ClaimType.OTHER
    description: str = ""
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    recommended_action: str = ""


class StaleClaim(BaseModel):
    """A claim that was found but is based on significantly outdated evidence."""

    claim: Claim
    staleness: StalenessT = StalenessT.STALE
    source_url: str = ""
    recommended_action: str = ""


class EvidenceIntegrityReport(BaseModel):
    """Full output of the Evidence Integrity Engine for one analysis run.

    Two-axis model (from evidence-integrity-review.md Part V):
      - integrity_score / integrity_grade  → consistency of the evidence base
      - evidence_depth / confidence_adjusted → how much / how reliable our picture is

    These two dimensions are always displayed together.  A standalone grade
    without its depth qualifier is never shown to investors.
    """

    # ── Primary outputs ───────────────────────────────────────────────────────
    integrity_score: float = Field(ge=0, le=100, default=100.0)
    integrity_grade: IntegrityGrade = IntegrityGrade.A

    # ── Two-axis signals ─────────────────────────────────────────────────────
    evidence_depth: EvidenceDepth = EvidenceDepth.THIN
    consistency_status: ConsistencyStatus = ConsistencyStatus.CLEAN

    # ── Corpus metadata ──────────────────────────────────────────────────────
    sparse_mode: bool = False          # True when < 5 sources or < 2 high-authority
    claim_count: int = 0               # Total claims extracted
    source_count: int = 0              # Total sources analysed
    high_authority_count: int = 0      # Sources classified as high_authority_web
    document_source_count: int = 0     # Sources originating from uploaded documents
    web_source_count: int = 0          # Non-document sources (web / social / blog)

    # ── Findings ─────────────────────────────────────────────────────────────
    contradictions: list[Contradiction] = Field(default_factory=list)
    ignored_conflicts: list[IgnoredConflict] = Field(default_factory=list)
    unsupported_claims: list[UnsupportedClaim] = Field(default_factory=list)
    stale_claims: list[StaleClaim] = Field(default_factory=list)

    # ── Scoring detail ────────────────────────────────────────────────────────
    corroboration_bonus: float = 0.0   # Points added for well-corroborated claims

    # ── Narrative ─────────────────────────────────────────────────────────────
    integrity_summary: str = ""        # Plain-English summary for the IC
    extraction_notes: str = ""         # Notes on extraction quality / failures

    # ── Confidence adjustment (the only numeric impact on InvestmentBrief) ────
    # EIE adjusts InvestmentBrief.confidence by this delta — never overall_score,
    # trust_score, founder_score, startup_score, market_score, or risk_score.
    confidence_adjusted: float = Field(ge=0, le=1, default=0.0)
    confidence_delta: float = 0.0      # Negative means reduced confidence

    # ── Display helpers ───────────────────────────────────────────────────────
    # Two-axis quadrant label: "A", "B", "C", or "D" per the model in the review
    two_axis_label: str = ""
    # Numbered action items for the IC (e.g. "Verify funding with founder")
    verification_checklist: list[str] = Field(default_factory=list)

    # ── Audit trail ──────────────────────────────────────────────────────────
    generated_at: datetime | None = None


# ── VC Thesis Engine Models ──────────────────────────────────────────────────


class ThesisStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


class FundProfile(BaseModel):
    name: str = "Kulima Africa Tech Fund I"
    preferred_sectors: list[str] = Field(
        default_factory=lambda: [
            "FinTech",
            "AgTech",
            "HealthTech",
            "ClimateTech",
            "Logistics",
            "EdTech",
            "InsurTech",
            "Mobility",
        ]
    )
    preferred_stages: list[str] = Field(
        default_factory=lambda: ["Pre-Seed", "Seed", "Series A", "Early Stage"]
    )
    preferred_geographies: list[str] = Field(
        default_factory=lambda: [
            "Nigeria",
            "Kenya",
            "South Africa",
            "Egypt",
            "Ghana",
            "Pan-Africa",
            "East Africa",
            "West Africa",
        ]
    )
    check_size_min: float = 50_000.0
    check_size_max: float = 1_000_000.0
    exclusions: list[str] = Field(
        default_factory=lambda: ["Crypto", "Gambling", "Real Estate", "Tobacco", "Weapons"]
    )


class ThesisMatchResult(BaseModel):
    overall_match: float = Field(ge=0, le=100)
    sector_fit: str = "High"
    stage_fit: str = "High"
    geography_fit: str = "High"
    evidence_fit: str = "High"
    notes: list[str] = Field(default_factory=list)
    status: ThesisStatus = ThesisStatus.PASS


class InvestmentBrief(BaseModel):
    founder_name: str
    startup_name: str
    sector: str = ""
    geography: str = ""
    stage: str = ""
    executive_summary: str = ""
    founder_assessment: str = ""
    startup_assessment: str = ""
    market_assessment: str = ""
    risk_assessment: str = ""
    investment_recommendation: str = ""
    next_steps: list[str] = Field(default_factory=list)
    recommendation: Recommendation = Recommendation.OBSERVE
    overall_score: float = 0.0
    founder_score: float = 0.0
    startup_score: float = 0.0
    market_score: float = 0.0
    trust_score: float = 0.0
    risk_score: float = 0.0
    growth_potential: float = 0.0
    investment_readiness: float = 0.0
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    red_flags: list[RedFlag] = Field(default_factory=list)
    agent_results: dict[str, AgentResult] = Field(default_factory=dict)
    trust_graph: TrustGraph | None = None
    syndicate: SyndicateDecision | None = None
    future_simulation: FutureSimulation | None = None
    sources: list[SourceAttribution] = Field(default_factory=list)
    explainability: list[str] = Field(default_factory=list)
    # Trust Layer — None for all pre-EIE runs; populated by EvidenceIntegrityEngine
    evidence_integrity: EvidenceIntegrityReport | None = None
    # VC Thesis Engine — None for all pre-thesis runs; populated by evaluate_thesis_match
    thesis_match: ThesisMatchResult | None = None
    # MEAL Intelligence Foundation (Phase 1)
    meal_record: MEALRecord | None = None
    # Uploaded Evidence Intelligence
    uploaded_evidence: list[UploadedEvidenceRecord] = Field(default_factory=list)


# ── MEAL Intelligence Foundational Data Structures ───────────────────────────


class IndicatorStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    OFF_TRACK = "OFF_TRACK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class MEALIndicator(BaseModel):
    id: str
    name: str
    category: str = "Outcome"  # Output | Outcome | Impact | ESG | Governance
    description: str = ""
    baseline: float = 0.0
    target: float = 0.0
    actual: float | None = None
    variance: float | None = None
    unit: str = ""
    verification_source: str = ""
    status: IndicatorStatus = IndicatorStatus.INSUFFICIENT_EVIDENCE


class MEALOutput(BaseModel):
    id: str
    title: str
    target_date: str = ""
    achieved_date: str | None = None
    metric: str = ""
    target_value: float = 0.0
    actual_value: float | None = None
    variance: float | None = None
    verification_evidence_id: str = ""


class MEALOutcome(BaseModel):
    id: str
    title: str
    target_date: str = ""
    baseline_value: float = 0.0
    target_value: float = 0.0
    current_value: float | None = None
    variance: float | None = None
    confidence: float = Field(ge=0, le=1, default=0.5)


class MEALRecord(BaseModel):
    venture_id: str
    reporting_period: str = "Initial Appraisal"
    indicators: list[MEALIndicator] = Field(default_factory=list)
    outputs: list[MEALOutput] = Field(default_factory=list)
    outcomes: list[MEALOutcome] = Field(default_factory=list)
    audit_trail: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Transparent Trust Engine & Uploaded Evidence Models ──────────────────────


class TrustScoreBreakdown(BaseModel):
    source_reliability: float = Field(ge=0, le=100, default=50.0)
    corroboration: float = Field(ge=0, le=100, default=50.0)
    recency: float = Field(ge=0, le=100, default=50.0)
    completeness: float = Field(ge=0, le=100, default=50.0)
    weighted_score: float = Field(ge=0, le=100, default=50.0)
    final_trust_score: float = Field(ge=0, le=100, default=50.0)
    rationale: str = ""


class UploadedEvidenceRecord(BaseModel):
    id: str
    filename: str
    source: str
    upload_date: str
    file_type: str
    uploader: str
    trust_breakdown: TrustScoreBreakdown
    evidence_status: str = "INSUFFICIENT_EVIDENCE"  # VERIFIED | CORROBORATED | UNCORROBORATED | INSUFFICIENT_EVIDENCE
    evidence_items: list[str] = Field(default_factory=list)
    signals_generated: list[str] = Field(default_factory=list)
    decision_impact: str = "Neutral / Pending Audit"
    audit_trail: list[str] = Field(default_factory=list)
    raw_summary: str = ""


# ── Decision Learning & Outcome Intelligence Models ──────────────────────────


class OutcomeStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    SUCCESSFUL = "Successful"
    PARTIALLY_SUCCESSFUL = "Partially Successful"
    UNSUCCESSFUL = "Unsuccessful"


class LessonsLearned(BaseModel):
    what_happened: str = ""
    what_was_predicted: str = ""
    what_was_missed: str = ""
    what_worked: str = ""
    what_failed: str = ""


class DecisionOutcomeRecord(BaseModel):
    decision_id: str
    run_id: str
    venture_name: str
    founder_name: str = ""
    decision_date: str
    original_recommendation: str
    original_trust_score: float
    evidence_count: int = 0
    signals_used: list[str] = Field(default_factory=list)
    contradictions_count: int = 0
    risks_count: int = 0
    next_actions: list[str] = Field(default_factory=list)
    outcome_status: OutcomeStatus = OutcomeStatus.PENDING
    outcome_date: str | None = None
    outcome_notes: str = ""
    lessons_learned: LessonsLearned = Field(default_factory=LessonsLearned)
    user_id: str | None = None


class TrustCalibrationBin(BaseModel):
    tier: str  # High Trust (80-100) | Moderate (60-79) | Low Trust (0-59)
    decision_count: int = 0
    successful_count: int = 0
    success_rate: float = 0.0
    is_predictive: bool = True


class TrustCalibrationReport(BaseModel):
    overall_predictive_score: float = 85.0
    high_trust_success_rate: float = 0.0
    low_trust_failure_rate: float = 0.0
    calibration_bins: list[TrustCalibrationBin] = Field(default_factory=list)
    calibration_summary: str = ""


class OutcomeIntelligenceReport(BaseModel):
    total_decisions: int = 0
    completed_outcomes: int = 0
    decision_accuracy: float = 0.0
    trust_accuracy: float = 0.0
    signal_accuracy: float = 0.0
    recommendation_accuracy: float = 0.0
    calibration: TrustCalibrationReport = Field(default_factory=TrustCalibrationReport)
    decisions: list[DecisionOutcomeRecord] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DecisionTimelineNode(BaseModel):
    stage: str  # Information | Evidence | Trust | Signals | Decision | Outcome | Learning
    title: str
    timestamp: str
    summary: str
    status: str
    details: list[str] = Field(default_factory=list)

