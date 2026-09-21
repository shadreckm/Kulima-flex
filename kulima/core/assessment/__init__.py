"""Shared Assessment Context — collect once, reuse everywhere.

Public surface:

- :class:`~kulima.core.assessment.models.AssessmentContext` — the shared intake record
- :class:`~kulima.core.assessment.repository.AssessmentRepository` — central storage
- :func:`~kulima.core.assessment.extraction.extract_from_documents` — auto extraction
- :mod:`~kulima.core.assessment.service` — identity resolution & confirmation rules
"""

from .models import (  # noqa: F401
    ASSESSMENT_TYPE_LABELS,
    AssessmentContext,
    AssessmentDocument,
    AssessmentExtraction,
    AssessmentStatus,
    AssessmentType,
    ExtractedField,
)
from .repository import AssessmentRepository  # noqa: F401

__all__ = [
    "ASSESSMENT_TYPE_LABELS",
    "AssessmentContext",
    "AssessmentDocument",
    "AssessmentExtraction",
    "AssessmentRepository",
    "AssessmentStatus",
    "AssessmentType",
    "ExtractedField",
]
