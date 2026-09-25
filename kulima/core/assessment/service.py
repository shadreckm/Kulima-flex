"""Assessment Context service — resolution rules shared by all workspaces.

Turns the extracted document fields into the identity the rest of the
platform needs (run identity for Tavily OSINT, display entity for Signals /
Decision surfaces, and the "do we still need to ask the user?" decision).

Collect once. Reuse everywhere.
"""

from __future__ import annotations

from typing import Optional, Tuple

from .models import (
    ASSESSMENT_TYPE_LABELS,
    AssessmentContext,
    AssessmentExtraction,
    AssessmentStatus,
    AssessmentType,
    ExtractedField,
)

# Below this overall confidence we ask the user ONE confirming question
# instead of silently running with a weak identity.
CONFIRMATION_THRESHOLD = 0.55

# Assessment types where the entity itself (not a founder person) is the subject.
_ORGANISATION_TYPES = {
    AssessmentType.NGO,
    AssessmentType.GOVERNMENT_PROGRAM,
    AssessmentType.DEVELOPMENT_PROGRAM,
    AssessmentType.TOURISM_SME,
    AssessmentType.ACCELERATOR,
}

_FALLBACK_ENTITY_NAMES = {
    AssessmentType.STARTUP: "Unnamed Venture",
    AssessmentType.NGO: "Unnamed Organisation",
    AssessmentType.GOVERNMENT_PROGRAM: "Unnamed Government Program",
    AssessmentType.DEVELOPMENT_PROGRAM: "Unnamed Development Program",
    AssessmentType.TOURISM_SME: "Unnamed Tourism Business",
    AssessmentType.ACCELERATOR: "Unnamed Programme",
}

_FALLBACK_LEADS = {
    AssessmentType.STARTUP: "Founding Team",
    AssessmentType.NGO: "Country Director",
    AssessmentType.GOVERNMENT_PROGRAM: "Program Coordinator",
    AssessmentType.DEVELOPMENT_PROGRAM: "Program Lead",
    AssessmentType.TOURISM_SME: "Business Owner",
    AssessmentType.ACCELERATOR: "Programme Lead",
}


def coerce_assessment_type(value: str | AssessmentType | None) -> AssessmentType:
    if isinstance(value, AssessmentType):
        return value
    raw = (value or "").strip().lower()
    aliases = {
        "startup": AssessmentType.STARTUP,
        "start-up": AssessmentType.STARTUP,
        "venture": AssessmentType.STARTUP,
        "ngo": AssessmentType.NGO,
        "non-profit": AssessmentType.NGO,
        "nonprofit": AssessmentType.NGO,
        "government": AssessmentType.GOVERNMENT_PROGRAM,
        "government_program": AssessmentType.GOVERNMENT_PROGRAM,
        "government program": AssessmentType.GOVERNMENT_PROGRAM,
        "public_program": AssessmentType.GOVERNMENT_PROGRAM,
        "development": AssessmentType.DEVELOPMENT_PROGRAM,
        "development_program": AssessmentType.DEVELOPMENT_PROGRAM,
        "development program": AssessmentType.DEVELOPMENT_PROGRAM,
        "tourism": AssessmentType.TOURISM_SME,
        "tourism_sme": AssessmentType.TOURISM_SME,
        "tourism sme": AssessmentType.TOURISM_SME,
        "hospitality": AssessmentType.TOURISM_SME,
        "accelerator": AssessmentType.ACCELERATOR,
    }
    return aliases.get(raw, AssessmentType.STARTUP)


def type_label(assessment_type: AssessmentType | str) -> str:
    value = getattr(assessment_type, "value", str(assessment_type))
    return ASSESSMENT_TYPE_LABELS.get(value, "Assessment")


def apply_extraction(ctx: AssessmentContext, extraction: AssessmentExtraction) -> AssessmentContext:
    """Store extraction results and decide whether user confirmation is needed."""
    ctx.extraction = extraction
    ctx.requires_confirmation = extraction_failed(ctx.assessment_type, extraction)
    if ctx.status not in (AssessmentStatus.RUNNING, AssessmentStatus.COMPLETE):
        ctx.status = (
            AssessmentStatus.NEEDS_CONFIRMATION if ctx.requires_confirmation else AssessmentStatus.READY
        )
    ctx.refresh_from_extraction()
    return ctx


def extraction_failed(
    assessment_type: AssessmentType | str,
    extraction: AssessmentExtraction,
) -> bool:
    """True when the platform must still ask the user for the entity identity.

    Startup: needs entity name AND founder name (the two run inputs).
    Organisation types: needs the entity/organisation name.
    """
    atype = coerce_assessment_type(assessment_type)
    entity_name = extraction.field_value("organization_name") or extraction.field_value("startup_name")

    if atype == AssessmentType.STARTUP:
        has_identity = bool(entity_name) and bool(extraction.field_value("founder_name"))
    else:
        has_identity = bool(entity_name)

    if not has_identity:
        return True
    return extraction.confidence < CONFIRMATION_THRESHOLD


def resolve_run_identity(ctx: AssessmentContext) -> Tuple[str, str]:
    """Return ``(founder, startup)`` for the intelligence run / Tavily research.

    Mirrors the legacy ``entityToRunParams`` convention:
    - startup assessments: founder = founder name, startup = venture name.
    - organisation assessments: the entity name is carried in the founder slot
      (kept for backwards compatibility with stored runs and reports).
    """
    atype = coerce_assessment_type(ctx.assessment_type)
    extracted_entity = (
        ctx.extraction.field_value("organization_name")
        or ctx.extraction.field_value("startup_name")
        or ctx.organization_name
        or ctx.startup_name
    )
    extracted_founder = ctx.extraction.field_value("founder_name") or ctx.founder_name

    entity_name = extracted_entity.strip() or _FALLBACK_ENTITY_NAMES.get(atype, "Unnamed Entity")
    lead_name = extracted_founder.strip() or _FALLBACK_LEADS.get(atype, "Assessment Lead")

    if atype == AssessmentType.STARTUP:
        return lead_name, entity_name
    return entity_name, ctx.startup_name.strip() or entity_name


def display_entity(ctx: AssessmentContext) -> str:
    """Entity label shown on the Signals / Decision surfaces."""
    return (
        ctx.organization_name.strip()
        or ctx.startup_name.strip()
        or ctx.extraction.display_entity()
        or "Assessment"
    )


def sector_hint(ctx: AssessmentContext) -> str:
    return (ctx.sector or ctx.extraction.field_value("sector")).strip()


def country_hint(ctx: AssessmentContext) -> str:
    return (ctx.country or ctx.extraction.field_value("country")).strip()


def field_from_confidence(value: str, confidence: float, source: str) -> Optional[ExtractedField]:
    value = (value or "").strip()
    if not value:
        return None
    return ExtractedField(value=value, confidence=confidence, source=source)


def manual_patch(
    ctx: AssessmentContext,
    *,
    entity_name: Optional[str] = None,
    founder_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    sector: Optional[str] = None,
    country: Optional[str] = None,
    website: Optional[str] = None,
) -> AssessmentContext:
    """Apply user-supplied corrections when extraction failed (Step 4 fallback)."""
    atype = coerce_assessment_type(ctx.assessment_type)

    org_value = (organization_name or "").strip()
    entity_value = (entity_name or "").strip()
    founder_value = (founder_name or "").strip()

    if org_value:
        ctx.extraction.organization_name = field_from_confidence(org_value, 1.0, "user")
    if entity_value:
        if atype == AssessmentType.STARTUP:
            ctx.extraction.startup_name = field_from_confidence(entity_value, 1.0, "user")
            ctx.extraction.organization_name = ctx.extraction.organization_name or field_from_confidence(
                entity_value, 1.0, "user"
            )
        else:
            ctx.extraction.organization_name = field_from_confidence(entity_value, 1.0, "user")
            ctx.extraction.startup_name = ctx.extraction.startup_name or field_from_confidence(
                entity_value, 1.0, "user"
            )
    if founder_value:
        ctx.extraction.founder_name = field_from_confidence(founder_value, 1.0, "user")
    if sector is not None and sector.strip():
        ctx.extraction.sector = field_from_confidence(sector.strip(), 1.0, "user")
    if country is not None and country.strip():
        ctx.extraction.country = field_from_confidence(country.strip(), 1.0, "user")
    if website is not None and website.strip():
        ctx.extraction.website = field_from_confidence(website.strip(), 1.0, "user")

    # Recompute confidence with user-verified values included.
    from .extraction import score_extraction_confidence

    ctx.extraction.confidence = score_extraction_confidence(
        ctx.extraction, text_available=ctx.extraction.text_available
    )
    ctx.requires_confirmation = extraction_failed(atype, ctx.extraction)
    if ctx.status not in (AssessmentStatus.RUNNING, AssessmentStatus.COMPLETE):
        ctx.status = AssessmentStatus.NEEDS_CONFIRMATION if ctx.requires_confirmation else AssessmentStatus.READY
    ctx.refresh_from_extraction()
    return ctx
