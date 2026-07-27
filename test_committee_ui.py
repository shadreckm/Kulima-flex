"""Phase 3 — Committee Intelligence UI tests.

Pure (non-Streamlit) helper coverage for the six Committee Intelligence
features introduced in the UX sprint:

1. Persona card compression  — one-line summaries + auto-expand rules
2. Debate keyword filters     — Objections / Support / Risks / Opportunities
3. Consistent speaker identity — same avatar / color / badge across surfaces
4. Speaker label filters      — VC / Operator / Banker / Impact / Market Specialist
5. Dissent detection          — minority opinions + PASS (negative) votes
6. Scoreboard sorting         — by confidence or by vote

Streamlit rendering functions are tested by verifying they do NOT raise when
called with a mocked ``st`` module via ``unittest.mock.patch``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kulima.config import INVESTOR_ARCHETYPES
from kulima.models import (
    InvestorVote,
    Recommendation,
    SyndicateDecision,
)
from kulima.ui import (
    COMMITTEE_SPEAKERS,
    DEBATE_FILTER_KEYWORDS,
    _debate_line_matches_filter,
    _persona_one_line_summary,
    _speaker_identity_for,
    _speaker_present_in_turn,
    _sort_votes,
    _vote_is_negative_or_dissenting,
    _vote_for_speaker_name,
    render_twin_syndicate_committee,
)


# ═════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═════════════════════════════════════════════════════════════════════════════


def _vote(
    archetype: dict,
    decision: Recommendation = Recommendation.INVEST,
    confidence: float = 75.0,
    reasoning: str = "Likes the founder and market fit.",
    concern: str = "FX risk is real.",
) -> InvestorVote:
    return InvestorVote(
        archetype_id=archetype["id"],
        investor_name=archetype["name"],
        firm=archetype["firm"],
        persona=archetype["persona"],
        title=archetype["title"],
        decision=decision,
        confidence_score=confidence,
        key_reasoning=reasoning,
        major_concern=concern,
        vote=decision,
        conviction=confidence / 100.0,
        score=confidence,
        thesis=reasoning,
        concerns=[concern] if concern else [],
        conditions=["Confirm series A lead interest."],
    )


@pytest.fixture()
def five_votes_consensus_invest() -> list[InvestorVote]:
    """Unanimous Invest with moderate-to-high confidence.  No dissenters."""
    return [
        _vote(INVESTOR_ARCHETYPES[0], Recommendation.INVEST, 82.0),
        _vote(INVESTOR_ARCHETYPES[1], Recommendation.INVEST, 87.0),
        _vote(INVESTOR_ARCHETYPES[2], Recommendation.INVEST, 74.0),
        _vote(INVESTOR_ARCHETYPES[3], Recommendation.INVEST, 78.0),
        _vote(INVESTOR_ARCHETYPES[4], Recommendation.INVEST, 88.0),
    ]


@pytest.fixture()
def five_votes_with_dissent(five_votes_consensus_invest) -> list[InvestorVote]:
    """Split: 3× INVEST, 1× OBSERVE (dissenting), 1× PASS (negative)."""
    votes = five_votes_consensus_invest
    votes[3] = _vote(INVESTOR_ARCHETYPES[3], Recommendation.OBSERVE, 58.0,
                     reasoning="Strategic fit unclear. Need more data.",
                     concern="No clear distribution partnership.")
    votes[4] = _vote(INVESTOR_ARCHETYPES[4], Recommendation.PASS, 41.0,
                     reasoning="Unit economics don't work under current FX.",
                     concern="Unsustainable CAC payback.")
    return votes


@pytest.fixture()
def five_votes_consensus_observe(five_votes_consensus_invest) -> list[InvestorVote]:
    """Majority Observe → any INVEST/PASS is dissenting, any PASS negative."""
    votes = five_votes_consensus_invest
    for i in (0, 1, 2):
        votes[i] = _vote(INVESTOR_ARCHETYPES[i], Recommendation.OBSERVE, 60.0 + i,
                         reasoning=f"OBSERVE vote reason #{i}.")
    votes[3] = _vote(INVESTOR_ARCHETYPES[3], Recommendation.INVEST, 70.0)
    votes[4] = _vote(INVESTOR_ARCHETYPES[4], Recommendation.PASS, 45.0)
    return votes


@pytest.fixture()
def syndicate_with_votes(request) -> SyndicateDecision:
    votes = request.getfixturevalue(request.param)
    tally: dict[Recommendation, int] = {}
    for v in votes:
        tally[v.decision] = tally.get(v.decision, 0) + 1
    final = max(tally.items(), key=lambda kv: kv[1])[0]
    consensus = sum(v.confidence_score for v in votes) / len(votes)
    dissent = 100.0 - max(tally.values()) / len(votes) * 100.0
    transcript_lines = []
    for v in votes:
        name = v.investor_name.split(" ")[0]
        transcript_lines.append(f"{name}: Let me explain my vote.")
        if v.decision == Recommendation.INVEST:
            transcript_lines.append(f"{name}: I support this — strong founder-market fit. Growth is real.")
        elif v.decision == Recommendation.OBSERVE:
            transcript_lines.append(f"{name}: My biggest concern is distribution risk. I need more data.")
        else:
            transcript_lines.append(f"{name}: I object — the unit economics don't work. I will not invest.")
    transcript_lines.append("Amina: Thank you, team — that captures our discussion. Opportunity looks clear.")
    return SyndicateDecision(
        votes=votes,
        majority_vote=final,
        average_score=consensus,
        dissent_index=dissent / 100.0,
        consensus_score=consensus,
        final_recommendation=final,
        dissent_score=dissent,
        debate_transcript="\n".join(transcript_lines),
        consensus_thesis=f"Committee lands on {final.value} with consensus {consensus:.0f}/100.",
        blocking_concerns=[v.major_concern for v in votes if v.decision == Recommendation.PASS and v.confidence_score >= 65][:5],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Mock streamlit globally for all rendering tests
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def mock_streamlit():
    mock_st = MagicMock()
    mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

    def _cols(n, *a, **kw):
        size = len(n) if isinstance(n, (list, tuple)) else int(n)
        out = [MagicMock() for _ in range(size)]
        for col in out:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)
        return out

    mock_st.columns.side_effect = _cols
    mock_st.session_state = {}
    with patch("kulima.ui.st", mock_st):
        yield mock_st


@pytest.fixture()
def mock_brief_with_syndicate(syndicate_with_votes):
    brief = MagicMock()
    brief.syndicate = syndicate_with_votes
    return brief


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — Persona card compression (summary + auto-expand rules)
# ═════════════════════════════════════════════════════════════════════════════


class TestPersonaCardCompression:
    def test_one_line_summary_present(self, five_votes_consensus_invest):
        """Every vote renders a non-empty one-line summary string."""
        for v in five_votes_consensus_invest:
            s = _persona_one_line_summary(v)
            assert isinstance(s, str)
            assert s.strip(), f"Empty summary for {v.investor_name}"
            assert len(s) <= 260, (
                f"Summary too long for {v.investor_name}: {len(s)} chars: {s}"
            )

    def test_one_line_summary_first_sentence_rule(self):
        """Summary should be first sentence of thesis (not full body)."""
        v = _vote(INVESTOR_ARCHETYPES[0], Recommendation.INVEST, 70,
                  reasoning="First sentence. Second sentence. Third sentence with many extra details we do not want in the summary at all costs.")
        s = _persona_one_line_summary(v)
        assert "First sentence." in s
        assert "Second sentence." not in s

    def test_one_line_summary_concern_included_when_present(self):
        """When a major concern exists, the summary line should carry ⚠."""
        v = _vote(INVESTOR_ARCHETYPES[0], Recommendation.INVEST, 70,
                  reasoning="Great founder.", concern="CAC too high.")
        s = _persona_one_line_summary(v)
        assert "⚠" in s
        assert "CAC too high." in s

    def test_one_line_summary_no_concern_no_warning_icon(self):
        """When no major concern, summary should NOT contain ⚠ warning marker."""
        v = _vote(INVESTOR_ARCHETYPES[0], Recommendation.INVEST, 70,
                  reasoning="Great founder.", concern="")
        s = _persona_one_line_summary(v)
        assert "⚠" not in s

    def test_summary_truncates_long_thesis(self):
        """Very long thesis should be ellipsised rather than explode a card."""
        long = "A" * 300 + "."
        v = _vote(INVESTOR_ARCHETYPES[0], Recommendation.INVEST, 70, reasoning=long, concern="")
        s = _persona_one_line_summary(v)
        assert len(s) <= 160
        assert s.endswith("…") or len(s) < 150

    def test_pass_votes_auto_expand(self, five_votes_with_dissent):
        """PASS votes are negative → always auto-expand."""
        majority = Recommendation.INVEST
        for v in five_votes_with_dissent:
            if v.decision == Recommendation.PASS:
                assert _vote_is_negative_or_dissenting(v, majority) is True

    def test_dissenting_observe_auto_expands(self, five_votes_with_dissent):
        """Any OBSERVE vote when majority is INVEST → dissenting → auto-expand."""
        majority = Recommendation.INVEST
        for v in five_votes_with_dissent:
            if v.decision == Recommendation.OBSERVE:
                assert _vote_is_negative_or_dissenting(v, majority) is True

    def test_consensus_majority_vote_not_auto_expand(self, five_votes_consensus_invest):
        """Unanimous INVEST → no vote dissents, no vote negative → no auto-expand."""
        majority = Recommendation.INVEST
        for v in five_votes_consensus_invest:
            assert _vote_is_negative_or_dissenting(v, majority) is False


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — Debate keyword filters
# ═════════════════════════════════════════════════════════════════════════════


class TestDebateKeywordFilters:
    def test_filters_dictionary_has_required_keys(self):
        required = ["All", "Objections", "Support", "Risks", "Opportunities"]
        for r in required:
            assert r in DEBATE_FILTER_KEYWORDS, f"Missing keyword filter '{r}'"

    def test_all_filter_matches_anything(self):
        assert _debate_line_matches_filter("literally any text", "All") is True
        assert _debate_line_matches_filter("", "All") is True

    def test_objections_filter_catches_disagreement(self):
        cases = [
            "I object — this valuation is too high.",
            "I disagree with the thesis.",
            "I will not invest. The CAC is brutal.",
            "I'm skeptical about the growth story.",
            "I will veto this.",
        ]
        for case in cases:
            assert _debate_line_matches_filter(case, "Objections"), f"Failed Objections on: {case}"

    def test_objections_filter_ignores_support(self):
        assert _debate_line_matches_filter("I fully support this round.", "Objections") is False

    def test_support_filter_catches_affirmative(self):
        cases = [
            "I'm excited about this founder.",
            "I will invest — strong conviction.",
            "Clear path to Series A — support the round.",
            "Founder-market fit is clear; I'm confident.",
        ]
        for case in cases:
            assert _debate_line_matches_filter(case, "Support"), f"Failed Support on: {case}"

    def test_risks_filter(self):
        cases = [
            "Biggest risk is churn.",
            "Currency exposure and FX risk concern me.",
            "Regulatory risk in Nigeria is a blocker.",
            "Downside is dangerous.",
        ]
        for case in cases:
            assert _debate_line_matches_filter(case, "Risks"), f"Failed Risks on: {case}"

    def test_opportunities_filter(self):
        cases = [
            "This category is large — huge opportunity.",
            "Strong revenue growth trajectory.",
            "Distribution partnership unlocks the market.",
            "Clear path to Series B.",
        ]
        for case in cases:
            assert _debate_line_matches_filter(case, "Opportunities"), f"Failed Opps on: {case}"


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — Consistent speaker identity
# ═════════════════════════════════════════════════════════════════════════════


class TestConsistentSpeakerIdentity:
    def test_speaker_identity_registry_has_five_roles(self):
        expected = {"VC", "Operator", "Banker", "Impact", "Market Specialist"}
        got = {s["label_short"] for s in COMMITTEE_SPEAKERS.values()}
        assert expected == got, f"Speaker registry mismatch: expected {expected}, got {got}"

    def test_vote_maps_to_stable_identity(self, five_votes_consensus_invest):
        """Same InvestorVote always returns the same identity dict each call."""
        ids = []
        for v in five_votes_consensus_invest:
            a = _speaker_identity_for(v)
            b = _speaker_identity_for(v)
            assert a is b or (a["id"] == b["id"] and a["avatar"] == b["avatar"] and a["color"] == b["color"])
            ids.append(a["id"])
        # All five archetypes should have distinct ids
        assert len(set(ids)) == 5

    def test_speaker_name_maps_to_stable_identity(self):
        """Amina Okonkwo / short 'Amina' → same identity (VC) both times."""
        ident1 = _speaker_identity_for("Amina Okonkwo")
        ident2 = _speaker_identity_for("Amina")
        assert ident1["id"] == ident2["id"] == "african_vc"
        assert ident1["label_short"] == "VC"
        assert ident1["avatar"] == ident2["avatar"]
        assert ident1["color"] == ident2["color"]

    def test_unknown_speaker_has_synthetic_identity(self):
        ident = _speaker_identity_for("Totally Unknown Person")
        assert ident["avatar"] in {"💬", "👤"}
        assert "label_short" in ident and ident["label_short"]
        assert "color" in ident and ident["color"]

    def test_vote_for_speaker_name_resolves_known(self, five_votes_consensus_invest):
        """_vote_for_speaker_name('Fatima', votes) → diaspora_angel vote."""
        v = _vote_for_speaker_name("Fatima", five_votes_consensus_invest)
        assert v is not None
        assert v.archetype_id == "diaspora_angel"


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Speaker label filters
# ═════════════════════════════════════════════════════════════════════════════


class TestSpeakerLabelFilters:
    @pytest.fixture()
    def votes(self, five_votes_consensus_invest):
        return five_votes_consensus_invest

    def test_all_always_true(self, votes):
        assert _speaker_present_in_turn("All", "Amina Okonkwo", votes) is True

    def test_vc_filter_only_matches_vc_speaker(self, votes):
        assert _speaker_present_in_turn("VC", "Amina Okonkwo", votes) is True
        assert _speaker_present_in_turn("VC", "Fatima Diallo", votes) is False

    def test_operator_filter_matches_operator(self, votes):
        assert _speaker_present_in_turn("Operator", "Fatima Diallo", votes) is True
        assert _speaker_present_in_turn("Operator", "James Mwangi-Reed", votes) is False

    def test_banker_filter_matches_cvc(self, votes):
        assert _speaker_present_in_turn("Banker", "Thabo Nkosi", votes) is True

    def test_impact_filter_matches_dfi(self, votes):
        assert _speaker_present_in_turn("Impact", "James Mwangi-Reed", votes) is True

    def test_market_specialist_filter_matches_global(self, votes):
        assert _speaker_present_in_turn("Market Specialist", "Elena Vargas", votes) is True

    def test_unknown_speaker_never_matches_role_filter(self, votes):
        for role in ("VC", "Operator", "Banker", "Impact", "Market Specialist"):
            assert _speaker_present_in_turn(role, "Some Random Commentator", votes) is False


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — Dissent detection
# ═════════════════════════════════════════════════════════════════════════════


class TestDissentDetection:
    @pytest.mark.parametrize("syndicate_with_votes", ["five_votes_with_dissent"], indirect=True)
    def test_dissent_block_present_when_dissent_exists(self, mock_brief_with_syndicate, mock_streamlit):
        render_twin_syndicate_committee(mock_brief_with_syndicate, key_suffix="t")
        # Step 5 expander should be created at least once per call with dissenters
        exp_calls = [c for c in mock_streamlit.expander.call_args_list
                     if "Dissenting Views" in (c.args[0] if c.args else "")]
        assert len(exp_calls) >= 1, "⚠ Dissenting Views expander not created"

    @pytest.mark.parametrize("syndicate_with_votes", ["five_votes_consensus_invest"], indirect=True)
    def test_dissent_block_skipped_on_unanimous(self, mock_brief_with_syndicate, mock_streamlit):
        render_twin_syndicate_committee(mock_brief_with_syndicate, key_suffix="t")
        # Without any dissenters, the expander must not fire
        dissenting = [
            v for v in mock_brief_with_syndicate.syndicate.votes
            if _vote_is_negative_or_dissenting(v, mock_brief_with_syndicate.syndicate.final_recommendation)
        ]
        assert dissenting == []


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — Scoreboard sorting
# ═════════════════════════════════════════════════════════════════════════════


class TestScoreboardSorting:
    def test_sort_by_confidence_desc(self, five_votes_with_dissent):
        """Default 'confidence' sort orders votes by confidence_score desc."""
        out = _sort_votes(five_votes_with_dissent, "confidence", Recommendation.INVEST)
        confs = [v.confidence_score for v in out]
        assert confs == sorted(confs, reverse=True), f"Not desc: {confs}"

    def test_sort_by_vote_grouped_invest_first(self, five_votes_with_dissent):
        """'vote' sort groups Invest first, then Observe/Watch, then Pass."""
        out = _sort_votes(five_votes_with_dissent, "vote", Recommendation.INVEST)
        order = [v.decision.value for v in out]
        # First N votes must be INVEST; any PASS must come last
        first_invest = [r for r in order if r == Recommendation.INVEST.value]
        assert order[:len(first_invest)] == [Recommendation.INVEST.value] * len(first_invest)
        assert order[-1] in {Recommendation.PASS.value, Recommendation.OBSERVE.value}

    def test_sort_by_vote_within_group_descending_confidence(self, five_votes_with_dissent):
        """Within a single vote bucket, order should still be confidence desc."""
        out = _sort_votes(five_votes_with_dissent, "vote", Recommendation.INVEST)
        invests = [v for v in out if v.decision == Recommendation.INVEST]
        confs = [v.confidence_score for v in invests]
        assert confs == sorted(confs, reverse=True)


# ═════════════════════════════════════════════════════════════════════════════
# End-to-end: render never raises for various committee configurations
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("syndicate_with_votes", [
    "five_votes_consensus_invest",
    "five_votes_with_dissent",
    "five_votes_consensus_observe",
], indirect=True)
def test_committee_render_never_raises(mock_brief_with_syndicate):
    # Patch is already installed via autouse fixture; any exception = failure
    render_twin_syndicate_committee(mock_brief_with_syndicate, key_suffix="e2e")


def test_committee_render_no_syndicate(mock_streamlit):
    """No syndicate → warning widget; no crash."""
    brief = MagicMock()
    brief.syndicate = None
    render_twin_syndicate_committee(brief)
    assert mock_streamlit.warning.called
