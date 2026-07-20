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
Return JSON with exactly these investor-grade sections:
executive_summary (2-3 dense paragraphs: what the company does, why now, key underwriting question),
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

    def run(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution] | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        context = context or {}
        sources = sources or []
        dossier = self._build_dossier(founder, startup, context, sources)

        try:
            data = self.llm.complete_json(
                system=self.SYSTEM, user=dossier, temperature=0.4
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
        return f"""
Deal: {founder} / {startup}
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

Evidence (ranked by source confidence; cite cautiously if confidence is low):
{ResearchEngine.evidence_corpus(sources, 10)}
""".strip()

    @staticmethod
    def _skeleton(founder: str, startup: str) -> dict:
        return {
            "executive_summary": f"Preliminary memo on {founder} / {startup} pending full model recovery.",
            "founder_assessment": "Insufficient generation path.",
            "startup_assessment": "Insufficient generation path.",
            "market_assessment": "Insufficient generation path.",
            "risk_assessment": "Insufficient generation path.",
            "investment_recommendation": "Observe — regenerate when model available.",
            "next_steps": [
                "Re-run full intelligence pipeline",
                "Collect primary founder interview",
            ],
            "one_liner_thesis": "Pending.",
            "conviction_paragraph": "Pending.",
        }
