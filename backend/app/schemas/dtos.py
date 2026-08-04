from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class IntelligenceCreateRequest(BaseModel):
    founder: str
    startup: Optional[str] = None


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


class AskResponse(BaseModel):
    answer: str


class DocumentResponse(BaseModel):
    id: str
    name: str
    url: str


class DecisionSnapshot(BaseModel):
    """Compact decision snapshot for a FLEX intelligence run.

    This mirrors the Streamlit Decision Snapshot panel but is shaped for
    the web ContextPanel. It does not introduce new intelligence logic –
    all fields are derived from InvestmentBrief and EvidenceIntegrity.
    """

    verdict: str
    confidencePercent: Optional[float] = None
    confidenceLabel: Optional[str] = None
    reliabilityGrade: Optional[str] = None
    reliabilityScore: Optional[float] = None
    topReasons: List[str]
    topRisks: List[str]
    nextAction: str


class SignalItem(BaseModel):
    id: str
    level: str
    category: str
    direction: str
    title: str
    description: str
    recommendedAction: str
    confidence: float


class SignalsSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    topRisks: List[SignalItem] = Field(default_factory=list)
    topOpportunities: List[SignalItem] = Field(default_factory=list)
