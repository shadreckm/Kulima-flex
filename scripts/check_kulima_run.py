"""Pilot readiness: inspect the completed Kulima Africa run end-to-end."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kulima.config import get_settings

RUN_ID = "52dad1cd-af7d-41af-9193-2f79f661743d"

conn = sqlite3.connect(get_settings().db_path)
conn.row_factory = sqlite3.Row

run = conn.execute(
    "SELECT * FROM api_runs WHERE run_id LIKE ?", (RUN_ID[:20] + "%",)
).fetchone()
print("api_run status:", run["status"], "| db_id:", run["db_id"],
      "| completed_at:", run["completed_at"], "| error:", run["error_message"])

brief_row = conn.execute(
    "SELECT * FROM intelligence_runs WHERE id=?", (run["db_id"],)
).fetchone()
brief_cols = [c[1] for c in conn.execute("PRAGMA table_info(intelligence_runs)").fetchall()]
print("intelligence_runs columns:", brief_cols)
payload = {}
brief_json = None
for cand in ("payload", "brief", "brief_json", "result", "data"):
    if cand in brief_cols and brief_row[cand]:
        brief_json = brief_row[cand]
        break
if brief_json:
    payload = json.loads(brief_json)
else:
    # The brief may live in a dedicated column or table; dump the row's JSON-ish columns.
    for col in brief_cols:
        val = brief_row[col]
        if isinstance(val, str) and val.strip().startswith("{"):
            try:
                payload = json.loads(val)
                print("brief found in column:", col)
                break
            except Exception:
                continue
if not payload:
    print("NO_BRIEF_PAYLOAD_FOUND — cannot run live signals from the stored brief")
print("payload keys:", list(payload.keys())[:15])
ib_src = payload.get("investment_brief") or payload.get("brief") or payload
ib = ib_src if isinstance(ib_src, dict) else {}
print("recommendation:", ib.get("recommendation"),
      "| overall:", ib.get("overall_score", ib.get("overallScore")),
      "| trust:", ib.get("trust_score", ib.get("trustScore")),
      "| risk:", ib.get("risk_score", ib.get("riskScore")))
print("sources:", len(ib.get("sources") or []),
      "| uploaded_evidence:", len(ib.get("uploaded_evidence") or []))
docs = [s.get("title") for s in (ib.get("sources") or [])
        if isinstance(s, dict) and s.get("source_type") == "document"]
print("document sources:", docs[:5])
print("executive_summary:", str(ib.get("executive_summary") or "")[:160])

if not ib.get("sources") and not ib.get("uploaded_evidence"):
    print("NOTE: payload carries no sources — brief likely stored without evidence")

# Signals summary generated live from the brief (what the Signals page calls).
from kulima.models import InvestmentBrief
from kulima.core.cases.adapters import from_investment_brief
from kulima.signals.orchestrator import SignalsOrchestrator
from kulima.signals.signals_summary import build_domain_overviews, count_signals_by_level

if not payload or not ib:
    print("KULIMA_RUN_VALIDATION_SKIPPED (no stored brief payload)")
    raise SystemExit(0)

brief = InvestmentBrief.model_validate(payload.get("investment_brief") or ib)
case = from_investment_brief(brief, case_id=str(run["db_id"]), created_by="pilot")
sigs = SignalsOrchestrator().generate(case, sort=True)
counts = count_signals_by_level(sigs)
overviews = build_domain_overviews(sigs)
print("signals generated:", len(sigs),
      "| levels:", {k: counts.get(k, 0) for k in ("critical", "high", "medium", "low")})
for want in ("tourism", "climate", "community_impact"):
    d = overviews.get(want) or {}
    print(f"  {want}: score={d.get('score')} signals={d.get('signal_count')}")

from kulima.decision import build_decision_view
view = build_decision_view(
    sigs,
    evidence_score=80.0,
    trust_score=float(brief.trust_score or 0) or None,
)
print("decision:", view["score"], view["band"], "|", view["recommendation"])

# Ask IC / provider observability
from kulima.providers import AIProviderManager
st = AIProviderManager.instance().status()
print("provider chain:", st["chain"],
      "| lastProviderUsed:", st["lastProviderUsed"],
      "| lastFallback:", st["lastFallbackTriggered"])
print("KULIMA_RUN_VALIDATION_DONE")
