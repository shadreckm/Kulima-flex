"""Due Diligence Agent — structured IC-grade diligence checklist."""

from __future__ import annotations

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, RedFlag, ScoreDimension, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import clamp


class DueDiligenceAgent(BaseAgent):
    name = "Due Diligence Agent"

    SYSTEM = """You are a McKinsey + top-tier VC diligence lead for African investments.
Produce an IC-ready diligence readout covering team, product, traction proxies, legal/regulatory,
capital structure unknowns, and go-to-market realism.
Return JSON:
summary,
scores: [{name, score, rationale, confidence}] names:
Team Diligence, Product Diligence, Traction Signal, Regulatory Posture, GTM Realism, Data Completeness,
findings: [string],
open_questions: [string],
red_flags: [{severity, title, detail, mitigation, confidence}],
diligence_grade (A|B|C|D)
"""

    def run(
        self,
        founder: str,
        startup: str,
        sources: list[SourceAttribution] | None = None,
        context: dict | None = None,
    ) -> AgentResult:
        context = context or {}
        # Prefer orchestrator-provided OSINT — avoid duplicate Tavily round-trips
        pooled = ResearchEngine._dedupe(list(sources or []))
        corpus = ResearchEngine.evidence_corpus(pooled)

        prior = ""
        if context.get("founder_summary"):
            prior += f"\nFounder Agent: {context['founder_summary']}"
        if context.get("startup_summary"):
            prior += f"\nStartup Agent: {context['startup_summary']}"

        try:
            data = self.llm.complete_json(
                system=self.SYSTEM,
                user=f"Founder: {founder}\nStartup: {startup}\nPrior agents:{prior}\n\nEvidence:\n{corpus}",
            )
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                summary=f"Diligence incomplete (degraded): {exc}",
                scores=[
                    ScoreDimension(
                        name="Data Completeness",
                        score=clamp(30 + len(pooled) * 4),
                        rationale="Fallback completeness estimate",
                        confidence=0.3,
                    )
                ],
                sources=pooled,
                confidence=0.25,
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
        ]
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
        for q in data.get("open_questions", [])[:6]:
            findings.append(f"Open question: {q}")

        return AgentResult(
            agent_name=self.name,
            summary=str(data.get("summary", "Diligence readout complete.")),
            scores=scores,
            findings=findings,
            red_flags=red_flags,
            sources=pooled,
            confidence=min(0.4 + len(pooled) * 0.04, 0.88),
            raw_reasoning=str(data.get("diligence_grade", "")),
            metadata={
                "diligence_grade": data.get("diligence_grade", "C"),
                "open_questions": data.get("open_questions", []),
            },
        )
