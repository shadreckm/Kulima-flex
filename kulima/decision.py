"""Expanded Decision Engine (Step 7).

The decision layer consumes the full signal picture — evidence, community
impact, trust, funding, programme delivery, risk, opportunity, climate,
environment, market and tourism — instead of only trust + risk.

Design notes:

- The engine is deterministic and LLM-free so decisions stay auditable and
  reproducible.
- Domain scores come from :func:`kulima.signals.signals_summary.build_domain_overviews`
  (0–100, higher = healthier); the composite blends them with fixed weights.
- Domains without signals are treated as *unknown* and excluded from the
  composite (weights renormalise over populated domains) so missing data
  lowers confidence rather than silently scoring 50.
- When an evidence score (0–100, higher = cleaner evidence) is supplied it is
  blended in as an additional decision component.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from kulima.models import Recommendation
from kulima.signals.models import Signal
from kulima.signals.signals_summary import (
    DISPLAY_DOMAINS,
    DOMAIN_LABELS,
    build_domain_overviews,
)

# Relative importance of each display domain in the composite score.
# Weights sum to 1.0. This is the default profile: it is programme-shaped
# (community reach, trust and delivery carry the most weight) because NGOs and
# development programmes are the primary customers of V1. Startup-specific
# weightings live in ENTITY_DOMAIN_WEIGHTS["startup"] and apply only when a
# Startup assessment is selected.
DOMAIN_WEIGHTS: dict[str, float] = {
    "community_impact": 0.14,
    "trust": 0.14,
    "funding": 0.11,
    "program_delivery": 0.12,
    "risk": 0.14,
    "opportunity": 0.08,
    "climate": 0.07,
    "environmental": 0.06,
    "market": 0.08,
    "tourism": 0.06,
}

# Phase 5: entity-aware weight profiles so that domains that are CORE to an
# entity type materially drive its decision instead of being garnish.
# Programme delivery + community reach are the business for NGOs and programs;
# Tourism/Climate are the business for a Tourism SME; market/traction/funding
# are the business for a Startup. Profiles are listed primary-customer first.
ENTITY_DOMAIN_WEIGHTS: dict[str, dict[str, float]] = {
    "ngo": {
        "community_impact": 0.28,
        "trust": 0.13,
        "funding": 0.13,
        "program_delivery": 0.18,
        "risk": 0.10,
        "opportunity": 0.05,
        "climate": 0.05,
        "environmental": 0.04,
        "market": 0.02,
        "tourism": 0.02,
    },
    "development_program": {
        "community_impact": 0.24,
        "trust": 0.12,
        "funding": 0.13,
        "program_delivery": 0.22,
        "risk": 0.10,
        "opportunity": 0.05,
        "climate": 0.05,
        "environmental": 0.04,
        "market": 0.03,
        "tourism": 0.02,
    },
    "government_program": {
        "community_impact": 0.22,
        "trust": 0.14,
        "funding": 0.12,
        "program_delivery": 0.20,
        "risk": 0.13,
        "opportunity": 0.05,
        "climate": 0.05,
        "environmental": 0.04,
        "market": 0.03,
        "tourism": 0.02,
    },
    "startup": {
        "trust": 0.14,
        "risk": 0.16,
        "opportunity": 0.13,
        "market": 0.15,
        "funding": 0.12,
        "program_delivery": 0.05,
        "community_impact": 0.08,
        "climate": 0.07,
        "environmental": 0.06,
        "tourism": 0.04,
    },
    "tourism_sme": {
        "trust": 0.12,
        "risk": 0.13,
        "opportunity": 0.08,
        "market": 0.09,
        "funding": 0.07,
        "program_delivery": 0.05,
        "community_impact": 0.06,
        "climate": 0.15,
        "environmental": 0.09,
        "tourism": 0.16,
    },
}
_ENTITY_WEIGHT_INHERIT = {
    "research_institution": "ngo",
    "social_enterprise": "startup",
    "foundation": "ngo",
    "cooperative": "startup",
    "farmer_organization": "development_program",
}


def domain_weights_for(entity_type: str | None) -> dict[str, float]:
    """Return the domain weight profile for an entity type."""
    if not entity_type:
        return DOMAIN_WEIGHTS
    weights = ENTITY_DOMAIN_WEIGHTS.get(entity_type)
    if weights:
        return weights
    parent = ENTITY_DOMAIN_WEIGHTS.get(_ENTITY_WEIGHT_INHERIT.get(entity_type, ""))
    return parent or DOMAIN_WEIGHTS

# Evidence is not a signal domain; its weight applies only when present.
# Phase 1 (Evidence Weighting): uploaded evidence is the dominant source of
# reasoning, so Source A carries the LARGEST single-component weight — a rich
# uploaded corpus can never be outweighed by missing/thin web research.
EVIDENCE_WEIGHT: float = 0.24

# Score bands → narrative band name and the matching Recommendation value.
_BANDS: tuple[tuple[float, str, Recommendation], ...] = (
    (72.0, "proceed", Recommendation.INVEST),
    (58.0, "proceed_with_conditions", Recommendation.REVIEW_REQUIRED),
    (42.0, "review_required", Recommendation.OBSERVE),
    (0.0, "decline", Recommendation.PASS),
)


def decision_band(score: float) -> tuple[str, Recommendation]:
    """Map a 0–100 composite score to (band name, recommendation)."""
    for threshold, band, recommendation in _BANDS:
        if score >= threshold:
            return band, recommendation
    return "decline", Recommendation.PASS


def _blend_components(
    overviews: dict[str, dict],
    *,
    evidence_score: Optional[float],
    trust_score: Optional[float],
    weights: Optional[dict[str, float]] = None,
) -> tuple[float, dict[str, float], float, int]:
    """Blend domain scores + evidence into a composite 0–100 score.

    Returns ``(composite, effective_weights, coverage, populated_count)``.
    Coverage is the fraction of display domains populated with signals.
    """
    weights = weights or DOMAIN_WEIGHTS
    components: dict[str, float] = {}
    effective: dict[str, float] = {}
    for domain in DISPLAY_DOMAINS:
        entry = overviews.get(domain.value) or {}
        if int(entry.get("signal_count") or 0) <= 0:
            continue
        score = float(entry.get("score", 50))
        # A live trust-graph score is more authoritative than the signal
        # heuristic, so it overrides the trust domain score when available.
        if domain.value == "trust" and trust_score is not None:
            score = float(max(0.0, min(100.0, trust_score)))
        components[domain.value] = score
        effective[domain.value] = weights.get(domain.value, DOMAIN_WEIGHTS.get(domain.value, 0.05))

    if evidence_score is not None:
        components["evidence"] = float(max(0.0, min(100.0, evidence_score)))
        effective["evidence"] = EVIDENCE_WEIGHT

    total_weight = sum(effective.values())
    populated = len(components)
    coverage = round(populated / (len(DISPLAY_DOMAINS) + 1), 3)
    if total_weight <= 0:
        return 50.0, {}, coverage, populated

    composite = sum(components[name] * effective[name] for name in effective) / total_weight
    return composite, effective, coverage, populated


def _confidence(coverage: float, populated: int, evidence_score: Optional[float]) -> float:
    base = 0.40 + 0.35 * coverage
    if populated >= max(1, len(DISPLAY_DOMAINS) - 1):
        base += 0.10
    if evidence_score is not None:
        base = 0.6 * base + 0.4 * (max(0.0, min(100.0, evidence_score)) / 100.0)
    return round(min(0.95, max(0.1, base)), 3)


def _build_rationale(contributions: list[dict[str, Any]], evidence_score: Optional[float]) -> list[str]:
    reasons: list[str] = []
    for entry in contributions:
        impact = entry["impact"]
        if abs(impact) < 0.15:
            continue
        direction = "uplift" if impact > 0 else "drag"
        reasons.append(
            f"{entry['label']} signals scored {entry['score']}/100 "
            f"({direction} of {abs(impact):.1f} points, weight {entry['weight']:.0%})."
        )
        if len(reasons) >= 5:
            break
    if evidence_score is not None:
        reasons.append(
            f"Evidence integrity contributes {evidence_score:.0f}/100 to the composite decision."
        )
    if not reasons:
        reasons.append(
            "Composite decision is neutral: no dominant domain driver detected yet."
        )
    return reasons


def _build_summary(
    score: float,
    band: str,
    contributions: list[dict[str, Any]],
    populated: int,
) -> str:
    if not contributions:
        return (
            "No domain signals available yet; run the evidence pipeline to populate "
            "the decision picture."
        )
    ordered = sorted(contributions, key=lambda c: c["impact"])
    drag = ordered[0]
    driver = ordered[-1]
    return (
        f"Composite decision score {score:.0f}/100 ({band.replace('_', ' ')}) across "
        f"{populated} populated component(s). Strongest drag: {drag['label']} "
        f"({drag['score']}/100); strongest driver: {driver['label']} ({driver['score']}/100)."
    )


def build_decision_view(
    signals: Iterable[Signal],
    *,
    evidence_score: Optional[float] = None,
    trust_score: Optional[float] = None,
    entity_profile: Optional[dict] = None,
) -> dict[str, Any]:
    """Build the expanded decision view from the signal corpus.

    Args:
        signals: All signals generated for the assessment.
        evidence_score: Optional 0–100 evidence cleanliness score (higher =
            cleaner, fewer contradictions / unsupported claims).
        trust_score: Optional live trust-graph score (0–100) which overrides
            the trust domain heuristic when available.
        entity_profile: Optional entity-aware profile payload. When present,
            the decision band is expressed in the entity's own framework
            (e.g. "Strong Capacity" for NGOs, "Ready for Growth" for Tourism
            SMEs) instead of the generic Invest/Observe/Pass ladder.

    Returns:
        A dict with ``score``, ``band``, ``recommendation``, ``confidence``,
        ``coverage``, per-domain ``domains`` overviews (score / summary /
        recommendation each), ranked ``contributions``, a ``summary`` sentence,
        and ``rationale`` lines. When an entity profile is supplied the result
        also carries ``entityBand``/``entityRecommendation`` plus
        ``entityType``/``reportTitle``.
    """
    materialised = list(signals)
    overviews = build_domain_overviews(materialised)
    # Phase 5: entity-aware domain weights — Tourism/Climate/Community are
    # core decision drivers for a Tourism SME, community impact for NGOs, etc.
    entity_type_for_weights = str((entity_profile or {}).get("entityType") or "")
    active_weights = domain_weights_for(entity_type_for_weights)
    composite, weights, coverage, populated = _blend_components(
        overviews, evidence_score=evidence_score, trust_score=trust_score,
        weights=active_weights,
    )
    score = round(composite, 1)
    band, recommendation = decision_band(score)

    # Phase 5: entity-aware decision framework.
    entity_band: Optional[str] = None
    entity_recommendation: Optional[str] = None
    entity_type: Optional[str] = None
    entity_label: Optional[str] = None
    report_title: Optional[str] = None
    if entity_profile:
        from kulima.intelligence.entity_profile import (
            entity_decision,
            entity_report_title,
        )

        entity_type = str(entity_profile.get("entityType") or "startup")
        entity_label = entity_profile.get("entityLabel") or entity_type
        entity_band, entity_label_band = entity_decision(score, entity_type)
        entity_recommendation = entity_label_band
        report_title = entity_report_title(entity_type)
        # The entity band is the authoritative decision wording.
        band = entity_band
        recommendation = entity_label_band

    contributions: list[dict[str, Any]] = []
    for domain in DISPLAY_DOMAINS:
        entry = overviews.get(domain.value) or {}
        if int(entry.get("signal_count") or 0) <= 0:
            continue
        effective_w = weights.get(domain.value, 0.0)
        if effective_w <= 0:
            continue
        domain_score = float(entry.get("score", 50))
        if domain.value == "trust" and trust_score is not None:
            domain_score = float(max(0.0, min(100.0, trust_score)))
        contributions.append(
            {
                "domain": domain.value,
                "label": DOMAIN_LABELS[domain],
                "score": int(round(domain_score)),
                "weight": round(effective_w, 3),
                "impact": round((domain_score - 50.0) * effective_w, 2),
            }
        )
    contributions.sort(key=lambda c: c["impact"], reverse=True)

    result = {
        "score": score,
        "band": band,
        "recommendation": recommendation.value if hasattr(recommendation, "value") else recommendation,
        "confidence": _confidence(coverage, populated, evidence_score),
        "coverage": coverage,
        "evidence_score": round(float(evidence_score), 1) if evidence_score is not None else None,
        "trust_score": round(float(trust_score), 1) if trust_score is not None else None,
        "summary": _build_summary(score, band, contributions, populated),
        "rationale": _build_rationale(contributions, evidence_score),
        "contributions": contributions,
        "domains": overviews,
        "signal_count": len(materialised),
    }
    if entity_profile:
        result.update({
            "entityType": entity_type,
            "entityLabel": entity_label,
            "entityBand": entity_band,
            "entityRecommendation": entity_recommendation,
            "reportTitle": report_title,
            "domainWeights": {k: round(v, 3) for k, v in active_weights.items()},
        })
    return result
