"""Risk Assessment Agent — red flags, Africa-specific risk physics."""

from __future__ import annotations

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, RedFlag, ScoreDimension, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import clamp, parse_qualitative_score, safe_float


class RiskAssessmentAgent(BaseAgent):
    name = "Risk Assessment Agent"

    SYSTEM = """You are a former Palantir risk analyst + African market risk officer for a top VC.
Score downside risks. Higher risk score = worse. Cover: execution, market, regulatory, FX/macro,
key-person, competitive, reputational, and capital-structure risk.
Return JSON:
summary,
scores: [{name, score, rationale, confidence}] where score is RISK severity 0-100,
  names: Execution Risk, Market Risk, Regulatory Risk, FX Macro Risk, Key Person Risk,
         Competitive Risk, Reputational Risk, Capital Risk,
composite_risk_score (0-100),
findings: [string],
red_flags: [{severity, title, detail, mitigation, confidence}],
risk_posture (Conservative|Balanced|Aggressive tolerance match)
"""

    def run(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution] | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        context = context or {}
        # Prefer pre-fetched risk OSINT from orchestrator
        if context.get("risk_sources") is not None:
            risk_sources = list(context.get("risk_sources") or [])
        else:
            risk_sources = self.research.research_risks(founder, startup)
        pooled = ResearchEngine._dedupe((sources or []) + risk_sources)
        corpus = ResearchEngine.evidence_corpus(pooled)

        try:
            data = self.llm.complete_json(
                system=self.SYSTEM,
                user=f"Founder: {founder}\nStartup: {startup}\n\nEvidence:\n{corpus}",
            )
        except Exception as exc:
            import logging
            logging.error(f"RiskAssessmentAgent LLM completion failed: {exc}", exc_info=True)
            from kulima.errors import PipelineStageError
            raise PipelineStageError(
                stage="Risk Assessment Agent",
                message=f"Failed to complete LLM risk analysis for '{founder} / {startup}'",
                cause=exc,
            ) from exc

        scores = [
            ScoreDimension(
                name=str(s.get("name", "Risk")),
                score=clamp(parse_qualitative_score(s.get("score"), is_risk=True, default=50.0)),
                rationale=str(s.get("rationale", "")),
                confidence=safe_float(s.get("confidence"), 0.55),
            )
            for s in data.get("scores", [])
        ]

        # Enforce and validate required risk dimensions
        required_dims = {
            "Execution Risk", "Market Risk", "Regulatory Risk", "FX Macro Risk",
            "Key Person Risk", "Competitive Risk", "Reputational Risk", "Capital Risk",
        }
        canonical_map = {d.lower(): d for d in required_dims}
        for s in scores:
            if s.name.lower() in canonical_map:
                s.name = canonical_map[s.name.lower()]
        returned_dims = {s.name for s in scores}
        missing_dims = required_dims - returned_dims
        if missing_dims:
            import logging
            logging.error(
                f"RiskAssessmentAgent validation failed. Missing: {missing_dims}. Output: {data}"
            )
            from kulima.errors import PipelineStageError
            raise PipelineStageError(
                stage="Risk Assessment Agent",
                message=f"AI output is missing required risk dimensions: {', '.join(missing_dims)}",
            )

        composite = parse_qualitative_score(
            data.get("composite_risk_score"),
            is_risk=True,
            default=(sum(s.score for s in scores) / len(scores) if scores else 50.0)
        )

        red_flags = [
            RedFlag(
                severity=str(rf.get("severity", "medium")).strip().lower(),
                title=str(rf.get("title", "Risk")),
                detail=str(rf.get("detail", "")),
                mitigation=str(rf.get("mitigation", "")),
                confidence=safe_float(rf.get("confidence"), 0.65),
            )
            for rf in data.get("red_flags", [])
        ]

        return AgentResult(
            agent_name=self.name,
            summary=str(data.get("summary", "Risk assessment complete.")),
            scores=scores,
            findings=[str(f) for f in data.get("findings", [])],
            red_flags=red_flags,
            sources=pooled,
            confidence=min(0.4 + len(pooled) * 0.04, 0.9),
            raw_reasoning=str(data.get("risk_posture", "")),
            metadata={
                "composite_risk_score": clamp(composite),
                "risk_posture": data.get("risk_posture", "Balanced"),
            },
        )
