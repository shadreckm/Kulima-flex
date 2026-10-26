"""Re-run intelligence on the existing pitch-deck assessment to validate the
entity-aware research + red-flag contract edits."""
import json
import time
import urllib.request as req

BASE = "http://127.0.0.1:8000"
TOKEN = open(r"C:\temp\kulima_test\token.txt").read().strip()
aid = json.load(open(r"C:\temp\kulima_test\kulima_africa_pitch_deck_test.json"))["assessmentId"]


def call(path, method="GET", data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = req.Request(BASE + path, method=method, data=body, headers={
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json",
    })
    return json.load(req.urlopen(r, timeout=120))


run = call(f"/api/v1/assessments/{aid}/start", "POST", {})
rid = run["runId"]
info = {}
for _ in range(80):
    time.sleep(3)
    info = call(f"/api/v1/intelligence/{rid}")
    if info.get("status") in ("completed", "failed"):
        break
print("run:", info.get("status"))
w = call(f"/api/v1/assessment-workspace/{aid}")
d = w.get("decision") or {}
print("decision:", {k: d.get(k) for k in ("recommendation", "overallScore", "entityBand", "entityRecommendation") if k in d})
print("research items:", len(w.get("research") or []))
b = call(f"/api/v1/intelligence/{rid}/brief/full")
rf = b.get("red_flags") or []
for flag in rf[:3]:
    print("redflag:", flag.get("severity"), "-", str(flag.get("title"))[:80], "|", str(flag.get("detail"))[:120])
print("sector:", b.get("sector"), "| geography:", b.get("geography"))
