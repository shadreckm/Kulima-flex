"""Offline demo chat responses for Ask IC and Ask Signals.

Uses stored brief / signals data only — no LLM calls.
"""

from __future__ import annotations

from kulima.core.cases.models import Case
from kulima.models import InvestmentBrief
from kulima.signals.models import Signal
from kulima.signals.signals_summary import highest_priority_signals

DEMO_MODE_LABEL = "Demo Mode Response"
DOCUMENT_INTELLIGENCE_LABEL = "Document Intelligence Mode"


def _banner() -> str:
    return (
        f"**{DEMO_MODE_LABEL}**\n\n"
        "Live model APIs are unavailable. This answer is synthesized from the stored "
        "decision snapshot, trust score, evidence integrity, and signals for this run.\n\n"
    )


def _doc_intelligence_banner(brief: "InvestmentBrief") -> str:
    """Banner shown when OpenAI is unavailable in production — uses stored evaluation data."""
    ei = brief.evidence_integrity
    grade = getattr(ei.integrity_grade, "value", ei.integrity_grade) if ei else "—"
    rec = getattr(brief.recommendation, "value", str(brief.recommendation))
    return (
        f"**📄 {DOCUMENT_INTELLIGENCE_LABEL}**\n\n"
        f"*Live AI services are currently unavailable. Answering from stored evaluation data: "
        f"uploaded documents, evidence store, evidence score, trust score, risk score, "
        f"completeness score, and generated reports.*\n\n"
        f"**Evaluation:** {brief.startup_name} · **Recommendation:** {rec} · "
        f"**Trust:** {brief.trust_score:.0f}/100 · "
        f"**Evidence Integrity:** Grade {grade} "
        f"({(ei.integrity_score if ei else 0):.0f}/100)\n\n"
        f"---\n\n"
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


def doc_intelligence_ask_ic_answer(brief: InvestmentBrief, question: str) -> str:
    """Production fallback: answers from stored evaluation data when OpenAI is unavailable.

    Uses: uploaded documents, evidence store, evidence/trust/risk/completeness scores,
    stored evaluation, and generated reports. Never fails silently.
    """
    q = (question or "").lower()
    rec = getattr(brief.recommendation, "value", str(brief.recommendation))
    ei = brief.evidence_integrity
    grade = getattr(ei.integrity_grade, "value", ei.integrity_grade) if ei else "—"
    integrity = f"Grade {grade} ({ei.integrity_score:.0f}/100)" if ei else "Not assessed"

    # Pull uploaded evidence records
    uploaded = getattr(brief, "uploaded_evidence", []) or []
    doc_lines = []
    total_doc_trust = []
    for doc in uploaded[:4]:
        fname = getattr(doc, "filename", None) or str(doc.get("filename", "Document") if isinstance(doc, dict) else "Document")
        score = None
        tb = getattr(doc, "trust_breakdown", None) or (doc.get("trust_breakdown") if isinstance(doc, dict) else None)
        if tb:
            score = getattr(tb, "final_trust_score", None) or (tb.get("final_trust_score") if isinstance(tb, dict) else None)
        if score is None:
            score = getattr(doc, "trust_score", None) or (doc.get("trust_score") if isinstance(doc, dict) else None)
        score_str = f" · Trust {score:.0f}/100" if isinstance(score, (int, float)) else ""
        if isinstance(score, (int, float)):
            total_doc_trust.append(float(score))
        status = getattr(doc, "evidence_status", None) or (doc.get("evidence_status") if isinstance(doc, dict) else None) or "Processed"
        doc_lines.append(f"- **{fname}** ({status}{score_str})")

    avg_doc_trust = f"{sum(total_doc_trust)/len(total_doc_trust):.0f}/100" if total_doc_trust else "—"

    risks = [f"[{rf.severity.upper()}] {rf.title}: {rf.detail}" for rf in (brief.red_flags or [])[:3]]
    if not risks:
        risks = ["No critical red flags recorded in the stored brief."]

    checklist = ei.verification_checklist[:3] if (ei and ei.verification_checklist) else []
    missing = ei.unsupported_claims[:2] if (ei and ei.unsupported_claims) else []
    contradictions = ei.contradictions[:2] if (ei and ei.contradictions) else []

    evidence_section = (
        f"**Uploaded Documents ({len(uploaded)} on file):**\n" + ("\n".join(doc_lines) if doc_lines else "- No documents uploaded yet.") + "\n\n"
        f"**Evidence Scores:**\n"
        f"- Evidence Integrity: {integrity}\n"
        f"- Trust Score: {brief.trust_score:.0f}/100\n"
        f"- Risk Score: {brief.risk_score:.0f}/100\n"
        f"- Document Trust (avg): {avg_doc_trust}\n"
        + (f"- Completeness: {ei.completeness_score:.0f}/100\n" if (ei and hasattr(ei, 'completeness_score') and ei.completeness_score is not None) else "")
    )

    if any(k in q for k in ("invest", "recommend", "should i", "verdict", "decision")):
        body = (
            f"**Recommendation: {rec}** for {brief.startup_name}\n\n"
            + evidence_section +
            f"**Key Rationale:**\n{brief.executive_summary[:280]}\n\n"
            f"**Top Risks:**\n" + "\n".join(f"- {r}" for r in risks) + "\n\n"
            f"**Stored Recommendation:**\n{brief.investment_recommendation[:200]}\n\n"
            f"**Next Step:** {brief.next_steps[0] if brief.next_steps else 'Review Evidence workspace.'}"
        )

    elif any(k in q for k in ("document", "upload", "file", "pdf", "evidence", "source")):
        body = (
            f"**Stored Document Evidence for {brief.startup_name}:**\n\n"
            + evidence_section +
            (f"**Missing Evidence:**\n" + "\n".join(f"- {u.description}" for u in missing) + "\n\n" if missing else "") +
            (f"**Contradictions Detected:**\n" + "\n".join(f"- {c.description}" for c in contradictions) + "\n\n" if contradictions else "") +
            (f"**Verification Checklist:**\n" + "\n".join(f"- {item}" for item in checklist) if checklist else "")
        )

    elif any(k in q for k in ("trust", "score", "integrity", "grade", "reliability")):
        body = (
            f"**Trust & Score Breakdown for {brief.startup_name}:**\n\n"
            f"- Overall Score: {brief.overall_score:.0f}/100\n"
            f"- Trust Score: {brief.trust_score:.0f}/100\n"
            f"- Founder Score: {brief.founder_score:.0f}/100\n"
            f"- Risk Score: {brief.risk_score:.0f}/100\n"
            f"- Evidence Integrity: {integrity}\n"
            f"- Document Trust (avg): {avg_doc_trust}\n\n"
            + evidence_section +
            f"**Confidence Level:** {brief.confidence_level.value} ({brief.confidence:.0%})"
        )

    elif any(k in q for k in ("risk", "red flag", "concern", "warning", "danger")):
        body = (
            f"**Risk Assessment for {brief.startup_name}:**\n\n"
            f"Risk Score: {brief.risk_score:.0f}/100\n\n"
            f"**Red Flags:**\n" + "\n".join(f"- {r}" for r in risks) + "\n\n"
            + (f"**Contradictions in Evidence:**\n" + "\n".join(f"- [{c.severity}] {c.description}" for c in contradictions) + "\n\n" if contradictions else "") +
            f"**Stored Risk Assessment:**\n{brief.risk_assessment[:250]}"
        )

    elif any(k in q for k in ("report", "export", "memo", "download", "pdf")):
        body = (
            f"**Available Reports for {brief.startup_name}:**\n\n"
            f"The following reports have been generated and are available for download:\n"
            f"- Investment Memo (PDF/TXT)\n"
            f"- Full IC Report (PDF/TXT)\n"
            f"- Signals Report (PDF/TXT)\n"
            f"- Due Diligence Summary (PDF/TXT)\n"
            f"- Executive One Pager (PDF/TXT)\n\n"
            f"Use the **Reports** workspace to download any of these. "
            f"They are pre-generated from the stored evaluation and available without AI services.\n\n"
            f"**Evaluation Summary:**\n"
            f"Recommendation: {rec} · Trust: {brief.trust_score:.0f}/100 · Integrity: {integrity}"
        )

    else:
        body = (
            f"**{brief.startup_name}** ({brief.founder_name}) — Recommendation: **{rec}**\n\n"
            + evidence_section +
            f"**Executive Summary:**\n{brief.executive_summary[:280]}\n\n"
            f"**Top Risks:**\n" + "\n".join(f"- {r}" for r in risks[:2]) + "\n\n"
            f"**Next Step:** {brief.next_steps[0] if brief.next_steps else 'Open Evidence and Decision workspaces.'}"
        )

    return _doc_intelligence_banner(brief) + body


def doc_intelligence_ask_signals_answer(case: Case, signals: list[Signal], question: str) -> str:
    """Production fallback for Signals when OpenAI is unavailable.

    Uses stored signals pack, evidence integrity, and case data deterministically.
    """
    from kulima.signals.signals_summary import count_signals_by_level

    q = (question or "").lower()
    subject = case.subject.name if case.subject else "this case"
    top = highest_priority_signals(signals, limit=5)
    counts = count_signals_by_level(signals)
    ei = case.evidence_integrity
    grade = getattr(ei.integrity_grade, "value", ei.integrity_grade) if ei else "—"

    risk_signals = [s for s in signals if getattr(s, "direction", "") == "risk" or s.level.value in {"critical", "high"}][:4]
    opp_signals = [s for s in signals if getattr(s, "direction", "") == "opportunity"][:4]

    counts_line = (
        f"Critical: {counts.get('critical', 0)} · High: {counts.get('high', 0)} · "
        f"Medium: {counts.get('medium', 0)} · Low: {counts.get('low', 0)}"
    )

    summary_section = (
        f"**Signals Summary for {subject}:**\n"
        f"{counts_line}\n"
        f"Evidence Integrity: Grade {grade}\n\n"
    )

    if any(k in q for k in ("top", "risk", "urgent", "critical", "high", "red", "warning")):
        lines = [f"- [{s.level.value.upper()}] **{s.title}**: {s.description[:160]}" for s in risk_signals]
        actions = [f"- {s.recommended_action}" for s in risk_signals if s.recommended_action]
        body = (
            summary_section +
            f"**Top Risk Signals:**\n" + ("\n".join(lines) if lines else "- No high-priority risk signals in stored pack.") + "\n\n"
            + (f"**Recommended Actions:**\n" + "\n".join(actions) + "\n\n" if actions else "") +
            f"**Next:** Prioritise verification on the highest-severity signal before IC committee review."
        )

    elif any(k in q for k in ("opportunit", "upside", "positive", "growth", "strength")):
        lines = [f"- **{s.title}**: {s.recommended_action or s.description[:120]}" for s in opp_signals]
        body = (
            summary_section +
            f"**Opportunity Signals:**\n" + ("\n".join(lines) if lines else "- No explicit opportunity signals in stored pack.") + "\n\n"
            f"**Next:** Validate the strongest opportunity signal with independent corroboration."
        )

    elif any(k in q for k in ("all", "list", "show", "summary", "overview")):
        all_lines = [f"- [{s.level.value.upper()}] {s.title}" for s in top]
        body = (
            summary_section +
            f"**All Top Signals ({len(signals)} total):**\n" + ("\n".join(all_lines) if all_lines else "- No signals available.") + "\n\n"
            f"Open the **Signals** workspace context panel for the full breakdown with confidence scores."
        )

    else:
        top_lines = [f"- [{s.level.value.upper()}] {s.title}: {s.description[:140]}" for s in top[:3]]
        body = (
            summary_section +
            f"**Stored Signals ({len(signals)} total):**\n" + ("\n".join(top_lines) if top_lines else "- No signals available.") + "\n\n"
            f"**Next:** Use the Signals workspace and Evidence panel for citation-backed detail.\n\n"
            f"**Your question:** {question}"
        )

    # Build a document-intelligence banner adapted for signals
    ei_obj = case.evidence_integrity
    grade_v = getattr(ei_obj.integrity_grade, "value", ei_obj.integrity_grade) if ei_obj else "—"
    banner = (
        f"**📄 {DOCUMENT_INTELLIGENCE_LABEL}**\n\n"
        f"*Live AI services are currently unavailable. Answering from stored signals pack "
        f"({len(signals)} signals) and evidence integrity data (Grade {grade_v}).*\n\n"
        f"---\n\n"
    )
    return banner + body
