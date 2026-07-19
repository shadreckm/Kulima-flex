"""Intelligence Orchestrator — multi-agent pipeline for Kulima FLEX VC Brain."""

from __future__ import annotations

from collections.abc import Callable

from kulima.agents.diligence_agent import DueDiligenceAgent
from kulima.agents.founder_agent import FounderIntelligenceAgent
from kulima.agents.memo_agent import InvestmentMemoAgent
from kulima.agents.risk_agent import RiskAssessmentAgent
from kulima.agents.startup_agent import StartupIntelligenceAgent
from kulima.breakthrough.futures import ContinentalFuturesEngine
from kulima.breakthrough.syndicate import InvestorTwinSyndicate
from kulima.config import FUTURES_MODEL, SYNDICATE_MODEL
from kulima.llm import LLMClient
from kulima.models import InvestmentBrief, Recommendation
from kulima.research import ResearchEngine
from kulima.scoring import (
    aggregate_agent_score,
    build_explainability,
    clamp,
    confidence_level,
    mean,
    recommendation_from_score,
)
from kulima.trust_graph import TrustGraphEngine

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

    def analyze(
        self,
        founder: str,
        startup: str,
        on_progress: ProgressCallback | None = None,
    ) -> InvestmentBrief:
        def progress(pct: float, message: str) -> None:
            if on_progress:
                on_progress(pct, message)

        founder = founder.strip()
        startup = (startup or "").strip() or "Unnamed Venture"

        progress(0.05, "Initializing Investment Intelligence OS…")
        progress(0.12, "Parallel OSINT sweep — founder · startup · market · risks…")
        bundle = self.research.research_bundle(founder, startup)
        founder_sources = bundle["founder"]
        startup_sources = ResearchEngine._dedupe(bundle["startup"] + bundle["market"])
        risk_sources = bundle["risks"]
        all_sources = ResearchEngine._dedupe(
            founder_sources + startup_sources + risk_sources
        )

        progress(0.30, "Parallel agents — Founder ∥ Startup intelligence…")
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_fut = pool.submit(
                self.founder_agent.run, founder, startup, founder_sources
            )
            s_fut = pool.submit(
                self.startup_agent.run,
                founder,
                startup,
                startup_sources,
                {"skip_market_research": True},
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
                },
            )
            r_fut = pool.submit(
                self.risk_agent.run,
                founder,
                startup,
                all_sources,
                {"risk_sources": risk_sources},
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
        market_score = market_dims[0].score if market_dims else startup_score
        growth_dims = [s for s in startup_result.scores if "Growth" in s.name]
        growth_potential = growth_dims[0].score if growth_dims else startup_score
        ready_dims = [s for s in startup_result.scores if "Readiness" in s.name]
        investment_readiness = ready_dims[0].score if ready_dims else clamp(startup_score - 5)
        trust_score = trust_graph.trust_score
        risk_score = float(
            risk_result.metadata.get("composite_risk_score")
            or aggregate_agent_score(risk_result, 50)
        )

        overall = clamp(
            founder_score * 0.28
            + startup_score * 0.27
            + market_score * 0.18
            + trust_score * 0.12
            + investment_readiness * 0.10
            + (100 - risk_score) * 0.05
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

        dossier = (
            f"Founder score {founder_score:.0f} | Startup {startup_score:.0f} | "
            f"Market {market_score:.0f} | Trust {trust_score:.0f} | Risk {risk_score:.0f}\n"
            f"Founder: {founder_result.summary}\nStartup: {startup_result.summary}\n"
            f"Diligence: {diligence_result.summary}\nRisk: {risk_result.summary}"
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

        progress(1.0, "Intelligence complete — IC pack ready.")
        return InvestmentBrief(
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
        )


def _blend_recommendation(
    algorithmic: Recommendation,
    syndicate: Recommendation,
    overall: float,
) -> Recommendation:
    # Normalize extended labels into the syndicate three-way ballot
    def _norm(rec: Recommendation) -> Recommendation:
        if rec in (Recommendation.INVEST, Recommendation.CO_INVEST):
            return Recommendation.INVEST
        if rec == Recommendation.PASS:
            return Recommendation.PASS
        return Recommendation.OBSERVE

    algorithmic = _norm(algorithmic)
    syndicate = _norm(syndicate)
    order = [
        Recommendation.PASS,
        Recommendation.OBSERVE,
        Recommendation.INVEST,
    ]
    ai = order.index(algorithmic)
    si = order.index(syndicate)
    blended = order[round((ai + si) / 2)]
    if overall >= 80 and syndicate == Recommendation.INVEST:
        return syndicate
    if overall < 45:
        return Recommendation.PASS
    return blended
