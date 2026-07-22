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
from kulima.ask_ic import answer_ask_ic_question
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
    render_history_panel,
    render_loaded_banner,
    render_recommendation_banner,
    render_score_row,
    render_success_banner,
    render_twin_syndicate_committee,
    syndicate_bar,
    trust_graph_table,
)
from kulima.compare_ui import render_comparison_selector, render_comparison_view

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
    founder = st.text_input(
        "Founder Name",
        placeholder="e.g. Iyinoluwa Aboyeji",
        key="deal_intake_founder_name",
    )
    startup = st.text_input(
        "Startup Name",
        placeholder="e.g. Flutterwave / Andela",
        key="deal_intake_startup_name",
    )
    st.caption("Africa-first OSINT · Multi-agent IC · Twin Syndicate · Futures")
    run = st.button(
        "▶ Run Full Intelligence",
        type="primary",
        use_container_width=True,
        key="run_full_intelligence",
    )
    st.divider()
    st.markdown("### System Status")
    st.write(f"Model · `{settings.openai_model}`")
    st.write(f"Syndicate · `{SYNDICATE_MODEL}`")
    st.write(f"Futures · `{FUTURES_MODEL}`")
    st.markdown("**Agents online**")
    st.write("Founder · Startup · Diligence · Risk · Memo")
    access = settings.pilot_access_summary()
    st.markdown("**Pilot access**")
    st.caption(
        f"Mode `{settings.access_mode}` · Guest {access['guest_daily_limit']}/day · "
        f"Analyst {access['analyst_daily_limit']}/day · Investor {access['investor_daily_limit']}/day"
    )
    missing = settings.missing_required_secrets()
    if missing:
        st.error(f"Missing secrets: {', '.join(missing)}")
    else:
        st.success("API credentials loaded")



def _ask_ic_session_key(brief: InvestmentBrief) -> str:
    return (
        "ask_ic_messages::"
        f"{brief.founder_name}::{brief.startup_name}::"
        f"{brief.overall_score:.0f}::{brief.recommendation.value}"
    )


def render_ask_ic_tab(brief: InvestmentBrief) -> None:
    st.markdown("#### 💬 Ask the Investment Committee")
    st.caption(
        "Ask follow-up diligence questions. Answers are grounded only in this generated "
        "report, evidence sources, syndicate outputs, risk analysis, and futures analysis."
    )

    examples = [
        "Why was this startup scored low?",
        "What would change the recommendation?",
        "Would you invest $25,000?",
        "What are the biggest risks?",
        "Compare this founder to similar founders.",
        "What should the founder do next?",
    ]
    st.markdown("**Suggested committee prompts**")
    chips = st.columns(3)
    for i, prompt in enumerate(examples):
        if chips[i % 3].button(prompt, key=f"ask_ic_example_{i}"):
            st.session_state["ask_ic_pending_prompt"] = prompt

    message_key = _ask_ic_session_key(brief)
    if message_key not in st.session_state:
        st.session_state[message_key] = [
            {
                "role": "assistant",
                "content": (
                    "I’m ready to answer as the IC analyst. I will stay inside the "
                    "generated memo, evidence, syndicate votes, risk analysis, and "
                    "futures scenarios, and I’ll cite those artifacts whenever possible."
                ),
            }
        ]

    if st.button("Clear Ask IC history", key="ask_ic_clear_history"):
        st.session_state[message_key] = st.session_state[message_key][:1]
        st.rerun()

    for message in st.session_state[message_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending_prompt = st.session_state.pop("ask_ic_pending_prompt", None)
    typed_prompt = st.chat_input(
        "Ask the IC analyst a follow-up question…",
        key=f"ask_ic_chat_input_{message_key}",
    )
    question = pending_prompt or typed_prompt
    if question:
        st.session_state[message_key].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Consulting the generated IC context…"):
                response = answer_ask_ic_question(
                    brief,
                    question,
                    history=st.session_state[message_key][:-1],
                )
            st.markdown(response)
        st.session_state[message_key].append({"role": "assistant", "content": response})


def render_brief(brief: InvestmentBrief) -> None:
    archive_meta = st.session_state.get("loaded_from_archive")
    if archive_meta:
        render_loaded_banner(
            run_id=archive_meta["run_id"],
            created_at=archive_meta["created_at"],
        )
    elif st.session_state.get("show_success_banner"):
        render_success_banner(brief)

    render_dashboard_shell_open()
    render_recommendation_banner(brief)
    render_score_row(brief)

    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.plotly_chart(
            radar_figure(brief), use_container_width=True, key="deal_dna_radar_main"
        )
    with c2:
        fig = syndicate_bar(brief)
        if fig:
            st.plotly_chart(
                fig, use_container_width=True, key="syndicate_bar_dashboard"
            )

        m1, m2 = st.columns(2)
        m1.metric("Growth Potential", f"{brief.growth_potential:.0f}")
        m2.metric("Investment Readiness", f"{brief.investment_readiness:.0f}")
        m3, m4 = st.columns(2)
        m3.metric("Evidence Sources", len(brief.sources))
        m4.metric("Red Flags", len(brief.red_flags))
    render_dashboard_shell_close()

    render_twin_syndicate_committee(brief, key_suffix="_main")
    render_continental_futures_simulator(brief, key_suffix="_main")
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
            "💬 Ask IC",
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
                st.progress(
                    min(s.score / 100, 1.0), text=f"{s.name}: {s.score:.0f}/100"
                )

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
        render_continental_futures_simulator(brief, key_suffix="_tab")

    with tabs[7]:
        st.markdown("#### Trust Graph")
        if brief.trust_graph:
            st.write(brief.trust_graph.explanation)
            df = trust_graph_table(brief)
            if df is not None:
                st.dataframe(
                    df, use_container_width=True, key="trust_graph_nodes_table"
                )
            st.caption(
                f"Nodes: {len(brief.trust_graph.nodes)} · "
                f"Edges: {len(brief.trust_graph.edges)} · "
                f"Density: {brief.trust_graph.density:.2f}"
            )

    with tabs[8]:
        st.markdown("#### Source Attribution")
        for i, src in enumerate(brief.sources, 1):
            with st.expander(f"[{i}] {src.title}", expanded=i <= 3):
                st.write(src.snippet)
                st.markdown(f"[Open source]({src.url})")
                st.caption(
                    f"Relevance: {src.relevance:.2f} · Confidence: {getattr(src, 'confidence_score', 0.0):.2f} · Type: {getattr(src, 'source_type', 'web')}"
                )

    with tabs[9]:
        st.markdown("#### Explainable AI Decisions")
        for reason in brief.explainability:
            st.markdown(f"- {reason}")


    with tabs[10]:
        render_ask_ic_tab(brief)


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

        with st.status(
            "Running multi-agent Investment Intelligence OS…", expanded=True
        ) as status:
            try:
                orchestrator = IntelligenceOrchestrator()
                brief = orchestrator.analyze(founder, startup, on_progress=on_progress)
                repo.save_brief(brief)
                st.session_state["latest_brief"] = brief
                st.session_state["show_success_banner"] = True
                # Clear any previously loaded archive state so the live-run
                # success banner takes precedence on the next render.
                st.session_state["loaded_from_archive"] = None
                st.session_state["loaded_run_id"] = None
                status.update(
                    label="Intelligence complete — IC pack ready", state="complete"
                )
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

                progress_bar.progress(
                    0.0, text=f"Pipeline failed — {exc_type}{stage_info}"
                )
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
                        traceback.format_exception(
                            type(cause), cause, cause.__traceback__
                        )
                    )
                    with st.expander(
                        f"🔗 Root Cause — `{type(cause).__name__}`", expanded=False
                    ):
                        st.code(cause_tb, language="python")
if "latest_brief" in st.session_state:
    render_brief(st.session_state["latest_brief"])
else:
    render_empty_state()

st.divider()
st.markdown("### Founder Memory")
history = repo.recent_runs(20)

selected_run_id = render_history_panel(history)

if selected_run_id is not None:
    # Guard: skip if this run is already loaded — prevents an infinite rerun
    # loop when Streamlit re-evaluates the page after st.rerun().
    if selected_run_id != st.session_state.get("loaded_run_id"):
        loaded_brief = repo.load_brief(selected_run_id)
        if loaded_brief is not None:
            # Locate the matching row so we can surface the original timestamp.
            matching_rows = [r for r in history if int(r["id"]) == selected_run_id]
            created_at = matching_rows[0]["created_at"] if matching_rows else ""

            st.session_state["latest_brief"] = loaded_brief
            st.session_state["loaded_from_archive"] = {
                "run_id": selected_run_id,
                "created_at": created_at,
            }
            st.session_state["loaded_run_id"] = selected_run_id
            st.session_state["show_success_banner"] = False
            st.toast(
                f"Loaded run #{selected_run_id} · "
                f"{loaded_brief.recommendation.value} · "
                f"{loaded_brief.overall_score:.0f}/100",
                icon="📂",
            )
            st.rerun()
        else:
            st.error(
                f"Run #{selected_run_id} could not be restored — "
                "the stored data may be from an older schema version.",
                icon="⚠️",
            )

st.divider()
with st.expander("⚖️ Compare Two Deals", expanded=False):
    try:
        compare_id_a, compare_id_b = render_comparison_selector(history)
        if compare_id_a is not None and compare_id_b is not None:
            brief_a = repo.load_brief(compare_id_a)
            brief_b = repo.load_brief(compare_id_b)
            if brief_a is None:
                st.error(f"Run #{compare_id_a} could not be loaded.", icon="⚠️")
            elif brief_b is None:
                st.error(f"Run #{compare_id_b} could not be loaded.", icon="⚠️")
            else:
                render_comparison_view(brief_a, brief_b, compare_id_a, compare_id_b)
    except Exception as _cmp_exc:
        st.error(
            f"Deal comparison unavailable — {type(_cmp_exc).__name__}: {_cmp_exc}",
            icon="⚠️",
        )
