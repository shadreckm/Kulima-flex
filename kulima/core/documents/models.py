"""Pydantic models for Kulima OS Document Intelligence (Phase A).

These models represent ingested documents, their text chunks, and how
those documents are exposed as evidence sources to the rest of the OS.

Phase A is ingestion and persistence only — no claim extraction, scoring,
or engine integration yet.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from kulima.models import SourceAttribution


class DocumentType(str, Enum):
    """High-level document kinds.

    This is intentionally broad and can be extended as new verticals
    adopt the Document Intelligence service.
    """

    GENERIC = "generic"
    PITCH_DECK = "pitch_deck"
    FINANCIAL_MODEL = "financial_model"
    BOARD_MINUTES = "board_minutes"
    POLICY_DOC = "policy_doc"
    REPORT = "report"
    DATA_EXPORT = "data_export"


class Document(BaseModel):
    """Logical document ingested into Kulima OS.

    In Phase A this is primarily metadata; content is represented via
    DocumentChunk instances and storage is handled by the repository.
    """

    id: str
    filename: str
    mime_type: str
    doc_type: DocumentType = DocumentType.GENERIC
    uploaded_by: str | None = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    source_type: str = "user_uploaded"  # e.g. investor_provided, founder_provided
    entities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """A chunk of text extracted from a document.

    Chunks are the basic unit passed to downstream engines and used for
    retrieval and inspection.
    """

    id: str
    document_id: str
    sequence: int = 0  # ordering within a document
    page_number: int | None = None
    section_heading: str | None = None
    text: str
    tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentSource(BaseModel):
    """Bridge from Document to existing SourceAttribution.

    This allows document-backed evidence to be treated like any other
    source in ResearchEngine and Evidence Integrity without changing
    their interfaces.
    """

    document_id: str
    source: SourceAttribution
