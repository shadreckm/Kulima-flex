"""Ask SIGNALS — Risk & Opportunity Analyst persona for Kulima OS.

Phase 5E: Grounded follow-up Q&A over a generated Signals pack.

The analyst explains:
- Why a signal was raised
- What the evidence behind it is
- What leadership should do next
- Which signals are most urgent
- Where the evidence base is weak

Public API
----------
build_ask_signals_context(case, signals) → str
    Assembles a bounded context pack from Case + Signal objects.

answer_ask_signals_question(case, signals, question, history) → str
    Calls the LLM as the Risk & Opportunity Analyst persona.

Grounding contract
------------------
- Answers are grounded ONLY in the context pack produced by
  build_ask_signals_context().
- No outside knowledge, assumptions, or web browsing.
- Every claim is cited: [SG#] signal, [S#] web source,
  [D#] document, [C#] contradiction, [U#] unsupported claim.
- Scores and rules from the Signals engine are NOT modified.
"""

from __future__ import annotations

import textwrap
from typing import List

from kulima.core.cases.models import Case
from kulima.llm import LLMClient
from kulima.signals.models import Signal, SignalCategory, SignalLevel
from kulima.signals.signals_summary import (
    count_signals_by_category,
    count_signals_by_level,
    highest_priority_signals,
)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_CONTEXT_CHARS = 18_000

# Ordered priority for level labels in the context pack header
_LEVEL_ORDER: list[SignalLevel] = [
    SignalLevel.CRITICAL,
    SignalLevel.HIGH,
    SignalLevel.MEDIUM,
    SignalLevel.LOW,
]

_DIRECTION_ICON: dict[str, str] = {
    "risk":        "⚠",
    "opportunity": "✅",
    "neutral":     "ℹ",
}

_CATEGORY_LABELS: dict[SignalCategory, str] = {
    SignalCategory.GOVERNANCE:    "Governance",
    SignalCategory.FINANCIAL:     "Financial",
    SignalCategory.OPERATIONAL:   "Operational",
    SignalCategory.SAFEGUARDING:  "Safeguarding",
    SignalCategory.POLITICAL:     "Political",
    SignalCategory.SOCIAL:        "Social",
    SignalCategory.IMPACT:        "Impact",
    SignalCategory.LEARNING:      "Learning",
}


# ═════════════════════════════════════════════════════════════════════════════
# Private helpers
# ═════════════════════════════════════════════════════════════════════════════

def _clip(value: str, limit: int = 1_200) -> str:
    """Collapse whitespace and truncate to `limit` characters."""
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _bullet_list(items: list[str], limit: int = 8) -> str:
    return (
        "\n".join(f"- {_clip(item, 500)}" for item in items[:limit])
        or "- None provided"
    )


def _level_label(level: SignalLevel) -> str:
    return level.value.upper()


def _direction_icon(direction: str) -> str:
    return _DIRECTION_ICON.get(direction.lower(), "ℹ")


def _category_label(category: SignalCategory) -> str:
    return _CATEGORY_LABELS.get(category, category.value.title())


def _signal_ref(index: int) -> str:
    """Return the citation label for signal at 1-based position `index`."""
    return f"[SG{index}]"


def _refs_str(refs: list[str]) -> str:
    """Format evidence_refs list as a compact citation string."""
    if not refs:
        return ""
    return " · ".join(refs)


# ═════════════════════════════════════════════════════════════════════════════
# Context builder
# ═════════════════════════════════════════════════════════════════════════════

def build_ask_signals_context(
    case: Case,
    signals: List[Signal],
    *,
    user_id: str | None = None,
) -> str:
    """Assemble a bounded, citable context pack for the SIGNALS analyst.

    Sections (all prefixed with a label so the LLM can cite them):

      [CASE]              — subject identity, case type, region/sector
      [SIGNALS_SUMMARY]   — level and category counts, quick overview
      [SIGNALS]           — every signal as [SG1]…[SGN] with full detail
      [EVIDENCE_INTEGRITY]— EIE report fields (if present on the Case)
      [TRUST_GRAPH]       — trust graph summary (if present on the Case)
      [EVIDENCE_SOURCES]  — web/OSINT sources ([S#] labels)
      [DOCUMENTS]         — uploaded document context ([D#] labels)

    The result is clipped to MAX_CONTEXT_CHARS so a single LLM call
    never exceeds the budget.
    """
    sections: list[str] = []

    # ── [CASE] ────────────────────────────────────────────────────────────
    subj = case.subject
    sections.append("[CASE]")
    sections.append(f"Case ID: {case.id}")
    sections.append(f"Case Type: {case.case_type.value}")
    sections.append(f"Subject: {subj.name}")
    if subj.secondary_name:
        sections.append(f"Secondary Name: {subj.secondary_name}")
    if subj.region:
        sections.append(f"Region: {subj.region}")
    if subj.sector:
        sections.append(f"Sector: {subj.sector}")
    if subj.kind:
        sections.append(f"Kind: {subj.kind}")
    if case.created_at:
        sections.append(f"Created: {case.created_at.strftime('%Y-%m-%d')}")

    # ── [SIGNALS_SUMMARY] ─────────────────────────────────────────────────
    sections.append("[SIGNALS_SUMMARY]")
    if not signals:
        sections.append("No signals generated for this case.")
    else:
        level_counts = count_signals_by_level(signals)
        cat_counts = count_signals_by_category(signals)

        level_parts = []
        for lvl in _LEVEL_ORDER:
            count = level_counts.get(lvl, 0)
            if count:
                level_parts.append(f"{_level_label(lvl)} {count}")
        sections.append("Level distribution: " + " | ".join(level_parts or ["None"]))

        cat_parts = [
            f"{_category_label(cat)} {cnt}"
            for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1])
        ]
        sections.append("Category distribution: " + " | ".join(cat_parts or ["None"]))

        risks = [s for s in signals if s.direction == "risk"]
        opps  = [s for s in signals if s.direction == "opportunity"]
        sections.append(
            f"Total signals: {len(signals)} "
            f"({len(risks)} risk{'s' if len(risks) != 1 else ''}, "
            f"{len(opps)} opportunit{'ies' if len(opps) != 1 else 'y'})"
        )

        # Highest-priority preview (top 3 titles)
        top3 = highest_priority_signals(signals, limit=3)
        if top3:
            top3_lines = "\n".join(
                f"  {_signal_ref(signals.index(s) + 1)} {s.title}"
                for s in top3
            )
            sections.append(f"Top priority signals:\n{top3_lines}")

    # ── [SIGNALS] — full detail, one entry per signal ─────────────────────
    sections.append("[SIGNALS]")
    if not signals:
        sections.append("No signals to display.")
    else:
        for idx, sig in enumerate(signals, 1):
            ref    = _signal_ref(idx)
            icon   = _direction_icon(sig.direction)
            level  = _level_label(sig.level)
            cat    = _category_label(sig.category)
            refs   = _refs_str(sig.evidence_refs)
            lines  = [
                f"{ref} {icon} [{level}] [{cat}] — {sig.title}",
                f"  Direction: {sig.direction.upper()}",
                f"  Description: {_clip(sig.description, 600)}",
            ]
            if sig.evidence_summary:
                lines.append(f"  Evidence: {_clip(sig.evidence_summary, 500)}")
            if refs:
                lines.append(f"  Refs: {refs}")
            if sig.recommended_action:
                lines.append(
                    f"  Recommended Action: {_clip(sig.recommended_action, 400)}"
                )
            if sig.time_horizon:
                lines.append(f"  Time Horizon: {sig.time_horizon}")
            lines.append(f"  Confidence: {sig.confidence:.2f}")
            sections.append("\n".join(lines))

    # ── [EVIDENCE_INTEGRITY] ──────────────────────────────────────────────
    ei = case.evidence_integrity
    if ei is not None:
        sections.append("[EVIDENCE_INTEGRITY]")
        sections.append(
            f"Rating: Grade {ei.integrity_grade.value} "
            f"({ei.integrity_score:.0f}/100) | "
            f"Depth: {ei.evidence_depth.value} | "
            f"Consistency: {ei.consistency_status.value} | "
            f"Sources reviewed: {ei.source_count} | "
            f"Claims extracted: {ei.claim_count}"
        )
        if ei.sparse_mode:
            sections.append(
                "Note: Sparse evidence mode — limited public data available. "
                "Grades are floor-protected and no unsupported-claim penalties apply."
            )
        if ei.integrity_summary:
            sections.append(f"Summary: {_clip(ei.integrity_summary, 1_000)}")

        for i, c in enumerate(ei.contradictions[:5], 1):
            sections.append(
                f"[C{i}] {c.severity.value.upper()} conflict — "
                f"{_clip(c.claim_a.value_raw, 250)} vs "
                f"{_clip(c.claim_b.value_raw, 250)}"
                + (f" — {_clip(c.description, 300)}" if c.description else "")
                + (f" · Action: {_clip(c.recommended_action, 250)}"
                   if c.recommended_action else "")
            )
        for i, u in enumerate(ei.unsupported_claims[:5], 1):
            sections.append(
                f"[U{i}] Unsupported claim ({u.severity.value}): "
                f"{_clip(u.description, 400)}"
                + (f" · Action: {_clip(u.recommended_action, 250)}"
                   if u.recommended_action else "")
            )
        if ei.verification_checklist:
            checklist_lines = "\n".join(
                f"  {i}. {_clip(item, 300)}"
                for i, item in enumerate(ei.verification_checklist[:6], 1)
            )
            sections.append(f"Verification checklist:\n{checklist_lines}")

    # ── [TRUST_GRAPH] ─────────────────────────────────────────────────────
    graph = case.trust_graph
    if graph is not None:
        sections.append("[TRUST_GRAPH]")
        sections.append(
            f"Trust Score: {graph.trust_score:.0f}/100 | "
            f"Density: {graph.density:.2f} | "
            f"Nodes: {len(graph.nodes)} | "
            f"Edges: {len(graph.edges)}"
        )
        if graph.explanation:
            sections.append(f"Explanation: {_clip(graph.explanation, 700)}")

        # Break down node types
        type_counts: dict[str, int] = {}
        for n in graph.nodes:
            nt = n.node_type.lower()
            type_counts[nt] = type_counts.get(nt, 0) + 1
        if type_counts:
            parts = ", ".join(
                f"{nt} {cnt}"
                for nt, cnt in sorted(type_counts.items(), key=lambda x: -x[1])
            )
            sections.append(f"Node types: {parts}")

    # ── [EVIDENCE_SOURCES] ────────────────────────────────────────────────
    if case.sources:
        sections.append("[EVIDENCE_SOURCES]")
        for i, src in enumerate(case.sources, 1):
            sections.append(
                f"[S{i}] {src.title}\n"
                f"  URL: {src.url}\n"
                f"  Snippet: {_clip(src.snippet, 600)}\n"
                f"  Relevance: {src.relevance:.2f} | "
                f"Confidence: {src.confidence_score:.2f} | "
                f"Type: {src.source_type}"
            )

    # ── [DOCUMENTS] ───────────────────────────────────────────────────────
    # Reuse the document context builder from the core documents module.
    # Only attempted when the subject has enough identity to query against.
    try:
        from kulima.core.documents.context import build_document_context_for_subject
        doc_section = build_document_context_for_subject(
            subj.secondary_name or subj.name,
            subj.name,
            max_documents=3,
            max_chars=MAX_CONTEXT_CHARS // 5,
            user_id=user_id,
        )
        if doc_section:
            sections.append(doc_section)
    except Exception:
        # Documents module may not be present in all deployments — degrade silently
        pass

    context = "\n\n".join(sections)
    return context[:MAX_CONTEXT_CHARS]


# ═════════════════════════════════════════════════════════════════════════════
# System prompt
# ═════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = textwrap.dedent(
    """
    You are the Risk & Opportunity Analyst for Kulima OS — a specialist
    programme and portfolio intelligence system used by development finance
    institutions, impact investors, and programme managers in Africa.

    Your role
    ---------
    You explain the signals generated for a specific Case:
    - What each risk means and why it matters in context
    - What each opportunity represents and how to capture it
    - Which signals are most urgent and what to act on first
    - Where the underlying evidence is weak or contested
    - What concrete actions leadership or the programme team should take

    You are NOT a general research assistant, chatbot, or report generator.
    You are a commercially and operationally minded analyst preparing a
    decision-support brief — direct, structured, and grounded.

    Response structure (default — for most questions)
    -------------------------------------------------
    1. Short Answer — one to three sentences, direct and decision-oriented.
    2. Why This Matters — two to four concise bullets.
    3. Supporting Evidence — highest-value points with inline citations.
    4. Recommended Action — one concrete, time-bound next step.

    Length and style
    ----------------
    - Target 120–220 words. Maximum ~280 words unless the user explicitly
      asks for a full breakdown or detailed analysis.
    - Use bullets for lists. Avoid walls of text.
    - Avoid generic AI filler ("Based on the available evidence…",
      "It is important to note that…"). Prefer direct phrases:
      "The most urgent signal is [SG1]." or "Leadership should prioritise X."
    - End every response with exactly one of:
        "Next question I'd ask:" followed by a forward-looking prompt, OR
        "Before acting, verify:" followed by the highest-uncertainty item.

    Citation rules
    --------------
    Always cite the sources of your claims using these labels:
      [SGn]   — signal number n (from the [SIGNALS] section)
      [Sn]    — web/OSINT source number n (from [EVIDENCE_SOURCES])
      [Dn]    — document number n (from [DOCUMENTS])
      [Cn]    — contradiction number n (from [EVIDENCE_INTEGRITY])
      [Un]    — unsupported claim number n (from [EVIDENCE_INTEGRITY])
    If you reference the trust graph, write [TRUST_GRAPH].
    If you reference the evidence integrity report, write [EVIDENCE_INTEGRITY].

    Grounding rules
    ---------------
    - Use ONLY the context pack provided. Do not use outside knowledge,
      market assumptions, or internet information.
    - If the context does not contain enough information to answer, state
      exactly what is missing and what evidence would resolve the gap.
    - Do NOT modify, downgrade, or inflate signal levels, evidence scores,
      or confidence values — report them as they appear in the context.
    - NEVER invent citations. Only use [SGn], [Sn], [Dn], [Cn], [Un]
      labels that actually exist in the context pack.

    Special question handling
    -------------------------
    "What are the top 3 risks?" / "Most urgent signals?"
    → Return exactly: three risk signals ranked by level + confidence,
      each with: signal ref [SGn], title, one-line reason it matters,
      recommended action, time horizon.
      Close with: "Before acting, verify:" + highest-uncertainty item.

    "What opportunities exist?"
    → Return all opportunity-direction signals with: ref [SGn], title,
      how to capture it, what evidence supports it.
      Close with: "Next question I'd ask:" + a question about capturing
      the most promising opportunity.

    "What should leadership focus on?" / "This month's priorities?"
    → Return: top 3 signals by urgency and time_horizon, each with
      concrete action. Close with: "Next question I'd ask:"

    "Which signal is most urgent?"
    → Return the single highest-priority signal. Explain why.
      State its time horizon and recommended action.
      Close with: "Before acting, verify:"

    "Which evidence is weak?" / "Where is the evidence thin?"
    → Reference [EVIDENCE_INTEGRITY] and any [Cn]/[Un] citations.
      Identify the signals whose evidence_refs are contested or absent.
      Close with: "Before acting, verify:"

    "What actions should I take this month?"
    → Return: prioritised action list (≤5 items) each tied to a signal [SGn]
      and a time horizon. Close with: "Next question I'd ask:"
    """
).strip()


# ═════════════════════════════════════════════════════════════════════════════
# Answer function
# ═════════════════════════════════════════════════════════════════════════════

def answer_ask_signals_question(
    case: Case,
    signals: List[Signal],
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    user_id: str | None = None,
) -> str:
    """Answer a follow-up question as the Risk & Opportunity Analyst.

    Parameters
    ----------
    case:      The Kulima OS Case this signals pack belongs to.
    signals:   Pre-generated Signal objects for this case.
    question:  The user's free-text question.
    history:   Optional list of prior chat messages
               (each a dict with 'role' and 'content' keys).
               At most the last 8 turns are included.

    Returns
    -------
    A grounded, cited analyst response as a plain string.
    """
    # Build history block — last 8 turns, each clipped
    history_text = "\n".join(
        f"{msg.get('role', 'user').upper()}: {_clip(msg.get('content', ''), 700)}"
        for msg in (history or [])[-8:]
    )

    # Build context pack
    context = build_ask_signals_context(case, signals, user_id=user_id)

    # Dynamic grounding appendix — injected when EIE is present
    system = _SYSTEM_PROMPT
    ei = case.evidence_integrity
    if ei is not None:
        system += (
            f"\n\nEvidence integrity grounding:\n"
            f"This case has been assessed as Grade {ei.integrity_grade.value} "
            f"({ei.integrity_score:.0f}/100) with {ei.evidence_depth.value} depth "
            f"and {ei.consistency_status.value} consistency. "
            f"Cite [EVIDENCE_INTEGRITY] when discussing evidence quality, "
            f"source reliability, or grading. If contradictions [C#] or "
            f"unsupported claims [U#] are relevant to the question, surface "
            f"them explicitly. Do not downplay evidence-quality concerns."
        )

    graph = case.trust_graph
    if graph is not None:
        system += (
            f"\n\nTrust graph grounding:\n"
            f"A trust graph is available for this case — trust score "
            f"{graph.trust_score:.0f}/100, density {graph.density:.2f}, "
            f"{len(graph.nodes)} nodes. "
            f"Cite [TRUST_GRAPH] when discussing ecosystem footprint, "
            f"partner network quality, or relationship-based risks."
        )

    # Compose the user turn
    user = textwrap.dedent(
        f"""
        Context pack:
        {context}

        Session chat history:
        {history_text or "No prior messages."}

        Analyst question:
        {question}
        """
    ).strip()

    return LLMClient().complete(system=system, user=user, temperature=0.2)
