"""
Kulima FLEX — AI Investment Intelligence Operating System for Africa
====================================================================
Executive dashboard + multi-agent diligence + Twin Syndicate breakthrough.
"""

from __future__ import annotations

import html
import logging
import traceback
import textwrap
import time

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
    render_evidence_workspace,
    render_hero,
    render_history_panel,
    render_loaded_banner,
    render_recommendation_banner,
    render_reports_workspace,
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
from kulima.portfolio_intelligence import (
    render_analytics_workspace,
    render_portfolio_dashboard,
)

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

# Feature flags for UI-only surfaces
ENABLE_VOICE_INPUT = False  # Keep voice code but hide from main UX

with st.sidebar:
    st.markdown("### Deal Intake")
    pilot_user = st.text_input(
        "Pilot User",
        placeholder="Your name or team",
        key="pilot_user_name",
    )
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
        width="stretch",
        key="run_full_intelligence",
    )

    st.divider()
    # Workspace mode selector — controls Portfolio, Analytics, History, Exports, Comparisons
    workspace_view = st.selectbox(
        "WORKSPACE ▾",
        [
            "Decision Mode",
            "Evidence",
            "Reports",
            "Portfolio",
            "Analytics",
            "History",
            "Exports",
            "Comparisons",
            "Signals",
        ],
        index=0,
        key="workspace_view",
    )



def _ask_ic_session_key(brief: InvestmentBrief) -> str:
    return (
        "ask_ic_messages::"
        f"{brief.founder_name}::{brief.startup_name}::"
        f"{brief.overall_score:.0f}::{brief.recommendation.value}"
    )


def render_ask_ic_panel(brief: InvestmentBrief, compact: bool = False, surface: str = "tab") -> None:
    """Shared Ask IC UI surface — Chat Shell V2.

    Layout (top → bottom):
      1. Chat header   — persona name · context badge · Clear button
      2. Suggestions   — collapsed expander (💡)
      3. Message history — scrolls with page
      4. Composer area — attached-file pills + file uploader + st.chat_input

    Backend and session-state contracts unchanged.
    Document ingestion preserved.
    """
    # ── Session message state ──────────────────────────────────────────────
    message_key = _ask_ic_session_key(brief)
    if message_key not in st.session_state:
        rec = getattr(brief, "recommendation", None)
        rec_text = rec.value if rec is not None else "Not available"
        conf_level = getattr(brief, "confidence_level", None)
        conf_label = getattr(conf_level, "value",
                             str(conf_level) if conf_level is not None else "Not available")
        conf_num = getattr(brief, "confidence", None)

        ei = getattr(brief, "evidence_integrity", None)
        ei_text = (
            f"Grade {getattr(ei.integrity_grade, 'value', ei.integrity_grade)} "
            f"({ei.integrity_score:.0f}/100)"
            if ei is not None else "Not available"
        )

        syn = getattr(brief, "syndicate", None)
        if syn is not None:
            final = syn.final_recommendation or syn.majority_vote
            final_text = final.value if final is not None else "Not available"
            consensus = syn.consensus_score or syn.average_score
            dissent = (syn.dissent_score if syn.dissent_score is not None
                       else syn.dissent_index * 100)
            committee_line = (
                f"{final_text} · Consensus {consensus:.0f}/100 · Dissent {dissent:.0f}/100"
            )
        else:
            committee_line = "Not available (syndicate not run)."

        intro = (
            "Your investment brief is ready.\n\n"
            f"Recommendation: {rec_text}\n"
            f"Confidence: {conf_label}"
            f"{f' ({conf_num:.2f})' if isinstance(conf_num, (int, float)) else ''}\n"
            f"Evidence Reliability: {ei_text}\n"
            f"Committee Position: {committee_line}\n\n"
            "What would you like to know?"
        )
        st.session_state[message_key] = [{"role": "assistant", "content": intro}]

    # ── Chat shell wrapper — supports sticky composer and scrollable history
    st.markdown('<div class="kulima-chat-shell">', unsafe_allow_html=True)

    # ── 1. Chat header — persona · badge · Clear ───────────────────────────
    rec_val = getattr(getattr(brief, "recommendation", None), "value", "—")
    hdr_col, _, clr_col = st.columns([5, 1, 1])
    with hdr_col:
        st.markdown(
            f'<div class="kulima-chat-header" style="border-bottom:none;margin-bottom:0;">'
            f'<span class="kulima-chat-persona">IC Analyst</span>'
            f'<span class="kulima-chat-badge">{html.escape(rec_val)} · '
            f'{brief.overall_score:.0f}/100</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with clr_col:
        st.markdown('<div class="kulima-chat-clear">', unsafe_allow_html=True)
        if st.button("Clear", key=f"ic_clear_{message_key}"):
            st.session_state[message_key] = st.session_state[message_key][:1]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<hr style="margin:0.3rem 0 0.55rem;border:none;'
        'border-top:1px solid rgba(11,61,46,0.10);">',
        unsafe_allow_html=True,
    )

    # ── 2. Suggested Questions — collapsed ────────────────────────────────
    _IC_SUGGESTIONS = [
        "Should I invest in this startup?",
        "What are the top 3 risks?",
        "What evidence is weak?",
        "What would make this a pass?",
        "What should I verify before a term sheet?",
        "Summarize this deal for investment committee.",
    ]
    st.markdown('<div class="kulima-suggestions-expander">', unsafe_allow_html=True)
    with st.expander("💡 Suggested questions", expanded=False):
        for _s in _IC_SUGGESTIONS:
            if st.button(_s, key=f"ic_sugg_{message_key}_{_s[:18]}", use_container_width=True):
                st.session_state[f"ic_pending_{message_key}"] = _s
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 3. Message history ────────────────────────────────────────────────
    st.markdown('<div class="kulima-chat-history">', unsafe_allow_html=True)
    for message in st.session_state[message_key]:
        logging.debug("render_ask_ic_panel: %s", repr(message.get("content"))[:120])
        _content = message.get("content")
        if not isinstance(_content, str):
            try:
                _content = __import__("json").dumps(_content, ensure_ascii=False, indent=2)
            except Exception:
                _content = str(_content)
        with st.chat_message(message["role"]):
            st.markdown(_content)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 4. Composer area — attached pills + uploader + st.chat_input ─────
    st.markdown('<div class="kulima-composer-wrapper">', unsafe_allow_html=True)
    attach_key = f"ask_ic_attachments::{message_key}"

    # File uploader — lives directly in the composer, no expander
    st.markdown('<div class="kulima-composer-meta">', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "📎 Attach documents (optional)",
        type=["pdf", "docx", "txt", "csv", "xlsx", "pptx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=attach_key,
        help="Attach pitch decks, financials, or diligence files. "
             "They'll be referenced in your next message.",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Attached file pills — shown above chat_input when files are present
    _current_files = uploaded_files or st.session_state.get(attach_key) or []
    if _current_files:
        pills_html = '<div class="kulima-attach-list">' + "".join(
            f'<span class="kulima-attach-pill">'
            f'{html.escape(getattr(f, "name", "attachment")[:32])}'
            f'</span>'
            for f in _current_files[:8]
        ) + "</div>"
        st.markdown(pills_html, unsafe_allow_html=True)

        # Ingest and persist as first-class document assets
        if uploaded_files:
            try:
                from kulima.core.documents.ingestion import DocumentIngestionService
                from kulima.core.documents.repository import DocumentRepository

                run_id: int | None = None
                _archive = st.session_state.get("loaded_from_archive")
                if _archive and "run_id" in _archive:
                    run_id = int(_archive["run_id"])
                else:
                    try:
                        _h = repo.recent_runs(1)
                        if _h:
                            run_id = int(_h[0]["id"])
                    except Exception:
                        run_id = None

                _svc = DocumentIngestionService()
                _drep = DocumentRepository()
                for _b in _svc.ingest_files(uploaded_files, run_id=run_id):
                    _drep.save_document(run_id=run_id, doc=_b.document)
                    _drep.save_chunks(_b.chunks)
            except Exception as _doc_exc:
                logging.getLogger(__name__).warning(
                    "Document ingestion failed: %s: %s",
                    type(_doc_exc).__name__, _doc_exc,
                )

    # ── st.chat_input — sole message entry point ──────────────────────────
    pending = st.session_state.pop(f"ic_pending_{message_key}", None)
    typed = st.chat_input(
        "Ask the IC Analyst anything…",
        key=f"ic_input_{surface}_{message_key}",
    )
    question = pending or typed

    if question:
        st.session_state[message_key].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # Augment backend question with attachment context note (titles only)
        backend_question = question
        if _current_files:
            _names = ", ".join(
                getattr(f, "name", "attachment") for f in _current_files[:5]
            )
            backend_question += (
                f"\n\n(Context note: the investor has attached: {_names}. "
                "Reference them where relevant to strengthen or challenge the case.)"
            )

        with st.chat_message("assistant"):
            with st.spinner("Consulting the generated IC context…"):
                response = answer_ask_ic_question(
                    brief,
                    backend_question,
                    history=st.session_state[message_key][:-1],
                )
            logging.debug("IC response: %s", repr(response)[:120])
            _resp = (
                response if isinstance(response, str)
                else __import__("json").dumps(response, ensure_ascii=False, indent=2)
            )
            st.markdown(_resp)

        st.session_state[message_key].append({"role": "assistant", "content": response})

    st.markdown('</div>', unsafe_allow_html=True)


def render_ask_ic_tab(brief: InvestmentBrief) -> None:
    """Tab 4 — full-width Ask IC experience.  Delegates to shared panel."""
    render_ask_ic_panel(brief, compact=False, surface="tab")




def render_decision_brief(brief: InvestmentBrief, detail_kind: str | None = None) -> None:
    """Render the right-hand Decision Snapshot panel.

    This is a pure presentation layer over the existing InvestmentBrief and
    related artefacts. No backend or orchestration logic is changed.
    """
    st.markdown('<div class="kulima-context-panel">', unsafe_allow_html=True)
    st.markdown("### Decision Snapshot")

    # VERDICT
    st.markdown(f"**Verdict:** {brief.recommendation.value}")

    # CONFIDENCE
    conf_level = getattr(brief, "confidence_level", None)
    conf_num = getattr(brief, "confidence", None)
    if isinstance(conf_num, (int, float)):
        st.markdown(f"**Confidence:** {conf_num*100:.0f}% ({getattr(conf_level, 'value', conf_level)})")
    else:
        st.markdown(f"**Confidence:** {getattr(conf_level, 'value', conf_level) if conf_level is not None else 'N/A'}")

    # RELIABILITY
    ei = getattr(brief, "evidence_integrity", None)
    if ei is not None:
        st.markdown(
            f"**Reliability:** Grade {getattr(ei.integrity_grade, 'value', ei.integrity_grade)} "
            f"({ei.integrity_score:.0f}/100)"
        )
    else:
        st.markdown("**Reliability:** Not available")

    # TOP REASONS (3)
    st.markdown("**Top Reasons:**")
    reasons = []
    if brief.executive_summary:
        reasons.append(str(brief.executive_summary).strip().split(". ")[0][:140])
    if brief.investment_recommendation:
        reasons.append(str(brief.investment_recommendation).strip().split(". ")[0][:140])
    # Fallback using scores if needed
    if len(reasons) < 3:
        reasons.append(f"Strong overall score at {brief.overall_score:.0f}/100 vs. peers.")
    for r in reasons[:3]:
        st.markdown(f"• {r}")

    # TOP RISKS (3)
    st.markdown("**Top Risks:**")
    if brief.red_flags:
        for rf in brief.red_flags[:3]:
            sev = html.escape(rf.severity.upper())
            title = html.escape(rf.title)
            detail = html.escape(rf.detail)[:120]
            st.markdown(f"• [{sev}] {title}: {detail}")
    else:
        st.markdown("• No critical red flags surfaced from open-source intelligence.")

    # NEXT ACTION (one sentence)
    st.markdown("**Next Action:**")
    if brief.investment_recommendation:
        line = str(brief.investment_recommendation).strip().split(". ")[0][:160]
        st.markdown(f"{line}")
    else:
        st.markdown("Advance to IC only after focused verification of key risks.")

    if detail_kind is None:
        st.markdown("---")
        st.markdown("**Details**")
        if st.button("View Thesis", key="detail_thesis_btn"):
            st.session_state["details_mode"] = True
            st.session_state["details_kind"] = "Thesis"
            st.rerun()
        if st.button("View Evidence", key="detail_evidence_btn"):
            st.session_state["details_mode"] = True
            st.session_state["details_kind"] = "Evidence"
            st.rerun()
        if st.button("View Committee", key="detail_committee_btn"):
            st.session_state["details_mode"] = True
            st.session_state["details_kind"] = "Committee"
            st.rerun()
        if st.button("View Verification", key="detail_verification_btn"):
            st.session_state["details_mode"] = True
            st.session_state["details_kind"] = "Verification"
            st.rerun()
    else:
        st.markdown("---")
        st.markdown(f"### {detail_kind}")
        if st.button("← Back to Decision", key=f"back_to_decision_btn_{detail_kind}"):
            st.session_state["details_mode"] = False
            st.session_state["details_kind"] = None
            st.rerun()

        with st.expander(f"Show {detail_kind} details", expanded=True):
            if detail_kind == "Thesis":
                try:
                    from kulima.thesis import evaluate_thesis_match

                    tm = brief.thesis_match or evaluate_thesis_match(brief)
                    if tm is not None:
                        render_thesis_fit_card(tm)
                    else:
                        st.caption("Thesis Engine not available for this run.")
                except Exception:
                    st.caption("Thesis details unavailable.")
            elif detail_kind == "Evidence":
                if ei is not None:
                    try:
                        render_reliability_card(ei)
                        render_reliability_report(ei)
                        render_trust_graph_coverage_note(ei)
                        render_trust_network_preview(brief, key="trust_net_fullwidth")
                    except Exception:
                        st.caption("Evidence details unavailable.")
                else:
                    st.caption("Evidence Integrity Engine not run for this analysis.")
            elif detail_kind == "Committee":
                try:
                    render_twin_syndicate_committee(brief, key_suffix="_details")
                except Exception:
                    st.caption("Committee details unavailable.")
            elif detail_kind == "Verification":
                if ei is not None and ei.verification_checklist:
                    st.markdown("**Verification Checklist**")
                    for item in ei.verification_checklist:
                        st.markdown(f"- {item}")
                elif getattr(brief, "next_steps", None):
                    st.markdown("**Next Steps**")
                    for step in brief.next_steps:
                        st.markdown(f"- {step}")
                else:
                    st.caption("No additional verification items listed.")

    st.markdown('</div>', unsafe_allow_html=True)


def render_detail_view(brief: InvestmentBrief, detail: str) -> None:
    """Full-width Details mode for a single analysis dimension.

    This replaces the usual split-screen view while active so rich content
    (Thesis, Evidence, Committee, Verification) is not compressed inside the
    compact Decision Snapshot column.
    """
    st.markdown(f"### Details: {detail}")
    if st.button("← Back to Decision", key="back_to_decision_btn"):
        st.session_state["details_mode"] = False
        st.session_state["details_kind"] = None
        st.rerun()

    ei = getattr(brief, "evidence_integrity", None)

    if detail == "Thesis":
        try:
            from kulima.thesis import evaluate_thesis_match

            tm = brief.thesis_match or evaluate_thesis_match(brief)
            if tm is not None:
                render_thesis_fit_card(tm)
            else:
                st.caption("Thesis Engine not available for this run.")
        except Exception:
            st.caption("Thesis details unavailable.")

    elif detail == "Evidence":
        if ei is not None:
            try:
                render_reliability_card(ei)
                render_reliability_report(ei)
                render_trust_graph_coverage_note(ei)
                render_trust_network_preview(brief, key="trust_net_fullwidth")
            except Exception:
                st.caption("Evidence details unavailable.")
        else:
            st.caption("Evidence Integrity Engine not run for this analysis.")

    elif detail == "Committee":
        try:
            render_twin_syndicate_committee(brief, key_suffix="_details")
        except Exception:
            st.caption("Committee details unavailable.")

    elif detail == "Verification":
        if ei is not None and ei.verification_checklist:
            st.markdown("**Verification Checklist**")
            for item in ei.verification_checklist:
                st.markdown(f"- {item}")
        elif getattr(brief, "next_steps", None):
            st.markdown("**Next Steps**")
            for step in brief.next_steps:
                st.markdown(f"- {step}")
        else:
            st.caption("No additional verification items listed.")



def render_brief(brief: InvestmentBrief) -> None:
    archive_meta = st.session_state.get("loaded_from_archive")
    if archive_meta:
        render_loaded_banner(
            run_id=archive_meta["run_id"],
            created_at=archive_meta["created_at"],
        )
    elif st.session_state.get("show_success_banner"):
        render_success_banner(brief)

    # Show diff banner if intelligence was re-run with documents
    re_meta = st.session_state.get("reintelligence_meta")
    if re_meta:
        try:
            prev_rec = re_meta.get("prev_rec")
            new_rec = re_meta.get("new_rec")
            prev_score = re_meta.get("prev_score")
            new_score = re_meta.get("new_score")
            msg_lines = [
                "✅ Intelligence updated using uploaded documents.",
                "",
                f"Previous recommendation: {prev_rec}",
                f"Updated recommendation: {new_rec}",
                "",
                f"Previous score: {prev_score:.0f}/100" if isinstance(prev_score, (int, float)) else "",
                f"Updated score: {new_score:.0f}/100" if isinstance(new_score, (int, float)) else "",
            ]
            # Filter out empty lines
            msg = "\n".join(line for line in msg_lines if line)
            st.success(msg)
        finally:
            # Clear after showing once so it doesn't persist across deals
            st.session_state["reintelligence_meta"] = None

    # Split-screen layout: left = IC Analyst chat shell (≈80%), right = compact Decision Snapshot panel (≈20%)
    left_col, right_col = st.columns([4, 1], gap="large")
    with left_col:
        render_ask_ic_panel(brief, compact=False, surface="analyst")
    with right_col:
        render_decision_brief(
            brief,
            detail_kind=st.session_state.get("details_kind")
            if st.session_state.get("details_mode") else None,
        )


if run:
    if not founder.strip():
        st.warning("Enter a founder name to begin intelligence.")
    elif settings.missing_required_secrets():
        st.error("Configure API keys in `.env` before running.")
    else:
        progress_bar = st.progress(0, text="Warming up Investment Intelligence OS…")
        status_box = st.empty()
        status_box.markdown(textwrap.dedent("""
            <div class="pipeline-card">
              <div class="pipeline-step"><span class="pipeline-dot"></span> Connecting agents…</div>
            </div>
            """), unsafe_allow_html=True)

        def on_progress(pct: float, message: str) -> None:
            progress_bar.progress(min(max(pct, 0.0), 1.0), text=message)
            status_box.markdown(textwrap.dedent(f"""
                <div class="pipeline-card">
                  <div class="pipeline-step">
                    <span class="pipeline-dot"></span>
                    <span><b>{int(pct * 100)}%</b> — {message}</span>
                  </div>
                </div>
                """), unsafe_allow_html=True)

        with st.status(
            "Running multi-agent Investment Intelligence OS…", expanded=True
        ) as status:
            try:
                orchestrator = IntelligenceOrchestrator()
                brief = orchestrator.analyze(founder, startup, on_progress=on_progress)
                run_id = repo.save_brief(brief)
                st.session_state["latest_brief"] = brief
                st.session_state["latest_run_id"] = run_id
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
view = st.session_state.get("workspace_view", "Decision Mode")

if view == "Decision Mode":
    if "latest_brief" in st.session_state:
        brief = st.session_state["latest_brief"]
        render_brief(brief)
        if st.session_state.get("latest_run_id") is not None:
            st.markdown("### 📝 Pilot Feedback")
            with st.form(f"pilot_feedback_{st.session_state['latest_run_id']}"):
                feedback_user = st.text_input(
                    "User",
                    value=st.session_state.get("pilot_user_name", ""),
                    key="pilot_feedback_user",
                )
                feedback_rating = st.slider(
                    "Rating",
                    min_value=1,
                    max_value=5,
                    value=4,
                    help="1 = poor, 5 = excellent",
                    key="pilot_feedback_rating",
                )
                feedback_comment = st.text_area(
                    "Comment",
                    placeholder="What worked, what was missing, what should improve next?",
                    key="pilot_feedback_comment",
                )
                submit_feedback = st.form_submit_button("Submit Feedback")
            if submit_feedback:
                repo.save_feedback(
                    int(st.session_state["latest_run_id"]),
                    feedback_user or st.session_state.get("pilot_user_name", "Pilot User"),
                    int(feedback_rating),
                    feedback_comment,
                )
                st.success("Feedback captured for the pilot review loop.")
    else:
        render_empty_state()
else:
    # Workspace mode: Evidence / Reports / Portfolio / History / Exports / Comparisons / Signals
    st.markdown(f"### Workspace · {view}")
    if view == "Evidence":
        if "latest_brief" in st.session_state:
            render_evidence_workspace(st.session_state["latest_brief"])
        else:
            st.info("No analysis loaded yet. Run a deal or reopen a saved run to inspect the evidence workspace.")
    elif view == "Reports":
        if "latest_brief" in st.session_state:
            render_reports_workspace(st.session_state["latest_brief"])
        else:
            st.info("No report is available yet. Run or reopen a deal to generate the export-ready report pack.")
    elif view == "Portfolio":
        try:
            render_portfolio_dashboard(repo, key_prefix="workspace_portfolio")
        except Exception:
            st.warning("Portfolio Intelligence is unavailable.")
    elif view == "Analytics":
        try:
            render_analytics_workspace(repo, key_prefix="workspace_analytics")
        except Exception:
            st.warning("Analytics Workspace is unavailable.")
    elif view == "History":
        try:
            history = repo.recent_runs(50, include_archived=True)
        except Exception:
            history = []
        if history:
            selected_run_id = render_history_panel(history)
            if selected_run_id is not None:
                selected_row = next((r for r in history if int(r["id"]) == selected_run_id), None)
                archived = bool(selected_row and selected_row.get("archived_at"))
                action_cols = st.columns([1.2, 1.2, 1.0])
                with action_cols[0]:
                    open_label = "♻️ Reopen Selected Run" if archived else "📂 Open Selected Run"
                    open_clicked = st.button(
                        open_label,
                        key=f"history_open_{selected_run_id}",
                        use_container_width=True,
                    )
                with action_cols[1]:
                    archive_clicked = st.button(
                        "🗄️ Archive Selected Run",
                        key=f"history_archive_{selected_run_id}",
                        disabled=archived,
                        use_container_width=True,
                    )
                with action_cols[2]:
                    delete_clicked = st.button(
                        "🗑️ Delete Selected Run",
                        key=f"history_delete_{selected_run_id}",
                        type="secondary",
                        use_container_width=True,
                    )

                if open_clicked:
                    if archived:
                        repo.reopen_run(selected_run_id)
                    loaded_brief = repo.load_brief(selected_run_id)
                    if loaded_brief is not None:
                        created_at = selected_row["created_at"] if selected_row else ""
                        st.session_state["latest_brief"] = loaded_brief
                        st.session_state["loaded_from_archive"] = {
                            "run_id": selected_run_id,
                            "created_at": created_at,
                        }
                        st.session_state["loaded_run_id"] = selected_run_id
                        st.session_state["latest_run_id"] = selected_run_id
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
                            f"Run #{selected_run_id} could not be restored — stored data may be from an older schema.",
                            icon="⚠️",
                        )
                elif archive_clicked:
                    if repo.archive_run(selected_run_id):
                        st.success(f"Run #{selected_run_id} archived for pilot review.")
                        st.rerun()
                elif delete_clicked:
                    if repo.delete_run(selected_run_id):
                        if st.session_state.get("loaded_run_id") == selected_run_id:
                            st.session_state.pop("latest_brief", None)
                            st.session_state.pop("loaded_run_id", None)
                            st.session_state.pop("loaded_from_archive", None)
                            st.session_state.pop("latest_run_id", None)
                        st.warning(f"Run #{selected_run_id} deleted from history.")
                        st.rerun()
        else:
            st.info("No saved analyses yet. Run a deal to build pilot history, then return here to reopen, archive, or delete runs.")
    elif view == "Exports":
        if "latest_brief" in st.session_state:
            render_export_buttons(st.session_state["latest_brief"], key_prefix="workspace_export")
            if st.session_state.get("latest_run_id") is not None:
                st.markdown("### 📝 Pilot Feedback")
                with st.form(f"pilot_feedback_exports_{st.session_state['latest_run_id']}"):
                    feedback_user = st.text_input(
                        "User",
                        value=st.session_state.get("pilot_user_name", ""),
                        key="pilot_feedback_user_exports",
                    )
                    feedback_rating = st.slider(
                        "Rating",
                        min_value=1,
                        max_value=5,
                        value=4,
                        help="1 = poor, 5 = excellent",
                        key="pilot_feedback_rating_exports",
                    )
                    feedback_comment = st.text_area(
                        "Comment",
                        placeholder="What worked, what was missing, what should improve next?",
                        key="pilot_feedback_comment_exports",
                    )
                    submit_feedback = st.form_submit_button("Submit Feedback")
                if submit_feedback:
                    repo.save_feedback(
                        int(st.session_state["latest_run_id"]),
                        feedback_user or st.session_state.get("pilot_user_name", "Pilot User"),
                        int(feedback_rating),
                        feedback_comment,
                    )
                    st.success("Feedback captured for the pilot review loop.")
        else:
            st.info("Run or reopen a deal to unlock one-click exports and pilot feedback.")
    elif view == "Comparisons":
        try:
            history = repo.recent_runs(50)
        except Exception:
            history = []
        if history:
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
        else:
            st.info("No saved analyses are available yet. Complete at least two runs to compare them side by side.")
    elif view == "Signals":
        from kulima.core.cases.adapters import from_investment_brief
        from kulima.signals.ask_signals import answer_ask_signals_question
        from kulima.signals.models import SignalLevel
        from kulima.signals.orchestrator import SignalsOrchestrator
        from kulima.signals.signals_summary import (
            count_signals_by_level,
            highest_priority_signals,
        )

        if "latest_brief" not in st.session_state:
            st.info("Run or reopen an analysis to inspect signal outputs and follow-up questions.")
        else:
            brief = st.session_state["latest_brief"]
            case_id = (
                f"case::{brief.founder_name}::{brief.startup_name}"
            )
            case = from_investment_brief(
                brief, case_id=case_id, created_by="workspace_signals"
            )

            orch = SignalsOrchestrator()
            signals = orch.generate(case)

            # ── Session-state key — unique per analysis (mirrors Ask IC pattern) ──
            ask_signals_key = (
                f"ask_signals_messages::{brief.founder_name}"
                f"::{brief.startup_name}::{brief.overall_score:.0f}"
            )
            if ask_signals_key not in st.session_state:
                # Analyst greeting — pre-populated on first load
                n_signals = len(signals)
                risk_count = sum(1 for s in signals if s.direction == "risk")
                opp_count  = sum(1 for s in signals if s.direction == "opportunity")
                from kulima.signals.signals_summary import count_signals_by_level
                level_counts = count_signals_by_level(signals)
                critical_n = level_counts.get(SignalLevel.CRITICAL, 0)
                high_n     = level_counts.get(SignalLevel.HIGH, 0)

                if not signals:
                    intro = (
                        "No signals were generated for this analysis. "
                        "This typically means the evidence corpus is clean "
                        "and no material risks or opportunities were detected. "
                        "You can still ask me questions about the case."
                    )
                else:
                    top = highest_priority_signals(signals, limit=1)
                    top_title = top[0].title if top else "—"
                    intro = (
                        f"Signals pack ready — **{n_signals}** signal"
                        f"{'s' if n_signals != 1 else ''} generated "
                        f"({risk_count} risk, {opp_count} opportunity).\n\n"
                        f"Priority breakdown: "
                        f"CRITICAL {critical_n} · HIGH {high_n} · "
                        f"MEDIUM {level_counts.get(SignalLevel.MEDIUM, 0)} · "
                        f"LOW {level_counts.get(SignalLevel.LOW, 0)}\n\n"
                        f"Most urgent: **{top_title}**\n\n"
                        "Ask me anything about these signals — risks, "
                        "opportunities, evidence quality, or what to do next."
                    )
                st.session_state[ask_signals_key] = [
                    {"role": "assistant", "content": intro}
                ]

            # ── Two-column layout ─────────────────────────────────────────────
            col_chat, col_signals = st.columns([4, 1], gap="large")

            # ────────────────────────────────────────────────────────────────
            # LEFT COLUMN: Ask SIGNALS — Chat Shell V2
            # ────────────────────────────────────────────────────────────────
            with col_chat:
                st.markdown('<div class="kulima-chat-shell">', unsafe_allow_html=True)
                # ── 1. Chat header — persona · badge · Clear ──────────────
                n_sig = len(signals)
                sig_badge = f"{n_sig} signal{'s' if n_sig != 1 else ''}"
                _sg_hdr, _, _sg_clr = st.columns([5, 1, 1])
                with _sg_hdr:
                    st.markdown(
                        f'<div class="kulima-chat-header"'
                        f' style="border-bottom:none;margin-bottom:0;">'
                        f'<span class="kulima-chat-persona">'
                        f'Risk &amp; Opportunity Analyst</span>'
                        f'<span class="kulima-chat-badge">{sig_badge}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with _sg_clr:
                    st.markdown('<div class="kulima-chat-clear">', unsafe_allow_html=True)
                    if st.button("Clear", key=f"sg_clear_{ask_signals_key}"):
                        st.session_state[ask_signals_key] = (
                            st.session_state[ask_signals_key][:1]
                        )
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

                st.markdown(
                    '<hr style="margin:0.3rem 0 0.55rem;border:none;'
                    'border-top:1px solid rgba(11,61,46,0.10);">',
                    unsafe_allow_html=True,
                )

                # ── 2. Suggested Questions — collapsed ────────────────────
                _SIGNALS_SUGGESTIONS = [
                    "What are my top 3 risks?",
                    "What opportunities should I pursue?",
                    "What should leadership focus on?",
                    "Which signal is most urgent?",
                    "What evidence is weak?",
                    "What actions should I take this month?",
                ]
                st.markdown(
                    '<div class="kulima-suggestions-expander">',
                    unsafe_allow_html=True,
                )
                with st.expander("💡 Suggested questions", expanded=False):
                    for _sq in _SIGNALS_SUGGESTIONS:
                        if st.button(
                            _sq,
                            key=f"sg_sugg_{ask_signals_key}_{_sq[:18]}",
                            use_container_width=True,
                        ):
                            st.session_state[
                                f"ask_signals_pending_{ask_signals_key}"
                            ] = _sq
                st.markdown("</div>", unsafe_allow_html=True)

                # ── 3. Message history ────────────────────────────────────
                st.markdown('<div class="kulima-chat-history">', unsafe_allow_html=True)
                for message in st.session_state[ask_signals_key]:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
                st.markdown('</div>', unsafe_allow_html=True)

                # ── 4. Composer — st.chat_input (no attachments for SIGNALS)
                st.markdown('<div class="kulima-composer-wrapper">', unsafe_allow_html=True)
                pending = st.session_state.pop(
                    f"ask_signals_pending_{ask_signals_key}", None
                )
                typed = st.chat_input(
                    "Ask the Risk & Opportunity Analyst…",
                    key=f"sg_input_{ask_signals_key}",
                )
                question = pending or typed

                if question:
                    st.session_state[ask_signals_key].append(
                        {"role": "user", "content": question}
                    )
                    with st.chat_message("user"):
                        st.markdown(question)

                    with st.chat_message("assistant"):
                        with st.spinner("Consulting the Risk & Opportunity Analyst…"):
                            response = answer_ask_signals_question(
                                case,
                                signals,
                                question,
                                history=st.session_state[ask_signals_key][:-1],
                            )
                        st.markdown(response)

                    st.session_state[ask_signals_key].append(
                        {"role": "assistant", "content": response}
                    )
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with col_signals:
                st.markdown('<div class="kulima-context-panel">', unsafe_allow_html=True)
                st.markdown("#### 📡 Signals")

                if not signals:
                    st.caption("No signals generated for this analysis yet.")
                else:
                    counts = count_signals_by_level(signals)

                    # Compact summary badges
                    badge_parts = []
                    for lvl, label, bg, fg in [
                        (SignalLevel.CRITICAL, "CRITICAL", "#9B2226", "#fff"),
                        (SignalLevel.HIGH, "HIGH", "#D97706", "#fff"),
                        (SignalLevel.MEDIUM, "MEDIUM", "#B8892D", "#fff"),
                        (SignalLevel.LOW, "LOW", "#0B6E4F", "#fff"),
                    ]:
                        if counts.get(lvl, 0) > 0:
                            badge_parts.append(
                                f'<span style="background:{bg};color:{fg};'
                                f'padding:0.18rem 0.6rem;border-radius:999px;'
                                f'font-size:0.78rem;font-weight:700;">'
                                f'{label} {counts.get(lvl, 0)}</span>'
                            )
                    badge_html = " &nbsp; ".join(badge_parts)
                    if badge_html:
                        st.markdown(badge_html, unsafe_allow_html=True)
                        st.markdown("")

                    _level_colors = {
                        "critical": "#9B2226",
                        "high": "#D97706",
                        "medium": "#B8892D",
                        "low": "#0B6E4F",
                    }
                    _dir_icons = {
                        "risk": "⚠",
                        "opportunity": "✅",
                        "neutral": "ℹ",
                    }

                    for idx, s in enumerate(
                        highest_priority_signals(signals), 1
                    ):
                        border = _level_colors.get(s.level.value, "#888")
                        icon = _dir_icons.get(s.direction, "ℹ")
                        ref = f"[SG{idx}]"
                        evidence_refs = (
                            f'<br/><span style="font-size:0.8rem;color:#5B6F64;">'
                            f'Refs: {", ".join(s.evidence_refs)}</span>'
                            if s.evidence_refs
                            else ""
                        )
                        action_html = (
                            f'<br/><span style="font-size:0.82rem;'
                            f'color:#0B3D2E;font-weight:600;">'
                            f'→ {s.recommended_action}</span>'
                            if s.recommended_action
                            else ""
                        )
                        time_horizon = (
                            f" · {s.time_horizon}" if s.time_horizon else ""
                        )
                        card_html = (
                            f'<div style="border-left:3px solid {border};'
                            f'padding:0.55rem 0.75rem;margin:0.45rem 0;'
                            f'background:rgba(0,0,0,0.02);border-radius:0 8px 8px 0;'
                            f'word-break:break-word;">'
                            f'<span style="font-size:0.72rem;font-weight:700;'
                            f'color:{border};text-transform:uppercase;">'
                            f'{s.level.value} · {s.category.value.title()}'
                            f'</span>'
                            f'<span style="font-size:0.7rem;color:#8A9E94;'
                            f'margin-left:0.4rem;">{ref}</span>'
                            f'<br/><strong>{icon} {s.title}</strong>'
                            f'<br/><span style="font-size:0.88rem;color:#2F453B;">'
                            f'{s.description}</span>'
                            f'{evidence_refs}'
                            f'{action_html}'
                            f'<br/><span style="font-size:0.75rem;color:#8A9E94;">'
                            f'Confidence {s.confidence:.2f}{time_horizon}</span>'
                            f'</div>'
                        )
                        st.markdown(card_html, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
