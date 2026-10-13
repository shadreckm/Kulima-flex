"""Pilot UX validation: signals render path against the live backend.

Creates an assessment from a real upload, waits for the run to complete, then
calls the exact endpoints the Signals page / ContextPanel consume
(/intelligence/{run}/signals) and verifies signals + decision are served —
no "Analysis in progress" dead state.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mint_token import main as mint  # noqa: E402

token = mint()
BASE = os.environ.get("KULIMA_TEST_BACKEND_URL", "http://127.0.0.1:8000")


def api(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"raw": raw[:200]}


def make_pdf(path: str) -> None:
    """Minimal but real PDF with extractable business-plan text."""
    text = (
        "Kulima Africa Business Plan 2026\\n"
        "Executive Summary\\n"
        "Kulima Africa is an agri-fintech startup in Nairobi connecting 12,000 "
        "smallholder farmers to urban markets through a mobile platform.\\n"
        "Business Model: commission-based revenue, 8% of transaction value.\\n"
        "Market: Kenya agricultural market TAM $4.2B.\\n"
        "Funding Ask: $750,000 seed round for 18-month runway.\\n"
        "Customer Discovery: 3 county pilots, 450 farmers onboarded.\\n"
    )
    stream = (
        "1 0 obj\\n<< /Type /Catalog /Pages 2 0 R >>\\nendobj\\n"
        "2 0 obj\\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\\nendobj\\n"
        "3 0 obj\\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\\nendobj\\n"
        "4 0 obj\\n<< /Length " + str(len(text)) + " >>\\nstream\\n"
        "BT /F1 10 Tf 50 750 Td (" + text.replace("\\n", ") Tj T* (") + ") Tj ET\\n"
        "endstream\\nendobj\\n"
        "5 0 obj\\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\\nendobj\\n"
        "trailer\\n<< /Root 1 0 R >>\\n"
    ).encode("latin-1", "replace")
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4\\n")
        f.write(stream)


if __name__ == "__main__":
    # 1. Create assessment from an uploaded business plan (direct backend).
    pdf_path = os.path.join(os.environ.get("TEMP", "/tmp"), "kulima_africa_business_plan.pdf")
    make_pdf(pdf_path)
    boundary = "----kulima-e2e"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="Kulima_Africa_Business_Plan.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="assessmentType"\r\n\r\nstartup\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="entityName"\r\n\r\nKulima Africa\r\n'
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/assessments/",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read().decode())
    assessment_id = payload["assessmentId"]
    run_id = payload.get("runId")
    print("assessment:", assessment_id[:8], "| status:", payload.get("status"), "| runId:", str(run_id)[:8])
    assert payload.get("status") in ("intake", "ready", "running", "complete", "needs_confirmation")

    # 2. If extraction confidence was low, confirm the entity once (the exact
    # PATCH the intake page issues), then start the run.
    if payload.get("status") == "needs_confirmation":
        st, patched = api(f"/api/v1/assessments/{assessment_id}", method="PATCH", body={"entityName": "Kulima Africa"})
        print("confirm entity ->", st, "| status:", (patched or {}).get("status"))

    # 2. Start the run if the upload didn't auto-start one.
    if not run_id:
        status, started = api(f"/api/v1/assessments/{assessment_id}/start", method="POST")
        print("start run ->", status, "| runId:", str(started.get("runId"))[:8])
        run_id = started.get("runId")
    assert run_id, "run did not start"

    # 3. Poll run status until complete (the same flow the frontend uses).
    final_status = None
    for _ in range(90):
        st, info = api(f"/api/v1/intelligence/{run_id}")
        final_status = (info or {}).get("status")
        if final_status in ("completed", "complete", "failed"):
            break
        time.sleep(5)
    print("run final status:", final_status)
    assert final_status in ("completed", "complete"), f"run did not complete: {final_status}"

    # 4. Signals endpoint — the exact call the Signals page makes.
    st, signals = api(f"/api/v1/intelligence/{run_id}/signals")
    print("signals endpoint ->", st,
          "| critical:", signals.get("critical"),
          "| high:", signals.get("high"),
          "| medium:", signals.get("medium"),
          "| low:", signals.get("low"))
    doms = signals.get("domains") or {}
    # The API DTO exposes 'count' per domain (the frontend reads count).
    populated = [k for k, v in doms.items() if isinstance(v, dict) and (v.get("count", 0) or len(v.get("signals") or [])) > 0]
    print("populated domains:", populated)
    assert st == 200 and len(populated) >= 5, "signals not populated"

    # 5. Decision endpoint.
    st, decision = api(f"/api/v1/intelligence/{run_id}/brief")
    print("decision endpoint ->", st, "| verdict:", decision.get("verdict"),
          "| score:", decision.get("decisionScore"))
    assert st == 200 and decision.get("verdict"), "decision missing"

    # 6. Ask IC endpoint (AI Analyst) — must return an answer, not an error.
    st, ans = api("/api/v1/ask/ic", method="POST", body={"runId": str(run_id), "question": "What evidence supports this assessment?"})
    answer = (ans or {}).get("answer") or (ans or {}).get("response") or ""
    print("ask-ic endpoint ->", st, "| answer head:", str(answer)[:110])
    assert st == 200 and answer, "ask IC failed"

    print("E2E_WORKFLOW_OK — assessment, signals, decision, ask-ic all serve data")
