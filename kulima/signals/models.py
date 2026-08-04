"""Kulima SIGNALS domain models (Phase 5B).

These models define the core Signal abstraction used by the Kulima SIGNALS
product line. They are independent of FLEX and can be reused across OS
verticals that need risk / opportunity signalling.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List

from pydantic import BaseModel, Field


class SignalLevel(str, Enum):
    """Severity / urgency of a signal."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SignalCategory(str, Enum):
    """Thematic category for a signal.

    Categories are intentionally broad and are suitable for development
    programs, risk, and operational monitoring.
    """

    GOVERNANCE = "governance"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    SAFEGUARDING = "safeguarding"
    POLITICAL = "political"
    SOCIAL = "social"
    IMPACT = "impact"
    LEARNING = "learning"


class Signal(BaseModel):
    """Atomic risk/opportunity signal for a Case.

    Signals are small, interpretable units that can be grouped, filtered,
    and sorted. They are always tied to a specific Case via case_id.
    """

    id: str
    case_id: str
    level: SignalLevel
    category: SignalCategory
    title: str
    description: str
    # Direction of the signal relative to the case: "risk", "opportunity", or "neutral".
    direction: str = Field(default="risk")
    # References into the evidence corpus (e.g. ["D1", "D2", "S3"]).
    evidence_refs: List[str] = Field(default_factory=list)
    # Short summary (1–3 sentences) of the supporting evidence.
    evidence_summary: str = ""
    # One concrete recommended action for this signal.
    recommended_action: str = ""
    # Time horizon for addressing the signal: e.g. "immediate", "short-term", "medium-term".
    time_horizon: str | None = None
    # Confidence in the signal (0–1).
    confidence: float = Field(ge=0, le=1, default=0.5)
    # Additional key/value pairs for vertical-specific metadata.
    metadata: dict[str, Any] = Field(default_factory=dict)
