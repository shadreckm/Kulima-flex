"""Grounded follow-up Q&A for the AI Analyst (Ask the IC) tab.

The analyst is entity-aware: NGOs and development programmes (V1's primary
customers) are answered from an institutional-capacity / programme-performance
frame, while Startup runs keep the Investment Committee frame.
"""

from __future__ import annotations

import textwrap
from typing import Any

from kulima.llm import LLMClient
from kulima.models import InvestmentBrief
from kulima.core.documents.context import build_document_context_for_subject

MAX_CONTEXT_CHARS = 18000


def _clip(value: str, limit: int = 1200) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _bullet_list(items: list[str], limit: int = 8) -> str:
    return "\n".join(f"- {_clip(item, 500)}" for item in items[:limit]) or "- None provided"


def _format_assessment_section(assessment: dict[str, Any]) -> list[str]:
    """Render the shared Assessment Context as an [ASSESSMENT_CONTEXT] block.

    Ask IC must already know the assessment type, organisation, founder,
    uploaded documents, and trust score — without asking the user again.
    """
    lines: list[str] = ["[ASSESSMENT_CONTEXT]"]
    type_label = assessment.get("assessmentTypeLabel") or assessment.get("assessment_type") or "Assessment"
    entity = assessment.get("displayEntity") or assessment.get("organizationName") or assessment.get("organization_name") or assessment.get("startupName") or assessment.get("startup_name") or "Unknown"
    founder = assessment.get("founderName") or assessment.get("founder_name") or "Unknown"
    lines.append(f"Assessment type: {type_label}")
    lines.append(f"Organisation / entity: {entity}")
    lines.append(f"Founder / lead: {founder}")
    sector = assessment.get("sector") or "Unknown"
    country = assessment.get("country") or "Unknown"
    lines.append(f"Sector: {sector}; Country: {country}")
    if assessment.get("website"):
        lines.append(f"Website: {assessment['website']}")
    if assessment.get("team"):
        lines.append(f"Team: {assessment['team']}")
    if assessment.get("problemStatement") or assessment.get("problem_statement"):
        lines.append(
            "Problem statement: "
            + _clip(str(assessment.get("problemStatement") or assessment.get("problem_statement")), 400)
        )
    documents = assessment.get("uploadedDocuments") or assessment.get("uploaded_documents") or []
    if documents:
        names = [
            str(doc.get("name") or doc.get("filename") or "document")
            if isinstance(doc, dict)
            else str(doc)
            for doc in documents[:8]
        ]
        lines.append(f"Uploaded documents ({len(documents)}): " + "; ".join(names))
    confidence = assessment.get("confidence")
    if confidence is not None:
        lines.append(f"Extraction confidence: {float(confidence):.2f}")
    trust = assessment.get("trustScore", assessment.get("trust_score"))
    if trust is not None:
        lines.append(f"Trust score: {float(trust):.0f}/100")
    decision = assessment.get("decision") or {}
    if isinstance(decision, dict) and decision:
        rec = decision.get("recommendation")
        overall = decision.get("overallScore")
        risk = decision.get("riskScore")
        parts = [p for p in [
            f"recommendation {rec}" if rec else "",
            f"decision score {float(overall):.0f}/100" if isinstance(overall, (int, float)) else "",
            f"risk score {float(risk):.0f}/100 (lower is better)" if isinstance(risk, (int, float)) else "",
        ] if p]
        if parts:
            lines.append("Decision snapshot: " + "; ".join(parts))
    return lines


def _format_domain_section(domain_overviews: dict[str, dict]) -> list[str]:
    """Render the dashboard domains as a [DOMAIN_SIGNALS] block.

    Order follows ``DISPLAY_DOMAINS`` (Community, Trust, Funding, Programme
    Delivery, Risk, Opportunity, Climate, ...) so the AI Analyst reads the
    primary customer's domains first.
    """
    try:
        from kulima.signals.signals_summary import DISPLAY_DOMAINS
        order = tuple(domain.value for domain in DISPLAY_DOMAINS)
    except Exception:  # noqa: BLE001 — grounding must never break Ask IC
        order = (
            "community_impact", "trust", "funding", "program_delivery", "risk",
            "opportunity", "climate", "environmental", "market", "tourism",
        )
    lines: list[str] = ["[DOMAIN_SIGNALS]"]
    for key in order:
        entry = domain_overviews.get(key)
        if not entry:
            continue
        label = entry.get("label") or key.replace("_", " ").title()
        score = entry.get("score")
        summary = _clip(str(entry.get("summary") or ""), 320)
        recommendation = _clip(str(entry.get("recommendation") or ""), 240)
        line = f"{label}: {score}/100"
        if summary:
            line += f" — {summary}"
        if recommendation:
            line += f" Recommendation: {recommendation}"
        lines.append(line)
    return lines


def build_ask_ic_context(
    brief: InvestmentBrief,
    *,
    run_id: int | None = None,
    user_id: str | None = None,
    assessment_context: dict[str, Any] | None = None,
    domain_overviews: dict[str, dict] | None = None,
) -> str:
    """Build a bounded, citable context pack from only generated artifacts.

    ``assessment_context`` / ``domain_overviews`` are optional additive
    grounding packs sourced from the shared Assessment Context; when absent,
    the context pack is identical to previous releases.

    The field labels inside the pack follow the entity: an NGO or programme
    is described in institutional terms, a Startup in investment terms — the
    underlying scores are the same.
    """
    declared_type = ""
    if assessment_context:
        declared_type = str(
            assessment_context.get("entityType")
            or assessment_context.get("assessment_type")
            or assessment_context.get("assessmentType")
            or ""
        ).lower()
    if not declared_type or declared_type in ("unknown", "none"):
        try:
            from kulima.intelligence.report_quality import detect_entity_type
            declared_type = detect_entity_type(brief)
        except Exception:  # noqa: BLE001 — labelling must never break grounding
            declared_type = "ngo"
    is_venture = declared_type in ("startup", "social_enterprise", "cooperative", "accelerator")

    entity_kind_label = "Venture" if is_venture else "Organisation / programme"
    lead_label = "Founder" if is_venture else "Lead / accountable person"
    readiness_label = (
        "Investment readiness" if is_venture else "Funding & delivery readiness"
    )
    sections: list[str] = [
        "[REPORT]",
        f"{lead_label}: {brief.founder_name}",
        f"{entity_kind_label}: {brief.startup_name}",
        f"Sector: {brief.sector or 'Unknown'}",
        f"Geography: {brief.geography or 'Unknown'}",
        f"Stage: {brief.stage or 'Unknown'}",
        f"Recommendation: {brief.recommendation.value}",
        f"Overall score: {brief.overall_score:.0f}/100",
        f"Founder score: {brief.founder_score:.0f}/100",
        f"Startup score: {brief.startup_score:.0f}/100",
        f"Market score: {brief.market_score:.0f}/100",
        f"Trust score: {brief.trust_score:.0f}/100",
        f"Risk score: {brief.risk_score:.0f}/100 (lower is better)",
        f"Growth potential: {brief.growth_potential:.0f}/100",
        f"{readiness_label}: {brief.investment_readiness:.0f}/100",
        f"Confidence: {brief.confidence_level.value} ({brief.confidence:.2f})",
        f"Executive summary: {_clip(brief.executive_summary, 1800)}",
        f"Founder assessment: {_clip(brief.founder_assessment, 1600)}",
        f"{'Startup' if is_venture else 'Organisation / programme'} assessment: {_clip(brief.startup_assessment, 1600)}",
        f"{'Market' if is_venture else 'Delivery & sector context'} assessment: {_clip(brief.market_assessment, 1600)}",
        f"Risk assessment: {_clip(brief.risk_assessment, 1600)}",
        f"{'Investment' if is_venture else 'Funding / partnership'} recommendation: {_clip(brief.investment_recommendation, 1600)}",
        "Next steps:\n" + _bullet_list(brief.next_steps),
        "Explainability:\n" + _bullet_list(brief.explainability, 12),
    ]

    # Intake grounding first so it survives context truncation.
    if assessment_context:
        sections.extend(_format_assessment_section(assessment_context))
    if domain_overviews:
        sections.extend(_format_domain_section(domain_overviews))

    tm = brief.thesis_match
    if tm is None and is_venture:
        try:
            from kulima.thesis import evaluate_thesis_match
            tm = evaluate_thesis_match(brief)
        except Exception:
            tm = None

    if tm and is_venture:
        sections.append("[THESIS_FIT]")
        st_str = tm.status.value if hasattr(tm.status, "value") else str(tm.status)
        sections.append(
            f"Overall Thesis Match: {tm.overall_match:.0f}% ({st_str}) | "
            f"Sector Fit: {tm.sector_fit} | "
            f"Stage Fit: {tm.stage_fit} | "
            f"Geography Fit: {tm.geography_fit} | "
            f"Evidence Fit: {tm.evidence_fit}"
        )
        if tm.notes:
            sections.append("Thesis Notes:\n" + _bullet_list(tm.notes))

    if brief.red_flags:
        sections.append("[RISK_ANALYSIS]")
        for i, flag in enumerate(brief.red_flags, 1):
            sections.append(
                f"[R{i}] {flag.severity.upper()} — {flag.title}: "
                f"{_clip(flag.detail, 700)} Mitigation: {_clip(flag.mitigation, 500)}"
            )

    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        sections.append("[EVIDENCE_INTEGRITY]")
        sections.append(
            f"Rating: Grade {ei.integrity_grade.value} ({ei.integrity_score:.0f}/100) | "
            f"Depth: {ei.evidence_depth.value} | "
            f"Consistency: {ei.consistency_status.value}"
        )
        for i, c in enumerate(ei.contradictions[:5], 1):
            sections.append(
                f"[C{i}] {c.severity.value.upper()} conflict — "
                f"{_clip(c.claim_a.value_raw, 300)} vs {_clip(c.claim_b.value_raw, 300)}"
            )
        for i, u in enumerate(ei.unsupported_claims[:5], 1):
            sections.append(
                f"[U{i}] Unsupported claim: {_clip(u.description, 400)}"
            )

    if brief.agent_results:
        sections.append("[AGENT_OUTPUTS]")
        for name, result in brief.agent_results.items():
            score_lines = "; ".join(
                f"{s.name} {s.score:.0f}/100 ({_clip(s.rationale, 220)})"
                for s in result.scores[:6]
            )
            sections.append(
                f"[{name.upper()}] {_clip(result.summary, 900)}\n"
                f"Findings:\n{_bullet_list(result.findings, 6)}\n"
                f"Scores: {score_lines or 'None provided'}"
            )

    if brief.syndicate:
        syn = brief.syndicate
        final = syn.final_recommendation or syn.majority_vote
        consensus = syn.consensus_score or syn.average_score
        sections.append("[SYNDICATE_OUTPUTS]")
        sections.append(
            f"Final recommendation: {final.value}; consensus {consensus:.0f}/100; "
            f"dissent {(syn.dissent_score or syn.dissent_index * 100):.0f}/100. "
            f"Consensus thesis: {_clip(syn.consensus_thesis, 1000)}"
        )
        for i, vote in enumerate(syn.votes, 1):
            role = vote.title or vote.persona
            sections.append(
                f"[V{i}] {role} ({vote.investor_name}, {vote.firm}) voted "
                f"{vote.decision.value} with confidence {vote.confidence_score:.0f}/100. "
                f"Reasoning: {_clip(vote.key_reasoning or vote.thesis, 700)} "
                f"Concern: {_clip(vote.major_concern or (vote.concerns[0] if vote.concerns else ''), 500)} "
                f"Conditions: {', '.join(vote.conditions[:4]) or 'None provided'}"
            )
        if syn.blocking_concerns:
            sections.append("Blocking concerns:\n" + _bullet_list(syn.blocking_concerns))
        if syn.debate_transcript:
            sections.append("Debate transcript: " + _clip(syn.debate_transcript, 1800))

    if brief.future_simulation:
        fs = brief.future_simulation
        sections.append("[FUTURES_ANALYSIS]")
        sections.append(
            f"Most likely case: {fs.most_likely_case}; Africa risk premium: "
            f"{fs.africa_risk_premium:.1f} pp; expected value 36m: ${fs.expected_value_usd:,.0f}. "
            f"Conditions summary: {_clip(fs.africa_conditions_summary, 1000)} "
            f"Notes: {_clip(fs.simulation_notes, 1000)}"
        )
        for i, scenario in enumerate(fs.scenarios, 1):
            sections.append(
                f"[F{i}] {scenario.emoji} {scenario.name}: success probability "
                f"{scenario.success_probability:.0f}%; investor attractiveness "
                f"{scenario.investor_attractiveness_score:.0f}/100; outlook: "
                f"{_clip(scenario.revenue_growth_outlook or scenario.narrative, 700)}\n"
                f"Risks:\n{_bullet_list(scenario.major_risks, 5)}\n"
                f"Opportunities:\n{_bullet_list(scenario.key_opportunities, 5)}"
            )

    if brief.sources:
        doc_sources = [s for s in brief.sources if s.source_type == "document"]
        if doc_sources:
            sections.append("[EVIDENCE_SOURCES — Source A: uploaded documents (PRIMARY)]")
            for i, src in enumerate(doc_sources, 1):
                sections.append(
                    f"[DS{i}] {src.title}\nSnippet: {_clip(src.snippet, 900)}\n"
                    f"Relevance: {src.relevance:.2f}; confidence: {src.confidence_score:.2f}"
                )

    # Append document evidence section when documents are available for this
    # founder/startup. This uses a separate [DOCUMENTS] header and [D#]
    # labels so the IC Analyst can distinguish document-backed claims from
    # web sources ([S#]).
    # Source Priority: documents (Source A) receive HALF the context budget
    # and are placed immediately after the assessment context — BEFORE web
    # evidence sections — so uploaded content drives the reasoning.
    doc_section = build_document_context_for_subject(
        brief.founder_name,
        brief.startup_name,
        max_documents=5,
        max_chars=MAX_CONTEXT_CHARS // 2,
        user_id=user_id,
    )
    if doc_section:
        sections.append(doc_section)

    # Web research (Source C) is corroborative — it follows the documents.
    if brief.sources:
        web_only = [s for s in brief.sources if s.source_type != "document"]
        if web_only:
            sections.append("[EVIDENCE_SOURCES — Source C: external web research (corroborative only)]")
            for i, src in enumerate(web_only, 1):
                sections.append(
                    f"[S{i}] {src.title}\nURL: {src.url}\nSnippet: {_clip(src.snippet, 800)}\n"
                    f"Relevance: {src.relevance:.2f}; confidence: {src.confidence_score:.2f}; type: {src.source_type}"
                )

    context = "\n\n".join(sections)
    return context[:MAX_CONTEXT_CHARS]


def answer_ask_ic_question(
    brief: InvestmentBrief,
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    run_id: int | None = None,
    user_id: str | None = None,
    assessment_context: dict[str, Any] | None = None,
    domain_overviews: dict[str, dict] | None = None,
) -> str:
    """Answer a follow-up question as an IC analyst using only the brief context."""
    history_text = "\n".join(
        f"{msg.get('role', 'user').upper()}: {_clip(msg.get('content', ''), 800)}"
        for msg in (history or [])[-8:]
    )
    context = build_ask_ic_context(
        brief,
        run_id=run_id,
        user_id=user_id,
        assessment_context=assessment_context,
        domain_overviews=domain_overviews,
    )
    etype = "ngo"
    if assessment_context:
        etype = str(assessment_context.get("entityType") or assessment_context.get("assessment_type") or "").lower()
    if not etype or etype in ("unknown", "none"):
        from kulima.intelligence.report_quality import detect_entity_type
        etype = detect_entity_type(brief)
    # V1's primary customers are NGOs and development programmes: an entity
    # that cannot be identified is reviewed with the institutional framework,
    # never the startup lens. Startup reasoning stays intact for Startup runs.
    etype = etype or "ngo"

    # The default reasoning framework for the primary customers (Phase 2).
    ngo_framework = (
        "Use the NGO / Development Programme capacity framework across six "
        "dimensions, in this order: (1) Institutional Capacity — governance, "
        "systems, policies, staff and audit readiness; (2) Programme "
        "Performance — workplan, milestones, logframe/results-framework "
        "targets versus actual delivery; (3) Community Reach — beneficiaries "
        "reached, inclusion of women, youth and marginalised groups; (4) "
        "Funding Sustainability — donor base, budget integrity, cost "
        "effectiveness, reliance and diversification; (5) Partnership Strength "
        "— implementing partners, consortia, MOUs and donor accountability; "
        "(6) Monitoring Quality — M&E/MEAL systems, indicator definitions, "
        "data verification and learning. Verdict bands: Strong Capacity, "
        "Moderate Capacity, Needs Strengthening. Never use startup/VC jargon "
        "such as 'invest', 'pass', 'seed round', 'term sheet', 'traction' or "
        "'exit'."
    )

    # Entity-specific AI Analyst personas and reasoning frameworks (Phase 4 & 5)
    if etype in ("ngo", "research_institution", "foundation"):
        role_title = "Senior Institutional Capacity & Grant Review Analyst for Kulima FLEX"
        mission_desc = "help donor representatives, trustees, and evaluation committees assess institutional capacity, programme performance, community reach, funding sustainability, partnership strength, and monitoring quality using the intelligence already generated."
        framework_note = ngo_framework
        decision_question = "Should we fund or partner with this organization?"
        decision_label = "Capacity Verdict"
        pass_trigger_label = "What would trigger a 'Needs Strengthening' verdict"
        summary_target = "summarize for institutional capacity review"
    elif etype in ("development_program", "farmer_organization"):
        role_title = "Senior Program Performance & Impact Reviewer for Kulima FLEX"
        mission_desc = "help program steering committees, DFIs, and portfolio directors review programme performance, institutional capacity, beneficiary reach, funding sustainability, partnership strength, and monitoring quality using the intelligence already generated."
        framework_note = (
            "Use the Development Programme framework across the same six "
            "dimensions, leading with Programme Performance: workplan, "
            "milestones, logframe outcomes, theory of change and beneficiary "
            "reach, then institutional capacity, funding sustainability, "
            "partnership strength and monitoring quality. Verdict bands: "
            "Ready, Requires Support, At Risk."
        )
        decision_question = "Is this program ready for implementation and funding?"
        decision_label = "Performance Verdict"
        pass_trigger_label = "What would trigger an 'At Risk' verdict"
        summary_target = "summarize for program performance review"
    elif etype == "government_program":
        role_title = "Public Governance & Policy Reviewer for Kulima FLEX"
        mission_desc = "help public sector oversight committees, ministries, and audit units evaluate governance, policy alignment, delivery capacity, and public value using the intelligence already generated."
        framework_note = "Use the Governance framework: Effective, Monitor, Intervene. Focus on statutory compliance, public value, policy alignment, and delivery capacity."
        decision_question = "Is this government program effective and compliant?"
        decision_label = "Governance Verdict"
        pass_trigger_label = "What would trigger an 'Intervene' verdict"
        summary_target = "summarize for governance review"
    elif etype == "tourism_sme":
        role_title = "Senior Tourism Resilience & Hospitality Analyst for Kulima FLEX"
        mission_desc = "help hospitality investors, tourism boards, and resilience funds assess destination readiness, visitor economy potential, climate vulnerability, and community benefits using the intelligence already generated."
        framework_note = "Use the Tourism framework: Ready for Growth, Build Resilience, High Risk. Focus on visitor economy, seasonality, climate resilience, and community employment."
        decision_question = "Is this tourism enterprise ready for growth investment?"
        decision_label = "Resilience Verdict"
        pass_trigger_label = "What would trigger a 'High Risk' verdict"
        summary_target = "summarize for tourism resilience review"
    elif etype in ("startup", "social_enterprise", "cooperative", "accelerator"):
        role_title = "Senior Investment Committee Associate for Kulima FLEX"
        mission_desc = "help a Partner decide whether to invest in this startup using the intelligence already generated."
        framework_note = "Use the Investment framework: Invest, Observe, Pass. Focus on customer discovery, market validation, roadmap, revenue model, and funding ask."
        decision_question = "Should I invest?"
        decision_label = "Investment Recommendation"
        pass_trigger_label = "What would make this a pass"
        summary_target = "summarize for investment committee"
    else:
        # Unrecognised entity: default to the primary customer's framework.
        role_title = "Senior Institutional Capacity & Grant Review Analyst for Kulima FLEX"
        mission_desc = "help donor representatives, trustees, and evaluation committees assess institutional capacity, programme performance, community reach, funding sustainability, partnership strength, and monitoring quality using the intelligence already generated."
        framework_note = ngo_framework
        decision_question = "Should we fund or partner with this organization?"
        decision_label = "Capacity Verdict"
        pass_trigger_label = "What would trigger a 'Needs Strengthening' verdict"
        summary_target = "summarize for institutional capacity review"

    system = textwrap.dedent(
        f"""
        You are a {role_title}.
        Your only job is to {mission_desc}

        Mindset:
        - You are NOT a generic chatbot, report writer, or external consultant.
        - {framework_note}
        - Do NOT dump everything; focus on what matters for the decision.

        Default response structure (for most questions):
        1) Short Answer — direct, decision-oriented.
        2) Why This Matters — 2–4 concise bullets.
        3) Supporting Evidence — only the highest-value points, with compact citations.
        4) Recommended Next Step — one concrete action.
        5) Next Question I'd Ask — one forward-looking prompt that helps move closer to a decision.

        Length & style:
        - Target 100–200 words; maximum ~250 words unless the user explicitly asks for a deep dive.
        - Use short paragraphs and bullets. Avoid walls of text.
        - Always end with either "Next question I'd ask:" or "Before making a decision, I'd verify:".

        Grounding rules:
        - SOURCE PRIORITY (critical): [DOCUMENTS] entries are UPLOADED
          DOCUMENTS (Source A) — the PRIMARY evidence base. The business plan,
          annual report, budget, or proposal IS primary evidence.
          Cite [D#] document content FIRST, before web sources [S#]. A web
          source NEVER overrules an uploaded document unless there is a
          material contradiction — if one exists, state it explicitly.
          NEVER conclude "no evidence exists", "unknown entity", "no product",
          "no founder information", "no market validation", or "no operational history"
          when [DOCUMENTS] contains substantive uploaded documents: read their content and reason from it.
        - Use ONLY the provided context pack: generated report, evidence sources,
          agent/syndicate outputs, risk analysis, and futures analysis.
        - Do not use outside knowledge, assumptions, or web browsing.
        - If the context does not support an answer, say what is missing and what
          evidence would be needed — and distinguish "not documented" from
          "no evidence exists".
        - Include citations when helpful using context labels: [REPORT], [R#], [V#], [F#],
          [S#] for web sources, and [D#] for document evidence.
        - The [ASSESSMENT_CONTEXT] section contains intake facts (assessment type,
          organisation, founder/lead, sector, country, uploaded documents, trust score).
        - The [DOMAIN_SIGNALS] section carries the signal domains in the order
          the analysis should reason through them: Community, Trust, Funding,
          Programme Delivery, Risk, Opportunity, Climate, Environment, Market,
          Tourism. Cite [DOMAIN_SIGNALS] for domain exposure questions.

        Special handling for key questions:
        - If the user asks "{decision_question}" (or similar):
          * {decision_label}
          * Confidence
          * Top 3 reasons
          * Top 3 risks
          * Required verification
          * Recommended action
          * Next question I'd ask
        - If the user asks "what evidence supports this?":
          1) Uploaded documents [D#] with specific sections/claims;
          2) Assessment Context facts;
          3) Signals [DOMAIN_SIGNALS] derived from that evidence;
          4) Trust graph / evidence integrity;
          5) External research [S#] as corroboration ONLY.
        - If the user asks about "{pass_trigger_label}":
          * Decision triggers
          * Why they matter
          * Verification needed
          * Recommended action
          * Next question I'd ask
        - If the user asks "what evidence is weak":
          * Weak Evidence
          * Why it matters
          * Impact on the decision
          * How to improve confidence
          * Next question I'd ask
        - If the user asks to "{summary_target}":
          * Verdict
          * Core thesis / capacity assessment
          * Top risks
          * Verification items
          * Recommended action
        """
    ).strip()
    if brief.evidence_integrity:
        ei = brief.evidence_integrity
        system += (
            f"\n\nEvidence integrity grounding rules:"
            f"\n- The evidence for this deal has been assessed as Grade {ei.integrity_grade.value} "
            f"({ei.integrity_score:.0f}/100) with {ei.evidence_depth.value} depth and "
            f"{ei.consistency_status.value} consistency. Cite [EVIDENCE_INTEGRITY] when "
            f"answering questions about evidence quality, source reliability, or confidence."
            f"\n- If contradictions [C#] or unsupported claims [U#] are relevant to the "
            f"question, surface them explicitly. Do not downplay evidence-quality concerns."
        )

    tm = brief.thesis_match
    if tm:
        st_str = tm.status.value if hasattr(tm.status, "value") else str(tm.status)
        system += (
            f"\n\nVC Thesis Engine grounding rules:"
            f"\n- The fund thesis match for this deal has been evaluated as {tm.overall_match:.0f}% "
            f"(Status: {st_str}; Sector: {tm.sector_fit}, Stage: {tm.stage_fit}, Geo: {tm.geography_fit}, Evidence Fit: {tm.evidence_fit}). "
            f"Cite [THESIS_FIT] when answering questions about fund thesis fit, sector alignment, check size, or thesis status."
        )
    user = textwrap.dedent(
        f"""
        Context pack:
        {context}

        Session chat history:
        {history_text or 'No prior messages.'}

        User question:
        {question}
        """
    ).strip()
    # Multi-provider: routes through AIProviderManager failover chain
    # (OpenAI → Groq → Gemini → OpenRouter → HuggingFace). Provider failures
    # never surface to users — orchestrator_adapter falls back to Document
    # Intelligence Mode.
    return LLMClient().manager.chat(system=system, user=user, history=history, temperature=0.2)
