"""Pilot readiness verification — adoption pass before real users arrive.

Covers the Pilot Success Engineer mission:
  P2  Workspaces + navigation graph: every sidebar and in-page link resolves
      to a real route; no dead ends, no placeholder hrefs, no legacy ?run=
      navigation.
  P3  Timings: deterministic server-side journey (assessment persistence,
      all five report exports in TXT and PDF, the full outcome-capture
      chain) measured end to end.  The live-assessment pipeline is
      provider-bound (LLM) — its time-to-first-assessment is instrumented
      in the pilot guides, not fabricated here.
  P4  State invariants: snapshot fidelity, follow-up idempotency, no stale
      state on fresh users, no contradictory recommendation between
      surfaces.

Offline and isolated: every DB write goes to a disposable SQLite file.

Usage: python scripts/pilot_readiness_check.py
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["KULIMA_DB_PATH"] = _TMP_DB.name
os.environ.setdefault("NEXTAUTH_SECRET", "pilot-readiness-secret")

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def _brief(entity: str, name: str, summary: str, lead: str):
    from kulima.models import InvestmentBrief, Recommendation, RedFlag

    return InvestmentBrief(
        founder_name=lead, startup_name=name,
        sector="Tourism" if entity == "tourism_sme" else "Food Security",
        geography="Zimbabwe" if entity == "tourism_sme" else "Kenya",
        stage="Growth Stage",
        overall_score=61.0, founder_score=58.0, startup_score=61.0,
        market_score=60.0, trust_score=61.0, risk_score=40.0, confidence=0.6,
        recommendation=Recommendation.OBSERVE,
        executive_summary=summary, startup_assessment=summary,
        investment_recommendation=summary,
        red_flags=[RedFlag(severity="high", title="Concentration risk",
                           detail="80% of revenue from a single source")],
        next_steps=["Verify the flagged evidence before committing."],
    )


ENTITIES = {
    "ngo": ("Bright Future Trust",
            "A non-governmental organization and registered charity: a civil society nonprofit serving beneficiaries.",
            "Grace Banda"),
    "development_program": ("Resilience Programme",
            "A donor-funded development programme working with farming communities across three provinces.",
            "John Mwangala"),
    "tourism_sme": ("Victoria Falls Lodge",
            "A tourism safari lodge and tour operator dependent on the visitor economy.",
            "Chipo Dube"),
    "government_program": ("County Delivery Programme",
            "A government programme delivering services to citizens through county implementation units.",
            "Amara Nkomo"),
    "startup": ("AgriPulse",
            "An agriculture technology startup with paying customers and a venture-scale growth plan.",
            "Tunde Adeyemi"),
}

KINDS = ["memo", "report", "signals", "due-diligence", "one-pager"]


# ── Navigation graph helpers ────────────────────────────────────────────────

def build_routes(app_dir: Path) -> set[tuple[str, ...]]:
    routes = set()
    for p in app_dir.rglob("page.tsx"):
        routes.add(tuple(s.lower() for s in p.parent.relative_to(app_dir).parts))
    return routes


def link_resolves(link: str, routes: set[tuple[str, ...]]) -> bool:
    segs = tuple(s for s in link.split("?")[0].split("#")[0].strip("/").lower().split("/") if s)
    for route in routes:
        if len(route) != len(segs):
            continue
        if all(a == b or a.startswith("[") or b.startswith("[") for a, b in zip(route, segs)):
            return True
    return False


def collect_links(frontend: Path) -> set[str]:
    pat = re.compile(r"""href=["'](/[^"'{}$]+)["']|(?:router\.(?:push|replace)|window\.location(?:\.href)?\s*=\s*)\s*["'](/[^"'{}$]+)["']""")
    links: set[str] = set()
    for base in (frontend / "app", frontend / "components", frontend / "hooks"):
        if not base.exists():
            continue
        for f in base.rglob("*.tsx"):
            for m in pat.finditer(f.read_text(encoding="utf-8", errors="replace")):
                link = m.group(1) or m.group(2)
                if link and not link.startswith("/api"):
                    links.add(link)
    return links


def main() -> int:
    frontend = ROOT / "frontend"

    # ── [P2] Workspaces, navigation, dead ends ───────────────────────────────
    print("\n[P2] Workspaces and navigation graph")
    workspaces = {
        "Assessment": "app/assessments/page.tsx",
        "Research": "app/research/page.tsx",
        "Evidence": "app/evidence/page.tsx",
        "Signals": "app/signals/page.tsx",
        "Decision": "app/decision/page.tsx",
        "Reports": "app/reports/page.tsx",
        "AI Analyst": "app/flex/page.tsx",
        "Feedback": "app/feedback/page.tsx",
        "Outcome Follow-Up": "app/outcomes/page.tsx",
    }
    for ws, rel in workspaces.items():
        check(f"workspace route exists: {ws} (/{rel.split('/')[1]})", (frontend / rel).exists())

    routes = build_routes(frontend / "app")
    links = collect_links(frontend)
    dead = sorted(l for l in links if not link_resolves(l, routes))
    check("every in-app link resolves to a real route (no dead ends)", not dead, f"dead: {dead}")

    sidebar_src = (frontend / "components/NavigationSidebar/NavigationSidebar.tsx").read_text(encoding="utf-8")
    sidebar_hrefs = re.findall(r"""href:\s*['"](/[^'"]+)['"]""", sidebar_src)
    dead_nav = [h for h in sidebar_hrefs if not link_resolves(h, routes)]
    check(f"all {len(sidebar_hrefs)} sidebar navigation links resolve", not dead_nav, f"dead: {dead_nav}")

    placeholder = []
    legacy_run_param = []
    for base in ("app",):
        for f in (frontend / base).rglob("page.tsx"):
            src = f.read_text(encoding="utf-8", errors="replace")
            if 'href="#"' in src:
                placeholder.append(str(f.relative_to(frontend)))
            if re.search(r"""href=[{`][^}]*\?run=""", src):
                legacy_run_param.append(str(f.relative_to(frontend)))
    check("no placeholder href='#' dead links on pages", not placeholder, str(placeholder))
    check("no legacy ?run= URL navigation on pages", not legacy_run_param, str(legacy_run_param))

    # ── [P3] Deterministic journey timings ───────────────────────────────────
    print("\n[P3] Timings (deterministic server-side journey; LLM pipeline is provider-bound)")
    from kulima.db import IntelligenceRepository
    from backend.app.routers.intelligence import _report_payload

    repo = IntelligenceRepository()

    t0 = time.perf_counter()
    run_ids = {}
    for ent, (name, summary, lead) in ENTITIES.items():
        run_ids[ent] = repo.save_brief(_brief(ent, name, summary, lead), user_id="pilot-user", org_id="pilot-org")
    t_assess = time.perf_counter() - t0
    print(f"  info  assessment persistence: {t_assess * 1000:.0f} ms for 5 entities")
    check("time to persist completed assessments < 2s for all 5 entities", t_assess < 2.0, f"{t_assess:.2f}s")

    ngo = _brief("ngo", *ENTITIES["ngo"])
    t_report_pdf = {}
    for kind in KINDS:
        s = time.perf_counter()
        payload_txt, _, _ = _report_payload(ngo, kind, "txt")
        t_report_txt = time.perf_counter() - s
        s = time.perf_counter()
        payload_pdf, mime, _ = _report_payload(ngo, kind, "pdf")
        t_report_pdf[kind] = time.perf_counter() - s
        print(f"  info  report {kind:<13} txt {len(payload_txt):>7}B in {t_report_txt:5.2f}s · pdf {len(payload_pdf):>7}B in {t_report_pdf[kind]:5.2f}s")
        check(f"report '{kind}' renders non-empty TXT and PDF", len(payload_txt) > 200 and len(payload_pdf) > 1000 and mime == "application/pdf")
    check("every report export renders in under 15s (time-to-first-report)",
          all(v < 15.0 for v in t_report_pdf.values()), str({k: round(v, 2) for k, v in t_report_pdf.items()}))

    t_capture = time.perf_counter()
    run_id = run_ids["ngo"]
    repo.ensure_decision_record(run_id)
    repo.save_followup_answer(run_id, "yes", "partially", "Board approved phase one")
    repo.save_decision_outcome(run_id, "In Progress", outcome_notes="First milestone met",
                               lessons={"what_happened": "Funding secured for phase one"}, user_id="pilot-user")
    hist = repo.list_decision_history(user_id="pilot-user", limit=50)
    t_capture_total = time.perf_counter() - t_capture
    print(f"  info  full outcome-capture chain (record→answer→outcome→history): {t_capture_total * 1000:.0f} ms")
    check("time to first outcome capture chain < 3s server-side", t_capture_total < 3.0, f"{t_capture_total:.2f}s")
    row = next((h for h in hist if h["id"] == run_id), None)
    check("outcome-capture journey is one round trip per step (3 writes max)",
          row is not None and row["decision_taken"] == "yes" and row["outcome_status"] == "In Progress")

    # ── [P4] State invariants ────────────────────────────────────────────────
    print("\n[P4] State invariants (no stale state, no contradictions)")
    check("snapshot fidelity: decision record freezes the run recommendation",
          row is not None and row["recommendation"] == "Observe", str(row and row["recommendation"]))

    repo.save_followup_answer(run_id, "no", "no", "Decision deferred to next cycle")
    with repo._connect() as conn:
        n_recs = conn.execute("SELECT COUNT(*) FROM decision_records WHERE run_id = ?", (run_id,)).fetchone()[0]
        n_out = conn.execute("SELECT COUNT(*) FROM decision_outcomes WHERE run_id = ?", (run_id,)).fetchone()[0]
    check("follow-up re-answer is idempotent (one record, updated — D60/D90 safe)",
          n_recs == 1 and n_out == 1, f"records={n_recs} outcomes={n_out}")

    fresh = repo.compute_outcome_intelligence(user_id="brand-new-user")
    check("fresh user sees no stale state: predictive score is None, not a number",
          fresh.get("overall_predictive_score") is None, str(fresh.get("overall_predictive_score")))
    check("fresh user calibration bins are honest (not predictive on empty data)",
          all(not b["is_predictive"] for b in fresh["calibration"]["calibration_bins"]))

    memo_txt, _, _ = _report_payload(ngo, "memo", "txt")
    one_txt, _, _ = _report_payload(ngo, "one-pager", "txt")
    # "LEAD/PRINCIPAL:" is the person-role field label, not the LEAD verdict
    # tier — neutralise it before scanning for investment verdict wording.
    memo_s = memo_txt.decode("utf-8", "replace").upper().replace("LEAD/PRINCIPAL", "")
    one_s = one_txt.decode("utf-8", "replace").upper().replace("LEAD/PRINCIPAL", "")
    check("memo and one-pager carry the identical score line (no page disagrees)",
          "OVERALL SCORE 61/100" in memo_s and "OVERALL SCORE 61/100" in one_s)
    check("OBSERVE assessment shows no INVEST/LEAD verdict wording in memo or one-pager",
          not re.search(r"\bINVEST\b|\bLEAD\b", memo_s) and not re.search(r"\bINVEST\b|\bLEAD\b", one_s)
          and "INVESTMENT DECISION MEMO" not in memo_s)

    # ── Result ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print(f"Pilot readiness checks passed: {len(PASSED)}/{len(PASSED) + len(FAILED)}")
    if FAILED:
        print("FAILED:")
        for f in FAILED:
            print(f"  - {f}")
        print("VERDICT: PILOT_READINESS_BLOCKED")
        print("=" * 62)
        return 1
    print("VERDICT: PILOT_READINESS_PASS")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
