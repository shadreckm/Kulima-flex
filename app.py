"""
Kulima FLEX — AI Investment Intelligence Operating System for Africa
====================================================================
Executive dashboard + multi-agent diligence + Twin Syndicate breakthrough.
"""

from __future__ import annotations

import logging
import traceback

import streamlit as st

# Configure root logger — writes to stderr / Streamlit server logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from kulima.agents.orchestrator import IntelligenceOrchestrator
from kulima.config import FUTURES_MODEL, SYNDICATE_MODEL, get_settings
from kulima.db import IntelligenceRepository
from kulima.export import render_export_buttons
from kulima.models import InvestmentBrief
from kulima.ui import (
    history_frame,
    inject_styles,
    radar_figure,
    render_continental_futures_simulator,
    render_dashboard_shell_close,
    render_dashboard_shell_open,
    render_empty_state,
    render_hero,
    render_recommendation_banner,
    render_score_row,
    render_success_banner,
    render_twin_syndicate_committee,
    syndicate_bar,
    trust_graph_table,
)

st.set_page_config(
    page_title="Kulima FLEX | Investment Intelligence OS",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()
render_hero()

settings = get_settings()
repo = IntelligenceRepository()

with st.sidebar:
    st.markdown("### Deal Intake")
    founder = st.text_input("Founder Name", placeholder="e.g. Iyinoluwa Aboyeji")
    startup = st.text_input("Startup Name", placeholder="e.g. Flutterwave / Andela")
    st.caption("Africa-first OSINT · Multi-agent IC · Twin Syndicate · Futures")
    run = st.button("▶ Run Full Intelligence", type="primary", use_container_width=True)
    st.divider()
    st.markdown("### System Status")
    st.write(f"Model · `{settings.openai_model}`")
    st.write(f"Syndicate · `{SYNDICATE_MODEL}`")
    st.write(f"Futures · `{FUTURES_MODEL}`")
    st.markdown("**Agents online**")
    st.write("Founder · Startup · Diligence · Risk · Memo")
    missing = []
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.tavily_api_key:
        missing.append("TAVILY_API_KEY")
    if missing:
        st.error(f"Missing secrets: {', '.join(missing)}")
    else:
        st.success("API credentials loaded")


def render_brief(brief: InvestmentBrief) -> None:
    if st.session_state.get("show_success_banner"):
        render_success_banner(brief)

    render_dashboard_shell_open()
    render_recommendation_banner(brief)
    render_score_row(brief)

    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.plotly_chart(radar_figure(brief), use_container_width=True)
    with c2:
        fig = syndicate_bar(brief)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        m1, m2 = st.columns(2)
        m1.metric("Growth Potential", f"{brief.growth_potential:.0f}")
        m2.metric("Investment Readiness", f"{brief.investment_readiness:.0f}")
        m3, m4 = st.columns(2)
        m3.metric("Evidence Sources", len(brief.sources))
        m4.metric("Red Flags", len(brief.red_flags))
    render_dashboard_shell_close()

    render_twin_syndicate_committee(brief, key_suffix="_main")
    render_continental_futures_simulator(brief)
    render_export_buttons(brief, key_prefix="main")

    st.markdown("### Executive Summary")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.write(brief.executive_summary)
    st.markdown("</div>", unsafe_allow_html=True)

    tabs = st.tabs(
        [
            "Founder",
            "Startup",
            "Market",
            "Risk & Flags",
            "IC Memo",
            "Twin Syndicate",
            "Futures",
            "Trust Graph",
            "Sources",
            "Explainability",
        ]
    )

    with tabs[0]:
        st.markdown("#### Founder Assessment")
        st.write(brief.founder_assessment)
        fr = brief.agent_results.get("founder")
        if fr:
            for s in fr.scores:
                st.progress(
                    min(s.score / 100, 1.0),
                    text=f"{s.name}: {s.score:.0f}/100 — {s.rationale}",
                )
            for f in fr.findings:
                st.markdown(f"- {f}")

    with tabs[1]:
        st.markdown("#### Startup Assessment")
        st.write(brief.startup_assessment)
        meta = brief.agent_results.get("startup")
        if meta:
            st.caption(
                f"Sector: {brief.sector or '—'} · Geography: {brief.geography or '—'} · "
                f"Stage: {brief.stage or '—'}"
            )
            for s in meta.scores:
                st.progress(min(s.score / 100, 1.0), text=f"{s.name}: {s.score:.0f}/100")

    with tabs[2]:
        st.markdown("#### Market Assessment")
        st.write(brief.market_assessment)
        g1, g2 = st.columns(2)
        g1.metric("Growth Potential", f"{brief.growth_potential:.0f}/100")
        g2.metric("Investment Readiness", f"{brief.investment_readiness:.0f}/100")

    with tabs[3]:
        st.markdown("#### Risk Assessment")
        st.write(brief.risk_assessment)
        if brief.red_flags:
            st.markdown("##### Red Flag Alerts")
            for rf in brief.red_flags:
                css = (
                    f"flag-{rf.severity.lower()}"
                    if rf.severity.lower() in {"critical", "high", "medium", "low"}
                    else "flag-medium"
                )
                st.markdown(
                    f"<div class='{css}'><strong>{rf.severity.upper()}: {rf.title}</strong><br/>"
                    f"{rf.detail}<br/><em>Mitigation: {rf.mitigation or 'TBD'}</em></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.success("No critical red flags surfaced from open-source intelligence.")

    with tabs[4]:
        st.markdown("#### Investment Recommendation")
        st.write(brief.investment_recommendation)
        st.markdown("#### Next Steps")
        for i, step in enumerate(brief.next_steps, 1):
            st.markdown(f"{i}. {step}")
        render_export_buttons(brief, key_prefix="memo_tab")

    with tabs[5]:
        render_twin_syndicate_committee(brief, key_suffix="_tab")

    with tabs[6]:
        render_continental_futures_simulator(brief)

    with tabs[7]:
        st.markdown("#### Trust Graph")
        if brief.trust_graph:
            st.write(brief.trust_graph.explanation)
            df = trust_graph_table(brief)
            if df is not None:
                st.dataframe(df, use_container_width=True)
            st.caption(
                f"Nodes: {len(brief.trust_graph.nodes)} · "
                f"Edges: {len(brief.trust_graph.edges)} · "
                f"Density: {brief.trust_graph.density:.2f}"
            )

    with tabs[8]:
        st.markdown("#### Source Attribution")
        for i, src in enumerate(brief.sources, 1):
            with st.expander(f"[{i}] {src.title}"):
                st.write(src.snippet)
                st.markdown(f"[Open source]({src.url})")
                st.caption(f"Relevance: {src.relevance:.2f}")

    with tabs[9]:
        st.markdown("#### Explainable AI Decisions")
        for reason in brief.explainability:
            st.markdown(f"- {reason}")


if run:
    if not founder.strip():
        st.warning("Enter a founder name to begin intelligence.")
    elif missing:
        st.error("Configure API keys in `.env` before running.")
    else:
        progress_bar = st.progress(0, text="Warming up Investment Intelligence OS…")
        status_box = st.empty()
        status_box.markdown(
            """
            <div class="pipeline-card">
              <div class="pipeline-step"><span class="pipeline-dot"></span> Connecting agents…</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def on_progress(pct: float, message: str) -> None:
            progress_bar.progress(min(max(pct, 0.0), 1.0), text=message)
            status_box.markdown(
                f"""
                <div class="pipeline-card">
                  <div class="pipeline-step">
                    <span class="pipeline-dot"></span>
                    <span><b>{int(pct * 100)}%</b> — {message}</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.status("Running multi-agent Investment Intelligence OS…", expanded=True) as status:
            try:
                orchestrator = IntelligenceOrchestrator()
                brief = orchestrator.analyze(founder, startup, on_progress=on_progress)
                repo.save_brief(brief)
                st.session_state["latest_brief"] = brief
                st.session_state["show_success_banner"] = True
                status.update(label="Intelligence complete — IC pack ready", state="complete")
                progress_bar.progress(1.0, text="Intelligence complete — IC pack ready")
                st.toast(
                    f"IC pack ready · {brief.recommendation.value} · {brief.overall_score:.0f}/100",
                    icon="✅",
                )
                st.balloons()
                st.success(
                    f"**Analysis complete.** Recommendation: **{brief.recommendation.value}** · "
                    f"Overall score **{brief.overall_score:.0f}/100** · "
                    f"{len(brief.sources)} sources · {len(brief.red_flags)} red flags"
                )
            except Exception as e:
                # Collect full diagnostics
                exc_type = type(e).__name__
                exc_module = type(e).__module__
                tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
                full_tb = "".join(tb_lines)

                # Stage label from PipelineStageError if available
                stage_label = getattr(e, "stage", None)
                stage_info = f" in **{stage_label}**" if stage_label else ""

                # Log everything to server stderr
                logging.error(
                    f"Pipeline failure{(' in stage: ' + stage_label) if stage_label else ''}: "
                    f"{exc_type}: {e}\n{full_tb}"
                )

                progress_bar.progress(0.0, text=f"Pipeline failed — {exc_type}{stage_info}")
                status.update(
                    label=f"Pipeline failed — {exc_type}{stage_info}",
                    state="error",
                )

                st.error(
                    f"### 🚨 Pipeline Failure{stage_info}\n\n"
                    f"**Exception type:** `{exc_module}.{exc_type}`  \n"
                    f"**Message:** {e}"
                )
                with st.expander("📋 Full Traceback (click to expand)", expanded=False):
                    st.code(full_tb, language="python")

                # Surface cause chain if present
                cause = getattr(e, "cause", None) or getattr(e, "__cause__", None)
                if cause and cause is not e:
                    cause_tb = "".join(
                        traceback.format_exception(type(cause), cause, cause.__traceback__)
                    )
                    with st.expander(f"🔗 Root Cause — `{type(cause).__name__}`", expanded=False):
                        st.code(cause_tb, language="python")
if "latest_brief" in st.session_state:
    render_brief(st.session_state["latest_brief"])
else:
    render_empty_state()

st.divider()
st.markdown("### Founder Memory")
history = repo.recent_runs(20)
df = history_frame(history)
if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.caption("No intelligence runs stored yet — run your first deal above.")
