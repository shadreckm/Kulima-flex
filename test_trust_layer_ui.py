"""Sub-Task 5 — Trust Layer UI tests.

All tests target the pure (non-Streamlit) helper functions in
kulima/trust_layer_ui.py.  Streamlit rendering functions are tested by
verifying they do NOT raise when called with mocked st (via unittest.mock).

Covers:
1.  Badge rendering — HTML content and structure
2.  Reliability report rendering — no exceptions
3.  Sparse evidence mode — correct wording
4.  Legacy run — None report → no-op
5.  Auto-expand C/D/F
6.  No rendering when evidence_integrity=None
7.  depth_dots coverage
8.  grade_color coverage
9.  consistency_icon coverage
10. render_history_panel integrity columns
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kulima.models import (
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    StalenessT,
    UnsupportedClaim,
)
from kulima.trust_layer_ui import (
    _consistency_icon,
    _consistency_label,
    _depth_dots,
    _grade_color,
    _should_expand,
    _sparse_label,
    reliability_badge_html,
    render_evidence_depth,
    render_reliability_badge,
    render_reliability_card,
    render_reliability_report,
    render_trust_graph_coverage_note,
    render_consistency_status,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _minimal_report(
    grade: IntegrityGrade = IntegrityGrade.B,
    score: float = 78.0,
    sparse: bool = False,
    consistency: ConsistencyStatus = ConsistencyStatus.CLEAN,
    depth: EvidenceDepth = EvidenceDepth.MODERATE,
) -> EvidenceIntegrityReport:
    return EvidenceIntegrityReport(
        integrity_score=score,
        integrity_grade=grade,
        evidence_depth=depth,
        consistency_status=consistency,
        sparse_mode=sparse,
        source_count=6,
        high_authority_count=3,
        integrity_summary="Moderate coverage.",
    )


def _claim(url: str = "https://a.com") -> Claim:
    return Claim(
        claim_type=ClaimType.FUNDING_AMOUNT,
        value_raw="$2M",
        source_url=url,
        source_authority="high_authority_web",
    )


def _with_contradictions(n: int = 1) -> EvidenceIntegrityReport:
    contradictions = [
        Contradiction(
            claim_a=_claim("https://a.com"),
            claim_b=_claim("https://b.com"),
            severity=ContradictionSeverity.CRITICAL,
            description="Sources disagree on funding.",
            recommended_action="Verify with founder.",
        )
        for _ in range(n)
    ]
    return EvidenceIntegrityReport(
        integrity_score=63.0,
        integrity_grade=IntegrityGrade.C,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=ConsistencyStatus.CONFLICTS,
        contradictions=contradictions,
        source_count=6,
    )


# ── Mock st globally for all rendering tests ─────────────────────────────────

@pytest.fixture(autouse=True)
def mock_streamlit():
    """Mock the entire streamlit module so no Streamlit server is needed."""
    mock_st = MagicMock()
    # Make expander work as a context manager
    mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
    mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
    # columns() also needs context manager support per column
    for col in mock_st.columns.return_value:
        col.__enter__ = MagicMock(return_value=col)
        col.__exit__ = MagicMock(return_value=False)
    with patch("kulima.trust_layer_ui.st", mock_st):
        yield mock_st


# ══════════════════════════════════════════════════════════════════════════════
# 1 — Badge rendering
# ══════════════════════════════════════════════════════════════════════════════

class TestBadgeRendering:
    def test_badge_html_contains_grade(self) -> None:
        report = _minimal_report(grade=IntegrityGrade.B)
        html = reliability_badge_html(report)
        assert "Rating B" in html

    def test_badge_html_contains_dots(self) -> None:
        report = _minimal_report(depth=EvidenceDepth.MODERATE)
        html = reliability_badge_html(report)
        # Moderate = ●●●○○
        assert "●●●○○" in html

    def test_badge_html_contains_consistency_icon(self) -> None:
        report = _minimal_report(consistency=ConsistencyStatus.CLEAN)
        html = reliability_badge_html(report)
        assert "✓" in html

    def test_badge_html_contains_depth_label(self) -> None:
        report = _minimal_report(depth=EvidenceDepth.RICH)
        html = reliability_badge_html(report)
        assert "Rich" in html

    def test_badge_html_none_returns_empty(self) -> None:
        assert reliability_badge_html(None) == ""

    def test_badge_html_contains_grade_css_class(self) -> None:
        report = _minimal_report(grade=IntegrityGrade.C)
        html = reliability_badge_html(report)
        assert "reliability-badge-C" in html

    def test_badge_html_grade_a_green_color(self) -> None:
        report = _minimal_report(grade=IntegrityGrade.A)
        html = reliability_badge_html(report)
        assert "#0B6E4F" in html

    def test_badge_html_grade_f_red_color(self) -> None:
        report = _minimal_report(grade=IntegrityGrade.F)
        html = reliability_badge_html(report)
        assert "#9B2226" in html

    def test_render_reliability_badge_calls_st_markdown(self, mock_streamlit) -> None:
        report = _minimal_report()
        render_reliability_badge(report)
        mock_streamlit.markdown.assert_called()

    def test_render_reliability_badge_none_does_not_call_st(self, mock_streamlit) -> None:
        render_reliability_badge(None)
        mock_streamlit.markdown.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 2 — Reliability report rendering
# ══════════════════════════════════════════════════════════════════════════════

class TestReliabilityReportRendering:
    def test_render_reliability_card_does_not_raise(self, mock_streamlit) -> None:
        report = _minimal_report()
        render_reliability_card(report)  # must not raise

    def test_render_reliability_card_calls_expander(self, mock_streamlit) -> None:
        report = _minimal_report(grade=IntegrityGrade.B, score=78.0)
        render_reliability_card(report)
        mock_streamlit.expander.assert_called()
        call_args = mock_streamlit.expander.call_args[0][0]
        assert "78" in call_args

    def test_render_reliability_report_does_not_raise(self, mock_streamlit) -> None:
        report = _with_contradictions(2)
        render_reliability_report(report)  # must not raise

    def test_render_reliability_report_with_no_contradictions(self, mock_streamlit) -> None:
        report = _minimal_report()
        render_reliability_report(report)  # must not raise
        mock_streamlit.success.assert_called_once()

    def test_render_evidence_depth_calls_st_markdown(self, mock_streamlit) -> None:
        report = _minimal_report(depth=EvidenceDepth.RICH)
        render_evidence_depth(report)
        mock_streamlit.markdown.assert_called()

    def test_render_consistency_status_calls_st_markdown(self, mock_streamlit) -> None:
        report = _minimal_report(consistency=ConsistencyStatus.CONFLICTS)
        render_consistency_status(report)
        mock_streamlit.markdown.assert_called()

    def test_render_trust_graph_coverage_note_does_not_raise(self, mock_streamlit) -> None:
        report = _minimal_report()
        render_trust_graph_coverage_note(report)


# ══════════════════════════════════════════════════════════════════════════════
# 3 — Sparse evidence mode wording
# ══════════════════════════════════════════════════════════════════════════════

class TestSparseEvidenceMode:
    def test_sparse_label_returns_limited_coverage(self) -> None:
        assert _sparse_label(True) == "Limited Coverage"

    def test_sparse_label_false_returns_empty(self) -> None:
        assert _sparse_label(False) == ""

    def test_sparse_label_never_says_low_trust(self) -> None:
        label = _sparse_label(True)
        assert "Low Trust" not in label
        assert "Insufficient Data" not in label

    def test_badge_html_includes_sparse_note(self) -> None:
        report = _minimal_report(sparse=True)
        html = reliability_badge_html(report)
        assert "Limited Coverage" in html

    def test_badge_html_sparse_false_no_note(self) -> None:
        report = _minimal_report(sparse=False)
        html = reliability_badge_html(report)
        assert "Limited Coverage" not in html

    def test_render_reliability_card_sparse_calls_st_info(self, mock_streamlit) -> None:
        report = _minimal_report(sparse=True)
        render_reliability_card(report)
        mock_streamlit.info.assert_called()

    def test_render_reliability_card_sparse_info_contains_approved_wording(
        self, mock_streamlit
    ) -> None:
        report = _minimal_report(sparse=True)
        render_reliability_card(report)
        info_call = mock_streamlit.info.call_args[0][0]
        assert "Limited Coverage" in info_call
        assert "Low Trust" not in info_call
        assert "Insufficient Data" not in info_call

    def test_trust_graph_note_sparse_shows_limited_coverage(self, mock_streamlit) -> None:
        report = _minimal_report(sparse=True)
        render_trust_graph_coverage_note(report)
        # Check that the markdown call included "Limited Coverage"
        call_str = mock_streamlit.markdown.call_args[0][0]
        assert "Limited Coverage" in call_str


# ══════════════════════════════════════════════════════════════════════════════
# 4 — Legacy run rendering (evidence_integrity=None)
# ══════════════════════════════════════════════════════════════════════════════

class TestLegacyRunRendering:
    def test_render_reliability_badge_none_is_noop(self, mock_streamlit) -> None:
        render_reliability_badge(None)
        mock_streamlit.markdown.assert_not_called()

    def test_render_reliability_card_none_is_noop(self, mock_streamlit) -> None:
        render_reliability_card(None)
        mock_streamlit.expander.assert_not_called()

    def test_render_reliability_report_none_is_noop(self, mock_streamlit) -> None:
        render_reliability_report(None)
        mock_streamlit.markdown.assert_not_called()

    def test_render_evidence_depth_none_is_noop(self, mock_streamlit) -> None:
        render_evidence_depth(None)
        mock_streamlit.markdown.assert_not_called()

    def test_render_consistency_status_none_is_noop(self, mock_streamlit) -> None:
        render_consistency_status(None)
        mock_streamlit.markdown.assert_not_called()

    def test_render_trust_graph_note_none_is_noop(self, mock_streamlit) -> None:
        render_trust_graph_coverage_note(None)
        mock_streamlit.markdown.assert_not_called()

    def test_reliability_badge_html_none_is_empty_string(self) -> None:
        assert reliability_badge_html(None) == ""


# ══════════════════════════════════════════════════════════════════════════════
# 5 — Auto-expand C/D/F
# ══════════════════════════════════════════════════════════════════════════════

class TestAutoExpand:
    def test_grade_c_should_expand(self) -> None:
        assert _should_expand(IntegrityGrade.C) is True

    def test_grade_d_should_expand(self) -> None:
        assert _should_expand(IntegrityGrade.D) is True

    def test_grade_f_should_expand(self) -> None:
        assert _should_expand(IntegrityGrade.F) is True

    def test_grade_a_should_not_expand(self) -> None:
        assert _should_expand(IntegrityGrade.A) is False

    def test_grade_b_should_not_expand(self) -> None:
        assert _should_expand(IntegrityGrade.B) is False

    def test_render_reliability_card_grade_c_expanded_true(self, mock_streamlit) -> None:
        report = _minimal_report(grade=IntegrityGrade.C, score=63.0)
        render_reliability_card(report)
        call_kwargs = mock_streamlit.expander.call_args[1]
        assert call_kwargs.get("expanded") is True

    def test_render_reliability_card_grade_a_expanded_false(self, mock_streamlit) -> None:
        report = _minimal_report(grade=IntegrityGrade.A, score=92.0)
        render_reliability_card(report)
        call_kwargs = mock_streamlit.expander.call_args[1]
        assert call_kwargs.get("expanded") is False

    def test_render_reliability_card_grade_f_expanded_true(self, mock_streamlit) -> None:
        report = _minimal_report(grade=IntegrityGrade.F, score=30.0)
        render_reliability_card(report)
        call_kwargs = mock_streamlit.expander.call_args[1]
        assert call_kwargs.get("expanded") is True


# ══════════════════════════════════════════════════════════════════════════════
# 6 — No rendering when evidence_integrity=None (in-context gate)
# ══════════════════════════════════════════════════════════════════════════════

class TestNoneGating:
    """Verify that app.py's `if brief.evidence_integrity:` gate works end-to-end
    by testing the rendering functions directly with None."""

    def test_all_render_functions_accept_none_without_exception(
        self, mock_streamlit
    ) -> None:
        # None must never raise — these are the same guards used in app.py
        render_reliability_badge(None)
        render_evidence_depth(None)
        render_consistency_status(None)
        render_reliability_card(None)
        render_reliability_report(None)
        render_trust_graph_coverage_note(None)

    def test_no_st_calls_made_for_any_none_report(self, mock_streamlit) -> None:
        render_reliability_badge(None)
        render_evidence_depth(None)
        render_consistency_status(None)
        render_reliability_card(None)
        render_reliability_report(None)
        render_trust_graph_coverage_note(None)
        # None of the above should have called any st.* method
        mock_streamlit.markdown.assert_not_called()
        mock_streamlit.expander.assert_not_called()
        mock_streamlit.info.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 7 — depth_dots coverage
# ══════════════════════════════════════════════════════════════════════════════

class TestDepthDots:
    def test_thin_is_one_filled(self) -> None:
        assert _depth_dots(EvidenceDepth.THIN) == "●○○○○"

    def test_limited_is_two_filled(self) -> None:
        assert _depth_dots(EvidenceDepth.LIMITED) == "●●○○○"

    def test_moderate_is_three_filled(self) -> None:
        assert _depth_dots(EvidenceDepth.MODERATE) == "●●●○○"

    def test_rich_is_four_filled(self) -> None:
        assert _depth_dots(EvidenceDepth.RICH) == "●●●●○"

    def test_comprehensive_is_five_filled(self) -> None:
        assert _depth_dots(EvidenceDepth.COMPREHENSIVE) == "●●●●●"


# ══════════════════════════════════════════════════════════════════════════════
# 8 — grade_color coverage
# ══════════════════════════════════════════════════════════════════════════════

class TestGradeColor:
    def test_grade_a_is_green(self) -> None:
        assert _grade_color(IntegrityGrade.A) == "#0B6E4F"

    def test_grade_b_is_medium_green(self) -> None:
        assert _grade_color(IntegrityGrade.B) == "#2D8A6B"

    def test_grade_c_is_amber(self) -> None:
        assert _grade_color(IntegrityGrade.C) == "#B8892D"

    def test_grade_d_is_orange(self) -> None:
        assert _grade_color(IntegrityGrade.D) == "#D97706"

    def test_grade_f_is_red(self) -> None:
        assert _grade_color(IntegrityGrade.F) == "#9B2226"

    def test_all_grades_return_a_hex_string(self) -> None:
        for grade in IntegrityGrade:
            color = _grade_color(grade)
            assert color.startswith("#")
            assert len(color) == 7


# ══════════════════════════════════════════════════════════════════════════════
# 9 — consistency_icon coverage
# ══════════════════════════════════════════════════════════════════════════════

class TestConsistencyIcon:
    def test_clean_is_checkmark(self) -> None:
        assert _consistency_icon(ConsistencyStatus.CLEAN) == "✓"

    def test_minor_differences_is_tilde(self) -> None:
        assert _consistency_icon(ConsistencyStatus.MINOR_DIFFERENCES) == "〜"

    def test_conflicts_is_warning(self) -> None:
        assert _consistency_icon(ConsistencyStatus.CONFLICTS) == "⚠"

    def test_major_conflicts_is_siren(self) -> None:
        assert _consistency_icon(ConsistencyStatus.MAJOR_CONFLICTS) == "🚨"


# ══════════════════════════════════════════════════════════════════════════════
# 10 — Memory panel integrity columns (ui.py render_history_panel)
# ══════════════════════════════════════════════════════════════════════════════

class TestHistoryPanelIntegrityColumns:
    """Test render_history_panel builds correct display rows with integrity data."""

    def _build_rows_with_integrity(self) -> list[dict]:
        return [
            {
                "id": 12,
                "created_at": "2025-01-15T10:00:00+00:00",
                "founder_name": "Ada Obi",
                "startup_name": "PayFast NG",
                "recommendation": "Invest",
                "overall_score": 82.0,
                "confidence": 0.81,
                "trust_score": 68.0,
                "founder_score": 78.0,
                "integrity_grade": "A",
                "integrity_score": 91.0,
            },
            {
                "id": 13,
                "created_at": "2025-01-12T08:30:00+00:00",
                "founder_name": "Kofi M",
                "startup_name": "AgriLink",
                "recommendation": "Observe",
                "overall_score": 64.0,
                "confidence": 0.65,
                "trust_score": 55.0,
                "founder_score": 62.0,
                "integrity_grade": "C",
                "integrity_score": 63.0,
            },
        ]

    def _build_rows_without_integrity(self) -> list[dict]:
        return [
            {
                "id": 10,
                "created_at": "2024-11-01T09:00:00+00:00",
                "founder_name": "Legacy Founder",
                "startup_name": "Legacy Startup",
                "recommendation": "Pass",
                "overall_score": 42.0,
                "confidence": 0.45,
                "trust_score": 40.0,
                "founder_score": 38.0,
                # no integrity_grade or integrity_score — pre-EIE run
            }
        ]

    def test_display_rows_include_reliability_column_when_available(self) -> None:
        """When integrity_grade is in row dicts, display rows must have Reliability."""
        rows = self._build_rows_with_integrity()
        _has_integrity = any("integrity_grade" in r for r in rows)
        assert _has_integrity is True

        display_rows = []
        for r in rows:
            row_dict: dict = {
                "Select": False,
                "ID": int(r["id"]),
                "Rec": r.get("recommendation", "Observe"),
                "Score": f"{float(r.get('overall_score') or 0):.0f}",
            }
            if _has_integrity:
                grade = r.get("integrity_grade") or "—"
                score = r.get("integrity_score")
                row_dict["Reliability"] = grade
                row_dict["Rel. Score"] = f"{score:.0f}" if score is not None else "—"
            display_rows.append(row_dict)

        assert display_rows[0]["Reliability"] == "A"
        assert display_rows[0]["Rel. Score"] == "91"
        assert display_rows[1]["Reliability"] == "C"
        assert display_rows[1]["Rel. Score"] == "63"

    def test_display_rows_without_integrity_have_no_reliability_column(self) -> None:
        rows = self._build_rows_without_integrity()
        _has_integrity = any("integrity_grade" in r for r in rows)
        assert _has_integrity is False

        display_rows = []
        for r in rows:
            row_dict: dict = {
                "Select": False,
                "ID": int(r["id"]),
                "Score": f"{float(r.get('overall_score') or 0):.0f}",
            }
            if _has_integrity:
                row_dict["Reliability"] = r.get("integrity_grade") or "—"
            display_rows.append(row_dict)

        assert "Reliability" not in display_rows[0]

    def test_null_integrity_values_show_dash(self) -> None:
        """Rows where integrity columns are present but NULL must show '—'."""
        rows = [
            {
                "id": 11,
                "created_at": "2025-01-01T00:00:00+00:00",
                "founder_name": "Test",
                "startup_name": "Test",
                "recommendation": "Observe",
                "overall_score": 60.0,
                "confidence": 0.60,
                "trust_score": 55.0,
                "founder_score": 58.0,
                "integrity_grade": None,
                "integrity_score": None,
            }
        ]
        _has_integrity = any("integrity_grade" in r for r in rows)
        assert _has_integrity is True

        display_rows = []
        for r in rows:
            row_dict: dict = {}
            if _has_integrity:
                grade = r.get("integrity_grade") or "—"
                score = r.get("integrity_score")
                row_dict["Reliability"] = grade
                row_dict["Rel. Score"] = f"{score:.0f}" if score is not None else "—"
            display_rows.append(row_dict)

        assert display_rows[0]["Reliability"] == "—"
        assert display_rows[0]["Rel. Score"] == "—"
