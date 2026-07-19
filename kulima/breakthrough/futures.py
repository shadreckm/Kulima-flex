"""
Continental Futures Engine
==========================
Predicts startup outcomes under African market conditions.
Produces Bull / Base / Bear scenarios via GPT-4.1-mini.
"""

from __future__ import annotations

from kulima.config import FUTURES_MODEL
from kulima.llm import LLMClient
from kulima.models import FutureSimulation, TrajectoryScenario
from kulima.scoring import clamp

SCENARIO_SPECS = [
    {"key": "bull", "name": "Bull Case", "emoji": "🚀"},
    {"key": "base", "name": "Base Case", "emoji": "📈"},
    {"key": "bear", "name": "Bear Case", "emoji": "⚠️"},
]


class ContinentalFuturesEngine:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient(model=FUTURES_MODEL)

    def simulate(
        self,
        founder: str,
        startup: str,
        overall_score: float,
        market_score: float,
        risk_score: float,
        sector: str = "",
        geography: str = "",
        dossier: str = "",
    ) -> FutureSimulation:
        system = """You are an MIT-trained AI researcher and African macro strategist.
Simulate 36-month startup outcomes under African market conditions:
FX volatility, power/logistics constraints, regulatory unpredictability,
mobile-money rails, diaspora networks, and fragmented distribution.

Produce EXACTLY three scenarios: Bull Case, Base Case, Bear Case.

Return ONLY valid JSON:
{
  "scenarios": [
    {
      "name": "Bull Case",
      "success_probability": <0-100>,
      "revenue_growth_outlook": "<concise growth outlook for Africa markets>",
      "investor_attractiveness_score": <0-100>,
      "major_risks": ["<risk>", "<risk>", "<risk>"],
      "key_opportunities": ["<opportunity>", "<opportunity>", "<opportunity>"],
      "narrative": "<2-3 sentences>",
      "revenue_36m_usd": <number>,
      "valuation_36m_usd": <number>
    },
    { "name": "Base Case", ... },
    { "name": "Bear Case", ... }
  ],
  "africa_conditions_summary": "<how African market physics shape all three cases>",
  "most_likely_case": "Bull Case" | "Base Case" | "Bear Case",
  "africa_risk_premium": <0-40>,
  "simulation_notes": "<one sentence method note>"
}

Rules:
- success_probability is likelihood this scenario materializes (three should roughly sum near 100).
- investor_attractiveness_score reflects how attractive the deal looks TO INVESTORS in that world.
- Be specific to African market realities. No generic Silicon Valley fluff.
"""
        try:
            data = self.llm.complete_json(
                system=system,
                user=(
                    f"FOUNDER: {founder}\n"
                    f"STARTUP: {startup}\n"
                    f"SECTOR: {sector or 'n/a'}\n"
                    f"GEOGRAPHY: {geography or 'Africa'}\n"
                    f"OVERALL SCORE: {overall_score:.0f}/100\n"
                    f"MARKET SCORE: {market_score:.0f}/100\n"
                    f"RISK SCORE: {risk_score:.0f}/100\n\n"
                    f"INTELLIGENCE DOSSIER:\n{dossier[:3200]}"
                ),
                temperature=0.45,
            )
            scenarios = self._parse_scenarios(data.get("scenarios", []))
            if len(scenarios) < 3:
                scenarios = self._heuristic(overall_score, market_score, risk_score)
            else:
                scenarios = self._normalize_trio(scenarios)

            expected = sum(
                (s.success_probability / 100.0) * s.valuation_36m_usd for s in scenarios
            )
            bull = next((s for s in scenarios if "Bull" in s.name), scenarios[0])
            bear = next((s for s in scenarios if "Bear" in s.name), scenarios[-1])
            base = next((s for s in scenarios if "Base" in s.name), scenarios[1])

            return FutureSimulation(
                scenarios=scenarios,
                expected_value_usd=float(data.get("expected_value_usd") or expected),
                downside_case=bear.narrative or bear.revenue_growth_outlook,
                upside_case=bull.narrative or bull.revenue_growth_outlook,
                africa_risk_premium=float(data.get("africa_risk_premium", 12)),
                simulation_notes=str(data.get("simulation_notes", "")),
                most_likely_case=str(data.get("most_likely_case") or base.name),
                africa_conditions_summary=str(
                    data.get("africa_conditions_summary", "")
                ),
            )
        except Exception as exc:
            scenarios = self._heuristic(overall_score, market_score, risk_score)
            return FutureSimulation(
                scenarios=scenarios,
                expected_value_usd=sum(
                    (s.success_probability / 100.0) * s.valuation_36m_usd
                    for s in scenarios
                ),
                downside_case=scenarios[2].narrative,
                upside_case=scenarios[0].narrative,
                africa_risk_premium=clamp(8 + risk_score / 5, 5, 35),
                simulation_notes=f"Heuristic simulation (LLM degraded): {exc}",
                most_likely_case="Base Case",
                africa_conditions_summary=(
                    "FX, regulatory, and infrastructure constraints dominate the path set."
                ),
            )

    def _parse_scenarios(self, raw: list) -> list[TrajectoryScenario]:
        out: list[TrajectoryScenario] = []
        for item in raw:
            name = str(item.get("name", "Scenario"))
            emoji = _emoji_for(name)
            success = float(
                item.get("success_probability")
                if item.get("success_probability") is not None
                else (item.get("probability", 0.33) * 100
                      if float(item.get("probability", 1)) <= 1
                      else item.get("probability", 50))
            )
            success = clamp(success, 0, 100)
            attractiveness = clamp(
                float(item.get("investor_attractiveness_score", 50)), 0, 100
            )
            risks = [str(r) for r in item.get("major_risks", [])][:5]
            opps = [str(o) for o in item.get("key_opportunities", [])][:5]
            if not risks and item.get("key_drivers"):
                risks = [str(d) for d in item.get("key_drivers", [])][:3]
            narrative = str(item.get("narrative", ""))
            outlook = str(
                item.get("revenue_growth_outlook")
                or item.get("growth_outlook")
                or narrative
            )
            revenue = float(item.get("revenue_36m_usd", 0))
            valuation = float(item.get("valuation_36m_usd", 0))
            out.append(
                TrajectoryScenario(
                    name=_canonical_name(name),
                    emoji=emoji,
                    success_probability=success,
                    revenue_growth_outlook=outlook,
                    investor_attractiveness_score=attractiveness,
                    major_risks=risks or ["Africa macro / FX pressure"],
                    key_opportunities=opps or ["Local distribution advantage"],
                    probability=success / 100.0,
                    revenue_36m_usd=revenue,
                    valuation_36m_usd=valuation,
                    survival_probability=clamp(success / 100.0 + 0.15, 0, 1),
                    narrative=narrative or outlook,
                    key_drivers=opps or risks,
                )
            )
        return out

    def _normalize_trio(
        self, scenarios: list[TrajectoryScenario]
    ) -> list[TrajectoryScenario]:
        """Ensure Bull / Base / Bear ordering with correct labels."""
        ordered: list[TrajectoryScenario] = []
        for spec in SCENARIO_SPECS:
            match = next(
                (s for s in scenarios if spec["key"] in s.name.lower()),
                None,
            )
            if match is None and scenarios:
                match = scenarios[len(ordered) % len(scenarios)]
            if match is None:
                continue
            match.name = spec["name"]
            match.emoji = spec["emoji"]
            ordered.append(match)
        return ordered[:3] if ordered else scenarios[:3]

    def _heuristic(
        self,
        overall: float,
        market: float,
        risk: float,
    ) -> list[TrajectoryScenario]:
        quality = (overall + market) / 200
        bear_p = clamp(25 + risk / 4, 15, 45)
        bull_p = clamp(20 + quality * 25, 15, 40)
        base_p = clamp(100 - bear_p - bull_p, 10, 60)
        base_val = 2_000_000 + overall * 80_000
        return [
            TrajectoryScenario(
                name="Bull Case",
                emoji="🚀",
                success_probability=bull_p,
                revenue_growth_outlook=(
                    "Hypergrowth across 2–3 African corridors; mobile-money rails unlock "
                    "distribution and FX-resilient unit economics compound."
                ),
                investor_attractiveness_score=clamp(70 + quality * 25, 60, 95),
                major_risks=[
                    "Execution stretch across borders",
                    "Talent density bottlenecks",
                    "Valuation expectation mismatch",
                ],
                key_opportunities=[
                    "Category leadership in core market",
                    "Diaspora + regional expansion",
                    "Strategic CVC distribution partnerships",
                ],
                probability=bull_p / 100,
                revenue_36m_usd=base_val * 0.35,
                valuation_36m_usd=base_val * 3.2,
                survival_probability=0.85,
                narrative="Continental breakout with durable product-market fit.",
                key_drivers=["Multi-country distribution", "Mobile-money rails"],
            ),
            TrajectoryScenario(
                name="Base Case",
                emoji="📈",
                success_probability=base_p,
                revenue_growth_outlook=(
                    "Steady double-digit growth in core market; capital-efficient scale; "
                    "Series A remains viable under disciplined burn."
                ),
                investor_attractiveness_score=clamp(55 + quality * 15, 45, 80),
                major_risks=[
                    "Slower enterprise sales cycles",
                    "Localized competitive pressure",
                    "Fundraising window compression",
                ],
                key_opportunities=[
                    "Deepen retention in home market",
                    "Local partnership leverage",
                    "Prove unit economics before expansion",
                ],
                probability=base_p / 100,
                revenue_36m_usd=base_val * 0.15,
                valuation_36m_usd=base_val * 1.4,
                survival_probability=0.7,
                narrative="Disciplined scale with credible path to next round.",
                key_drivers=["Retention", "Cost discipline"],
            ),
            TrajectoryScenario(
                name="Bear Case",
                emoji="⚠️",
                success_probability=bear_p,
                revenue_growth_outlook=(
                    "Flat-to-down real revenue after FX; growth stalls; bridge capital "
                    "required to survive regulatory and macro drag."
                ),
                investor_attractiveness_score=clamp(35 - risk / 5, 10, 45),
                major_risks=[
                    "FX / macro shock",
                    "Regulatory delay or compliance failure",
                    "Burn mismanagement and key-person risk",
                ],
                key_opportunities=[
                    "Pivot to cash-flow positive niche",
                    "Strategic acqui-hire / soft landing",
                    "Rebuild with tighter geography focus",
                ],
                probability=bear_p / 100,
                revenue_36m_usd=base_val * 0.04,
                valuation_36m_usd=base_val * 0.45,
                survival_probability=0.45,
                narrative="Constrained survival under African downside physics.",
                key_drivers=["FX shock", "Regulatory delay"],
            ),
        ]


def _emoji_for(name: str) -> str:
    lower = name.lower()
    if "bull" in lower:
        return "🚀"
    if "bear" in lower:
        return "⚠️"
    return "📈"


def _canonical_name(name: str) -> str:
    lower = name.lower()
    if "bull" in lower:
        return "Bull Case"
    if "bear" in lower:
        return "Bear Case"
    if "base" in lower:
        return "Base Case"
    return name
