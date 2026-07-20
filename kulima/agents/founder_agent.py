"""Founder Intelligence Agent — credibility, leadership, reputation, digital footprint."""

from __future__ import annotations

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, RedFlag, ScoreDimension, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import clamp, parse_qualitative_score, safe_float


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
            import logging
            logging.error(f"FounderIntelligenceAgent LLM completion failed: {exc}", exc_info=True)
            from kulima.errors import PipelineStageError
            raise PipelineStageError(
                stage="Founder Intelligence Agent",
                message=f"Failed to complete LLM analysis for founder '{founder}'",
                cause=exc
            ) from exc

        scores = [
            ScoreDimension(
                name=str(s.get("name", "Dimension")),
                score=clamp(parse_qualitative_score(s.get("score"), is_risk=False, default=50.0)),
                rationale=str(s.get("rationale", "")),
                confidence=safe_float(s.get("confidence"), 0.55),
            )
            for s in data.get("scores", [])
        ]

        # Enforce and validate required dimensions
        required_dims = {"Credibility", "Leadership", "Digital Footprint", "Reputation", "Domain Expertise"}
        canonical_map = {d.lower(): d for d in required_dims}
        for s in scores:
            name_lower = s.name.lower()
            if name_lower in canonical_map:
                s.name = canonical_map[name_lower]

        returned_dims = {s.name for s in scores}
        missing_dims = required_dims - returned_dims
        if missing_dims:
            import logging
            logging.error(f"FounderIntelligenceAgent validation failed. Missing: {missing_dims}. Output was: {data}")
            from kulima.errors import PipelineStageError
            raise PipelineStageError(
                stage="Founder Intelligence Agent",
                message=f"AI output is missing required scoring dimensions: {', '.join(missing_dims)}"
            )

        red_flags = [
            RedFlag(
                severity=str(rf.get("severity", "medium")).strip().lower(),
                title=str(rf.get("title", "Concern")),
                detail=str(rf.get("detail", "")),
                mitigation=str(rf.get("mitigation", "")),
                confidence=safe_float(rf.get("confidence"), 0.6),
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
