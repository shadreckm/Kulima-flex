"""
Kulima FLEX — AI Investment Intelligence Operating System for Africa
====================================================================
Executive dashboard + multi-agent diligence + Twin Syndicate breakthrough.
"""

from __future__ import annotations

import html
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
)
from kulima.trust_layer_ui import (
    render_reliability_badge,
    render_reliability_card,
    render_reliability_report,
    render_thesis_fit_card,
    render_trust_graph_coverage_note,
)
from kulima.trust_graph_viz import (
    render_trust_network_preview,
    render_trust_graph_explorer,
)
from kulima.compare_ui import render_comparison_selector, render_comparison_view
from kulima.portfolio_intelligence import render_portfolio_dashboard

st.set_page_config(
    page_title="Kulima FLEX VC Brain",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Viewport meta — ensures mobile browsers use device width, not 980px desktop default
st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1.0, '
    'maximum-scale=5.0">',
    unsafe_allow_html=True,
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


def render_ask_ic_panel(brief: InvestmentBrief, compact: bool = False, surface: str = "tab") -> None:
    """Shared Ask IC UI surface.

    Renders (1) grounding context badges, (2) prompt-suggestion chips,
    (3) the chat history + sticky input, and (4) a clear-history action.

    Parameters
    ----------
    brief : InvestmentBrief
        The active deal — answers are grounded strictly in this object's
        artifacts via ``answer_ask_ic_question``.
    compact : bool
        If True, suggest a shorter chip list and hide the section title /
        lead caption.  Used inside the floating right-side drawer where
        vertical space is at a premium.
    """
    from kulima.thesis import evaluate_thesis_match

    if not compact:
        st.markdown("#### 💬 Ask the Investment Committee")
        st.caption(
            "Ask follow-up diligence questions. Answers are grounded only in this generated "
            "report, evidence sources, syndicate outputs, risk analysis, and futures analysis."
        )

    # ── Grounding context row (compact badges: reliability + thesis fit) ──
    ei = brief.evidence_integrity
    tm = brief.thesis_match or evaluate_thesis_match(brief)
    ctx_html = '<div style="display:flex;flex-wrap:wrap;gap:0.35rem;margin:0.2rem 0 0.6rem 0;">'
    if ei:
        from kulima.trust_layer_ui import reliability_badge_html
        ctx_html += reliability_badge_html(ei)
    if tm:
        from kulima.models import ThesisStatus
        status_text = tm.status.value if hasattr(tm.status, "value") else str(tm.status)
        status_color_map = {
            "PASS":  "#0B6E4F", "WARN":  "#B8892D", "BLOCK": "#9B2226",
        }
        status_color = "#5B6F64"
        for k, v in status_color_map.items():
            if k.upper() in status_text.upper():
                status_color = v
                break
        ctx_html += (
            f'<span style="display:inline-flex;align-items:center;gap:0.25rem;'
            f'padding:0.18rem 0.6rem;border-radius:999px;'
            f'background:{status_color}1F;border:1px solid {status_color}4D;'
            f'font-size:0.76rem;font-weight:700;color:{status_color};'
            f'font-family:\'Source Sans 3\',sans-serif;letter-spacing:0.02em;">'
            f'🎯 Thesis Match {tm.overall_match:.0f}% · {status_text}</span>'
        )
    ctx_html += "</div>"
    st.markdown(ctx_html, unsafe_allow_html=True)

    # ── Prompt suggestion chips ────────────────────────────────────────────
    if compact:
        examples = [
            "Why invest?",
            "Biggest risks?",
            "Low reliability?",
            "Low thesis fit?",
            "What should I verify before IC?",
        ]
    else:
        examples = [
            "Why was this startup scored low?",
            "What would change the recommendation?",
            "Would you invest $25,000?",
            "What are the biggest risks?",
            "Compare this founder to similar founders.",
            "What should the founder do next?",
        ]
    if compact:
        st.caption("💡 Suggested prompts")
        chips_html = (
            '<div style="display:flex;flex-wrap:wrap;gap:0.3rem;'
            'margin:0.1rem 0 0.55rem 0;">'
        )
        for i, prompt in enumerate(examples):
            chip_id = f"ask_ic_fab_chip::%s::%d::%s" % (surface, i, _ask_ic_session_key(brief))
            btn = st.button(prompt, key=chip_id)
            if btn:
                st.session_state["ask_ic_pending_prompt"] = prompt
        chips_html += "</div>"
    else:
        st.markdown("**Suggested committee prompts**")
        cols = st.columns(3)
        for i, prompt in enumerate(examples):
            chip_id = f"ask_ic_example::%s::%d::%s" % (surface, i, _ask_ic_session_key(brief))
            if cols[i % 3].button(prompt, key=chip_id):
                st.session_state["ask_ic_pending_prompt"] = prompt

    # ── Session message state (shared key → tab + drawer share history) ────
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

    # ── Clear history (small CTA; drawer places it in header too) ──────────
    clear_key = f"ask_ic_clear_history::%s::%s" % (surface, _ask_ic_session_key(brief))
    if compact:
        if st.button("🧹 Clear", key=clear_key, help="Clear Ask IC conversation"):
            st.session_state[message_key] = st.session_state[message_key][:1]
            st.rerun()
    else:
        if st.button("Clear Ask IC history", key=clear_key):
            st.session_state[message_key] = st.session_state[message_key][:1]
            st.rerun()

    # ── Chat history scroll area + sticky input ────────────────────────────
    if compact:
        st.markdown(
            '<div class="ask-ic-drawer-scroll" style="flex:1 1 auto;min-height:0;overflow-y:auto;'
            'padding:0 0.1rem 0.5rem 0.1rem;">',
            unsafe_allow_html=True,
        )
    for message in st.session_state[message_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if compact:
        st.markdown("</div>", unsafe_allow_html=True)

    pending_prompt = st.session_state.pop("ask_ic_pending_prompt", None)
    input_key = f"ask_ic_chat_input::%s::%s" % (surface, message_key)
    if compact:
        st.markdown(
            '<div class="ask-ic-sticky-input" '
            'style="position:sticky;bottom:0;padding:0.5rem 0 0.15rem;'
            'background:inherit;border-top:1px solid rgba(0,0,0,0.06);'
            'backdrop-filter:blur(6px);">',
            unsafe_allow_html=True,
        )
    typed_prompt = st.chat_input(
        "Ask the IC analyst a follow-up question…",
        key=input_key,
    )
    if compact:
        st.markdown("</div>", unsafe_allow_html=True)

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


def render_ask_ic_tab(brief: InvestmentBrief) -> None:
    """Tab 4 — full-width Ask IC experience.  Delegates to shared panel."""
    render_ask_ic_panel(brief, compact=False, surface="tab")


def render_floating_ask_ic(brief: InvestmentBrief) -> None:
    """Render the persistent Floating Ask IC: FAB + backdrop + drawer.

    The floating experience is available from every tab.  The drawer uses
    ``render_ask_ic_panel(compact=True)`` to render a density-optimised
    chat UI.  The message history is shared with Tab 4 via the same
    ``_ask_ic_session_key()``, so questions/answers persist across
    both surfaces.
    """
    drawer_state_key = f"ask_ic_drawer_open::{_ask_ic_session_key(brief)}"
    if drawer_state_key not in st.session_state:
        st.session_state[drawer_state_key] = False

    # ── Floating Action Button (fixed bottom-right) ──────────────────────
    # Render via HTML wrapper for fixed positioning.
    # Separate widget keys (used by Streamlit widgets) from session state keys.
    fab_widget_key = f"ask_ic_fab_widget::{_ask_ic_session_key(brief)}"
    close_widget_key = f"ask_ic_close_widget::{_ask_ic_session_key(brief)}"

    # Drawer open/closed state lives in session state under a dedicated key.
    is_open = bool(st.session_state[drawer_state_key])

    # Backdrop (overlay behind drawer; click to dismiss on wide screens)
    # Note: Streamlit cannot capture clicks on HTML overlays; dismiss via
    # the explicit Close button in header. Render only for visual dim.
    bd_open = "open" if is_open else ""
    st.markdown(
        f'<div class="ask-ic-backdrop {bd_open}" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )

    # ── FAB (always rendered; z-index forces it above all tabs) ─────────
    # Use st.button wrapped in HTML wrapper.  We need to render a Streamlit
    # button for the event to fire, so we use the wrapper via markdown before
    # the button (Streamlit outputs the button into its standard column block,
    # so we style the wrapper's inner stButton via CSS).
    st.markdown(
        '<div class="ask-ic-fab-wrapper" data-fab-wrap="true">',
        unsafe_allow_html=True,
    )
    # Use the button return value to update drawer open state. Do NOT
    # write directly to the widget key in session_state.
    fab_clicked = st.button("💬 Ask IC", key=fab_widget_key)
    if fab_clicked:
        st.session_state[drawer_state_key] = True
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Drawer shell (fixed; transform slides it in when .open is set) ───
    drawer_open_class = "open" if is_open else ""
    st.markdown(
        f'<div class="ask-ic-drawer-shell {drawer_open_class}" '
        f'role="dialog" aria-modal="true" aria-label="Ask IC Analyst">',
        unsafe_allow_html=True,
    )

    # ── Drawer header (sticky top) ───────────────────────────────────────
    st.markdown(
        '<div class="ask-ic-drawer-header'>
        '<div class="ask-ic-drawer-title">💬 Ask IC Analyst</div>'
        '<div class="ask-ic-close-btn">',
        unsafe_allow_html=True,
    )
    close_clicked = st.button("✕", key=close_widget_key)
    if close_clicked:
        st.session_state[drawer_state_key] = False
    st.markdown("</div></div>", unsafe_allow_html=True)

    # ── Drawer body (flex-fill scroll) — compact chat panel ─────────────
    st.markdown('<div class="ask-ic-drawer-body">', unsafe_allow_html=True)
    if is_open:
        # Only render the Streamlit chat widgets when open to avoid wasting
        # computation + session state on a hidden surface.
        render_ask_ic_panel(brief, compact=True, surface="drawer")
    else:
        # Hidden state — emit minimal spacer so Streamlit block order stays
        # stable between renders (widget key ordering invariant).
        # Use st.empty() as a lightweight placeholder (container() does not
        # accept height/border kwargs across Streamlit versions).
        st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div><!-- /ask-ic-drawer-shell -->", unsafe_allow_html=True)


def render_brief(brief: InvestmentBrief) -> None:
    archive_meta = st.session_state.get("loaded_from_archive")
    if archive_meta:
        render_loaded_banner(
            run_id=archive_meta["run_id"],
            created_at=archive_meta["created_at"],
        )
    elif st.session_state.get("show_success_banner"):
        render_success_banner(brief)

    # ── Floating Ask IC (FAB + right-side drawer) — available on ALL tabs
    render_floating_ask_ic(brief)

    # New 6-tab structure
    tabs = st.tabs(
        [
            "📊 Executive Overview",
            "💬 Committee Debate",
            "📈 Continental Futures",
            "🤖 Ask IC Assistant",
            "📥 Reports & Memory",
            "📂 Portfolio Intelligence",
        ]
    )

    # TAB 1: Executive Overview
    with tabs[0]:
        render_dashboard_shell_open()
        render_recommendation_banner(brief)
        # Trust Layer — reliability badge inline below rec banner (gated)
        if brief.evidence_integrity:
            render_reliability_badge(brief.evidence_integrity)
        render_score_row(brief)
        # Trust Layer — reliability card below scorecard (gated)
        if brief.evidence_integrity:
            render_reliability_card(brief.evidence_integrity)

        # VC Thesis Engine — Thesis Fit Card directly below Reliability Rating
        from kulima.thesis import evaluate_thesis_match

        thesis_match = brief.thesis_match or evaluate_thesis_match(brief)
        render_thesis_fit_card(thesis_match)

        # Trust Network Preview — compact stats bar (gated on trust_graph)
        render_trust_network_preview(brief, key="trust_net_preview_tab1")

        # Charts row — flex container stacks to single column on mobile
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:0.75rem;'
            'align-items:flex-start;">',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.plotly_chart(
                radar_figure(brief), use_container_width=True, key="deal_dna_radar_overview"
            )
        with c2:
            fig = syndicate_bar(brief)
            if fig:
                st.plotly_chart(
                    fig, use_container_width=True, key="syndicate_bar_overview"
                )

            m1, m2 = st.columns(2)
            m1.metric("Growth Potential", f"{brief.growth_potential:.0f}")
            m2.metric("Investment Readiness", f"{brief.investment_readiness:.0f}")
            m3, m4 = st.columns(2)
            m3.metric("Evidence Sources", len(brief.sources))
            m4.metric("Red Flags", len(brief.red_flags))
        st.markdown("</div>", unsafe_allow_html=True)
        render_dashboard_shell_close()

        st.markdown("### Executive Summary")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.write(brief.executive_summary)
        st.markdown("</div>", unsafe_allow_html=True)

        # Detailed assessments in expanders
        with st.expander("👤 Founder Assessment", expanded=False):
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

        with st.expander("🚀 Startup Assessment", expanded=False):
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

        with st.expander("🌍 Market Assessment", expanded=False):
            st.write(brief.market_assessment)

        with st.expander("⚠️ Top Risks", expanded=True):
            if brief.red_flags:
                for rf in brief.red_flags:
                    css = (
                        f"flag-{rf.severity.lower()}"
                        if rf.severity.lower() in {"critical", "high", "medium", "low"}
                        else "flag-medium"
                    )
                    safe_sev = html.escape(rf.severity.upper())
                    safe_title = html.escape(rf.title)
                    safe_detail = html.escape(rf.detail)
                    safe_mitigation = html.escape(rf.mitigation or "TBD")
                    st.markdown(
                        f"<div class='{css}'><strong>{safe_sev}: {safe_title}</strong><br/>"
                        f"{safe_detail}<br/><em>Mitigation: {safe_mitigation}</em></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.success("No critical red flags surfaced from open-source intelligence.")

        with st.expander("📄 Full Risk Assessment Narrative", expanded=False):
            st.write(brief.risk_assessment)

        with st.expander("📝 Investment Recommendation", expanded=True):
            st.write(brief.investment_recommendation)
            st.markdown("#### Next Steps")
            for i, step in enumerate(brief.next_steps, 1):
                st.markdown(f"{i}. {step}")

        with st.expander("🕸️ Trust Graph Explorer", expanded=False):
            render_trust_graph_explorer(brief, key_prefix="tge_tab1")

        with st.expander("🔬 Full Reliability Report", expanded=False):
            # Trust Layer — full Layer 3 analyst view (gated)
            if brief.evidence_integrity:
                render_reliability_report(brief.evidence_integrity)
            else:
                st.caption("Evidence Integrity Engine not run for this analysis.")

        with st.expander("📚 Source Attribution", expanded=False):
            if not brief.sources:
                st.caption("No sources were captured for this analysis.")
            else:
                for i, src in enumerate(brief.sources, 1):
                    st.markdown(f"**[{i}] {src.title}**")
                    src_type = getattr(src, "source_type", "web")
                    conf = getattr(src, "confidence_score", 0.0)
                    st.caption(
                        f"Type: {src_type} · "
                        f"Relevance: {src.relevance:.2f} · "
                        f"Confidence: {conf:.2f}"
                    )
                    st.write(src.snippet)
                    st.markdown(f"🔗 [Open source]({src.url})")
                    if i < len(brief.sources):
                        st.divider()

        with st.expander("🔍 Explainable AI Decisions", expanded=False):
            for reason in brief.explainability:
                st.markdown(f"- {reason}")

    # TAB 2: Committee Debate
    with tabs[1]:
        render_twin_syndicate_committee(brief, key_suffix="_debate")

    # TAB 3: Continental Futures
    with tabs[2]:
        render_continental_futures_simulator(brief, key_suffix="_futures")

    # TAB 4: Ask IC Assistant
    with tabs[3]:
        render_ask_ic_tab(brief)

    # TAB 5: Reports & Memory
    with tabs[4]:
        st.markdown("### Export Reports")
        st.markdown("Download IC-ready documents in multiple formats.")
        render_export_buttons(brief, key_prefix="reports_tab")

        st.divider()
        st.markdown("### Founder Memory")
        st.caption("Load and review previous intelligence runs.")
        history = repo.recent_runs(20)
        selected_run_id = render_history_panel(history)

        if selected_run_id is not None:
            if selected_run_id != st.session_state.get("loaded_run_id"):
                loaded_brief = repo.load_brief(selected_run_id)
                if loaded_brief is not None:
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

    # TAB 6: Portfolio Intelligence
    with tabs[5]:
        render_portfolio_dashboard(repo, key_prefix="brief_portfolio")


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
    render_portfolio_dashboard(repo, key_prefix="empty_portfolio")
