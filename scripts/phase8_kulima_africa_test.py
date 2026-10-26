"""Phase 8 — Kulima Africa test: full business-plan upload through the live
pipeline. Verifies entity recognition and evidence-first narrative."""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()
OUT = r"C:\temp\kulima_test\kulima_africa_test.json"

BUSINESS_PLAN = """KULIMA AFRICA — BUSINESS PLAN
Organization Name: Kulima Africa
Founder: Mr. Edward Chikwero
Country: Malawi
Sector: Technology

1. EXECUTIVE SUMMARY
Kulima Africa is a decision intelligence company building evidence-to-decision
infrastructure for NGOs, development programs, DFIs and government programs.
Our platform turns scattered program evidence into underwriting-grade
decisions. Business model: SaaS subscriptions plus per-assessment pricing.
We serve NGO MEAL teams, government program review units and DFI portfolio
officers. We are NOT an AgriTech or agriculture business — Kulima is a
technology platform whose customers are development and public institutions.

2. PRODUCT ARCHITECTURE
The Kulima FLEX platform ingests business plans, annual reports, proposals,
budgets and M&E reports; runs evidence integrity, trust scoring, signal
generation and a composite decision engine; and produces IC-grade reports.

3. MARKET VALIDATION AND CUSTOMER DISCOVERY
Primary market: NGOs, development programs, DFIs, government programs.
Customer discovery completed with 40+ interviews with MEAL teams, evidence
units and portfolio officers. Research intelligence, signals engine and
evidence engine modules were co-designed with pilot deployment partners across Malawi, Kenya and
Zambia. Market validation confirms willingness to pay for evidence-backed
assessment tooling.

4. REVENUE MODEL
Recurring SaaS revenue: USD 250-2500/month per workspace plus per-assessment
fees. Pilot contracts signed with two NGOs.

5. ROADMAP
Q1 2026: multi-provider AI resilience. Q2 2026: DFI workspace. Q3 2026:
government program review templates. Q4 2026: continental expansion.

6. FUNDING REQUEST
Funding ask: USD 1.2M seed to expand engineering, sales and delivery.
Use of funds: 45% engineering, 30% go-to-market, 25% operations.
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
    f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="Kulima_Africa_Business_Plan.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
    + BUSINESS_PLAN.encode() + doc + b"\r\n",
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
    "negativePhrases": [
        p for p in ("no evidence exists", "unknown entity", "unknown startup", "no evidence", "not been parsed")
        if p in all_text.lower()
    ],
    "recognizedTerms": [
        t for t in ("decision intelligence", "evidence-to-decision", "NGO", "development program", "DFI",
                    "government program", "customer discovery", "market validation", "roadmap",
                    "funding", "business model", "revenue")
        if t.lower() in all_text.lower()
    ],
}
print(json.dumps({k: out[k] for k in ("runStatus", "trust", "signals", "negativePhrases", "recognizedTerms")}, indent=1, default=str))
with open(OUT, "w") as f:
    json.dump(out, f, indent=1, default=str)
