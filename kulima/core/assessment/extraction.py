"""Deterministic entity extraction from uploaded documents (Step 3).

This module powers "collect once": after a document is ingested, we attempt to
read the entity identity directly out of the document text so the user never
re-types the startup / organisation / founder name in downstream workspaces.

The extractor is deliberately deterministic (regex + curated dictionaries) so
it works fully offline, is auditable, and never invents values without
recording a confidence.  When extraction confidence is low the caller can ask
the user a single confirming question instead of a full form.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

from .models import AssessmentExtraction, AssessmentType, ExtractedField

# ── Dictionaries ──────────────────────────────────────────────────────────

_COUNTRY_NAMES = (
    "malawi", "kenya", "tanzania", "uganda", "rwanda", "burundi", "zambia",
    "zimbabwe", "mozambique", "south africa", "namibia", "botswana", "angola",
    "nigeria", "ghana", "senegal", "côte d'ivoire", "cote d'ivoire", "mali",
    "burkina faso", "niger", "benin", "togo", "cameroon", "chad", "ethiopia",
    "somalia", "somaliland", "djibouti", "eritrea", "sudan", "south sudan",
    "egypt", "libya", "tunisia", "algeria", "morocco", "mauritania", "gambia",
    "guinea", "guinea-bissau", "sierra leone", "liberia", "congo",
    "democratic republic of the congo", "dr congo", "gabon", "equatorial guinea",
    "madagascar", "mauritius", "seychelles", "comoros", "cape verde", "eswatini",
    "swaziland", "lesotho", "gambia",
)

_SECTOR_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("AgriTech", ("agritech", "agriculture", "smallholder", "farming", "crop", "irrigation", "soya", "maize")),
    ("Clean Energy", ("solar", "renewable", "clean energy", "off-grid", "mini-grid", "biogas", "cooking")),
    ("Tourism & Hospitality", ("tourism", "tourist", "safari", "lodge", "hotel", "hospitality", "visitor", "heritage")),
    ("FinTech", ("fintech", "financial inclusion", "mobile money", "payments", "lending")),
    ("HealthTech", ("health", "clinic", "medical", "telemedicine", "maternal")),
    ("EdTech", ("education", "edtech", "school", "training", "literacy", "skills")),
    ("Logistics & Mobility", ("logistics", "cold chain", "transport", "delivery", "mobility", "distribution")),
    ("Water & Sanitation", ("water", "sanitation", "wash", "borehole", "hygiene")),
    ("Waste & Circular Economy", ("waste", "recycling", "circular", "compost", "plastic")),
    ("Financial Services", ("banking", "insurance", "microfinance", "savings")),
    ("Manufacturing", ("manufactur", "processing plant", "factory", "assembly")),
    ("Climate & Environment", ("climate", "conservation", "biodiversity", "forest", "carbon")),
    ("Community Development", ("community development", "livelihood", "women empowerment", "youth")),
)

_ORG_LABEL_RE = re.compile(
    r"(?:company|organisation|organization|startup|start-up|business|entity|venture|"
    r"programme|program|project|ngo|co-?operative|initiative|enterprise)\s*"
    r"(?:name|title)?\s*[:\-–]\s*"
    r"([A-Z][^\n\r]{1,80})",
    re.IGNORECASE,
)

_FOUNDER_LABEL_RE = re.compile(
    r"(?:founder|co-?founder|ceo|chief executive(?: officer)?|managing director|"
    r"executive director|country director|program(?:me)? (?:director|coordinator|lead)|"
    r"lead(?:er)?|director|chair(?:person|man)?)\s*"
    r"(?:and\s+(?:ceo|founder|director))?[ \t]*[:\-–][ \t]*"
    r"((?:Dr|Mr|Mrs|Ms|Prof|Eng)\.?[ \t]+)?([A-Z][A-Za-z'\-]+(?:[ \t]+[A-Z][A-Za-z'\-]+){1,3})",
    re.IGNORECASE,
)

# ``[ \t]+`` (not ``\s+``) between name parts so a captured person name can
# never swallow the next line of the document.
_FOUNDED_BY_RE = re.compile(
    r"(?:founded|co-?founded|led|managed|established|run)\s+by\s+"
    r"((?:Dr|Mr|Mrs|Ms|Prof|Eng)\.?[ \t]+)?([A-Z][A-Za-z'\-]+(?:[ \t]+[A-Z][A-Za-z'\-]+){1,3})",
    re.IGNORECASE,
)

_PERSON_TITLE_RE = re.compile(
    r"\b(Dr|Mr|Mrs|Ms|Prof|Eng)\.?[ \t]+([A-Z][A-Za-z'\-]+(?:[ \t]+[A-Z][A-Za-z'\-]+){1,2})\b"
)

_ORG_SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&'’\-]*(?:[ \t]+[A-Z][A-Za-z0-9&'’\-]*){0,4}[ \t]+"
    r"(?:Limited|Ltd\.?|Inc\.?|LLC|GmbH|PLC|Company|Co\.?|Cooperative|Co-operative|"
    r"Foundation|Trust|NGO|Enterprises?|Ventures?|Group|Holdings|Capital|Technologies|"
    r"Foods|Agro|Farms|Lodge|Safaris?|Tours|Programme|Program))\b"
)

_URL_RE = re.compile(
    r"(?:https?://|www\.)[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{4,120}",
)

_DOMAIN_RE = re.compile(
    r"\b([A-Za-z0-9\-]+\.(?:com|org|net|io|africa|co\.ke|co\.tz|co\.mw|co\.za|co\.ug|co\.rw|ac\.[a-z]{2})\b)"
)

_TEAM_OF_RE = re.compile(
    r"team of\s+(\d{1,5})", re.IGNORECASE
)

_HEADCOUNT_RE = re.compile(
    r"(\d{1,6})\s+(?:full[-\s]?time\s+|permanent\s+|paid\s+)?"
    r"(?:staff|employees|workers|farmers|agents|team members)",
    re.IGNORECASE,
)

_PROBLEM_LEAD_RE = re.compile(
    r"(?:^|\n)\s*(?:the\s+)?(?:problem|challenge|pain point|issue|why now|context)\s*"
    r"(?:statement)?\s*[:\-–]?\s*",
    re.IGNORECASE,
)

_FILENAME_NOISE_RE = re.compile(
    r"\b(pdf|docx?|xlsx?|csv|txt|pptx?|json|final|draft|v\d+|version|copy|deck|"
    r"pitch|slide|report|model|proposal|application|form|template|scan)\b",
    re.IGNORECASE,
)

_RUN_IDS = ("anonymous", "unknown", "unnamed", "tbd", "n/a", "na", "none")

_EXTRACTION_KEY_FIELDS = ("organization_name", "startup_name", "founder_name", "sector", "country")


def _clean(value: str, limit: int = 80) -> str:
    """Normalise whitespace, strip trailing punctuation, clamp length."""
    text = " ".join((value or "").split())
    text = text.strip(" .,;:-–—|\t")
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].strip()
    return text


def _is_usable(value: str) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    if lowered in _RUN_IDS:
        return False
    if len(lowered) < 3:
        return False
    # Reject strings that are only numbers or punctuation
    if not any(ch.isalpha() for ch in lowered):
        return False
    return True


def _first_match_values(text: str, pattern: re.Pattern[str], *, group_count: int = 2, limit: int = 60) -> Optional[str]:
    match = pattern.search(text)  # type: ignore[arg-type]
    if not match:
        return None
    groups = [g for g in match.groups() if g and g.strip()]
    if not groups:
        return None
    name = groups[-1] if len(groups) >= group_count else groups[0]
    name = _clean(name, limit=limit)
    return name if _is_usable(name) else None


def _extract_organization(text: str, filename: Optional[str]) -> Optional[ExtractedField]:
    # 1. Explicit label ("Company: ...")
    labelled = _first_match_values(text, _ORG_LABEL_RE, group_count=1)
    if labelled and _is_usable(labelled):
        return ExtractedField(value=labelled, confidence=0.85, source="document_label")

    # 2. Legal / institutional suffix on a capitalised name
    suffix_match = _ORG_SUFFIX_RE.search(text)
    if suffix_match:
        candidate = _clean(suffix_match.group(1))
        if _is_usable(candidate):
            return ExtractedField(value=candidate, confidence=0.8, source="document_suffix")

    # 3. Filename-derived fallback (weak but honest signal)
    filename_candidate = _organization_from_filename(filename)
    if filename_candidate:
        return ExtractedField(value=filename_candidate, confidence=0.55, source="filename")

    return None


def _organization_from_filename(filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    base = re.sub(r"\.[A-Za-z0-9]{1,6}$", "", filename)
    base = base.replace("_", " ").replace("-", " ")
    base = _FILENAME_NOISE_RE.sub(" ", base)
    candidate = _clean(base, limit=60)
    if not _is_usable(candidate):
        return None
    # Require at least two words or a known suffix to avoid generic names
    if len(candidate.split()) < 2 and not _ORG_SUFFIX_RE.search(candidate):
        return None
    return candidate


def _extract_founder(text: str) -> Optional[ExtractedField]:
    # 1. Explicit label ("Founder & CEO: Jane Doe")
    labelled = _first_match_values(text, _FOUNDER_LABEL_RE, group_count=2)
    if labelled and _is_usable(labelled):
        return ExtractedField(value=labelled, confidence=0.85, source="document_label")

    # 2. "founded by / led by Jane Doe"
    founded = _first_match_values(text, _FOUNDED_BY_RE, group_count=2)
    if founded and _is_usable(founded):
        return ExtractedField(value=founded, confidence=0.8, source="document_phrase")

    # 3. Titled person name (Dr./Mr./Ms. …) — weakest signal
    titled = _first_match_values(text, _PERSON_TITLE_RE, group_count=2)
    if titled and _is_usable(titled):
        return ExtractedField(value=titled, confidence=0.65, source="document_title")

    return None


def _extract_country(text_lower: str) -> Optional[ExtractedField]:
    for country in _COUNTRY_NAMES:
        if country in text_lower:
            return ExtractedField(value=country.title(), confidence=0.8, source="document_dictionary")
    return None


def _extract_sector(text_lower: str) -> Optional[ExtractedField]:
    best: Optional[Tuple[str, int]] = None
    for label, keywords in _SECTOR_KEYWORDS:
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits and (best is None or hits > best[1]):
            best = (label, hits)
    if best:
        confidence = 0.85 if best[1] >= 3 else (0.72 if best[1] == 2 else 0.6)
        return ExtractedField(value=best[0], confidence=confidence, source="document_dictionary")
    return None


def _extract_website(text: str) -> Optional[ExtractedField]:
    match = _URL_RE.search(text)
    if match:
        return ExtractedField(value=match.group(0).rstrip(".,;"), confidence=0.85, source="document_url")
    match = _DOMAIN_RE.search(text)
    if match:
        return ExtractedField(value=match.group(1), confidence=0.7, source="document_url")
    return None


def _extract_team(text: str) -> Optional[ExtractedField]:
    match = _TEAM_OF_RE.search(text)
    if match:
        return ExtractedField(value=f"Team of {match.group(1)}", confidence=0.8, source="document_metric")
    match = _HEADCOUNT_RE.search(text)
    if match:
        return ExtractedField(value=f"{match.group(1)} staff", confidence=0.7, source="document_metric")
    return None


def _extract_problem_statement(text: str) -> Optional[ExtractedField]:
    match = _PROBLEM_LEAD_RE.search(text)
    if not match:
        return None
    tail = text[match.end():]
    # Take up to two sentences, max ~320 chars
    sentences = re.split(r"(?<=[.!?])\s+", tail.strip())
    statement = " ".join(s for s in sentences[:2]).strip()
    statement = statement[:320]
    if not _is_usable(statement):
        return None
    return ExtractedField(value=statement, confidence=0.7, source="document_section")


def extract_assessment_fields(
    text: str,
    assessment_type: AssessmentType | str = AssessmentType.STARTUP,
    *,
    filename: Optional[str] = None,
) -> AssessmentExtraction:
    """Extract entity fields from a single document's text.

    The same regexes are applied regardless of assessment type; the type only
    influences how the organisation / entity name is mirrored afterwards (see
    :mod:`kulima.core.assessment.service`).
    """
    raw = text or ""
    text_lower = raw.lower()
    text_available = len(raw.strip()) >= 20

    organization = _extract_organization(raw, filename)
    founder = _extract_founder(raw)
    sector = _extract_sector(text_lower)
    country = _extract_country(text_lower)
    website = _extract_website(raw)
    team = _extract_team(raw)
    problem = _extract_problem_statement(raw)

    # Startup name mirrors the organisation name for venture-style documents.
    startup_name = organization

    extraction = AssessmentExtraction(
        organization_name=organization,
        startup_name=startup_name,
        founder_name=founder,
        sector=sector,
        country=country,
        website=website,
        team=team,
        problem_statement=problem,
        text_available=text_available,
    )
    extraction.confidence = score_extraction_confidence(extraction, text_available=text_available)
    return extraction


def score_extraction_confidence(extraction: AssessmentExtraction, *, text_available: bool = True) -> float:
    """Blend per-field confidences into one overall extraction confidence."""
    if not text_available:
        return 0.0

    weights = {
        "organization_name": 0.34,
        "founder_name": 0.26,
        "sector": 0.16,
        "country": 0.14,
        "website": 0.05,
        "team": 0.05,
    }
    total_weight = 0.0
    weighted = 0.0
    for field_name, weight in weights.items():
        confidence = extraction.field_confidence(field_name)
        if confidence > 0:
            weighted += confidence * weight
            total_weight += weight
        else:
            total_weight += 0

    if total_weight == 0:
        return 0.0
    # Normalise by full weight budget so missing fields genuinely lower confidence.
    budget = sum(weights.values())
    return round(min(1.0, weighted / budget), 3)


def best_field(current: Optional[ExtractedField], candidate: Optional[ExtractedField]) -> Optional[ExtractedField]:
    """Keep the higher-confidence field when merging multiple documents."""
    if candidate is None or candidate.is_empty:
        return current
    if current is None or current.is_empty:
        return candidate
    if candidate.confidence > current.confidence:
        return candidate
    # Prefer longer values at equal confidence (usually the fuller legal name).
    if candidate.confidence == current.confidence and len(candidate.value) > len(current.value):
        return candidate
    return current


def merge_extractions(extractions: Iterable[AssessmentExtraction]) -> AssessmentExtraction:
    """Merge per-document extractions, keeping the best value per field."""
    merged = AssessmentExtraction(text_available=False)
    fields = (
        "organization_name",
        "startup_name",
        "founder_name",
        "sector",
        "country",
        "website",
        "team",
        "problem_statement",
    )
    for extraction in extractions:
        if extraction.text_available:
            merged.text_available = True
        for field_name in fields:
            current = getattr(merged, field_name)
            candidate = getattr(extraction, field_name)
            setattr(merged, field_name, best_field(current, candidate))

    merged.confidence = score_extraction_confidence(merged, text_available=merged.text_available)
    return merged


def extract_from_documents(
    documents: Iterable[Tuple[str, str]],
    assessment_type: AssessmentType | str = AssessmentType.STARTUP,
) -> AssessmentExtraction:
    """Extract from ``(filename, text)`` pairs and merge the results."""
    return merge_extractions(
        extract_assessment_fields(text, assessment_type, filename=filename)
        for filename, text in documents
    )
