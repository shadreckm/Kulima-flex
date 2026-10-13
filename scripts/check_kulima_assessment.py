"""Pilot readiness: inspect the Kulima Africa Business Plan assessment record.

Reads the shared Assessment Context row (status / entity / trust) and the
linked api_runs row, then generates the live signals summary and decision the
same way the Signals / Decision pages do — so the validation reflects what a
pilot user actually sees.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kulima.config import get_settings

ASSESSMENT_ID = "f100161d-1049-4715-9bce-9cf691c395cb"

conn = sqlite3.connect(get_settings().db_path)
conn.row_factory = sqlite3.Row

r = conn.execute(
    "SELECT * FROM assessment_contexts WHERE assessment_id=?", (ASSESSMENT_ID,)
).fetchone()
if r is None:
    print("ASSESSMENT_NOT_FOUND")
    raise SystemExit(0)

ctx_payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
print("assessment:", r["assessment_id"][:8], "| status:", r["status"],
      "| run_id:", (r["run_id"] or "")[:8],
      "| entity:", ctx_payload.get("startup_name") or ctx_payload.get("organization_name"),
      "| trust:", ctx_payload.get("trust_score"))

run = conn.execute(
    "SELECT * FROM api_runs WHERE run_id=?", (r["run_id"],)
).fetchone()
if run is not None:
    print("api_run status:", run["status"], "| db_id:", run["db_id"],
          "| completed_at:", run["completed_at"], "| error:", run["error_message"])

# Live signals + decision from the stored brief (same path as the pages).
try:
    brief_row = conn.execute(
        "SELECT payload_json FROM intelligence_runs WHERE id=?", (run["db_id"],)
    ).fetchone()
    payload = json.loads(brief_row["payload_json"])

    from kulima.models import InvestmentBrief
    from kulima.core.cases.adapters import from_investment_brief
    from kulima.signals.orchestrator import SignalsOrchestrator
    from kulima.signals.signals_summary import build_domain_overviews, count_signals_by_level
    from kulima.decision import build_decision_view

    brief = InvestmentBrief.model_validate(payload)
    case = from_investment_brief(brief, case_id=str(run["db_id"]), created_by="pilot")
    sigs = SignalsOrchestrator().generate(case, sort=True)
    counts = count_signals_by_level(sigs)
    overviews = build_domain_overviews(sigs)
    print("signals:", len(sigs),
          "| levels:", {k: counts.get(k, 0) for k in ("critical", "high", "medium", "low")})
    for want in ("tourism", "climate", "community_impact"):
        d = overviews.get(want) or {}
        print(f"  {want}: score={d.get('score')} signals={d.get('signal_count')}")
    view = build_decision_view(sigs, evidence_score=80.0,
                               trust_score=float(brief.trust_score or 0) or None)
    print("decision:", view["score"], view["band"], "|", view["recommendation"])
    print("KULIMA_AFRICA_VALIDATION_OK")
except Exception as exc:  # noqa: BLE001
    print("live validation error:", type(exc).__name__, str(exc)[:200])
