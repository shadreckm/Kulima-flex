"""Shared Assessment Context models — the single intake record.

Kulima FLEX collects information once on the landing page and reuses it
across Evidence, Signals, Decision, Reports and Ask IC.  These models define
that shared contract.  They are intentionally free of backend/API concerns so
they can be reused by any surface (web, Streamlit, exports).

Design notes
------------
- ``assessment_id`` is the primary key of the intake record.
- ``run_id`` is attached once the intelligence run (Tavily OSINT + agents)
  has been started from this context.
- Extracted fields carry their own confidence so downstream workspaces can
  decide when to ask the user a confirming question (and when not to).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AssessmentType(str, Enum):
    """The five canonical assessment types collected on the landing page."""

    STARTUP = "startup"
    NGO = "ngo"
    GOVERNMENT_PROGRAM = "government_program"
    DEVELOPMENT_PROGRAM = "development_program"
    TOURISM_SME = "tourism_sme"
    # Legacy alias retained so contexts stored before Tourism SME existed
    # continue to load without migration.
    ACCELERATOR = "accelerator"


class AssessmentStatus(str, Enum):
    """Lifecycle of an assessment context."""

    INTAKE = "intake"
    NEEDS_CONFIRMATION = "needs_confirmation"
    READY = "ready"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


# Human-readable labels used in prompts, reports and API payloads.
ASSESSMENT_TYPE_LABELS: Dict[str, str] = {
    AssessmentType.STARTUP.value: "Startup",
    AssessmentType.NGO.value: "NGO",
    AssessmentType.GOVERNMENT_PROGRAM.value: "Government Program",
    AssessmentType.DEVELOPMENT_PROGRAM.value: "Development Program",
    AssessmentType.TOURISM_SME.value: "Tourism SME",
    AssessmentType.ACCELERATOR.value: "Accelerator",
}


class ExtractedField(BaseModel):
    """A single auto-extracted field with provenance and confidence."""

    value: str = ""
    confidence: float = Field(ge=0, le=1, default=0.0)
    source: str = "document"

    @property
    def is_empty(self) -> bool:
        return not (self.value or "").strip()


class AssessmentExtraction(BaseModel):
    """Everything auto-extracted from the uploaded documents."""

    startup_name: Optional[ExtractedField] = None
    founder_name: Optional[ExtractedField] = None
    organization_name: Optional[ExtractedField] = None
    sector: Optional[ExtractedField] = None
    country: Optional[ExtractedField] = None
    website: Optional[ExtractedField] = None
    team: Optional[ExtractedField] = None
    problem_statement: Optional[ExtractedField] = None
    # Overall extraction confidence (0–1) used to decide whether the user
    # must confirm entity details before the run starts.
    confidence: float = Field(ge=0, le=1, default=0.0)
    # True when at least one document yielded readable text at all.
    text_available: bool = True

    def field_value(self, name: str) -> str:
        field = getattr(self, name, None)
        if isinstance(field, ExtractedField):
            return field.value.strip()
        return ""

    def field_confidence(self, name: str) -> float:
        field = getattr(self, name, None)
        if isinstance(field, ExtractedField):
            return float(field.confidence)
        return 0.0

    def display_entity(self) -> str:
        """Best available display name for the assessed entity."""
        for key in ("organization_name", "startup_name"):
            value = self.field_value(key)
            if value:
                return value
        return ""


class AssessmentDocument(BaseModel):
    """Compact record of a document ingested into the assessment."""

    id: str
    name: str
    url: str = ""
    file_type: str = ""
    trust_score: Optional[float] = None
    evidence_status: Optional[str] = None
    signals: List[str] = Field(default_factory=list)
    evidence_items: List[str] = Field(default_factory=list)
    decision_impact: str = ""
    raw_summary: str = ""
    trust_breakdown: Dict[str, Any] = Field(default_factory=dict)
    upload_date: str = ""


class AssessmentContext(BaseModel):
    """The single shared intake record reused by every workspace."""

    assessment_id: str
    assessment_type: AssessmentType = AssessmentType.STARTUP
    run_id: Optional[str] = None

    # ── Documents ─────────────────────────────────────────────────────────
    document_ids: List[str] = Field(default_factory=list)
    uploaded_documents: List[AssessmentDocument] = Field(default_factory=list)
    extracted_text: str = ""
    extracted_text_length: int = 0

    # ── Auto extraction (Step 3) ──────────────────────────────────────────
    extraction: AssessmentExtraction = Field(default_factory=AssessmentExtraction)

    # Flat convenience mirrors — the fields named in the Assessment Context spec.
    organization_name: str = ""
    startup_name: str = ""
    founder_name: str = ""
    sector: str = ""
    country: str = ""
    website: str = ""
    team: str = ""
    problem_statement: str = ""

    # ── Pipeline outputs (populated as the platform runs) ─────────────────
    trust_score: Optional[float] = None
    signals: List[str] = Field(default_factory=list)
    decision: Dict[str, Any] = Field(default_factory=dict)

    # ── Lifecycle ─────────────────────────────────────────────────────────
    status: AssessmentStatus = AssessmentStatus.INTAKE
    requires_confirmation: bool = False
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
    created_by: Optional[str] = None

    def type_label(self) -> str:
        return ASSESSMENT_TYPE_LABELS.get(
            getattr(self.assessment_type, "value", str(self.assessment_type)),
            "Assessment",
        )

    def refresh_from_extraction(self) -> None:
        """Mirror extracted values into the flat convenience fields."""
        self.organization_name = self.extraction.field_value("organization_name")
        self.startup_name = self.extraction.field_value("startup_name")
        self.founder_name = self.extraction.field_value("founder_name")
        self.sector = self.extraction.field_value("sector")
        self.country = self.extraction.field_value("country")
        self.website = self.extraction.field_value("website")
        self.team = self.extraction.field_value("team")
        self.problem_statement = self.extraction.field_value("problem_statement")
        self.updated_at = _utc_now_iso()
