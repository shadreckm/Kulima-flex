"""
BREAKTHROUGH FEATURE: Kulima Twin Syndicate Investment Committee
================================================================
Five investor twins independently underwrite every founder deal using
gpt-4.1-mini, then produce consensus, final recommendation, and dissent.
"""

from __future__ import annotations

from kulima.config import INVESTOR_ARCHETYPES, SYNDICATE_MODEL
from kulima.llm import LLMClient
from kulima.models import (
    InvestorVote,
    Recommendation,
    SourceAttribution,
    SyndicateDecision,
)
from kulima.research import ResearchEngine


# Invest / Observe / Pass only (hackathon IC ballot)
_SYNDICATE_RECS = {Recommendation.INVEST, Recommendation.OBSERVE, Recommendation.PASS}

_VOTE_POINTS = {
    Recommendation.INVEST: 100.0,
    Recommendation.OBSERVE: 50.0,
    Recommendation.PASS: 0.0,
}


class InvestorTwinSyndicate:
    """Virtual IC: five investor twins independently vote, then reconcile."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient(model=SYNDICATE_MODEL)

    def convene(
        self,
        founder: str,
        startup: str,
        dossier: str,
        sources: list[SourceAttribution] | None = None,
    ) -> SyndicateDecision:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        votes: list[InvestorVote | None] = [None] * len(INVESTOR_ARCHETYPES)
        src = sources or []

        with ThreadPoolExecutor(max_workers=5) as pool:
            future_map = {
                pool.submit(
                    self._cast_vote, archetype, founder, startup, dossier, src
                ): idx
                for idx, archetype in enumerate(INVESTOR_ARCHETYPES)
            }
            for fut in as_completed(future_map):
                votes[future_map[fut]] = fut.result()

        resolved: list[InvestorVote] = [v for v in votes if v is not None]

        consensus_score = self._consensus_score(resolved)
        final_recommendation = self._final_recommendation(resolved)
        dissent_score = self._dissent_score(resolved)
        debate = self._debate(founder, startup, resolved, dossier)

        blocking: list[str] = []
        for v in resolved:
            if v.vote == Recommendation.PASS and v.confidence_score >= 65:
                if v.major_concern:
                    blocking.append(v.major_concern)

        return SyndicateDecision(
            votes=resolved,
            majority_vote=final_recommendation,
            average_score=consensus_score,
            dissent_index=dissent_score / 100.0,
            consensus_score=consensus_score,
            final_recommendation=final_recommendation,
            dissent_score=dissent_score,
            debate_transcript=str(debate.get("transcript", "")),
            consensus_thesis=str(
                debate.get("consensus_thesis")
                or f"Committee lands on {final_recommendation.value} "
                f"with consensus {consensus_score:.0f}/100 "
                f"(dissent {dissent_score:.0f}/100)."
            ),
            blocking_concerns=blocking[:5]
            or [str(c) for c in debate.get("blocking_concerns", [])][:5],
        )

    def _cast_vote(
        self,
        archetype: dict,
        founder: str,
        startup: str,
        dossier: str,
        sources: list[SourceAttribution],
    ) -> InvestorVote:
        system = f"""You ARE {archetype['name']}, {archetype['title']} at {archetype['firm']}.
Role: {archetype['persona']}
Investment lens: {archetype['bias']}
Typical check size: {archetype['check_size']}
Style: {archetype['style']}

You are an independent voting member of the Kulima Twin Syndicate Investment Committee.
Evaluate this African / Africa-linked venture deal strictly through YOUR mandate.
Do not soften your persona. Be specific and opinionated.

Return ONLY valid JSON with these exact keys:
{{
  "decision": "Invest" | "Observe" | "Pass",
  "confidence_score": <number 0-100>,
  "key_reasoning": "<2-4 sentences in first person explaining your vote>",
  "major_concern": "<single sharpest risk or blocker from your seat>"
}}
"""
        try:
            data = self.llm.complete_json(
                system=system,
                user=(
                    f"DEAL UNDER REVIEW\n"
                    f"Founder: {founder}\n"
                    f"Startup: {startup}\n\n"
                    f"Intelligence Dossier:\n{dossier}\n\n"
                    f"Open-Source Evidence:\n"
                    f"{ResearchEngine.evidence_corpus(sources, 5)}"
                ),
                temperature=0.55,
            )
            decision = _parse_syndicate_decision(
                str(data.get("decision") or data.get("vote") or "Observe")
            )
            confidence = _clamp(
                float(
                    data.get("confidence_score")
                    if data.get("confidence_score") is not None
                    else data.get("confidence", 55)
                ),
                0,
                100,
            )
            # Normalize if model returned 0-1
            if confidence <= 1.0 and "confidence_score" not in data:
                confidence = confidence * 100

            reasoning = str(
                data.get("key_reasoning")
                or data.get("thesis")
                or data.get("reasoning")
                or ""
            ).strip()
            concern = str(
                data.get("major_concern")
                or (
                    (data.get("concerns") or ["Insufficient diligence signal"])[0]
                    if isinstance(data.get("concerns"), list)
                    else data.get("concerns")
                )
                or "Insufficient diligence signal"
            ).strip()

            return InvestorVote(
                archetype_id=archetype["id"],
                investor_name=archetype["name"],
                firm=archetype["firm"],
                persona=archetype["persona"],
                title=archetype["title"],
                vote=decision,
                decision=decision,
                confidence_score=confidence,
                conviction=confidence / 100.0,
                score=confidence,
                key_reasoning=reasoning,
                major_concern=concern,
                thesis=reasoning,
                concerns=[concern] if concern else [],
                conditions=[],
            )
        except Exception as exc:
            return InvestorVote(
                archetype_id=archetype["id"],
                investor_name=archetype["name"],
                firm=archetype["firm"],
                persona=archetype["persona"],
                title=archetype["title"],
                vote=Recommendation.OBSERVE,
                decision=Recommendation.OBSERVE,
                confidence_score=40.0,
                conviction=0.4,
                score=40.0,
                key_reasoning=f"Abstaining pending model recovery: {exc}",
                major_concern="Insufficient signal to underwrite",
                thesis=f"Abstaining pending model recovery: {exc}",
                concerns=["Insufficient signal to underwrite"],
                conditions=[],
            )

    def _debate(
        self,
        founder: str,
        startup: str,
        votes: list[InvestorVote],
        dossier: str,
    ) -> dict:
        ballots = "\n\n".join(
            f"{v.investor_name} ({v.persona}) — {v.decision.value} "
            f"@ confidence {v.confidence_score:.0f}/100\n"
            f"Reasoning: {v.key_reasoning}\n"
            f"Major concern: {v.major_concern}"
            for v in votes
        )
        try:
            return self.llm.complete_json(
                system=(
                    "You are the managing partner moderating the Twin Syndicate "
                    "Investment Committee. Synthesize the five independent ballots "
                    "into a crisp IC outcome. Return JSON: "
                    "transcript (professional IC dialogue, 4-8 exchanges), "
                    "consensus_thesis, blocking_concerns: [string]"
                ),
                user=(
                    f"Deal: {founder} / {startup}\n\nBallots:\n{ballots}\n\n"
                    f"Dossier excerpt:\n{dossier[:2500]}"
                ),
                temperature=0.55,
            )
        except Exception:
            return {
                "transcript": "Syndicate debate unavailable — majority ballot stands.",
                "consensus_thesis": "Proceed per majority with heightened monitoring.",
                "blocking_concerns": [],
            }

    @staticmethod
    def _consensus_score(votes: list[InvestorVote]) -> float:
        """Confidence-weighted mean of Invest=100 / Observe=50 / Pass=0."""
        if not votes:
            return 50.0
        num = sum(
            _VOTE_POINTS.get(v.decision, 50.0) * max(v.confidence_score, 1.0)
            for v in votes
        )
        den = sum(max(v.confidence_score, 1.0) for v in votes)
        return _clamp(num / den if den else 50.0, 0, 100)

    @staticmethod
    def _final_recommendation(votes: list[InvestorVote]) -> Recommendation:
        weights = {
            Recommendation.INVEST: 0.0,
            Recommendation.OBSERVE: 0.0,
            Recommendation.PASS: 0.0,
        }
        for v in votes:
            if v.decision in weights:
                weights[v.decision] += max(v.confidence_score, 1.0)
        return max(weights, key=weights.get)

    @staticmethod
    def _dissent_score(votes: list[InvestorVote]) -> float:
        """0 = full agreement, 100 = maximum disagreement."""
        if not votes:
            return 0.0
        unique = {v.decision for v in votes}
        label_component = ((len(unique) - 1) / 2.0) * 55.0  # 0, 27.5, or 55
        confidences = [v.confidence_score for v in votes]
        spread = max(confidences) - min(confidences)
        points = [_VOTE_POINTS.get(v.decision, 50.0) for v in votes]
        point_spread = max(points) - min(points)
        score = label_component + (spread / 100.0) * 20.0 + (point_spread / 100.0) * 25.0
        return _clamp(score, 0, 100)


def _parse_syndicate_decision(raw: str) -> Recommendation:
    normalized = raw.strip().lower().replace("_", " ").replace("-", " ")
    if "invest" in normalized and "co" not in normalized:
        return Recommendation.INVEST
    if "pass" in normalized:
        return Recommendation.PASS
    if "observe" in normalized or "watch" in normalized:
        return Recommendation.OBSERVE
    # Map legacy labels into the three-way ballot
    if "co invest" in normalized or "coinvest" in normalized:
        return Recommendation.INVEST
    return Recommendation.OBSERVE


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
