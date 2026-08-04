"""Phase 5E — Ask SIGNALS unit tests.

All tests target the pure context-building layer (build_ask_signals_context)
and the private helper functions.  No LLM calls are made.

Coverage
--------
1.  _clip()                  — truncation and whitespace collapse
2.  _signal_ref()            — citation label generation [SG#]
3.  _refs_str()              — evidence_refs formatting
4.  build_ask_signals_context — [CASE] section
5.  build_ask_signals_context — [SIGNALS_SUMMARY] section
6.  build_ask_signals_context — [SIGNALS] section detail
7.  build_ask_signals_context — [SG#] signal citations present
8.  build_ask_signals_context — [EVIDENCE_INTEGRITY] section
9.  build_ask_signals_context — contradiction [C#] citations
10. build_ask_signals_context — unsupported claim [U#] citations
11. build_ask_signals_context — [TRUST_GRAPH] section
12. build_ask_signals_context — [EVIDENCE_SOURCES] section [S#]
13. build_ask_signals_context — empty signals list
14. build_ask_signals_context — no EIE / no trust graph (graceful)
15. build_ask_signals_context — context bounded to MAX_CONTEXT_CHARS
16. answer_ask_signals_question — LLM called with correct args (mock)
17. answer_ask_signals_question — history truncated to 8 turns (mock)
18. answer_ask_signals_question — EI grounding appended to system (mock)
19. answer_ask_signals_question — trust graph grounding appended (mock)
20. Synthetic end-to-end: "top 3 risks" response cites [SG#] (mock)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from kulima.core.cases.models import Case, CaseSubject, CaseType
from kulima.models import (
    Claim,
    ClaimType,
    ConsistencyStatus,
    Contradiction,
    ContradictionSeverity,
    EvidenceDepth,
    EvidenceIntegrityReport,
    IntegrityGrade,
    SourceAttribution,
    StalenessT,
    TrustEdge,
    TrustGraph,
    TrustNode,
    UnsupportedClaim,
)
from kulima.signals.ask_signals import (
    MAX_CONTEXT_CHARS,
    _clip,
    _refs_str,
    _signal_ref,
    answer_ask_signals_question,
    build_ask_signals_context,
)
from kulima.signals.models import Signal, SignalCategory, SignalLevel


# ── Shared fixture builders ───────────────────────────────────────────────────

def _make_case(
    *,
    with_ei: bool = True,
    with_graph: bool = True,
    with_sources: bool = True,
) -> Case:
    subject = CaseSubject(
        id="sub-001",
        kind="program",
        name="HealthBridge Kenya",
        secondary_name="Dr. Amina Osei",
        region="East Africa",
        sector="HealthTech",
    )
    ei = _make_ei() if with_ei else None
    graph = _make_graph() if with_graph else None
    sources = _make_sources() if with_sources else []
    return Case(
        id="case-001",
        case_type=CaseType.RISK,
        subject=subject,
        created_at=datetime(2025, 6, 1),
        sources=sources,
        evidence_integrity=ei,
        trust_graph=graph,
    )


def _make_ei(
    *,
    grade: IntegrityGrade = IntegrityGrade.B,
    score: float = 78.0,
    n_contradictions: int = 1,
    n_unsupported: int = 1,
) -> EvidenceIntegrityReport:
    contradictions = [
        Contradiction(
            contradiction_id=f"con-{i}",
            claim_a=Claim(
                claim_id=f"ca-{i}",
                claim_type=ClaimType.FUNDING_AMOUNT,
                value_raw="$2M raised",
                source_url="https://techcabal.com/article",
                source_title="TechCabal",
                staleness=StalenessT.FRESH,
                confidence=0.85,
            ),
            claim_b=Claim(
                claim_id=f"cb-{i}",
                claim_type=ClaimType.FUNDING_AMOUNT,
                value_raw="$500K raised",
                source_url="https://blog.example.com/post",
                source_title="Example Blog",
                staleness=StalenessT.AGING,
                confidence=0.60,
            ),
            severity=ContradictionSeverity.HIGH,
            description=f"Revenue figures conflict across sources (#{i}).",
            recommended_action="Verify with audited accounts.",
        )
        for i in range(n_contradictions)
    ]
    unsupported = [
        UnsupportedClaim(
            claim_type=ClaimType.EMPLOYEE_COUNT,
            description=f"Team size not verified in open sources (#{i}).",
            severity=ContradictionSeverity.MEDIUM,
            recommended_action="Request current org chart.",
        )
        for i in range(n_unsupported)
    ]
    return EvidenceIntegrityReport(
        integrity_score=score,
        integrity_grade=grade,
        evidence_depth=EvidenceDepth.MODERATE,
        consistency_status=(
            ConsistencyStatus.CONFLICTS
            if n_contradictions > 0
            else ConsistencyStatus.CLEAN
        ),
        sparse_mode=False,
        source_count=6,
        claim_count=12,
        high_authority_count=3,
        contradictions=contradictions,
        unsupported_claims=unsupported,
        integrity_summary="Moderate OSINT coverage with one material conflict.",
        verification_checklist=["Verify funding with audited accounts."],
    )


def _make_graph() -> TrustGraph:
    return TrustGraph(
        nodes=[
            TrustNode(id="subj", label="HealthBridge Kenya", node_type="company", weight=1.0),
            TrustNode(id="partner", label="AMREF Health Africa", node_type="institution", weight=0.9),
            TrustNode(id="media1", label="Health Policy Plus", node_type="media", weight=0.7),
        ],
        edges=[
            TrustEdge(source="subj", target="partner", relation="partnered_with", strength=0.85),
            TrustEdge(source="subj", target="media1", relation="mentioned_in", strength=0.60),
        ],
        trust_score=68.0,
        density=0.67,
        explanation="Strong institutional anchor via AMREF partnership.",
    )


def _make_sources() -> list[SourceAttribution]:
    return [
        SourceAttribution(
            title="HealthBridge Kenya - TechCabal",
            url="https://techcabal.com/healthbridge",
            snippet="HealthBridge Kenya raised $2M to expand digital health.",
            relevance=0.92,
            source_type="web",
            confidence_score=0.88,
        ),
        SourceAttribution(
            title="Example Blog post",
            url="https://blog.example.com/post",
            snippet="HealthBridge reported $500K in early funding.",
            relevance=0.65,
            source_type="web",
            confidence_score=0.55,
        ),
    ]


def _make_signal(
    idx: int = 1,
    level: SignalLevel = SignalLevel.HIGH,
    category: SignalCategory = SignalCategory.GOVERNANCE,
    direction: str = "risk",
    evidence_refs: list[str] | None = None,
) -> Signal:
    return Signal(
        id=f"sig-{idx}",
        case_id="case-001",
        level=level,
        category=category,
        title=f"Test signal {idx}",
        description=f"Description of signal {idx}.",
        direction=direction,
        evidence_refs=evidence_refs or [f"C{idx}"],
        evidence_summary=f"Evidence summary for signal {idx}.",
        recommended_action=f"Recommended action for signal {idx}.",
        time_horizon="short-term",
        confidence=0.75,
    )


def _make_signals(n: int = 3) -> list[Signal]:
    levels = [SignalLevel.CRITICAL, SignalLevel.HIGH, SignalLevel.MEDIUM, SignalLevel.LOW]
    cats = [
        SignalCategory.GOVERNANCE,
        SignalCategory.FINANCIAL,
        SignalCategory.IMPACT,
        SignalCategory.OPERATIONAL,
    ]
    return [
        _make_signal(
            idx=i,
            level=levels[(i - 1) % len(levels)],
            category=cats[(i - 1) % len(cats)],
        )
        for i in range(1, n + 1)
    ]


# ── Test 1 — _clip() ─────────────────────────────────────────────────────────

class TestClip:
    def test_short_string_unchanged(self):
        assert _clip("hello world") == "hello world"

    def test_truncates_at_limit(self):
        long = "a " * 700
        result = _clip(long, 100)
        assert len(result) <= 100
        assert result.endswith("…")

    def test_collapses_whitespace(self):
        assert _clip("hello   \n  world") == "hello world"

    def test_empty_string(self):
        assert _clip("") == ""

    def test_none_safe(self):
        assert _clip(None) == ""  # type: ignore[arg-type]

    def test_exact_limit_no_ellipsis(self):
        text = "a" * 50
        result = _clip(text, 50)
        assert "…" not in result


# ── Test 2 — _signal_ref() ───────────────────────────────────────────────────

class TestSignalRef:
    def test_first_signal(self):
        assert _signal_ref(1) == "[SG1]"

    def test_tenth_signal(self):
        assert _signal_ref(10) == "[SG10]"

    def test_format_is_bracket_sg_number(self):
        for i in range(1, 6):
            ref = _signal_ref(i)
            assert ref.startswith("[SG")
            assert ref.endswith("]")
            assert str(i) in ref


# ── Test 3 — _refs_str() ─────────────────────────────────────────────────────

class TestRefsStr:
    def test_empty_returns_empty_string(self):
        assert _refs_str([]) == ""

    def test_single_ref(self):
        assert _refs_str(["C1"]) == "C1"

    def test_multiple_refs_joined_by_dot(self):
        result = _refs_str(["C1", "S2", "D3"])
        assert "C1" in result
        assert "S2" in result
        assert "D3" in result

    def test_separator_is_middot(self):
        result = _refs_str(["A", "B"])
        assert "·" in result


# ── Test 4 — [CASE] section ──────────────────────────────────────────────────

class TestCaseSectionInContext:
    def test_case_header_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "[CASE]" in ctx

    def test_case_id_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "case-001" in ctx

    def test_subject_name_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "HealthBridge Kenya" in ctx

    def test_secondary_name_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "Dr. Amina Osei" in ctx

    def test_region_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "East Africa" in ctx

    def test_sector_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "HealthTech" in ctx

    def test_case_type_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "risk" in ctx.lower()


# ── Test 5 — [SIGNALS_SUMMARY] section ───────────────────────────────────────

class TestSignalsSummarySectionInContext:
    def test_summary_header_present(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(3))
        assert "[SIGNALS_SUMMARY]" in ctx

    def test_total_signal_count_correct(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(3))
        assert "3" in ctx

    def test_level_distribution_line_present(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(3))
        assert "Level distribution" in ctx

    def test_category_distribution_line_present(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(3))
        assert "Category distribution" in ctx

    def test_empty_signals_shows_no_signals_message(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "No signals generated" in ctx

    def test_top_priority_preview_present_for_three_signals(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(3))
        assert "Top priority" in ctx


# ── Test 6 — [SIGNALS] detail section ────────────────────────────────────────

class TestSignalsDetailSectionInContext:
    def test_signals_header_present(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(2))
        assert "[SIGNALS]" in ctx

    def test_signal_title_present(self):
        signals = _make_signals(1)
        ctx = build_ask_signals_context(_make_case(), signals)
        assert signals[0].title in ctx

    def test_signal_description_present(self):
        signals = _make_signals(1)
        ctx = build_ask_signals_context(_make_case(), signals)
        assert signals[0].description in ctx

    def test_recommended_action_present(self):
        signals = _make_signals(1)
        ctx = build_ask_signals_context(_make_case(), signals)
        assert signals[0].recommended_action in ctx

    def test_time_horizon_present(self):
        signals = _make_signals(1)
        ctx = build_ask_signals_context(_make_case(), signals)
        assert "short-term" in ctx

    def test_direction_present(self):
        signals = _make_signals(1)
        ctx = build_ask_signals_context(_make_case(), signals)
        assert "RISK" in ctx or "risk" in ctx

    def test_confidence_present(self):
        signals = _make_signals(1)
        ctx = build_ask_signals_context(_make_case(), signals)
        assert "0.75" in ctx


# ── Test 7 — [SG#] signal citations ──────────────────────────────────────────

class TestSignalCitationLabels:
    def test_sg1_present_for_one_signal(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(1))
        assert "[SG1]" in ctx

    def test_sg1_through_sg3_for_three_signals(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(3))
        assert "[SG1]" in ctx
        assert "[SG2]" in ctx
        assert "[SG3]" in ctx

    def test_sg4_absent_for_three_signals(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(3))
        assert "[SG4]" not in ctx

    def test_sg_labels_increase_sequentially(self):
        signals = _make_signals(5)
        ctx = build_ask_signals_context(_make_case(), signals)
        for i in range(1, 6):
            assert f"[SG{i}]" in ctx

    def test_no_sg_labels_when_no_signals(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "[SG1]" not in ctx


# ── Test 8 — [EVIDENCE_INTEGRITY] section ────────────────────────────────────

class TestEvidenceIntegritySectionInContext:
    def test_ei_header_present_when_ei_set(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "[EVIDENCE_INTEGRITY]" in ctx

    def test_ei_header_absent_when_no_ei(self):
        ctx = build_ask_signals_context(_make_case(with_ei=False), [])
        assert "[EVIDENCE_INTEGRITY]" not in ctx

    def test_grade_present_in_ei_section(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "Grade B" in ctx

    def test_score_present_in_ei_section(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "78/100" in ctx

    def test_depth_and_consistency_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "moderate" in ctx.lower()

    def test_integrity_summary_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "Moderate OSINT coverage" in ctx

    def test_verification_checklist_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "Verify funding" in ctx


# ── Test 9 — [C#] contradiction citations ────────────────────────────────────

class TestContradictionCitationsInContext:
    def test_c1_label_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "[C1]" in ctx

    def test_contradiction_severity_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "HIGH" in ctx

    def test_claim_values_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "$2M" in ctx
        assert "$500K" in ctx

    def test_multiple_contradictions_all_labeled(self):
        case = _make_case(with_ei=False)
        case.evidence_integrity = _make_ei(n_contradictions=3)
        ctx = build_ask_signals_context(case, [])
        assert "[C1]" in ctx
        assert "[C2]" in ctx
        assert "[C3]" in ctx

    def test_max_5_contradictions_rendered(self):
        case = _make_case(with_ei=False)
        case.evidence_integrity = _make_ei(n_contradictions=7)
        ctx = build_ask_signals_context(case, [])
        assert "[C5]" in ctx
        assert "[C6]" not in ctx


# ── Test 10 — [U#] unsupported claim citations ───────────────────────────────

class TestUnsupportedClaimCitationsInContext:
    def test_u1_label_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "[U1]" in ctx

    def test_unsupported_description_present(self):
        ctx = build_ask_signals_context(_make_case(with_ei=True), [])
        assert "Team size not verified" in ctx

    def test_max_5_unsupported_rendered(self):
        case = _make_case(with_ei=False)
        case.evidence_integrity = _make_ei(n_unsupported=7)
        ctx = build_ask_signals_context(case, [])
        assert "[U5]" in ctx
        assert "[U6]" not in ctx

    def test_no_u_labels_when_no_unsupported(self):
        case = _make_case(with_ei=False)
        case.evidence_integrity = _make_ei(n_unsupported=0)
        ctx = build_ask_signals_context(case, [])
        assert "[U1]" not in ctx


# ── Test 11 — [TRUST_GRAPH] section ──────────────────────────────────────────

class TestTrustGraphSectionInContext:
    def test_trust_graph_header_when_graph_set(self):
        ctx = build_ask_signals_context(_make_case(with_graph=True), [])
        assert "[TRUST_GRAPH]" in ctx

    def test_trust_graph_absent_when_no_graph(self):
        ctx = build_ask_signals_context(_make_case(with_graph=False), [])
        assert "[TRUST_GRAPH]" not in ctx

    def test_trust_score_present(self):
        ctx = build_ask_signals_context(_make_case(with_graph=True), [])
        assert "68/100" in ctx

    def test_density_present(self):
        ctx = build_ask_signals_context(_make_case(with_graph=True), [])
        assert "0.67" in ctx

    def test_graph_explanation_present(self):
        ctx = build_ask_signals_context(_make_case(with_graph=True), [])
        assert "AMREF" in ctx

    def test_node_type_breakdown_present(self):
        ctx = build_ask_signals_context(_make_case(with_graph=True), [])
        assert "company" in ctx or "institution" in ctx


# ── Test 12 — [EVIDENCE_SOURCES] / [S#] citations ────────────────────────────

class TestEvidenceSourcesSectionInContext:
    def test_sources_header_present(self):
        ctx = build_ask_signals_context(_make_case(with_sources=True), [])
        assert "[EVIDENCE_SOURCES]" in ctx

    def test_s1_label_present(self):
        ctx = build_ask_signals_context(_make_case(with_sources=True), [])
        assert "[S1]" in ctx

    def test_s2_label_present(self):
        ctx = build_ask_signals_context(_make_case(with_sources=True), [])
        assert "[S2]" in ctx

    def test_source_title_present(self):
        ctx = build_ask_signals_context(_make_case(with_sources=True), [])
        assert "TechCabal" in ctx

    def test_source_url_present(self):
        ctx = build_ask_signals_context(_make_case(with_sources=True), [])
        assert "techcabal.com" in ctx

    def test_source_snippet_present(self):
        ctx = build_ask_signals_context(_make_case(with_sources=True), [])
        assert "digital health" in ctx

    def test_sources_absent_when_no_sources(self):
        ctx = build_ask_signals_context(_make_case(with_sources=False), [])
        assert "[EVIDENCE_SOURCES]" not in ctx


# ── Test 13 — Empty signals list ─────────────────────────────────────────────

class TestEmptySignals:
    def test_no_sg1_label(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "[SG1]" not in ctx

    def test_signals_section_still_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "[SIGNALS]" in ctx

    def test_no_signals_message_present(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert "No signals" in ctx

    def test_context_is_non_empty_string(self):
        ctx = build_ask_signals_context(_make_case(), [])
        assert isinstance(ctx, str) and len(ctx) > 0


# ── Test 14 — Minimal case (no EIE, no graph, no sources) ────────────────────

class TestMinimalCase:
    def _bare_case(self) -> Case:
        return Case(
            id="bare-001",
            case_type=CaseType.RISK,
            subject=CaseSubject(id="s", name="Bare Subject", kind="program"),
        )

    def test_builds_without_error(self):
        ctx = build_ask_signals_context(self._bare_case(), [])
        assert isinstance(ctx, str)

    def test_no_ei_section(self):
        ctx = build_ask_signals_context(self._bare_case(), [])
        assert "[EVIDENCE_INTEGRITY]" not in ctx

    def test_no_trust_graph_section(self):
        ctx = build_ask_signals_context(self._bare_case(), [])
        assert "[TRUST_GRAPH]" not in ctx

    def test_no_sources_section(self):
        ctx = build_ask_signals_context(self._bare_case(), [])
        assert "[EVIDENCE_SOURCES]" not in ctx

    def test_case_section_still_present(self):
        ctx = build_ask_signals_context(self._bare_case(), [])
        assert "[CASE]" in ctx


# ── Test 15 — Context bounded to MAX_CONTEXT_CHARS ───────────────────────────

class TestContextBound:
    def test_large_payload_stays_within_limit(self):
        signals = [
            _make_signal(
                idx=i,
                evidence_refs=[f"C{i}", f"S{i}"],
            )
            for i in range(1, 40)
        ]
        case = _make_case(with_ei=True, with_graph=True, with_sources=True)
        ctx = build_ask_signals_context(case, signals)
        assert len(ctx) <= MAX_CONTEXT_CHARS

    def test_small_payload_not_clipped(self):
        ctx = build_ask_signals_context(_make_case(), _make_signals(2))
        assert len(ctx) < MAX_CONTEXT_CHARS


# ── Test 16 — answer_ask_signals_question: LLM called correctly (mock) ───────

class TestAnswerCallsLLM:
    def _call(self, question: str, history=None) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) captured from the mock."""
        captured: dict = {}

        def fake_complete(system: str, user: str, temperature: float = 0.2) -> str:
            captured["system"] = system
            captured["user"] = user
            return "Mocked analyst response."

        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.side_effect = fake_complete
            answer_ask_signals_question(
                _make_case(), _make_signals(3), question, history
            )

        return captured["system"], captured["user"]

    def test_llm_called_once(self):
        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.return_value = "response"
            answer_ask_signals_question(_make_case(), _make_signals(1), "test?")
        instance.complete.assert_called_once()

    def test_returns_string(self):
        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.return_value = "analyst response"
            result = answer_ask_signals_question(
                _make_case(), _make_signals(1), "What is the top risk?"
            )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_question_present_in_user_prompt(self):
        _, user = self._call("What are the top 3 risks?")
        assert "What are the top 3 risks?" in user

    def test_context_pack_present_in_user_prompt(self):
        _, user = self._call("Explain signal 1")
        assert "[CASE]" in user

    def test_temperature_is_0_2(self):
        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.return_value = "ok"
            answer_ask_signals_question(_make_case(), [], "test?")
        _, kwargs = instance.complete.call_args
        # temperature can come as positional arg[2] or kwarg
        call_args = instance.complete.call_args
        temp = call_args[1].get("temperature", call_args[0][2] if len(call_args[0]) > 2 else None)
        assert temp == 0.2


# ── Test 17 — History truncated to 8 turns ───────────────────────────────────

class TestHistoryTruncation:
    def test_more_than_8_messages_truncated(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(20)
        ]
        captured: dict = {}

        def fake_complete(system: str, user: str, temperature: float = 0.2) -> str:
            captured["user"] = user
            return "ok"

        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.side_effect = fake_complete
            answer_ask_signals_question(_make_case(), [], "?", history)

        # Only last 8 messages should appear — msg 12..19
        assert "msg 0" not in captured["user"]
        assert "msg 12" in captured["user"] or "msg 19" in captured["user"]

    def test_none_history_does_not_raise(self):
        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.return_value = "ok"
            answer_ask_signals_question(_make_case(), [], "test?", None)
        instance.complete.assert_called_once()

    def test_empty_history_does_not_raise(self):
        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.return_value = "ok"
            answer_ask_signals_question(_make_case(), [], "test?", [])
        instance.complete.assert_called_once()


# ── Test 18 — EI grounding appended to system prompt ─────────────────────────

class TestEIGroundingInSystemPrompt:
    def _capture_system(self, with_ei: bool) -> str:
        captured: dict = {}

        def fake_complete(system: str, user: str, temperature: float = 0.2) -> str:
            captured["system"] = system
            return "ok"

        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.side_effect = fake_complete
            answer_ask_signals_question(
                _make_case(with_ei=with_ei), [], "test?"
            )
        return captured.get("system", "")

    def test_ei_grounding_present_when_ei_set(self):
        system = self._capture_system(with_ei=True)
        assert "Evidence integrity grounding" in system

    def test_ei_grounding_absent_when_no_ei(self):
        system = self._capture_system(with_ei=False)
        assert "Evidence integrity grounding" not in system

    def test_grade_in_ei_grounding(self):
        system = self._capture_system(with_ei=True)
        assert "Grade B" in system

    def test_score_in_ei_grounding(self):
        system = self._capture_system(with_ei=True)
        assert "78/100" in system


# ── Test 19 — Trust graph grounding appended to system prompt ────────────────

class TestTrustGraphGroundingInSystemPrompt:
    def _capture_system(self, with_graph: bool) -> str:
        captured: dict = {}

        def fake_complete(system: str, user: str, temperature: float = 0.2) -> str:
            captured["system"] = system
            return "ok"

        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.side_effect = fake_complete
            answer_ask_signals_question(
                _make_case(with_graph=with_graph), [], "test?"
            )
        return captured.get("system", "")

    def test_trust_graph_grounding_present_when_graph_set(self):
        system = self._capture_system(with_graph=True)
        assert "Trust graph grounding" in system

    def test_trust_graph_grounding_absent_when_no_graph(self):
        system = self._capture_system(with_graph=False)
        assert "Trust graph grounding" not in system

    def test_trust_score_in_grounding(self):
        system = self._capture_system(with_graph=True)
        assert "68/100" in system


# ── Test 20 — Synthetic end-to-end: "top 3 risks" response cites [SG#] ───────

class TestSyntheticEndToEnd:
    """Verify that when the LLM returns a response containing [SG#] citations,
    those labels originate from signals that were actually in the context pack.
    This is a grounding validation: every [SG#] in the response must correspond
    to a signal that was numbered in the context."""

    def test_sg_references_in_mocked_response_are_valid(self):
        signals = _make_signals(4)
        case = _make_case()
        context = build_ask_signals_context(case, signals)

        # Simulate an LLM response that cites signals
        mocked_response = (
            "The top 3 risks are: [SG1] governance conflict, "
            "[SG2] financial exposure, and [SG3] operational gap. "
            "Evidence: [C1] confirms the conflict. "
            "Before acting, verify: [SG1] recommended action."
        )

        with patch("kulima.signals.ask_signals.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.complete.return_value = mocked_response
            result = answer_ask_signals_question(
                case, signals, "What are the top 3 risks?"
            )

        # Response was returned
        assert result == mocked_response

        # All cited [SG#] in the response exist in the context pack
        import re
        cited_refs = re.findall(r"\[SG(\d+)\]", result)
        for ref_num in cited_refs:
            assert f"[SG{ref_num}]" in context, (
                f"[SG{ref_num}] cited in response but not found in context pack"
            )

    def test_signals_in_context_match_count(self):
        """Context must contain exactly as many [SG#] labels as signals provided."""
        import re
        signals = _make_signals(5)
        ctx = build_ask_signals_context(_make_case(), signals)
        found = set(re.findall(r"\[SG(\d+)\]", ctx))
        assert found == {"1", "2", "3", "4", "5"}

    def test_opportunity_signal_direction_in_context(self):
        opp_signal = _make_signal(
            idx=1, level=SignalLevel.LOW,
            category=SignalCategory.IMPACT,
            direction="opportunity",
        )
        ctx = build_ask_signals_context(_make_case(), [opp_signal])
        assert "opportunity" in ctx.lower()
        assert "✅" in ctx

    def test_risk_signal_direction_in_context(self):
        risk_signal = _make_signal(idx=1, direction="risk")
        ctx = build_ask_signals_context(_make_case(), [risk_signal])
        assert "⚠" in ctx

    def test_all_citation_types_present_in_full_context(self):
        """With EI + graph + sources + signals, all citation namespaces present."""
        case = _make_case(with_ei=True, with_graph=True, with_sources=True)
        signals = _make_signals(3)
        ctx = build_ask_signals_context(case, signals)
        assert "[SG1]" in ctx   # signal
        assert "[C1]"  in ctx   # contradiction
        assert "[U1]"  in ctx   # unsupported claim
        assert "[S1]"  in ctx   # web source
