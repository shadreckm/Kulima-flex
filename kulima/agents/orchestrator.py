"""Intelligence Orchestrator — multi-agent pipeline for Kulima FLEX."""

from __future__ import annotations

import logging
from collections.abc import Callable

from kulima.agents.diligence_agent import DueDiligenceAgent
from kulima.agents.founder_agent import FounderIntelligenceAgent
from kulima.agents.memo_agent import InvestmentMemoAgent
from kulima.agents.risk_agent import RiskAssessmentAgent
from kulima.agents.startup_agent import StartupIntelligenceAgent
from kulima.breakthrough.futures import ContinentalFuturesEngine
from kulima.breakthrough.syndicate import InvestorTwinSyndicate
from kulima.config import FUTURES_MODEL, SYNDICATE_MODEL
from kulima.core.documents.repository import DocumentRepository
from kulima.evidence_integrity import EvidenceIntegrityEngine
from kulima.llm import LLMClient
from kulima.models import EvidenceIntegrityReport, InvestmentBrief, Recommendation, SourceAttribution
from kulima.research import ResearchEngine
from kulima.scoring import (
    aggregate_agent_score,
    build_explainability,
    clamp,
    confidence_level,
    mean,
    parse_qualitative_score,
    recommendation_from_score,
)
from kulima.trust_graph import TrustGraphEngine

_log = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


class IntelligenceOrchestrator:
    """Runs the full Investment Intelligence Operating System pipeline."""

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.research = ResearchEngine()
        self.founder_agent = FounderIntelligenceAgent(self.llm, self.research)
        self.startup_agent = StartupIntelligenceAgent(self.llm, self.research)
        self.diligence_agent = DueDiligenceAgent(self.llm, self.research)
        self.risk_agent = RiskAssessmentAgent(self.llm, self.research)
        self.memo_agent = InvestmentMemoAgent(self.llm, self.research)
        self.trust_engine = TrustGraphEngine(self.llm)
        self.syndicate = InvestorTwinSyndicate(LLMClient(model=SYNDICATE_MODEL))
        self.futures = ContinentalFuturesEngine(LLMClient(model=FUTURES_MODEL))
        self.evidence_engine = EvidenceIntegrityEngine(self.llm)

    def analyze(
        self,
        founder: str,
        startup: str,
        on_progress: ProgressCallback | None = None,
        *,
        user_id: str | None = None,
        sector_hint: str = "",
        research_results: dict[str, list[SourceAttribution]] | None = None,
        entity_profile: dict | None = None,
        document_trust_scores: list[float] | None = None,
    ) -> InvestmentBrief:
        """Run the full intelligence pipeline.

        ``sector_hint`` is an optional additive refinement sourced from the
        shared Assessment Context (auto-extracted from uploaded documents).
        When empty, behaviour is identical to previous releases.

        ``entity_profile`` (Phase 4/5) steers entity-aware research queries and
        the decision framework. Uploaded documents remain the primary evidence
        base (Source A) — external research is corroborative only.

        ``document_trust_scores`` (Phase 7): Trust Engine scores of the run's
        uploaded documents. When present they are blended into the trust graph
        score so that a rich document dossier is never drowned out by thin web
        OSINT coverage (the root cause of "no evidence exists" verdicts).
        """
        def progress(pct: float, message: str) -> None:
            if on_progress:
                on_progress(pct, message)

        founder = founder.strip()
        startup = (startup or "").strip() or "Unnamed Venture"

        progress(0.05, "Initializing Investment Intelligence OS…")
        progress(0.12, "Parallel OSINT sweep — founder · startup · market · risks…")
        entity_type = "startup"
        if entity_profile:
            entity_type = str(entity_profile.get("entityType") or "startup")
        bundle = research_results or self.research.research_bundle(
            founder, startup, sector_hint, entity_type=entity_type
        )
        founder_sources = bundle["founder"]
        startup_sources = ResearchEngine._dedupe(bundle["startup"] + bundle["market"])
        risk_sources = bundle["risks"]
        all_sources = ResearchEngine._dedupe(
            founder_sources + startup_sources + risk_sources
        )

        # ── Evidence Integrity Engine — runs post-research, pre-agents ────────
        # Wrapped in a blanket try/except: failure is logged and the pipeline
        # continues with integrity_report = None.  No score is ever modified here.
        integrity_report: EvidenceIntegrityReport | None = None
        try:
            progress(0.18, "Evidence Integrity Engine — source consistency analysis…")
            integrity_report = self.evidence_engine.evaluate(
                all_sources, founder, startup, sector=sector_hint
            )
            _log.info(
                "EIE complete — grade %s (%.0f/100), sparse=%s, contradictions=%d",
                integrity_report.integrity_grade.value,
                integrity_report.integrity_score,
                integrity_report.sparse_mode,
                len(integrity_report.contradictions),
            )
        except Exception as _eie_exc:
            _log.warning(
                "EvidenceIntegrityEngine failed gracefully — pipeline continues: %s",
                _eie_exc,
            )
            integrity_report = None

        # Enrich evidence corpus with any document-backed sources associated
        # with this founder/startup (Phase B: Evidence Integration).
        #
        # Entity-aware intelligence (Phase 7 fix): the document SNIPPET is
        # filled from the document's actual extracted chunks. Previously the
        # snippet was empty, so agents saw only a filename and concluded
        # "the business plan has not been parsed / no evidence exists" even
        # though the full text was stored. Uploaded documents (Source A) are
        # given the highest confidence so they outrank every web source.
        try:
            doc_repo = DocumentRepository()
            doc_sources: list[SourceAttribution] = []
            for d in doc_repo.get_documents_for_subject(founder, startup, user_id=user_id):
                chunks = doc_repo.get_chunks_for_document(d.id)
                chunk_text = " ".join(c.text for c in chunks if c.text and c.text.strip())
                doc_sources.append(
                    SourceAttribution(
                        title=d.filename,
                        url=f"document://{d.id}",
                        snippet=chunk_text[:1200],
                        relevance=1.0,
                        source_type="document",
                        # Source A outranks all external web research.
                        confidence_score=0.98,
                    )
                )
            if doc_sources:
                # Documents first, then web sources, so corpus ranking keeps
                # uploaded evidence at the top.
                all_sources = ResearchEngine._dedupe(doc_sources + all_sources, limit=40)
                _log.info(
                    "Document evidence injected: %d doc(s), %d chars of primary text",
                    len(doc_sources),
                    sum(len(s.snippet) for s in doc_sources),
                )
        except Exception:
            # Fail closed: if document integration fails, continue with web
            # sources only so orchestrator behaviour and scoring remain
            # consistent for non-document runs.
            pass

        progress(0.30, "Parallel agents — Founder ∥ Startup intelligence…")
        from concurrent.futures import ThreadPoolExecutor

        # Source A (uploaded documents) is the PRIMARY evidence base. Every
        # agent receives the entity profile so its reasoning is anchored on
        # uploaded evidence before any web/OSINT material (Source C).
        agent_context = {
            "entity_profile": entity_profile or {},
            "document_trust_scores": document_trust_scores or [],
        }

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_fut = pool.submit(
                self.founder_agent.run,
                founder,
                startup,
                founder_sources,
                dict(agent_context),
            )
            s_fut = pool.submit(
                self.startup_agent.run,
                founder,
                startup,
                startup_sources,
                {"skip_market_research": True, **agent_context},
            )
            founder_result = f_fut.result()
            startup_result = s_fut.result()

        progress(0.50, "Parallel underwriting — Diligence ∥ Risk ∥ Trust Graph…")
        with ThreadPoolExecutor(max_workers=3) as pool:
            d_fut = pool.submit(
                self.diligence_agent.run,
                founder,
                startup,
                all_sources,
                {
                    "founder_summary": founder_result.summary,
                    "startup_summary": startup_result.summary,
                    **agent_context,
                },
            )
            r_fut = pool.submit(
                self.risk_agent.run,
                founder,
                startup,
                all_sources,
                {"risk_sources": risk_sources, **agent_context},
            )
            t_fut = pool.submit(
                self.trust_engine.build, founder, startup, all_sources
            )
            diligence_result = d_fut.result()
            risk_result = r_fut.result()
            trust_graph = t_fut.result()

        founder_score = aggregate_agent_score(founder_result, 55)
        startup_score = aggregate_agent_score(startup_result, 55)

        market_dims = [s for s in startup_result.scores if "Market" in s.name]
        if not market_dims:
            import logging
            logging.warning("Orchestrator: 'Market Opportunity' dimension missing from startup_result — falling back to aggregate startup score.")
        market_score = market_dims[0].score if market_dims else startup_score

        growth_dims = [s for s in startup_result.scores if "Growth" in s.name]
        if not growth_dims:
            import logging
            logging.warning("Orchestrator: 'Growth Potential' dimension missing from startup_result — falling back to aggregate startup score.")
        growth_potential = growth_dims[0].score if growth_dims else startup_score

        ready_dims = [s for s in startup_result.scores if "Readiness" in s.name]
        if not ready_dims:
            from kulima.errors import PipelineStageError
            raise PipelineStageError(
                stage="Orchestrator",
                message=(
                    "Startup AI output is missing the 'Investment Readiness' dimension. "
                    "Cannot compute investment readiness without structured AI output."
                ),
            )
        investment_readiness = ready_dims[0].score
        trust_score = trust_graph.trust_score

        # Phase 7 (Source Priority): uploaded documents are the primary
        # evidence base. Blend their Trust Engine scores into the trust graph
        # with 60% weight so a solid document dossier is never overruled by
        # thin external web coverage. Never lowers below the web-only score.
        if document_trust_scores:
            doc_mean = sum(document_trust_scores) / len(document_trust_scores)
            doc_count = len(document_trust_scores)
            # More documents → more weight on Source A evidence (cap 75%).
            doc_weight = min(0.75, 0.4 + 0.1 * (doc_count - 1))
            blended = doc_mean * doc_weight + trust_score * (1 - doc_weight)
            trust_score = round(max(trust_score, blended), 1)
            _log.info(
                "Trust blend: %d document(s) mean %.1f (weight %.0f%%) + web %.1f → %.1f",
                doc_count, doc_mean, doc_weight * 100, trust_graph.trust_score, trust_score,
            )

        risk_score = clamp(
            parse_qualitative_score(
                risk_result.metadata.get("composite_risk_score")
                or aggregate_agent_score(risk_result, 50),
                is_risk=True,
            )
        )

        overall = clamp(
            founder_score * 0.28
            + startup_score * 0.27
            + market_score * 0.18
            + trust_score * 0.12
            + investment_readiness * 0.10
            + (100 - risk_score) * 0.05
        )

        # Phase 7 (Source Priority): when a rich document dossier exists its
        # Trust Engine scores must be reflected in the overall verdict. Blend
        # the document-trust evidence into the composite so thin agent output
        # (transient AI quality) can never drown a well-documented entity.
        if document_trust_scores:
            doc_mean = sum(document_trust_scores) / len(document_trust_scores)
            doc_count = len(document_trust_scores)
            doc_weight = min(0.35, 0.15 + 0.05 * (doc_count - 1))
            overall = round(clamp(overall * (1 - doc_weight) + doc_mean * doc_weight), 1)
            _log.info(
                "Overall blend: %d document(s) mean %.1f (weight %.0f%%) → overall %.1f",
                doc_count, doc_mean, doc_weight * 100, overall,
            )

        red_flags = (
            founder_result.red_flags
            + startup_result.red_flags
            + diligence_result.red_flags
            + risk_result.red_flags
        )
        # Deduplicate by title
        seen = set()
        unique_flags = []
        for rf in red_flags:
            if rf.title in seen:
                continue
            seen.add(rf.title)
            unique_flags.append(rf)

        rec_hint = recommendation_from_score(overall, risk_score, len(unique_flags))

        _scores_line = (
            f"Founder score {founder_score:.0f} | Startup {startup_score:.0f} | "
            f"Market {market_score:.0f} | Trust {trust_score:.0f} | Risk {risk_score:.0f}"
        )
        _agents_lines = (
            f"Founder: {founder_result.summary}\nStartup: {startup_result.summary}\n"
            f"Diligence: {diligence_result.summary}\nRisk: {risk_result.summary}"
        )
        # Prepend a compact EIE summary so Syndicate twins vote knowing evidence quality.
        # Max 500 chars; omitted entirely when integrity_report is None.
        _eie_summary = _build_eie_dossier_line(integrity_report)
        dossier = (
            (_eie_summary + "\n" if _eie_summary else "")
            + _scores_line + "\n"
            + _agents_lines
        )

        progress(0.72, "Parallel IC — Twin Syndicate (5 votes) ∥ Continental Futures…")
        with ThreadPoolExecutor(max_workers=2) as pool:
            syn_fut = pool.submit(
                self.syndicate.convene, founder, startup, dossier, all_sources
            )
            fut_fut = pool.submit(
                self.futures.simulate,
                founder,
                startup,
                overall,
                market_score,
                risk_score,
                str(startup_result.metadata.get("sector", "")),
                str(startup_result.metadata.get("geography", "")),
                dossier,
            )
            syndicate = syn_fut.result()
            future = fut_fut.result()

        # Blend algorithmic rec with Twin Syndicate final recommendation
        syndicate_final = syndicate.final_recommendation or syndicate.majority_vote
        recommendation = _blend_recommendation(rec_hint, syndicate_final, overall)

        conf = mean(
            [
                founder_result.confidence,
                startup_result.confidence,
                diligence_result.confidence,
                risk_result.confidence,
                min(0.35 + len(all_sources) * 0.05, 0.9),
            ]
        )

        progress(0.92, "Investment Memo Agent drafting partner-grade IC paper…")
        memo = self.memo_agent.run(
            founder,
            startup,
            all_sources,
            context={
                "scores": {
                    "overall": overall,
                    "founder": founder_score,
                    "startup": startup_score,
                    "market": market_score,
                    "trust": trust_score,
                    "risk": risk_score,
                },
                "recommendation_hint": recommendation.value,
                "entity_profile": entity_profile or {},
                "syndicate_majority": syndicate_final.value,
                "syndicate_thesis": syndicate.consensus_thesis,
                "syndicate_consensus_score": syndicate.consensus_score,
                "syndicate_dissent_score": syndicate.dissent_score,
                "trust_score": trust_score,
                "risk_score": risk_score,
                "founder_summary": founder_result.summary,
                "startup_summary": startup_result.summary,
                "diligence_summary": diligence_result.summary,
                "risk_summary": risk_result.summary,
                "future_summary": (
                    future.africa_conditions_summary
                    or future.simulation_notes
                    or (future.scenarios[1].revenue_growth_outlook if len(future.scenarios) > 1 else "")
                ),
                "futures_most_likely": future.most_likely_case,
                "confidence": conf,
            },
        )
        meta = memo.metadata

        explainability = build_explainability(
            founder_score,
            startup_score,
            market_score,
            trust_score,
            risk_score,
            len(all_sources),
            syndicate.consensus_score or syndicate.average_score,
        )
        explainability.append(
            f"Twin Syndicate final recommendation: {syndicate_final.value} "
            f"(consensus {syndicate.consensus_score:.0f}/100, "
            f"dissent {syndicate.dissent_score:.0f}/100)."
        )
        if future.scenarios:
            for s in future.scenarios:
                explainability.append(
                    f"Continental Futures {s.emoji} {s.name}: "
                    f"success {s.success_probability:.0f}%, "
                    f"attractiveness {s.investor_attractiveness_score:.0f}/100."
                )
        explainability.append(
            f"Continental Futures EV (36m): ${future.expected_value_usd:,.0f} "
            f"with Africa risk premium {future.africa_risk_premium:.1f}pp "
            f"(most likely: {future.most_likely_case or 'Base Case'})."
        )

        # Issue 4: surface agent-extracted market-validation categories in the brief.
        _mv = startup_result.metadata.get("market_validation") or {}
        if isinstance(_mv, dict) and _mv:
            explainability.append(
                "Market validation extracted from uploaded documents: "
                + ", ".join(sorted(_mv.keys())) + "."
            )

        progress(1.0, "Intelligence complete — IC pack ready.")
        brief_out = InvestmentBrief(
            founder_name=founder,
            startup_name=startup,
            sector=str(startup_result.metadata.get("sector", "")),
            geography=str(startup_result.metadata.get("geography", "")),
            stage=str(startup_result.metadata.get("stage", "")),
            executive_summary=str(meta.get("executive_summary", memo.summary)),
            founder_assessment=str(meta.get("founder_assessment", founder_result.summary)),
            startup_assessment=str(meta.get("startup_assessment", startup_result.summary)),
            market_assessment=str(meta.get("market_assessment", "")),
            risk_assessment=str(meta.get("risk_assessment", risk_result.summary)),
            investment_recommendation=str(meta.get("investment_recommendation", recommendation.value)),
            next_steps=list(meta.get("next_steps") or memo.findings),
            recommendation=recommendation,
            overall_score=overall,
            founder_score=founder_score,
            startup_score=startup_score,
            market_score=market_score,
            trust_score=trust_score,
            risk_score=risk_score,
            growth_potential=growth_potential,
            investment_readiness=investment_readiness,
            confidence=conf,
            confidence_level=confidence_level(conf),
            red_flags=unique_flags,
            agent_results={
                "founder": founder_result,
                "startup": startup_result,
                "diligence": diligence_result,
                "risk": risk_result,
                "memo": memo,
            },
            trust_graph=trust_graph,
            syndicate=syndicate,
            future_simulation=future,
            sources=all_sources,
            explainability=explainability,
            evidence_integrity=integrity_report,
        )
        try:
            from kulima.thesis import evaluate_thesis_match
            brief_out.thesis_match = evaluate_thesis_match(brief_out)
        except Exception as _th_exc:
            _log.warning("Thesis evaluation failed gracefully: %s", _th_exc)

        return brief_out


def _build_eie_dossier_line(report: EvidenceIntegrityReport | None) -> str:
    """Return a compact EIE summary for the Twin Syndicate dossier (≤ 500 chars).

    Returns an empty string when the report is None — the caller omits the
    section entirely in that case.
    """
    if report is None:
        return ""

    lines: list[str] = [
        f"[EVIDENCE_INTEGRITY] Reliability: {report.integrity_grade.value} "
        f"({report.integrity_score:.0f}/100) · "
        f"Evidence Depth: {report.evidence_depth.value.title()} · "
        f"Consistency: {report.consistency_status.value.replace('_', ' ').title()}"
    ]

    if report.sparse_mode:
        lines.append("  Note: Sparse evidence corpus — limited OSINT available.")

    if report.contradictions:
        lines.append("  Top Issues:")
        for con in report.contradictions[:3]:           # cap at 3 in the dossier
            lines.append(f"  - {con.description[:120]}")

    summary = "\n".join(lines)
    # Hard cap at 500 chars as specified
    if len(summary) > 500:
        summary = summary[:497] + "…"
    return summary


def _blend_recommendation(
    algorithmic: Recommendation,
    syndicate: Recommendation,
    overall: float,
) -> Recommendation:
    # Preserve the calibrated scoring tier as the live recommendation.
    # The syndicate output remains available for memo/context layers, but it
    # should not flatten the calibrated tiers back into Pass-heavy averages.
    def _norm(rec: Recommendation) -> Recommendation:
        if rec in (Recommendation.INVEST, Recommendation.CO_INVEST):
            return rec
        if rec == Recommendation.PASS:
            return Recommendation.PASS
        return Recommendation.OBSERVE

    algorithmic = _norm(algorithmic)
    syndicate = _norm(syndicate)

    if algorithmic == Recommendation.CO_INVEST:
        return Recommendation.CO_INVEST
    if overall >= 80 and algorithmic == Recommendation.INVEST and syndicate == Recommendation.INVEST:
        return Recommendation.CO_INVEST
    return algorithmic
