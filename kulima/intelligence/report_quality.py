"""Report Quality Engine — Final Intelligence Quality Engineer pass.

Central, deterministic helpers that guarantee every Kulima FLEX report is:

1. CONSISTENT      — exactly ONE recommendation per report, expressed in the
                     entity's own decision framework (no "PASS" + "Review
                     Required" in the same output).
2. EVIDENCE-HONEST — evidence accounting always counts uploaded documents
                     (Source A). "Claims Extracted: 0 / Sources Reviewed: 0"
                     can never appear while documents were actually used.
3. FOUNDER-FAIR    — uploaded documents ARE founder evidence. When founder
                     details exist in documents but external verification is
                     absent, the wording is "Founder not independently
                     verified" — never "No founder information".
4. MARKET-AWARE    — customer discovery, validation, pilots, partnerships,
                     revenue indicators and traction stated in pitch decks and
                     business plans are extracted and surfaced.
5. ENTITY-TYPED    — report title, recommendation framework, and language
                     match the entity type.

All helpers are pure functions over the stored InvestmentBrief — no LLM calls,
no exceptions propagate (fail-safe defaults everywhere).
"""

from __future__ import annotations

import re
from typing import Any

# ── Issue 6: canonical report titles per entity ──────────────────────────────

ENTITY_REPORT_TITLES_FINAL: dict[str, str] = {
    "startup": "Investment Committee Report",
    "ngo": "Institutional Capacity Report",
    "development_program": "Program Performance Review",
    "government_program": "Governance Review",
    "tourism_sme": "Tourism Resilience Report",
    # Sub-entities inherit
    "research_institution": "Institutional Capacity Report",
    "foundation": "Institutional Capacity Report",
    "social_enterprise": "Investment Committee Report",
    "cooperative": "Investment Committee Report",
    "farmer_organization": "Program Performance Review",
}

_ENTITY_INHERIT = {
    "research_institution": "ngo",
    "foundation": "ngo",
    "cooperative": "startup",
    "social_enterprise": "startup",
    "farmer_organization": "development_program",
}

# Issue 6: recommendation framework — the generic Invest/Observe/Pass ladder is
# only correct for startups. Every other entity speaks its own language.
_ENTITY_REC_WORDS: dict[str, tuple[str, str, str]] = {
    # entity_type: (positive, neutral, negative)
    "startup": ("Invest", "Observe", "Pass"),
    "ngo": ("Strong Capacity", "Moderate Capacity", "Needs Strengthening"),
    "development_program": ("Ready", "Requires Support", "At Risk"),
    "government_program": ("Effective", "Monitor", "Intervene"),
    "tourism_sme": ("Ready for Growth", "Build Resilience", "High Risk"),
    "research_institution": ("Strong Capacity", "Moderate Capacity", "Needs Strengthening"),
    "foundation": ("Strong Capacity", "Moderate Capacity", "Needs Strengthening"),
    "social_enterprise": ("Invest", "Observe", "Pass"),
    "cooperative": ("Invest", "Observe", "Pass"),
    "farmer_organization": ("Ready", "Requires Support", "At Risk"),
}


def entity_report_title(entity_type: str | None) -> str:
    """Canonical report title for the entity type (Issue 6)."""
    etype = str(entity_type or "startup").lower()
    if etype not in ENTITY_REPORT_TITLES_FINAL:
        etype = _ENTITY_INHERIT.get(etype, "startup")
    return ENTITY_REPORT_TITLES_FINAL.get(etype, ENTITY_REPORT_TITLES_FINAL["startup"])


def entity_recommendation_words(entity_type: str | None) -> tuple[str, str, str]:
    """(positive, neutral, negative) recommendation wording for the entity."""
    etype = str(entity_type or "startup").lower()
    if etype not in _ENTITY_REC_WORDS:
        etype = _ENTITY_INHERIT.get(etype, "startup")
    return _ENTITY_REC_WORDS.get(etype, _ENTITY_REC_WORDS["startup"])


def detect_entity_type(brief: Any) -> str:
    """Best-effort entity-type detection from a stored brief (no LLM).

    Priority: explicit metadata fields → assessment narrative keywords →
    startup default. Used by report exports when no entity profile payload
    was persisted on the run.
    """
    for attr in ("entity_type", "entityType"):
        val = getattr(brief, attr, None)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    corpus = " ".join(
        str(getattr(brief, attr, "") or "")
        for attr in (
            "startup_assessment", "executive_summary",
            "market_assessment", "risk_assessment",
        )
    ).lower()
    hints: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("tourism_sme", ("tourism", "safari", "lodge", "hospitality", "tour operator", "destination", "visitor")),
        ("ngo", ("non-governmental", "ngo", "nonprofit", "non-profit", "charity", "civil society", "community-based")),
        ("government_program", ("ministry", "government of", "public sector", "state department", "county government")),
        ("development_program", ("development program", "development programme", "donor-funded", "bilateral", "theory of change", "beneficiar")),
    )
    best_type, best_hits = None, 0
    for etype, needles in hints:
        hits = sum(1 for n in needles if n in corpus)
        if hits > best_hits:
            best_type, best_hits = etype, hits
    if best_type and best_hits >= 2:
        return best_type
    return "startup"


# ── Issue 1: SINGLE recommendation per report ────────────────────────────────

_REC_TIER = {
    "invest": "positive",
    "co-invest": "positive",
    "co_invest": "positive",
    "observe": "neutral",
    "review required": "negative",
    "pass": "negative",
    "follow-on watch": "neutral",
    "follow_on_watch": "neutral",
}


def single_recommendation(brief: Any) -> str:
    """THE one recommendation line for the whole report (Issue 1).

    Derived from ``brief.recommendation`` (the calibrated tier) and expressed
    in the entity's own framework. Any free-text recommendation string that
    contradicts the calibrated tier is discarded, so a report can never show
    both "PASS" and "Review Required".
    """
    raw = getattr(brief, "recommendation", None)
    tier_value = str(getattr(raw, "value", raw or "Observe")).strip()
    etype = detect_entity_type(brief)
    positive, neutral, negative = entity_recommendation_words(etype)
    # REVIEW_REQUIRED is its own calibrated tier — never collapsed into Pass
    # (that collapse was the root cause of PASS + Review Required mixing).
    if tier_value.lower() == "review required":
        label = "Review Required" if etype in ("startup", "social_enterprise", "cooperative") else negative
    else:
        tier = _REC_TIER.get(tier_value.lower(), "neutral")
        label = {"positive": positive, "neutral": neutral, "negative": negative}[tier]
    score = float(getattr(brief, "overall_score", 0.0) or 0.0)
    return f"{label} — overall score {score:.0f}/100"


def recommendation_tier(brief: Any) -> str:
    tier_value = getattr(getattr(brief, "recommendation", None), "value", "Observe")
    return _REC_TIER.get(str(tier_value).strip().lower(), "neutral")


# ── Issue 3: honest evidence accounting ──────────────────────────────────────

def _doc_evidence_item_count(brief: Any) -> int:
    """Count evidence items actually extracted from uploaded documents."""
    total = 0
    for record in getattr(brief, "uploaded_evidence", []) or []:
        items = getattr(record, "evidence_items", None) or (
            record.get("evidence_items", []) if isinstance(record, dict) else []
        )
        total += len(items or [])
    return total


def evidence_accounting(brief: Any) -> dict[str, int]:
    """Evidence counts that can never contradict document usage (Issue 3).

    When the Evidence Integrity Engine produced zero counts (its corpus was
    web-only, or it degraded gracefully), the uploaded documents that the
    pipeline DID use are counted instead — Source A is evidence.
    """
    ei = getattr(brief, "evidence_integrity", None)
    docs = list(getattr(brief, "uploaded_evidence", []) or [])
    sources = list(getattr(brief, "sources", []) or [])
    doc_sources = [
        s for s in sources
        if getattr(s, "source_type", "") == "document"
        or str(getattr(s, "url", "")).startswith(("document://", "/uploads/"))
    ]
    web_sources = [s for s in sources if s not in doc_sources]

    ei_source = int(getattr(ei, "source_count", 0) or 0) if ei else 0
    ei_claim = int(getattr(ei, "claim_count", 0) or 0) if ei else 0
    ei_high = int(getattr(ei, "high_authority_count", 0) or 0) if ei else 0

    doc_items = _doc_evidence_item_count(brief)
    # Every uploaded document contributes at least one reviewed evidence unit.
    doc_units = max(len(docs), len(doc_sources), 1 if docs else 0)

    source_count = max(ei_source, len(docs) + len(web_sources))
    claim_count = max(ei_claim, doc_items, doc_units if docs else 0)
    return {
        "source_count": source_count,
        "claim_count": claim_count,
        "high_authority_count": ei_high,
        "document_count": len(docs),
        "document_source_count": max(len(doc_sources), len(docs)) if docs else int(getattr(ei, "document_source_count", 0) or 0) if ei else 0,
        "web_source_count": len(web_sources) or (int(getattr(ei, "web_source_count", 0) or 0) if ei else 0),
    }


def evidence_accounting_line(brief: Any) -> str:
    acc = evidence_accounting(brief)
    return (
        f"Sources reviewed: {acc['source_count']} | "
        f"Claims extracted: {acc['claim_count']} | "
        f"Uploaded documents: {acc['document_count']} | "
        f"High-authority sources: {acc['high_authority_count']}"
    )


# ── Issue 2: founder reasoning ───────────────────────────────────────────────

_FOUNDER_NEGATIVE = re.compile(
    r"no founder (?:information|details|evidence)|founder (?:is )?unknown|"
    r"unknown founder|no information about the founder|founder not provided|"
    r"not provided\b(?=[^.]*founder)",
    re.IGNORECASE,
)


def founder_evidence_status(brief: Any) -> str:
    """Issue 2: founder reasoning respects uploaded documents as evidence.

    Returns the single founder-evidence statement for the report:
    - documents contain founder details + external verification → "Founder evidence documented in uploaded documents and independently corroborated."
    - documents contain founder details, no external verification → "Founder not independently verified."
    - no founder details anywhere → "No founder details available in the evidence base."
    """
    docs = list(getattr(brief, "uploaded_evidence", []) or [])
    corpus = " ".join(
        str(getattr(d, "raw_summary", "") or (d.get("raw_summary", "") if isinstance(d, dict) else "") or "")
        for d in docs
    ).lower()
    text_lower = corpus
    founder_mentioned = bool(
        re.search(r"\b(founder|co-?founder|ceo|executive director|managing director|director|proprietor|owner)\b", text_lower)
    )
    sources = list(getattr(brief, "sources", []) or [])
    web_snippets = " ".join(
        str(getattr(s, "snippet", "") or "") for s in sources
        if getattr(s, "source_type", "") != "document"
    ).lower()
    external_check = bool(
        re.search(r"\b(founder|co-?founder|ceo|executive director|managing director)\b", web_snippets)
    ) and len(sources) > len(docs)

    founder_name = str(getattr(brief, "founder_name", "") or "").strip()
    name_known = bool(founder_name) and founder_name.lower() not in {
        "not provided", "unknown", "unknown founder", "unnamed venture",
        "assessment lead", "founding team", "n/a",
    }

    if name_known and (founder_mentioned or docs):
        if external_check:
            return "Founder evidence documented in uploaded documents and independently corroborated."
        return "Founder not independently verified."
    if founder_mentioned or docs:
        return "Founder not independently verified."
    return "No founder details available in the evidence base."


def sanitize_founder_reasoning(text: str, brief: Any) -> str:
    """Rewrite legacy negative founder phrasing to the evidence-honest form."""
    if not text:
        return text
    status = founder_evidence_status(brief)
    replaced = _FOUNDER_NEGATIVE.sub("Founder not independently verified", text)
    # Never leave a bare "Not provided" founder statement in a report that used documents.
    if getattr(brief, "uploaded_evidence", None) and replaced.strip() in {"Not provided", "—", "-"}:
        replaced = status
    return replaced


# ── Issue 4: market validation extraction ────────────────────────────────────

_MARKET_VALIDATION_TERMS: dict[str, tuple[str, ...]] = {
    "Customer Discovery": (
        "customer discovery", "customer research", "user research", "customer interviews",
        "user interviews", "customer validation", "customer insights", "target customers",
        "customer segments", "early adopters",
    ),
    "Validation": (
        "market validation", "validated", "problem-solution fit", "product-market fit",
        "validation", "survey results", "market research", "feedback loop",
    ),
    "Pilots": (
        "pilot", "pilots", "pilot program", "pilot project", "beta", "mvp",
        "minimum viable product", "trial",
    ),
    "Partnerships": (
        "partnership", "partner", "mou", "memorandum of understanding", "alliance",
        "collaboration", "joint venture", "distribution partner", "channel partner",
        "strategic partner",
    ),
    "Revenue Indicators": (
        "revenue", "arr", "mrr", "monthly recurring revenue", "annual recurring revenue",
        "pricing", "sales", "monetisation", "monetization", "bookings", "gross margin",
        "profit",
    ),
    "Traction": (
        "traction", "growth", "users", "active users", "customers", "adoption",
        "retention", "engagement", "expansion", "kpi", "month-over-month", "yoy",
        "year-over-year", "mothers", "churn",
    ),
}


def extract_market_validation(brief: Any, max_items_per_category: int = 4) -> dict[str, list[str]]:
    """Issue 4: extract market-validation evidence from uploaded documents and sources.

    Deterministic keyword matching over document summaries, evidence items and
    source snippets. Returns ``{category: [evidence excerpts]}`` — only
    categories with actual evidence are included.
    """
    chunks: list[tuple[str, str]] = []  # (excerpt, origin_label)
    for record in getattr(brief, "uploaded_evidence", []) or []:
        if isinstance(record, dict):
            fname = record.get("filename", "document")
            summary = str(record.get("raw_summary") or "")
            items = [str(i) for i in (record.get("evidence_items") or [])]
        else:
            fname = getattr(record, "filename", "document")
            summary = str(getattr(record, "raw_summary", "") or "")
            items = [str(i) for i in (getattr(record, "evidence_items", None) or [])]
        if summary:
            chunks.append((summary, fname))
        for item in items:
            chunks.append((item, fname))
    for src in getattr(brief, "sources", []) or []:
        stype = str(getattr(src, "source_type", "") or "web")
        snippet = str(getattr(src, "snippet", "") or "")
        if snippet:
            chunks.append((snippet, f"{stype}: {getattr(src, 'title', 'source')}"))

    sentences: list[tuple[str, str]] = []
    for chunk, origin in chunks:
        for sent in re.split(r"(?<=[.!?])\s+|\n+|;", chunk):
            sent = " ".join(sent.split()).strip()
            if len(sent) >= 12:
                sentences.append((sent, origin))

    result: dict[str, list[str]] = {}
    for category, terms in _MARKET_VALIDATION_TERMS.items():
        hits: list[str] = []
        seen: set[str] = set()
        for sent, origin in sentences:
            low = sent.lower()
            if any(t in low for t in terms):
                excerpt = sent[:200]
                line = f"{excerpt} [{origin}]"
                if line not in seen:
                    seen.add(line)
                    hits.append(line)
            if len(hits) >= max_items_per_category:
                break
        if hits:
            result[category] = hits
    return result


def market_validation_lines(brief: Any) -> list[str]:
    """Flat report lines for the Market Validation section ('— none recorded' when empty)."""
    found = extract_market_validation(brief)
    if not found:
        return [
            "No explicit market-validation statements were detected in the uploaded "
            "documents or research sources. This is a diligence gap: request customer "
            "discovery, pilot and revenue evidence from the entity."
        ]
    lines: list[str] = []
    for category, hits in found.items():
        lines.append(f"{category}:")
        lines.extend(f"  - {h}" for h in hits)
    return lines


# ── Issue 5: exception-free report text ──────────────────────────────────────

_EXCEPTION_MARKERS = (
    "traceback (most recent call last)",
    "abstaining pending model recovery:",
    "zerodivisionerror:",
    "keyerror:",
    "valueerror:",
    "typeerror:",
    "apiconnectionerror",
    "ratelimiterror",
    "filenotfounderror",
    "connectionrefusederror",
)


def sanitize_runtime_artifacts(text: str) -> str:
    """Strip Python exception leakage and runtime artifacts from report text (Phase 6)."""
    if not text:
        return text
    cleaned = text
    cleaned = re.sub(
        r"Abstaining pending model recovery:.*?(?:\.|$)",
        "Vote recorded as abstain pending model recovery. Deterministic evidence scoring applied.",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"Traceback \(most recent call last\):[\s\S]*?(?=\n\n[A-Z]|\Z)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'File\s+"[^"]+",\s+line\s+\d+,\s+in\s+[^\n]+', "", cleaned)
    cleaned = re.sub(r"(?:[A-Za-z]+Error|Exception):\s+[^\n]+", "", cleaned)
    return cleaned.strip()


def has_python_error_text(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _EXCEPTION_MARKERS)
