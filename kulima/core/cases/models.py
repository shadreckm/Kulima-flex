"""Kulima OS Case models (Phase 4 Enterprise Layer).

These models introduce the enterprise Case abstraction that becomes the
aggregate root for transaction management, workspaces, collaboration, and
decision dossiers.

Phase 4 Enterprise:
- Case lifecycle state machine (Draft → Processing → Review → Decision Ready → Exported → Archived)
- Workspace types mapping to assessment types
- Case service and repository for durable case management
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


class WorkspaceType(str, Enum):
    """Workspace templates that map 1:1 to AssessmentType.

    Each workspace type renders the same six tabs: Documents · Research ·
    Evidence · Signals · Decision · Reports + Activity (audit feed).
    """

    STARTUP = "startup"
    NGO = "ngo"
    GOVERNMENT_PROGRAM = "government_program"
    DEVELOPMENT_PROGRAM = "development_program"
    TOURISM_SME = "tourism_sme"


class CaseLifecycleStatus(str, Enum):
    """Enterprise transaction lifecycle state machine.

    Draft → Processing → Review → Decision Ready → Exported → Archived
    """

    DRAFT = "draft"
    PROCESSING = "processing"
    REVIEW = "review"
    DECISION_READY = "decision_ready"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class Case(BaseModel):
    """Enterprise Case aggregate root - the single source of truth for assessments.

    A Case encapsulates:
    - identity and type information (CaseType, CaseSubject)
    - workspace and lifecycle management
    - assessment linkage
    - evidence-level artefacts (sources, evidence_integrity, trust_graph)
    - a vertical-specific payload (e.g. InvestmentBrief) stored as
      opaque JSON in `payload`.

    Phase 4 Enterprise: This becomes the persisted aggregate root with
    lifecycle state machine, workspace binding, and role-based workflow.
    """

    id: str
    case_type: CaseType
    subject: CaseSubject
    workspace_type: WorkspaceType
    lifecycle_status: CaseLifecycleStatus = CaseLifecycleStatus.DRAFT
    assessment_id: str | None = None  # Link to AssessmentContext
    org_id: str | None = None  # Workspace binding
    assignee_id: str | None = None  # Primary owner
    reviewer_id: str | None = None  # Current reviewer in REVIEW state
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Evidence & graph surfaces shared across verticals
    sources: list[SourceAttribution] = Field(default_factory=list)
    evidence_integrity: EvidenceIntegrityReport | None = None
    trust_graph: TrustGraph | None = None
    document_ids: list[str] = Field(default_factory=list)

    # Vertical-specific payload (opaque to the core OS layer). For FLEX
    # this will contain a serialised InvestmentBrief.
    payload: dict[str, Any] = Field(default_factory=dict)

    # Phase 4: Transaction metadata
    last_transition_at: datetime | None = None
    last_transition_by: str | None = None
