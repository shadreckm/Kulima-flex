"""Offline demo chat responses for Ask IC and Ask Signals.

Uses stored brief / signals data only — no LLM calls.
"""

from __future__ import annotations

from kulima.core.cases.models import Case
from kulima.models import InvestmentBrief
from kulima.signals.models import Signal
from kulima.signals.signals_summary import highest_priority_signals

DEMO_MODE_LABEL = "Demo Mode Response"


def _banner() -> str:
    return (
        f"**{DEMO_MODE_LABEL}**\n\n"
        "Live model APIs are unavailable. This answer is synthesized from the stored "
        "decision snapshot, trust score, evidence integrity, and signals for this run.\n\n"
    )


def demo_ask_ic_answer(brief: InvestmentBrief, question: str) -> str:
    q = (question or "").lower()
    rec = getattr(brief.recommendation, "value", str(brief.recommendation))
    ei = brief.evidence_integrity
    grade = getattr(ei.integrity_grade, "value", ei.integrity_grade) if ei else "—"
    integrity = f"{grade} ({ei.integrity_score:.0f}/100)" if ei else "Not assessed"

    reasons = [
        brief.executive_summary,
        brief.investment_recommendation,
        f"Overall score {brief.overall_score:.0f}/100 with trust {brief.trust_score:.0f}/100.",
    ]
    risks = [f"[{rf.severity.upper()}] {rf.title}: {rf.detail}" for rf in (brief.red_flags or [])[:3]]
    if not risks:
        risks = ["No critical red flags recorded in the stored brief."]

    if any(k in q for k in ("invest", "recommend", "should i", "verdict")):
        body = (
            f"**Short Answer:** Recommendation is **{rec}** for {brief.startup_name}.\n\n"
            f"**Why This Matters:**\n"
            f"- Trust score {brief.trust_score:.0f}/100\n"
            f"- Evidence integrity {integrity}\n"
            f"- Confidence {brief.confidence_level.value} ({brief.confidence:.0%})\n\n"
            f"**Supporting Evidence:**\n- {reasons[0][:220]}\n\n"
            f"**Top Risks:**\n" + "\n".join(f"- {r}" for r in risks) + "\n\n"
            f"**Recommended Next Step:** {brief.next_steps[0] if brief.next_steps else brief.investment_recommendation[:160]}\n\n"
            f"**Next question I'd ask:** What verification item would change this from {rec}?"
        )
    elif any(k in q for k in ("weak", "evidence", "integrity", "contradiction")):
        contradictions = ei.contradictions if ei else []
        unsupported = ei.unsupported_claims if ei else []
        body = (
            f"**Short Answer:** Evidence integrity is **{integrity}**.\n\n"
            f"**Why This Matters:**\n"
            f"- Contradictions found: {len(contradictions)}\n"
            f"- Unsupported claims: {len(unsupported)}\n"
            f"- Depth: {getattr(ei.evidence_depth, 'value', ei.evidence_depth) if ei else '—'}\n\n"
            f"**Supporting Evidence:**\n- {ei.integrity_summary if ei else brief.risk_assessment[:220]}\n\n"
            f"**Recommended Next Step:** Review the Evidence workspace verification checklist.\n\n"
            f"**Before making a decision, I'd verify:** "
            + (ei.verification_checklist[0] if ei and ei.verification_checklist else "Primary traction and legal claims.")
        )
    elif any(k in q for k in ("observe", "pass", "why not")):
        body = (
            f"**Short Answer:** {brief.startup_name} is **{rec}** because stored evidence and risk posture "
            f"do not support a higher conviction action.\n\n"
            f"**Why This Matters:**\n"
            f"- Trust {brief.trust_score:.0f}/100 vs peer cohort\n"
            f"- Integrity {integrity}\n"
            f"- Risk score {brief.risk_score:.0f}/100 (lower is better)\n\n"
            f"**Recommended Next Step:** {brief.investment_recommendation[:200]}\n\n"
            f"**Next question I'd ask:** Which milestone would move this case off {rec}?"
        )
    else:
        body = (
            f"**Short Answer:** {brief.startup_name} ({brief.founder_name}) is currently **{rec}** "
            f"with trust {brief.trust_score:.0f}/100.\n\n"
            f"**Why This Matters:**\n"
            f"- {reasons[0][:180]}\n"
            f"- Founder score {brief.founder_score:.0f}/100 · Startup {brief.startup_score:.0f}/100\n\n"
            f"**Top Risks:**\n" + "\n".join(f"- {r}" for r in risks[:2]) + "\n\n"
            f"**Recommended Next Step:** Open the Decision Snapshot and Evidence panels for this run.\n\n"
            f"**Next question I'd ask:** {question}"
        )

    return _banner() + body


def demo_ask_signals_answer(case: Case, signals: list[Signal], question: str) -> str:
    q = (question or "").lower()
    top = highest_priority_signals(signals, limit=3)
    subject = case.subject.name if case.subject else "this case"
    risk_lines = [
        f"[{s.level.value.upper()}] {s.title}: {s.description[:160]}"
        for s in top
        if getattr(s, "direction", "") == "risk" or s.level.value in {"critical", "high"}
    ][:3]
    if not risk_lines and top:
        risk_lines = [f"[{s.level.value.upper()}] {s.title}: {s.description[:160]}" for s in top]

    ei = case.evidence_integrity
    grade = getattr(ei.integrity_grade, "value", ei.integrity_grade) if ei else "—"

    if any(k in q for k in ("top", "risk", "urgent", "critical")):
        body = (
            f"**Short Answer:** The most urgent stored signals for {subject} are listed below.\n\n"
            f"**Why This Matters:**\n"
            + ("\n".join(f"- {line}" for line in risk_lines) or "- No high-priority risk signals in stored pack.") + "\n\n"
            f"**Recommended Action:** Prioritise verification on the highest-severity signal before IC.\n\n"
            f"**Before acting, verify:** "
            + (ei.verification_checklist[0] if ei and ei.verification_checklist else "Signal evidence references.")
        )
    elif any(k in q for k in ("opportunit", "upside", "positive")):
        opps = [s for s in signals if getattr(s, "direction", "") == "opportunity"][:3]
        opp_lines = [f"- {s.title}: {s.recommended_action or s.description[:120]}" for s in opps]
        body = (
            f"**Short Answer:** Stored opportunity signals for {subject}.\n\n"
            + ("\n".join(opp_lines) if opp_lines else "- No explicit opportunity signals tagged in stored pack.") + "\n\n"
            f"**Next question I'd ask:** Which opportunity signal has the strongest evidence backing?"
        )
    else:
        body = (
            f"**Short Answer:** {len(signals)} stored signals available for {subject} "
            f"(integrity Grade {grade}).\n\n"
            f"**Why This Matters:**\n"
            + ("\n".join(f"- {line}" for line in risk_lines) or "- Review Signals summary counts in the context panel.") + "\n\n"
            f"**Recommended Action:** Use the Signals workspace summary, then drill into Evidence for citations.\n\n"
            f"**Next question I'd ask:** {question}"
        )

    return _banner() + body
