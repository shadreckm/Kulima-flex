"""Founder Intelligence Agent — credibility, leadership, reputation, digital footprint."""

from __future__ import annotations

import json

from kulima.agents.base import BaseAgent
from kulima.models import AgentResult, RedFlag, ScoreDimension, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import clamp, parse_qualitative_score, safe_float, normalize_confidence


class FounderIntelligenceAgent(BaseAgent):
    name = "Founder Intelligence Agent"

    SYSTEM = """You are a world-class venture partner specializing in African founder diligence.
Evaluate founder credibility, leadership quality, digital footprint authenticity, and reputation.
Be rigorous, evidence-based, and explicit about uncertainty.
Africa context matters: scarcity of public data is not automatically a red flag — weigh operator proof,
community trust, and execution under constraint more heavily than Silicon Valley signaling.

SOURCE PRIORITY (critical):
1. Uploaded documents (Source A) are the PRIMARY evidence base — cite them FIRST and by name.
2. Connected systems (Source B) next.
3. External web research (Source C) is corroborative only. NEVER allow a web source to overrule an uploaded document.
The entity profile, track record, and leadership evidence in the uploaded documents ARE founder evidence.
If the uploaded documents establish identity, roles, and history, the founder is NOT 'unknown' and has NOT
'no operational history'. State uncertainty only where the documents themselves are silent.
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
        context = context or {}
        entity_profile = context.get("entity_profile") or {}
        uploaded_docs = self._uploaded_evidence_block(entity_profile)
        corpus = ResearchEngine.evidence_corpus(sources)
        try:
            data = self.llm.complete_json(
                system=self.SYSTEM,
                user=f"Founder: {founder}\nStartup: {startup}\n\n{uploaded_docs}\nOSINT Evidence (Source C, corroborative only):\n{corpus}",
            )
        except json.JSONDecodeError as exc:
            # Resilience: a malformed JSON payload from one provider must not
            # kill the assessment. Retry once with a stricter instruction.
            import logging
            logging.warning("FounderIntelligenceAgent JSON parse failed — retrying with stricter format: %s", exc)
            try:
                data = self.llm.complete_json(
                    system=self.SYSTEM + "\n\nCRITICAL: Respond with a SINGLE valid JSON object. No prose, no markdown, no trailing text.",
                    user=f"Founder: {founder}\nStartup: {startup}\n\n{uploaded_docs}\nOSINT Evidence (Source C, corroborative only):\n{corpus}",
                    temperature=0.0,
                )
            except Exception as retry_exc:
                import logging
                logging.error(f"FounderIntelligenceAgent LLM completion failed after retry: {retry_exc}", exc_info=True)
                from kulima.errors import PipelineStageError
                raise PipelineStageError(
                    stage="Founder Intelligence Agent",
                    message=f"Failed to complete LLM analysis for founder '{founder}'",
                    cause=retry_exc
                ) from retry_exc
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
                confidence=normalize_confidence(s.get("confidence"), 0.55),
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
                confidence=normalize_confidence(rf.get("confidence"), 0.6),
            )
            for rf in data.get("red_flags", [])
        ]

        findings = [str(f) for f in data.get("findings", [])]
        if data.get("leadership_archetype"):
            findings.insert(0, f"Leadership archetype: {data['leadership_archetype']}")

        confidence = min(0.35 + len(sources) * 0.06, 0.92)
        if uploaded_docs:
            # Source A presence materially strengthens founder evidence confidence.
            confidence = min(confidence + 0.10, 0.95)
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
