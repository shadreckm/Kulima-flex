"""Memo and Investment Committee report export (TXT + PDF).

Provides boardroom-ready PDF and TXT exports branded with Kulima Africa logo,
Kulima OS branding, mission tagline, executive summary callout boxes, badges,
and custom numbered canvas footers.
"""

from __future__ import annotations

from datetime import datetime, timezone
import io
import os
import re
from typing import Any


def _load_reportlab_symbols() -> tuple[Any, ...]:
    try:
        from reportlab.lib import colors as colors_
        from reportlab.lib.enums import TA_CENTER as TA_CENTER_, TA_JUSTIFY as TA_JUSTIFY_, TA_LEFT as TA_LEFT_, TA_RIGHT as TA_RIGHT_
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
            Image as Image_,
            HRFlowable as HRFlowable_,
            KeepTogether as KeepTogether_,
        )
        from reportlab.pdfgen import canvas as canvas_
        return (
            colors_,       # 1
            TA_CENTER_,    # 2
            TA_JUSTIFY_,   # 3
            TA_LEFT_,      # 4
            TA_RIGHT_,     # 5
            A4_,           # 6
            ParagraphStyle_,      # 7
            getSampleStyleSheet_, # 8
            inch_,         # 9
            Paragraph_,    # 10
            SimpleDocTemplate_,   # 11
            Spacer_,       # 12
            Table_,        # 13
            TableStyle_,   # 14
            Image_,        # 15
            HRFlowable_,   # 16
            KeepTogether_, # 17
            canvas_,       # 18
        )
    except ImportError:
        return (None,) * 18


(colors, TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT, A4,
 ParagraphStyle, getSampleStyleSheet, inch,
 Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
 Image, HRFlowable, KeepTogether, canvas) = _load_reportlab_symbols()


from kulima.core.cases.adapters import from_investment_brief
from kulima.core.documents.context import build_document_context_for_subject
from kulima.models import EvidenceIntegrityReport, InvestmentBrief
from kulima.signals.models import Signal
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.signals_summary import count_signals_by_level, highest_priority_signals


# ── Logo Path Resolution ─────────────────────────────────────────────────────

def _get_logo_path() -> str | None:
    candidates = [
        os.path.join(os.getcwd(), "frontend", "public", "kulima-logo.png"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "kulima-logo.png"),
        "C:\\Users\\HP\\Desktop\\Kulima vc brain\\frontend\\public\\kulima-logo.png",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# ── Custom Numbered Canvas for PDF Header/Footer ─────────────────────────────

class NumberedCanvas(canvas.Canvas if canvas else object): # type: ignore
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        left_m = 54
        right_m = 541
        
        # Header rule & text on pages 2+
        if self._pageNumber > 1:
            self.setStrokeColor(colors.HexColor("#D1D5DB"))
            self.setLineWidth(0.5)
            self.line(left_m, 802, right_m, 802)
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#064E3B"))
            self.drawString(left_m, 807, "KULIMA AFRICA")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#4B5563"))
            self.drawString(130, 807, "|  Kulima OS Investment Intelligence Platform")

        # Footer on every page
        self.setStrokeColor(colors.HexColor("#D1D5DB"))
        self.setLineWidth(0.5)
        self.line(left_m, 45, right_m, 45)
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#064E3B"))
        self.drawString(left_m, 32, "Kulima Africa | Kulima OS")
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#6B7280"))
        self.drawCentredString(297, 32, "Confidential · Generated Automatically")
        self.drawRightString(right_m, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


# ── Trust Layer Helpers ──────────────────────────────────────────────────────

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


# ── TXT Exports ──────────────────────────────────────────────────────────────

def _txt_header(report_title: str, brief: InvestmentBrief) -> str:
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    rec = brief.recommendation.value.upper()
    trust = f"{brief.trust_score:.0f}/100"
    grade = brief.evidence_integrity.integrity_grade.value if brief.evidence_integrity else "Grade B"
    conf = f"{brief.confidence * 100:.0f}% ({brief.confidence_level.value.upper()})"
    
    return f"""================================================================================
KULIMA AFRICA | KULIMA OS
Food Everywhere, For Everyone, At All Times.
================================================================================
REPORT TYPE:     {report_title.upper()}
STARTUP:         {brief.startup_name}
FOUNDER:         {brief.founder_name}
DATE:            {date_str}
GENERATED BY:    Kulima OS – Evidence-Backed Investment Intelligence Platform
================================================================================
EXECUTIVE DECISION SNAPSHOT
--------------------------------------------------------------------------------
RECOMMENDATION:  {rec}
TRUST SCORE:     {trust} | CONFIDENCE: {conf} | INTEGRITY: {grade}
SECTOR:          {brief.sector or "—"} | GEOGRAPHY: {brief.geography or "—"} | STAGE: {brief.stage or "—"}
================================================================================
"""


def build_memo_text(brief: InvestmentBrief) -> str:
    steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(brief.next_steps, 1)) or "  —"
    header = _txt_header("Executive Investment Committee Memo", brief)

    reliability_line = ""
    if brief.evidence_integrity:
        reliability_line = f"\n{_ei_reliability_line(brief.evidence_integrity)}"

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

    return f"""{header}
KULIMA FLEX — INVESTMENT COMMITTEE MEMO
========================================
Deal: {brief.founder_name} / {brief.startup_name}
Sector: {brief.sector or '—'} | Geography: {brief.geography or '—'} | Stage: {brief.stage or '—'}
Recommendation: {brief.recommendation.value}
Overall Score: {brief.overall_score:.0f}/100 | Confidence: {brief.confidence_level.value}{reliability_line}
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

EXECUTIVE SUMMARY
----------------------------------------
{brief.executive_summary or '—'}

FOUNDER ASSESSMENT
----------------------------------------
{brief.founder_assessment or '—'}

STARTUP ASSESSMENT
----------------------------------------
{brief.startup_assessment or '—'}

MARKET ASSESSMENT
----------------------------------------
{brief.market_assessment or '—'}

RISK ASSESSMENT
----------------------------------------
{brief.risk_assessment or '—'}

INVESTMENT RECOMMENDATION
----------------------------------------
{brief.investment_recommendation or brief.recommendation.value}

NEXT STEPS
----------------------------------------
{steps}

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
================================================================================
Kulima Africa | Kulima OS · Confidential · Generated Automatically
""".strip()


def build_full_ic_report_text(brief: InvestmentBrief) -> str:
    parts = [
        build_memo_text(brief),
        "",
        "=" * 80,
        "FULL INVESTMENT COMMITTEE REPORT",
        "=" * 80,
        "",
    ]

    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        depth_label = "Limited Coverage" if ei.sparse_mode else ei.evidence_depth.value.capitalize()
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

    parts.append("TWIN SYNDICATE INVESTMENT COMMITTEE")
    parts.append("-" * 40)
    if brief.syndicate:
        syn = brief.syndicate
        final = syn.final_recommendation or syn.majority_vote
        parts.append(f"Final Recommendation: {final.value}")
        parts.append(f"Consensus Score: {syn.consensus_score or syn.average_score:.0f}/100")
        parts.append(f"Dissent Score: {syn.dissent_score or syn.dissent_index * 100:.0f}/100")
        if syn.consensus_thesis:
            parts.append(f"Consensus Thesis: {syn.consensus_thesis}")
        parts.append("")
        for v in syn.votes:
            role = v.title or v.persona
            parts.append(f"• {role} ({v.investor_name}, {v.firm})")
            parts.append(f"  Decision: {v.decision.value} | Confidence: {v.confidence_score:.0f}/100")
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
            parts.append(f"  Investor Attractiveness: {s.investor_attractiveness_score:.0f}/100")
            parts.append(f"  Revenue Growth Outlook: {s.revenue_growth_outlook or s.narrative}")
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

    parts.append("SOURCE ATTRIBUTION")
    parts.append("-" * 40)
    if brief.sources:
        for i, src in enumerate(brief.sources, 1):
            parts.append(f"[{i}] {src.title}")
            parts.append(f"    URL: {src.url}")
            parts.append(f"    Type: {src.source_type} | Relevance: {src.relevance:.2f} | Confidence: {src.confidence_score:.2f}")
            snippet = (src.snippet or "")[:280]
            if snippet:
                parts.append(f"    Excerpt: {snippet}")
            parts.append("")
    else:
        parts.append("No sources attached.")
        parts.append("")

    parts.append("EXPLAINABLE AI DECISIONS")
    parts.append("-" * 40)
    for reason in brief.explainability:
        parts.append(f"• {reason}")
    parts.append("")
    parts.append("================================================================================")
    parts.append("Kulima Africa | Kulima OS · Confidential · Generated Automatically")
    return "\n".join(parts)


def build_signals_report_text(brief: InvestmentBrief) -> str:
    _, signals = _brief_case_and_signals(brief)
    counts = count_signals_by_level(signals)
    header = _txt_header("Signals Intelligence Pack", brief)
    
    from kulima.signals.models import SignalLevel
    parts = [
        header,
        "SIGNALS OVERVIEW",
        "-" * 40,
        f"Total signals: {len(signals)}",
        f"Critical: {counts.get(SignalLevel.CRITICAL, 0)}",
        f"High: {counts.get(SignalLevel.HIGH, 0)}",
        f"Medium: {counts.get(SignalLevel.MEDIUM, 0)}",
        f"Low: {counts.get(SignalLevel.LOW, 0)}",
        "",
    ]
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
    parts.append("================================================================================")
    parts.append("Kulima Africa | Kulima OS · Confidential · Generated Automatically")
    return "\n".join(parts).strip()


def build_due_diligence_summary_text(brief: InvestmentBrief) -> str:
    header = _txt_header("Due Diligence & Research Summary", brief)
    lines = [
        header,
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
    lines.append("================================================================================")
    lines.append("Kulima Africa | Kulima OS · Confidential · Generated Automatically")
    return "\n".join(lines).strip()


def build_executive_one_pager_text(brief: InvestmentBrief) -> str:
    header = _txt_header("Executive One Pager", brief)
    top_reasons = [
        brief.executive_summary or "—",
        brief.investment_recommendation or brief.recommendation.value,
    ]
    if brief.red_flags:
        risks = [f"[{rf.severity.upper()}] {rf.title}: {rf.detail}" for rf in brief.red_flags[:3]]
    else:
        risks = ["No critical red flags surfaced from open-source intelligence."]
    lines = [
        header,
        "TOP 3 INVESTMENT DRIVERS",
        "-" * 40,
        *top_reasons,
        "",
        "TOP 3 FLAGGED RISKS",
        "-" * 40,
        *risks,
        "",
        "RECOMMENDED NEXT ACTION",
        "-" * 40,
        brief.next_steps[0] if brief.next_steps else "Continue verification before IC.",
        "",
        "EVIDENCE RELIABILITY SUMMARY",
        "-" * 40,
    ]
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        lines.append(f"Grade {ei.integrity_grade.value} ({ei.integrity_score:.0f}/100) · {ei.source_count} Sources Reviewed · {ei.high_authority_count} High-Authority Records")
    else:
        lines.append("Evidence Integrity Engine Verified.")
    lines.append("================================================================================")
    lines.append("Kulima Africa | Kulima OS · Confidential · Generated Automatically")
    return "\n".join(lines).strip()


# ── PDF Styles & Generator Helpers ────────────────────────────────────────────

def _pdf_styles() -> Any:
    styles = getSampleStyleSheet()
    
    # Custom Brand Colors
    c_primary = colors.HexColor("#064E3B")    # Deep Green
    c_accent = colors.HexColor("#047857")     # Emerald Green
    c_text = colors.HexColor("#1F2937")       # Dark Charcoal
    c_muted = colors.HexColor("#4B5563")      # Slate Gray
    
    styles.add(
        ParagraphStyle(
            name="KulimaBrandTitle",
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=c_primary,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaBrandSubtitle",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=c_accent,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaTagline",
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=c_muted,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaDocTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=c_primary,
            spaceBefore=8,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaH2",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            textColor=c_primary,
            spaceBefore=12,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=12.5,
            alignment=TA_JUSTIFY,
            textColor=c_text,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaMeta",
            parent=styles["Normal"],
            fontSize=8,
            leading=10.5,
            textColor=c_muted,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaBullet",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11.5,
            leftIndent=8,
            textColor=c_text,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaCalloutTitle",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.white,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaIntegrityGrade",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=c_primary,
            fontName="Helvetica-Bold",
            spaceBefore=4,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KulimaVerification",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#7A3B00"),
            leftIndent=6,
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


def _build_brand_header(brief: InvestmentBrief, report_name: str, styles: Any) -> list:
    elements = []
    logo_path = _get_logo_path()
    
    # Left Cell: Logo (if available) or Text Banner
    if logo_path and Image:
        logo_img = Image(logo_path, width=1.65 * inch, height=0.5 * inch)
        left_cell = logo_img
    else:
        left_cell = Paragraph("<b>KULIMA AFRICA</b>", styles["KulimaBrandTitle"])
    
    right_cell_content = [
        Paragraph("KULIMA AFRICA", styles["KulimaBrandTitle"]),
        Paragraph("Kulima OS — Investment Intelligence Platform", styles["KulimaBrandSubtitle"]),
        Paragraph("Food Everywhere, For Everyone, At All Times.", styles["KulimaTagline"]),
    ]
    
    header_table = Table([[left_cell, right_cell_content]], colWidths=[2.2 * inch, 4.45 * inch])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "LEFT"),
                ("LEFTPADDING", (1, 0), (1, 0), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(header_table)
    
    if HRFlowable:
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#064E3B"), spaceBefore=4, spaceAfter=8))
    else:
        elements.append(Spacer(1, 6))

    # Metadata Banner
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    elements.append(Paragraph(report_name, styles["KulimaDocTitle"]))

    meta_data = [
        [
            Paragraph("<b>Startup:</b> " + _esc(brief.startup_name), styles["KulimaBody"]),
            Paragraph("<b>Founder:</b> " + _esc(brief.founder_name), styles["KulimaBody"]),
        ],
        [
            Paragraph(f"<b>Sector / Geo:</b> {_esc(brief.sector or '—')} | {_esc(brief.geography or '—')}", styles["KulimaBody"]),
            Paragraph(f"<b>Stage:</b> {_esc(brief.stage or '—')} | <b>Date:</b> {date_str}", styles["KulimaBody"]),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[3.3 * inch, 3.35 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 8))
    return elements


def _build_executive_summary_box(brief: InvestmentBrief, styles: Any) -> list:
    elements = []
    
    rec = brief.recommendation.value.upper()
    if rec == "INVEST":
        badge_bg = colors.HexColor("#064E3B") # Deep Green
    elif rec == "OBSERVE":
        badge_bg = colors.HexColor("#B45309") # Amber
    else:
        badge_bg = colors.HexColor("#BE123C") # Rose Red
        
    grade = brief.evidence_integrity.integrity_grade.value if brief.evidence_integrity else "Grade B"
    trust_score_val = f"{brief.trust_score:.0f}/100"
    conf_val = f"{brief.confidence * 100:.0f}% ({brief.confidence_level.value.upper()})"

    # 1. Title Banner
    title_table = Table(
        [[Paragraph("<b>EXECUTIVE INVESTMENT DECISION SNAPSHOT</b>", styles["KulimaCalloutTitle"])]],
        colWidths=[6.65 * inch]
    )
    title_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#064E3B")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    
    # 2. Badges & Score Grid
    p_rec = Paragraph(f"<font color='#ffffff'><b>{rec}</b></font>", ParagraphStyle('RecB', parent=styles['KulimaBody'], alignment=TA_CENTER, fontSize=10, fontName='Helvetica-Bold'))
    p_trust = Paragraph(f"<b>Trust Score:</b> {trust_score_val}", styles['KulimaBody'])
    p_conf = Paragraph(f"<b>Conviction:</b> {conf_val}", styles['KulimaBody'])
    p_grade = Paragraph(f"<b>Reliability:</b> {grade}", styles['KulimaBody'])
    
    grid_table = Table(
        [[p_rec, p_trust, p_conf, p_grade]],
        colWidths=[1.4 * inch, 1.75 * inch, 1.75 * inch, 1.75 * inch]
    )
    grid_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), badge_bg),
            ("BACKGROUND", (1, 0), (-1, -1), colors.HexColor("#ECFDF5")),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#A7F3D0")),
        ])
    )

    # 3. Key Reasons vs Key Risks Table
    reasons_list = [Paragraph("• " + _esc(brief.executive_summary or "—"), styles["KulimaBullet"])]
    if brief.investment_recommendation:
        reasons_list.append(Paragraph("• " + _esc(brief.investment_recommendation), styles["KulimaBullet"]))
        
    if brief.red_flags:
        risks_list = [Paragraph(f"• <b>[{rf.severity.upper()}]</b> " + _esc(rf.title) + ": " + _esc(rf.detail), styles["KulimaBullet"]) for rf in brief.red_flags[:2]]
    else:
        risks_list = [Paragraph("• No critical red flags surfaced from open-source intelligence.", styles["KulimaBullet"])]
        
    cols_table = Table(
        [[
            [Paragraph("<b>TOP INVESTMENT DRIVERS</b>", styles["KulimaH2"])] + reasons_list,
            [Paragraph("<b>TOP FLAGGED RISKS</b>", styles["KulimaH2"])] + risks_list,
        ]],
        colWidths=[3.3 * inch, 3.35 * inch]
    )
    cols_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ])
    )

    # 4. Next Action Footer Bar
    next_step = brief.next_steps[0] if brief.next_steps else "Proceed to IC verification sprint."
    action_table = Table(
        [[Paragraph(f"<b>RECOMMENDED NEXT ACTION:</b> {_esc(next_step)}", styles["KulimaBody"])]],
        colWidths=[6.65 * inch]
    )
    action_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")), # Amber tint
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FCD34D")),
        ])
    )

    elements.extend([title_table, grid_table, cols_table, action_table, Spacer(1, 10)])
    return elements


# ── PDF Build Engine ─────────────────────────────────────────────────────────

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
        topMargin=0.65 * inch,
        bottomMargin=0.75 * inch,
        title=f"Kulima IC {'Report' if full_report else 'Memo'} — {brief.founder_name}",
        author="Kulima Africa | Kulima OS",
    )
    styles = _pdf_styles()
    story: list = []

    # Brand Header & Executive Callout
    report_title = "Executive Full Investment Committee Report" if full_report else "Executive Investment Committee Memo"
    story.extend(_build_brand_header(brief, report_title, styles))
    story.extend(_build_executive_summary_box(brief, styles))

    # Scorecard Table
    score_data = [
        ["Founder", "Startup", "Market", "Trust", "Risk↓", "Overall Score"],
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
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#064E3B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ECFDF5")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#A7F3D0")),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))

    # Main Analysis Sections
    sections = [
        ("1. Executive Summary & Thesis", brief.executive_summary),
        ("2. Founder & Capability Assessment", brief.founder_assessment),
        ("3. Startup Product & Operational Assessment", brief.startup_assessment),
        ("4. Market Dynamics & Competition", brief.market_assessment),
        ("5. Risk Factors & Mitigations", brief.risk_assessment),
        (
            "6. Final Investment Recommendation",
            brief.investment_recommendation or brief.recommendation.value,
        ),
    ]
    for heading, body in sections:
        story.append(Paragraph(heading, styles["KulimaH2"]))
        story.append(Paragraph(_esc(body), styles["KulimaBody"]))

    story.append(Paragraph("7. Actionable Next Steps", styles["KulimaH2"]))
    if brief.next_steps:
        for idx, step in enumerate(brief.next_steps, 1):
            story.append(Paragraph(f"{idx}. {_esc(step)}", styles["KulimaBullet"]))
    else:
        story.append(Paragraph("—", styles["KulimaBody"]))

    # Additional Full IC Report Sections
    if full_report:
        story.append(Spacer(1, 8))
        if brief.evidence_integrity:
            ei = brief.evidence_integrity
            depth_label = "Limited Coverage" if ei.sparse_mode else ei.evidence_depth.value.capitalize()
            consistency = ei.consistency_status.value.replace("_", " ").capitalize()

            story.append(Paragraph("Evidence Reliability & Contradiction Report", styles["KulimaH2"]))
            story.append(
                Paragraph(
                    f"<b>Rating: {_esc(ei.integrity_grade.value)} ({ei.integrity_score:.0f}/100)</b> &nbsp;·&nbsp; "
                    f"Depth: {_esc(depth_label)} &nbsp;·&nbsp; Consistency: {_esc(consistency)}<br/>"
                    f"Sources reviewed: {ei.source_count} &nbsp;·&nbsp; Claims extracted: {ei.claim_count} &nbsp;·&nbsp; "
                    f"High-authority sources: {ei.high_authority_count}",
                    styles["KulimaIntegrityGrade"],
                )
            )
            if ei.contradictions:
                story.append(Paragraph("<b>Conflicts detected:</b>", styles["KulimaBody"]))
                for i, c in enumerate(ei.contradictions, 1):
                    a_val = c.claim_a.value_raw or "—"
                    b_val = c.claim_b.value_raw or "—"
                    claim_label = c.claim_a.claim_type.value.replace("_", " ").capitalize()
                    action = c.recommended_action or "Verify with founder."
                    story.append(
                        Paragraph(
                            f"[C{i}] <b>{_esc(c.severity.value.upper())}</b> — {_esc(claim_label)}: &ldquo;{_esc(a_val)}&rdquo; vs &ldquo;{_esc(b_val)}&rdquo;<br/>"
                            f"<i>Action: {_esc(action)}</i>",
                            styles["KulimaVerification"],
                        )
                    )

        story.append(Paragraph("Red Flag Alerts & Mitigations", styles["KulimaH2"]))
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
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("No critical red flags surfaced.", styles["KulimaBody"]))

        story.append(Paragraph("Twin Syndicate Consensus & Investor Voting", styles["KulimaH2"]))
        if brief.syndicate:
            syn = brief.syndicate
            final = syn.final_recommendation or syn.majority_vote
            story.append(
                Paragraph(
                    f"Final Consensus Recommendation: <b>{_esc(final.value)}</b> | "
                    f"Consensus Score: {syn.consensus_score or syn.average_score:.0f}/100 | "
                    f"Dissent Score: {syn.dissent_score or syn.dissent_index * 100:.0f}/100",
                    styles["KulimaBody"],
                )
            )
            for v in syn.votes:
                role = v.title or v.persona
                story.append(
                    Paragraph(
                        f"• <b>{_esc(role)}</b> ({_esc(v.investor_name)}, {_esc(v.firm)}) — <b>{_esc(v.decision.value)}</b><br/>"
                        f"  Reasoning: {_esc(v.key_reasoning or v.thesis)}",
                        styles["KulimaBody"],
                    )
                )

        story.append(Paragraph("Source Attribution & OSINT Intelligence", styles["KulimaH2"]))
        if brief.sources:
            for i, src in enumerate(brief.sources, 1):
                story.append(
                    Paragraph(
                        f"[{i}] <b>{_esc(src.title)}</b> &nbsp;·&nbsp; {_esc(src.url)}",
                        styles["KulimaBody"],
                    )
                )

    if canvas and NumberedCanvas:
        doc.build(story, canvasmaker=NumberedCanvas)
    else:
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


def build_signals_report_pdf(brief: InvestmentBrief) -> bytes:
    _, signals = _brief_case_and_signals(brief)
    counts = count_signals_by_level(signals)
    from kulima.signals.models import SignalLevel
    
    section_lines: list[tuple[str, list[str]]] = []
    overview = [
        f"Total signals extracted: {len(signals)}",
        f"Critical severity: {counts.get(SignalLevel.CRITICAL, 0)}",
        f"High severity: {counts.get(SignalLevel.HIGH, 0)}",
        f"Medium severity: {counts.get(SignalLevel.MEDIUM, 0)}",
        f"Low severity: {counts.get(SignalLevel.LOW, 0)}",
    ]
    section_lines.append(("Signals Overview & Severity Breakdown", overview))
    for idx, sig in enumerate(highest_priority_signals(signals), 1):
        refs = ", ".join(sig.evidence_refs) if sig.evidence_refs else "—"
        section_lines.append(
            (
                f"[SG{idx}] {sig.title}",
                [
                    f"Severity: {sig.level.value.upper()} | Category: {sig.category.value.title()}",
                    f"Direction: {sig.direction} | Confidence: {sig.confidence:.2f}",
                    f"Description: {sig.description}",
                    f"Recommended Action: {sig.recommended_action or '—'}",
                    f"Evidence refs: {refs}",
                ],
            )
        )
    return _build_styled_report_pdf(
        brief=brief,
        report_title="Signals Intelligence Pack",
        sections=section_lines,
    )


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
    return _build_styled_report_pdf(
        brief=brief,
        report_title="Due Diligence & Research Summary",
        sections=section_lines,
    )


def build_executive_one_pager_pdf(brief: InvestmentBrief) -> bytes:
    top_reasons = [brief.executive_summary or "—"]
    if brief.investment_recommendation:
        top_reasons.append(brief.investment_recommendation)
        
    risks = [
        f"[{rf.severity.upper()}] {rf.title}: {rf.detail}"
        for rf in (brief.red_flags[:3] if brief.red_flags else [])
    ] or ["No critical red flags surfaced from open-source intelligence."]
    
    next_act = [brief.next_steps[0] if brief.next_steps else "Continue verification before IC."]
    
    section_lines: list[tuple[str, list[str]]] = [
        ("Top 3 Investment Drivers", top_reasons),
        ("Top 3 Flagged Risks", risks),
        ("Recommended Next Action", next_act),
    ]
    return _build_styled_report_pdf(
        brief=brief,
        report_title="Executive One Pager",
        sections=section_lines,
    )


def _build_styled_report_pdf(
    *,
    brief: InvestmentBrief,
    report_title: str,
    sections: list[tuple[str, list[str]]],
) -> bytes:
    if any(symbol is None for symbol in (colors, TA_CENTER, A4, ParagraphStyle, getSampleStyleSheet, inch, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)):
        return build_executive_one_pager_text(brief).encode("utf-8")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.75 * inch,
        title=f"{report_title} — {brief.founder_name}",
        author="Kulima Africa | Kulima OS",
    )
    styles = _pdf_styles()
    story: list = []

    story.extend(_build_brand_header(brief, report_title, styles))
    story.extend(_build_executive_summary_box(brief, styles))

    for heading, items in sections:
        story.append(Paragraph(heading, styles["KulimaH2"]))
        if not items:
            story.append(Paragraph("—", styles["KulimaBody"]))
        else:
            for item in items:
                story.append(Paragraph(f"• {_esc(item)}", styles["KulimaBullet"]))
        story.append(Spacer(1, 4))

    if canvas and NumberedCanvas:
        doc.build(story, canvasmaker=NumberedCanvas)
    else:
        doc.build(story)
    return buffer.getvalue()


# ── Streamlit Component Helpers ──────────────────────────────────────────────

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
