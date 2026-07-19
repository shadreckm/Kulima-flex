"""Shared domain models for the Kulima Investment Intelligence OS."""

from __future__ import annotations

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
