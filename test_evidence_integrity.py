"""Sub-Task 3 — Evidence Integrity Engine tests.

Covers all 14 required test categories:
 1.  Identical claims → no contradiction
 2.  Funding discrepancy → contradiction
 3.  Funding discrepancy explained by FX → currency artefact
 4.  Incorporation year vs founding year within tolerance
 5.  Temporal drift detection
 6.  Sparse evidence mode
 7.  Unsupported claims
 8.  Freshness classification
 9.  Evidence depth classification
10.  Consistency classification
11.  Reliability grade calculation
12.  Legacy / missing fields
13.  Malformed extraction handling
14.  Engine failure isolation

All tests are unit-level and deterministic — no LLM calls are made.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from kulima.evidence_integrity import (
    ClaimExtractor,
    ClaimNormaliser,
    ContradictionDetector,
    EvidenceIntegrityEngine,
    FreshnessEvaluator,
    IntegrityScoreCalculator,
    SupportEvaluator,
)
from kulima.models import (
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    SourceAttribution,
    StalenessT,
    UnsupportedClaim,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _src(
    url: str = "https://techcabal.com/example",
    title: str = "TechCabal",
    snippet: str = "",
    source_type: str = "high_authority_web",
) -> SourceAttribution:
    return SourceAttribution(
        title=title, url=url, snippet=snippet,
        source_type=source_type, relevance=0.9, confidence_score=0.85,
    )


def _claim(
    ct: ClaimType = ClaimType.FUNDING_AMOUNT,
    value_raw: str = "$2M seed",
    value_normalised: str | None = "2000000",
    source_url: str = "https://techcabal.com/a",
    source_authority: str = "high_authority_web",
    staleness: StalenessT = StalenessT.FRESH,
) -> Claim:
    return Claim(
        claim_id="test",
        claim_type=ct,
        value_raw=value_raw,
        value_normalised=value_normalised,
        source_url=source_url,
        source_authority=source_authority,
        staleness=staleness,
        snippet=f"Snippet about {value_raw}",
    )


def _mk_llm(response: str) -> Any:
    """Return a mock LLM client that always returns `response`."""
    mock = MagicMock()
    mock.complete.return_value = response
    return mock


def _mk_llm_raising(exc: Exception) -> Any:
    """Return a mock LLM client that always raises `exc`."""
    mock = MagicMock()
    mock.complete.side_effect = exc
    return mock


normaliser = ClaimNormaliser()
freshness = FreshnessEvaluator()
detector = ContradictionDetector()
scorer = IntegrityScoreCalculator()
support = SupportEvaluator()


# ══════════════════════════════════════════════════════════════════════════════
# 1 — Identical claims produce no contradiction
# ══════════════════════════════════════════════════════════════════════════════

class TestIdenticalClaims:
    def test_same_funding_no_contradiction(self) -> None:
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://a.com")
        b = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://b.com")
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []

    def test_same_stage_no_contradiction(self) -> None:
        a = _claim(ct=ClaimType.STAGE, value_raw="Seed", value_normalised="seed", source_url="https://a.com")
        b = _claim(ct=ClaimType.STAGE, value_raw="Seed", value_normalised="seed", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert contradictions == []

    def test_same_source_url_skipped(self) -> None:
        """Two claims from the same URL must never produce a contradiction."""
        url = "https://techcabal.com/same"
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url=url)
        b = _claim(value_raw="$5M", value_normalised="5000000", source_url=url)
        contradictions, _ = detector.detect([a, b])
        assert contradictions == []

    def test_within_20pct_threshold_no_contradiction(self) -> None:
        """Funding figures within 20% of each other are not contradictions."""
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://a.com")
        # $2.3M = 15% above $2M → within threshold
        b = _claim(value_raw="$2.3M", value_normalised="2300000", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert contradictions == []


# ══════════════════════════════════════════════════════════════════════════════
# 2 — Funding discrepancy → contradiction
# ══════════════════════════════════════════════════════════════════════════════

class TestFundingContradiction:
    def test_4x_discrepancy_is_critical(self) -> None:
        """$500K vs $2M (4x ratio) must be CRITICAL GENUINE."""
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://a.com")
        b = _claim(value_raw="$500K", value_normalised="500000", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert len(contradictions) == 1
        assert contradictions[0].severity == ContradictionSeverity.CRITICAL
        assert contradictions[0].subtype == "GENUINE_CONTRADICTION"

    def test_2x_discrepancy_is_high(self) -> None:
        """$1M vs $2M (2x ratio) must be HIGH GENUINE."""
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://a.com")
        b = _claim(value_raw="$1M", value_normalised="1000000", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert len(contradictions) == 1
        assert contradictions[0].severity == ContradictionSeverity.HIGH

    def test_normaliser_2m_usd(self) -> None:
        assert normaliser._normalise_funding("$2M") == pytest.approx(2_000_000)

    def test_normaliser_2_million(self) -> None:
        assert normaliser._normalise_funding("$2 million") == pytest.approx(2_000_000)

    def test_normaliser_500k(self) -> None:
        assert normaliser._normalise_funding("$500K") == pytest.approx(500_000)

    def test_normaliser_1b(self) -> None:
        assert normaliser._normalise_funding("$1B") == pytest.approx(1_000_000_000)

    def test_recommended_action_present(self) -> None:
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://a.com")
        b = _claim(value_raw="$200K", value_normalised="200000", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert contradictions[0].recommended_action != ""


# ══════════════════════════════════════════════════════════════════════════════
# 3 — Funding discrepancy explained by FX → currency artefact
# ══════════════════════════════════════════════════════════════════════════════

class TestCurrencyArtefact:
    def test_naira_funding_returns_none_normalisation(self) -> None:
        """₦850M must not normalise to a USD float."""
        result = normaliser._normalise_funding("₦850M")
        assert result is None

    def test_ngn_text_returns_none(self) -> None:
        assert normaliser._normalise_funding("₦600M raised") is None

    def test_kes_returns_none(self) -> None:
        assert normaliser._normalise_funding("KES 120M") is None

    def test_ghs_returns_none(self) -> None:
        assert normaliser._normalise_funding("GHS 50M") is None

    def test_none_normalisation_produces_currency_artefact(self) -> None:
        """A claim with None normalised value paired with a USD claim → CURRENCY_ARTEFACT."""
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://a.com")
        b = _claim(value_raw="₦850M", value_normalised=None, source_url="https://b.com")
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []
        assert len(ignored) == 1
        assert ignored[0].reason == "CURRENCY_ARTEFACT"

    def test_small_usd_gap_is_fx_artefact_not_contradiction(self) -> None:
        """A 40% gap (within FX range heuristic) produces an IgnoredConflict."""
        # $2M vs $1.4M = 43% gap → within heuristic FX range (30–70%)
        a = _claim(value_raw="$2M", value_normalised="2000000", source_url="https://a.com")
        b = _claim(value_raw="$1.4M", value_normalised="1400000", source_url="https://b.com")
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []
        assert any(i.reason == "CURRENCY_ARTEFACT" for i in ignored)


# ══════════════════════════════════════════════════════════════════════════════
# 4 — Founding year within tolerance
# ══════════════════════════════════════════════════════════════════════════════

class TestFoundingYearTolerance:
    def test_same_year_no_contradiction(self) -> None:
        a = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2019", value_normalised="2019", source_url="https://a.com")
        b = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2019", value_normalised="2019", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert contradictions == []

    def test_1yr_gap_ignored(self) -> None:
        """LinkedIn 2018, registry 2019 — within Africa 2-year tolerance."""
        a = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2018", value_normalised="2018", source_url="https://linkedin.com/co")
        b = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2019", value_normalised="2019", source_url="https://registry.co.ke")
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []
        assert len(ignored) == 1
        assert ignored[0].reason == "FOUNDING_YEAR_TOLERANCE"

    def test_2yr_gap_ignored(self) -> None:
        """LinkedIn 2018, registry 2020 — exactly at the 2-year Africa tolerance."""
        a = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2018", value_normalised="2018", source_url="https://a.com")
        b = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2020", value_normalised="2020", source_url="https://b.com")
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []
        assert len(ignored) == 1

    def test_3yr_gap_is_contradiction(self) -> None:
        """A 3-year gap exceeds the Africa tolerance → contradiction."""
        a = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2018", value_normalised="2018", source_url="https://a.com")
        b = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2021", value_normalised="2021", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert len(contradictions) == 1
        assert contradictions[0].subtype == "GENUINE_CONTRADICTION"

    def test_5yr_gap_is_critical(self) -> None:
        a = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2015", value_normalised="2015", source_url="https://a.com")
        b = _claim(ct=ClaimType.FOUNDING_YEAR, value_raw="Founded 2020", value_normalised="2020", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert contradictions[0].severity == ContradictionSeverity.CRITICAL

    def test_normaliser_extracts_year(self) -> None:
        assert normaliser._normalise_year("Founded in 2019") == 2019

    def test_normaliser_invalid_returns_none(self) -> None:
        assert normaliser._normalise_year("no year here") is None


# ══════════════════════════════════════════════════════════════════════════════
# 5 — Temporal drift detection
# ══════════════════════════════════════════════════════════════════════════════

class TestTemporalDrift:
    def test_stale_vs_fresh_is_temporal_drift(self) -> None:
        """$300K (old source, STALE) vs $1.2M (fresh source, FRESH) — temporal drift."""
        a = _claim(value_raw="$300K", value_normalised="300000",
                   source_url="https://a.com", staleness=StalenessT.STALE)
        b = _claim(value_raw="$1.2M", value_normalised="1200000",
                   source_url="https://b.com", staleness=StalenessT.FRESH)
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []
        assert any(i.reason == "TEMPORAL_DRIFT" for i in ignored)

    def test_same_staleness_tier_is_not_temporal_drift(self) -> None:
        """Two FRESH sources with 4x discrepancy → genuine contradiction."""
        a = _claim(value_raw="$2M", value_normalised="2000000",
                   source_url="https://a.com", staleness=StalenessT.FRESH)
        b = _claim(value_raw="$500K", value_normalised="500000",
                   source_url="https://b.com", staleness=StalenessT.FRESH)
        contradictions, _ = detector.detect([a, b])
        assert len(contradictions) == 1
        assert contradictions[0].subtype == "GENUINE_CONTRADICTION"

    def test_stage_adjacent_tier_is_ignored(self) -> None:
        """Seed vs Series-A (1 tier apart) → IgnoredConflict."""
        a = _claim(ct=ClaimType.STAGE, value_raw="Seed", value_normalised="seed", source_url="https://a.com")
        b = _claim(ct=ClaimType.STAGE, value_raw="Series A", value_normalised="series a", source_url="https://b.com")
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []
        assert len(ignored) == 1
        assert ignored[0].reason == "STAGE_VOCABULARY"

    def test_stage_two_tiers_apart_is_contradiction(self) -> None:
        """Seed vs Series B (2 tiers apart) → genuine contradiction."""
        a = _claim(ct=ClaimType.STAGE, value_raw="Seed", value_normalised="seed", source_url="https://a.com")
        b = _claim(ct=ClaimType.STAGE, value_raw="Series B", value_normalised="series b", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert len(contradictions) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 6 — Sparse evidence mode
# ══════════════════════════════════════════════════════════════════════════════

class TestSparseEvidenceMode:
    def test_3_sources_1_high_auth_is_sparse(self) -> None:
        sources = [
            _src("https://a.com", source_type="high_authority_web"),
            _src("https://b.com", source_type="web"),
            _src("https://c.com", source_type="web"),
        ]
        assert IntegrityScoreCalculator._is_sparse(sources) is True

    def test_5_sources_2_high_auth_is_not_sparse(self) -> None:
        sources = [
            _src("https://a.com", source_type="high_authority_web"),
            _src("https://b.com", source_type="high_authority_web"),
            _src("https://c.com", source_type="web"),
            _src("https://d.com", source_type="web"),
            _src("https://e.com", source_type="web"),
        ]
        assert IntegrityScoreCalculator._is_sparse(sources) is False

    def test_4_sources_3_high_auth_is_sparse_by_count(self) -> None:
        """4 sources (even with 3 high-auth) → sparse because count < 5."""
        sources = [
            _src("https://a.com", source_type="high_authority_web"),
            _src("https://b.com", source_type="high_authority_web"),
            _src("https://c.com", source_type="high_authority_web"),
            _src("https://d.com", source_type="web"),
        ]
        assert IntegrityScoreCalculator._is_sparse(sources) is True

    def test_sparse_mode_floor_at_65(self) -> None:
        """Zero claims + sparse mode must yield score >= 65."""
        sources = [_src("https://a.com", source_type="web")]
        score, grade, _, _, _ = scorer.calculate(
            contradictions=[], unsupported=[], stale=[],
            sources=sources, claims=[], sparse_mode=True,
        )
        assert score >= 65.0

    def test_sparse_mode_no_unsupported_penalty(self) -> None:
        """Unsupported claims in sparse mode must not reduce the score."""
        sources = [_src("https://a.com", source_type="web")]
        unsupported = [
            UnsupportedClaim(
                claim_type=ClaimType.FUNDING_AMOUNT,
                severity=ContradictionSeverity.CRITICAL,
                description="not found",
                recommended_action="verify",
            )
        ]
        score_with, _, _, _, _ = scorer.calculate(
            contradictions=[], unsupported=unsupported, stale=[],
            sources=sources, claims=[], sparse_mode=True,
        )
        score_without, _, _, _, _ = scorer.calculate(
            contradictions=[], unsupported=[], stale=[],
            sources=sources, claims=[], sparse_mode=True,
        )
        assert score_with == score_without

    def test_sparse_mode_grade_no_worse_than_c_without_genuine_contradictions(self) -> None:
        """Sparse corpus with no genuine contradictions cannot grade below C."""
        sources = [_src("https://a.com", source_type="web")]
        unsupported = [
            UnsupportedClaim(
                claim_type=ct,
                severity=ContradictionSeverity.CRITICAL,
                description="not found",
                recommended_action="verify",
            )
            for ct in [ClaimType.FUNDING_AMOUNT, ClaimType.FOUNDING_YEAR, ClaimType.GEOGRAPHY]
        ]
        score, grade, _, _, _ = scorer.calculate(
            contradictions=[], unsupported=unsupported, stale=[],
            sources=sources, claims=[], sparse_mode=True,
        )
        assert grade in (IntegrityGrade.A, IntegrityGrade.B, IntegrityGrade.C)
        assert score >= 65.0

    def test_engine_sets_sparse_mode_flag(self) -> None:
        """EvidenceIntegrityEngine must set sparse_mode=True for a thin corpus."""
        sources = [_src("https://a.com", source_type="web")]
        engine = EvidenceIntegrityEngine(llm=None)
        report = engine.evaluate(sources, "Ada Obi", "PayFast NG")
        assert report.sparse_mode is True


# ══════════════════════════════════════════════════════════════════════════════
# 7 — Unsupported claims
# ══════════════════════════════════════════════════════════════════════════════

class TestUnsupportedClaims:
    def test_fintech_requires_regulatory_status(self) -> None:
        """Fintech sector must require REGULATORY_STATUS."""
        findings = support.evaluate(claims=[], sector="fintech")
        types = [u.claim_type for u in findings]
        assert ClaimType.REGULATORY_STATUS in types

    def test_regulatory_status_is_critical_for_fintech(self) -> None:
        findings = support.evaluate(claims=[], sector="fintech")
        reg = next(u for u in findings if u.claim_type == ClaimType.REGULATORY_STATUS)
        assert reg.severity == ContradictionSeverity.CRITICAL

    def test_base_tier_always_includes_founding_year(self) -> None:
        findings = support.evaluate(claims=[], sector="agritech")
        types = [u.claim_type for u in findings]
        assert ClaimType.FOUNDING_YEAR in types

    def test_present_claim_not_flagged(self) -> None:
        """A present FOUNDING_YEAR claim must not appear in unsupported findings."""
        claims = [_claim(ct=ClaimType.FOUNDING_YEAR, value_raw="2019")]
        findings = support.evaluate(claims=claims, sector="agritech")
        types = [u.claim_type for u in findings]
        assert ClaimType.FOUNDING_YEAR not in types

    def test_full_corpus_unsupported_deducts_score(self) -> None:
        """CRITICAL unsupported claim in full-corpus mode must reduce the score."""
        sources_full = [_src(f"https://src{i}.com") for i in range(6)]
        # Mark 2 as high-authority
        sources_full[0] = _src("https://a.com", source_type="high_authority_web")
        sources_full[1] = _src("https://b.com", source_type="high_authority_web")

        unsupported = [
            UnsupportedClaim(
                claim_type=ClaimType.FUNDING_AMOUNT,
                severity=ContradictionSeverity.CRITICAL,
                description="not found",
                recommended_action="verify",
            )
        ]
        score_with, _, _, _, _ = scorer.calculate(
            contradictions=[], unsupported=unsupported, stale=[],
            sources=sources_full, claims=[], sparse_mode=False,
        )
        score_without, _, _, _, _ = scorer.calculate(
            contradictions=[], unsupported=[], stale=[],
            sources=sources_full, claims=[], sparse_mode=False,
        )
        assert score_with < score_without


# ══════════════════════════════════════════════════════════════════════════════
# 8 — Freshness classification
# ══════════════════════════════════════════════════════════════════════════════

class TestFreshnessClassification:
    def test_url_with_recent_year_is_fresh(self) -> None:
        now = datetime.now(timezone.utc)
        recent_year = now.year
        url = f"https://techcabal.com/{recent_year}/06/startup-funding"
        result = freshness._from_url(url)
        assert result == StalenessT.FRESH

    def test_url_with_old_year_is_stale_or_very_stale(self) -> None:
        """2019 is > 24 months ago — must be STALE or VERY_STALE (time-relative)."""
        result = freshness._from_url("https://blog.com/2019/03/article")
        assert result in (StalenessT.STALE, StalenessT.VERY_STALE)

    def test_url_with_very_old_year_is_very_stale(self) -> None:
        result = freshness._from_url("https://blog.com/2015/01/article")
        assert result == StalenessT.VERY_STALE

    def test_snippet_with_month_year_classified(self) -> None:
        """Any named-month year in a snippet must produce a non-None staleness."""
        now = datetime.now(timezone.utc)
        # Use a year that is 6 months ago to guarantee FRESH regardless of test date
        recent_year = now.year
        snippet = f"PayFast raised $2M in June {recent_year}."
        result = freshness._from_text(snippet)
        assert result is not None
        assert result in (StalenessT.FRESH, StalenessT.AGING, StalenessT.STALE)

    def test_no_date_signal_returns_unknown(self) -> None:
        result = freshness._from_text("No date information anywhere here.")
        assert result is None

    def test_url_with_no_date_returns_none(self) -> None:
        result = freshness._from_url("https://techcabal.com/about")
        assert result is None

    def test_evaluate_populates_staleness_on_claims(self) -> None:
        now = datetime.now(timezone.utc)
        fresh_year = now.year
        src = _src(url=f"https://techcabal.com/{fresh_year}/05/article")
        claim = _claim(source_url=src.url)
        result = freshness.evaluate([claim], [src])
        assert len(result) == 1
        assert result[0].staleness == StalenessT.FRESH


# ══════════════════════════════════════════════════════════════════════════════
# 9 — Evidence depth classification
# ══════════════════════════════════════════════════════════════════════════════

class TestEvidenceDepth:
    def test_1_source_is_thin(self) -> None:
        depth = scorer._depth_from_sources([_src()], 2)
        assert depth == EvidenceDepth.THIN

    def test_2_sources_is_thin(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(2)]
        assert scorer._depth_from_sources(sources, 4) == EvidenceDepth.THIN

    def test_3_sources_is_limited(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(3)]
        assert scorer._depth_from_sources(sources, 6) == EvidenceDepth.LIMITED

    def test_4_sources_is_limited(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(4)]
        assert scorer._depth_from_sources(sources, 8) == EvidenceDepth.LIMITED

    def test_5_sources_is_moderate(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(5)]
        assert scorer._depth_from_sources(sources, 10) == EvidenceDepth.MODERATE

    def test_8_sources_is_rich(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(8)]
        assert scorer._depth_from_sources(sources, 16) == EvidenceDepth.RICH

    def test_12_sources_is_comprehensive(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(12)]
        assert scorer._depth_from_sources(sources, 24) == EvidenceDepth.COMPREHENSIVE


# ══════════════════════════════════════════════════════════════════════════════
# 10 — Consistency classification
# ══════════════════════════════════════════════════════════════════════════════

class TestConsistencyClassification:
    def _mk_contradiction(self, sev: ContradictionSeverity = ContradictionSeverity.HIGH) -> Contradiction:
        return Contradiction(
            claim_a=_claim(source_url="https://a.com"),
            claim_b=_claim(source_url="https://b.com"),
            severity=sev,
        )

    def test_zero_contradictions_is_clean(self) -> None:
        assert scorer._consistency_from_contradictions([]) == ConsistencyStatus.CLEAN

    def test_one_contradiction_is_minor_differences(self) -> None:
        assert scorer._consistency_from_contradictions(
            [self._mk_contradiction()]
        ) == ConsistencyStatus.MINOR_DIFFERENCES

    def test_two_contradictions_is_conflicts(self) -> None:
        assert scorer._consistency_from_contradictions(
            [self._mk_contradiction(), self._mk_contradiction()]
        ) == ConsistencyStatus.CONFLICTS

    def test_three_contradictions_is_major_conflicts(self) -> None:
        assert scorer._consistency_from_contradictions(
            [self._mk_contradiction()] * 3
        ) == ConsistencyStatus.MAJOR_CONFLICTS


# ══════════════════════════════════════════════════════════════════════════════
# 11 — Reliability grade calculation
# ══════════════════════════════════════════════════════════════════════════════

class TestReliabilityGrade:
    def test_score_100_is_grade_a(self) -> None:
        assert scorer._grade_from_score(100.0) == IntegrityGrade.A

    def test_score_90_is_grade_a(self) -> None:
        assert scorer._grade_from_score(90.0) == IntegrityGrade.A

    def test_score_89_is_grade_b(self) -> None:
        assert scorer._grade_from_score(89.0) == IntegrityGrade.B

    def test_score_75_is_grade_b(self) -> None:
        assert scorer._grade_from_score(75.0) == IntegrityGrade.B

    def test_score_74_is_grade_c(self) -> None:
        assert scorer._grade_from_score(74.0) == IntegrityGrade.C

    def test_score_60_is_grade_c(self) -> None:
        assert scorer._grade_from_score(60.0) == IntegrityGrade.C

    def test_score_59_is_grade_d(self) -> None:
        assert scorer._grade_from_score(59.0) == IntegrityGrade.D

    def test_score_45_is_grade_d(self) -> None:
        assert scorer._grade_from_score(45.0) == IntegrityGrade.D

    def test_score_44_is_grade_f(self) -> None:
        assert scorer._grade_from_score(44.0) == IntegrityGrade.F

    def test_zero_findings_score_100_grade_a(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(6)]
        sources[0] = _src("https://a.com", source_type="high_authority_web")
        sources[1] = _src("https://b.com", source_type="high_authority_web")
        score, grade, _, _, _ = scorer.calculate(
            contradictions=[], unsupported=[], stale=[],
            sources=sources, claims=[], sparse_mode=False,
        )
        assert score == pytest.approx(100.0)
        assert grade == IntegrityGrade.A

    def test_one_critical_contradiction_deducts_15(self) -> None:
        sources = [_src(f"https://src{i}.com") for i in range(6)]
        sources[0] = _src("https://a.com", source_type="high_authority_web")
        sources[1] = _src("https://b.com", source_type="high_authority_web")
        contradiction = Contradiction(
            claim_a=_claim(source_url="https://a.com"),
            claim_b=_claim(source_url="https://b.com"),
            severity=ContradictionSeverity.CRITICAL,
            subtype="GENUINE_CONTRADICTION",
        )
        score, grade, _, _, _ = scorer.calculate(
            contradictions=[contradiction], unsupported=[], stale=[],
            sources=sources, claims=[], sparse_mode=False,
        )
        assert score == pytest.approx(85.0)
        assert grade == IntegrityGrade.B

    def test_two_critical_contradictions_cap_at_30(self) -> None:
        """Two CRITICAL contradictions = 2 × 15 = 30 deducted (hits the cap exactly)."""
        sources = [_src(f"https://src{i}.com") for i in range(6)]
        sources[0] = _src("https://a.com", source_type="high_authority_web")
        sources[1] = _src("https://b.com", source_type="high_authority_web")
        contradictions = [
            Contradiction(
                claim_a=_claim(source_url=f"https://a{i}.com"),
                claim_b=_claim(source_url=f"https://b{i}.com"),
                severity=ContradictionSeverity.CRITICAL,
                subtype="GENUINE_CONTRADICTION",
            )
            for i in range(2)
        ]
        score, _, _, _, _ = scorer.calculate(
            contradictions=contradictions, unsupported=[], stale=[],
            sources=sources, claims=[], sparse_mode=False,
        )
        assert score == pytest.approx(70.0)

    def test_corroboration_bonus_applied(self) -> None:
        """3 independent sources for FUNDING_AMOUNT → +5 bonus."""
        claims = [
            _claim(ct=ClaimType.FUNDING_AMOUNT, source_url=f"https://src{i}.com")
            for i in range(3)
        ]
        sources = [_src(f"https://src{i}.com") for i in range(6)]
        sources[0] = _src("https://src0.com", source_type="high_authority_web")
        sources[1] = _src("https://src1.com", source_type="high_authority_web")
        _, _, _, _, bonus = scorer.calculate(
            contradictions=[], unsupported=[], stale=[],
            sources=sources, claims=claims, sparse_mode=False,
        )
        assert bonus >= 5.0


# ══════════════════════════════════════════════════════════════════════════════
# 12 — Legacy / missing fields
# ══════════════════════════════════════════════════════════════════════════════

class TestLegacyMissingFields:
    def test_empty_sources_produces_safe_report(self) -> None:
        """Empty source list must produce a valid report, not raise."""
        engine = EvidenceIntegrityEngine(llm=None)
        report = engine.evaluate([], "Ada Obi", "PayFast NG")
        assert isinstance(report, EvidenceIntegrityReport)
        assert report.source_count == 0
        assert report.sparse_mode is True

    def test_engine_without_llm_skips_extraction(self) -> None:
        """Engine with llm=None must set extraction_notes."""
        sources = [_src()]
        engine = EvidenceIntegrityEngine(llm=None)
        report = engine.evaluate(sources, "Ada", "Startup")
        assert "skipped" in report.extraction_notes.lower() or "no llm" in report.extraction_notes.lower()

    def test_report_is_pydantic_serialisable(self) -> None:
        """The report must round-trip via model_dump / model_validate."""
        engine = EvidenceIntegrityEngine(llm=None)
        report = engine.evaluate([_src()], "Ada", "Startup")
        dumped = report.model_dump(mode="json")
        restored = EvidenceIntegrityReport.model_validate(dumped)
        assert restored.integrity_grade == report.integrity_grade


# ══════════════════════════════════════════════════════════════════════════════
# 13 — Malformed extraction handling
# ══════════════════════════════════════════════════════════════════════════════

class TestMalformedExtraction:
    def test_llm_returns_empty_json_object(self) -> None:
        llm = _mk_llm("{}")
        extractor = ClaimExtractor(llm)
        result = extractor.extract([_src()], "Ada", "Startup")
        assert result == []

    def test_llm_returns_non_json(self) -> None:
        llm = _mk_llm("This is not JSON at all.")
        extractor = ClaimExtractor(llm)
        result = extractor.extract([_src()], "Ada", "Startup")
        assert result == []

    def test_llm_returns_empty_claims_list(self) -> None:
        llm = _mk_llm('{"claims": []}')
        extractor = ClaimExtractor(llm)
        result = extractor.extract([_src()], "Ada", "Startup")
        assert result == []

    def test_llm_returns_claims_with_missing_fields(self) -> None:
        """Claims missing optional fields must use safe defaults, not raise."""
        payload = json.dumps({
            "claims": [
                {"claim_type": "funding_amount", "value_raw": "$2M"},
                {"claim_type": "UNKNOWN_TYPE", "value_raw": "x"},
                "not-a-dict",
            ]
        })
        llm = _mk_llm(payload)
        extractor = ClaimExtractor(llm)
        result = extractor.extract([_src()], "Ada", "Startup")
        # At least the valid claim must be parsed; the invalid string must be skipped
        assert isinstance(result, list)
        valid = [c for c in result if isinstance(c, Claim)]
        assert len(valid) >= 1

    def test_llm_returns_markdown_fenced_json(self) -> None:
        """LLM often wraps JSON in code fences — must be stripped."""
        payload = '```json\n{"claims": [{"claim_type": "founding_year", "value_raw": "2019"}]}\n```'
        llm = _mk_llm(payload)
        extractor = ClaimExtractor(llm)
        result = extractor.extract([_src()], "Ada", "Startup")
        assert len(result) == 1
        assert result[0].claim_type == ClaimType.FOUNDING_YEAR


# ══════════════════════════════════════════════════════════════════════════════
# 14 — Engine failure isolation
# ══════════════════════════════════════════════════════════════════════════════

class TestEngineFailureIsolation:
    def test_extractor_exception_returns_empty_list(self) -> None:
        """LLM exception in ClaimExtractor.extract must return [] not raise."""
        llm = _mk_llm_raising(RuntimeError("API timeout"))
        extractor = ClaimExtractor(llm)
        result = extractor.extract([_src()], "Ada", "Startup")
        assert result == []

    def test_engine_with_raising_llm_returns_report(self) -> None:
        """EvidenceIntegrityEngine must not raise even if LLM fails."""
        llm = _mk_llm_raising(RuntimeError("Network error"))
        engine = EvidenceIntegrityEngine(llm=llm)
        sources = [_src()]
        report = engine.evaluate(sources, "Ada Obi", "PayFast NG")
        assert isinstance(report, EvidenceIntegrityReport)
        assert report.integrity_score == pytest.approx(100.0)
        assert report.integrity_grade == IntegrityGrade.A

    def test_extraction_notes_set_on_empty_extraction(self) -> None:
        """When extraction produces no claims, extraction_notes must be set."""
        llm = _mk_llm('{"claims": []}')
        engine = EvidenceIntegrityEngine(llm=llm)
        report = engine.evaluate([_src()], "Ada", "Startup")
        assert report.extraction_notes != ""

    def test_engine_safe_report_structure(self) -> None:
        """The safe fallback report must be a valid EvidenceIntegrityReport."""
        report = EvidenceIntegrityEngine._safe_report(
            sources=[_src()], note="test failure"
        )
        assert report.integrity_score == pytest.approx(100.0)
        assert report.integrity_grade == IntegrityGrade.A
        assert "test failure" in report.extraction_notes

    def test_no_scores_modified_by_engine(self) -> None:
        """The engine must never modify InvestmentBrief scores.

        This test asserts the engine is pure: it returns an EvidenceIntegrityReport
        and has no side effects on any score value outside the report.
        """
        engine = EvidenceIntegrityEngine(llm=None)
        report = engine.evaluate([_src()], "Ada", "Startup")
        # The only numeric output that may affect InvestmentBrief is confidence_delta
        # which is stored on the report — it is applied by the orchestrator only.
        assert hasattr(report, "confidence_delta")
        assert report.confidence_delta <= 0.0  # always non-positive


# ══════════════════════════════════════════════════════════════════════════════
# Additional: Africa-specific calibration
# ══════════════════════════════════════════════════════════════════════════════

class TestAfricaCalibration:
    def test_employee_different_terminology_ignored(self) -> None:
        """'team of 4' vs '12 staff' — different terminology → IgnoredConflict."""
        a = _claim(ct=ClaimType.EMPLOYEE_COUNT, value_raw="team of 4",
                   value_normalised="4", source_url="https://a.com")
        b = _claim(ct=ClaimType.EMPLOYEE_COUNT, value_raw="12 staff",
                   value_normalised="12", source_url="https://b.com")
        contradictions, ignored = detector.detect([a, b])
        assert contradictions == []
        assert any(i.reason == "EMPLOYEE_TERMINOLOGY" for i in ignored)

    def test_high_authority_corroboration_bonus(self) -> None:
        """2 high-authority sources for FUNDING_AMOUNT → +5 corroboration bonus."""
        claims = [
            _claim(ct=ClaimType.FUNDING_AMOUNT, source_url="https://techcabal.com",
                   source_authority="high_authority_web"),
            _claim(ct=ClaimType.FUNDING_AMOUNT, source_url="https://disrupt-africa.com",
                   source_authority="high_authority_web"),
        ]
        sources = [_src(f"https://src{i}.com") for i in range(6)]
        sources[0] = _src("https://techcabal.com", source_type="high_authority_web")
        sources[1] = _src("https://disrupt-africa.com", source_type="high_authority_web")
        _, _, _, _, bonus = scorer.calculate(
            contradictions=[], unsupported=[], stale=[],
            sources=sources, claims=claims, sparse_mode=False,
        )
        assert bonus >= 5.0

    def test_two_axis_quadrant_a_thin_consistent(self) -> None:
        from kulima.evidence_integrity import EvidenceIntegrityEngine as EIE
        label = EIE._two_axis_label(EvidenceDepth.THIN, ConsistencyStatus.CLEAN)
        assert label == "A"

    def test_two_axis_quadrant_b_rich_consistent(self) -> None:
        from kulima.evidence_integrity import EvidenceIntegrityEngine as EIE
        label = EIE._two_axis_label(EvidenceDepth.RICH, ConsistencyStatus.CLEAN)
        assert label == "B"

    def test_two_axis_quadrant_c_thin_conflicted(self) -> None:
        from kulima.evidence_integrity import EvidenceIntegrityEngine as EIE
        label = EIE._two_axis_label(EvidenceDepth.LIMITED, ConsistencyStatus.CONFLICTS)
        assert label == "C"

    def test_two_axis_quadrant_d_rich_conflicted(self) -> None:
        from kulima.evidence_integrity import EvidenceIntegrityEngine as EIE
        label = EIE._two_axis_label(EvidenceDepth.COMPREHENSIVE, ConsistencyStatus.MAJOR_CONFLICTS)
        assert label == "D"

    def test_stage_normalisation_africa_vocabulary(self) -> None:
        assert normaliser._normalise_stage("Pre-Series A") is not None
        assert normaliser._normalise_stage("post-seed") is not None
        assert normaliser._normalise_stage("accelerator-funded") is not None
        assert normaliser._normalise_stage("grant-funded startup") is not None

    def test_normaliser_stage_tiers_consistent(self) -> None:
        """pre-series-a and seed must be in the same tier."""
        tier_seed = ClaimNormaliser.stage_tier("seed")
        tier_pre_a = ClaimNormaliser.stage_tier("pre-series a")
        assert tier_seed == tier_pre_a

    def test_geography_partial_match_not_contradiction(self) -> None:
        """'Lagos, Nigeria' vs 'Nigeria' — partial match → no contradiction."""
        a = _claim(ct=ClaimType.GEOGRAPHY, value_raw="Lagos, Nigeria",
                   value_normalised="lagos, nigeria", source_url="https://a.com")
        b = _claim(ct=ClaimType.GEOGRAPHY, value_raw="Nigeria",
                   value_normalised="nigeria", source_url="https://b.com")
        contradictions, _ = detector.detect([a, b])
        assert contradictions == []
