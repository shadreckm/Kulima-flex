"""Outcome Layer V1 adoption validation — AI Analyst grounding, report snapshot.

Covers the Phase 3–5 surfaces added on top of the V1 DecisionRecord:

1. build_ask_ic_context emits an [OUTCOME_FOLLOWUP] block from the stored
   30-day follow-up — answered records state the answers, pending records
   state that nothing was reported (and the analyst must not invent one).
2. The Document Intelligence fallback answers the three post-decision
   questions from the stored outcome record only.
3. Report exports gain an Outcome Snapshot section when — and only when —
   a follow-up answer exists. Facts only: no scores, no learning models.

No database is touched: the decision record is injected via monkeypatch or
plain dicts.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("NEXTAUTH_SECRET", "local-pytest-secret")

import pytest  # noqa: E402

from kulima.ask_ic import build_ask_ic_context
from kulima.export import outcome_snapshot_lines, outcome_snapshot_markdown
from kulima.models import InvestmentBrief, Recommendation

# Production (second) definition in demo_chat wins the module name.
from backend.app.services.demo_chat import doc_intelligence_ask_ic_answer


def _brief(startup: str = "PayFast NG") -> InvestmentBrief:
    return InvestmentBrief(
        founder_name="Ada Obi",
        startup_name=startup,
        sector="Fintech",
        geography="Nigeria",
        stage="Seed",
        overall_score=72.0,
        founder_score=68.0,
        startup_score=74.0,
        market_score=70.0,
        trust_score=65.0,
        risk_score=28.0,
        confidence=0.71,
        recommendation=Recommendation.OBSERVE,
    )


def _record(status: str = "answered", decision: str = "yes", followed: str = "partially") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "run_id": 7,
        "entity_name": "PayFast NG",
        "recommendation": "OBSERVE",
        "decision_snapshot_at": (now - timedelta(days=31)).isoformat(),
        "followup_due_at": (now - timedelta(days=1)).isoformat(),
        "followup_status": status,
        "decision_taken": decision if status == "answered" else None,
        "recommendation_followed": followed if status == "answered" else None,
        "answered_at": now.isoformat() if status == "answered" else None,
    }


# ── 1. AI Analyst context grounding ──────────────────────────────────────────

def test_ask_ic_context_includes_answered_outcome(monkeypatch) -> None:
    from kulima.db import IntelligenceRepository

    monkeypatch.setattr(
        IntelligenceRepository, "ensure_decision_record",
        lambda self, run_id: _record(),
    )
    ctx = build_ask_ic_context(_brief(), run_id=7)
    assert "[OUTCOME_FOLLOWUP]" in ctx
    assert "Was a decision taken? Yes — a decision was taken" in ctx
    assert "Was the recommendation followed? Partially followed" in ctx


def test_ask_ic_context_marks_pending_outcome(monkeypatch) -> None:
    from kulima.db import IntelligenceRepository

    monkeypatch.setattr(
        IntelligenceRepository, "ensure_decision_record",
        lambda self, run_id: _record(status="pending"),
    )
    ctx = build_ask_ic_context(_brief(), run_id=7)
    assert "[OUTCOME_FOLLOWUP]" in ctx
    assert "PENDING" in ctx
    assert "Do not invent an outcome" in ctx


def test_ask_ic_context_unchanged_without_run_id(monkeypatch) -> None:
    def _boom(self, run_id):  # pragma: no cover - must not be called
        raise AssertionError("outcome lookup must not run without a run id")

    from kulima.db import IntelligenceRepository
    monkeypatch.setattr(IntelligenceRepository, "ensure_decision_record", _boom)
    ctx = build_ask_ic_context(_brief())
    assert "[OUTCOME_FOLLOWUP]" not in ctx


# ── 2. Document Intelligence fallback: the three questions ───────────────────

@pytest.mark.parametrize("question", [
    "What happened after this recommendation?",
    "Was a decision taken?",
    "Was the recommendation followed?",
])
def test_doc_intel_answers_outcome_questions_from_record(question) -> None:
    answer = doc_intelligence_ask_ic_answer(
        _brief(), question, outcome=_record(),
    )
    assert "Follow-up recorded for PayFast NG" in answer
    assert "Was a decision taken? **Yes" in answer
    assert "Was the recommendation followed? **Partially followed" in answer


def test_doc_intel_pending_outcome_is_honest() -> None:
    answer = doc_intelligence_ask_ic_answer(
        _brief(), "What happened after this recommendation?", outcome=_record(status="pending"),
    )
    assert "not been recorded yet" in answer
    assert "Outcomes" in answer


def test_doc_intel_missing_outcome_never_invents() -> None:
    answer = doc_intelligence_ask_ic_answer(
        _brief(), "Was a decision taken for this entity?", outcome=None,
    )
    assert "No follow-up on file" in answer
    assert "will not invent an outcome" in answer


def test_doc_intel_other_questions_unaffected() -> None:
    answer = doc_intelligence_ask_ic_answer(_brief(), "what are the top risks?")
    assert "Follow-up" not in answer


# ── 3. Report Outcome Snapshot ───────────────────────────────────────────────

def test_snapshot_lines_only_when_answered() -> None:
    assert outcome_snapshot_lines(None) == []
    assert outcome_snapshot_lines(_record(status="pending")) == []
    lines = outcome_snapshot_lines(_record())
    assert any("Was a decision taken? Yes" in line for line in lines)
    assert any("Was the recommendation followed? Partially followed" in line for line in lines)
    assert any("Recommendation at decision time: OBSERVE" in line for line in lines)


def test_snapshot_markdown_block() -> None:
    assert outcome_snapshot_markdown(None) == ""
    assert outcome_snapshot_markdown(_record(status="pending")) == ""
    block = outcome_snapshot_markdown(_record())
    assert "## Outcome Snapshot (30-Day Follow-up)" in block
    # Scope guard: facts only — no scoring or learning vocabulary.
    for forbidden in ("score", "accuracy", "learning", "DAS"):
        assert forbidden.lower() not in block.lower()


def test_router_report_payload_carries_snapshot() -> None:
    from backend.app.routers.intelligence import _report_payload

    body, media, ext = _report_payload(_brief(), "memo", "txt", _record())
    text = body.decode("utf-8")
    assert ext == "txt"
    assert "Outcome Snapshot (30-Day Follow-up)" in text

    body2, _, _ = _report_payload(_brief(), "memo", "txt", None)
    assert "Outcome Snapshot" not in body2.decode("utf-8")

    # PDF path must not crash with or without the snapshot (reportlab may be
    # absent in dev; both the PDF and the text-fallback paths are valid).
    body3, _, ext3 = _report_payload(_brief(), "memo", "pdf", _record())
    assert body3 and ext3 in ("pdf", "txt")


# ── 4. Follow-up comments + "What changed?" + Outcome Review ─────────────────

def _commented(comment: str = "Board approved the pilot phase") -> dict:
    rec = _record()
    rec["decision_comment"] = comment
    return rec


def test_ask_ic_context_includes_team_comment(monkeypatch) -> None:
    from kulima.db import IntelligenceRepository

    monkeypatch.setattr(
        IntelligenceRepository, "ensure_decision_record",
        lambda self, run_id: _commented(),
    )
    ctx = build_ask_ic_context(_brief(), run_id=7)
    assert "Team comment (verbatim): Board approved the pilot phase" in ctx


def test_doc_intel_answers_what_changed_from_record() -> None:
    answer = doc_intelligence_ask_ic_answer(
        _brief(), "What changed?", outcome=_commented(),
    )
    assert "Follow-up recorded for PayFast NG" in answer
    assert 'Team comment: \u201cBoard approved the pilot phase\u201d' in answer


def test_snapshot_lines_include_comment_only_when_recorded() -> None:
    lines = outcome_snapshot_lines(_commented())
    assert any(line.startswith("Comments: Board approved the pilot phase") for line in lines)
    assert not any(line.startswith("Comments:") for line in outcome_snapshot_lines(_record()))


def test_outcome_review_sections_cover_the_four_headings() -> None:
    from kulima.export import build_outcome_review_text, outcome_review_sections

    titles = [t for t, _ in outcome_review_sections(_brief(), _commented())]
    assert titles == ["Recommendation", "Decision Taken", "Comments", "Lessons"]

    text = build_outcome_review_text(_brief(), _commented())
    assert "Was a decision taken? Yes — a decision was taken" in text
    assert "Board approved the pilot phase" in text
    # Scope guard: a review of recorded facts — no scoring/learning vocabulary.
    for forbidden in ("accuracy", "learning model", "calibration", "DAS"):
        assert forbidden.lower() not in text.lower()


def test_outcome_review_pending_is_honest() -> None:
    from kulima.export import build_outcome_review_text

    text = build_outcome_review_text(_brief(), _record(status="pending"))
    assert "Follow-up still waiting" in text
    assert "No lessons can be drawn yet" in text

