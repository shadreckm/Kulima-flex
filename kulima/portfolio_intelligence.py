"""Portfolio Intelligence Layer — aggregation, charts, risk matrix, and ranking.

Transforms stored deal rows (from IntelligenceRepository.recent_runs) into
portfolio-level insights without any new AI calls or external APIs.

Public API — pure functions (no Streamlit, fully testable):
  aggregate_portfolio()         — KPI dict from a list of run rows
  build_pilot_analytics_metrics() — Pilot analytics KPI dict from stored runs
  top_deals()                   — ranked slice of rows
  ic_pipeline_filter()          — rows ready for IC presentation
  quadrant_label()              — risk-matrix quadrant for a single row
  recommendation_chart()        — Plotly donut/pie for rec distribution
  reliability_chart()           — Plotly bar for grade distribution
  sector_chart()                — Plotly bar for sector distribution
  score_vs_reliability_scatter()— Plotly scatter: score vs reliability
  risk_matrix_figure()          — Plotly scatter: portfolio risk matrix
  thesis_distribution_chart()   — Plotly bar: fund thesis status distribution

Public API — Streamlit renderers:
  render_portfolio_dashboard()  — full Portfolio Intelligence dashboard
  render_analytics_workspace()  — pilot analytics workspace

No agents, orchestrator, scoring, Trust Layer, or database schema modified.
"""

from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go
import streamlit as st

# ── Grade ordering (A best → F worst) ────────────────────────────────────────
_GRADE_ORDER: dict[str, int] = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1, "—": 0}
_GRADE_COLORS: dict[str, str] = {
    "A": "#0B6E4F",
    "B": "#2D8A6B",
    "C": "#B8892D",
    "D": "#D97706",
    "F": "#9B2226",
    "—": "#8A9E94",
}

# ── Recommendation colours (consistent with existing REC_COLORS in ui.py) ───
_REC_COLORS: dict[str, str] = {
    "Invest": "#0B6E4F",
    "Co-Invest": "#1B9AAA",
    "Observe": "#B8892D",
    "Follow-On Watch": "#D97706",
    "Pass": "#9B2226",
    "—": "#8A9E94",
}

# ── IC-ready criteria ─────────────────────────────────────────────────────────
_IC_READY_RECS: frozenset[str] = frozenset({"Invest", "Co-Invest"})
_IC_READY_GRADES: frozenset[str] = frozenset({"A", "B"})


# ═════════════════════════════════════════════════════════════════════════════
# Pure data helpers
# ═════════════════════════════════════════════════════════════════════════════


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "—") -> str:
    return str(value).strip() if value is not None and str(value).strip() else default


def aggregate_portfolio(rows: list[dict]) -> dict[str, Any]:
    """Compute portfolio-level KPIs from a list of run-row dicts."""
    if not rows:
        return {
            "total_deals": 0,
            "invest_count": 0,
            "co_invest_count": 0,
            "observe_count": 0,
            "follow_on_count": 0,
            "pass_count": 0,
            "avg_score": 0.0,
            "avg_reliability": 0.0,
            "avg_confidence": 0.0,
            "avg_thesis_match": 0.0,
            "ic_ready_count": 0,
            "has_reliability_data": False,
        }

    rec_counts: dict[str, int] = {}
    scores: list[float] = []
    reliabilities: list[float] = []
    confidences: list[float] = []
    thesis_matches: list[float] = []

    from kulima.thesis import evaluate_thesis_match

    for row in rows:
        rec = _safe_str(row.get("recommendation"), "—")
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

        score = _safe_float(row.get("overall_score"))
        if score > 0:
            scores.append(score)

        rel = row.get("integrity_score")
        if rel is not None:
            reliabilities.append(_safe_float(rel))

        conf = row.get("confidence")
        if conf is not None:
            confidences.append(_safe_float(conf))

        tm = row.get("thesis_match")
        if isinstance(tm, dict):
            thesis_matches.append(_safe_float(tm.get("overall_match")))
        elif tm is not None and hasattr(tm, "overall_match"):
            thesis_matches.append(_safe_float(tm.overall_match))
        else:
            t_res = evaluate_thesis_match(row)
            thesis_matches.append(_safe_float(getattr(t_res, "overall_match", 0.0)))

    ic_ready = ic_pipeline_filter(rows)

    return {
        "total_deals": len(rows),
        "invest_count": rec_counts.get("Invest", 0),
        "co_invest_count": rec_counts.get("Co-Invest", 0),
        "observe_count": rec_counts.get("Observe", 0),
        "follow_on_count": rec_counts.get("Follow-On Watch", 0),
        "pass_count": rec_counts.get("Pass", 0),
        "avg_score": sum(scores) / len(scores) if scores else 0.0,
        "avg_reliability": sum(reliabilities) / len(reliabilities) if reliabilities else 0.0,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "avg_thesis_match": sum(thesis_matches) / len(thesis_matches) if thesis_matches else 0.0,
        "ic_ready_count": len(ic_ready),
        "has_reliability_data": len(reliabilities) > 0,
    }


def build_pilot_analytics_metrics(rows: list[dict]) -> dict[str, Any]:
    """Compute pilot analytics metrics from stored run rows.

    The workspace reads persisted runs only; it does not derive any new model
    output or mutate the intelligence pipeline.
    """
    if not rows:
        return {
            "total_runs": 0,
            "pass_count": 0,
            "observe_count": 0,
            "invest_count": 0,
            "co_invest_count": 0,
            "average_score": 0.0,
            "average_confidence": 0.0,
            "average_trust": 0.0,
            "average_risk": 0.0,
            "average_contradictions": 0.0,
            "average_unsupported_claims": 0.0,
            "evidence_coverage": 0.0,
            "signal_coverage": 0.0,
        }

    rec_counts: dict[str, int] = {}
    scores: list[float] = []
    confidences: list[float] = []
    trusts: list[float] = []
    risks: list[float] = []
    contradictions: list[float] = []
    unsupported_claims: list[float] = []
    evidence_coverage: list[float] = []
    signal_coverage: list[float] = []
    core_signal_sections = ("founder", "startup", "diligence", "risk", "memo")

    for row in rows:
        payload: dict[str, Any] = {}
        payload_json = row.get("payload_json")
        if isinstance(payload_json, str) and payload_json.strip():
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}
        elif isinstance(row.get("payload"), dict):
            payload = row["payload"]

        recommendation = _safe_str(row.get("recommendation") or payload.get("recommendation"), "—")
        rec_counts[recommendation] = rec_counts.get(recommendation, 0) + 1

        score = row.get("overall_score")
        if score is None:
            score = payload.get("overall_score")
        scores.append(_safe_float(score))

        confidence = row.get("confidence")
        if confidence is None:
            confidence = payload.get("confidence")
        confidences.append(_safe_float(confidence))

        trust = row.get("trust_score")
        if trust is None:
            trust = payload.get("trust_score")
        trusts.append(_safe_float(trust))

        risk = row.get("risk_score")
        if risk is None:
            risk = payload.get("risk_score")
        risks.append(_safe_float(risk))

        ei = row.get("evidence_integrity")
        if not isinstance(ei, dict):
            ei = payload.get("evidence_integrity") or {}

        contradictions.append(float(len(ei.get("contradictions") or [])))
        unsupported_claims.append(float(len(ei.get("unsupported_claims") or [])))

        claim_count = _safe_float(ei.get("claim_count"), 0.0)
        source_count = _safe_float(ei.get("source_count"), 0.0)
        if claim_count > 0:
            evidence_coverage.append(min(source_count / claim_count, 1.0) * 100.0)
        else:
            evidence_coverage.append(0.0)

        agent_results = row.get("agent_results")
        if not isinstance(agent_results, dict):
            agent_results = payload.get("agent_results") or {}
        if isinstance(agent_results, dict):
            completed = sum(1 for section in core_signal_sections if agent_results.get(section))
            signal_coverage.append((completed / len(core_signal_sections)) * 100.0)
        else:
            signal_coverage.append(0.0)

    return {
        "total_runs": len(rows),
        "pass_count": rec_counts.get("Pass", 0),
        "observe_count": rec_counts.get("Observe", 0),
        "invest_count": rec_counts.get("Invest", 0),
        "co_invest_count": rec_counts.get("Co-Invest", 0),
        "average_score": sum(scores) / len(scores),
        "average_confidence": sum(confidences) / len(confidences),
        "average_trust": sum(trusts) / len(trusts),
        "average_risk": sum(risks) / len(risks),
        "average_contradictions": sum(contradictions) / len(contradictions),
        "average_unsupported_claims": sum(unsupported_claims) / len(unsupported_claims),
        "evidence_coverage": sum(evidence_coverage) / len(evidence_coverage),
        "signal_coverage": sum(signal_coverage) / len(signal_coverage),
    }



def top_deals(
    rows: list[dict],
    sort_by: str = "score",
    limit: int = 10,
) -> list[dict]:
    """Return the top N deals ranked by the chosen dimension.

    sort_by options: 'score' | 'reliability' | 'confidence' | 'thesis_match'
    """
    if not rows:
        return []

    from kulima.thesis import evaluate_thesis_match

    def _sort_key(row: dict) -> float:
        if sort_by == "thesis_match":
            tm = row.get("thesis_match")
            if isinstance(tm, dict):
                return _safe_float(tm.get("overall_match"))
            if tm is not None and hasattr(tm, "overall_match"):
                return _safe_float(tm.overall_match)
            t_res = evaluate_thesis_match(row)
            return _safe_float(getattr(t_res, "overall_match", 0.0))
        if sort_by == "reliability":
            rel = row.get("integrity_score")
            if rel is not None:
                return _safe_float(rel)
            grade = _safe_str(row.get("integrity_grade"), "—")
            return float(_GRADE_ORDER.get(grade, 0) * 20.0)
        if sort_by == "confidence":
            return _safe_float(row.get("confidence"))
        # default: score
        return _safe_float(row.get("overall_score"))

    return sorted(rows, key=_sort_key, reverse=True)[:limit]


def ic_pipeline_filter(rows: list[dict]) -> list[dict]:
    """Return only rows that are IC-ready."""
    result: list[dict] = []
    for row in rows:
        rec = _safe_str(row.get("recommendation"), "—")
        if rec not in _IC_READY_RECS:
            continue
        grade = _safe_str(row.get("integrity_grade"), "—")
        if grade == "—" or grade in _IC_READY_GRADES:
            result.append(row)
    return result


def quadrant_label(overall_score: float, integrity_score: float | None) -> str:
    """Return the risk-matrix quadrant label for a single deal."""
    if integrity_score is None:
        return "No Reliability Data"
    high_score = overall_score >= 65
    high_rel = integrity_score >= 65
    if high_score and high_rel:
        return "Strong IC Candidate"
    if high_score and not high_rel:
        return "Verify Before IC"
    if not high_score and high_rel:
        return "Evidence Solid, Deal Weak"
    return "Primary Data Needed"


# ═════════════════════════════════════════════════════════════════════════════
# Plotly Chart Generators (Pure Functions)
# ═════════════════════════════════════════════════════════════════════════════


def recommendation_chart(rows: list[dict]) -> go.Figure:
    """Plotly donut chart of recommendation distribution."""
    if not rows:
        fig = go.Figure()
        fig.add_annotation(
            text="No Deal Data", showarrow=False, font=dict(size=14, color="#8A9E94")
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=280
        )
        return fig

    counts: dict[str, int] = {}
    for r in rows:
        rec = _safe_str(r.get("recommendation"), "—")
        counts[rec] = counts.get(rec, 0) + 1

    labels = list(counts.keys())
    values = list(counts.values())
    colors = [_REC_COLORS.get(lbl, "#8A9E94") for lbl in labels]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.5,
                marker=dict(colors=colors),
                textinfo="label+value",
                insidetextorientation="radial",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        title="Recommendation Distribution",
        title_x=0.05,
        margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(orientation="h", y=-0.1),
        height=280,
    )
    return fig


def reliability_chart(rows: list[dict]) -> go.Figure:
    """Plotly bar chart of Integrity Grade distribution (A, B, C, D, F, Unrated)."""
    grade_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0, "Unrated": 0}
    for r in rows:
        grade = _safe_str(r.get("integrity_grade"), "—")
        if grade in grade_counts:
            grade_counts[grade] += 1
        else:
            grade_counts["Unrated"] += 1

    grades = ["A", "B", "C", "D", "F", "Unrated"]
    counts = [grade_counts[g] for g in grades]
    colors = [_GRADE_COLORS.get(g, "#8A9E94") for g in grades]

    fig = go.Figure(
        data=[
            go.Bar(
                x=grades,
                y=counts,
                marker=dict(color=colors),
                text=counts,
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title="Reliability Grade Distribution",
        title_x=0.05,
        xaxis=dict(title="Integrity Grade"),
        yaxis=dict(title="Deals", dtick=1),
        margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
    )
    return fig


def sector_chart(rows: list[dict]) -> go.Figure:
    """Plotly horizontal bar chart of sector breakdown."""
    if not rows:
        fig = go.Figure()
        fig.add_annotation(
            text="No Sector Data", showarrow=False, font=dict(size=14, color="#8A9E94")
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=280
        )
        return fig

    sector_counts: dict[str, int] = {}
    for r in rows:
        sec = _safe_str(r.get("sector"), "General / Tech")
        sector_counts[sec] = sector_counts.get(sec, 0) + 1

    sorted_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=False)
    sectors = [item[0] for item in sorted_sectors]
    counts = [item[1] for item in sorted_sectors]

    fig = go.Figure(
        data=[
            go.Bar(
                x=counts,
                y=sectors,
                orientation="h",
                marker=dict(color="#1B9AAA"),
                text=counts,
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title="Sector Breakdown",
        title_x=0.05,
        xaxis=dict(title="Deals", dtick=1),
        yaxis=dict(title="Sector"),
        margin=dict(t=40, b=30, l=80, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
    )
    return fig


def thesis_distribution_chart(rows: list[dict]) -> go.Figure:
    """Plotly bar chart showing Thesis Status Distribution (PASS, WARN, BLOCK)."""
    if not rows:
        fig = go.Figure()
        fig.add_annotation(
            text="No Deal Data", showarrow=False, font=dict(size=14, color="#8A9E94")
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=280
        )
        return fig

    status_counts = {"PASS": 0, "WARN": 0, "BLOCK": 0}
    from kulima.thesis import evaluate_thesis_match

    for r in rows:
        tm = r.get("thesis_match")
        if isinstance(tm, dict):
            st_val = str(tm.get("status", "PASS")).upper()
        elif tm is not None and hasattr(tm, "status"):
            st_val = tm.status.value if hasattr(tm.status, "value") else str(tm.status).upper()
        else:
            t_res = evaluate_thesis_match(r)
            st_val = getattr(getattr(t_res, "status", None), "value", str(getattr(t_res, "status", "PASS")).upper())

        status_counts[st_val] = status_counts.get(st_val, 0) + 1

    labels = ["PASS", "WARN", "BLOCK"]
    counts = [status_counts[l] for l in labels]
    colors = ["#0B6E4F", "#B8892D", "#9B2226"]

    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=counts,
                marker=dict(color=colors),
                text=counts,
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title="Fund Thesis Status Distribution",
        title_x=0.05,
        xaxis=dict(title="Thesis Status"),
        yaxis=dict(title="Deals", dtick=1),
        margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
    )
    return fig


def score_vs_reliability_scatter(rows: list[dict]) -> go.Figure:
    """Plotly scatter plot mapping Overall Score vs Reliability Rating."""
    if not rows:
        fig = go.Figure()
        fig.add_annotation(
            text="No Deal Data", showarrow=False, font=dict(size=14, color="#8A9E94")
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=320
        )
        return fig

    x_scores = []
    y_rels = []
    hover_texts = []
    colors = []

    for r in rows:
        score = _safe_float(r.get("overall_score"))
        rel = r.get("integrity_score")
        rel_val = _safe_float(rel, default=50.0) if rel is not None else 50.0
        rec = _safe_str(r.get("recommendation"), "—")
        startup = _safe_str(r.get("startup_name"), "Unknown Startup")
        founder = _safe_str(r.get("founder_name"), "Unknown Founder")
        grade = _safe_str(r.get("integrity_grade"), "—")

        x_scores.append(score)
        y_rels.append(rel_val)
        hover_texts.append(
            f"<b>{startup}</b> ({founder})<br/>"
            f"Overall Score: {score:.1f}/100<br/>"
            f"Reliability: {rel_val:.1f}% (Grade: {grade})<br/>"
            f"Recommendation: {rec}"
        )
        colors.append(_REC_COLORS.get(rec, "#1B9AAA"))

    fig = go.Figure(
        data=[
            go.Scatter(
                x=x_scores,
                y=y_rels,
                mode="markers+text",
                text=[_safe_str(r.get("startup_name")) for r in rows],
                textposition="top center",
                hoverinfo="text",
                hovertext=hover_texts,
                marker=dict(
                    size=12,
                    color=colors,
                    line=dict(width=1.5, color="#1A2B23"),
                ),
            )
        ]
    )
    fig.update_layout(
        title="Overall Score vs. Reliability Scatter",
        title_x=0.05,
        xaxis=dict(title="Overall Score (0-100)", range=[0, 105]),
        yaxis=dict(title="Reliability Rating % (0-100)", range=[0, 105]),
        margin=dict(t=40, b=40, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=320,
    )
    return fig


def risk_matrix_figure(rows: list[dict]) -> go.Figure:
    """Plotly 4-Quadrant Portfolio Risk Matrix Heatmap."""
    fig = go.Figure()

    # Threshold lines at X=65, Y=65
    fig.add_shape(
        type="line",
        x0=65,
        y0=0,
        x1=65,
        y1=100,
        line=dict(color="#4A5568", width=1.5, dash="dash"),
    )
    fig.add_shape(
        type="line",
        x0=0,
        y0=65,
        x1=100,
        y1=65,
        line=dict(color="#4A5568", width=1.5, dash="dash"),
    )

    # Quadrant annotations
    fig.add_annotation(
        x=82.5,
        y=82.5,
        text="<b>STRONG IC CANDIDATE</b><br/>High Score + High Reliability",
        showarrow=False,
        font=dict(size=11, color="#0B6E4F"),
    )
    fig.add_annotation(
        x=32.5,
        y=82.5,
        text="<b>EVIDENCE SOLID, DEAL WEAK</b><br/>Low Score + High Reliability",
        showarrow=False,
        font=dict(size=11, color="#B8892D"),
    )
    fig.add_annotation(
        x=82.5,
        y=32.5,
        text="<b>VERIFY BEFORE IC</b><br/>High Score + Low Reliability",
        showarrow=False,
        font=dict(size=11, color="#D97706"),
    )
    fig.add_annotation(
        x=32.5,
        y=32.5,
        text="<b>PRIMARY DATA NEEDED</b><br/>Low Score + Low Reliability",
        showarrow=False,
        font=dict(size=11, color="#9B2226"),
    )

    if rows:
        x_vals, y_vals, texts, colors = [], [], [], []
        for r in rows:
            score = _safe_float(r.get("overall_score"))
            rel = r.get("integrity_score")
            rel_val = _safe_float(rel, default=50.0) if rel is not None else 50.0
            startup = _safe_str(r.get("startup_name"), "Unknown Startup")
            quad = quadrant_label(score, rel if rel is not None else None)

            x_vals.append(score)
            y_vals.append(rel_val)
            texts.append(f"{startup}<br/>Quad: {quad}")
            colors.append(
                _REC_COLORS.get(_safe_str(r.get("recommendation")), "#1B9AAA")
            )

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="markers+text",
                text=[_safe_str(r.get("startup_name")) for r in rows],
                textposition="top center",
                hoverinfo="text",
                hovertext=texts,
                marker=dict(
                    size=14, color=colors, line=dict(width=2, color="#000")
                ),
            )
        )

    fig.update_layout(
        title="Portfolio Risk Matrix (Score vs. Reliability Quadrants)",
        title_x=0.05,
        xaxis=dict(title="Overall Score (Threshold = 65)", range=[0, 100]),
        yaxis=dict(title="Reliability Rating (Threshold = 65)", range=[0, 100]),
        margin=dict(t=50, b=40, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        showlegend=False,
    )
    return fig


# ═════════════════════════════════════════════════════════════════════════════
# Streamlit Dashboard Renderer
# ═════════════════════════════════════════════════════════════════════════════


def _load_recent_full_rows(repo: Any, limit: int = 100) -> list[dict[str, Any]]:
    """Load full stored rows, including payload_json, for analytics views."""
    rows: list[dict[str, Any]] = []
    for row in repo.recent_runs(limit=limit):
        run_id = row.get("id")
        if run_id is None:
            continue
        full_row = repo.get_run(int(run_id))
        if full_row is not None:
            rows.append(full_row)
    return rows


def render_analytics_workspace(repo: Any, key_prefix: str = "analytics") -> None:
    """Render the pilot analytics workspace from stored database rows only."""
    st.markdown("## 📈 Analytics Workspace")
    st.caption(
        "Read-only pilot analytics derived from stored runs in `founders.db`. No mock data, no new model calls."
    )

    full_rows = _load_recent_full_rows(repo, limit=100)
    if not full_rows:
        st.info(
            "No stored runs found in `founders.db`. Run intelligence on deals to populate Analytics Workspace."
        )
        return

    metrics = build_pilot_analytics_metrics(full_rows)
    st.caption(
        "Evidence coverage = source_count ÷ claim_count, capped at 100%. Signal coverage = completeness of the five stored agent result sections."
    )

    cards = [
        ("Total Runs", metrics["total_runs"]),
        ("Pass Count", metrics["pass_count"]),
        ("Observe Count", metrics["observe_count"]),
        ("Invest Count", metrics["invest_count"]),
        ("Co-Invest Count", metrics["co_invest_count"]),
        ("Average Score", f"{metrics['average_score']:.1f}"),
        ("Average Confidence", f"{metrics['average_confidence']:.2f}"),
        ("Average Trust", f"{metrics['average_trust']:.1f}"),
        ("Average Risk", f"{metrics['average_risk']:.1f}"),
        ("Average Contradictions", f"{metrics['average_contradictions']:.2f}"),
        ("Average Unsupported Claims", f"{metrics['average_unsupported_claims']:.2f}"),
        ("Evidence Coverage", f"{metrics['evidence_coverage']:.1f}%"),
        ("Signal Coverage", f"{metrics['signal_coverage']:.1f}%"),
    ]

    for start in range(0, len(cards), 4):
        cols = st.columns(min(4, len(cards) - start))
        for col, (label, value) in zip(cols, cards[start : start + 4]):
            col.metric(label, value)

    st.divider()

    st.markdown("### 📋 Live Pilot Snapshot")
    st.dataframe(
        [
            {
                "Metric": label,
                "Value": value,
            }
            for label, value in cards
        ],
        width="stretch",
        hide_index=True,
    )


def render_portfolio_dashboard(repo: Any, key_prefix: str = "portfolio") -> None:
    """Render full Portfolio Intelligence Layer dashboard."""
    st.markdown("## 📂 Portfolio Intelligence")
    st.caption(
        "Cross-deal analytical view of all intelligence runs stored in the repository."
    )

    all_rows = repo.recent_runs(limit=100)

    if not all_rows:
        st.info(
            "No stored deals found in `founders.db`. Run intelligence on deals to populate the portfolio view."
        )
        return

    # Filter controls: IC Ready Filter
    c_flt1, _ = st.columns([2, 1])
    with c_flt1:
        ic_only = st.checkbox(
            "🎯 IC Ready Only (Invest / Co-Invest + Grade A/B)",
            value=False,
            key=f"{key_prefix}_ic_only_toggle",
        )

    active_rows = ic_pipeline_filter(all_rows) if ic_only else all_rows
    kpis = aggregate_portfolio(active_rows)

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:0.75rem;margin-bottom:1rem;">',
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4, m5, m6, m7, m8 = st.columns(8)
    m1.metric("Total Deals", kpis["total_deals"])
    m2.metric("Invest Recs", kpis["invest_count"] + kpis["co_invest_count"])
    m3.metric("Observe Recs", kpis["observe_count"])
    m4.metric("Pass Recs", kpis["pass_count"])
    m5.metric("Avg Score", f"{kpis['avg_score']:.1f}")
    m6.metric(
        "Avg Reliability",
        f"{kpis['avg_reliability']:.1f}%"
        if kpis["has_reliability_data"]
        else "—",
    )
    m7.metric("Avg Confidence", f"{kpis['avg_confidence']:.2f}")
    m8.metric("Avg Thesis Match", f"{kpis['avg_thesis_match']:.1f}%")
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Visual Charts ─────────────────────────────────────────────────────────
    st.markdown("### 📊 Portfolio Distribution & Analytics")
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            recommendation_chart(active_rows),
            width="stretch",
            key=f"{key_prefix}_rec_chart",
        )
    with col2:
        st.plotly_chart(
            reliability_chart(active_rows),
            width="stretch",
            key=f"{key_prefix}_rel_chart",
        )

    col3, col4, col5 = st.columns(3)
    with col3:
        st.plotly_chart(
            sector_chart(active_rows),
            width="stretch",
            key=f"{key_prefix}_sec_chart",
        )
    with col4:
        st.plotly_chart(
            thesis_distribution_chart(active_rows),
            width="stretch",
            key=f"{key_prefix}_thesis_chart",
        )
    with col5:
        st.plotly_chart(
            score_vs_reliability_scatter(active_rows),
            width="stretch",
            key=f"{key_prefix}_scatter_chart",
        )

    st.divider()

    # ── Portfolio Risk Matrix ─────────────────────────────────────────────────
    st.markdown("### 🎯 Portfolio Risk Matrix")
    st.caption(
        "Classifies deals across overall score vs. evidence reliability into 4 decision quadrants."
    )
    st.plotly_chart(
        risk_matrix_figure(active_rows),
        width="stretch",
        key=f"{key_prefix}_risk_matrix",
    )

    st.divider()

    # ── Top 10 Deals Table ────────────────────────────────────────────────────
    st.markdown("### 🏆 Top Deals Leaderboard")
    sort_col, limit_col = st.columns([2, 1])
    with sort_col:
        sort_by_label = st.radio(
            "Rank deals by",
            options=["Score", "Reliability", "Thesis Match", "Confidence"],
            horizontal=True,
            key=f"{key_prefix}_sort_by",
        )
    with limit_col:
        top_limit = st.slider(
            "Show Top N",
            min_value=3,
            max_value=20,
            value=10,
            key=f"{key_prefix}_top_limit",
        )

    sort_mapping = {
        "Score": "score",
        "Reliability": "reliability",
        "Thesis Match": "thesis_match",
        "Confidence": "confidence",
    }
    ranked = top_deals(
        active_rows, sort_by=sort_mapping[sort_by_label], limit=top_limit
    )

    from kulima.thesis import evaluate_thesis_match

    table_data = []
    for idx, r in enumerate(ranked, 1):
        rel = r.get("integrity_score")
        rel_str = f"{rel:.1f}%" if rel is not None else "—"
        grade = _safe_str(r.get("integrity_grade"), "—")

        tm = r.get("thesis_match")
        if isinstance(tm, dict):
            tm_val = f"{_safe_float(tm.get('overall_match')):.0f}% ({tm.get('status', 'PASS')})"
        elif tm is not None and hasattr(tm, "overall_match"):
            st_str = tm.status.value if hasattr(tm.status, "value") else str(tm.status)
            tm_val = f"{tm.overall_match:.0f}% ({st_str})"
        else:
            t_res = evaluate_thesis_match(r)
            tm_val = f"{_safe_float(getattr(t_res, 'overall_match', 0.0)):.0f}% ({getattr(getattr(t_res, 'status', None), 'value', 'PASS')})"

        table_data.append(
            {
                "Rank": f"#{idx}",
                "Startup": _safe_str(r.get("startup_name")),
                "Founder": _safe_str(r.get("founder_name")),
                "Sector": _safe_str(r.get("sector")),
                "Score": f"{_safe_float(r.get('overall_score')):.1f}",
                "Reliability": f"{rel_str} ({grade})",
                "Thesis Match": tm_val,
                "Confidence": f"{_safe_float(r.get('confidence')):.2f}",
                "Recommendation": _safe_str(r.get("recommendation")),
                "Run ID": r.get("id"),
            }
        )

    st.dataframe(table_data, width="stretch")
