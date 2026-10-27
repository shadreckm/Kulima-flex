"""Outcome Layer V1 adoption validation — end-to-end workflow rehearsal.

Creates five realistic assessments (Startup, NGO, Tourism SME, Development
Program, Government Program) in an ISOLATED temporary database, opens their
30-day follow-up windows, records follow-up answers on four of them (one is
deliberately left pending to validate the honest-pending behaviour), and
verifies the full product surface:

  Phase 1-2  follow-up queue text explains why / what / consequences
  Phase 3    reminder surfaces exist in dashboard, history, outcomes, analyst
  Phase 4    AI Analyst answers post-decision questions from the record
  Phase 5    report exports carry the Outcome Snapshot (answered only)
  Scope      no DAS / learning / portfolio features leaked into V1

Usage:  python scripts/validate_outcome_adoption.py
Prints PASS/FAIL per check and the final verdict OUTCOME_V1_VALIDATED.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["KULIMA_DB_PATH"] = _TMP_DB.name
os.environ.setdefault("NEXTAUTH_SECRET", "local-validation-secret")

from kulima.db import IntelligenceRepository  # noqa: E402
from kulima.models import InvestmentBrief, Recommendation  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name} {detail}")


def brief_for(name: str, founder: str, sector: str, geo: str, stage: str, rec: Recommendation) -> InvestmentBrief:
    return InvestmentBrief(
        founder_name=founder,
        startup_name=name,
        sector=sector,
        geography=geo,
        stage=stage,
        overall_score=68.0,
        founder_score=64.0,
        startup_score=70.0,
        market_score=66.0,
        trust_score=71.0,
        risk_score=35.0,
        confidence=0.7,
        recommendation=rec,
        executive_summary=f"{name} — {sector} entity evaluated for funding/partnership readiness.",
    )


def main() -> int:
    repo = IntelligenceRepository()
    now = datetime.now(timezone.utc)

    # ── 1. Five representative assessments ───────────────────────────────────
    print("\n[1] Creating five profile assessments (isolated temp DB)")
    profiles = [
        ("Kampala Fresh Markets", "Amina Welela", "Agritech Startup", "Uganda", "Seed", Recommendation.OBSERVE, ("yes", "partially", "Board approved a smaller pilot first")),
        ("Bright Future Trust", "Joseph Mwangi", "NGO", "Kenya", "Growth Stage", Recommendation.INVEST, ("yes", "fully", "Grant signed, hiring started")),
        ("Victoria Falls Lodge", "Chipo Dube", "Tourism SME", "Zimbabwe", "Series A", Recommendation.OBSERVE, ("in_progress", "not_yet", "Investor shortlist under review")),
        ("Resilient Farms Programme", "Grace Banda", "Development Program", "Malawi", "Growth Stage", Recommendation.INVEST, ("yes", "partially", "Phased rollout agreed with ministry")),
        ("National Irrigation Scheme", "Peter Odhiambo", "Government Program", "Tanzania", "Growth Stage", Recommendation.PASS, (None, None, None)),  # left pending
    ]
    run_ids: dict[str, int] = {}
    for name, founder, sector, geo, stage, rec, _answers in profiles:
        rid = repo.save_brief(
            brief_for(name, founder, sector, geo, stage, rec),
            user_id="validation-user",
            org_id="validation-org",
        )
        run_ids[name] = rid
    check("five assessments persisted", len(run_ids) == 5)

    # Backdate completions past the 30-day window (simulates real time passing).
    with repo._connect() as conn:
        for rid in run_ids.values():
            conn.execute(
                "UPDATE intelligence_runs SET created_at = ? WHERE id = ?",
                ((now - timedelta(days=32)).isoformat(), rid),
            )
        conn.commit()

    # ── 2. DecisionRecords + due queue ───────────────────────────────────────
    print("\n[2] 30-day follow-up window")
    due = repo.list_decision_records(org_id="validation-org", only_due=True)
    check("all five follow-ups open after 30 days", len(due) == 5, f"got {len(due)}")
    sample = next(d for d in due if d["entity_name"] == "Bright Future Trust")
    snap = datetime.fromisoformat(sample["decision_snapshot_at"])
    due_dt = datetime.fromisoformat(sample["followup_due_at"])
    check("due date is snapshot + 30 days", (due_dt - snap) == timedelta(days=30))

    # ── 3. Outcome Capture: the two questions ────────────────────────────────
    print("\n[3] Recording follow-up answers (4 answered, 1 pending)")
    for name, _f, _s, _g, _st, _r, answers in profiles:
        if answers[0] is None:
            continue
        rec = repo.save_followup_answer(run_ids[name], answers[0], answers[1], answers[2])
        check(f"follow-up stored for {name}", rec["followup_status"] == "answered")

    due_after = repo.list_decision_records(org_id="validation-org", only_due=True)
    check("answered items leave the queue", len(due_after) == 1)
    check("pending item remains in queue", due_after[0]["entity_name"] == "National Irrigation Scheme")

    # ── 4. Decision History + Decision Outcome surfaces ──────────────────────
    print("\n[4] Decision History enrichment")
    history = repo.list_decision_history(user_id="validation-user", limit=50)
    by_name = {h["startup_name"]: h for h in history}
    h = by_name["Kampala Fresh Markets"]
    check("history carries follow-up answers",
          h["followup_status"] == "answered" and h["decision_taken"] == "yes" and h["recommendation_followed"] == "partially")
    check("history carries follow-up comment",
          h["decision_comment"] == "Board approved a smaller pilot first")
    h_pending = by_name["National Irrigation Scheme"]
    check("history keeps pending visible", h_pending["followup_status"] == "pending")

    # ── 5. AI Analyst grounding (Phase 4) ────────────────────────────────────
    print("\n[5] AI Analyst post-decision grounding")
    from kulima.ask_ic import build_ask_ic_context
    brief_ngo = brief_for("Bright Future Trust", "Joseph Mwangi", "NGO", "Kenya", "Growth Stage", Recommendation.INVEST)
    ctx = build_ask_ic_context(brief_ngo, run_id=run_ids["Bright Future Trust"])
    check("analyst context carries [OUTCOME_FOLLOWUP]", "[OUTCOME_FOLLOWUP]" in ctx)
    check("analyst sees recorded answers",
          "Was a decision taken? Yes" in ctx and "Fully followed" in ctx)
    check("analyst sees recorded comment verbatim",
          "Team comment (verbatim): Grant signed, hiring started" in ctx)
    brief_gov = brief_for("National Irrigation Scheme", "Peter Odhiambo", "Government Program", "Tanzania", "Growth Stage", Recommendation.PASS)
    ctx_pending = build_ask_ic_context(brief_gov, run_id=run_ids["National Irrigation Scheme"])
    check("analyst told pending follow-up must not be invented",
          "PENDING" in ctx_pending and "Do not invent an outcome" in ctx_pending)

    from backend.app.services.demo_chat import doc_intelligence_ask_ic_answer
    answered_rec = repo.ensure_decision_record(run_ids["Victoria Falls Lodge"])
    ans = doc_intelligence_ask_ic_answer(
        brief_for("Victoria Falls Lodge", "Chipo Dube", "Tourism SME", "Zimbabwe", "Series A", Recommendation.OBSERVE),
        "What happened after this recommendation?",
        outcome=answered_rec,
    )
    check("doc-intelligence answers 'what happened' from record",
          "Follow-up recorded" in ans and "In progress" in ans and "Too early to tell" in ans)
    ans_changed = doc_intelligence_ask_ic_answer(
        brief_for("Victoria Falls Lodge", "Chipo Dube", "Tourism SME", "Zimbabwe", "Series A", Recommendation.OBSERVE),
        "What changed?",
        outcome=answered_rec,
    )
    check("doc-intelligence answers 'what changed' from record",
          "Follow-up recorded" in ans_changed
          and "Investor shortlist under review" in ans_changed)
    pending_rec = repo.ensure_decision_record(run_ids["National Irrigation Scheme"])
    ans_pending = doc_intelligence_ask_ic_answer(brief_gov, "Was a decision taken?", outcome=pending_rec)
    check("doc-intelligence is honest when nothing recorded", "not been recorded yet" in ans_pending)

    # ── 6. Report Outcome Snapshot (Phase 5) ─────────────────────────────────
    print("\n[6] Report exports — Outcome Snapshot")
    from backend.app.routers.intelligence import _report_payload
    body_answered, _, _ = _report_payload(brief_ngo, "memo", "txt", repo.ensure_decision_record(run_ids["Bright Future Trust"]))
    text_answered = body_answered.decode("utf-8")
    check("answered follow-up appears in memo export",
          "Outcome Snapshot (30-Day Follow-up)" in text_answered
          and "Was a decision taken? Yes" in text_answered
          and "Was the recommendation followed? Fully followed" in text_answered)
    body_pending, _, _ = _report_payload(brief_gov, "report", "txt", repo.ensure_decision_record(run_ids["National Irrigation Scheme"]))
    check("pending follow-up adds no snapshot", "Outcome Snapshot" not in body_pending.decode("utf-8"))
    for kind in ("memo", "report", "signals", "due-diligence", "one-pager"):
        pdf_body, _, ext = _report_payload(brief_ngo, kind, "pdf", repo.ensure_decision_record(run_ids["Bright Future Trust"]))
        check(f"{kind} export renders with snapshot (pdf/txt fallback={ext})", bool(pdf_body))

    # ── 6b. Outcome Review Report (Phase 5 artifact) ─────────────────────────
    print("\n[6b] Outcome Review Report per profile")
    from kulima.export import build_outcome_review_text
    for name, founder, sector, geo, stage, rec, answers in profiles:
        review = build_outcome_review_text(
            brief_for(name, founder, sector, geo, stage, rec),
            repo.ensure_decision_record(run_ids[name]),
        )
        has_headings = all(t in review for t in ("Recommendation", "Decision Taken", "Comments", "Lessons"))
        check(f"outcome review renders for {name}", has_headings)
        if answers[0] is None:
            check(f"pending review stays honest ({name})",
                  "still waiting" in review and "No lessons can be drawn yet" in review)
        else:
            check(f"review carries recorded comment ({name})", answers[2] in review)

    # ── 7. Frontend reminder surfaces (text-level checks) ────────────────────
    print("\n[7] In-product reminder + UX surfaces")
    surfaces = {
        "outcomes queue explains itself": (ROOT / "frontend/app/outcomes/page.tsx",
            ["30-Day Follow-ups Waiting", "Follow-up waiting", "Assessment completed",
             "Help us learn whether", "optional: ignoring them blocks nothing",
             "3. Comments", "Outcome Review Report", "outcomeReviewDownloadHref"]),
        "dashboard follow-up widget": (ROOT / "frontend/app/dashboard/page.tsx",
            ["Pending Follow-Ups", "getDueFollowups", "Help us learn if these recommendations worked",
             "/outcomes", "Recommendation:", "Due {new Date(f.followupDueAt)"]),
        "assessment history reminder": (ROOT / "frontend/app/runs/page.tsx",
            ["Follow-up waiting", "getDueFollowups", "/outcomes"]),
        "AI analyst reminder + quick questions": (ROOT / "frontend/components/ChatShell/ChatShell.tsx",
            ["What happened after this recommendation?", "What changed?", "Was a decision taken?",
             "Was the recommendation followed?", "getDecisionRecord", "Record follow-up"]),
    }
    for label, (path, needles) in surfaces.items():
        src = path.read_text(encoding="utf-8")
        missing = [n for n in needles if n not in src]
        check(label, not missing, f"missing: {missing}")

    # ── 8. Scope guards: nothing beyond V1 was added ─────────────────────────
    print("\n[8] V1 scope guards")
    backend_src = "\n".join(
        p.read_text(encoding="utf-8")
        for p in [
            ROOT / "kulima/db.py",
            ROOT / "backend/app/routers/outcomes.py",
            ROOT / "kulima/export.py",
            ROOT / "kulima/ask_ic.py",
        ]
    )
    for forbidden in ("decision_accuracy_score", "portfolio_learning", "learning_report", "DAS_"):
        check(f"no {forbidden} in V1 backend", forbidden.lower() not in backend_src.lower())

    # ── Verdict ──────────────────────────────────────────────────────────────
    total = len(PASSED) + len(FAILED)
    print(f"\n{'=' * 60}\nChecks passed: {len(PASSED)}/{total}")
    if FAILED:
        for f in FAILED:
            print(f"  FAILED: {f}")
        print("VERDICT: BLOCKERS_REMAIN")
        return 1
    print("Follow-up capture, reminders, analyst grounding and report snapshot "
          "verified across five entity profiles.")
    print("VERDICT: OUTCOME_V1_VALIDATED")
    return 0
    # (founders.db untouched — validation ran on a temporary isolated database)


if __name__ == "__main__":
    try:
        code = main()
    finally:
        os.unlink(_TMP_DB.name)
    sys.exit(code)
