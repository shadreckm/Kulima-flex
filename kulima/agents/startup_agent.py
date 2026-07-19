"""Startup Intelligence Agent — market, competition, model, growth, readiness."""

from __future__ import annotations

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, RedFlag, ScoreDimension, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import clamp


class StartupIntelligenceAgent(BaseAgent):
    name = "Startup Intelligence Agent"

    SYSTEM = """You are a Sequoia/a16z-caliber startup analyst focused on African markets.
Assess market opportunity, competitive landscape, business model quality, growth potential,
and investment readiness. Explicitly adjust for African market realities: fragmented distribution,
mobile-money rails, FX risk, infrastructure constraints, and leapfrog dynamics.
Return JSON:
summary, sector, geography, stage,
scores: [{name, score, rationale, confidence}] with names:
Market Opportunity, Competitive Position, Business Model, Growth Potential, Investment Readiness,
findings: [string],
red_flags: [{severity, title, detail, mitigation, confidence}],
business_model_thesis (string),
tam_narrative (string)
"""

    def run(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution] | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        sources = sources or self.research.research_startup(founder, startup)
        # Skip extra market OSINT when orchestrator already bundled it
        if context and context.get("skip_market_research"):
            merged = ResearchEngine._dedupe(sources)
        else:
            market_sources = self.research.research_market(startup)
            merged = ResearchEngine._dedupe(sources + market_sources)
        corpus = ResearchEngine.evidence_corpus(merged)

        try:
            data = self.llm.complete_json(
                system=self.SYSTEM,
                user=f"Founder: {founder}\nStartup: {startup}\n\nEvidence:\n{corpus}",
            )
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                summary=f"Partial startup assessment (degraded): {exc}",
                scores=self._heuristic(merged),
                sources=merged,
                confidence=0.3,
                raw_reasoning=str(exc),
            )

        scores = [
            ScoreDimension(
                name=str(s.get("name", "Dimension")),
                score=clamp(float(s.get("score", 50))),
                rationale=str(s.get("rationale", "")),
                confidence=float(s.get("confidence", 0.55)),
            )
            for s in data.get("scores", [])
        ] or self._heuristic(merged)

        red_flags = [
            RedFlag(
                severity=str(rf.get("severity", "medium")),
                title=str(rf.get("title", "Concern")),
                detail=str(rf.get("detail", "")),
                mitigation=str(rf.get("mitigation", "")),
                confidence=float(rf.get("confidence", 0.6)),
            )
            for rf in data.get("red_flags", [])
        ]

        return AgentResult(
            agent_name=self.name,
            summary=str(data.get("summary", "Startup assessment complete.")),
            scores=scores,
            findings=[str(f) for f in data.get("findings", [])],
            red_flags=red_flags,
            sources=merged,
            confidence=min(0.35 + len(merged) * 0.05, 0.9),
            raw_reasoning=str(data.get("business_model_thesis", "")),
            metadata={
                "sector": data.get("sector", ""),
                "geography": data.get("geography", ""),
                "stage": data.get("stage", ""),
                "tam_narrative": data.get("tam_narrative", ""),
                "business_model_thesis": data.get("business_model_thesis", ""),
            },
        )

    def _heuristic(self, sources: list[SourceAttribution]) -> list[ScoreDimension]:
        base = clamp(50 + len(sources) * 3.5)
        return [
            ScoreDimension(name="Market Opportunity", score=clamp(base + 5), rationale="Evidence-volume proxy", confidence=0.4),
            ScoreDimension(name="Competitive Position", score=clamp(base - 8), rationale="Limited competitive intel", confidence=0.35),
            ScoreDimension(name="Business Model", score=clamp(base - 2), rationale="Inferred model quality", confidence=0.35),
            ScoreDimension(name="Growth Potential", score=clamp(base), rationale="Africa leapfrog optionality", confidence=0.4),
            ScoreDimension(name="Investment Readiness", score=clamp(base - 10), rationale="Readiness inferred conservatively", confidence=0.35),
        ]
