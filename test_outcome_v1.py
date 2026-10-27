"""Outcome Layer V1 validation — DecisionRecord, 30-day follow-up, Outcome Capture.

Scope (deliberately minimal — the V1 goal is to validate whether users actually
provide follow-up information):

1. ensure_decision_record() freezes a pending DecisionRecord with a 30-day
   follow-up window derived from the run's created_at.
2. Record creation is idempotent and backfills historical runs.
3. list_decision_records(only_due=True) only surfaces unanswered records whose
   window has opened.
4. save_followup_answer() stores exactly the two V1 answers
   ("Was a decision taken?", "Was the recommendation followed?") and closes
   the cycle; re-answering updates the record.
5. list_decision_history() exposes the follow-up fields for the Decision
   History / Decision Outcome UI.
6. The outcomes router endpoints validate the answer enums, enforce
   workspace isolation, and return camelCase payloads.

NO DAS, NO Portfolio Learning, NO Learning Reports, NO billing changes —
these tests also assert the V1 payload surface stays free of such fields.

All tests use temporary SQLite databases — no production DB is touched.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The backend auth module requires NEXTAUTH_SECRET at import time.
os.environ.setdefault("NEXTAUTH_SECRET", "local-pytest-secret")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from backend.app.core.auth import AuthenticatedUser, OrgContext  # noqa: E402
from backend.app.routers import outcomes as outcomes_router  # noqa: E402
from backend.app.routers.outcomes import FollowupAnswerRequest  # noqa: E402
from kulima.core.orgs.models import (  # noqa: E402
    Organization,
    OrganizationMember,
    Role,
)
from kulima.db import IntelligenceRepository  # noqa: E402
from kulima.models import InvestmentBrief, Recommendation  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _tmp_repo() -> tuple[IntelligenceRepository, Path]:
    """Return a fresh repository backed by a temporary file DB."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = Path(tmp.name)
    repo = IntelligenceRepository(db_path=str(path))
    return repo, path


def _minimal_brief(startup: str = "PayFast NG") -> InvestmentBrief:
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


def _make_run(
    repo: IntelligenceRepository, startup: str = "PayFast NG"
) -> int:
    return repo.save_brief(_minimal_brief(startup), user_id="u-1", org_id="org-1")


def _mark_overdue(repo: IntelligenceRepository, run_id: int) -> None:
    """Backdate the follow-up window so the record counts as due."""
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE decision_records SET followup_due_at = ? WHERE run_id = ?",
            (past, run_id),
        )
        conn.commit()


def _ctx() -> OrgContext:
    org = Organization(id="org-1", name="Acme", slug="acme", plan="free")
    member = OrganizationMember(org_id="org-1", user_id="u-1", role=Role("owner"))
    return OrgContext(user=AuthenticatedUser("u-1"), org=org, membership=member)


@pytest.fixture()
def repo():  # noqa: ANN201
    repository, path = _tmp_repo()
    yield repository
    path.unlink(missing_ok=True)


@pytest.fixture()
def patched_repo(repo, monkeypatch):  # noqa: ANN001, ANN201
    """Point the outcomes router at the temporary repository."""
    monkeypatch.setattr(outcomes_router, "_repo", repo)
    return repo


# ── 1. DecisionRecord creation + 30-day window ───────────────────────────────

def test_ensure_decision_record_creates_pending_with_30_day_window(repo) -> None:
    run_id = _make_run(repo)
    record = repo.ensure_decision_record(run_id)

    assert record is not None
    assert record["run_id"] == run_id
    assert record["followup_status"] == "pending"
    assert record["decision_taken"] is None
    assert record["recommendation_followed"] is None
    assert record["answered_at"] is None
    assert record["entity_name"] == "PayFast NG"
    assert record["recommendation"] == Recommendation.OBSERVE.value
    assert record["org_id"] == "org-1"

    snapshot = datetime.fromisoformat(record["decision_snapshot_at"])
    due = datetime.fromisoformat(record["followup_due_at"])
    assert (due - snapshot) == timedelta(days=30)


def test_ensure_decision_record_is_idempotent(repo) -> None:
    run_id = _make_run(repo)
    first = repo.ensure_decision_record(run_id)
    second = repo.ensure_decision_record(run_id)

    assert first == second
    with repo._connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM decision_records WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
    assert count == 1


def test_ensure_decision_record_unknown_run_returns_none(repo) -> None:
    assert repo.ensure_decision_record(999_999) is None


# ── 2. Backfill + due-window filtering ───────────────────────────────────────

def test_backfill_covers_historical_runs(repo) -> None:
    run_id = _make_run(repo)  # run saved without touching decision surfaces
    rows = repo.list_decision_records(org_id="org-1")
    assert [r["run_id"] for r in rows] == [run_id]
    assert rows[0]["followup_status"] == "pending"


def test_only_due_surfaces_open_windows_only(repo) -> None:
    fresh = _make_run(repo, startup="Fresh Co")
    overdue = _make_run(repo, startup="Late Co")
    repo.ensure_decision_record(fresh)
    repo.ensure_decision_record(overdue)
    _mark_overdue(repo, overdue)

    due = repo.list_decision_records(org_id="org-1", only_due=True)
    assert [r["run_id"] for r in due] == [overdue]

    all_rows = repo.list_decision_records(org_id="org-1")
    assert {r["run_id"] for r in all_rows} == {fresh, overdue}


def test_backfill_reports_created_count(repo) -> None:
    _make_run(repo, startup="A Co")
    _make_run(repo, startup="B Co")
    assert repo.ensure_decision_records_backfill(org_id="org-1") == 2
    assert repo.ensure_decision_records_backfill(org_id="org-1") == 0


# ── 3. Outcome Capture: the two V1 questions ─────────────────────────────────

def test_save_followup_answer_stores_both_questions_and_closes_cycle(repo) -> None:
    run_id = _make_run(repo)
    record = repo.save_followup_answer(run_id, "yes", "fully")

    assert record is not None
    assert record["decision_taken"] == "yes"
    assert record["recommendation_followed"] == "fully"
    assert record["followup_status"] == "answered"
    assert record["answered_at"] is not None

    # Answered records no longer appear in the due queue.
    _mark_overdue(repo, run_id)
    assert repo.list_decision_records(org_id="org-1", only_due=True) == []


def test_save_followup_answer_is_reanswerable(repo) -> None:
    run_id = _make_run(repo)
    repo.save_followup_answer(run_id, "in_progress", "partially")
    updated = repo.save_followup_answer(run_id, "no", "unknown")

    assert updated["decision_taken"] == "no"
    assert updated["recommendation_followed"] == "unknown"
    assert updated["followup_status"] == "answered"
    with repo._connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM decision_records WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
    assert count == 1


# ── 4. Decision History enrichment for the UI ────────────────────────────────

def test_list_decision_history_exposes_followup_fields(repo) -> None:
    run_id = _make_run(repo)
    repo.ensure_decision_record(run_id)
    repo.save_followup_answer(run_id, "yes", "not_yet")

    rows = repo.list_decision_history(user_id="u-1", limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row["followup_status"] == "answered"
    assert row["decision_taken"] == "yes"
    assert row["recommendation_followed"] == "not_yet"
    assert row["answered_at"] is not None
    assert "followup_due_at" in row


def test_v1_payload_has_no_learning_fields(repo) -> None:
    """V1 boundary: no DAS / portfolio-learning fields leak into the record."""
    run_id = _make_run(repo)
    record = repo.ensure_decision_record(run_id)
    forbidden = {"das", "decision_accuracy_score", "learning", "cycle", "signal_kind"}
    keys = {k.lower() for k in record}
    assert not (keys & forbidden)


# ── 5. Router endpoints ──────────────────────────────────────────────────────

def test_router_due_endpoint_returns_camelcase_queue(patched_repo) -> None:
    run_id = _make_run(patched_repo)
    patched_repo.ensure_decision_record(run_id)
    _mark_overdue(patched_repo, run_id)

    res = outcomes_router.get_due_followups(current=_ctx())
    assert res["total"] == 1
    item = res["followups"][0]
    assert item["runId"] == run_id
    assert item["followupStatus"] == "pending"
    assert item["decisionTaken"] is None
    assert set(item) == {
        "runId", "entityName", "recommendation", "trustScore", "integrityGrade",
        "decisionSnapshotAt", "followupDueAt", "followupStatus", "decisionTaken",
        "recommendationFollowed", "decisionComment", "answeredAt",
    }


def test_router_decision_record_endpoint_creates_on_read(patched_repo) -> None:
    run_id = _make_run(patched_repo)
    payload = outcomes_router.get_decision_record(run_id, current=_ctx())
    assert payload["runId"] == run_id
    assert payload["followupStatus"] == "pending"


def test_router_decision_record_404_for_foreign_run(patched_repo) -> None:
    with pytest.raises(HTTPException) as exc:
        outcomes_router.get_decision_record(4242, current=_ctx())
    assert exc.value.status_code == 404


def test_router_answer_endpoint_stores_valid_answers(patched_repo) -> None:
    run_id = _make_run(patched_repo)
    req = FollowupAnswerRequest(decisionTaken="YES", recommendationFollowed=" Partially ")
    payload = outcomes_router.post_followup_answer(run_id, req, current=_ctx())

    assert payload["decisionTaken"] == "yes"
    assert payload["recommendationFollowed"] == "partially"
    assert payload["followupStatus"] == "answered"
    assert payload["answeredAt"] is not None


def test_router_answer_endpoint_rejects_invalid_enums(patched_repo) -> None:
    run_id = _make_run(patched_repo)

    bad = FollowupAnswerRequest(decisionTaken="maybe", recommendationFollowed="fully")
    with pytest.raises(HTTPException) as exc:
        outcomes_router.post_followup_answer(run_id, bad, current=_ctx())
    assert exc.value.status_code == 422

    bad2 = FollowupAnswerRequest(decisionTaken="yes", recommendationFollowed="sometimes")
    with pytest.raises(HTTPException) as exc2:
        outcomes_router.post_followup_answer(run_id, bad2, current=_ctx())
    assert exc2.value.status_code == 422

    # Nothing was written for the rejected attempts.
    record = patched_repo.ensure_decision_record(run_id)
    assert record["followup_status"] == "pending"


def test_router_answer_endpoint_404_for_foreign_run(patched_repo) -> None:
    req = FollowupAnswerRequest(decisionTaken="yes", recommendationFollowed="fully")
    with pytest.raises(HTTPException) as exc:
        outcomes_router.post_followup_answer(4242, req, current=_ctx())
    assert exc.value.status_code == 404


# ── 5b. Follow-up comments + Outcome Review Report ───────────────────────────

def test_save_followup_answer_stores_comment(repo) -> None:
    run_id = _make_run(repo)
    record = repo.save_followup_answer(run_id, "yes", "partially", "Board approved the pilot")
    assert record["decision_comment"] == "Board approved the pilot"

    # Omitted comment defaults to empty on re-answers that skip it.
    again = repo.save_followup_answer(run_id, "no", "no")
    assert again["decision_comment"] == ""


def test_router_answer_passes_comment(patched_repo) -> None:
    run_id = _make_run(patched_repo)
    req = FollowupAnswerRequest(
        decisionTaken="yes", recommendationFollowed="fully", comment="  Signed the MoU  "
    )
    payload = outcomes_router.post_followup_answer(run_id, req, current=_ctx())
    assert payload["decisionComment"] == "Signed the MoU"

    req2 = FollowupAnswerRequest(decisionTaken="yes", recommendationFollowed="fully")
    payload2 = outcomes_router.post_followup_answer(run_id, req2, current=_ctx())
    assert payload2["decisionComment"] == ""


def test_outcome_review_report_txt_contains_four_sections(patched_repo, monkeypatch) -> None:
    from kulima.models import InvestmentBrief  # noqa: F811 — same class, local clarity

    run_id = _make_run(patched_repo)
    patched_repo.save_followup_answer(run_id, "yes", "partially", "Hired the country lead")
    monkeypatch.setattr(
        outcomes_router, "_load_brief_model",
        lambda *a, **k: _minimal_brief("PayFast NG"),
    )

    res = outcomes_router.download_outcome_review(run_id, format="txt", current=_ctx())
    text = res.body.decode("utf-8")
    assert "Recommendation" in text and "Decision Taken" in text
    assert "Comments" in text and "Lessons" in text
    assert "Hired the country lead" in text
    assert "Partially followed" in text
    assert res.media_type == "text/plain; charset=utf-8"


def test_outcome_review_report_pending_never_invents(patched_repo, monkeypatch) -> None:
    run_id = _make_run(patched_repo)
    patched_repo.ensure_decision_record(run_id)
    monkeypatch.setattr(
        outcomes_router, "_load_brief_model",
        lambda *a, **k: _minimal_brief("PayFast NG"),
    )

    res = outcomes_router.download_outcome_review(run_id, format="txt", current=_ctx())
    text = res.body.decode("utf-8")
    assert "still waiting" in text
    assert "No lessons can be drawn yet" in text
    assert "Comments appear here" in text


def test_outcome_review_report_pdf_renders(patched_repo, monkeypatch) -> None:
    run_id = _make_run(patched_repo)
    patched_repo.save_followup_answer(run_id, "in_progress", "not_yet", "Committee convened")
    monkeypatch.setattr(
        outcomes_router, "_load_brief_model",
        lambda *a, **k: _minimal_brief("PayFast NG"),
    )

    res = outcomes_router.download_outcome_review(run_id, format="pdf", current=_ctx())
    assert len(res.body) > 100  # PDF bytes, or text fallback without reportlab
    assert "Outcome_Review.pdf" in res.headers["content-disposition"]


def test_outcome_review_404_for_foreign_run(patched_repo) -> None:
    with pytest.raises(HTTPException) as exc:
        outcomes_router.download_outcome_review(4242, format="txt", current=_ctx())
    assert exc.value.status_code == 404


# ── 6. V1 scope guard: no new billing/DAS surfaces were added ────────────────

def test_v1_route_table_is_minimal() -> None:
    paths = {
        (route.path, tuple(sorted(route.methods)))
        for route in outcomes_router.router.routes
    }
    assert paths == {
        ("/due", ("GET",)),
        ("/{run_id}/decision-record", ("GET",)),
        ("/{run_id}/decision-record/answer", ("POST",)),
        ("/{run_id}/outcome-review", ("GET",)),
        ("/history", ("GET",)),
        ("/{run_id}/outcome", ("GET",)),
        ("/{run_id}/outcome", ("POST",)),
        ("/intelligence", ("GET",)),
    }
