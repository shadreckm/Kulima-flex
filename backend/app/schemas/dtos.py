from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class IntelligenceCreateRequest(BaseModel):
    """Start a run.

    Legacy callers pass ``founder`` (+ optional ``startup``). When
    ``assessmentId`` is supplied (single-intake flow), the run identity is
    resolved from the shared Assessment Context and ``founder`` is optional.
    """

    founder: Optional[str] = None
    startup: Optional[str] = None
    assessmentId: Optional[str] = None


class IntelligenceCreateResponse(BaseModel):
    runId: str
    status: str = "running"


class IntelligenceStatusResponse(BaseModel):
    runId: str
    status: str
    dbId: Optional[int] = None
    createdAt: Optional[str] = None
    completedAt: Optional[str] = None
    error: Optional[str] = None


class AskRequest(BaseModel):
    runId: str
    question: str
    history: Optional[List[dict]] = Field(default_factory=list)


class AssessmentPatchRequest(BaseModel):
    """User corrections applied when auto-extraction confidence is low."""

    assessmentType: Optional[str] = None
    entityName: Optional[str] = None
    founderName: Optional[str] = None
    organizationName: Optional[str] = None
    sector: Optional[str] = None
    country: Optional[str] = None


class AskResponse(BaseModel):
    answer: str


class DocumentResponse(BaseModel):
    id: str
    name: str
    url: str
    trustScore: Optional[float] = None
    evidenceStatus: Optional[str] = None
    signals: Optional[List[str]] = Field(default_factory=list)
    mode: Optional[str] = None


class DecisionSnapshot(BaseModel):
    """Compact decision snapshot for a FLEX intelligence run.

    This mirrors the Streamlit Decision Snapshot panel but is shaped for
    the web ContextPanel. It does not introduce new intelligence logic –
    all fields are derived from InvestmentBrief and EvidenceIntegrity.

    Extended decision fields (decisionScore, decisionBand, domainScores,
    decisionRationale) come from the expanded Decision Engine
    (kulima.decision) which consumes Trust, Risk, Opportunity, Market,
    Funding, Climate, Environment, Tourism and Community Impact domains
    on top of Evidence.
    """

    verdict: str
    confidencePercent: Optional[float] = None
    confidenceLabel: Optional[str] = None
    reliabilityGrade: Optional[str] = None
    reliabilityScore: Optional[float] = None
    topReasons: List[str]
    topRisks: List[str]
    nextAction: str
    # Expanded Decision Engine outputs (additive; None for legacy runs)
    decisionScore: Optional[float] = None
    decisionBand: Optional[str] = None
    decisionRationale: Optional[List[str]] = None
    domainScores: Optional[dict[str, Any]] = None


class SignalItem(BaseModel):
    id: str
    level: str
    category: str
    direction: str
    title: str
    description: str
    recommendedAction: str
    confidence: float
    evidenceRefs: List[str] = Field(default_factory=list)
    evidenceSummary: str = ""
    timeHorizon: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DomainSignals(BaseModel):
    domain: str
    label: str
    count: int = 0
    riskCount: int = 0
    opportunityCount: int = 0
    # Expanded dashboard fields (Step 6): every domain renders score, summary
    # and recommendation.
    score: int = 50
    summary: str = ""
    recommendation: str = ""
    signals: List[SignalItem] = Field(default_factory=list)


class SignalsSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    topRisks: List[SignalItem] = Field(default_factory=list)
    topOpportunities: List[SignalItem] = Field(default_factory=list)
    domains: dict[str, DomainSignals] = Field(default_factory=dict)
    allSignals: List[SignalItem] = Field(default_factory=list)
