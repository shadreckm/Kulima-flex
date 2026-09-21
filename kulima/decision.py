"""Expanded Decision Engine (Step 7).

The decision layer consumes the full signal picture — evidence, trust, risk,
opportunity, market, funding, climate, environment, tourism, and community
impact — instead of only trust + risk.

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
# Weights sum to 1.0.
DOMAIN_WEIGHTS: dict[str, float] = {
    "trust": 0.16,
    "risk": 0.18,
    "opportunity": 0.10,
    "market": 0.12,
    "funding": 0.10,
    "climate": 0.09,
    "environmental": 0.08,
    "tourism": 0.07,
    "community_impact": 0.10,
}

# Evidence is not a signal domain; its weight applies only when present.
EVIDENCE_WEIGHT: float = 0.18

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
) -> tuple[float, dict[str, float], float, int]:
    """Blend domain scores + evidence into a composite 0–100 score.

    Returns ``(composite, effective_weights, coverage, populated_count)``.
    Coverage is the fraction of display domains populated with signals.
    """
    components: dict[str, float] = {}
    weights: dict[str, float] = {}
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
        weights[domain.value] = DOMAIN_WEIGHTS[domain.value]

    if evidence_score is not None:
        components["evidence"] = float(max(0.0, min(100.0, evidence_score)))
        weights["evidence"] = EVIDENCE_WEIGHT

    total_weight = sum(weights.values())
    populated = len(components)
    coverage = round(populated / (len(DISPLAY_DOMAINS) + 1), 3)
    if total_weight <= 0:
        return 50.0, {}, coverage, populated

    composite = sum(components[name] * weights[name] for name in weights) / total_weight
    return composite, weights, coverage, populated


def _confidence(coverage: float, populated: int, evidence_score: Optional[float]) -> float:
    base = 0.40 + 0.35 * coverage
    if populated >= 9:
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
) -> dict[str, Any]:
    """Build the expanded decision view from the signal corpus.

    Args:
        signals: All signals generated for the assessment.
        evidence_score: Optional 0–100 evidence cleanliness score (higher =
            cleaner, fewer contradictions / unsupported claims).
        trust_score: Optional live trust-graph score (0–100) which overrides
            the trust domain heuristic when available.

    Returns:
        A dict with ``score``, ``band``, ``recommendation``, ``confidence``,
        ``coverage``, per-domain ``domains`` overviews (score / summary /
        recommendation each), ranked ``contributions``, a ``summary`` sentence,
        and ``rationale`` lines.
    """
    materialised = list(signals)
    overviews = build_domain_overviews(materialised)
    composite, weights, coverage, populated = _blend_components(
        overviews, evidence_score=evidence_score, trust_score=trust_score
    )
    score = round(composite, 1)
    band, recommendation = decision_band(score)

    contributions: list[dict[str, Any]] = []
    for domain in DISPLAY_DOMAINS:
        entry = overviews.get(domain.value) or {}
        if int(entry.get("signal_count") or 0) <= 0:
            continue
        effective = weights.get(domain.value, 0.0)
        if effective <= 0:
            continue
        domain_score = float(entry.get("score", 50))
        if domain.value == "trust" and trust_score is not None:
            domain_score = float(max(0.0, min(100.0, trust_score)))
        contributions.append(
            {
                "domain": domain.value,
                "label": DOMAIN_LABELS[domain],
                "score": int(round(domain_score)),
                "weight": round(effective, 3),
                "impact": round((domain_score - 50.0) * effective, 2),
            }
        )
    contributions.sort(key=lambda c: c["impact"], reverse=True)

    return {
        "score": score,
        "band": band,
        "recommendation": recommendation.value,
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
