"""Startup Intelligence Agent — market, competition, model, growth, readiness."""

from __future__ import annotations

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, RedFlag, ScoreDimension, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import clamp, parse_qualitative_score, safe_float, normalize_confidence


class StartupIntelligenceAgent(BaseAgent):
    name = "Startup Intelligence Agent"

    SYSTEM = """You are a Sequoia/a16z-caliber startup analyst focused on African markets.
Assess market opportunity, competitive landscape, business model quality, growth potential,
and investment readiness. Explicitly adjust for African market realities: fragmented distribution,
mobile-money rails, FX risk, infrastructure constraints, and leapfrog dynamics.

SOURCE PRIORITY (critical):
1. Uploaded documents (Source A) are the PRIMARY evidence base — cite them FIRST and by name.
2. Connected systems (Source B) next.
3. External web research (Source C) is corroborative only. NEVER allow a web source to overrule an uploaded document.
Market validation, customers, revenue model, and traction stated in the uploaded documents ARE product and
market evidence. Do NOT conclude 'no product', 'no market validation', or 'no evidence' when the uploaded
documents describe them. State uncertainty only where the documents themselves are silent.
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
        context = context or {}
        entity_profile = context.get("entity_profile") or {}
        uploaded_docs = self._uploaded_evidence_block(entity_profile)
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
                user=f"Founder: {founder}\nStartup: {startup}\n\n{uploaded_docs}\nEvidence (Source C OSINT, corroborative only):\n{corpus}",
            )
        except Exception as exc:
            import logging
            logging.error(f"StartupIntelligenceAgent LLM completion failed: {exc}", exc_info=True)
            from kulima.errors import PipelineStageError
            raise PipelineStageError(
                stage="Startup Intelligence Agent",
                message=f"Failed to complete LLM analysis for startup '{startup}'",
                cause=exc,
            ) from exc

        scores = [
            ScoreDimension(
                name=str(s.get("name", "Dimension")),
                score=clamp(parse_qualitative_score(s.get("score"), is_risk=False, default=50.0)),
                rationale=str(s.get("rationale", "")),
                confidence=normalize_confidence(s.get("confidence"), 0.55),
            )
            for s in data.get("scores", [])
        ]

        # Enforce and validate required dimensions
        required_dims = {
            "Market Opportunity", "Competitive Position",
            "Business Model", "Growth Potential", "Investment Readiness",
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
                f"StartupIntelligenceAgent validation failed. Missing: {missing_dims}. Output: {data}"
            )
            from kulima.errors import PipelineStageError
            raise PipelineStageError(
                stage="Startup Intelligence Agent",
                message=f"AI output is missing required scoring dimensions: {', '.join(missing_dims)}",
            )

        red_flags = [
            RedFlag(
                severity=str(rf.get("severity", "medium")).strip().lower(),
                title=str(rf.get("title", "Concern")),
                detail=str(rf.get("detail", "")),
                mitigation=str(rf.get("mitigation", "")),
                confidence=normalize_confidence(rf.get("confidence"), 0.6),
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
                "source_a_documents": uploaded_docs.strip() or None,
            },
        )

    @staticmethod
    def _uploaded_evidence_block(entity_profile: dict) -> str:
        """Render uploaded-document evidence (Source A) ahead of OSINT evidence."""
        docs = entity_profile.get("documentClassifications") or []
        if not docs:
            return ""
        lines = ["Uploaded Document Evidence (Source A, PRIMARY — cite these first by name):"]
        for d in docs:
            filename = d.get("filename", "unnamed document")
            doc_class = d.get("docClass", "document")
            summary = d.get("summary", "")
            line = f"- {doc_class}: {filename}"
            if summary:
                line += f" — {summary}"
            lines.append(line)
        extracted = entity_profile.get("extractedInsights") or {}
        if extracted:
            insights = "\n".join(f"- {k}: {v}" for k, v in extracted.items() if v)
            lines.append(f"Extracted entity facts from Source A:\n{insights}")
        return "\n".join(lines) + "\n\n"


