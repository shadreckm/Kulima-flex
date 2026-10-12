"""Gemini integration validation: full pipeline per single-provider outage.

For each provider P in {openai, groq, gemini, openrouter, huggingface}:
disable P via the live override endpoint, run a complete pipeline
(Upload → Assessment/Research → Evidence → Trust → Signals → Decision →
Reports) and record which provider served the run.
"""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()
OUT = r"C:\temp\kulima_test\gemini_validation.json"

PROVIDERS = ["openai", "groq", "gemini", "openrouter", "huggingface"]


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


def run_pipeline(org):
    doc = open(r"C:\temp\kulima_test\small_1mb.txt", "rb").read()
    text = (f"Organization Name: {org}\nFounder: Ms. Test Lead\nLocations: Nairobi\n"
            "Budget: USD 500,000\nActivities: training, outreach\nObjectives: expand coverage\n"
            "Outcomes: 2000 beneficiaries\nRisks: drought, currency\nJanuary 2026\n").encode()
    boundary = "----kv"
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="brief.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()
        + text + doc + b"\r\n",
        f'--{boundary}\r\nContent-Disposition: form-data; name="assessmentType"\r\n\r\nstartup\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="organizationName"\r\n\r\n{org}\r\n'.encode(),
        f'--{boundary}--\r\n'.encode(),
    ])
    r = urllib.request.Request(BASE + "/api/v1/assessments/", method="POST", data=body)
    r.add_header("Authorization", "Bearer " + TOKEN)
    r.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(r, timeout=180) as resp:
        created = json.loads(resp.read())
    aid = created["assessmentId"]
    st, run = req(f"/api/v1/assessments/{aid}/start", "POST", {})
    rid = run["runId"]
    info = {}
    for _ in range(150):
        time.sleep(3)
        st, info = req(f"/api/v1/intelligence/{rid}")
        if info.get("status") in ("completed", "failed"):
            break
    st, ws = req(f"/api/v1/assessment-workspace/{aid}")
    reports = {}
    for kind in ("memo", "report", "signals", "one-pager", "due-diligence"):
        for attempt in range(3):
            st2, payload = req(f"/api/v1/intelligence/{rid}/reports/{kind}", raw=True)
            if st2 == 200:
                break
            time.sleep(4)
        reports[kind] = st2 if st2 == 200 else f"HTTP {st2}"
    st, brief = req(f"/api/v1/intelligence/{rid}/brief/full")
    return {
        "assessmentId": aid,
        "runStatus": info.get("status"),
        "trust": ws.get("trustScore"),
        "signals": len(ws.get("signals") or []),
        "decision": (ws.get("decision") or {}).get("recommendation"),
        "providerUsed": ws.get("providerUsed"),
        "providerLabel": ws.get("providerLabel"),
        "aiMode": ws.get("aiMode"),
        "reports": reports,
        "execHead": str(brief.get("executive_summary") or "")[:70] if isinstance(brief, dict) else str(st),
    }


results = []
for p in PROVIDERS:
    org = f"Gemini Validation {p} Ltd"
    req("/api/v1/intelligence/providers/override", "POST", {"reset": True})
    st, ov = req("/api/v1/intelligence/providers/override", "POST", {"disable": [p]})
    row = {"disabled": p, "chain": ov.get("chain") if isinstance(ov, dict) else ov}
    try:
        row.update(run_pipeline(org))
    except Exception as exc:
        row["error"] = str(exc)[:200]
    st, status_after = req("/api/v1/intelligence/providers/status")
    row["lastProviderUsed"] = status_after.get("lastProviderUsed")
    row["lastFallbackCount"] = status_after.get("lastFallbackCount")
    results.append(row)
    with open(OUT, "w") as f:
        json.dump(results, f, indent=1)
    req("/api/v1/intelligence/providers/override", "POST", {"reset": True})

print(json.dumps(results, indent=1))
