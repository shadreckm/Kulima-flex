"""Sub-Task 6 — Ask IC Integration tests.

Tests for the [EVIDENCE_INTEGRITY] section injected into build_ask_ic_context()
and the two integrity-aware grounding rules added to answer_ask_ic_question().

Blueprint Phase 6 spec: lines 564–637 of trust-layer-implementation-blueprint.md
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kulima.ask_ic import MAX_CONTEXT_CHARS, _clip, build_ask_ic_context
from kulima.models import (
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    InvestmentBrief,
    Recommendation,
    StalenessT,
    UnsupportedClaim,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_claim(value: str = "some value", claim_type: ClaimType = ClaimType.OTHER) -> Claim:
    """Build a minimal Claim with the given raw value."""
    return Claim(
        claim_id="test-claim",
        claim_type=claim_type,
        value_raw=value,
        source_url="https://example.com",
        source_title="Test Source",
        staleness=StalenessT.FRESH,
        confidence=0.8,
    )


def _make_contradiction(
    value_a: str = "Revenue is $1M",
    value_b: str = "Revenue is $500K",
    severity: ContradictionSeverity = ContradictionSeverity.HIGH,
) -> Contradiction:
    """Build a Contradiction using real Claim objects."""
    return Contradiction(
        contradiction_id="test-contradiction",
        claim_a=_make_claim(value_a, ClaimType.REVENUE),
        claim_b=_make_claim(value_b, ClaimType.REVENUE),
        severity=severity,
        description="Revenue figures conflict across sources.",
        recommended_action="Verify with founder financials.",
    )


def _make_unsupported(description: str = "The company has 100,000 active users.") -> UnsupportedClaim:
    """Build an UnsupportedClaim using real field names."""
    return UnsupportedClaim(
        claim_type=ClaimType.CUSTOMER_COUNT,
        description=description,
        severity=ContradictionSeverity.MEDIUM,
        recommended_action="Request user metrics from founder.",
    )


def _make_integrity_report(
    *,
    grade: IntegrityGrade = IntegrityGrade.B,
    score: float = 78.0,
    depth: EvidenceDepth = EvidenceDepth.MODERATE,
    consistency: ConsistencyStatus = ConsistencyStatus.CLEAN,
    contradictions: list | None = None,
    unsupported_claims: list | None = None,
) -> EvidenceIntegrityReport:
    return EvidenceIntegrityReport(
        integrity_score=score,
        integrity_grade=grade,
        evidence_depth=depth,
        consistency_status=consistency,
        contradictions=contradictions or [],
        unsupported_claims=unsupported_claims or [],
        stale_claims=[],
        ignored_conflicts=[],
        source_count=6,
        high_authority_count=3,
        claim_count=10,
        confidence_delta=0.0,
        sparse_mode=False,
        two_axis_label="B",
    )


def _make_brief(ei=None) -> InvestmentBrief:
    from kulima.models import ConfidenceLevel

    return InvestmentBrief(
        founder_name="Amara Diallo",
        startup_name="PayZen Africa",
        sector="Fintech",
        geography="West Africa",
        stage="Series A",
        recommendation=Recommendation.INVEST,
        overall_score=80.0,
        founder_score=82.0,
        startup_score=78.0,
        market_score=76.0,
        trust_score=74.0,
        risk_score=28.0,
        growth_potential=72.0,
        investment_readiness=70.0,
        confidence=0.82,
        confidence_level=ConfidenceLevel.HIGH,
        executive_summary="Strong fintech play in underbanked West Africa.",
        founder_assessment="Experienced operator with prior exit.",
        startup_assessment="Early but growing revenue.",
        market_assessment="Large TAM with improving mobile penetration.",
        risk_assessment="FX and regulatory risk.",
        investment_recommendation="Proceed with lead investment.",
        next_steps=["Due diligence call", "Term sheet"],
        explainability=["High founder score driven by track record"],
        red_flags=[],
        sources=[],
        evidence_integrity=ei,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBuildAskIcContextWithEI:
    """[EVIDENCE_INTEGRITY] section is injected when evidence_integrity is set."""

    def test_section_header_present(self):
        ei = _make_integrity_report()
        brief = _make_brief(ei=ei)
        ctx = build_ask_ic_context(brief)
        assert "[EVIDENCE_INTEGRITY]" in ctx

    def test_section_absent_when_no_ei(self):
        brief = _make_brief(ei=None)
        ctx = build_ask_ic_context(brief)
        assert "[EVIDENCE_INTEGRITY]" not in ctx

    def test_rating_line_format(self):
        ei = _make_integrity_report(grade=IntegrityGrade.A, score=92.0)
        brief = _make_brief(ei=ei)
        ctx = build_ask_ic_context(brief)
        assert "Grade A" in ctx
        assert "92/100" in ctx

    def test_depth_and_consistency_present(self):
        ei = _make_integrity_report(
            depth=EvidenceDepth.RICH,
            consistency=ConsistencyStatus.CONFLICTS,
        )
        brief = _make_brief(ei=ei)
        ctx = build_ask_ic_context(brief)
        assert EvidenceDepth.RICH.value in ctx
        assert ConsistencyStatus.CONFLICTS.value in ctx

    def test_contradiction_entries_present(self):
        contradiction = _make_contradiction(
            value_a="Revenue is $1M",
            value_b="Revenue is $500K",
            severity=ContradictionSeverity.HIGH,
        )
        ei = _make_integrity_report(contradictions=[contradiction])
        brief = _make_brief(ei=ei)
        ctx = build_ask_ic_context(brief)
        assert "[C1]" in ctx
        assert "HIGH" in ctx

    def test_unsupported_claim_entries_present(self):
        unsupported = _make_unsupported("The company has 100,000 active users.")
        ei = _make_integrity_report(unsupported_claims=[unsupported])
        brief = _make_brief(ei=ei)
        ctx = build_ask_ic_context(brief)
        assert "[U1]" in ctx
        assert "100,000 active users" in ctx

    def test_context_stays_within_max_chars(self):
        # Build a large payload to stress the char limit
        contras = [
            _make_contradiction("A" * 400, "B" * 400, ContradictionSeverity.HIGH)
            for _ in range(5)
        ]
        unsups = [
            _make_unsupported("C" * 400)
            for _ in range(5)
        ]
        ei = _make_integrity_report(contradictions=contras, unsupported_claims=unsups)
        brief = _make_brief(ei=ei)
        ctx = build_ask_ic_context(brief)
        assert len(ctx) <= MAX_CONTEXT_CHARS


class TestAnswerAskIcQuestionWithEI:
    """Grounding rules are appended to the system prompt when evidence_integrity is set."""

    def _capture_system(self, brief) -> str:
        """Call answer_ask_ic_question and capture the system prompt used."""
        captured = {}

        def fake_complete(system, user, temperature=0.2):
            captured["system"] = system
            return "Mocked IC answer."

        with patch("kulima.ask_ic.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.side_effect = fake_complete
            from kulima.ask_ic import answer_ask_ic_question

            answer_ask_ic_question(brief, "What is the evidence quality?")

        return captured.get("system", "")

    def test_grounding_rules_present_when_ei_set(self):
        ei = _make_integrity_report(grade=IntegrityGrade.C, score=65.0)
        brief = _make_brief(ei=ei)
        system = self._capture_system(brief)
        assert "Evidence integrity grounding rules" in system

    def test_grounding_rules_absent_when_no_ei(self):
        brief = _make_brief(ei=None)
        system = self._capture_system(brief)
        assert "Evidence integrity grounding rules" not in system

    def test_grade_and_score_in_grounding_rules(self):
        ei = _make_integrity_report(grade=IntegrityGrade.B, score=78.0)
        brief = _make_brief(ei=ei)
        system = self._capture_system(brief)
        assert "Grade B" in system
        assert "78/100" in system

    def test_contradiction_citation_instruction_present(self):
        ei = _make_integrity_report()
        brief = _make_brief(ei=ei)
        system = self._capture_system(brief)
        assert "[C#]" in system

    def test_unsupported_claim_citation_instruction_present(self):
        ei = _make_integrity_report()
        brief = _make_brief(ei=ei)
        system = self._capture_system(brief)
        assert "[U#]" in system
