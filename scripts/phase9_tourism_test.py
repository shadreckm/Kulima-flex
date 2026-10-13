"""Phase 9 — Tourism validation: Tourism Strategy + Business Plan + Financial
Statements uploaded as a tourism_sme assessment. Verifies Tourism / Climate /
Community signals materially influence the decision."""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()
OUT = r"C:\temp\kulima_test\tourism_validation.json"

TOURISM_STRATEGY = """LAKELAND SAFARIS — TOURISM STRATEGY
Destination: Lake Malawi shore, Mangochi. Visitor economy positioning:
eco-lodges, cultural heritage tours, water sports. Seasonality profile:
peak May-October. Target segments: international eco-tourists, regional
diaspora travelers. Distribution: tour operators, OTA listings.
"""

BUSINESS_PLAN = """LAKELAND SAFARIS LIMITED — BUSINESS PLAN
Organization Name: Lakeland Safaris Limited
Founder: Mrs. Thandi Banda
Country: Malawi
Business model: lodge accommodation, guided safari tours, hospitality
services. Revenue model: room bookings, tour packages, restaurant.
Roadmap: expand lodge capacity 2026, add destination experiences.
Funding request: USD 800,000 for lodge expansion and climate resilience
infrastructure (solar power, water storage, flood-resistant construction).
"""

FINANCIALS = """LAKELAND SAFARIS LIMITED — FINANCIAL STATEMENTS
Balance sheet, income statement and cash flow for fiscal year 2025.
Revenue: USD 420,000. Gross profit: USD 168,000. Occupancy 62%.
Climate exposure: drought and flooding affect lake levels and access roads.
Community: 85 local jobs, community heritage partnership, women employment.
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
parts = [
    ("Lakeland_Safaris_Tourism_Strategy.pdf", TOURISM_STRATEGY),
    ("Lakeland_Safaris_Business_Plan.pdf", BUSINESS_PLAN),
    ("Lakeland_Safaris_Financial_Statements.pdf", FINANCIALS),
]
boundary = "----kv"
chunks = []
for fname, text in parts:
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{fname}"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
        + text.encode() + doc + b"\r\n"
    )
chunks += [
    f'--{boundary}\r\nContent-Disposition: form-data; name="assessmentType"\r\n\r\ntourism_sme\r\n'.encode(),
    f'--{boundary}\r\nContent-Disposition: form-data; name="organizationName"\r\n\r\nLakeland Safaris Limited\r\n'.encode(),
    f'--{boundary}\r\nContent-Disposition: form-data; name="country"\r\n\r\nMalawi\r\n'.encode(),
    f'--{boundary}--\r\n'.encode(),
]
body = b"".join(chunks)
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
print("docClasses:", [(d["filename"][:28], d["docClass"]) for d in profile.get("documentClassifications", [])])
print("entity:", profile.get("entityLabel"), "| reportTitle:", profile.get("reportTitle"))
print("signalDomains:", profile.get("signalDomains"))

st, run = req(f"/api/v1/assessments/{aid}/start", "POST", {})
rid = run["runId"]
info = {}
for _ in range(160):
    time.sleep(3)
    st, info = req(f"/api/v1/intelligence/{rid}")
    if info.get("status") in ("completed", "failed"):
        break
print("run:", info.get("status"))

st, ws = req(f"/api/v1/assessment-workspace/{aid}")
st, brief = req(f"/api/v1/intelligence/{rid}/brief/full")
exec_sum = str(brief.get("executive_summary") or "") if isinstance(brief, dict) else ""

out = {
    "assessmentId": aid,
    "runId": rid,
    "runStatus": info.get("status"),
    "entityProfile": profile,
    "trust": ws.get("trustScore"),
    "signalsCount": len(ws.get("signals") or []),
    "decision": ws.get("decision") or {},
    "executiveSummary": exec_sum[:500],
    "tourismClimateCommunityInfluence": None,
}
# Check signals domain summary for Tourism/Climate/Community impact on decision
st, sig = req(f"/api/v1/intelligence/{rid}/signals")
domains = (sig or {}).get("domains") or {}
influence = {}
for key in ("tourism", "climate", "community_impact"):
    d = domains.get(key) or {}
    influence[key] = {
        "score": d.get("score"),
        "count": d.get("count"),
        "summary": (d.get("summary") or "")[:160],
    }
out["tourismClimateCommunityInfluence"] = influence
print(json.dumps(influence, indent=1, default=str))
with open(OUT, "w") as f:
    json.dump(out, f, indent=1, default=str)
