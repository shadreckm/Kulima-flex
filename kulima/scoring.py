"""Scoring, confidence, and explainability utilities."""

from __future__ import annotations

from typing import Any

from kulima.models import (
    AgentResult,
    ConfidenceLevel,
    EvidenceDepth,
    IntegrityGrade,
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


def normalize_confidence(val: Any, default: float = 0.55) -> float:
    """Normalize a confidence value to the 0.0–1.0 range.

    Heuristics:
    - If value is None -> return default
    - If numeric and <= 1.0 -> assume already 0–1 and return clamped
    - If numeric and > 1.0 -> assume 0–100 scale and divide by 100, then clamp
    - If string like "80%" safe_float will parse 80.0 and the above rule applies
    """
    v = safe_float(val, default)
    # If the model returned a 0–100 percentage scale, convert to 0–1
    if v > 1.0:
        v = v / 100.0
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, v))


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


def recommendation_from_score(
    score: float,
    risk_score: float,
    red_flag_count: int,
    trust_score: float | None = None,
    confidence: float | None = None,
    integrity_grade: IntegrityGrade | str | None = None,
    evidence_depth: EvidenceDepth | str | None = None,
) -> Recommendation:
    """Calibrate a deal recommendation from available decision signals.

    Backwards compatible with the existing three-argument call sites, while
    allowing richer tiering when trust, confidence, and evidence-quality inputs
    are available.
    """

    def _grade_value(value: IntegrityGrade | str | None) -> str:
        return getattr(value, "value", str(value) if value is not None else "").upper()

    def _depth_value(value: EvidenceDepth | str | None) -> str:
        return getattr(value, "value", str(value) if value is not None else "").lower()

    score = clamp(score)
    trust = clamp(trust_score if trust_score is not None else 50.0)
    conf = max(0.0, min(1.0, confidence if confidence is not None else 0.55))
    grade = _grade_value(integrity_grade)
    depth = _depth_value(evidence_depth)

    # Hard block only truly severe cases. The earlier >=3 red-flag rule was
    # collapsing nearly the entire historical corpus into Pass.
    if risk_score >= 75 or red_flag_count >= 12:
        return Recommendation.PASS
    if score < 15 or trust < 18:
        return Recommendation.PASS
    if red_flag_count >= 10 and risk_score >= 65:
        return Recommendation.PASS

    low_depth = depth in {EvidenceDepth.THIN.value, EvidenceDepth.LIMITED.value}
    weak_grade = grade in {IntegrityGrade.D.value, IntegrityGrade.F.value}

    if (
        score >= 35
        and risk_score < 60
        and trust >= 60
        and conf >= 0.85
        and grade == IntegrityGrade.A.value
        and depth in {EvidenceDepth.RICH.value, EvidenceDepth.COMPREHENSIVE.value}
    ):
        return Recommendation.CO_INVEST

    if (
        score >= 25
        and risk_score < 65
        and trust >= 45
        and conf >= 0.55
        and not weak_grade
        and not low_depth
    ):
        return Recommendation.INVEST

    if (
        score >= 18
        and risk_score < 70
        and trust >= 20
        and conf >= 0.35
    ):
        return Recommendation.OBSERVE

    if score >= 15 and risk_score < 70:
        return Recommendation.OBSERVE

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
