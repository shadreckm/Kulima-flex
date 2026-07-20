"""Grounded follow-up Q&A for the Ask the Investment Committee tab."""

from __future__ import annotations

import textwrap
from kulima.llm import LLMClient
from kulima.models import InvestmentBrief

MAX_CONTEXT_CHARS = 18000


def _clip(value: str, limit: int = 1200) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _bullet_list(items: list[str], limit: int = 8) -> str:
    return "\n".join(f"- {_clip(item, 500)}" for item in items[:limit]) or "- None provided"


def build_ask_ic_context(brief: InvestmentBrief) -> str:
    """Build a bounded, citable context pack from only generated IC artifacts."""
    sections: list[str] = [
        "[REPORT]",
        f"Founder: {brief.founder_name}",
        f"Startup: {brief.startup_name}",
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
        f"Investment readiness: {brief.investment_readiness:.0f}/100",
        f"Confidence: {brief.confidence_level.value} ({brief.confidence:.2f})",
        f"Executive summary: {_clip(brief.executive_summary, 1800)}",
        f"Founder assessment: {_clip(brief.founder_assessment, 1600)}",
        f"Startup assessment: {_clip(brief.startup_assessment, 1600)}",
        f"Market assessment: {_clip(brief.market_assessment, 1600)}",
        f"Risk assessment: {_clip(brief.risk_assessment, 1600)}",
        f"Investment recommendation: {_clip(brief.investment_recommendation, 1600)}",
        "Next steps:\n" + _bullet_list(brief.next_steps),
        "Explainability:\n" + _bullet_list(brief.explainability, 12),
    ]

    if brief.red_flags:
        sections.append("[RISK_ANALYSIS]")
        for i, flag in enumerate(brief.red_flags, 1):
            sections.append(
                f"[R{i}] {flag.severity.upper()} — {flag.title}: "
                f"{_clip(flag.detail, 700)} Mitigation: {_clip(flag.mitigation, 500)}"
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
        sections.append("[EVIDENCE_SOURCES]")
        for i, src in enumerate(brief.sources, 1):
            sections.append(
                f"[S{i}] {src.title}\nURL: {src.url}\nSnippet: {_clip(src.snippet, 800)}\n"
                f"Relevance: {src.relevance:.2f}; confidence: {src.confidence_score:.2f}; type: {src.source_type}"
            )

    context = "\n\n".join(sections)
    return context[:MAX_CONTEXT_CHARS]


def answer_ask_ic_question(
    brief: InvestmentBrief, question: str, history: list[dict[str, str]] | None = None
) -> str:
    """Answer a follow-up question as an IC analyst using only the brief context."""
    history_text = "\n".join(
        f"{msg.get('role', 'user').upper()}: {_clip(msg.get('content', ''), 800)}"
        for msg in (history or [])[-8:]
    )
    context = build_ask_ic_context(brief)
    system = textwrap.dedent(
        """
        You are an investment committee analyst for Kulima FLEX. Answer follow-up
        questions in a concise, sober, partner-grade IC style.

        Grounding rules:
        - Use ONLY the provided context pack: generated report, evidence sources,
          agent/syndicate outputs, risk analysis, and futures analysis.
        - Do not use outside knowledge, assumptions, market facts, or web browsing.
        - If the context does not support an answer, say what is missing and what
          evidence would be needed.
        - Include citations whenever possible using the context labels, e.g. [REPORT],
          [R1], [V2], [F1], [S3]. For source-backed claims, prefer [S#].
        - Style the response as if it comes from an investment committee analyst.
        """
    ).strip()
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
    return LLMClient().complete(system=system, user=user, temperature=0.2)
