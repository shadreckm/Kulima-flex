"""Phase 8 validation: run all 5 assessment types through the full chain
with OpenAI and Tavily disabled (backend started with empty keys)."""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()
DOC = r"C:\temp\kulima_test\small_1mb.txt"

TYPES = {
    "startup": ("Solar Startup Ltd", "Nairobi"),
    "ngo": ("Clean Water NGO", "Malawi"),
    "tourism_sme": ("Safari Lodge SME", "Tanzania"),
    "development_program": ("Rural Development Program", "Uganda"),
    "government_program": ("Ministry Energy Program", "Kenya"),
}

def req(path, method="GET", data=None, headers=None, raw=False):
    r = urllib.request.Request(BASE + path, method=method, data=data)
    r.add_header("Authorization", f"Bearer {TOKEN}")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    with urllib.request.urlopen(r, timeout=120) as resp:
        body = resp.read()
    if raw:
        return resp.status, body
    return resp.status, json.loads(body or b"{}")

results = []
for atype, (org, country) in TYPES.items():
    # multipart upload
    boundary = "----kulimavalidation"
    with open(DOC, "rb") as f:
        fbytes = f.read()
    parts = []
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="brief.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n".encode()
        + f"Organization Name: {org}\nFounder: Ms. Test Lead\nLocations: {country}\nBudget: USD 500,000\nActivities: training, outreach\nObjectives: expand coverage\nOutcomes: 2000 beneficiaries\nRisks: drought, currency\nJanuary 2026\n".encode()
        + fbytes
        + b"\r\n"
    )
    for field, value in [
        ("assessmentType", atype),
        ("organizationName", org),
        ("founderName", "Ms. Test Lead"),
        ("keywords", "Climate,Test"),
    ]:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    status, created = req(
        "/api/v1/assessments/",
        "POST",
        body,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    aid = created["assessmentId"]
    ctx_conf = created.get("confidence")

    status, run = req(f"/api/v1/assessments/{aid}/start", "POST")
    rid = run["runId"]

    # poll for completion
    final_status = "running"
    for _ in range(40):
        time.sleep(2)
        status, info = req(f"/api/v1/intelligence/{rid}")
        final_status = info.get("status")
        if final_status in ("completed", "failed"):
            break

    status, ws = req(f"/api/v1/assessment-workspace/{aid}")
    sig_count = len(ws.get("signals") or [])
    research = ws.get("research") or {}
    decision = ws.get("decision") or {}
    status, brief = req(f"/api/v1/intelligence/{rid}/brief/full")
    exec_summary = str((brief.get("executive_summary") or "")[:120])
    demo_terms = [t for t in ("AgriNova", "OSTX", "Demo Mode") if t in exec_summary]
    status, memo = req(f"/api/v1/intelligence/{rid}/reports/memo", raw=True)

    results.append({
        "type": atype,
        "runStatus": final_status,
        "signals": sig_count,
        "trust": ws.get("trustScore"),
        "researchSources": len(research.get("sources") or []),
        "researchMode": research.get("mode") or "document_intelligence",
        "aiMode": ws.get("aiMode"),
        "decision": decision.get("recommendation"),
        "execHead": exec_summary[:80],
        "demoTerms": demo_terms,
        "memoBytes": len(memo),
    })

print(json.dumps(results, indent=2))
