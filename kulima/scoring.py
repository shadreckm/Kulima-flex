"""Scoring, confidence, and explainability utilities."""

from __future__ import annotations

from typing import Any

from kulima.models import (
    AgentResult,
    ConfidenceLevel,
    Recommendation,
    ScoreDimension,
)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any value to float, returning default if parsing fails."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    try:
        return float(s)
    except ValueError:
        pass
    import re
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            pass
    return default


def parse_qualitative_score(val: Any, is_risk: bool = False, default: float = 50.0) -> float:
    """
    Parses a score which can be a number, string representation of a number,
    or a qualitative term (e.g. High, Medium, Low, Critical).
    `is_risk` indicates if a higher score is worse (for risk assessment).
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
        
    s = str(val).strip().lower()
    
    # Check qualitative terms first
    # Risk-specific mapping: Higher risk score = worse (closer to 100)
    risk_mapping = {
        "low": 20.0,
        "medium": 50.0,
        "high": 75.0,
        "very high": 90.0,
        "critical": 95.0,
    }
    
    # General-specific mapping: Higher score = better (closer to 100)
    general_mapping = {
        "low": 20.0,
        "medium": 50.0,
        "high": 80.0,
        "very high": 95.0,
        "critical": 20.0, 
    }
    
    mapping = risk_mapping if is_risk else general_mapping
    
    if s in mapping:
        return mapping[s]
        
    # Try to parse as direct float
    try:
        return float(s)
    except ValueError:
        pass
        
    # Try extracting first numeric match (e.g. "85%" -> 85.0, "risk: 45" -> 45.0)
    import re
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            pass
            
    # Substring matching as fallback
    for key, value in mapping.items():
        if key in s:
            return value
            
    return default



def mean(values: list[float], default: float = 0.0) -> float:
    return sum(values) / len(values) if values else default


def confidence_level(score: float) -> ConfidenceLevel:
    if score >= 0.85:
        return ConfidenceLevel.VERY_HIGH
    if score >= 0.7:
        return ConfidenceLevel.HIGH
    if score >= 0.45:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def evidence_boost(n_sources: int, base: float, per_source: float = 4.0, cap: float = 100.0) -> float:
    return clamp(base + n_sources * per_source, 0, cap)


def aggregate_agent_score(result: AgentResult, default: float = 50.0) -> float:
    if not result.scores:
        return default
    weighted = []
    for dim in result.scores:
        weighted.append(dim.score * max(dim.confidence, 0.2))
    total_w = sum(max(d.confidence, 0.2) for d in result.scores)
    return clamp(sum(weighted) / total_w if total_w else default)


def recommendation_from_score(score: float, risk_score: float, red_flag_count: int) -> Recommendation:
    if red_flag_count >= 3 or risk_score >= 75:
        return Recommendation.PASS
    if score >= 78 and risk_score < 45:
        return Recommendation.INVEST
    if score >= 68 and risk_score < 55:
        return Recommendation.CO_INVEST
    if score >= 55:
        return Recommendation.OBSERVE
    if score >= 45:
        return Recommendation.FOLLOW_ON_WATCH
    return Recommendation.PASS


def build_explainability(
    founder_score: float,
    startup_score: float,
    market_score: float,
    trust_score: float,
    risk_score: float,
    n_sources: int,
    syndicate_avg: float | None,
) -> list[str]:
    reasons = [
        f"Founder intelligence contributes {founder_score:.0f}/100 to conviction.",
        f"Startup / product-market signals scored {startup_score:.0f}/100.",
        f"Africa-adjusted market opportunity scored {market_score:.0f}/100.",
        f"Trust graph density and digital footprint yield {trust_score:.0f}/100.",
        f"Composite risk pressure sits at {risk_score:.0f}/100 (lower is better).",
        f"Decision grounded in {n_sources} attributed open-source evidence items.",
    ]
    if syndicate_avg is not None:
        reasons.append(
            f"AI Investor Twin Syndicate averaged {syndicate_avg:.0f}/100 across five archetypes."
        )
    return reasons


def score_card_payload(dimensions: list[ScoreDimension]) -> list[dict]:
    return [
        {
            "Dimension": d.name,
            "Score": round(d.score, 1),
            "Confidence": f"{d.confidence:.0%}",
            "Rationale": d.rationale,
        }
        for d in dimensions
    ]
