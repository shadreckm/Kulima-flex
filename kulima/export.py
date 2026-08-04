"""Memo and Investment Committee report export (TXT + PDF)."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import re
from typing import Any


def _load_reportlab_symbols() -> tuple[Any, ...]:
    try:
        from reportlab.lib import colors as colors_
        from reportlab.lib.enums import TA_CENTER as TA_CENTER_, TA_JUSTIFY as TA_JUSTIFY_
        from reportlab.lib.pagesizes import A4 as A4_
        from reportlab.lib.styles import (
            ParagraphStyle as ParagraphStyle_,
            getSampleStyleSheet as getSampleStyleSheet_,
        )
        from reportlab.lib.units import inch as inch_
        from reportlab.platypus import (
            Paragraph as Paragraph_,
            SimpleDocTemplate as SimpleDocTemplate_,
            Spacer as Spacer_,
            Table as Table_,
            TableStyle as TableStyle_,
        )
        return (
            colors_,
            TA_CENTER_,
            TA_JUSTIFY_,
            A4_,
            ParagraphStyle_,
            getSampleStyleSheet_,
            inch_,
            Paragraph_,
            SimpleDocTemplate_,
            Spacer_,
            Table_,
            TableStyle_,
        )
    except ImportError:
        return (None,) * 12


colors, TA_CENTER, TA_JUSTIFY, A4, ParagraphStyle, getSampleStyleSheet, inch, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle = _load_reportlab_symbols()

from kulima.core.cases.adapters import from_investment_brief
from kulima.core.documents.context import build_document_context_for_subject
from kulima.models import EvidenceIntegrityReport, InvestmentBrief
from kulima.signals.models import Signal
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.signals_summary import count_signals_by_level, highest_priority_signals


# ── Trust Layer helpers ───────────────────────────────────────────────────────

def _ei_reliability_line(ei: EvidenceIntegrityReport) -> str:
    """Single-line reliability summary for use in text exports and PDF meta."""
    depth_label = ei.evidence_depth.value.capitalize()
    if ei.sparse_mode:
        depth_label = "Limited Coverage"
    consistency = ei.consistency_status.value.replace("_", " ").capitalize()
    return (
        f"Reliability Rating: {ei.integrity_grade.value} "
        f"({ei.integrity_score:.0f}/100) | "
        f"Evidence Depth: {depth_label} | "
        f"Consistency: {consistency}"
    )


def _ei_verification_items(ei: EvidenceIntegrityReport) -> list[str]:
    """Return actionable verification items from contradictions and unsupported claims."""
    items: list[str] = []
    for c in ei.contradictions:
        a_val = c.claim_a.value_raw or "—"
        b_val = c.claim_b.value_raw or "—"
        action = c.recommended_action or "Verify with founder before IC."
        items.append(
            f"Sources disagree on {c.claim_a.claim_type.value.replace('_', ' ')}: "
            f'"{a_val}" vs "{b_val}". {action}'
        )
    for u in ei.unsupported_claims:
        action = u.recommended_action or "Request primary data from founder."
        items.append(f"{u.description} {action}")
    return items


def _slug(brief: InvestmentBrief) -> str:
    raw = f"{brief.founder_name}_{brief.startup_name}".strip("_")
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return cleaned[:80] or "kulima_deal"


def export_filenames(brief: InvestmentBrief) -> dict[str, str]:
    base = _slug(brief)
    return {
        "memo_txt": f"Kulima_IC_Memo_{base}.txt",
        "memo_pdf": f"Kulima_IC_Memo_{base}.pdf",
        "report_txt": f"Kulima_Full_IC_Report_{base}.txt",
        "report_pdf": f"Kulima_Full_IC_Report_{base}.pdf",
        "signals_txt": f"Kulima_Signals_Report_{base}.txt",
        "signals_pdf": f"Kulima_Signals_Report_{base}.pdf",
        "dd_txt": f"Kulima_Due_Diligence_Summary_{base}.txt",
        "dd_pdf": f"Kulima_Due_Diligence_Summary_{base}.pdf",
        "onepager_txt": f"Kulima_Executive_One_Pager_{base}.txt",
        "onepager_pdf": f"Kulima_Executive_One_Pager_{base}.pdf",
    }


def build_memo_text(brief: InvestmentBrief) -> str:
    steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(brief.next_steps, 1)) or "  —"

    # Trust Layer — reliability line for header block (gated)
    reliability_line = ""
    if brief.evidence_integrity:
        reliability_line = (
            f"\n{_ei_reliability_line(brief.evidence_integrity)}"
        )

    # Trust Layer — verification section (gated on actionable findings)
    verification_section = ""
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        items = _ei_verification_items(ei)
        if items:
            numbered = "\n".join(f"  {i}. {item}" for i, item in enumerate(items, 1))
            verification_section = f"""
----------------------------------------
EVIDENCE VERIFICATION REQUIRED
----------------------------------------
Before IC presentation, verify the following from primary sources:

{numbered}
"""
        else:
            depth_label = (
                "Limited Coverage" if ei.sparse_mode
                else ei.evidence_depth.value.capitalize()
            )
            verification_section = f"""
----------------------------------------
EVIDENCE NOTE
----------------------------------------
Key facts in this memo are consistently supported across {ei.source_count} independently
reviewed sources. Evidence Depth: {depth_label}.
"""

    return f"""KULIMA FLEX — INVESTMENT COMMITTEE MEMO
========================================
Deal: {brief.founder_name} / {brief.startup_name}
Sector: {brief.sector or "—"} | Geography: {brief.geography or "—"} | Stage: {brief.stage or "—"}
Recommendation: {brief.recommendation.value}
Overall Score: {brief.overall_score:.0f}/100 | Confidence: {brief.confidence_level.value}{reliability_line}
Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

----------------------------------------
1. EXECUTIVE SUMMARY
----------------------------------------
{brief.executive_summary or "—"}

----------------------------------------
2. FOUNDER ASSESSMENT
----------------------------------------
{brief.founder_assessment or "—"}

----------------------------------------
3. STARTUP ASSESSMENT
----------------------------------------
{brief.startup_assessment or "—"}

----------------------------------------
4. MARKET ASSESSMENT
----------------------------------------
{brief.market_assessment or "—"}

----------------------------------------
5. RISK ASSESSMENT
----------------------------------------
{brief.risk_assessment or "—"}

----------------------------------------
6. INVESTMENT RECOMMENDATION
----------------------------------------
{brief.investment_recommendation or brief.recommendation.value}

----------------------------------------
7. NEXT STEPS
----------------------------------------
{steps}

----------------------------------------
SCORECARD
----------------------------------------
Founder: {brief.founder_score:.0f}/100
Startup: {brief.startup_score:.0f}/100
Market: {brief.market_score:.0f}/100
Trust: {brief.trust_score:.0f}/100
Risk (lower better): {brief.risk_score:.0f}/100
Growth Potential: {brief.growth_potential:.0f}/100
Investment Readiness: {brief.investment_readiness:.0f}/100
{verification_section}
— End of Memo —
Generated by Kulima FLEX AI Investment Intelligence OS
""".strip()


def build_full_ic_report_text(brief: InvestmentBrief) -> str:
    parts = [
        build_memo_text(brief),
        "",
        "=" * 60,
        "FULL INVESTMENT COMMITTEE REPORT",
        "=" * 60,
        "",
    ]

    # Trust Layer — Evidence Reliability Report (gated)
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = (
            "Limited Coverage" if ei.sparse_mode
            else ei.evidence_depth.value.capitalize()
        )
        consistency = ei.consistency_status.value.replace("_", " ").capitalize()

        parts.append("EVIDENCE RELIABILITY REPORT")
        parts.append("-" * 40)
        parts.append(
            f"[RELIABILITY]\n"
            f"Rating: {ei.integrity_grade.value} ({ei.integrity_score:.0f}/100)\n"
            f"Depth: {depth_label}\n"
            f"Consistency: {consistency}\n"
            f"Summary: {ei.integrity_summary or '—'}\n"
            f"Sources reviewed: {ei.source_count} | "
            f"Claims extracted: {ei.claim_count} | "
            f"High-authority sources: {ei.high_authority_count}"
        )

        if ei.contradictions:
            parts.append("")
            parts.append("Conflicts detected:")
            for i, c in enumerate(ei.contradictions, 1):
                a_val = c.claim_a.value_raw or "—"
                b_val = c.claim_b.value_raw or "—"
                parts.append(
                    f"  [C{i}] {c.severity.value.upper()} — "
                    f"{c.claim_a.claim_type.value.replace('_', ' ').capitalize()}: "
                    f'"{a_val}" vs "{b_val}"'
                )
                if c.recommended_action:
                    parts.append(f"       Action: {c.recommended_action}")

        if ei.unsupported_claims:
            parts.append("")
            parts.append("Unverified claims:")
            for i, u in enumerate(ei.unsupported_claims, 1):
                parts.append(f"  [U{i}] {u.description}")
                if u.recommended_action:
                    parts.append(f"       Action: {u.recommended_action}")

        if ei.verification_checklist:
            parts.append("")
            parts.append("Recommended Action:")
            for i, item in enumerate(ei.verification_checklist, 1):
                parts.append(f"  {i}. {item}")

        parts.append("")

    # Red flags
    parts.append("RED FLAG ALERTS")
    parts.append("-" * 40)
    if brief.red_flags:
        for rf in brief.red_flags:
            parts.append(f"[{rf.severity.upper()}] {rf.title}")
            parts.append(f"  Detail: {rf.detail}")
            parts.append(f"  Mitigation: {rf.mitigation or 'TBD'}")
            parts.append("")
    else:
        parts.append("No critical red flags surfaced.")
        parts.append("")

    # Twin Syndicate
    parts.append("TWIN SYNDICATE INVESTMENT COMMITTEE")
    parts.append("-" * 40)
    if brief.syndicate:
        syn = brief.syndicate
        final = syn.final_recommendation or syn.majority_vote
        parts.append(f"Final Recommendation: {final.value}")
        parts.append(
            f"Consensus Score: {syn.consensus_score or syn.average_score:.0f}/100"
        )
        parts.append(
            f"Dissent Score: {syn.dissent_score or syn.dissent_index * 100:.0f}/100"
        )
        if syn.consensus_thesis:
            parts.append(f"Consensus Thesis: {syn.consensus_thesis}")
        parts.append("")
        for v in syn.votes:
            role = v.title or v.persona
            parts.append(f"• {role} ({v.investor_name}, {v.firm})")
            parts.append(
                f"  Decision: {v.decision.value} | Confidence: {v.confidence_score:.0f}/100"
            )
            parts.append(f"  Reasoning: {v.key_reasoning or v.thesis}")
            parts.append(f"  Major Concern: {v.major_concern or '—'}")
            parts.append("")
        if syn.debate_transcript:
            parts.append("IC Debate Transcript:")
            parts.append(syn.debate_transcript)
            parts.append("")
        if syn.blocking_concerns:
            parts.append("Blocking Concerns: " + "; ".join(syn.blocking_concerns))
            parts.append("")
    else:
        parts.append("Syndicate not convened.")
        parts.append("")

    # Continental Futures
    parts.append("CONTINENTAL FUTURES SIMULATOR")
    parts.append("-" * 40)
    if brief.future_simulation:
        fs = brief.future_simulation
        parts.append(f"Most Likely Case: {fs.most_likely_case or '—'}")
        parts.append(f"Africa Risk Premium: {fs.africa_risk_premium:.1f} pp")
        parts.append(f"Expected Value (36m): ${fs.expected_value_usd:,.0f}")
        if fs.africa_conditions_summary:
            parts.append(f"Africa Conditions: {fs.africa_conditions_summary}")
        parts.append("")
        for s in fs.scenarios:
            parts.append(f"{s.emoji} {s.name}")
            parts.append(f"  Success Probability: {s.success_probability:.0f}%")
            parts.append(
                f"  Investor Attractiveness: {s.investor_attractiveness_score:.0f}/100"
            )
            parts.append(
                f"  Revenue Growth Outlook: {s.revenue_growth_outlook or s.narrative}"
            )
            if s.major_risks:
                parts.append("  Major Risks:")
                for r in s.major_risks:
                    parts.append(f"    - {r}")
            if s.key_opportunities:
                parts.append("  Key Opportunities:")
                for o in s.key_opportunities:
                    parts.append(f"    - {o}")
            parts.append("")
    else:
        parts.append("Futures simulation not available.")
        parts.append("")

    # Trust graph
    parts.append("TRUST GRAPH")
    parts.append("-" * 40)
    if brief.trust_graph:
        parts.append(brief.trust_graph.explanation)
        parts.append(
            f"Nodes: {len(brief.trust_graph.nodes)} | Edges: {len(brief.trust_graph.edges)} | "
            f"Density: {brief.trust_graph.density:.2f} | Trust Score: {brief.trust_graph.trust_score:.0f}"
        )
        for n in brief.trust_graph.nodes:
            parts.append(f"  - [{n.node_type}] {n.label} (weight {n.weight:.2f})")
        parts.append("")
    else:
        parts.append("Trust graph not available.")
        parts.append("")

    # Sources
    parts.append("SOURCE ATTRIBUTION")
    parts.append("-" * 40)
    if brief.sources:
        for i, src in enumerate(brief.sources, 1):
            parts.append(f"[{i}] {src.title}")
            parts.append(f"    URL: {src.url}")
            parts.append(
                f"    Type: {src.source_type} | Relevance: {src.relevance:.2f} | Confidence: {src.confidence_score:.2f}"
            )
            snippet = (src.snippet or "")[:280]
            if snippet:
                parts.append(f"    Excerpt: {snippet}")
            parts.append("")
    else:
        parts.append("No sources attached.")
        parts.append("")

    # Explainability
    parts.append("EXPLAINABLE AI DECISIONS")
    parts.append("-" * 40)
    for reason in brief.explainability:
        parts.append(f"• {reason}")
    parts.append("")
    parts.append("— End of Full Investment Committee Report —")
    parts.append("Generated by Kulima FLEX AI Investment Intelligence OS")
    return "\n".join(parts)


def _pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="KulimaTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0B3D2E"),
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaH2",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#0B6E4F"),
            spaceBefore=14,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaBody",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#1F2A24"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaMeta",
            parent=styles["Normal"],
            fontSize=8.5,
            textColor=colors.HexColor("#5B6F64"),
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaBullet",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            leftIndent=8,
            textColor=colors.HexColor("#1F2A24"),
        )
    )
    # ── Trust Layer styles ────────────────────────────────────────────────────
    styles.add(
        ParagraphStyle(
            name="KulimaIntegrityGrade",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#0B3D2E"),
            fontName="Helvetica-Bold",
            spaceBefore=4,
            spaceAfter=4,
            leftIndent=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaVerification",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#7A3B00"),
            leftIndent=8,
            spaceBefore=2,
            spaceAfter=2,
        )
    )
    return styles


def _esc(text: str) -> str:
    return (
        (text or "—")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _build_pdf(brief: InvestmentBrief, full_report: bool = False) -> bytes:
    if any(
        symbol is None
        for symbol in (
            colors,
            TA_CENTER,
            TA_JUSTIFY,
            A4,
            ParagraphStyle,
            getSampleStyleSheet,
            inch,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    ):
        text = build_full_ic_report_text(brief) if full_report else build_memo_text(brief)
        return text.encode("utf-8")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=f"Kulima IC {'Report' if full_report else 'Memo'} — {brief.founder_name}",
        author="Kulima FLEX",
    )
    styles = _pdf_styles()
    story: list = []

    title = (
        "Kulima FLEX — Full Investment Committee Report"
        if full_report
        else "Kulima FLEX — Investment Committee Memo"
    )
    story.append(Paragraph(title, styles["KulimaTitle"]))
    story.append(
        Paragraph(
            f"{_esc(brief.founder_name)} / {_esc(brief.startup_name)} &nbsp;·&nbsp; "
            f"Recommendation: <b>{_esc(brief.recommendation.value)}</b> &nbsp;·&nbsp; "
            f"Overall {brief.overall_score:.0f}/100"
            + (
                f" &nbsp;·&nbsp; Reliability: <b>{brief.evidence_integrity.integrity_grade.value}</b>"
                if brief.evidence_integrity else ""
            ),
            styles["KulimaMeta"],
        )
    )
    story.append(
        Paragraph(
            f"Sector: {_esc(brief.sector or '—')} | Geography: {_esc(brief.geography or '—')} | "
            f"Stage: {_esc(brief.stage or '—')} | "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["KulimaMeta"],
        )
    )

    score_data = [
        ["Founder", "Startup", "Market", "Trust", "Risk↓", "Overall"],
        [
            f"{brief.founder_score:.0f}",
            f"{brief.startup_score:.0f}",
            f"{brief.market_score:.0f}",
            f"{brief.trust_score:.0f}",
            f"{brief.risk_score:.0f}",
            f"{brief.overall_score:.0f}",
        ],
    ]
    table = Table(score_data, colWidths=[1.1 * inch] * 6)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3D2E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#E7F0EA")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A8BDB2")),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    # Trust Layer — Evidence Reliability Report page (full report only, gated)
    if full_report and brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = (
            "Limited Coverage" if ei.sparse_mode
            else ei.evidence_depth.value.capitalize()
        )
        consistency = ei.consistency_status.value.replace("_", " ").capitalize()

        story.append(Paragraph("Evidence Reliability Report", styles["KulimaH2"]))
        story.append(
            Paragraph(
                f"<b>Rating: {_esc(ei.integrity_grade.value)} "
                f"({ei.integrity_score:.0f}/100)</b> &nbsp;·&nbsp; "
                f"Depth: {_esc(depth_label)} &nbsp;·&nbsp; "
                f"Consistency: {_esc(consistency)}<br/>"
                f"Sources reviewed: {ei.source_count} &nbsp;·&nbsp; "
                f"Claims extracted: {ei.claim_count} &nbsp;·&nbsp; "
                f"High-authority sources: {ei.high_authority_count}",
                styles["KulimaIntegrityGrade"],
            )
        )
        if ei.integrity_summary:
            story.append(Paragraph(_esc(ei.integrity_summary), styles["KulimaBody"]))
        story.append(Spacer(1, 6))

        if ei.contradictions:
            story.append(
                Paragraph("<b>Conflicts detected:</b>", styles["KulimaBody"])
            )
            for i, c in enumerate(ei.contradictions, 1):
                a_val = c.claim_a.value_raw or "—"
                b_val = c.claim_b.value_raw or "—"
                claim_label = c.claim_a.claim_type.value.replace("_", " ").capitalize()
                action = c.recommended_action or "Verify with founder."
                story.append(
                    Paragraph(
                        f"[C{i}] <b>{_esc(c.severity.value.upper())}</b> — "
                        f"{_esc(claim_label)}: "
                        f"&ldquo;{_esc(a_val)}&rdquo; vs &ldquo;{_esc(b_val)}&rdquo;<br/>"
                        f"<i>Action: {_esc(action)}</i>",
                        styles["KulimaVerification"],
                    )
                )
            story.append(Spacer(1, 4))

        if ei.unsupported_claims:
            story.append(
                Paragraph("<b>Unverified claims:</b>", styles["KulimaBody"])
            )
            for i, u in enumerate(ei.unsupported_claims, 1):
                action = u.recommended_action or "Request primary data from founder."
                story.append(
                    Paragraph(
                        f"[U{i}] {_esc(u.description)}<br/>"
                        f"<i>Action: {_esc(action)}</i>",
                        styles["KulimaVerification"],
                    )
                )
            story.append(Spacer(1, 4))

        if ei.verification_checklist:
            story.append(
                Paragraph("<b>Verification checklist:</b>", styles["KulimaBody"])
            )
            for idx, item in enumerate(ei.verification_checklist, 1):
                story.append(
                    Paragraph(f"{idx}. {_esc(item)}", styles["KulimaVerification"])
                )
        story.append(Spacer(1, 8))

    sections = [
        ("1. Executive Summary", brief.executive_summary),
        ("2. Founder Assessment", brief.founder_assessment),
        ("3. Startup Assessment", brief.startup_assessment),
        ("4. Market Assessment", brief.market_assessment),
        ("5. Risk Assessment", brief.risk_assessment),
        (
            "6. Investment Recommendation",
            brief.investment_recommendation or brief.recommendation.value,
        ),
    ]
    for heading, body in sections:
        story.append(Paragraph(heading, styles["KulimaH2"]))
        story.append(Paragraph(_esc(body), styles["KulimaBody"]))
        # Trust Layer — append verification block after Risk Assessment (gated)
        if heading.startswith("5.") and brief.evidence_integrity:
            ei = brief.evidence_integrity
            v_items = _ei_verification_items(ei)
            if v_items:
                story.append(
                    Paragraph(
                        "<b>Evidence Verification Required</b>",
                        styles["KulimaIntegrityGrade"],
                    )
                )
                story.append(
                    Paragraph(
                        "Before IC presentation, verify the following from primary sources:",
                        styles["KulimaVerification"],
                    )
                )
                for item in v_items:
                    story.append(
                        Paragraph(f"• {_esc(item)}", styles["KulimaVerification"])
                    )
                story.append(Spacer(1, 4))

    story.append(Paragraph("7. Next Steps", styles["KulimaH2"]))
    if brief.next_steps:
        for idx, step in enumerate(brief.next_steps, 1):
            story.append(Paragraph(f"{idx}. {_esc(step)}", styles["KulimaBullet"]))
    else:
        story.append(Paragraph("—", styles["KulimaBody"]))

    if full_report:
        story.append(Paragraph("Red Flag Alerts", styles["KulimaH2"]))
        if brief.red_flags:
            for rf in brief.red_flags:
                story.append(
                    Paragraph(
                        f"<b>[{_esc(rf.severity.upper())}] {_esc(rf.title)}</b><br/>"
                        f"{_esc(rf.detail)}<br/>"
                        f"<i>Mitigation: {_esc(rf.mitigation or 'TBD')}</i>",
                        styles["KulimaBody"],
                    )
                )
                story.append(Spacer(1, 6))
        else:
            story.append(
                Paragraph("No critical red flags surfaced.", styles["KulimaBody"])
            )

        story.append(
            Paragraph("Twin Syndicate Investment Committee", styles["KulimaH2"])
        )
        if brief.syndicate:
            syn = brief.syndicate
            final = syn.final_recommendation or syn.majority_vote
            story.append(
                Paragraph(
                    f"Final Recommendation: <b>{_esc(final.value)}</b> | "
                    f"Consensus: {syn.consensus_score or syn.average_score:.0f}/100 | "
                    f"Dissent: {syn.dissent_score or syn.dissent_index * 100:.0f}/100",
                    styles["KulimaBody"],
                )
            )
            if syn.consensus_thesis:
                story.append(
                    Paragraph(_esc(syn.consensus_thesis), styles["KulimaBody"])
                )
            for v in syn.votes:
                role = v.title or v.persona
                story.append(
                    Paragraph(
                        f"<b>{_esc(role)}</b> — {_esc(v.decision.value)} "
                        f"(Confidence {v.confidence_score:.0f}/100)<br/>"
                        f"{_esc(v.investor_name)} · {_esc(v.firm)}<br/>"
                        f"<b>Reasoning:</b> {_esc(v.key_reasoning or v.thesis)}<br/>"
                        f"<b>Major Concern:</b> {_esc(v.major_concern or '—')}",
                        styles["KulimaBody"],
                    )
                )
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("Syndicate not convened.", styles["KulimaBody"]))

        story.append(Paragraph("Continental Futures Simulator", styles["KulimaH2"]))
        if brief.future_simulation:
            fs = brief.future_simulation
            story.append(
                Paragraph(
                    f"Most Likely: {_esc(fs.most_likely_case or '—')} | "
                    f"Africa Risk Premium: {fs.africa_risk_premium:.1f} pp | "
                    f"EV 36m: ${fs.expected_value_usd:,.0f}",
                    styles["KulimaBody"],
                )
            )
            if fs.africa_conditions_summary:
                story.append(
                    Paragraph(_esc(fs.africa_conditions_summary), styles["KulimaBody"])
                )
            for s in fs.scenarios:
                risks = "; ".join(s.major_risks) or "—"
                opps = "; ".join(s.key_opportunities) or "—"
                story.append(
                    Paragraph(
                        f"<b>{_esc(s.emoji + ' ' + s.name)}</b><br/>"
                        f"Success Probability: {s.success_probability:.0f}% | "
                        f"Investor Attractiveness: {s.investor_attractiveness_score:.0f}/100<br/>"
                        f"Revenue Growth Outlook: {_esc(s.revenue_growth_outlook or s.narrative)}<br/>"
                        f"Major Risks: {_esc(risks)}<br/>"
                        f"Key Opportunities: {_esc(opps)}",
                        styles["KulimaBody"],
                    )
                )
                story.append(Spacer(1, 4))
        else:
            story.append(
                Paragraph("Futures simulation not available.", styles["KulimaBody"])
            )

        story.append(Paragraph("Source Attribution", styles["KulimaH2"]))
        if brief.sources:
            for i, src in enumerate(brief.sources, 1):
                story.append(
                    Paragraph(
                        f"[{i}] <b>{_esc(src.title)}</b><br/>{_esc(src.url)}",
                        styles["KulimaBody"],
                    )
                )
        else:
            story.append(Paragraph("No sources attached.", styles["KulimaBody"]))

        story.append(Paragraph("Explainable AI Decisions", styles["KulimaH2"]))
        for reason in brief.explainability:
            story.append(Paragraph(f"• {_esc(reason)}", styles["KulimaBullet"]))

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "Confidential — Generated by Kulima FLEX AI Investment Intelligence OS for Africa",
            styles["KulimaMeta"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def build_memo_pdf(brief: InvestmentBrief) -> bytes:
    return _build_pdf(brief, full_report=False)


def build_full_ic_report_pdf(brief: InvestmentBrief) -> bytes:
    return _build_pdf(brief, full_report=True)


def _brief_case_and_signals(brief: InvestmentBrief) -> tuple[object, list[Signal]]:
    case = from_investment_brief(
        brief,
        case_id=f"reports::{brief.founder_name}::{brief.startup_name}",
        created_by="report_exports",
    )
    signals = SignalsOrchestrator().generate(case)
    return case, signals


def _brief_document_lines(brief: InvestmentBrief, max_documents: int = 3) -> list[str]:
    doc_section = build_document_context_for_subject(
        brief.founder_name,
        brief.startup_name,
        max_documents=max_documents,
        max_chars=2400,
    )
    if not doc_section:
        return ["No documents attached to this run."]
    return [line for line in doc_section.splitlines() if line.strip()]


def build_signals_report_text(brief: InvestmentBrief) -> str:
    _, signals = _brief_case_and_signals(brief)
    counts = count_signals_by_level(signals)
    parts = [
        "KULIMA FLEX — SIGNALS REPORT",
        "=" * 40,
        f"Deal: {brief.founder_name} / {brief.startup_name}",
        f"Recommendation: {brief.recommendation.value} | Overall Score: {brief.overall_score:.0f}/100",
        f"Confidence: {brief.confidence_level.value} ({brief.confidence:.2f})",
    ]
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = "Limited Coverage" if ei.sparse_mode else ei.evidence_depth.value.capitalize()
        parts.append(
            f"Reliability: {ei.integrity_grade.value} ({ei.integrity_score:.0f}/100) | "
            f"Depth: {depth_label} | Consistency: {ei.consistency_status.value}"
        )
    from kulima.signals.models import SignalLevel
    parts.extend([
        "",
        "SIGNALS OVERVIEW",
        "-" * 40,
        f"Total signals: {len(signals)}",
        f"Critical: {counts.get(SignalLevel.CRITICAL, 0)}",
        f"High: {counts.get(SignalLevel.HIGH, 0)}",
        f"Medium: {counts.get(SignalLevel.MEDIUM, 0)}",
        f"Low: {counts.get(SignalLevel.LOW, 0)}",
        "",
    ])
    for idx, sig in enumerate(highest_priority_signals(signals), 1):
        refs = ", ".join(sig.evidence_refs) if sig.evidence_refs else "—"
        parts.extend(
            [
                f"[SG{idx}] {sig.level.value.upper()} · {sig.category.value.title()} · {sig.title}",
                f"Direction: {sig.direction}",
                f"Description: {sig.description}",
                f"Evidence refs: {refs}",
                f"Action: {sig.recommended_action or '—'}",
                f"Confidence: {sig.confidence:.2f}",
                f"Time horizon: {sig.time_horizon or '—'}",
                "",
            ]
        )
    return "\n".join(parts).strip()


def build_signals_report_pdf(brief: InvestmentBrief) -> bytes:
    _, signals = _brief_case_and_signals(brief)
    counts = count_signals_by_level(signals)
    section_lines: list[tuple[str, list[str]]] = []
    overview = [
        f"Total signals: {len(signals)}",
        f"Critical: {counts.get(__import__('kulima.signals.models').signals.models.SignalLevel.CRITICAL, 0)}",
        f"High: {counts.get(__import__('kulima.signals.models').signals.models.SignalLevel.HIGH, 0)}",
        f"Medium: {counts.get(__import__('kulima.signals.models').signals.models.SignalLevel.MEDIUM, 0)}",
        f"Low: {counts.get(__import__('kulima.signals.models').signals.models.SignalLevel.LOW, 0)}",
    ]
    section_lines.append(("Signals Overview", overview))
    for idx, sig in enumerate(highest_priority_signals(signals), 1):
        refs = ", ".join(sig.evidence_refs) if sig.evidence_refs else "—"
        section_lines.append(
            (
                f"[SG{idx}] {sig.title}",
                [
                    f"Level: {sig.level.value.upper()}",
                    f"Category: {sig.category.value.title()}",
                    f"Direction: {sig.direction}",
                    f"Description: {sig.description}",
                    f"Evidence refs: {refs}",
                    f"Recommended action: {sig.recommended_action or '—'}",
                    f"Confidence: {sig.confidence:.2f}",
                    f"Time horizon: {sig.time_horizon or '—'}",
                ],
            )
        )
    return _build_simple_pdf(
        title="Kulima FLEX — Signals Report",
        subtitle=[
            f"{brief.founder_name} / {brief.startup_name}",
            f"Recommendation: {brief.recommendation.value} | Overall {brief.overall_score:.0f}/100",
        ],
        sections=section_lines,
    )


def build_due_diligence_summary_text(brief: InvestmentBrief) -> str:
    lines = [
        "KULIMA FLEX — DUE DILIGENCE SUMMARY",
        "=" * 40,
        f"Deal: {brief.founder_name} / {brief.startup_name}",
        f"Recommendation: {brief.recommendation.value} | Overall Score: {brief.overall_score:.0f}/100",
        f"Confidence: {brief.confidence_level.value} ({brief.confidence:.2f})",
        "",
        "RESEARCH RESULTS",
        "-" * 40,
        f"Executive summary: {brief.executive_summary or '—'}",
        f"Founder assessment: {brief.founder_assessment or '—'}",
        f"Startup assessment: {brief.startup_assessment or '—'}",
        f"Market assessment: {brief.market_assessment or '—'}",
        f"Risk assessment: {brief.risk_assessment or '—'}",
        "",
        "DOCUMENTS USED",
        "-" * 40,
        *_brief_document_lines(brief),
        "",
        "SOURCES USED",
        "-" * 40,
    ]
    if brief.sources:
        for i, src in enumerate(brief.sources, 1):
            lines.extend(
                [
                    f"[S{i}] {src.title}",
                    f"URL: {src.url}",
                    f"Type: {src.source_type} | Relevance: {src.relevance:.2f} | Confidence: {src.confidence_score:.2f}",
                    f"Snippet: {src.snippet or '—'}",
                    "",
                ]
            )
    else:
        lines.append("No sources attached.")
        lines.append("")

    lines.extend([
        "RELIABILITY INDICATORS",
        "-" * 40,
    ])
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = "Limited Coverage" if ei.sparse_mode else ei.evidence_depth.value.capitalize()
        lines.extend(
            [
                f"Grade: {ei.integrity_grade.value} ({ei.integrity_score:.0f}/100)",
                f"Depth: {depth_label}",
                f"Consistency: {ei.consistency_status.value.replace('_', ' ')}",
                f"Sources reviewed: {ei.source_count}",
                f"Claims extracted: {ei.claim_count}",
                f"High-authority sources: {ei.high_authority_count}",
            ]
        )
    else:
        lines.append("Evidence Integrity Engine not run for this analysis.")

    lines.extend([
        "",
        "NEXT STEPS",
        "-" * 40,
    ])
    if brief.next_steps:
        for i, step in enumerate(brief.next_steps, 1):
            lines.append(f"{i}. {step}")
    else:
        lines.append("No next steps recorded.")
    return "\n".join(lines).strip()


def build_due_diligence_summary_pdf(brief: InvestmentBrief) -> bytes:
    section_lines: list[tuple[str, list[str]]] = [
        (
            "Research Results",
            [
                f"Executive summary: {brief.executive_summary or '—'}",
                f"Founder assessment: {brief.founder_assessment or '—'}",
                f"Startup assessment: {brief.startup_assessment or '—'}",
                f"Market assessment: {brief.market_assessment or '—'}",
                f"Risk assessment: {brief.risk_assessment or '—'}",
            ],
        ),
        ("Documents Used", _brief_document_lines(brief)),
    ]
    if brief.sources:
        source_lines = []
        for i, src in enumerate(brief.sources, 1):
            source_lines.extend(
                [
                    f"[{i}] {src.title}",
                    f"URL: {src.url}",
                    f"Type: {src.source_type} | Relevance: {src.relevance:.2f} | Confidence: {src.confidence_score:.2f}",
                    f"Snippet: {src.snippet or '—'}",
                    "",
                ]
            )
    else:
        source_lines = ["No sources attached."]
    section_lines.append(("Sources Used", source_lines))
    reliability_lines = []
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = "Limited Coverage" if ei.sparse_mode else ei.evidence_depth.value.capitalize()
        reliability_lines.extend(
            [
                f"Grade: {ei.integrity_grade.value} ({ei.integrity_score:.0f}/100)",
                f"Depth: {depth_label}",
                f"Consistency: {ei.consistency_status.value.replace('_', ' ')}",
                f"Sources reviewed: {ei.source_count}",
                f"Claims extracted: {ei.claim_count}",
                f"High-authority sources: {ei.high_authority_count}",
            ]
        )
    else:
        reliability_lines.append("Evidence Integrity Engine not run for this analysis.")
    section_lines.append(("Reliability Indicators", reliability_lines))
    section_lines.append(("Next Steps", list(brief.next_steps) or ["No next steps recorded."]))
    return _build_simple_pdf(
        title="Kulima FLEX — Due Diligence Summary",
        subtitle=[
            f"{brief.founder_name} / {brief.startup_name}",
            f"Recommendation: {brief.recommendation.value} | Overall {brief.overall_score:.0f}/100",
        ],
        sections=section_lines,
    )


def build_executive_one_pager_text(brief: InvestmentBrief) -> str:
    top_reasons = [
        brief.executive_summary or "—",
        brief.investment_recommendation or brief.recommendation.value,
    ]
    if brief.red_flags:
        risks = [f"[{rf.severity.upper()}] {rf.title}: {rf.detail}" for rf in brief.red_flags[:3]]
    else:
        risks = ["No critical red flags surfaced from open-source intelligence."]
    lines = [
        "KULIMA FLEX — EXECUTIVE ONE PAGER",
        "=" * 40,
        f"Deal: {brief.founder_name} / {brief.startup_name}",
        f"Recommendation: {brief.recommendation.value} | Overall Score: {brief.overall_score:.0f}/100",
        f"Confidence: {brief.confidence_level.value} ({brief.confidence:.2f})",
    ]
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = "Limited Coverage" if ei.sparse_mode else ei.evidence_depth.value.capitalize()
        lines.append(
            f"Reliability: {ei.integrity_grade.value} ({ei.integrity_score:.0f}/100) | "
            f"Depth: {depth_label} | Consistency: {ei.consistency_status.value}"
        )
    lines.extend([
        "",
        "TOP REASONS",
        "-" * 40,
        *top_reasons,
        "",
        "TOP RISKS",
        "-" * 40,
        *risks,
        "",
        "NEXT ACTION",
        "-" * 40,
        brief.next_steps[0] if brief.next_steps else "Continue verification before IC.",
    ])
    return "\n".join(lines).strip()


def build_executive_one_pager_pdf(brief: InvestmentBrief) -> bytes:
    section_lines: list[tuple[str, list[str]]] = [
        (
            "Top Reasons",
            [brief.executive_summary or "—", brief.investment_recommendation or brief.recommendation.value],
        ),
        (
            "Top Risks",
            [
                f"[{rf.severity.upper()}] {rf.title}: {rf.detail}"
                for rf in (brief.red_flags[:3] if brief.red_flags else [])
            ] or ["No critical red flags surfaced from open-source intelligence."],
        ),
        ("Next Action", [brief.next_steps[0] if brief.next_steps else "Continue verification before IC."])
    ]
    return _build_simple_pdf(
        title="Kulima FLEX — Executive One Pager",
        subtitle=[
            f"{brief.founder_name} / {brief.startup_name}",
            f"Recommendation: {brief.recommendation.value} | Overall {brief.overall_score:.0f}/100",
        ],
        sections=section_lines,
    )


def _build_simple_pdf(
    *,
    title: str,
    subtitle: list[str],
    sections: list[tuple[str, list[str]]],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.7 * inch, bottomMargin=0.7 * inch, title=title, author="Kulima FLEX")
    styles = _pdf_styles()
    story: list = [Paragraph(title, styles["KulimaTitle"])]
    if subtitle:
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(_esc(s) for s in subtitle), styles["KulimaMeta"]))
    for heading, items in sections:
        story.append(Paragraph(heading, styles["KulimaH2"]))
        if not items:
            story.append(Paragraph("—", styles["KulimaBody"]))
        else:
            for item in items:
                story.append(Paragraph(f"• {_esc(item)}", styles["KulimaBullet"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Confidential — Generated by Kulima FLEX AI Investment Intelligence OS for Africa", styles["KulimaMeta"]))
    doc.build(story)
    return buffer.getvalue()


def render_reports_buttons(brief: InvestmentBrief, key_prefix: str = "reports") -> None:
    import streamlit as st

    st.markdown("### 📚 Report Pack")
    st.caption("All report PDFs are generated from the current run’s actual outputs.")
    names = export_filenames(brief)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Investment Brief")
        st.caption("Concise investment memo built from the current brief.")
        st.download_button(
            "Download Investment Brief PDF",
            data=build_memo_pdf(brief),
            file_name=names["memo_pdf"],
            mime="application/pdf",
            width="stretch",
            key=f"{key_prefix}_investment_brief_pdf",
        )
        st.markdown("#### Signals Report")
        st.caption("Deterministic signal pack derived from the current case.")
        st.download_button(
            "Download Signals Report PDF",
            data=build_signals_report_pdf(brief),
            file_name=names["signals_pdf"],
            mime="application/pdf",
            width="stretch",
            key=f"{key_prefix}_signals_pdf",
        )
    with col2:
        st.markdown("#### Due Diligence Summary")
        st.caption("Research summary, documents used, sources, and reliability.")
        st.download_button(
            "Download Due Diligence Summary PDF",
            data=build_due_diligence_summary_pdf(brief),
            file_name=names["dd_pdf"],
            mime="application/pdf",
            width="stretch",
            key=f"{key_prefix}_dd_pdf",
        )
        st.markdown("#### Executive One Pager")
        st.caption("Highly compressed decision snapshot for leadership.")
        st.download_button(
            "Download Executive One Pager PDF",
            data=build_executive_one_pager_pdf(brief),
            file_name=names["onepager_pdf"],
            mime="application/pdf",
            width="stretch",
            key=f"{key_prefix}_onepager_pdf",
        )


def render_export_buttons(brief: InvestmentBrief, key_prefix: str = "main") -> None:
    """Streamlit download buttons for memo + full IC report.

    Responsive layout: 3-column on desktop/tablet, stacked on mobile.
    All columns use use_container_width=True so buttons fill their slot.
    """
    import streamlit as st

    st.markdown("### 📥 Export Investment Materials")
    st.caption(
        "Download IC-ready documents in multiple formats. "
        "All exports include scores, syndicate votes, and futures analysis."
    )

    names = export_filenames(brief)
    memo_txt = build_memo_text(brief).encode("utf-8")
    memo_pdf = build_memo_pdf(brief)
    report_pdf = build_full_ic_report_pdf(brief)
    report_txt = build_full_ic_report_text(brief).encode("utf-8")

    # ── Reliability summary for Deal Summary column (if Trust Layer present) ─
    reliability_md = ""
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = "Limited Coverage" if ei.sparse_mode else ei.evidence_depth.value.capitalize()
        reliability_md = (
            f"Reliability: **{ei.integrity_grade.value}** "
            f"({ei.integrity_score:.0f}/100) · {depth_label}  \n"
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            '<div class="export-group">'
            '<div class="export-group-title">IC MEMO</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label="📄 Download Memo PDF",
            data=memo_pdf,
            file_name=names["memo_pdf"],
            mime="application/pdf",
            width="stretch",
            key=f"{key_prefix}_dl_memo_pdf",
            help="Concise IC memo — 1-2 pages, suitable for partner review.",
        )
        st.download_button(
            label="📝 Download Memo TXT",
            data=memo_txt,
            file_name=names["memo_txt"],
            mime="text/plain",
            width="stretch",
            key=f"{key_prefix}_dl_memo_txt",
            help="Plain-text version for email / Slack sharing.",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(
            '<div class="export-group">'
            '<div class="export-group-title">FULL IC REPORT</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label="📄 Download Full Report PDF",
            data=report_pdf,
            file_name=names["report_pdf"],
            mime="application/pdf",
            width="stretch",
            key=f"{key_prefix}_dl_full_ic_pdf",
            type="primary",
            help=(
                "Complete IC pack: memo + syndicate votes + futures + "
                "trust graph + sources. Recommended for board or LP distribution."
            ),
        )
        st.download_button(
            label="📝 Download Full Report TXT",
            data=report_txt,
            file_name=names["report_txt"],
            mime="text/plain",
            width="stretch",
            key=f"{key_prefix}_dl_full_ic_txt",
            help="Plain-text full report for archival or LLM ingestion.",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        st.markdown(
            '<div class="export-group">'
            '<div class="export-group-title">DEAL SUMMARY</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f"**{brief.founder_name}** / **{brief.startup_name}**  \n"
            f"Recommendation: **{brief.recommendation.value}**  \n"
            f"Overall: **{brief.overall_score:.0f}/100**  \n"
            f"Conviction: {brief.confidence_level.value}  \n"
            f"Sector: {brief.sector or '—'}  \n"
            f"{reliability_md}"
            f"Sources: {len(brief.sources)} · Red flags: {len(brief.red_flags)}"
        )
        st.markdown("</div>", unsafe_allow_html=True)
