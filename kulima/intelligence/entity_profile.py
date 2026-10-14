"""Entity-aware intelligence layer (Phases 1–7 of the quality upgrade).

Before any research runs, uploaded documents are classified and the entity is
profiled from *document evidence first* (Source A). External web research
(Source C) never overrules uploaded documents — it can only corroborate or,
where contradictions exist, flag them.

Key exports:
    classify_documents()      — Phase 1 document classification
    classify_entity()         — Phase 2 entity classification
    entity_signal_domains()   — Phase 3 entity-aware signal domains
    entity_research_queries() — Phase 4 entity-aware research focus
    entity_decision_framework() — Phase 5 decision frameworks
    entity_report_title()     — Phase 6 entity-adaptive report titles
    build_entity_profile()    — one-shot profile used by every workspace
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ── Phase 1: Document classification ─────────────────────────────────────

DOCUMENT_CLASSES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Business Plan", ("business plan", "executive summary", "business model", "value proposition", "go-to-market", "revenue model")),
    ("Annual Report", ("annual report", "fiscal year", "audited financial", "year in review", "annual accounts")),
    ("Proposal", ("proposal", "terms of reference", "scope of work", "rfp", "concept note")),
    ("Budget", ("budget", "budget line", "expenditure", "cost breakdown", "financial plan")),
    ("M&E Report", ("monitoring and evaluation", "m&e", "logframe", "logical framework", "theory of change", "outcome indicators", "results framework")),
    ("Tourism Strategy", ("tourism strategy", "destination", "visitor economy", "tourism development", "hospitality strategy")),
    ("Financial Statements", ("balance sheet", "income statement", "cash flow", "statement of financial position", "profit and loss", "audited accounts")),
    ("Policy Document", ("policy", "policy brief", "regulation", "legislation", "act no", "policy framework")),
    ("Investment Memo", ("investment memo", "investment memorandum", "ic memo", "deal memo", "investment case")),
    ("Project Report", ("project report", "progress report", "interim report", "final report", "narrative report")),
    ("Pitch Deck", ("pitch deck", "investor deck", "slide", "deck", "term sheet")),
    ("Strategic Plan", ("strategic plan", "strategy 20", "five-year plan", "corporate strategy", "theory of change")),
    ("Grant Application", ("grant application", "grant proposal", "call for proposals", "funding request", "application form")),
    ("Community Survey", ("community survey", "survey results", "questionnaire", "respondents", "focus group")),
)

# Filename-first classifiers (cheap, applied before content scan).
_FILENAME_CLASSES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Business Plan", ("business_plan", "business plan", "bp_")),
    ("Annual Report", ("annual_report", "annual report")),
    ("Tourism Strategy", ("tourism_strategy", "tourism strategy", "tourism")),
    ("Financial Statements", ("financial_statement", "financial statement", "financials", "financial_")),
    ("Proposal", ("proposal",)),
    ("Budget", ("budget",)),
    ("M&E Report", ("m&e", "me_report", "monitoring")),
    ("Pitch Deck", ("pitch", "deck")),
    ("Strategic Plan", ("strategic_plan", "strategy")),
    ("Grant Application", ("grant",)),
    ("Community Survey", ("survey",)),
    ("Project Report", ("project_report", "report")),
    ("Investment Memo", ("memo",)),
    ("Policy Document", ("policy",)),
)


@dataclass
class DocumentClassification:
    filename: str
    doc_class: str
    confidence: float
    matched_terms: List[str] = field(default_factory=list)


def classify_documents(
    documents: Sequence[dict],
) -> List[DocumentClassification]:
    """Phase 1 — classify each uploaded document before research begins.

    ``documents`` items may carry ``name``/``filename`` and ``rawSummary``/
    ``raw_summary``/``evidence_items``. Classification is deterministic.
    """
    results: List[DocumentClassification] = []
    for doc in documents or []:
        filename = str(doc.get("name") or doc.get("filename") or doc.get("title") or "document")
        name_lower = filename.lower()
        text = " ".join(
            str(doc.get(key) or "")
            for key in ("rawSummary", "raw_summary", "summary")
        )
        items = doc.get("evidenceItems") or doc.get("evidence_items") or []
        text = (text + " " + " ".join(str(i) for i in items)).lower()

        # Filename match first (strong signal, high confidence).
        for cls, needles in _FILENAME_CLASSES:
            if any(n in name_lower for n in needles):
                results.append(DocumentClassification(
                    filename=filename, doc_class=cls, confidence=0.9,
                    matched_terms=[n for n in needles if n in name_lower][:3],
                ))
                break
        else:
            # Content scan.
            best_cls, best_count, best_terms = "General Document", 0, []
            for cls, needles in DOCUMENT_CLASSES:
                hits = [n for n in needles if n in text]
                if len(hits) > best_count:
                    best_cls, best_count, best_terms = cls, len(hits), hits
            confidence = min(0.85, 0.4 + 0.15 * best_count) if best_count else 0.35
            results.append(DocumentClassification(
                filename=filename, doc_class=best_cls,
                confidence=round(confidence, 2), matched_terms=best_terms[:4],
            ))
    return results


# ── Phase 2: Entity classification ───────────────────────────────────────

ENTITY_TYPES: Tuple[str, ...] = (
    "startup", "ngo", "development_program", "government_program",
    "tourism_sme", "research_institution", "social_enterprise",
    "foundation", "cooperative", "farmer_organization",
)

ENTITY_LABELS: Dict[str, str] = {
    "startup": "Startup",
    "ngo": "NGO",
    "development_program": "Development Program",
    "government_program": "Government Program",
    "tourism_sme": "Tourism SME",
    "research_institution": "Research Institution",
    "social_enterprise": "Social Enterprise",
    "foundation": "Foundation",
    "cooperative": "Cooperative",
    "farmer_organization": "Farmer Organization",
}

# Canonical assessment types map 1:1 onto the primary entity families.
_ASSESSMENT_TYPE_TO_ENTITY = {
    "startup": "startup",
    "accelerator": "startup",
    "ngo": "ngo",
    "development_program": "development_program",
    "government_program": "government_program",
    "tourism_sme": "tourism_sme",
}

# Text evidence that refines the declared type into a sub-entity.
_ENTITY_TEXT_HINTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("cooperative", ("cooperative", "co-operative", "sacco", "member-owned")),
    ("farmer_organization", ("farmer organization", "farmers association", "farmers' association", "producer organization", "cooperative union")),
    ("foundation", ("foundation", "endowment", "philanthropic")),
    ("research_institution", ("research institute", "research institution", "university", "think tank", "polytechnic", "institute of")),
    ("social_enterprise", ("social enterprise", "social business", "hybrid model", "impact-first", "non-profit business model")),
    ("development_program", ("development program", "development programme", "donor-funded", "bilateral", "multi-donor", "undp", "usaid", "dfid", "fao", "world bank project", "giz", "eu-funded", "meal team", "meal teams", "development intelligence")),
    ("ngo", ("non-governmental", "ngo", "ngos", "nonprofit", "non-profit", "charity", "civil society", "community-based organization", "ngo consortium", "ngo consortia")),
    ("government_program", ("ministry", "government of", "national program", "public sector", "state department", "county government")),
    ("tourism_sme", ("tourism", "safari", "lodge", "hospitality", "tour operator", "travel", "destination", "visitor")),
    ("startup", ("startup", "start-up", "venture", "seed round", "series a", "saas", "b2b", "business plan")),
)


@dataclass
class EntityClassification:
    entity_type: str
    label: str
    confidence: float
    source: str                      # "declared" | "document_evidence" | "inferred"
    signals_detected: List[str] = field(default_factory=list)


def classify_entity(
    assessment_type: str | None,
    document_text: str = "",
    document_classes: Sequence[DocumentClassification] = (),
) -> EntityClassification:
    """Phase 2 — classify the entity, preferring document evidence.

    The declared assessment type is the floor, not the ceiling: a "startup"
    declaration whose documents read like an NGO proposal is still classified
    by what the documents say, with the declared type kept as fallback.
    """
    atype = _ASSESSMENT_TYPE_TO_ENTITY.get(str(assessment_type or "").lower())
    text = (document_text or "").lower()
    doc_text = " ".join(
        " ".join(d.matched_terms) + " " + d.doc_class for d in document_classes
    ).lower()
    corpus = f"{text} {doc_text}"

    best_type, best_hits = None, 0
    for etype, needles in _ENTITY_TEXT_HINTS:
        hits = [n for n in needles if n in corpus]
        if len(hits) > best_hits:
            best_type, best_hits = etype, len(hits)

    if best_type and best_type != atype and best_hits >= 2:
        # Document evidence is explicit enough to refine/override the declared type.
        return EntityClassification(
            entity_type=best_type, label=ENTITY_LABELS[best_type],
            confidence=min(0.9, 0.5 + 0.1 * best_hits),
            source="document_evidence",
            signals_detected=[ENTITY_LABELS[best_type]],
        )
    if atype:
        return EntityClassification(
            entity_type=atype, label=ENTITY_LABELS[atype],
            confidence=0.75 if best_hits else 0.6,
            source="declared",
        )
    if best_type:
        return EntityClassification(
            entity_type=best_type, label=ENTITY_LABELS[best_type],
            confidence=min(0.8, 0.4 + 0.1 * best_hits), source="inferred",
        )
    return EntityClassification("startup", "Startup", 0.4, "inferred")


# ── Phase 3: Entity-aware signal domains ─────────────────────────────────

ENTITY_SIGNAL_DOMAINS: Dict[str, Tuple[str, ...]] = {
    "startup": ("Founder Risk", "Market Readiness", "Revenue Potential", "Investment Readiness"),
    "ngo": ("Institutional Capacity", "Program Delivery", "Partnership Strength", "Funding Diversity", "Monitoring Capacity", "Community Reach"),
    "development_program": ("Program Performance", "Implementation Readiness", "Beneficiary Reach", "Impact Evidence"),
    "government_program": ("Governance", "Policy Alignment", "Delivery Capacity", "Public Value"),
    "tourism_sme": ("Tourism Signals", "Climate Signals", "Community Signals", "Destination Readiness", "Visitor Economy Signals"),
    "research_institution": ("Research Quality", "Partnership Strength", "Funding Diversity", "Knowledge Transfer"),
    "social_enterprise": ("Founder Risk", "Impact Evidence", "Revenue Potential", "Community Reach"),
    "foundation": ("Governance", "Grantmaking Capacity", "Funding Diversity", "Public Value"),
    "cooperative": ("Member Governance", "Program Delivery", "Revenue Potential", "Community Reach"),
    "farmer_organization": ("Member Governance", "Market Readiness", "Community Reach", "Funding Diversity"),
}

# Keyword detectors per domain so evidence items can be attributed.
_DOMAIN_DETECTORS: Dict[str, Tuple[str, ...]] = {
    "Founder Risk": ("founder", "ceo", "leadership team", "co-founder", "track record", "management"),
    "Market Readiness": ("market", "customers", "demand", "validation", "pilot", "adoption", "target segment", "tam"),
    "Revenue Potential": ("revenue", "pricing", "business model", "monetisation", "monetization", "profit", "margins", "contract"),
    "Investment Readiness": ("funding", "investment", "raise", "round", "capital", "ask", "valuation", "use of funds", "roadmap"),
    "Institutional Capacity": ("board", "governance", "organisation structure", "organization structure", "staff", "policies", "systems"),
    "Program Delivery": ("program", "programme", "delivery", "implementation", "activities", "beneficiaries", "reached"),
    "Partnership Strength": ("partner", "partnership", "memorandum of understanding", "mou", "collaboration", "consortium"),
    "Funding Diversity": ("grant", "donor", "funding sources", "diversif", "income streams", "crowdfunding", "earned income"),
    "Monitoring Capacity": ("monitoring", "evaluation", "m&e", "indicators", "data collection", "reporting", "learning"),
    "Community Reach": ("community", "beneficiar", "women", "youth", "households", "villages", "outreach"),
    "Program Performance": ("performance", "results", "achieved", "delivered", "targets", "outcomes"),
    "Implementation Readiness": ("implementation", "workplan", "work plan", "timeline", "milestones", "gantt", "phases"),
    "Beneficiary Reach": ("beneficiar", "households", "farmers", "reach", "coverage", "participants"),
    "Impact Evidence": ("impact", "outcomes", "evidence", "evaluation", "baseline", "endline", "attribution"),
    "Governance": ("governance", "board", "oversight", "accountability", "transparency", "procurement", "audit"),
    "Policy Alignment": ("policy", "national development", "sdg", "sustainable development goals", "agenda", "strategy alignment", "vision 2030"),
    "Delivery Capacity": ("capacity", "delivery", "implementation", "infrastructure", "systems", "staffing"),
    "Public Value": ("public", "citizens", "taxpayer", "service delivery", "public goods", "welfare"),
    "Tourism Signals": ("tourism", "tourist", "visitors", "bookings", "occupancy", "attractions", "itinerary"),
    "Climate Signals": ("climate", "weather", "drought", "flood", "resilience", "carbon", "adaptation", "emissions"),
    "Community Signals": ("community", "local", "employment", "jobs", "culture", "heritage", "benefits"),
    "Destination Readiness": ("destination", "infrastructure", "access", "roads", "airport", "amenities", "certification"),
    "Visitor Economy Signals": ("visitor economy", "spending", "tourism revenue", "seasonality", "market segments", "source markets"),
    "Research Quality": ("research", "publications", "peer-reviewed", "methodology", "studies", "data"),
    "Knowledge Transfer": ("training", "capacity building", "dissemination", "extension", "knowledge"),
    "Grantmaking Capacity": ("grantmaking", "grants", "disbursement", "portfolio", "giving"),
    "Member Governance": ("members", "membership", "elected", "committee", "constitution", "bylaws"),
    "Impact-First Governance": ("impact", "mission", "social"),
}


def entity_signal_domains(entity_type: str) -> Tuple[str, ...]:
    return ENTITY_SIGNAL_DOMAINS.get(entity_type, ENTITY_SIGNAL_DOMAINS["startup"])


def detect_domain_evidence(corpus: str, domains: Iterable[str]) -> Dict[str, List[str]]:
    """For each requested domain return matched evidence terms from the corpus."""
    text = (corpus or "").lower()
    out: Dict[str, List[str]] = {}
    for domain in domains:
        hits = [n for n in _DOMAIN_DETECTORS.get(domain, ()) if n in text]
        out[domain] = hits
    return out


# ── Phase 4: Entity-aware research focus ─────────────────────────────────

ENTITY_RESEARCH_QUERIES: Dict[str, Tuple[str, ...]] = {
    "startup": ("{name} funding round investment", "{name} market traction customers", "{sector} startup market size Africa", "{name} competitors market"),
    "ngo": ("{name} annual report programs", "{name} donors partners funding", "{sector} NGO program impact", "{name} beneficiaries outcomes"),
    "development_program": ("{name} program results implementation", "{name} beneficiaries impact evaluation", "{sector} development program outcomes", "{name} donor funding"),
    "government_program": ("{name} policy implementation", "{name} public service delivery", "{sector} government program outcomes", "{name} governance oversight"),
    "tourism_sme": ("{name} tourism lodge reviews", "{sector} tourism destination trends Africa", "climate risk tourism {country}", "{name} visitor economy hospitality"),
    "research_institution": ("{name} research publications", "{name} partnerships funding", "{sector} research findings"),
    "social_enterprise": ("{name} impact business model", "{name} funding social enterprise", "{sector} social enterprise market"),
    "foundation": ("{name} grantmaking portfolio", "{name} foundation programs", "{sector} foundation funding"),
    "cooperative": ("{name} cooperative members", "{name} market sales", "{sector} cooperative development"),
    "farmer_organization": ("{name} farmer organization programs", "{sector} smallholder market access", "{name} members impact"),
}


def entity_research_queries(entity_type: str, name: str, sector: str = "", country: str = "") -> Tuple[str, ...]:
    templates = ENTITY_RESEARCH_QUERIES.get(
        entity_type, ENTITY_RESEARCH_QUERIES["startup"]
    )
    subs = {"name": name or "", "sector": sector or "", "country": country or ""}
    return tuple(t.format(**subs).strip() for t in templates)


# ── Phase 5: Entity-aware decision frameworks ────────────────────────────

@dataclass(frozen=True)
class DecisionFramework:
    entity_type: str
    bands: Tuple[Tuple[float, str, str], ...]   # (threshold, band_key, label)
    positive_band: str
    neutral_band: str
    negative_band: str


ENTITY_DECISION_FRAMEWORKS: Dict[str, DecisionFramework] = {
    "startup": DecisionFramework(
        "startup",
        ((72.0, "invest", "Invest"), (58.0, "observe", "Observe"), (0.0, "pass", "Pass")),
        "invest", "observe", "pass",
    ),
    "ngo": DecisionFramework(
        "ngo",
        ((72.0, "strong_capacity", "Strong Capacity"), (55.0, "moderate_capacity", "Moderate Capacity"), (0.0, "needs_strengthening", "Needs Strengthening")),
        "strong_capacity", "moderate_capacity", "needs_strengthening",
    ),
    "development_program": DecisionFramework(
        "development_program",
        ((72.0, "ready", "Ready"), (55.0, "requires_support", "Requires Support"), (0.0, "at_risk", "At Risk")),
        "ready", "requires_support", "at_risk",
    ),
    "government_program": DecisionFramework(
        "government_program",
        ((72.0, "effective", "Effective"), (55.0, "monitor", "Monitor"), (0.0, "intervene", "Intervene")),
        "effective", "monitor", "intervene",
    ),
    "tourism_sme": DecisionFramework(
        "tourism_sme",
        ((72.0, "ready_for_growth", "Ready for Growth"), (55.0, "build_resilience", "Build Resilience"), (0.0, "high_risk", "High Risk")),
        "ready_for_growth", "build_resilience", "high_risk",
    ),
}
# Sub-entities inherit the closest canonical framework.
_INHERIT = {
    "research_institution": "ngo",
    "social_enterprise": "startup",
    "foundation": "ngo",
    "cooperative": "startup",
    "farmer_organization": "development_program",
}


def entity_decision_framework(entity_type: str) -> DecisionFramework:
    fw = ENTITY_DECISION_FRAMEWORKS.get(entity_type)
    if fw:
        return fw
    parent = ENTITY_DECISION_FRAMEWORKS.get(_INHERIT.get(entity_type, "startup"))
    return parent or ENTITY_DECISION_FRAMEWORKS["startup"]


def entity_decision(score: float, entity_type: str) -> Tuple[str, str]:
    """Map a composite score to (band_key, human label) for the entity type."""
    framework = entity_decision_framework(entity_type)
    for threshold, band_key, label in framework.bands:
        if score >= threshold:
            return band_key, label
    band_key, label = framework.bands[-1][1], framework.bands[-1][2]
    return band_key, label


# ── Phase 6: Entity-adaptive report titles ───────────────────────────────

ENTITY_REPORT_TITLES: Dict[str, str] = {
    "startup": "Startup Assessment Report",
    "ngo": "NGO Capacity Report",
    "development_program": "Development Program Review",
    "government_program": "Government Program Review",
    "tourism_sme": "Tourism Resilience Report",
    "research_institution": "Research Institution Review",
    "social_enterprise": "Social Enterprise Impact Report",
    "foundation": "Foundation Program Review",
    "cooperative": "Cooperative Assessment Report",
    "farmer_organization": "Farmer Organization Review",
}


def entity_report_title(entity_type: str) -> str:
    return ENTITY_REPORT_TITLES.get(entity_type, ENTITY_REPORT_TITLES["startup"])


# ── One-shot profile ─────────────────────────────────────────────────────

@dataclass
class EntityProfile:
    entity: EntityClassification
    documents: List[DocumentClassification]
    signal_domains: Tuple[str, ...]
    research_queries: Tuple[str, ...]
    decision_framework: DecisionFramework
    report_title: str


def build_entity_profile(
    assessment_type: str | None,
    documents: Sequence[dict],
    document_text: str = "",
    *,
    sector: str = "",
    country: str = "",
    entity_name: str = "",
) -> EntityProfile:
    doc_classes = classify_documents(documents)
    entity = classify_entity(assessment_type, document_text, doc_classes)
    # Tourism overrides only when the declared type already agrees OR documents
    # are heavily tourism-classified — otherwise keep the declaration.
    return EntityProfile(
        entity=entity,
        documents=doc_classes,
        signal_domains=entity_signal_domains(entity.entity_type),
        research_queries=entity_research_queries(
            entity.entity_type, entity_name, sector, country
        ),
        decision_framework=entity_decision_framework(entity.entity_type),
        report_title=entity_report_title(entity.entity_type),
    )


def profile_to_payload(profile: EntityProfile) -> dict:
    """JSON-safe payload for the Assessment Context / workspace surfaces."""
    return {
        "entityType": profile.entity.entity_type,
        "entityLabel": profile.entity.label,
        "entityConfidence": round(profile.entity.confidence, 3),
        "entitySource": profile.entity.source,
        "documentClassifications": [
            {
                "filename": d.filename,
                "docClass": d.doc_class,
                "confidence": d.confidence,
                "matchedTerms": d.matched_terms,
            }
            for d in profile.documents
        ],
        "signalDomains": list(profile.signal_domains),
        "researchFocus": list(profile.research_queries),
        "decisionFramework": {
            "entityType": profile.decision_framework.entity_type,
            "bands": [
                {"threshold": t, "band": b, "label": l}
                for t, b, l in profile.decision_framework.bands
            ],
        },
        "reportTitle": profile.report_title,
    }
