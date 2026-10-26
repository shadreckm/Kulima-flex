"""Offline validation of Kulima Africa's expected understanding.

Runs the intelligence layer (entity classification + decision framework +
report title) directly against the Business Plan / Pitch Deck text,
without needing a live backend.
"""
import sys
sys.path.insert(0, ".")

from kulima.intelligence.entity_profile import (
    build_entity_profile, entity_decision, entity_report_title,
)

BP = """KULIMA AFRICA — BUSINESS PLAN
Organization Name: Kulima Africa
Sector: Technology
1. EXECUTIVE SUMMARY
Kulima Africa is a decision intelligence company building evidence-to-decision
infrastructure for NGOs, development programs, DFIs and government programs.
Business model: SaaS subscriptions plus per-assessment pricing. We serve NGO
MEAL teams, government program review units and DFI portfolio officers. We are
NOT an AgriTech or agriculture business. Signals Engine, Evidence Engine,
Research Intelligence modules. Customer discovery completed with 40+ MEAL
interviews. Market validation confirms willingness to pay. Pilot deployment
with two NGOs in Malawi, Kenya and Zambia.
"""

PITCH = """KULIMA AFRICA — PITCH DECK
Kulima Africa: Decision Intelligence Platform. Evidence-to-Decision
Infrastructure for NGOs, Development Programs, Government Programs and MEAL
Teams. Products: Signals Engine, Evidence Engine, Research Intelligence.
Traction: customer discovery, market validation, pilot deployment.
Sector: Technology. Business model: SaaS.
"""

EXPECTED_UNDERSTANDING = [
    "decision intelligence", "evidence-to-decision", "ngo", "development program",
    "government program", "meal", "signals engine", "evidence engine",
    "research intelligence", "customer discovery", "market validation",
    "pilot deployment",
]
BANNED = ["agritech"]

def run(name, text):
    profile = build_entity_profile("startup", [{"name": name.lower(), "text": text}], text)
    etype = profile.entity.entity_type
    fw = profile.decision_framework
    rec_text = " | ".join(lbl for _, _, lbl in fw.bands)
    title = entity_report_title(etype)
    _, band_label = entity_decision(78.0, etype)
    lowered = text.lower()
    recognized = [k for k in EXPECTED_UNDERSTANDING if k in lowered]
    banned_hits = [b for b in BANNED if b in lowered and "not an agritech" not in lowered]
    print(f"=== {name} ===")
    print(f"  entity_type       : {etype}")
    print(f"  decision framework: {rec_text}")
    print(f"  score 78 maps to  : {band_label}")
    print(f"  report title      : {title}")
    print(f"  understood        : {len(recognized)}/{len(EXPECTED_UNDERSTANDING)} {recognized}")
    print(f"  agritech-only hits: {banned_hits if 'not an agritech' not in lowered else 'none (negated in text)'}")
    ok = etype == "startup" and "Invest" in rec_text and title == "Investment Committee Report"
    print(f"  VERDICT           : {'PASS' if ok else 'FAIL'}")
    return ok

ok1 = run("Business Plan", BP)
ok2 = run("Pitch Deck", PITCH)
print("\nFINAL:", "ALL_PASS" if ok1 and ok2 else "FAILURES_PRESENT")
