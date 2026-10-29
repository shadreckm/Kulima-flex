"""Collection-channel domain models (Forms Integration V1, Phases 1 & 3).

These models live *beside* the evidence layer, never inside it. A collection
batch is normalised into a CSV document and handed to the existing
``save_uploaded_file`` pipeline, so ``InvestmentBrief.uploaded_evidence``,
``TrustScoreBreakdown``, signals, decisions and reports keep their current
shapes. What is stored here is provenance and re-derivation data: which form a
batch came from, which responses it contained, and how each response scored.

Evidence classes (Phase 3) are labels for humans and for the report source
table — they do not create a second evidence model:

    DOCUMENT   ·  SURVEY  ·  FORM  ·  OPERATIONAL  ·  COMMUNITY
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceKind(str, Enum):
    """Registered collection channels. Only the first two are live in V1."""

    DOCUMENT = "document"
    GOOGLE_FORM = "google_form"
    GOOGLE_SHEET = "google_sheet"
    KOBO = "kobo"
    WHATSAPP = "whatsapp"
    USSD = "ussd"
    API = "api"


#: Human label for provenance chips (design guard G4: provenance always visible).
SOURCE_KIND_LABELS: dict[str, str] = {
    SourceKind.DOCUMENT.value: "Document",
    SourceKind.GOOGLE_FORM.value: "Google Form",
    SourceKind.GOOGLE_SHEET.value: "Google Sheet",
    SourceKind.KOBO.value: "KoBoToolbox",
    SourceKind.WHATSAPP.value: "WhatsApp",
    SourceKind.USSD.value: "USSD",
    SourceKind.API.value: "System API",
}

#: Channels that can be materialised as evidence in this build.
LIVE_KINDS: tuple[str, ...] = (
    SourceKind.DOCUMENT.value,
    SourceKind.GOOGLE_FORM.value,
    SourceKind.GOOGLE_SHEET.value,
)


class EvidenceClass(str, Enum):
    """Phase 3 vocabulary. All five coexist inside the one evidence model."""

    DOCUMENT = "document"
    SURVEY = "survey"
    FORM = "form"
    OPERATIONAL = "operational"
    COMMUNITY = "community"


EVIDENCE_CLASS_LABELS: dict[str, str] = {
    EvidenceClass.DOCUMENT.value: "Document evidence",
    EvidenceClass.SURVEY.value: "Survey evidence",
    EvidenceClass.FORM.value: "Form evidence",
    EvidenceClass.OPERATIONAL.value: "Operational evidence",
    EvidenceClass.COMMUNITY.value: "Community evidence",
}


class CollectionPurpose(str, Enum):
    """Why the workspace is collecting — drives Phase 8 behaviour."""

    EVIDENCE = "evidence"
    FOLLOW_UP = "follow_up"


PURPOSE_LABELS: dict[str, str] = {
    CollectionPurpose.EVIDENCE.value: "Assessment evidence",
    CollectionPurpose.FOLLOW_UP.value: "Follow-up / outcome validation",
}


class ConnectionStatus(str, Enum):
    PENDING_AUTH = "pending_auth"
    ACTIVE = "active"
    ERROR = "error"
    REVOKED = "revoked"


class SyncStatus(str, Enum):
    NO_NEW_RESPONSES = "no_new_responses"
    PENDING_BELOW_MINIMUM = "pending_below_minimum"
    MATERIALISED = "materialised"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


class FormQuestion(BaseModel):
    """One discovered question of the instrument (schema plane)."""

    key: str
    title: str
    question_type: str = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list)


class CollectedAnswer(BaseModel):
    question_key: str
    question_title: str
    value: str = ""
    answer_type: str = "text"


class CollectedResponse(BaseModel):
    """One normalised response, as it will be trusted and reported."""

    response_id: str
    submitted_at: str = ""
    answers: list[CollectedAnswer] = Field(default_factory=list)
    # ── Phase 4: per-response trust fields ────────────────────────────────
    respondent_type: str = "Unidentified respondent"
    respondent_ref: str = ""
    completeness_pct: float = 0.0
    answered_count: int = 0
    expected_count: int = 0
    consistency: str = "NOT MEASURED"
    consistency_notes: list[str] = Field(default_factory=list)
    verification_status: str = "SELF_REPORTED"
    trust_score: float = 0.0
    evidence_class: str = EvidenceClass.FORM.value
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


class CollectionDigest(BaseModel):
    """Deterministic summary of a batch — the evidence record's raw summary.

    The signals layer reads an evidence record's summary (not the stored file)
    when it looks for term evidence, so this digest is the channel's only
    legitimate way of putting respondent language in front of the detectors.
    It contains verbatim answer text and counts, nothing invented.
    """

    form_title: str
    source_kind: str = SourceKind.GOOGLE_FORM.value
    purpose: str = CollectionPurpose.EVIDENCE.value
    response_count: int = 0
    window_start: str = ""
    window_end: str = ""
    median_completeness_pct: float = 0.0
    median_trust_score: float = 0.0
    respondent_mix: dict[str, int] = Field(default_factory=dict)
    consistency_flagged: int = 0
    themes: list[str] = Field(default_factory=list)
    verbatim_lines: list[str] = Field(default_factory=list)
    evidence_class: str = EvidenceClass.FORM.value
    text: str = ""


class FormConnection(BaseModel):
    """A workspace's link to one instrument (the assessment mapping layer)."""

    id: str
    org_id: str
    assessment_id: str
    kind: str = SourceKind.GOOGLE_FORM.value
    form_id: str = ""
    sheet_id: str = ""
    sheet_range: str = ""
    title: str = ""
    purpose: str = CollectionPurpose.EVIDENCE.value
    status: str = ConnectionStatus.PENDING_AUTH.value
    owner_user_id: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    last_synced_at: str = ""
    last_error: str = ""
    total_responses: int = 0
    pending_responses: int = 0
    batch_count: int = 0
    schema_hash: str = ""
    questions: list[FormQuestion] = Field(default_factory=list)
    evidence_class: str = EvidenceClass.FORM.value
    note: str = ""

    @property
    def kind_label(self) -> str:
        return SOURCE_KIND_LABELS.get(self.kind, self.kind)


class CollectionBatch(BaseModel):
    """One materialised batch == exactly one evidence document.

    Never one document per response: the document trust engine grants a
    corroboration bonus by *document count*, the contradiction detector skips
    pairs sharing a ``source_url``, and report evidence accounting counts
    uploaded documents. Per-response documents would let volume buy authority.
    """

    id: str
    connection_id: str
    org_id: str
    assessment_id: str
    response_ids: list[str] = Field(default_factory=list)
    document_id: str = ""
    run_id: str = ""
    response_count: int = 0
    window_start: str = ""
    window_end: str = ""
    trust_score: float | None = None
    evidence_status: str = ""
    created_at: datetime = Field(default_factory=_now)
    digest: str = ""
    filename: str = ""
