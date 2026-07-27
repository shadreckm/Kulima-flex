"""VC Thesis Engine — fund-specific thesis matching with Evidence Fit.

Pure domain engine that evaluates deal alignment against VC fund thesis parameters
(sectors, stages, geographies, check size, exclusions, and evidence quality).

Public API:
  evaluate_thesis_match() — pure evaluation function returning ThesisMatchResult

INVARIANTS:
  - Additive & informational ONLY.
  - Does NOT modify recommendation, overall_score, founder_score, startup_score,
    market_score, or trust_score.
"""

from __future__ import annotations

from typing import Any

from kulima.models import (
    ConsistencyStatus,
    EvidenceDepth,
    EvidenceIntegrityReport,
    FundProfile,
    InvestmentBrief,
    ThesisMatchResult,
    ThesisStatus,
)


def _safe_str(val: Any) -> str:
    return str(val).strip() if val is not None else ""


def _contains_any(target: str, items: list[str]) -> str | None:
    """Return the matched item if target contains any string in items (case-insensitive)."""
    t_lower = target.lower()
    for item in items:
        if item.lower() in t_lower or t_lower in item.lower():
            return item
    return None


def evaluate_thesis_match(
    brief_or_deal: InvestmentBrief | dict[str, Any],
    fund: FundProfile | None = None,
) -> ThesisMatchResult:
    """Evaluate deal alignment against fund thesis parameters including Evidence Fit.

    Parameters
    ----------
    brief_or_deal: An InvestmentBrief instance or a stored deal dict.
    fund: FundProfile instance (defaults to standard FundProfile if None).

    Returns
    -------
    ThesisMatchResult with overall_match %, component fits, notes, and status.
    """
    if fund is None:
        fund = FundProfile()

    notes: list[str] = []

    # Extract attributes from brief object or dict
    if isinstance(brief_or_deal, InvestmentBrief):
        sector = _safe_str(brief_or_deal.sector)
        stage = _safe_str(brief_or_deal.stage)
        geography = _safe_str(brief_or_deal.geography)
        evidence_report = brief_or_deal.evidence_integrity
    else:
        sector = _safe_str(brief_or_deal.get("sector"))
        stage = _safe_str(brief_or_deal.get("stage"))
        geography = _safe_str(brief_or_deal.get("geography"))
        evidence_report = brief_or_deal.get("evidence_integrity")

    # ── 1. Sector Fit & Exclusion Check ───────────────────────────────────────
    exclusion_hit = _contains_any(sector, fund.exclusions) if sector else None
    if exclusion_hit:
        notes.append(
            f"🚫 Sector '{sector}' matches excluded sector list ({exclusion_hit}). Deal blocked by fund thesis."
        )
        return ThesisMatchResult(
            overall_match=0.0,
            sector_fit="Excluded",
            stage_fit="Low",
            geography_fit="Low",
            evidence_fit="Low",
            notes=notes,
            status=ThesisStatus.BLOCK,
        )

    preferred_sector_match = _contains_any(sector, fund.preferred_sectors) if sector else None
    if preferred_sector_match:
        s_sec = 100.0
        sector_fit = "High"
        notes.append(f"✅ Sector '{sector}' aligns with preferred fund focus ({preferred_sector_match}).")
    elif not sector or sector.lower() in {"general", "tech", "general / tech"}:
        s_sec = 65.0
        sector_fit = "Medium"
        notes.append("ℹ️ General technology sector — neutral thesis fit.")
    else:
        s_sec = 30.0
        sector_fit = "Low"
        notes.append(f"⚠️ Sector '{sector}' is outside preferred fund sectors ({', '.join(fund.preferred_sectors[:4])}).")

    # ── 2. Stage Fit ──────────────────────────────────────────────────────────
    preferred_stage_match = _contains_any(stage, fund.preferred_stages) if stage else None
    if preferred_stage_match:
        s_stage = 100.0
        stage_fit = "High"
        notes.append(f"✅ Stage '{stage}' matches target investment stage.")
    elif not stage:
        s_stage = 70.0
        stage_fit = "Medium"
        notes.append("ℹ️ Unspecified stage — defaulting to neutral stage fit.")
    else:
        s_stage = 40.0
        stage_fit = "Low"
        notes.append(f"⚠️ Stage '{stage}' is outside target stages ({', '.join(fund.preferred_stages[:3])}).")

    # ── 3. Geography Fit ──────────────────────────────────────────────────────
    preferred_geo_match = _contains_any(geography, fund.preferred_geographies) if geography else None
    if preferred_geo_match or "pan-africa" in geography.lower():
        s_geo = 100.0
        geography_fit = "High"
        notes.append(f"✅ Geography '{geography}' aligns with target fund geographies.")
    elif not geography:
        s_geo = 70.0
        geography_fit = "Medium"
        notes.append("ℹ️ Unspecified geography — defaulting to neutral geography fit.")
    else:
        s_geo = 40.0
        geography_fit = "Low"
        notes.append(f"⚠️ Geography '{geography}' is outside core target markets.")

    # ── 4. Evidence Fit (derived from Evidence Integrity Engine) ──────────────
    if isinstance(evidence_report, EvidenceIntegrityReport):
        base_r = float(evidence_report.integrity_score)
        depth = evidence_report.evidence_depth
        status_enum = evidence_report.consistency_status

        # Depth multiplier
        if depth in (EvidenceDepth.COMPREHENSIVE, EvidenceDepth.RICH):
            depth_mult = 1.0
        elif depth == EvidenceDepth.MODERATE:
            depth_mult = 0.95
        elif depth == EvidenceDepth.LIMITED:
            depth_mult = 0.85
        else:  # THIN
            depth_mult = 0.70

        # Consistency adjustment
        if status_enum == ConsistencyStatus.CLEAN:
            c_adj = 5.0
        elif status_enum == ConsistencyStatus.MINOR_DIFFERENCES:
            c_adj = 0.0
        elif status_enum == ConsistencyStatus.CONFLICTS:
            c_adj = -10.0
        else:  # MAJOR_CONFLICTS
            c_adj = -25.0

        s_ev = min(max(base_r * depth_mult + c_adj, 0.0), 100.0)

        if s_ev >= 80.0:
            evidence_fit = "High"
            notes.append(
                f"✅ Strong Evidence Fit ({s_ev:.0f}%) — Integrity Grade {evidence_report.integrity_grade.value}, {depth.value.title()} depth."
            )
        elif s_ev >= 60.0:
            evidence_fit = "Medium"
            notes.append(
                f"ℹ️ Moderate Evidence Fit ({s_ev:.0f}%) — Integrity Grade {evidence_report.integrity_grade.value}."
            )
        else:
            evidence_fit = "Low"
            notes.append(
                f"⚠️ Low Evidence Fit ({s_ev:.0f}%) — Integrity Grade {evidence_report.integrity_grade.value}, {depth.value.title()} depth."
            )
    elif isinstance(evidence_report, dict):
        rel_score = float(evidence_report.get("integrity_score", 70.0))
        grade = str(evidence_report.get("integrity_grade", "B"))
        s_ev = min(max(rel_score, 0.0), 100.0)
        evidence_fit = "High" if s_ev >= 80.0 else ("Medium" if s_ev >= 60.0 else "Low")
        notes.append(f"ℹ️ Evidence Fit: {evidence_fit} ({s_ev:.0f}%) based on stored reliability score.")
    else:
        # Pre-EIE or no report run
        s_ev = 70.0
        evidence_fit = "Medium"
        notes.append("ℹ️ No Evidence Integrity report present — assuming default moderate evidence fit.")

    # ── 5. Overall Match Calculation & Status ─────────────────────────────────
    overall = 0.35 * s_sec + 0.25 * s_stage + 0.20 * s_geo + 0.20 * s_ev
    overall = min(max(overall, 0.0), 100.0)

    final_status = ThesisStatus.PASS if overall >= 75.0 else ThesisStatus.WARN

    return ThesisMatchResult(
        overall_match=round(overall, 1),
        sector_fit=sector_fit,
        stage_fit=stage_fit,
        geography_fit=geography_fit,
        evidence_fit=evidence_fit,
        notes=notes,
        status=final_status,
    )
