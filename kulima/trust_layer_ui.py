"""Trust Layer UI helpers — renders EvidenceIntegrityReport surfaces.

All public functions are gated on the caller having confirmed
``brief.evidence_integrity is not None`` before calling.  Helpers that
accept an ``EvidenceIntegrityReport`` directly will gracefully no-op if
None is passed.

Five rendering surfaces:
  1. render_reliability_badge()  — inline one-liner signal
  2. render_evidence_depth()     — depth dots + label
  3. render_consistency_status() — icon + label
  4. render_reliability_card()   — expandable three-column card (Layer 2)
  5. render_reliability_report() — full analyst view (Layer 3)

Plus helpers used by kulima/ui.py:
  - render_trust_graph_coverage_note()
  - _depth_dots() / _grade_color() / _consistency_icon()
"""

from __future__ import annotations

import html
import textwrap
import logging

import streamlit as st

_log = logging.getLogger(__name__)

from kulima.models import (
    ConsistencyStatus,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    ThesisMatchResult,
    ThesisStatus,
)


def render_thesis_fit_card(thesis: ThesisMatchResult | None) -> None:
    """Render the 4-column Thesis Fit Card (directly below Reliability Rating)."""
    if thesis is None:
        return

    status = thesis.status
    status_text = status.value if hasattr(status, "value") else str(status)

    status_colors = {
        ThesisStatus.PASS: ("#0B6E4F", "rgba(11, 110, 79, 0.12)", "rgba(11, 110, 79, 0.3)"),
        ThesisStatus.WARN: ("#B8892D", "rgba(184, 137, 45, 0.12)", "rgba(184, 137, 45, 0.3)"),
        ThesisStatus.BLOCK: ("#9B2226", "rgba(155, 34, 38, 0.12)", "rgba(155, 34, 38, 0.3)"),
    }
    color, bg, border = status_colors.get(
        status, ("#5B6F64", "rgba(0,0,0,0.05)", "rgba(0,0,0,0.1)")
    )

    html_block = textwrap.dedent(f"""
    <div style="
        background: {bg};
        border: 1px solid {border};
        border-radius: 14px;
        padding: 0.9rem 1.1rem;
        margin: 0.6rem 0 1rem 0;
    ">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">
            <div style="font-family:Fraunces,Georgia,serif;font-size:1.15rem;font-weight:700;color:#0B3D2E;">
                🎯 Thesis Fit
            </div>
            <div style="
                background: {color};
                color: #FFFFFF;
                padding: 0.2rem 0.75rem;
                border-radius: 999px;
                font-weight: 700;
                font-size: 0.82rem;
                letter-spacing: 0.03em;
            ">
                {html.escape(status_text)} · Match {thesis.overall_match:.0f}%
            </div>
        </div>

        <div style="
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.5rem;
            text-align: center;
            margin-bottom: 0.4rem;
        ">
            <div style="background:rgba(255,255,255,0.6);padding:0.45rem;border-radius:8px;">
                <div style="font-size:0.68rem;text-transform:uppercase;color:#5B6F64;font-weight:700;">Sector Fit</div>
                <div style="font-weight:700;font-size:0.95rem;color:#0B3D2E;">{html.escape(thesis.sector_fit)}</div>
            </div>
            <div style="background:rgba(255,255,255,0.6);padding:0.45rem;border-radius:8px;">
                <div style="font-size:0.68rem;text-transform:uppercase;color:#5B6F64;font-weight:700;">Stage Fit</div>
                <div style="font-weight:700;font-size:0.95rem;color:#0B3D2E;">{html.escape(thesis.stage_fit)}</div>
            </div>
            <div style="background:rgba(255,255,255,0.6);padding:0.45rem;border-radius:8px;">
                <div style="font-size:0.68rem;text-transform:uppercase;color:#5B6F64;font-weight:700;">Geography Fit</div>
                <div style="font-weight:700;font-size:0.95rem;color:#0B3D2E;">{html.escape(thesis.geography_fit)}</div>
            </div>
            <div style="background:rgba(255,255,255,0.6);padding:0.45rem;border-radius:8px;">
                <div style="font-size:0.68rem;text-transform:uppercase;color:#5B6F64;font-weight:700;">Evidence Fit</div>
                <div style="font-weight:700;font-size:0.95rem;color:#0B3D2E;">{html.escape(thesis.evidence_fit)}</div>
            </div>
        </div>
    </div>
    """)

    _log.debug("render_thesis_fit_card html_block: %s", repr(html_block))
    st.markdown(html_block, unsafe_allow_html=True)

    if thesis.notes:
        with st.expander(
            "📝 Fund Thesis Notes",
            expanded=(status in (ThesisStatus.WARN, ThesisStatus.BLOCK)),
        ):
            for note in thesis.notes:
                st.markdown(f"- {note}")


# ── Grade colour palette ──────────────────────────────────────────────────────
_GRADE_COLORS: dict[IntegrityGrade, str] = {
    IntegrityGrade.A: "#0B6E4F",   # strong green
    IntegrityGrade.B: "#2D8A6B",   # medium green
    IntegrityGrade.C: "#B8892D",   # amber
    IntegrityGrade.D: "#D97706",   # orange
    IntegrityGrade.F: "#9B2226",   # red
}

# ── Depth dot strings (five-dot scale) ───────────────────────────────────────
_DEPTH_DOTS: dict[EvidenceDepth, str] = {
    EvidenceDepth.THIN:          "●○○○○",
    EvidenceDepth.LIMITED:       "●●○○○",
    EvidenceDepth.MODERATE:      "●●●○○",
    EvidenceDepth.RICH:          "●●●●○",
    EvidenceDepth.COMPREHENSIVE: "●●●●●",
}

# ── Consistency icons + labels ────────────────────────────────────────────────
_CONSISTENCY_ICONS: dict[ConsistencyStatus, str] = {
    ConsistencyStatus.CLEAN:             "✓",
    ConsistencyStatus.MINOR_DIFFERENCES: "〜",
    ConsistencyStatus.CONFLICTS:         "⚠",
    ConsistencyStatus.MAJOR_CONFLICTS:   "🚨",
}

_CONSISTENCY_LABELS: dict[ConsistencyStatus, str] = {
    ConsistencyStatus.CLEAN:             "Consistent",
    ConsistencyStatus.MINOR_DIFFERENCES: "Mostly consistent",
    ConsistencyStatus.CONFLICTS:         "Conflicts · Review needed",
    ConsistencyStatus.MAJOR_CONFLICTS:   "Major conflicts · Verify before IC",
}

# ── Grades that trigger auto-expanded card ────────────────────────────────────
_EXPAND_GRADES: frozenset[IntegrityGrade] = frozenset({
    IntegrityGrade.C, IntegrityGrade.D, IntegrityGrade.F,
})


# ═════════════════════════════════════════════════════════════════════════════
# Pure helper functions (no Streamlit — testable without mocking st)
# ═════════════════════════════════════════════════════════════════════════════

def _depth_dots(depth: EvidenceDepth) -> str:
    """Return a five-dot depth string, e.g. '●●●○○'."""
    return _DEPTH_DOTS.get(depth, "○○○○○")


def _grade_color(grade: IntegrityGrade) -> str:
    """Return hex colour for the given integrity grade."""
    return _GRADE_COLORS.get(grade, "#5B6F64")


def _consistency_icon(status: ConsistencyStatus) -> str:
    """Return the symbol for a consistency status."""
    return _CONSISTENCY_ICONS.get(status, "?")


def _consistency_label(status: ConsistencyStatus) -> str:
    """Return the short text label for a consistency status."""
    return _CONSISTENCY_LABELS.get(status, status.value.replace("_", " ").title())


def _sparse_label(sparse: bool) -> str:
    """Return approved Africa-aware wording for sparse evidence.

    Never returns 'Low Trust' or 'Insufficient Data'.
    """
    return "Limited Coverage" if sparse else ""


def _should_expand(grade: IntegrityGrade) -> bool:
    """Return True when the reliability card should auto-expand (grade C, D, or F)."""
    return grade in _EXPAND_GRADES


def reliability_badge_html(report: EvidenceIntegrityReport) -> str:
    """Return a compact HTML string for embedding in existing HTML elements.

    Designed for inline insertion into rec-banner HTML f-strings.
    Uses flex-wrap so the badge wraps cleanly on narrow viewports instead
    of overflowing.
    """
    if report is None:
        return ""
    color = _grade_color(report.integrity_grade)
    dots = _depth_dots(report.evidence_depth)
    icon = _consistency_icon(report.consistency_status)
    grade = html.escape(report.integrity_grade.value)
    depth_label = html.escape(
        "Limited Coverage" if report.sparse_mode
        else report.evidence_depth.value.title()
    )
    consistency = html.escape(_consistency_label(report.consistency_status))
    sparse_note = ""
    if report.sparse_mode:
        sparse_note = (
            f' <span style="font-size:0.72rem;opacity:0.85;">'
            f'· {html.escape(_sparse_label(True))}</span>'
        )
    out = (
        f'<span class="reliability-badge reliability-badge-{grade}" '
        f'style="display:inline-flex;flex-wrap:wrap;align-items:center;'
        f'gap:0.25rem;max-width:100%;overflow-wrap:break-word;'
        f'background:{color}20;border:1px solid {color}44;'
        f'color:{color};padding:0.18rem 0.6rem;border-radius:999px;'
        f'font-size:0.76rem;font-weight:700;'
        f'font-family:\'Source Sans 3\',sans-serif;letter-spacing:0.02em;">'
        f'🔬 Rating {grade}&nbsp;'
        f'<span style="font-family:monospace;white-space:nowrap;">{dots}</span>&nbsp;'
        f'{depth_label}&nbsp;{icon}&nbsp;'
        f'<span style="word-break:break-word;">{consistency}</span>'
        f'{sparse_note}</span>'
    )
    _log.debug("reliability_badge_html return: %s", repr(out))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Streamlit rendering functions
# ═════════════════════════════════════════════════════════════════════════════

def render_reliability_badge(report: EvidenceIntegrityReport | None) -> None:
    """Render the one-line inline reliability signal via st.markdown.

    Surface 1 — always visible, appears directly below recommendation banner.
    """
    if report is None:
        return
    st.markdown(reliability_badge_html(report), unsafe_allow_html=True)


def render_evidence_depth(report: EvidenceIntegrityReport | None) -> None:
    """Render evidence depth dots + label."""
    if report is None:
        return
    dots = _depth_dots(report.evidence_depth)
    label = report.evidence_depth.value.title()
    color = _grade_color(report.integrity_grade)
    st.markdown(
        f'<span style="font-family:monospace;font-size:1.1rem;color:{color};">{dots}</span> '
        f'<span style="font-size:0.85rem;color:#5B6F64;font-weight:600;">{html.escape(label)}</span>',
        unsafe_allow_html=True,
    )


def render_consistency_status(report: EvidenceIntegrityReport | None) -> None:
    """Render consistency icon + label."""
    if report is None:
        return
    icon = _consistency_icon(report.consistency_status)
    label = _consistency_label(report.consistency_status)
    st.markdown(
        f'{icon} <span style="font-size:0.85rem;color:#5B6F64;font-weight:600;">'
        f'{html.escape(label)}</span>',
        unsafe_allow_html=True,
    )


def render_reliability_card(report: EvidenceIntegrityReport | None) -> None:
    """Render the three-column expandable Reliability Card (Layer 2).

    Auto-expands for grades C, D, F.  Collapsed for A, B.
    """
    if report is None:
        return

    grade = report.integrity_grade
    color = _grade_color(grade)
    auto_expand = _should_expand(grade)

    with st.expander(
        f"🔬 Evidence Reliability Report · Rating {grade.value} ({report.integrity_score:.0f}/100)",
        expanded=auto_expand,
    ):
        # ── Three-signal row: CSS grid reflows to 1-col below 480 px ─────
        depth_label_str = (
            "Limited Coverage" if report.sparse_mode
            else report.evidence_depth.value.title()
        )
        n_con = len(report.contradictions)
        conflict_note = (
            f"{n_con} conflict{'s' if n_con != 1 else ''}"
            if n_con > 0 else "No conflicts"
        )
        icon = _consistency_icon(report.consistency_status)
        con_label = _consistency_label(report.consistency_status)
        dots = _depth_dots(report.evidence_depth)

        html_block = textwrap.dedent(f"""
            <div data-reliability-grid="" style="
                display:grid;
                grid-template-columns:repeat(3,1fr);
                gap:0.75rem;
                width:100%;
                margin-bottom:0.5rem;
            ">
                <!-- Rating -->
                <div style="text-align:center;min-width:0;">
                    <div style="font-size:0.7rem;text-transform:uppercase;
                        letter-spacing:0.07em;color:#5B6F64;font-weight:700;">
                        Rating
                    </div>
                    <div style="font-family:Fraunces,Georgia,serif;font-size:2.2rem;
                        font-weight:700;color:{color};line-height:1.1;">
                        {html.escape(grade.value)}
                    </div>
                    <div style="font-size:0.82rem;color:#5B6F64;">
                        {report.integrity_score:.0f}&nbsp;/&nbsp;100
                    </div>
                </div>
                <!-- Evidence Depth -->
                <div style="text-align:center;min-width:0;">
                    <div style="font-size:0.7rem;text-transform:uppercase;
                        letter-spacing:0.07em;color:#5B6F64;font-weight:700;">
                        Evidence Depth
                    </div>
                    <div style="font-family:monospace;font-size:1.45rem;
                        color:{color};margin:0.35rem 0 0.15rem;
                        word-break:keep-all;white-space:nowrap;">
                        {dots}
                    </div>
                    <div style="font-size:0.82rem;color:#5B6F64;">
                        {html.escape(depth_label_str)}
                    </div>
                    <div style="font-size:0.75rem;color:#8A9E94;margin-top:0.1rem;">
                        {report.source_count} source{"s" if report.source_count != 1 else ""} reviewed
                    </div>
                </div>
                <!-- Consistency -->
                <div style="text-align:center;min-width:0;">
                    <div style="font-size:0.7rem;text-transform:uppercase;
                        letter-spacing:0.07em;color:#5B6F64;font-weight:700;">
                        Consistency
                    </div>
                    <div style="font-size:1.6rem;margin:0.3rem 0 0.15rem;">
                        {icon}
                    </div>
                    <div style="font-size:0.82rem;color:#5B6F64;
                        word-break:break-word;overflow-wrap:break-word;">
                        {html.escape(con_label)}
                    </div>
                    <div style="font-size:0.75rem;color:#8A9E94;margin-top:0.1rem;">
                        {html.escape(conflict_note)}
                    </div>
                </div>
            </div>
            """)
        _log.debug("render_reliability_card html_block: %s", repr(html_block))
        st.markdown(html_block, unsafe_allow_html=True)

        # Sparse evidence Africa-aware note
        if report.sparse_mode:
            st.info(
                "**Limited Coverage** — Limited OSINT available for this company. "
                "Primary data collection recommended before IC.",
                icon="🌍",
            )

        # Plain-English summary
        if report.integrity_summary:
            st.markdown("---")
            st.caption(report.integrity_summary)

        # Top conflicts (if any)
        if report.contradictions:
            st.markdown("---")
            for i, con in enumerate(report.contradictions[:3], 1):
                severity_colors = {
                    "critical": "#9B2226", "high": "#D97706",
                    "medium": "#B8892D", "low": "#1B9AAA",
                }
                sev_color = severity_colors.get(con.severity.value, "#5B6F64")
                st.markdown(
                    f'<div style="border-left:3px solid {sev_color};'
                    f'padding:0.35rem 0.7rem;margin:0.35rem 0;'
                    f'background:rgba(0,0,0,0.02);border-radius:0 6px 6px 0;'
                    f'word-break:break-word;overflow-wrap:break-word;">'
                    f'<strong style="color:{sev_color};">⚠ [{i}]</strong> '
                    f'{html.escape(con.description[:160])}'
                    f'{"…" if len(con.description) > 160 else ""}'
                    f'<br/><span style="font-size:0.78rem;color:#5B6F64;'
                    f'word-break:break-word;">'
                    f'{html.escape(con.recommended_action)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Link to full report
        if report.extraction_notes:
            st.caption(f"ℹ️ {report.extraction_notes}")


def render_reliability_report(report: EvidenceIntegrityReport | None) -> None:
    """Render the full Layer 3 analyst reliability report.

    Shows: all contradictions, unsupported claims, stale claims,
    verification checklist, and corpus coverage note.
    """
    if report is None:
        return

    st.markdown("#### 🔬 Full Evidence Reliability Report")

    # Contradictions table
    if report.contradictions:
        st.markdown("**Detected Conflicts**")
        for i, con in enumerate(report.contradictions, 1):
            sev = con.severity.value.upper()
            st.markdown(
                f"**[C{i}] {sev}** — {con.description}  \n"
                f"*Source A:* {con.claim_a.source_title or con.claim_a.source_url}  \n"
                f"*Source B:* {con.claim_b.source_title or con.claim_b.source_url}  \n"
                f"*Action:* {con.recommended_action}"
            )
    else:
        st.success("No material conflicts detected in the evidence base.")

    # Unsupported claims
    if report.unsupported_claims and not report.sparse_mode:
        st.markdown("**Expected Facts Not Found**")
        for i, uc in enumerate(report.unsupported_claims, 1):
            st.markdown(f"**[U{i}]** {uc.description} — *{uc.recommended_action}*")

    # Stale claims
    if report.stale_claims:
        st.markdown("**Outdated Signals**")
        for i, sc in enumerate(report.stale_claims, 1):
            st.markdown(
                f"**[S{i}]** {sc.claim.claim_type.value.replace('_', ' ').title()} "
                f"({sc.staleness.value}) — *{sc.recommended_action}*"
            )

    # Verification checklist
    if report.verification_checklist:
        st.markdown("**Verification Checklist**")
        for item in report.verification_checklist:
            st.markdown(f"- {item}")

    # Coverage note
    n_ign = len(report.ignored_conflicts)
    st.caption(
        f"{report.source_count} source(s) reviewed · "
        f"{report.claim_count} fact(s) extracted · "
        f"{len(report.contradictions)} material conflict(s) · "
        f"{n_ign} suppressed (FX artefact / temporal drift)"
    )


def render_trust_graph_coverage_note(report: EvidenceIntegrityReport | None) -> None:
    """Render the compact coverage/consistency line inside the Trust Graph expander."""
    if report is None:
        return
    depth_label = report.evidence_depth.value.title()
    if report.sparse_mode:
        depth_label = "Limited Coverage"
    con_label = _consistency_label(report.consistency_status)
    icon = _consistency_icon(report.consistency_status)
    color = _grade_color(report.integrity_grade)
    st.markdown(
        f'<div style="font-size:0.82rem;color:#5B6F64;margin:0.35rem 0 0.5rem;">'
        f'Coverage: <strong style="color:{color};">{html.escape(depth_label)}</strong>'
        f'&nbsp;·&nbsp;'
        f'Consistency: <strong>{icon} {html.escape(con_label)}</strong>'
        f'</div>',
        unsafe_allow_html=True,
    )
