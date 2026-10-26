"""Phase 8b — Kulima Africa PITCH DECK validation: same expectations as the
Business Plan run, but with a Pitch Deck upload. Verifies the intelligence
layer understands Kulima Africa as a Decision Intelligence Platform /
Evidence-to-Decision Infrastructure — never as a generic AgriTech startup."""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()
OUT = r"C:\temp\kulima_test\kulima_africa_pitch_deck_test.json"

PITCH_DECK = """KULIMA AFRICA — INVESTOR PITCH DECK
Organization Name: Kulima Africa
Founder: Mr. Edward Chikwero
Country: Malawi
Sector: Technology

SLIDE 1 — WHO WE ARE
Kulima Africa is a decision intelligence company building evidence-to-decision
infrastructure for NGOs, development programs, DFIs and government programs.
We are NOT an AgriTech or agriculture business — Kulima is a technology
platform whose customers are development and public institutions.

SLIDE 2 — THE PROBLEM
Scattered program evidence cannot support underwriting-grade decisions for
MEAL teams, evidence units and DFI portfolio officers.

SLIDE 3 — PRODUCT
Kulima FLEX ingests business plans, annual reports, proposals, budgets and
M&E reports; runs evidence integrity, trust scoring, signal generation and a
composite decision engine; produces IC-grade reports.

SLIDE 4 — CUSTOMER DISCOVERY & MARKET VALIDATION
40+ interviews with MEAL teams, evidence units and portfolio officers.
Research intelligence, signals engine and evidence engine modules co-designed
with pilot deployment partners in Malawi, Kenya and Zambia.

SLIDE 5 — BUSINESS MODEL
SaaS subscriptions USD 250-2500/month per workspace plus per-assessment
pricing. Pilot contracts signed with two NGOs.

SLIDE 6 — FUNDING REQUEST
USD 1.2M seed. Use of funds: 45% engineering, 30% go-to-market, 25% operations.
"""


def req(path, method="GET", data=None, raw=False):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(BASE + path, method=method, data=body)
    r.add_header("Authorization", "Bearer " + TOKEN)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            payload = resp.read()
            return resp.status, (payload if raw else json.loads(payload or b"{}"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


doc = open(r"C:\temp\kulima_test\small_1mb.txt", "rb").read()
boundary = "----kv"
body = b"".join([
    f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="Kulima_Africa_Pitch_Deck.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
    + PITCH_DECK.encode() + doc + b"\r\n",
    f'--{boundary}\r\nContent-Disposition: form-data; name="assessmentType"\r\n\r\nstartup\r\n'.encode(),
    f'--{boundary}\r\nContent-Disposition: form-data; name="organizationName"\r\n\r\nKulima Africa\r\n'.encode(),
    f'--{boundary}--\r\n'.encode(),
])
r = urllib.request.Request(BASE + "/api/v1/assessments/", method="POST", data=body)
r.add_header("Authorization", "Bearer " + TOKEN)
r.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
with urllib.request.urlopen(r, timeout=180) as resp:
    created = json.loads(resp.read())
aid = created["assessmentId"]
st, ctx = req(f"/api/v1/assessments/{aid}")
if not isinstance(ctx, dict):
    print("context fetch failed:", st, str(ctx)[:150])
    ctx = {}
profile = ctx.get("entityProfile") or {}
print("docClass:", [(d["filename"], d["docClass"]) for d in profile.get("documentClassifications", [])])
print("entity:", profile.get("entityLabel"), "| confidence:", profile.get("entityConfidence"), "| source:", profile.get("entitySource"))
print("reportTitle:", profile.get("reportTitle"))

st, run = req(f"/api/v1/assessments/{aid}/start", "POST", {})
rid = run["runId"]
info = {}
for _ in range(200):
    time.sleep(3)
    st, info = req(f"/api/v1/intelligence/{rid}")
    if info.get("status") in ("completed", "failed"):
        break
print("run:", info.get("status"))

st, ws = req(f"/api/v1/assessment-workspace/{aid}")
st, brief = req(f"/api/v1/intelligence/{rid}/brief/full")
exec_sum = str(brief.get("executive_summary") or "") if isinstance(brief, dict) else ""
startup_as = str(brief.get("startup_assessment") or "") if isinstance(brief, dict) else ""
market_as = str(brief.get("market_assessment") or "") if isinstance(brief, dict) else ""
all_text = exec_sum + " " + startup_as + " " + market_as

out = {
    "assessmentId": aid,
    "runId": rid,
    "runStatus": info.get("status"),
    "entityProfile": profile,
    "trust": ws.get("trustScore"),
    "signals": len(ws.get("signals") or []),
    "decision": ws.get("decision") or {},
    "providerUsed": ws.get("providerUsed"),
    "aiMode": ws.get("aiMode"),
    "executiveSummary": exec_sum[:900],
    "startupAssessment": startup_as[:500],
    "agritechHits": [t for t in ("agritech", "agritech startup", "agriculture startup") if t in all_text.lower()],
    "negativePhrases": [
        p for p in ("no evidence exists", "unknown entity", "unknown startup", "no evidence", "not been parsed")
        if p in all_text.lower()
    ],
    "recognizedTerms": [
        t for t in ("decision intelligence", "evidence-to-decision", "NGO", "development program", "DFI",
                    "government program", "customer discovery", "market validation", "pilot deployment",
                    "signals engine", "evidence engine", "research intelligence", "MEAL")
        if t.lower() in all_text.lower()
    ],
}
print(json.dumps({k: out[k] for k in ("runStatus", "trust", "signals", "negativePhrases", "agritechHits", "recognizedTerms")}, indent=1, default=str))
with open(OUT, "w") as f:
    json.dump(out, f, indent=1, default=str)
