"""Investment Memo Agent — top-tier VC communication output."""

from __future__ import annotations

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, SourceAttribution
from kulima.research import ResearchEngine


class InvestmentMemoAgent(BaseAgent):
    name = "Investment Memo Agent"

    SYSTEM = """You are the partner writing an Investment Committee memo for a top-tier Africa-focused fund.
Voice: Sequoia clarity + a16z ambition + YC candor. No fluff. No buzzword salad.
Produce IC-ready prose that a partner can forward to LPs.

SOURCE PRIORITY (critical):
1. Uploaded documents (Source A) are the PRIMARY evidence base — cite them FIRST and by name.
2. Connected systems (Source B) next.
3. External web research (Source C) is corroborative only. NEVER allow a web source to overrule an uploaded document unless there is a material contradiction — if one exists, state it explicitly.
Never conclude that 'no evidence exists' or that the entity is 'unknown' when uploaded documents are present. The business plan IS evidence. The annual report IS evidence. The proposal IS evidence.

GROUNDING CONTRACT (critical — hallucination ban):
- Every factual claim about the entity (sector, customers, product, geography, revenue model) MUST come from the [DOCUMENTS] / [EVIDENCE] sections of the dossier.
- NEVER invent a sector, customer group, business model or technology for the entity. If the document says the entity is X, the memo describes X — even if web sources suggest otherwise.
- Where the documents do not specify a detail, write 'not specified in uploaded documents' — never fill the gap with assumption.
- Use the document's OWN words for the entity's self-description (e.g. 'decision intelligence company', 'NGO', 'destination business').

Return JSON with exactly these investor-grade sections:
executive_summary (2-3 dense paragraphs: what the entity does, why now, key underwriting question),
founder_assessment (evidence-backed judgment on founder-market fit, credibility, velocity, gaps),
startup_assessment (product, traction, business model, defensibility, stage readiness),
market_assessment (TAM/SAM/SOM framing, Africa-specific tailwinds/constraints, competitive map),
risk_assessment (ranked critical risks, what would change your mind, mitigations),
investment_recommendation (prose ending with clear Invest / Co-Invest / Observe / Pass / Follow-On Watch),
confidence_score (0-100 numeric memo confidence),
next_steps (array of 5-8 concrete diligence actions with owners/timeframes),
one_liner_thesis (string),
conviction_paragraph (string).
Use source confidence explicitly. Distinguish verified evidence from inference. Sound like a Tier-1 VC investment memo, not a generic report.
"""

    # Phase 6: entity-adaptive system prompts — reports adapt automatically and
    # startup templates are NEVER reused for NGOs or other entity types.
    ENTITY_SYSTEM_PROMPTS: dict[str, str] = {
        "ngo": SYSTEM.replace(
            "Investment Committee memo for a top-tier Africa-focused fund",
            "Capacity Assessment for a development finance and grantmaking audience",
        ).replace(
            "ending with clear Invest / Co-Invest / Observe / Pass / Follow-On Watch",
            "ending with Strong Capacity / Moderate Capacity / Needs Strengthening",
        ),
        "development_program": SYSTEM.replace(
            "Investment Committee memo for a top-tier Africa-focused fund",
            "Program Review for a donor and implementation audience",
        ).replace(
            "ending with clear Invest / Co-Invest / Observe / Pass / Follow-On Watch",
            "ending with Ready / Requires Support / At Risk",
        ),
        "government_program": SYSTEM.replace(
            "Investment Committee memo for a top-tier Africa-focused fund",
            "Public Program Review for government oversight stakeholders",
        ).replace(
            "ending with clear Invest / Co-Invest / Observe / Pass / Follow-On Watch",
            "ending with Effective / Monitor / Intervene",
        ),
        "tourism_sme": SYSTEM.replace(
            "Investment Committee memo for a top-tier Africa-focused fund",
            "Tourism Resilience Assessment for hospitality investors and destination stakeholders",
        ).replace(
            "ending with clear Invest / Co-Invest / Observe / Pass / Follow-On Watch",
            "ending with Ready for Growth / Build Resilience / High Risk",
        ),
    }

    def run(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution] | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        context = context or {}
        sources = sources or []
        entity_profile = context.get("entity_profile") or {}
        entity_type = str(entity_profile.get("entityType") or "startup")
        system = self.ENTITY_SYSTEM_PROMPTS.get(entity_type, self.SYSTEM)
        dossier = self._build_dossier(founder, startup, context, sources)

        try:
            data = self.llm.complete_json(
                system=system, user=dossier, temperature=0.4
            )
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                summary="Memo generation degraded.",
                findings=[str(exc)],
                sources=sources,
                confidence=0.2,
                metadata=self._skeleton(founder, startup),
                raw_reasoning=str(exc),
            )

        next_steps = [str(s) for s in data.get("next_steps", [])]
        return AgentResult(
            agent_name=self.name,
            summary=str(data.get("executive_summary", "")),
            findings=next_steps,
            sources=sources,
            confidence=float(context.get("confidence", 0.6)),
            raw_reasoning=str(data.get("conviction_paragraph", "")),
            metadata={
                "executive_summary": data.get("executive_summary", ""),
                "founder_assessment": data.get("founder_assessment", ""),
                "startup_assessment": data.get("startup_assessment", ""),
                "market_assessment": data.get("market_assessment", ""),
                "risk_assessment": data.get("risk_assessment", ""),
                "investment_recommendation": data.get("investment_recommendation", ""),
                "next_steps": next_steps,
                "one_liner_thesis": data.get("one_liner_thesis", ""),
                "conviction_paragraph": data.get("conviction_paragraph", ""),
                "confidence_score": data.get(
                    "confidence_score",
                    round(float(context.get("confidence", 0.6)) * 100),
                ),
            },
        )

    def _build_dossier(
        self,
        founder: str,
        startup: str,
        context: dict,
        sources: list[SourceAttribution],
    ) -> str:
        entity_profile = context.get("entity_profile") or {}
        return f"""
Deal: {founder} / {startup}
Entity type: {entity_profile.get('entityLabel', 'Startup') if entity_profile else 'Startup'} — use the matching assessment framework and vocabulary.
SECTOR AUTHORITY (Source A): the document-declared sector is authoritative. If the uploaded document declares a sector label (e.g. 'Sector: Technology'), the memo MUST use that sector verbatim and MUST NOT replace it with a keyword-guessed or web-inferred sector (e.g. never invent 'AgriTech' for a technology platform whose documents say otherwise).
SUBJECT DECLARATION (authoritative — the entity's own words from Source A. The memo MUST describe the entity as stated here; web sources about similarly-named companies NEVER redefine the entity):
{context.get('subject_declaration') or '(not extracted — rely on the document text below)'}
Document classification (Source A, PRIMARY evidence — cite these first by name):
{chr(10).join('- ' + d.get('docClass', '?') + ': ' + d.get('filename', '') for d in (entity_profile.get('documentClassifications') or [])) or '- none uploaded'}
Scores: {context.get('scores', {})}
Recommendation hint: {context.get('recommendation_hint', 'Observe')}
Syndicate majority: {context.get('syndicate_majority', 'n/a')}
Trust score: {context.get('trust_score', 'n/a')}
Risk composite: {context.get('risk_score', 'n/a')}
Memo confidence target: {context.get('confidence', 0.6)}

Founder agent: {context.get('founder_summary', '')}
Startup agent: {context.get('startup_summary', '')}
Diligence agent: {context.get('diligence_summary', '')}
Risk agent: {context.get('risk_summary', '')}
Syndicate thesis: {context.get('syndicate_thesis', '')}
Future simulation: {context.get('future_summary', '')}

Evidence ([DOCUMENTS] = Source A primary — quote these verbatim when describing the entity; [WEB] = Source C corroborative only):
{ResearchEngine.evidence_corpus(sources, 10)}
""".strip()

    @staticmethod
    def _skeleton(founder: str, startup: str) -> dict:
        return {
            "executive_summary": (
                f"Preliminary memo on {founder} / {startup}. The AI memo agent was "
                "temporarily unavailable (provider rate limit), so this narrative is "
                "pending regeneration. The uploaded documents remain the primary "
                "evidence base (Source A); the trust score and deterministic signals "
                "already reflect them."
            ),
            "founder_assessment": "AI founder analysis unavailable (provider rate limit); verify identity and track record from the uploaded documents and references.",
            "startup_assessment": "AI product analysis unavailable (provider rate limit); the uploaded business plan remains the primary product evidence.",
            "market_assessment": "AI market analysis unavailable (provider rate limit); uploaded market-validation sections remain the primary market evidence.",
            "risk_assessment": "AI risk analysis unavailable (provider rate limit); deterministic risk scoring from document trust and evidence integrity still applies.",
            "investment_recommendation": "Review Required — regenerate the AI memo when a provider is available; do not decide from this degraded narrative alone.",
            "next_steps": [
                "Re-run the full intelligence pipeline when AI providers recover",
                "Review uploaded documents directly — they remain the primary evidence",
                "Collect primary founder interview",
            ],
            "one_liner_thesis": "Pending AI regeneration — uploaded documents remain the primary evidence.",
            "conviction_paragraph": "Pending.",
        }
