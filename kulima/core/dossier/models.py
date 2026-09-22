"""Decision Dossier models for single source of truth (Phase 11).

These models implement the Decision Dossier that becomes the single source of
truth for assessment results, containing all scores, recommendations, and summaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DossierScores(BaseModel):
    """The seven canonical scores that make up the decision dossier."""

    evidence_score: float = 0.0
    trust_score: float = 0.0
    risk_score: float = 0.0
    climate_score: float = 0.0
    tourism_score: float = 0.0
    community_score: float = 0.0
    opportunity_score: float = 0.0


class TourismProfile(BaseModel):
    """Tourism-specific intelligence for Tourism SME assessments (Phase 12)."""

    tourism_contribution: float = 0.0
    visitor_economy_impact: float = 0.0
    local_employment_potential: float = 0.0
    cultural_preservation: float = 0.0
    environmental_sustainability: float = 0.0
    destination_growth_potential: float = 0.0


class InvestmentReadiness(BaseModel):
    """Investment readiness metrics for startup assessments (Phase 13)."""

    investment_readiness_score: float = 0.0
    founder_readiness: float = 0.0
    market_readiness: float = 0.0
    traction_readiness: float = 0.0
    due_diligence_readiness: float = 0.0
    funding_recommendation: str = ""


class DecisionDossier(BaseModel):
    """The single source of truth for assessment decisions.

    The dossier contains all scores, recommendations, summaries, and profiles
    that represent the final decision. Once approved, it becomes immutable
    (versioning creates new versions for changes).
    """

    id: str
    case_id: str  # Unique linkage to case
    version: int = 1
    scores: DossierScores = Field(default_factory=DossierScores)
    recommendation: str = ""
    research_summary: str = ""
    executive_summary: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    pdf_path: str | None = None

    # Optional domain-specific profiles
    tourism_profile: TourismProfile | None = None
    investment_readiness: InvestmentReadiness | None = None

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
