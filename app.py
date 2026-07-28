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

# Feature flags for UI-only surfaces
ENABLE_VOICE_INPUT = False  # Keep voice code but hide from main UX

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
        width="stretch",
        key="run_full_intelligence",
    )

    st.divider()
    # Workspace mode selector — controls Portfolio, History, Exports, Comparisons
    workspace_view = st.selectbox(
        "WORKSPACE ▾",
        ["Decision Mode", "Portfolio", "History", "Exports", "Comparisons"],
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
    """Shared Ask IC UI surface (IC Analyst front-end).

    Front-end only: uses the existing Ask IC backend to power a chat-first
    IC Analyst experience. No prompt chips or quick buttons are rendered
    anymore — the chat input is the primary control.
    """

    # ── Session message state (shared key → all surfaces share history) ────
    message_key = _ask_ic_session_key(brief)
    if message_key not in st.session_state:
        # First automatic IC Analyst message once a brief is ready
        rec = getattr(brief, "recommendation", None)
        rec_text = rec.value if rec is not None else "Not available"
        conf_level = getattr(brief, "confidence_level", None)
        conf_label = getattr(conf_level, "value", str(conf_level) if conf_level is not None else "Not available")
        conf_num = getattr(brief, "confidence", None)

        ei = getattr(brief, "evidence_integrity", None)
        if ei is not None:
            ei_text = f"Grade {getattr(ei.integrity_grade, 'value', ei.integrity_grade)} ({ei.integrity_score:.0f}/100)"
        else:
            ei_text = "Not available"

        syn = getattr(brief, "syndicate", None)
        if syn is not None:
            final = syn.final_recommendation or syn.majority_vote
            final_text = final.value if final is not None else "Not available"
            consensus = syn.consensus_score or syn.average_score
            dissent = syn.dissent_score if syn.dissent_score is not None else syn.dissent_index * 100
            committee_line = (
                f"{final_text} · Consensus {consensus:.0f}/100 · Dissent {dissent:.0f}/100"
            )
        else:
            committee_line = "Not available (syndicate not run)."

        intro = (
            "Your investment brief is ready.\n\n"
            f"Recommendation: {rec_text}\n"
            f"Confidence: {conf_label}{f' ({conf_num:.2f})' if isinstance(conf_num, (int, float)) else ''}\n"
            f"Evidence Reliability: {ei_text}\n"
            f"Committee Position: {committee_line}\n\n"
            "What would you like to know?"
        )
        st.session_state[message_key] = [
            {
                "role": "assistant",
                "content": intro,
            }
        ]

    # ── Chat history ───────────────────────────────────────────────────────
    for message in st.session_state[message_key]:
        logging.debug("render_ask_ic_panel message.content: %s", repr(message.get("content")))
        # Normalize non-string content to safe JSON/text for display
        _msg_content = message.get("content")
        if not isinstance(_msg_content, str):
            try:
                _msg_content = __import__("json").dumps(_msg_content, ensure_ascii=False, indent=2)
            except Exception:
                _msg_content = str(_msg_content)
        with st.chat_message(message["role"]):
            st.markdown(_msg_content)

    # ── Voice input (upload-based stub with editable transcript) ───────────
    voice_key = f"ask_ic_voice::{message_key}"
    transcript_key = f"{voice_key}_transcript"
    if ENABLE_VOICE_INPUT:
        with st.expander("🎤 Voice Input", expanded=False):
            st.caption(
                "Upload a short voice note; its transcript will appear below for "
                "editing before sending. Configure speech-to-text separately."
            )
            voice_file = st.file_uploader(
                "Upload voice note",
                type=["wav", "mp3", "m4a", "ogg"],
                key=f"{voice_key}_file",
            )
            if voice_file is not None and transcript_key not in st.session_state:
                st.session_state[transcript_key] = ""
                st.info(
                    "Voice note received. Configure speech-to-text service to enable "
                    "automatic transcription.",
                    icon="🎤",
                )
            transcript_val = st.session_state.get(transcript_key, "")
            transcript_val = st.text_area(
                "Transcript",
                value=transcript_val,
                key=transcript_key,
                height=80,
            )

    # ── Chat input with rotating placeholder prompts ───────────────────────
    input_key = f"ask_ic_chat_input::%s::%s" % (surface, message_key)
    placeholders = [
        "Should I invest in this startup?",
        "What would make this a pass?",
        "What evidence is weak?",
        "What scares the committee?",
        "What should I verify before issuing a term sheet?",
        "How would an African VC evaluate this deal?",
        "Summarize this deal for investment committee.",
        "If I had 15 minutes, what is your verdict?",
    ]
    try:
        idx = int(time.time() // 5) % len(placeholders)
    except Exception:
        idx = 0
    placeholder_text = placeholders[idx]

    # Modern chat composer: multi-line input + attachments + Send
    st.markdown("**Ask your IC Analyst anything…**")
    user_text = st.text_area(
        "",
        key=input_key,
        height=100,
        placeholder=placeholder_text,
    )

    cols = st.columns([3, 1])
    with cols[0]:
        # Attachments integrated with the composer
        attach_key = f"ask_ic_attachments::{message_key}"
        uploaded_files = st.file_uploader(
            "📎 Attach Documents",
            type=["pdf", "docx", "txt", "csv", "xlsx", "pptx", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key=attach_key,
        )
    with cols[1]:
        send_clicked = st.button("➤ Send", key=f"send_btn::{message_key}")

    files = uploaded_files or st.session_state.get(attach_key, [])
    if uploaded_files:
        st.info(
            "Document received. Kulima FLEX will incorporate:\n"
            "• Uploaded Documents\n"
            "• Existing Intelligence\n"
            "• Twin Syndicate\n"
            "• Trust Layer\n"
            "• Thesis Analysis\n"
            "• Evidence Integrity",
            icon="📎",
        )

    if files:
        st.markdown(f"**Supporting Documents ({len(files)})**")
        for f in files:
            st.markdown(f"✅ {getattr(f, 'name', 'attachment')}")
        rerun_clicked = st.button(
            "Re-run Intelligence With Documents",
            key=f"rerun_docs::{message_key}",
        )
        if rerun_clicked:
            st.info(
                "Re-running intelligence using uploaded documents and existing intelligence...",
                icon="🔄",
            )
            prev_rec = getattr(brief.recommendation, "value", str(brief.recommendation))
            prev_score = float(getattr(brief, "overall_score", 0.0) or 0.0)

            def _noop_progress(pct: float, message: str) -> None:
                # Minimal progress hook for orchestrator; UI handled by surrounding spinner.
                return None

            from kulima.agents.orchestrator import IntelligenceOrchestrator

            try:
                with st.spinner("Running updated Investment Intelligence…"):
                    orchestrator = IntelligenceOrchestrator()
                    new_brief = orchestrator.analyze(
                        brief.founder_name,
                        brief.startup_name,
                        on_progress=_noop_progress,
                    )
                    repo.save_brief(new_brief)
                new_rec = getattr(new_brief.recommendation, "value", str(new_brief.recommendation))
                new_score = float(getattr(new_brief, "overall_score", 0.0) or 0.0)
                st.session_state["latest_brief"] = new_brief
                st.session_state["reintelligence_meta"] = {
                    "prev_rec": prev_rec,
                    "prev_score": prev_score,
                    "new_rec": new_rec,
                    "new_score": new_score,
                }
                # Force a full redraw so Decision Snapshot and IC Analyst use the new brief
                st.rerun()
            except Exception as _re_exc:
                st.error(
                    f"Re-run with documents failed — {type(_re_exc).__name__}: {_re_exc}",
                    icon="⚠️",
                )

    # Use typed text if Send is clicked; otherwise fall back to voice transcript
    transcript_text = st.session_state.get(transcript_key, "") if ENABLE_VOICE_INPUT else ""
    question = None
    if send_clicked and user_text and user_text.strip():
        question = user_text.strip()
    elif ENABLE_VOICE_INPUT and transcript_text.strip():
        question = transcript_text.strip()

    if question:
        # Persist and display exactly what the investor typed/confirmed
        st.session_state[message_key].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # Augment the backend question with attachment metadata (titles only)
        backend_question = question
        if files:
            attachment_names = ", ".join(getattr(f, "name", "attachment") for f in files[:5])
            note = textwrap.dedent(
                f"""
                
                (Context note for IC Associate:
                The investor has uploaded additional documents titled: {attachment_names}.
                You do not have direct access to their full contents here.
                When relevant, suggest what to look for in these documents to
                strengthen or challenge the investment case.)
                """
            ).strip()
            backend_question = f"{question}\n\n{note}"

        with st.chat_message("assistant"):
            with st.spinner("Consulting the generated IC context…"):
                response = answer_ask_ic_question(
                    brief,
                    backend_question,
                    history=st.session_state[message_key][:-1],
                )
            logging.debug("answer_ask_ic_question response: %s", repr(response))
            # Ensure the response is a string for markdown rendering
            _resp_content = response if isinstance(response, str) else __import__("json").dumps(response, ensure_ascii=False, indent=2)
            st.markdown(_resp_content)
        logging.debug("append_message_to_session_state: %s", repr(response))
        st.session_state[message_key].append({"role": "assistant", "content": response})


def render_ask_ic_tab(brief: InvestmentBrief) -> None:
    """Tab 4 — full-width Ask IC experience.  Delegates to shared panel."""
    render_ask_ic_panel(brief, compact=False, surface="tab")




def render_decision_brief(brief: InvestmentBrief) -> None:
    """Render the right-hand Decision Snapshot (compressed A–G view).

    This is a pure presentation layer over the existing InvestmentBrief and
    related artefacts. No backend or orchestration logic is changed.
    """
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

    # Detail actions: triggers only; rich content rendered in full-width Details mode
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

    # Split-screen layout: left = IC Analyst (≈80%), right = Decision Brief (≈20%)
    left_col, right_col = st.columns([4, 1])
    with left_col:
        render_ask_ic_panel(brief, compact=False, surface="analyst")
    with right_col:
        render_decision_brief(brief)


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
view = st.session_state.get("workspace_view", "Decision Mode")

if view == "Decision Mode":
    if "latest_brief" in st.session_state:
        brief = st.session_state["latest_brief"]
        if st.session_state.get("details_mode") and st.session_state.get("details_kind"):
            render_detail_view(brief, st.session_state["details_kind"])
        else:
            render_brief(brief)
    else:
        render_empty_state()
else:
    # Workspace mode: Portfolio / History / Exports / Comparisons
    st.markdown(f"### Workspace · {view}")
    if view == "Portfolio":
        try:
            render_portfolio_dashboard(repo, key_prefix="workspace_portfolio")
        except Exception:
            st.warning("Portfolio Intelligence is unavailable.")
    elif view == "History":
        try:
            history = repo.recent_runs(50)
        except Exception:
            history = []
        if history:
            selected_run_id = render_history_panel(history)
            if selected_run_id is not None and selected_run_id != st.session_state.get("loaded_run_id"):
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
                        f"Run #{selected_run_id} could not be restored — stored data may be from an older schema.",
                        icon="⚠️",
                    )
        else:
            st.caption("No previous analyses stored yet.")
    elif view == "Exports":
        if "latest_brief" in st.session_state:
            with st.expander("Export", expanded=True):
                try:
                    render_export_buttons(st.session_state["latest_brief"], key_prefix="workspace_export")
                except Exception:
                    st.warning("Exports are unavailable for this run.")
        else:
            st.caption("Run or load an analysis to enable exports.")
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
            st.caption("No analyses available for comparison.")
