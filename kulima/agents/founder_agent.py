"""Founder Intelligence Agent — credibility, leadership, reputation, digital footprint."""

from __future__ import annotations

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, RedFlag, ScoreDimension, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import clamp


class FounderIntelligenceAgent(BaseAgent):
    name = "Founder Intelligence Agent"

    SYSTEM = """You are a world-class venture partner specializing in African founder diligence.
Evaluate founder credibility, leadership quality, digital footprint authenticity, and reputation.
Be rigorous, evidence-based, and explicit about uncertainty.
Africa context matters: scarcity of public data is not automatically a red flag — weigh operator proof,
community trust, and execution under constraint more heavily than Silicon Valley signaling.
Return JSON with keys:
summary (string),
scores: [{name, score 0-100, rationale, confidence 0-1}],
findings: [string],
red_flags: [{severity, title, detail, mitigation, confidence}],
leadership_archetype (string),
credibility_narrative (string)
Required score names: Credibility, Leadership, Digital Footprint, Reputation, Domain Expertise.
"""

    def run(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution] | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        sources = sources or self.research.research_founder(founder, startup)
        corpus = ResearchEngine.evidence_corpus(sources)
        try:
            data = self.llm.complete_json(
                system=self.SYSTEM,
                user=f"Founder: {founder}\nStartup: {startup}\n\nOSINT Evidence:\n{corpus}",
            )
        except Exception as exc:
            return self._fallback(founder, sources, str(exc))

        scores = [
            ScoreDimension(
                name=str(s.get("name", "Dimension")),
                score=clamp(float(s.get("score", 50))),
                rationale=str(s.get("rationale", "")),
                confidence=float(s.get("confidence", 0.55)),
            )
            for s in data.get("scores", [])
        ]
        if not scores:
            scores = self._heuristic_scores(sources)

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

        findings = [str(f) for f in data.get("findings", [])]
        if data.get("leadership_archetype"):
            findings.insert(0, f"Leadership archetype: {data['leadership_archetype']}")

        confidence = min(0.35 + len(sources) * 0.06, 0.92)
        return AgentResult(
            agent_name=self.name,
            summary=str(data.get("summary") or data.get("credibility_narrative") or "Founder assessment complete."),
            scores=scores,
            findings=findings,
            red_flags=red_flags,
            sources=sources,
            confidence=confidence,
            raw_reasoning=str(data.get("credibility_narrative", "")),
            metadata={
                "leadership_archetype": data.get("leadership_archetype"),
            },
        )

    def _heuristic_scores(self, sources: list[SourceAttribution]) -> list[ScoreDimension]:
        base = clamp(48 + len(sources) * 5)
        return [
            ScoreDimension(name="Credibility", score=base, rationale="Heuristic from evidence volume", confidence=0.4),
            ScoreDimension(name="Leadership", score=clamp(base - 3), rationale="Limited public leadership signal", confidence=0.35),
            ScoreDimension(name="Digital Footprint", score=clamp(40 + len(sources) * 6), rationale="Source breadth proxy", confidence=0.45),
            ScoreDimension(name="Reputation", score=clamp(base - 5), rationale="Sparse reputation corpus", confidence=0.35),
            ScoreDimension(name="Domain Expertise", score=clamp(base), rationale="Inferred from public mentions", confidence=0.35),
        ]

    def _fallback(self, founder: str, sources: list[SourceAttribution], error: str) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            summary=f"Partial founder assessment for {founder} (LLM degraded). Evidence-only heuristics applied.",
            scores=self._heuristic_scores(sources),
            findings=[f"LLM path error: {error}", f"Recovered from {len(sources)} sources."],
            sources=sources,
            confidence=0.3,
            raw_reasoning=error,
        )
