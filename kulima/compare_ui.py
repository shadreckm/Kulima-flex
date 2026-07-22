"""MVP Deal Comparison UI — selector, score table, dual radar, winner line.

Exports two public functions:
- ``render_comparison_selector`` — two selectboxes + Compare button
- ``render_comparison_view``     — score table + dual radar + winner line

Does NOT import from kulima.agents, kulima.llm, kulima.research, or kulima.db.
Does NOT write to st.session_state.
Does NOT call st.rerun().
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from kulima.comparison import build_comparison_rows, build_winner_line
from kulima.models import InvestmentBrief
from kulima.ui import REC_COLORS, radar_figure_dual

# ── Widget keys — globally unique across the whole app ────────────────────────
# Confirmed non-colliding with: history_panel_editor, load_selected_run_btn,
# deal_dna_radar_main, syndicate_bar_dashboard, trust_graph_nodes_table,
# deal_intake_founder_name, deal_intake_startup_name, run_full_intelligence,
# ask_ic_clear_history, founder_memory_history
_KEY_SEL_A = "cmp_selectbox_a"
_KEY_SEL_B = "cmp_selectbox_b"
_KEY_BTN = "cmp_compare_btn"
_KEY_RADAR = "cmp_radar_chart"
_KEY_TABLE = "cmp_score_table"


# ── Public functions ──────────────────────────────────────────────────────────

def render_comparison_selector(history: list[dict]) -> tuple[int | None, int | None]:
    """Render the deal-selector row and Compare button.

    Returns ``(run_id_a, run_id_b)`` when the Compare button is clicked and
    two *different* runs are selected.  Returns ``(None, None)`` in all other
    cases (button not pressed, same run selected for both, fewer than 2 runs).
    """
    if len(history) < 2:
        st.info(
            "Run at least two intelligence analyses to unlock Deal Comparison.",
            icon="ℹ️",
        )
        return None, None

    # Build parallel option-string and ID lists — same index order.
    options: list[str] = []
    ids: list[int] = []
    for r in history:
        rec = r.get("recommendation") or "—"
        score = float(r.get("overall_score") or 0)
        label = (
            f"#{r['id']} · {r.get('founder_name', '—')} / "
            f"{r.get('startup_name', '—')} ({rec}, {score:.0f})"
        )
        options.append(label)
        ids.append(int(r["id"]))

    c1, c2 = st.columns(2)
    sel_a = c1.selectbox(
        "Deal A",
        options,
        index=0,
        key=_KEY_SEL_A,
        help="Select the first deal",
    )
    sel_b = c2.selectbox(
        "Deal B",
        options,
        index=min(1, len(options) - 1),
        key=_KEY_SEL_B,
        help="Select the second deal",
    )

    clicked = st.button(
        "⚖️ Compare Deals",
        key=_KEY_BTN,
        help="Load both runs and render side-by-side comparison",
    )
    if not clicked:
        return None, None

    id_a = ids[options.index(sel_a)]
    id_b = ids[options.index(sel_b)]

    if id_a == id_b:
        st.warning("Select two different deals to compare.", icon="☝️")
        return None, None

    return id_a, id_b


def render_comparison_view(
    brief_a: InvestmentBrief,
    brief_b: InvestmentBrief,
    run_id_a: int,
    run_id_b: int,
) -> None:
    """Render the full MVP comparison: dual radar + score table + winner line.

    Accepts transient ``InvestmentBrief`` objects — does NOT store them in
    session state.  All data is read once and discarded after render.
    """
    st.markdown("---")
    st.markdown("## ⚖️ Deal Comparison")
    st.caption(
        f"Run #{run_id_a} ({brief_a.founder_name} / {brief_a.startup_name})  "
        f"vs  Run #{run_id_b} ({brief_b.founder_name} / {brief_b.startup_name})  "
        f"· No agents were re-run · Scores loaded from archive"
    )

    # ── Header strip ──────────────────────────────────────────────────────────
    h1, hmid, h2 = st.columns([2, 0.5, 2])

    def _rec_color(brief: InvestmentBrief) -> str:
        return REC_COLORS.get(brief.recommendation, "#0B3D2E")

    with h1:
        st.markdown(
            f"""
            <div style="background:{_rec_color(brief_a)};color:white;
                border-radius:14px;padding:0.75rem 1rem;text-align:center;">
                <div style="font-size:0.75rem;opacity:0.85;margin-bottom:0.2rem;">
                    Deal A · Run #{run_id_a}
                </div>
                <div style="font-family:Fraunces,Georgia,serif;font-size:1.2rem;font-weight:700;">
                    {brief_a.founder_name} / {brief_a.startup_name}
                </div>
                <div style="font-size:1rem;margin-top:0.25rem;">
                    {brief_a.recommendation.value} · {brief_a.overall_score:.0f}/100
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hmid:
        st.markdown(
            "<div style='text-align:center;padding-top:1.4rem;"
            "font-size:1.15rem;color:#5B6F64;font-weight:700;'>vs</div>",
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            f"""
            <div style="background:{_rec_color(brief_b)};color:white;
                border-radius:14px;padding:0.75rem 1rem;text-align:center;">
                <div style="font-size:0.75rem;opacity:0.85;margin-bottom:0.2rem;">
                    Deal B · Run #{run_id_b}
                </div>
                <div style="font-family:Fraunces,Georgia,serif;font-size:1.2rem;font-weight:700;">
                    {brief_b.founder_name} / {brief_b.startup_name}
                </div>
                <div style="font-size:1rem;margin-top:0.25rem;">
                    {brief_b.recommendation.value} · {brief_b.overall_score:.0f}/100
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

    # ── Dual radar chart ──────────────────────────────────────────────────────
    label_a = f"A: {brief_a.founder_name}"
    label_b = f"B: {brief_b.founder_name}"
    fig = radar_figure_dual(brief_a, brief_b, label_a, label_b)
    st.plotly_chart(fig, use_container_width=True, key=_KEY_RADAR)

    # ── Score comparison table ────────────────────────────────────────────────
    st.markdown("#### Score Comparison")
    rows = build_comparison_rows(brief_a, brief_b)
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        key=_KEY_TABLE,
        column_config={
            "Dimension":  st.column_config.TextColumn("Dimension", width="medium"),
            "Deal A":     st.column_config.TextColumn(f"A: {brief_a.founder_name[:14]}", width="small"),
            "Deal B":     st.column_config.TextColumn(f"B: {brief_b.founder_name[:14]}", width="small"),
            "\u0394":     st.column_config.TextColumn("Δ", width="small"),
            "Winner":     st.column_config.TextColumn("Winner", width="small"),
        },
    )

    # ── One-line winner summary ───────────────────────────────────────────────
    winner_line = build_winner_line(brief_a, brief_b, rows)
    st.info(winner_line, icon="⚖️")
