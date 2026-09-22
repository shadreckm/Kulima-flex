"""Research models for auto-launched research packs (Phase 2).

These models implement the ResearchPack entity that fuses document extraction
with automatic Tavily research, creating a unified evidence graph.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResearchStatus(str, Enum):
    """Lifecycle status of a research pack."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchPack(BaseModel):
    """A research pack that auto-launches from document extraction.

    When documents are uploaded and entities extracted (founder, startup, sector,
    country), a ResearchPack is automatically created to gather external intelligence
    without requiring separate forms.

    The research status is tracked separately from the assessment lifecycle,
    enabling users to see progress while the case continues to PROCESSING.
    """

    id: str
    case_id: str
    assessment_id: str | None = None
    status: ResearchStatus = ResearchStatus.PENDING
    queries: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    attempt_count: int = 0
    max_attempts: int = 3
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Extracted entities that drive the research
    founder_name: str = ""
    startup_name: str = ""
    organization_name: str = ""
    sector: str = ""
    country: str = ""

    # Research results
    research_summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
