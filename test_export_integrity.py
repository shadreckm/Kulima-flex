"""Sub-Task 7 — Trust Layer Export Integration tests.

Required tests (8):
1. Legacy export unchanged   — brief with evidence_integrity=None produces identical
                               output to pre-EIE behaviour (no new sections).
2. Reliability section present — [RELIABILITY] tag appears in full IC report TXT.
3. Verification section present — 'EVIDENCE VERIFICATION REQUIRED' appears in memo
                                   TXT when contradictions/unsupported claims exist.
4. Sparse coverage wording    — 'Limited Coverage' used; 'Low Trust' / 'Insufficient Data'
                                  never appear.
5. PDF generation succeeds    — build_memo_pdf() returns non-empty bytes without exception.
6. TXT generation succeeds    — build_full_ic_report_text() returns non-empty string.
7. Conflicted report rendering — contradictions render as [C1] in full report TXT.
8. Clean report rendering     — no verification section when report is clean (no findings).
"""

from __future__ import annotations

import pytest

from kulima.export import (
    build_full_ic_report_pdf,
    build_full_ic_report_text,
    build_memo_pdf,
    build_memo_text,
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
    InvestmentBrief,
    Recommendation,
    StalenessT,
    UnsupportedClaim,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_claim(
    value: str = "some value",
    claim_type: ClaimType = ClaimType.FUNDING_AMOUNT,
    url: str = "https://techcabal.com/example",
) -> Claim:
    return Claim(
        claim_id="test-claim",
        claim_type=claim_type,
        value_raw=value,
        source_url=url,
        source_title="TechCabal",
        staleness=StalenessT.FRESH,
        confidence=0.85,
    )


def _make_contradiction(
    value_a: str = "Revenue is $2M",
    value_b: str = "Revenue is $500K",
    severity: ContradictionSeverity = ContradictionSeverity.HIGH,
) -> Contradiction:
    return Contradiction(
        contradiction_id="c-test",
        claim_a=_make_claim(value_a, ClaimType.REVENUE),
        claim_b=_make_claim(value_b, ClaimType.REVENUE, "https://blog.example.com"),
        severity=severity,
        description="Revenue figures conflict across sources.",
        recommended_action="Verify with founder financials.",
    )


def _make_unsupported(
    description: str = "Team size not verified in open sources.",
) -> UnsupportedClaim:
    return UnsupportedClaim(
        claim_type=ClaimType.EMPLOYEE_COUNT,
        description=description,
        severity=ContradictionSeverity.MEDIUM,
        recommended_action="Request current org chart from founder.",
    )


def _make_clean_report() -> EvidenceIntegrityReport:
    """Grade A report — no contradictions, no unsupported claims."""
    return EvidenceIntegrityReport(
        integrity_score=92.0,
        integrity_grade=IntegrityGrade.A,
        evidence_depth=EvidenceDepth.RICH,
        consistency_status=ConsistencyStatus.CLEAN,
        sparse_mode=False,
        claim_count=14,
        source_count=11,
        high_authority_count=6,
        contradictions=[],
        unsupported_claims=[],
        stale_claims=[],
        ignored_conflicts=[],
        integrity_summary=(
            "Strong OSINT coverage across 11 sources. "
            "No material conflicts found."
        ),
        confidence_adjusted=0.88,
        confidence_delta=0.0,
    )


def _make_conflicted_report() -> EvidenceIntegrityReport:
    """Grade C report — one contradiction and one unsupported claim."""
    return EvidenceIntegrityReport(
        integrity_score=63.0,
        integrity_grade=IntegrityGrade.C,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=ConsistencyStatus.CONFLICTS,
        sparse_mode=False,
        claim_count=8,
        source_count=6,
        high_authority_count=3,
        contradictions=[_make_contradiction()],
        unsupported_claims=[_make_unsupported()],
        stale_claims=[],
        ignored_conflicts=[],
        integrity_summary=(
            "Moderate OSINT coverage. Sources disagree on revenue. "
            "Recommend direct founder confirmation before IC."
        ),
        verification_checklist=[
            "Verify revenue figures directly with founder.",
            "Request current org chart.",
        ],
        confidence_adjusted=0.60,
        confidence_delta=-0.05,
    )


def _make_sparse_report() -> EvidenceIntegrityReport:
    """Sparse-mode report — limited coverage, no genuine contradictions."""
    return EvidenceIntegrityReport(
        integrity_score=75.0,
        integrity_grade=IntegrityGrade.B,
        evidence_depth=EvidenceDepth.LIMITED,
        consistency_status=ConsistencyStatus.CLEAN,
        sparse_mode=True,
        claim_count=4,
        source_count=3,
        high_authority_count=1,
        contradictions=[],
        unsupported_claims=[],
        stale_claims=[],
        ignored_conflicts=[],
        integrity_summary="Limited public profile — standard for early-stage companies.",
        confidence_delta=-0.03,
    )


def _make_brief(
    ei: EvidenceIntegrityReport | None = None,
    *,
    founder: str = "Amara Diallo",
    startup: str = "PayZen Africa",
) -> InvestmentBrief:
    from kulima.models import ConfidenceLevel

    return InvestmentBrief(
        founder_name=founder,
        startup_name=startup,
        sector="Fintech",
        geography="West Africa",
        stage="Series A",
        recommendation=Recommendation.INVEST,
        overall_score=80.0,
        founder_score=82.0,
        startup_score=78.0,
        market_score=76.0,
        trust_score=74.0,
        risk_score=28.0,
        growth_potential=72.0,
        investment_readiness=70.0,
        confidence=0.82,
        confidence_level=ConfidenceLevel.HIGH,
        executive_summary="Strong fintech play in underbanked West Africa.",
        founder_assessment="Experienced operator with prior exit.",
        startup_assessment="Early but growing revenue.",
        market_assessment="Large TAM with improving mobile penetration.",
        risk_assessment="FX and regulatory risk present.",
        investment_recommendation="Proceed with lead investment.",
        next_steps=["Due diligence call", "Term sheet"],
        explainability=["High founder score driven by track record"],
        red_flags=[],
        sources=[],
        evidence_integrity=ei,
    )


# ── Test 1 — Legacy export unchanged ─────────────────────────────────────────

class TestLegacyExportUnchanged:
    """When evidence_integrity is None, exports must be functionally identical
    to pre-EIE behaviour — no new sections, no formatting changes."""

    def test_memo_text_no_reliability_section(self):
        brief = _make_brief(ei=None)
        text = build_memo_text(brief)
        assert "EVIDENCE VERIFICATION REQUIRED" not in text
        assert "EVIDENCE NOTE" not in text
        assert "Reliability Rating" not in text
        assert "[RELIABILITY]" not in text

    def test_full_report_text_no_reliability_section(self):
        brief = _make_brief(ei=None)
        text = build_full_ic_report_text(brief)
        assert "EVIDENCE RELIABILITY REPORT" not in text
        assert "[RELIABILITY]" not in text
        assert "Evidence Verification Required" not in text

    def test_memo_text_still_contains_core_sections(self):
        """Core memo structure must be intact when ei=None."""
        brief = _make_brief(ei=None)
        text = build_memo_text(brief)
        for marker in [
            "KULIMA FLEX — INVESTMENT COMMITTEE MEMO",
            "EXECUTIVE SUMMARY",
            "FOUNDER ASSESSMENT",
            "RISK ASSESSMENT",
            "SCORECARD",
            "— End of Memo —",
        ]:
            assert marker in text, f"Core section '{marker}' must be present"

    def test_full_report_text_still_contains_core_sections(self):
        brief = _make_brief(ei=None)
        text = build_full_ic_report_text(brief)
        for marker in [
            "FULL INVESTMENT COMMITTEE REPORT",
            "RED FLAG ALERTS",
            "SOURCE ATTRIBUTION",
        ]:
            assert marker in text, f"Core section '{marker}' must be present"


# ── Test 2 — Reliability section present ─────────────────────────────────────

class TestReliabilitySectionPresent:
    """[RELIABILITY] tag and rating appear in full IC report TXT when ei is set."""

    def test_reliability_tag_in_full_report(self):
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "[RELIABILITY]" in text

    def test_reliability_report_header_present(self):
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "EVIDENCE RELIABILITY REPORT" in text

    def test_rating_grade_present(self):
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "Rating: A" in text
        assert "92/100" in text

    def test_depth_label_present(self):
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "Depth:" in text
        assert EvidenceDepth.RICH.value.capitalize() in text

    def test_consistency_label_present(self):
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "Consistency:" in text

    def test_reliability_line_in_memo_header(self):
        """Memo TXT header must contain the reliability line."""
        brief = _make_brief(ei=_make_clean_report())
        text = build_memo_text(brief)
        assert "Reliability Rating:" in text
        assert "92/100" in text


# ── Test 3 — Verification section present ────────────────────────────────────

class TestVerificationSectionPresent:
    """'EVIDENCE VERIFICATION REQUIRED' appears in memo TXT when ei has findings."""

    def test_verification_section_in_memo_text(self):
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_memo_text(brief)
        assert "EVIDENCE VERIFICATION REQUIRED" in text

    def test_verification_section_contains_conflict_description(self):
        """Contradiction description ('Sources disagree on') must appear."""
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_memo_text(brief)
        assert "Sources disagree on" in text

    def test_verification_section_contains_unsupported_description(self):
        """Unsupported claim description must appear in verification section."""
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_memo_text(brief)
        assert "Team size not verified" in text

    def test_verification_section_in_full_report(self):
        """Full IC report TXT must also contain the verification entries."""
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_full_ic_report_text(brief)
        # Conflicts appear as [C1] entries
        assert "[C1]" in text
        # Unsupported appear as [U1] entries
        assert "[U1]" in text


# ── Test 4 — Sparse coverage wording ─────────────────────────────────────────

class TestSparseCoverageWording:
    """When sparse_mode=True, display 'Limited Coverage'.
    Never display 'Low Trust' or 'Insufficient Data'."""

    def test_sparse_shows_limited_coverage_in_memo(self):
        brief = _make_brief(ei=_make_sparse_report())
        text = build_memo_text(brief)
        assert "Limited Coverage" in text

    def test_sparse_shows_limited_coverage_in_full_report(self):
        brief = _make_brief(ei=_make_sparse_report())
        text = build_full_ic_report_text(brief)
        assert "Limited Coverage" in text

    def test_sparse_never_shows_low_trust(self):
        brief = _make_brief(ei=_make_sparse_report())
        memo = build_memo_text(brief)
        report = build_full_ic_report_text(brief)
        assert "Low Trust" not in memo
        assert "Low Trust" not in report

    def test_sparse_never_shows_insufficient_data(self):
        brief = _make_brief(ei=_make_sparse_report())
        memo = build_memo_text(brief)
        report = build_full_ic_report_text(brief)
        assert "Insufficient Data" not in memo
        assert "Insufficient Data" not in report

    def test_non_sparse_does_not_show_limited_coverage_label(self):
        """Non-sparse reports must not be labelled 'Limited Coverage'."""
        brief = _make_brief(ei=_make_clean_report())
        memo = build_memo_text(brief)
        # Clean report has EvidenceDepth.RICH — must show "Rich", not "Limited Coverage"
        assert "Rich" in memo
        assert "Limited Coverage" not in memo


# ── Test 5 — PDF memo generation succeeds ────────────────────────────────────

class TestPdfMemoGeneration:
    """build_memo_pdf() must return non-empty bytes without exception
    for both legacy (ei=None) and Trust Layer (ei set) briefs."""

    def test_memo_pdf_no_ei_succeeds(self):
        brief = _make_brief(ei=None)
        pdf_bytes = build_memo_pdf(brief)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_memo_pdf_with_clean_ei_succeeds(self):
        brief = _make_brief(ei=_make_clean_report())
        pdf_bytes = build_memo_pdf(brief)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_memo_pdf_with_conflicted_ei_succeeds(self):
        brief = _make_brief(ei=_make_conflicted_report())
        pdf_bytes = build_memo_pdf(brief)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_memo_pdf_with_sparse_ei_succeeds(self):
        brief = _make_brief(ei=_make_sparse_report())
        pdf_bytes = build_memo_pdf(brief)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_full_report_pdf_no_ei_succeeds(self):
        brief = _make_brief(ei=None)
        pdf_bytes = build_full_ic_report_pdf(brief)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_full_report_pdf_with_ei_succeeds(self):
        brief = _make_brief(ei=_make_conflicted_report())
        pdf_bytes = build_full_ic_report_pdf(brief)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0


# ── Test 6 — TXT generation succeeds ─────────────────────────────────────────

class TestTxtGeneration:
    """build_full_ic_report_text() must return a non-empty string without
    exception for all combinations of evidence_integrity state."""

    def test_full_report_txt_no_ei(self):
        brief = _make_brief(ei=None)
        text = build_full_ic_report_text(brief)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_full_report_txt_with_clean_ei(self):
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_full_report_txt_with_conflicted_ei(self):
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_full_ic_report_text(brief)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_full_report_txt_with_sparse_ei(self):
        brief = _make_brief(ei=_make_sparse_report())
        text = build_full_ic_report_text(brief)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_memo_txt_no_ei(self):
        brief = _make_brief(ei=None)
        text = build_memo_text(brief)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_memo_txt_with_ei(self):
        brief = _make_brief(ei=_make_clean_report())
        text = build_memo_text(brief)
        assert isinstance(text, str)
        assert len(text) > 0


# ── Test 7 — Conflicted report rendering ─────────────────────────────────────

class TestConflictedReportRendering:
    """When contradictions are present, they must render as [C1], [C2], …
    with severity and claim values visible in the full IC report TXT."""

    def test_c1_label_present(self):
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_full_ic_report_text(brief)
        assert "[C1]" in text

    def test_severity_label_present(self):
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_full_ic_report_text(brief)
        assert "HIGH" in text

    def test_claim_values_present(self):
        """Both raw claim values must appear in the output."""
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_full_ic_report_text(brief)
        assert "Revenue is $2M" in text
        assert "Revenue is $500K" in text

    def test_u1_label_present(self):
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_full_ic_report_text(brief)
        assert "[U1]" in text

    def test_unsupported_description_present(self):
        brief = _make_brief(ei=_make_conflicted_report())
        text = build_full_ic_report_text(brief)
        assert "Team size not verified" in text

    def test_multiple_contradictions_render_sequentially(self):
        """Two contradictions must produce [C1] and [C2] labels."""
        ei = EvidenceIntegrityReport(
            integrity_score=55.0,
            integrity_grade=IntegrityGrade.C,
            evidence_depth=EvidenceDepth.MODERATE,
            consistency_status=ConsistencyStatus.MAJOR_CONFLICTS,
            sparse_mode=False,
            source_count=7,
            claim_count=10,
            high_authority_count=3,
            contradictions=[
                _make_contradiction("$2M", "$500K", ContradictionSeverity.HIGH),
                _make_contradiction(
                    "Founded 2018", "Founded 2022",
                    ContradictionSeverity.MEDIUM,
                ),
            ],
            unsupported_claims=[],
        )
        brief = _make_brief(ei=ei)
        text = build_full_ic_report_text(brief)
        assert "[C1]" in text
        assert "[C2]" in text


# ── Test 8 — Clean report rendering ──────────────────────────────────────────

class TestCleanReportRendering:
    """When evidence_integrity is set but has no findings (Grade A, no
    contradictions, no unsupported claims), no verification section is shown."""

    def test_no_verification_required_section_in_memo(self):
        """Clean report must not generate 'EVIDENCE VERIFICATION REQUIRED'."""
        brief = _make_brief(ei=_make_clean_report())
        text = build_memo_text(brief)
        assert "EVIDENCE VERIFICATION REQUIRED" not in text

    def test_evidence_note_present_in_memo(self):
        """Clean report should show the EVIDENCE NOTE section instead."""
        brief = _make_brief(ei=_make_clean_report())
        text = build_memo_text(brief)
        assert "EVIDENCE NOTE" in text

    def test_no_c1_label_in_full_report(self):
        """Clean report full TXT must not contain contradiction labels."""
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "[C1]" not in text

    def test_no_u1_label_in_full_report(self):
        """Clean report full TXT must not contain unsupported claim labels."""
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "[U1]" not in text

    def test_integrity_summary_present(self):
        """The integrity_summary text must appear in the full IC report."""
        brief = _make_brief(ei=_make_clean_report())
        text = build_full_ic_report_text(brief)
        assert "Strong OSINT coverage" in text

    def test_clean_pdf_does_not_raise(self):
        """Full report PDF with a clean EI report must generate without error."""
        brief = _make_brief(ei=_make_clean_report())
        pdf_bytes = build_full_ic_report_pdf(brief)
        assert len(pdf_bytes) > 0
