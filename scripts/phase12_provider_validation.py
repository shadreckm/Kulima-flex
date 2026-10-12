"""Phase 12 validation: run all 5 assessment types under progressive provider
outage scenarios. The backend is started externally with specific provider
keys removed; this script exercises the full chain and reports results."""
import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()

TYPES = {
    "startup": "Solar Startup Ltd",
    "ngo": "Clean Water NGO",
    "tourism_sme": "Safari Lodge SME",
    "development_program": "Rural Development Program",
    "government_program": "Ministry Energy Program",
}

def req(path, method="GET", data=None, headers=None):
    r = urllib.request.Request(BASE + path, method=method, data=data)
    r.add_header("Authorization", f"Bearer {TOKEN}")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read() or b"{}")

def run_type(atype, org):
    doc = open(r"C:\temp\kulima_test\small_1mb.txt", "rb").read()
    text = (f"Organization Name: {org}\nFounder: Ms. Test Lead\nLocations: Nairobi\n"
            "Budget: USD 500,000\nActivities: training, outreach\nObjectives: expand coverage\n"
            "Outcomes: 2000 beneficiaries\nRisks: drought, currency\nJanuary 2026\n").encode()
    boundary = "----kv"
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="brief.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()
        + text + doc + b"\r\n",
        f'--{boundary}\r\nContent-Disposition: form-data; name="assessmentType"\r\n\r\n{atype}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="organizationName"\r\n\r\n{org}\r\n'.encode(),
        f'--{boundary}--\r\n'.encode(),
    ])
    created = req("/api/v1/assessments/", "POST", body,
                  {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    aid = created["assessmentId"]
    run = req(f"/api/v1/assessments/{aid}/start", "POST")
    rid = run["runId"]
    for _ in range(90):
        time.sleep(2)
        info = req(f"/api/v1/intelligence/{rid}")
        if info.get("status") in ("completed", "failed"):
            break
    ws = req(f"/api/v1/assessment/assistant".replace("assistant", f"workspace/{aid}")) if False else req(f"/api/v1/assessment-workspace/{aid}")
    reports_ok = []
    for kind in ("memo", "report", "signals", "one-pager", "due-diligence"):
        try:
            r = urllib.request.Request(f"{BASE}/api/v1/intelligence/{rid}/reports/{kind}")
            r.add_header("Authorization", f"Bearer {TOKEN}")
            with urllib.request.urlopen(r, timeout=60) as resp:
                reports_ok.append((kind, resp.status, len(resp.read())))
        except Exception as exc:
            reports_ok.append((kind, "ERR", str(exc)[:60]))
    brief = req(f"/api/v1/intelligence/{rid}/brief/full")
    exec_head = str(brief.get("executive_summary") or "")[:70]
    demo_terms = [t for t in ("AgriNova", "OSTX", "Demo Mode") if t in exec_head]
    return {
        "type": atype,
        "run": info.get("status"),
        "signals": len(ws.get("signals") or []),
        "trust": ws.get("trustScore"),
        "decision": (ws.get("decision") or {}).get("recommendation"),
        "researchMode": (ws.get("research") or {}).get("mode"),
        "providerUsed": ws.get("providerUsed"),
        "providerLabel": ws.get("providerLabel"),
        "reports": all(k[1] == 200 for k in reports_ok),
        "reportKinds": [k[0] for k in reports_ok if k[1] == 200],
        "demoTerms": demo_terms,
        "execHead": exec_head,
    }

scenario = sys.argv[1] if len(sys.argv) > 1 else "scenario"
results = []
for atype, org in TYPES.items():
    try:
        results.append(run_type(atype, org))
    except Exception as exc:
        results.append({"type": atype, "error": str(exc)[:200]})
print(json.dumps(results, indent=2))
