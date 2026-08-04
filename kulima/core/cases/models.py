"""Kulima OS Case models (Phase 4A).

These models introduce a vertical-agnostic Case abstraction for Kulima OS
without changing the existing InvestmentBrief model or FLEX behaviour.

Phase 4A is foundation only:
- CaseType enumerates top-level case categories.
- CaseSubject describes what the case is about.
- Case wraps a vertical-specific payload (e.g. InvestmentBrief) plus
  shared OS intelligence fields.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from kulima.models import EvidenceIntegrityReport, SourceAttribution, TrustGraph


class CaseType(str, Enum):
    """High-level case categories for Kulima OS.

    These are intentionally broad and align with current and planned
    products. Additional types can be added without breaking existing
    behaviour.
    """

    INVESTMENT = "investment"   # Kulima FLEX
    RISK = "risk"               # Kulima SIGNALS
    PROGRAM = "program"         # Kulima IMPACT
    EVALUATION = "evaluation"   # Kulima MEAL


class CaseSubject(BaseModel):
    """The entity or object this case is about.

    For FLEX today, this roughly corresponds to (founder, startup). For
    other verticals it may represent a program, project, portfolio, or
    evaluation target.
    """

    id: str | None = None
    kind: str = "entity"       # e.g. "startup", "project", "program", "portfolio"
    name: str                   # primary display name
    secondary_name: str | None = None  # e.g. founder name when name is startup
    region: str | None = None
    sector: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Case(BaseModel):
    """Generic Kulima OS Case abstraction.

    A Case encapsulates:
    - identity and type information (CaseType, CaseSubject)
    - evidence-level artefacts (sources, evidence_integrity, trust_graph)
    - a vertical-specific payload (e.g. InvestmentBrief) stored as
      opaque JSON in `payload`.

    Phase 4A only introduces the model; orchestration, repository, and
    UI continue to use InvestmentBrief directly.
    """

    id: str
    case_type: CaseType
    subject: CaseSubject
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None

    # Evidence & graph surfaces shared across verticals
    sources: list[SourceAttribution] = Field(default_factory=list)
    evidence_integrity: EvidenceIntegrityReport | None = None
    trust_graph: TrustGraph | None = None
    document_ids: list[str] = Field(default_factory=list)

    # Vertical-specific payload (opaque to the core OS layer). For FLEX
    # this will contain a serialised InvestmentBrief.
    payload: dict[str, Any] = Field(default_factory=dict)
