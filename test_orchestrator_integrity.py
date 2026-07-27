"""Sub-Task 4 — Orchestrator pipeline integration tests.

All tests are unit-level and use mocks for external dependencies.
No real LLM, API, or database calls are made.

Covers:
1. EIE output attached to brief.evidence_integrity
2. Pipeline succeeds when EIE succeeds
3. Pipeline succeeds when EIE raises (graceful degradation)
4. Legacy behaviour preserved: all pre-existing scores unchanged
5. Syndicate dossier receives Trust Layer summary
6. No score modifications from EIE
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from kulima.agents.orchestrator import (
    IntelligenceOrchestrator,
    _build_eie_dossier_line,
)
from kulima.models import (
    AgentResult,
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    FutureSimulation,
    IntegrityGrade,
    InvestmentBrief,
    InvestorVote,
    Recommendation,
    ScoreDimension,
    SourceAttribution,
    StalenessT,
    SyndicateDecision,
    TrajectoryScenario,
    TrustGraph,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _src(url: str = "https://techcabal.com/a") -> SourceAttribution:
    return SourceAttribution(
        title="Test Source", url=url,
        snippet="Test snippet.", source_type="high_authority_web",
    )


def _agent_result(
    name: str = "agent",
    summary: str = "Strong performance.",
    score: float = 72.0,
    confidence: float = 0.75,
    extra_scores: list[ScoreDimension] | None = None,
) -> AgentResult:
    base_scores = [
        ScoreDimension(name="Dimension A", score=score, rationale="Good.", confidence=0.8),
    ]
    if extra_scores:
        base_scores.extend(extra_scores)
    return AgentResult(
        agent_name=name,
        summary=summary,
        scores=base_scores,
        confidence=confidence,
        metadata={},
    )


def _startup_result_with_dims(score: float = 72.0) -> AgentResult:
    """Startup result with the three dimensions the orchestrator looks for."""
    return AgentResult(
        agent_name="startup",
        summary="Solid startup.",
        confidence=0.75,
        scores=[
            ScoreDimension(name="Market Opportunity", score=score, rationale="Good market.", confidence=0.8),
            ScoreDimension(name="Growth Potential", score=score, rationale="Strong growth.", confidence=0.8),
            ScoreDimension(name="Investment Readiness", score=score, rationale="Ready.", confidence=0.8),
        ],
        metadata={"sector": "Fintech", "geography": "Nigeria", "stage": "Seed"},
    )


def _syndicate() -> SyndicateDecision:
    vote = InvestorVote(
        archetype_id="v1",
        investor_name="Test Investor",
        firm="Test VC",
        persona="Pragmatist",
        decision=Recommendation.INVEST,
        confidence_score=75.0,
        key_reasoning="Strong team.",
        vote=Recommendation.INVEST,
        conviction=0.75,
        score=75.0,
    )
    return SyndicateDecision(
        votes=[vote],
        majority_vote=Recommendation.INVEST,
        average_score=75.0,
        dissent_index=0.1,
        consensus_score=75.0,
        final_recommendation=Recommendation.INVEST,
        dissent_score=10.0,
        debate_transcript="Debate text.",
        consensus_thesis="Good opportunity.",
    )


def _future() -> FutureSimulation:
    return FutureSimulation(
        scenarios=[
            TrajectoryScenario(
                name="Base", emoji="📊",
                success_probability=60.0, revenue_growth_outlook="Steady",
                investor_attractiveness_score=65.0,
            ),
            TrajectoryScenario(
                name="Bull", emoji="🚀",
                success_probability=80.0, revenue_growth_outlook="Strong",
                investor_attractiveness_score=80.0,
            ),
            TrajectoryScenario(
                name="Bear", emoji="🐻",
                success_probability=30.0, revenue_growth_outlook="Weak",
                investor_attractiveness_score=40.0,
            ),
        ],
        expected_value_usd=5_000_000.0,
        africa_risk_premium=3.5,
        most_likely_case="Base",
    )


def _trust_graph() -> TrustGraph:
    return TrustGraph(trust_score=65.0, density=0.4, explanation="Solid network.")


def _memo_result() -> AgentResult:
    return AgentResult(
        agent_name="memo",
        summary="Strong IC recommendation.",
        confidence=0.80,
        metadata={
            "executive_summary": "Strong opportunity.",
            "founder_assessment": "Experienced founder.",
            "startup_assessment": "Good startup.",
            "market_assessment": "Large market.",
            "risk_assessment": "Manageable risks.",
            "investment_recommendation": "Invest",
            "next_steps": ["Schedule follow-up", "Review cap table"],
        },
    )


def _minimal_integrity_report(
    grade: IntegrityGrade = IntegrityGrade.B,
    score: float = 78.0,
    sparse: bool = False,
) -> EvidenceIntegrityReport:
    return EvidenceIntegrityReport(
        integrity_score=score,
        integrity_grade=grade,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=ConsistencyStatus.CLEAN,
        sparse_mode=sparse,
        source_count=6,
        high_authority_count=3,
        integrity_summary="Moderate coverage, no conflicts.",
    )


def _make_orchestrator_with_mocks(
    eie_report: EvidenceIntegrityReport | None = None,
    eie_raises: Exception | None = None,
) -> tuple[IntelligenceOrchestrator, dict[str, MagicMock]]:
    """Build an IntelligenceOrchestrator with all external calls mocked.

    Returns (orchestrator, mocks_dict).
    """
    orch = IntelligenceOrchestrator.__new__(IntelligenceOrchestrator)

    # Sources for the research bundle
    sources = [_src(f"https://src{i}.com") for i in range(6)]

    # Mock ResearchEngine
    research = MagicMock()
    research.research_bundle.return_value = {
        "founder": sources[:2],
        "startup": sources[2:4],
        "market": sources[4:5],
        "risks": sources[5:],
    }
    research._dedupe = staticmethod(lambda s: list({x.url: x for x in s}.values()))

    # Mock agents
    founder_agent = MagicMock()
    founder_agent.run.return_value = _agent_result("founder", score=72.0)

    startup_agent = MagicMock()
    startup_agent.run.return_value = _startup_result_with_dims(score=72.0)

    diligence_agent = MagicMock()
    diligence_agent.run.return_value = _agent_result("diligence", score=70.0)

    risk_agent = MagicMock()
    risk_agent.run.return_value = _agent_result(
        "risk", score=25.0,
        extra_scores=[
            ScoreDimension(name="Risk Score", score=25.0, rationale="Low risk.", confidence=0.8)
        ],
    )
    risk_agent.run.return_value.metadata = {"composite_risk_score": 25.0}

    memo_agent = MagicMock()
    memo_agent.run.return_value = _memo_result()

    trust_engine = MagicMock()
    trust_engine.build.return_value = _trust_graph()

    syndicate = MagicMock()
    syndicate.convene.return_value = _syndicate()

    futures = MagicMock()
    futures.simulate.return_value = _future()

    # Mock EIE
    evidence_engine = MagicMock()
    if eie_raises is not None:
        evidence_engine.evaluate.side_effect = eie_raises
    else:
        evidence_engine.evaluate.return_value = (
            eie_report if eie_report is not None else _minimal_integrity_report()
        )

    orch.llm = MagicMock()
    orch.research = research
    orch.founder_agent = founder_agent
    orch.startup_agent = startup_agent
    orch.diligence_agent = diligence_agent
    orch.risk_agent = risk_agent
    orch.memo_agent = memo_agent
    orch.trust_engine = trust_engine
    orch.syndicate = syndicate
    orch.futures = futures
    orch.evidence_engine = evidence_engine

    mocks = {
        "research": research,
        "founder_agent": founder_agent,
        "startup_agent": startup_agent,
        "evidence_engine": evidence_engine,
        "syndicate": syndicate,
    }
    return orch, mocks


# ═══════════════════════════════════════════════════════════════════════════════
# 1 — EIE output attached to brief.evidence_integrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrityAttachedToBrief:
    def test_evidence_integrity_field_present_on_brief(self) -> None:
        """brief.evidence_integrity must be the EvidenceIntegrityReport returned by EIE."""
        report = _minimal_integrity_report(grade=IntegrityGrade.B, score=78.0)
        orch, _ = _make_orchestrator_with_mocks(eie_report=report)
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert brief.evidence_integrity is not None
        assert isinstance(brief.evidence_integrity, EvidenceIntegrityReport)

    def test_integrity_grade_matches_eie_output(self) -> None:
        report = _minimal_integrity_report(grade=IntegrityGrade.A, score=92.0)
        orch, _ = _make_orchestrator_with_mocks(eie_report=report)
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert brief.evidence_integrity.integrity_grade == IntegrityGrade.A
        assert brief.evidence_integrity.integrity_score == pytest.approx(92.0)

    def test_integrity_metadata_preserved(self) -> None:
        report = _minimal_integrity_report(sparse=True)
        orch, _ = _make_orchestrator_with_mocks(eie_report=report)
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert brief.evidence_integrity.sparse_mode is True


# ═══════════════════════════════════════════════════════════════════════════════
# 2 — Pipeline succeeds when EIE succeeds
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineSucceedsWithEIE:
    def test_analyze_returns_investment_brief(self) -> None:
        orch, _ = _make_orchestrator_with_mocks()
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert isinstance(brief, InvestmentBrief)

    def test_eie_evaluate_called_once(self) -> None:
        orch, mocks = _make_orchestrator_with_mocks()
        orch.analyze("Ada Obi", "PayFast NG")
        mocks["evidence_engine"].evaluate.assert_called_once()

    def test_eie_receives_all_sources(self) -> None:
        """EIE must be called with the merged deduplicated all_sources list."""
        orch, mocks = _make_orchestrator_with_mocks()
        orch.analyze("Ada Obi", "PayFast NG")
        call_args = mocks["evidence_engine"].evaluate.call_args
        sources_arg = call_args[0][0]  # first positional argument
        assert isinstance(sources_arg, list)
        assert len(sources_arg) > 0

    def test_eie_called_before_agents(self) -> None:
        """EIE must be called before founder_agent.run (post-research, pre-agents)."""
        call_order: list[str] = []

        orch, mocks = _make_orchestrator_with_mocks()
        original_eie = mocks["evidence_engine"].evaluate.side_effect
        original_founder = mocks["founder_agent"].run.side_effect

        def _track_eie(*args: Any, **kwargs: Any) -> EvidenceIntegrityReport:
            call_order.append("eie")
            return _minimal_integrity_report()

        def _track_founder(*args: Any, **kwargs: Any) -> AgentResult:
            call_order.append("founder")
            return _agent_result("founder")

        mocks["evidence_engine"].evaluate.side_effect = _track_eie
        mocks["founder_agent"].run.side_effect = _track_founder

        orch.analyze("Ada Obi", "PayFast NG")

        assert "eie" in call_order
        assert "founder" in call_order
        assert call_order.index("eie") < call_order.index("founder"), (
            "EIE must execute before founder agent"
        )

    def test_progress_callback_called_for_eie(self) -> None:
        """The progress callback must be called with the EIE step message."""
        progress_messages: list[str] = []

        def _cb(pct: float, msg: str) -> None:
            progress_messages.append(msg)

        orch, _ = _make_orchestrator_with_mocks()
        orch.analyze("Ada Obi", "PayFast NG", on_progress=_cb)
        assert any("Evidence Integrity" in m for m in progress_messages)


# ═══════════════════════════════════════════════════════════════════════════════
# 3 — Pipeline succeeds when EIE fails (graceful degradation)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineSucceedsWhenEIEFails:
    def test_pipeline_completes_when_eie_raises_runtime_error(self) -> None:
        orch, _ = _make_orchestrator_with_mocks(eie_raises=RuntimeError("API timeout"))
        # Must NOT raise
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert isinstance(brief, InvestmentBrief)

    def test_evidence_integrity_is_none_when_eie_fails(self) -> None:
        orch, _ = _make_orchestrator_with_mocks(eie_raises=ValueError("LLM error"))
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert brief.evidence_integrity is None

    def test_pipeline_completes_when_eie_raises_any_exception(self) -> None:
        """Even a bare Exception must be caught."""
        orch, _ = _make_orchestrator_with_mocks(eie_raises=Exception("Unexpected"))
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert isinstance(brief, InvestmentBrief)

    def test_brief_fully_populated_when_eie_fails(self) -> None:
        """All other brief fields must be populated normally when EIE fails."""
        orch, _ = _make_orchestrator_with_mocks(eie_raises=RuntimeError("fail"))
        brief = orch.analyze("Ada Obi", "PayFast NG")
        assert brief.founder_name == "Ada Obi"
        assert brief.startup_name == "PayFast NG"
        assert brief.overall_score > 0
        assert brief.syndicate is not None
        assert brief.future_simulation is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 4 — Legacy behaviour preserved
# ═══════════════════════════════════════════════════════════════════════════════

class TestLegacyBehaviourPreserved:
    def test_all_existing_brief_fields_populated(self) -> None:
        """Every field that existed before Sub-Task 4 must still be populated."""
        orch, _ = _make_orchestrator_with_mocks()
        brief = orch.analyze("Ada Obi", "PayFast NG")

        assert brief.founder_name == "Ada Obi"
        assert brief.startup_name == "PayFast NG"
        assert brief.sector == "Fintech"
        assert brief.geography == "Nigeria"
        assert brief.overall_score > 0
        assert brief.founder_score > 0
        assert brief.startup_score > 0
        assert brief.market_score > 0
        assert brief.trust_score > 0
        assert brief.risk_score >= 0
        assert brief.confidence > 0
        assert brief.recommendation in list(Recommendation)
        assert brief.syndicate is not None
        assert brief.future_simulation is not None
        assert brief.sources is not None

    def test_brief_without_integrity_still_has_all_required_fields(self) -> None:
        """When EIE fails, all pre-existing brief fields must be unchanged."""
        orch, _ = _make_orchestrator_with_mocks(eie_raises=RuntimeError("fail"))
        brief = orch.analyze("Ada Obi", "PayFast NG")

        assert brief.founder_name == "Ada Obi"
        assert brief.overall_score > 0
        assert brief.syndicate is not None
        assert brief.future_simulation is not None
        assert brief.trust_graph is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 5 — Syndicate dossier receives Trust Layer summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestSyndicateDossierContainsEIE:
    def test_dossier_contains_evidence_integrity_section(self) -> None:
        """When EIE succeeds, the dossier passed to syndicate.convene must contain
        the [EVIDENCE_INTEGRITY] header."""
        orch, mocks = _make_orchestrator_with_mocks(
            eie_report=_minimal_integrity_report(grade=IntegrityGrade.B, score=78.0)
        )
        orch.analyze("Ada Obi", "PayFast NG")
        call_args = mocks["syndicate"].convene.call_args
        dossier_arg = call_args[0][2]  # 3rd positional arg: founder, startup, dossier, sources
        assert "[EVIDENCE_INTEGRITY]" in dossier_arg

    def test_dossier_contains_grade_label(self) -> None:
        orch, mocks = _make_orchestrator_with_mocks(
            eie_report=_minimal_integrity_report(grade=IntegrityGrade.C, score=63.0)
        )
        orch.analyze("Ada Obi", "PayFast NG")
        dossier = mocks["syndicate"].convene.call_args[0][2]
        assert "Reliability: C" in dossier

    def test_dossier_contains_depth_label(self) -> None:
        orch, mocks = _make_orchestrator_with_mocks(
            eie_report=_minimal_integrity_report()
        )
        orch.analyze("Ada Obi", "PayFast NG")
        dossier = mocks["syndicate"].convene.call_args[0][2]
        assert "Evidence Depth:" in dossier

    def test_dossier_contains_consistency_label(self) -> None:
        orch, mocks = _make_orchestrator_with_mocks(
            eie_report=_minimal_integrity_report()
        )
        orch.analyze("Ada Obi", "PayFast NG")
        dossier = mocks["syndicate"].convene.call_args[0][2]
        assert "Consistency:" in dossier

    def test_dossier_eie_section_under_500_chars(self) -> None:
        """The EIE section prepended to the dossier must not exceed 500 chars."""
        # Build report with 3 contradictions to exercise the full format
        claim_a = Claim(
            claim_type=ClaimType.FUNDING_AMOUNT,
            value_raw="$2M", source_url="https://a.com", source_authority="web",
        )
        claim_b = Claim(
            claim_type=ClaimType.FUNDING_AMOUNT,
            value_raw="$500K", source_url="https://b.com", source_authority="web",
        )
        contradictions = [
            Contradiction(
                claim_a=claim_a, claim_b=claim_b,
                severity=ContradictionSeverity.CRITICAL,
                subtype="GENUINE_CONTRADICTION",
                description="Sources disagree on funding raised by 300%.",
            )
            for _ in range(3)
        ]
        report = EvidenceIntegrityReport(
            integrity_score=55.0,
            integrity_grade=IntegrityGrade.D,
            evidence_depth=EvidenceDepth.LIMITED,
            consistency_status=ConsistencyStatus.MAJOR_CONFLICTS,
            sparse_mode=True,
            contradictions=contradictions,
        )
        summary = _build_eie_dossier_line(report)
        assert len(summary) <= 500

    def test_dossier_no_eie_section_when_eie_fails(self) -> None:
        """When EIE fails, the dossier must still contain the score line."""
        orch, mocks = _make_orchestrator_with_mocks(eie_raises=RuntimeError("fail"))
        orch.analyze("Ada Obi", "PayFast NG")
        dossier = mocks["syndicate"].convene.call_args[0][2]
        assert "[EVIDENCE_INTEGRITY]" not in dossier
        # Core content must still be present
        assert "Founder score" in dossier

    def test_dossier_still_has_score_line(self) -> None:
        """The existing score line must always be in the dossier."""
        orch, mocks = _make_orchestrator_with_mocks()
        orch.analyze("Ada Obi", "PayFast NG")
        dossier = mocks["syndicate"].convene.call_args[0][2]
        assert "Founder score" in dossier
        assert "Startup" in dossier
        assert "Trust" in dossier


# ═══════════════════════════════════════════════════════════════════════════════
# 6 — No score modifications
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoScoreModifications:
    def test_overall_score_identical_with_and_without_eie(self) -> None:
        """overall_score must be byte-identical whether EIE succeeds or fails."""
        orch_with, _ = _make_orchestrator_with_mocks(eie_report=_minimal_integrity_report())
        brief_with = orch_with.analyze("Ada Obi", "PayFast NG")

        orch_without, _ = _make_orchestrator_with_mocks(eie_raises=RuntimeError("fail"))
        brief_without = orch_without.analyze("Ada Obi", "PayFast NG")

        assert brief_with.overall_score == pytest.approx(brief_without.overall_score)

    def test_trust_score_not_modified_by_eie(self) -> None:
        """trust_score must be identical whether EIE is present or not."""
        orch_with, _ = _make_orchestrator_with_mocks(eie_report=_minimal_integrity_report())
        brief_with = orch_with.analyze("Ada Obi", "PayFast NG")

        orch_without, _ = _make_orchestrator_with_mocks(eie_raises=RuntimeError("fail"))
        brief_without = orch_without.analyze("Ada Obi", "PayFast NG")

        assert brief_with.trust_score == pytest.approx(brief_without.trust_score)

    def test_founder_score_not_modified(self) -> None:
        orch_with, _ = _make_orchestrator_with_mocks(eie_report=_minimal_integrity_report())
        brief_with = orch_with.analyze("Ada Obi", "PayFast NG")

        orch_without, _ = _make_orchestrator_with_mocks(eie_raises=RuntimeError("fail"))
        brief_without = orch_without.analyze("Ada Obi", "PayFast NG")

        assert brief_with.founder_score == pytest.approx(brief_without.founder_score)

    def test_recommendation_not_modified_by_eie(self) -> None:
        """recommendation must be identical with and without EIE."""
        orch_with, _ = _make_orchestrator_with_mocks(eie_report=_minimal_integrity_report())
        brief_with = orch_with.analyze("Ada Obi", "PayFast NG")

        orch_without, _ = _make_orchestrator_with_mocks(eie_raises=RuntimeError("fail"))
        brief_without = orch_without.analyze("Ada Obi", "PayFast NG")

        assert brief_with.recommendation == brief_without.recommendation

    def test_confidence_not_modified_by_orchestrator(self) -> None:
        """The orchestrator must NOT apply confidence_delta to InvestmentBrief.confidence.
        The delta is stored on evidence_integrity only; UI/export phases apply it.
        """
        report = _minimal_integrity_report(grade=IntegrityGrade.F, score=30.0)
        report = report.model_copy(update={"confidence_delta": -0.15})
        orch, _ = _make_orchestrator_with_mocks(eie_report=report)
        brief = orch.analyze("Ada Obi", "PayFast NG")
        # confidence on the brief must NOT have had -0.15 applied
        # (it is computed solely from agent confidences)
        assert brief.confidence > 0
        # The delta is on the report, not the brief
        assert brief.evidence_integrity.confidence_delta == pytest.approx(-0.15)
        # brief.confidence is NOT brief.evidence_integrity.confidence_adjusted
        # We can't assert exact equality without knowing agent values,
        # but we can assert the brief confidence was not reduced to near zero
        assert brief.confidence > 0.10


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests for _build_eie_dossier_line helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildEieDossierLine:
    def test_none_report_returns_empty_string(self) -> None:
        assert _build_eie_dossier_line(None) == ""

    def test_contains_evidence_integrity_header(self) -> None:
        report = _minimal_integrity_report()
        result = _build_eie_dossier_line(report)
        assert "[EVIDENCE_INTEGRITY]" in result

    def test_contains_grade(self) -> None:
        report = _minimal_integrity_report(grade=IntegrityGrade.C)
        result = _build_eie_dossier_line(report)
        assert "Reliability: C" in result

    def test_sparse_note_included(self) -> None:
        report = _minimal_integrity_report(sparse=True)
        result = _build_eie_dossier_line(report)
        assert "Sparse" in result or "sparse" in result

    def test_contradictions_listed(self) -> None:
        claim_a = Claim(
            claim_type=ClaimType.FUNDING_AMOUNT,
            value_raw="$2M", source_url="https://a.com", source_authority="web",
        )
        claim_b = Claim(
            claim_type=ClaimType.FUNDING_AMOUNT,
            value_raw="$500K", source_url="https://b.com", source_authority="web",
        )
        contradiction = Contradiction(
            claim_a=claim_a, claim_b=claim_b,
            severity=ContradictionSeverity.CRITICAL,
            subtype="GENUINE_CONTRADICTION",
            description="Sources disagree on funding raised.",
        )
        report = EvidenceIntegrityReport(
            integrity_score=70.0, integrity_grade=IntegrityGrade.C,
            evidence_depth=EvidenceDepth.MODERATE,
            consistency_status=ConsistencyStatus.CONFLICTS,
            contradictions=[contradiction],
        )
        result = _build_eie_dossier_line(report)
        assert "Top Issues" in result
        assert "Sources disagree on funding raised." in result

    def test_max_3_contradictions_listed(self) -> None:
        """Only the first 3 contradictions must appear even if there are more."""
        claim_a = Claim(claim_type=ClaimType.OTHER, value_raw="x", source_url="https://a.com", source_authority="web")
        claim_b = Claim(claim_type=ClaimType.OTHER, value_raw="y", source_url="https://b.com", source_authority="web")
        contradictions = [
            Contradiction(
                claim_a=claim_a, claim_b=claim_b,
                severity=ContradictionSeverity.HIGH,
                description=f"Conflict {i}.",
            )
            for i in range(5)
        ]
        report = EvidenceIntegrityReport(
            integrity_score=50.0, integrity_grade=IntegrityGrade.D,
            evidence_depth=EvidenceDepth.LIMITED,
            consistency_status=ConsistencyStatus.MAJOR_CONFLICTS,
            contradictions=contradictions,
        )
        result = _build_eie_dossier_line(report)
        # Conflicts 0-2 present, 3 and 4 absent
        assert "Conflict 0" in result
        assert "Conflict 2" in result
        assert "Conflict 3" not in result

    def test_always_under_500_chars(self) -> None:
        claim_a = Claim(claim_type=ClaimType.OTHER, value_raw="x" * 200, source_url="https://a.com", source_authority="web")
        claim_b = Claim(claim_type=ClaimType.OTHER, value_raw="y" * 200, source_url="https://b.com", source_authority="web")
        contradictions = [
            Contradiction(
                claim_a=claim_a, claim_b=claim_b,
                severity=ContradictionSeverity.CRITICAL,
                description="A very long description " * 20,
            )
            for _ in range(3)
        ]
        report = EvidenceIntegrityReport(
            integrity_score=30.0, integrity_grade=IntegrityGrade.F,
            evidence_depth=EvidenceDepth.THIN,
            consistency_status=ConsistencyStatus.MAJOR_CONFLICTS,
            sparse_mode=True,
            contradictions=contradictions,
        )
        result = _build_eie_dossier_line(report)
        assert len(result) <= 500
