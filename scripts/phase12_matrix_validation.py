"""Phase 12 multi-provider validation driver (Scenarios A-E).

Uses the live /providers/override endpoint to flip the provider chain between
scenarios, then runs one full pipeline (upload -> assessment -> evidence ->
trust -> signals -> decision -> report) per scenario and records which
provider served it.
"""
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()

SCENARIOS = {
    "A": [],
    "B": ["openai"],
    "C": ["openai", "groq"],
    "D": ["openai", "groq", "openrouter"],
    "E": ["openai", "groq", "openrouter", "huggingface"],
}


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
        return e.code, e.read().decode()[:200]


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
    status, created = req("/api/v1/assessments/", "POST", body,
                          None)  # placeholder; multipart handled below
    return None


def run_pipeline_multipart(org):
    import uuid
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
    status, run = req(f"/api/v1/assessments/{aid}/start", "POST", {})
    rid = run["runId"]
    info = {}
    for _ in range(150):
        time.sleep(3)
        status, info = req(f"/api/v1/intelligence/{rid}")
        if info.get("status") in ("completed", "failed"):
            break
    st, ws = req(f"/api/v1/assessment-workspace/{aid}")
    reports = {}
    for kind in ("memo", "report", "signals", "one-pager", "due-diligence"):
        for attempt in range(3):
            st2, payload = req(f"/api/v1/intelligence/{rid}/reports/{kind}", raw=True)
            if st2 == 200:
                break
            time.sleep(4)  # brief may still be flushing to storage
        reports[kind] = st2 if st2 == 200 else f"HTTP {st2}: {payload[:60]}" if isinstance(payload, str) else st2
    st3, brief = req(f"/api/v1/intelligence/{rid}/brief/full")
    return {
        "assessmentId": aid,
        "runId": rid,
        "runStatus": info.get("status"),
        "trust": ws.get("trustScore"),
        "signals": len(ws.get("signals") or []),
        "evidence": len(ws.get("evidence") or ws.get("evidenceItems") or []),
        "decision": (ws.get("decision") or {}).get("recommendation"),
        "providerUsed": ws.get("providerUsed"),
        "providerLabel": ws.get("providerLabel"),
        "aiMode": ws.get("aiMode"),
        "reports": reports,
        "executiveSummaryHead": str(brief.get("executive_summary") or "")[:80] if isinstance(brief, dict) else str(st3),
    }


def run_scenario(name, disabled):
    org = f"Phase12 Validation {name} Ltd"
    status, ov = req("/api/v1/intelligence/providers/override", "POST",
                     {"reset": True})
    if disabled:
        status, ov = req("/api/v1/intelligence/providers/override", "POST",
                         {"disable": disabled})
    chain = ov.get("chain") if isinstance(ov, dict) else ov
    result = {"scenario": name, "disabled": disabled, "chain": chain}
    try:
        result.update(run_pipeline_multipart(org))
    except Exception as exc:
        result["error"] = str(exc)[:200]
    # Restore full chain for next scenario
    req("/api/v1/intelligence/providers/override", "POST", {"reset": True})
    st, status_after = req("/api/v1/intelligence/providers/status")
    result["lastProviderUsed"] = status_after.get("lastProviderUsed")
    result["lastFallbackCount"] = status_after.get("lastFallbackCount")
    return result


if __name__ == "__main__":
    out = []
    for name, disabled in SCENARIOS.items():
        out.append(run_scenario(name, disabled))
        with open(r"C:\temp\kulima_test\phase12_matrix.json", "w") as f:
            json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))
