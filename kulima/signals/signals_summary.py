"""Helper functions for summarising SIGNALS collections (Phase 5B).

These utilities operate purely on the Signal domain model and can be
used by any UI or orchestrator layer.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from kulima.signals.models import Signal, SignalLevel, SignalCategory


def count_signals_by_level(signals: Iterable[Signal]) -> dict[SignalLevel, int]:
    """Return a mapping from SignalLevel → count.

    Levels with zero occurrences are omitted from the result.
    """

    counter: Counter[SignalLevel] = Counter()
    for s in signals:
        counter[s.level] += 1
    return dict(counter)


def count_signals_by_category(signals: Iterable[Signal]) -> dict[SignalCategory, int]:
    """Return a mapping from SignalCategory → count.

    Categories with zero occurrences are omitted from the result.
    """

    counter: Counter[SignalCategory] = Counter()
    for s in signals:
        counter[s.category] += 1
    return dict(counter)


_LEVEL_PRIORITY: dict[SignalLevel, int] = {
    SignalLevel.CRITICAL: 0,
    SignalLevel.HIGH: 1,
    SignalLevel.MEDIUM: 2,
    SignalLevel.LOW: 3,
}


def highest_priority_signals(
    signals: Iterable[Signal],
    *,
    limit: int | None = 5,
) -> list[Signal]:
    """Return the highest-priority signals from the collection.

    Ordering rules:
    - Primary: SignalLevel (CRITICAL → HIGH → MEDIUM → LOW)
    - Secondary: confidence (descending)
    - Tertiary: title (ascending, to keep ordering stable)
    """

    def _sort_key(s: Signal) -> tuple[int, float, str]:
        level_rank = _LEVEL_PRIORITY.get(s.level, 99)
        # Negative confidence so higher confidence comes first.
        return (level_rank, -s.confidence, s.title or "")

    ordered = sorted(list(signals), key=_sort_key)
    if limit is not None and limit >= 0:
        return ordered[:limit]
    return ordered


# ── Domain overview (score / summary / recommendation) ────────────────────
#
# The Signals dashboard displays nine core domains in a fixed order:
# Trust, Risk, Opportunity, Market, Funding, Climate, Environment, Tourism,
# Community. COMPETITIVE and the legacy monitoring categories are folded into
# the closest core domain so no signal becomes invisible; categories with no
# sensible home (e.g. LEARNING, INTERNAL) are excluded from the dashboard.

DISPLAY_DOMAINS: tuple[SignalCategory, ...] = (
    SignalCategory.TRUST,
    SignalCategory.RISK,
    SignalCategory.OPPORTUNITY,
    SignalCategory.MARKET,
    SignalCategory.FUNDING,
    SignalCategory.CLIMATE,
    SignalCategory.ENVIRONMENTAL,
    SignalCategory.TOURISM,
    SignalCategory.COMMUNITY_IMPACT,
)

DOMAIN_LABELS: dict[SignalCategory, str] = {
    SignalCategory.TRUST: "Trust",
    SignalCategory.RISK: "Risk",
    SignalCategory.OPPORTUNITY: "Opportunity",
    SignalCategory.MARKET: "Market",
    SignalCategory.FUNDING: "Funding",
    SignalCategory.CLIMATE: "Climate",
    SignalCategory.ENVIRONMENTAL: "Environment",
    SignalCategory.TOURISM: "Tourism",
    SignalCategory.COMMUNITY_IMPACT: "Community",
}

DOMAIN_ALIASES: dict[SignalCategory, SignalCategory] = {
    SignalCategory.COMPETITIVE: SignalCategory.OPPORTUNITY,
    SignalCategory.GOVERNANCE: SignalCategory.RISK,
    SignalCategory.POLITICAL: SignalCategory.RISK,
    SignalCategory.OPERATIONAL: SignalCategory.RISK,
    SignalCategory.SAFEGUARDING: SignalCategory.RISK,
    SignalCategory.FINANCIAL: SignalCategory.FUNDING,
    SignalCategory.SOCIAL: SignalCategory.COMMUNITY_IMPACT,
    SignalCategory.IMPACT: SignalCategory.COMMUNITY_IMPACT,
}


def display_domain(category: SignalCategory) -> SignalCategory | None:
    """Map a raw signal category to one of the nine dashboard domains."""
    if category in DISPLAY_DOMAINS:
        return category
    return DOMAIN_ALIASES.get(category)


# Impact of a single signal on its domain score, before confidence weighting.
_LEVEL_IMPACT: dict[SignalLevel, float] = {
    SignalLevel.CRITICAL: 30.0,
    SignalLevel.HIGH: 22.0,
    SignalLevel.MEDIUM: 12.0,
    SignalLevel.LOW: 6.0,
}


def score_signals(signals: Iterable[Signal], *, base: int = 50) -> int:
    """Blend a domain's signals into a 0–100 health score.

    The score starts at a neutral ``base``. Opportunity signals raise it,
    risk signals lower it; the magnitude scales with level and confidence.
    """
    score = float(base)
    for s in signals:
        impact = _LEVEL_IMPACT.get(s.level, 10.0) * max(0.0, min(1.0, s.confidence or 0.5))
        if s.direction == "opportunity":
            score += impact * 0.75
        elif s.direction == "risk":
            score -= impact
    return int(round(max(0.0, min(100.0, score))))


def domain_summary(signals: Iterable[Signal]) -> str:
    """One-paragraph narrative for a domain, grounded in its signals."""
    ordered = highest_priority_signals(signals, limit=None)
    if not ordered:
        return "No signals generated for this domain yet."

    top = ordered[0]
    lead = (top.evidence_summary or top.description or top.title or "").strip()
    risk_count = sum(1 for s in ordered if s.direction == "risk")
    opportunity_count = sum(1 for s in ordered if s.direction == "opportunity")
    counts = []
    if risk_count:
        counts.append(f"{risk_count} risk")
    if opportunity_count:
        counts.append(f"{opportunity_count} opportunity")
    balance = f"{' and '.join(counts)} signal(s) observed." if counts else f"{len(ordered)} signal(s) observed."
    return f"{lead} {balance}".strip()


def domain_recommendation(signals: Iterable[Signal]) -> str:
    """The most actionable recommendation for a domain (highest priority)."""
    for s in highest_priority_signals(signals, limit=None):
        if s.recommended_action:
            return s.recommended_action
    return ""


def build_domain_overviews(signals: Iterable[Signal]) -> dict[str, dict]:
    """Group signals into the nine display domains.

    Each domain entry carries ``score`` (0–100), ``summary``, and
    ``recommendation`` so the Signals dashboard can render every domain with
    the same shape.
    """
    grouped: dict[SignalCategory, list[Signal]] = {domain: [] for domain in DISPLAY_DOMAINS}
    for s in signals:
        domain = display_domain(s.category)
        if domain is not None:
            grouped[domain].append(s)

    overviews: dict[str, dict] = {}
    for domain in DISPLAY_DOMAINS:
        items = grouped[domain]
        overviews[domain.value] = {
            "domain": domain.value,
            "label": DOMAIN_LABELS[domain],
            "score": score_signals(items),
            "summary": domain_summary(items),
            "recommendation": domain_recommendation(items),
            "signal_count": len(items),
            "risk_count": sum(1 for s in items if s.direction == "risk"),
            "opportunity_count": sum(1 for s in items if s.direction == "opportunity"),
        }
    return overviews
