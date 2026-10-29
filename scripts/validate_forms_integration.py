"""Google Forms / Collection Sources integration gate (Forms Integration V1).

Offline by design: every Google call is served by a stub client, so this gate
runs in CI, on a laptop, and on a deployment with no Google credentials. It
asserts the *contract* the pilot depends on:

  * the channel is off unless explicitly enabled, and declines honestly;
  * one sync batch becomes exactly one evidence document;
  * self-reported evidence cannot reach VERIFIED trust;
  * repeated syncs of one instrument cannot buy the corroboration bonus;
  * response data cannot be mistaken for extra documents in a report;
  * privacy: contact answers never reach the stored evidence file;
  * ordinary document uploads are byte-for-byte unaffected.

Writes to a throwaway SQLite database and removes the files it uploads.

    python scripts/validate_forms_integration.py

Exit code 0 with ``VERDICT: FORMS_INTEGRATION_PASS`` when every check holds.
``LIVE_VALIDATION_REQUIRED`` lines mark what only a real Google project can
confirm (OAuth consent, quota, and the exact response payload shape).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

if hasattr(sys.stdout, "reconfigure"):  # Windows console is cp437 by default
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP_DIR = tempfile.mkdtemp(prefix="kulima-forms-gate-")
DB_PATH = os.path.join(TMP_DIR, "forms_gate.db")

# ── Environment must be set before any kulima import (settings are read lazily)
os.environ["KULIMA_DB_PATH"] = DB_PATH
os.environ["KULIMA_FORMS_ENABLED"] = "true"
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "gate-client-id.apps.googleusercontent.com"
os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = "gate-client-secret"
os.environ["GOOGLE_OAUTH_REDIRECT_URI"] = "http://localhost:3000/api/v1/forms/oauth/callback"
os.environ["KULIMA_DOC_ENCRYPTION_KEY"] = "gate-storage-encryption-key"
os.environ["KULIMA_FORMS_MIN_BATCH_SIZE"] = "5"
# An offline gate must not start an intelligence run (no LLM credentials).
os.environ["KULIMA_FORMS_AUTO_RERUN"] = "false"
os.environ.setdefault("ENVIRONMENT", "development")

from fastapi import UploadFile  # noqa: E402
from starlette.datastructures import Headers  # noqa: E402

from backend.app.services import assessment_adapter, forms_adapter  # noqa: E402
from backend.app.services.document_adapter import UPLOAD_DIR  # noqa: E402
from kulima.core.assessment.models import AssessmentContext, AssessmentStatus, AssessmentType  # noqa: E402
from kulima.core.assessment.repository import AssessmentRepository  # noqa: E402
from kulima.core.documents.repository import DocumentRepository  # noqa: E402
from kulima.core.forms import client as forms_client  # noqa: E402
from kulima.core.forms import mapping as forms_mapping  # noqa: E402
from kulima.core.forms import normalizer as forms_normalizer  # noqa: E402
from kulima.core.forms.config import FormsConfig, extract_form_id, extract_sheet_id, get_forms_config  # noqa: E402
from kulima.core.forms.models import (  # noqa: E402
    CollectionPurpose,
    CollectedResponse,
    ConnectionStatus,
    EvidenceClass,
    FormConnection,
    LIVE_KINDS,
    SourceKind,
    SyncStatus,
)
from kulima.core.forms.repository import FormsRepository  # noqa: E402
from kulima.core.security.encryption import decrypt_bytes, is_encrypted  # noqa: E402
from kulima.intelligence.report_quality import (  # noqa: E402
    collection_accounting,
    collection_accounting_line,
    evidence_accounting,
    evidence_accounting_line,
    is_collection_evidence,
)
from kulima.models import TrustScoreBreakdown, UploadedEvidenceRecord  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []
LIVE: list[str] = []

_created_files: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}" + (f" :: {detail}" if detail else ""))
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}" + (f" :: {detail}" if detail else ""))
    return bool(condition)


def live(note: str) -> None:
    LIVE.append(note)
    print(f"  LIVE  {note}")


def upload_text(filename: str, text: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(text.encode("utf-8")),
        filename=filename,
        headers=Headers({"content-type": "text/plain"}),
    )


# ── Fixtures: the instrument Google would return ─────────────────────────────

FORM_ID = "1FAIpQLSfGateNGOFeedbackInstrument0000000000000"
SHEET_ID = "1GateResponseSheet0000000000000000000000000000"

FORM_RESOURCE = {
    "formId": FORM_ID,
    "info": {"title": "NGO Beneficiary Feedback - Mzimba", "documentTitle": "NGO Beneficiary Feedback"},
    "items": [
        {"itemId": "q1", "questionId": "101", "title": "Which district did you receive support in?", "required": True, "textQuestion": {}},
        {"itemId": "q2", "questionId": "102", "title": "How satisfied are you with the service?", "required": True,
         "linearScaleQuestion": {"range": {"start": 1, "end": 5}}},
        {"itemId": "q3", "questionId": "103", "title": "Did the food distribution and training improve your household?",
         "paragraphTextQuestion": {}},
        {"itemId": "q4", "questionId": "104", "title": "Which best describes you?", "required": True,
         "choiceQuestion": {"options": [{"value": "Beneficiary / community member"}, {"value": "Community leader"},
                                        {"value": "Staff member"}]}},
        {"itemId": "q5", "questionId": "105", "title": "Phone number for follow-up", "textQuestion": {}},
    ],
}

STATEMENTS = [
    "The food distribution reached our village but the training dates were announced too late for many households.",
    "My household income improved because the seeds and extension advice arrived before the planting season.",
    "The health camp was useful, however the clinic still runs out of medicine and the wait was four hours.",
    "Governance of the programme is unclear to us; we do not know who to complain to about the graft.",
    "Market access improved after the road repair, and the cooperative revenue was recorded honestly.",
    "The bursary payment was late and the reporting to the donor did not reflect our real situation.",
    "Water point rehabilitation helped, but the committee never receives the monitoring report they ask for.",
    "Training quality was good and the agronomist followed up, though the tools were insufficient.",
    "We trust the field officers, but the funding for next year is uncertain and staff are leaving.",
    "The climate information service reached us by radio and improved our planting decisions.",
]


def form_response(index: int, total: int) -> dict:
    """A Forms API v1 shaped response (answerSheet.answers as a list)."""
    return {
        "responseId": f"gate-response-{index:03d}",
        "submittedTime": (datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc) + timedelta(hours=index)).isoformat(),
        "answerSheet": {
            "answers": [
                {"questionId": "101", "textAnswers": {"answers": [{"value": "Mzimba"}]}},
                {"questionId": "102", "linearScaleAnswer": {"value": str(3 + (index % 3))}},
                {"questionId": "103", "textAnswers": {"answers": [{"value": STATEMENTS[index % len(STATEMENTS)]}]}},
                {"questionId": "104", "multipleChoiceAnswer": {"value": "Beneficiary / community member"}},
                {"questionId": "105", "textAnswers": {"answers": [{"value": f"+2659911000{index:02d}"}]}},
            ]
        },
    }


class StubClient:
    """Stands in for GoogleCollectionClient; no network is touched."""

    def __init__(self, responses: list[dict], *, sheet_rows: tuple[list[str], list[list[str]]] | None = None) -> None:
        self.responses = responses
        self._sheet_rows = sheet_rows or ([], [])

    def get_form(self, form_id: str) -> dict:
        return FORM_RESOURCE

    def iter_responses(self, form_id: str, *, page_size: int = 100, max_pages: int = 10) -> tuple[list[dict], str]:
        return list(self.responses), ""

    def sheet_rows(self, spreadsheet_id: str, range_name: str = "") -> tuple[list[str], list[list[str]]]:
        return self._sheet_rows


def stub_factory(client: StubClient):
    return lambda config, access_token: client


def stored_bytes(document_id: str) -> bytes:
    doc = DocumentRepository().get_document(document_id) or {}
    storage = doc.get("storagePath")
    if not storage:
        return b""
    target = UPLOAD_DIR / str(storage)
    _created_files.append(str(target))
    blob = target.read_bytes() if target.is_file() else b""
    if is_encrypted(doc.get("encryption")):
        return decrypt_bytes(blob)
    return blob


def connection_token(repo: FormsRepository, connection_id: str) -> None:
    """Pretend the OAuth round-trip completed (the gate never calls Google)."""
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    ok = repo.set_credentials(connection_id, {"access_token": "gate-access", "refresh_token": "gate-refresh", "expires_at": expires})
    if not ok:
        raise RuntimeError("gate could not store credentials - KULIMA_DOC_ENCRYPTION_KEY missing")


# ── Gate 1: configuration and the default-off switch ─────────────────────────


def gate_config() -> None:
    print("\n[1] Configuration, default-off, honest decline")
    off = FormsConfig(enabled=False, client_id="", client_secret="", redirect_uri="")
    check("channel is off by default in a bare config", not off.enabled and not off.configured)
    check("decline message names the missing secrets",
          "KULIMA_FORMS_ENABLED" in off.missing_required_secrets() and bool(off.degraded_message()))
    payload = off.status_payload()
    check("status payload is self-describing", payload["enabled"] is False and payload["message"])

    live_config = get_forms_config()
    check("gate environment reads as configured", live_config.enabled and live_config.configured)
    check("self-reported ceilings sit below VERIFIED",
          live_config.self_reported_source_ceiling <= 70.0 and live_config.self_reported_trust_ceiling < 80.0)
    check("form id parsed from a /forms/d/e/ URL", extract_form_id(f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform") == FORM_ID)
    check("sheet id parsed from a spreadsheets URL", extract_sheet_id(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit") == SHEET_ID)
    check("junk input yields no id", extract_form_id("not a form") == "" and extract_sheet_id("") == "")


# ── Gate 2: evidence model coexistence + entity awareness (Phases 3 & 6) ─────


def gate_models() -> None:
    print("\n[2] Evidence model and per-entity contracts")
    classes = {c.value for c in EvidenceClass}
    check("five evidence classes coexist",
          classes == {"document", "survey", "form", "operational", "community"}, ",".join(sorted(classes)))
    check("only document/form/sheet are live in V1", set(LIVE_KINDS) == {"document", "google_form", "google_sheet"})
    check("purposes are evidence and follow_up",
          {p.value for p in CollectionPurpose} == {"evidence", "follow_up"})

    entities = ["ngo", "development_program", "government_program", "tourism_sme", "startup"]
    contracts = [forms_mapping.collection_contract(e) for e in entities]
    check("every pilot entity resolves a contract", all(c.entity_type in entities for c in contracts))
    check("entities use the channel differently (distinct minimums)",
          len({c.minimum_responses for c in contracts}) >= 4,
          str({c.entity_type: c.minimum_responses for c in contracts}))
    check("respondent vocabularies differ per entity",
          len({c.respondent_types[0] for c in contracts}) >= 4)
    check("each contract states what the channel can never prove",
          all(len(c.honesty_caveat) > 40 for c in contracts))
    ngo = forms_mapping.entity_guidance("ngo")
    check("NGO guidance names the pilot report sections",
          "Institutional Capacity Review" in ngo["reportSections"], str(ngo["reportSections"]))
    check("unknown entity types fall back without failing", bool(forms_mapping.entity_guidance("cooperative")["entityLabel"]))


# ── Gate 3: normalisation, per-response trust, privacy (Phases 1 & 4) ────────


def gate_normalizer() -> None:
    print("\n[3] Normalization, per-response trust, privacy")
    questions = forms_mapping.questions_from_metadata(FORM_RESOURCE)
    check("instrument schema discovered with types",
          len({q.key for q in questions}) == 10 and any(q.question_type == "linear scale" for q in questions))
    collected = [
        CollectedResponse(
            response_id=raw["responseId"],
            submitted_at=forms_normalizer.parse_timestamp(raw["submittedTime"]),
            answers=forms_mapping.answers_from_form_response(raw, questions),
        )
        for raw in (form_response(i, 10) for i in range(10))
    ]
    annotated = forms_normalizer.annotate_responses(collected, questions)
    check("answerSheet list shape parsed", all(len(r.answers) >= 4 for r in annotated),
          str([len(r.answers) for r in annotated]))
    check("Phase 4 fields populated",
          all(r.completeness_pct > 0 and r.verification_status == "SELF_REPORTED" and r.respondent_type
              for r in annotated))
    check("respondent type detected from answers",
          annotated[0].respondent_type == "Beneficiary / community member", annotated[0].respondent_type)
    check("per-response trust capped at 79", all(10.0 <= r.trust_score <= 79.0 for r in annotated),
          f"max={max(r.trust_score for r in annotated)}")
    check("respondent reference is non-reversible", all(r.respondent_ref.startswith("anon-") for r in annotated))
    check("consistency is measured or declared, never invented",
          {r.consistency for r in annotated} <= {"CONSISTENT", "REVIEW", "NOT MEASURED"},
          str({r.consistency for r in annotated}))

    csv_bytes = forms_normalizer.to_csv_bytes(annotated, questions)
    text = csv_bytes.decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header = lines[0].split(",")
    check("one CSV row per response", len(lines) == len(annotated) + 1, f"{len(lines)} lines")
    check("fixed provenance columns lead the file",
          header[:8] == list(forms_normalizer.FIXED_COLUMNS), ",".join(header[:8]))
    check("contact answers redacted from evidence file",
          "[REDACTED - identifier]" in text.replace("\u2014", "-") and "+2659911000" not in text)
    digest = forms_normalizer.build_digest(
        FORM_RESOURCE["info"]["title"], annotated, source_kind=SourceKind.GOOGLE_FORM.value, purpose="evidence"
    )
    check("digest carries counts and respondent mix", digest.response_count == len(annotated) and digest.respondent_mix)
    check("digest states self-reported status and the corroboration rule",
          "SELF_REPORTED" in digest.text and "one source" in digest.text)
    check("digest quotes respondents verbatim", len(digest.verbatim_lines) >= 3)
    check("filename records the batch, not one file per response",
          forms_normalizer.batch_filename("NGO Feedback", 42).endswith("-42responses.csv"))


# ── Gate 4: trust-engine guards (Phase 4) ────────────────────────────────────


def gate_trust_guards() -> None:
    print("\n[4] Trust engine guards G1 / G2 (documents unchanged)")
    from backend.app.services.document_adapter import _calculate_trust_engine_scores

    text = (
        "Annual Report 2025. Audited financial statements attached. Programme reach 12,000 beneficiaries. "
        "Governance policy adopted. Revenue 4.2 MWK million. Independent audit by a registered firm. "
        "Cash position for nine months. Board minutes recorded."
    ) * 3
    baseline = _calculate_trust_engine_scores("annual_report.pdf", "annual_report", text, 6, None, 0)
    identical = _calculate_trust_engine_scores(
        "annual_report.pdf", "annual_report", text, 6, None, 0,
        source_ceiling=None, self_reported=False, duplicate_instrument_count=0,
    )
    check("ordinary document scoring is unchanged by the new parameters",
          baseline.final_trust_score == identical.final_trust_score and baseline.source_reliability == identical.source_reliability,
          f"{baseline.final_trust_score} vs {identical.final_trust_score}")

    csv_text = "kulima_response_id,submitted_at,respondent_type\n" + "\n".join(
        f"r{i},2026-10-01T09:00:00+00:00,Beneficiary / community member" for i in range(200)
    )
    plain = _calculate_trust_engine_scores("responses.csv", "data_export", csv_text, 4, None, 0)
    guarded = _calculate_trust_engine_scores(
        "responses.csv", "data_export", csv_text, 4, None, 0,
        source_ceiling=70.0, self_reported=True, duplicate_instrument_count=0,
    )
    capped = _calculate_trust_engine_scores(
        "responses.csv", "data_export", csv_text, 4, None, 1,
        source_ceiling=70.0, self_reported=True, duplicate_instrument_count=1,
    )
    check("G1 source reliability capped at the structured-data rung",
          guarded.source_reliability <= 70.0, f"{guarded.source_reliability}")
    check("G1 final trust cannot reach VERIFIED (80)",
          guarded.final_trust_score < 80.0, f"{guarded.final_trust_score}")
    check("G1 guard is explained in the rationale",
          "self-reported" in (guarded.rationale or "").lower() or "cap" in (guarded.rationale or "").lower(),
          (guarded.rationale or "")[:120])
    check("G2 repeat sync of one instrument does not add corroboration",
          capped.corroboration <= guarded.corroboration,
          f"{guarded.corroboration} -> {capped.corroboration}")
    check("an unguarded file of the same shape could score higher (guard is the difference)",
          plain.final_trust_score >= guarded.final_trust_score,
          f"plain={plain.final_trust_score} guarded={guarded.final_trust_score}")


# ── Gate 5: OAuth state + credential refusal (Phase 2) ───────────────────────


def gate_oauth() -> None:
    print("\n[5] OAuth state binding and credential safety")
    state = forms_adapter._sign_state({"cid": "c1", "org": "o1", "aid": "a1", "iat": datetime.now(timezone.utc).timestamp()})
    read = forms_adapter._read_state(state)
    check("signed state round-trips", read.get("cid") == "c1" and read.get("org") == "o1")

    tampered = state[:-4] + ("aaaa" if state[-4:] != "aaaa" else "bbbb")
    try:
        forms_adapter._read_state(tampered)
        check("tampered state rejected", False)
    except forms_client.FormsIntegrationError as exc:
        check("tampered state rejected", exc.code == "OAUTH_STATE_INVALID", exc.code)

    stale = forms_adapter._sign_state({"cid": "c1", "org": "o1", "aid": "a1", "iat": datetime.now(timezone.utc).timestamp() - 3600})
    try:
        forms_adapter._read_state(stale)
        check("expired state rejected", False)
    except forms_client.FormsIntegrationError as exc:
        check("expired state rejected", exc.code == "OAUTH_STATE_EXPIRED", exc.code)

    repo = FormsRepository()
    probe = FormConnection(id="gate-credential-probe", org_id="gate-org", assessment_id="gate-a")
    repo.save_connection(probe)
    key = os.environ.pop("KULIMA_DOC_ENCRYPTION_KEY", None)
    try:
        refused = repo.set_credentials(probe.id, {"access_token": "secret", "refresh_token": "secret-r"})
    finally:
        if key is not None:
            os.environ["KULIMA_DOC_ENCRYPTION_KEY"] = key
    check("credentials refused when storage cannot encrypt", refused is False)
    check("no plaintext token was persisted", repo.get_credentials(probe.id) == {})
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT credential_json FROM form_connections WHERE id = ?", (probe.id,)).fetchone()
    check("database row holds no clear-text secret", not (row and row[0] and "secret" in row[0]))

    errors = {
        401: "GOOGLE_UNAUTHENTICATED",
        403: "GOOGLE_FORBIDDEN",
        404: "FORM_NOT_FOUND",
        429: "GOOGLE_RATE_LIMITED",
    }
    ok = True
    for status, code in errors.items():
        got_code, _msg, got_status = forms_client._map_error(status, {})
        ok = ok and got_code == code and got_status == status
    check("Google errors map to stable codes (never a fake success)", ok)


# ── Gate 6: end-to-end through the existing pipeline ─────────────────────────


def gate_pipeline() -> None:
    print("\n[6] End-to-end: form responses become evidence (documents coexist)")
    proposal = (
        "AgriNova Community Trust Annual Report 2025\n"
        "Audited financial statements: revenue 480000 MWK, programme spend 361000 MWK.\n"
        "Governance: board of nine, adopted safeguarding policy, independent audit completed.\n"
        "Programme: food distribution and farming training for 12000 beneficiaries in Mzimba.\n"
        "M&E: quarterly monitoring reports submitted to the district officer.\n"
    )
    created = assessment_adapter.create_assessment(
        [upload_text("ngo_annual_report.txt", proposal)],
        "ngo",
        "gate-user",
        org_id="gate-org",
        entity_name="AgriNova Community Trust",
        country="Malawi",
    )
    assessment_id = str(created["assessmentId"])
    doc_count_before = len(assessment_adapter._repo.get(assessment_id, org_id="gate-org").document_ids)
    check("primary document attached first", doc_count_before == 1, f"{doc_count_before} document(s)")

    made = forms_adapter.create_connection(
        org_id="gate-org",
        user_id="gate-user",
        assessment_id=assessment_id,
        form_url=f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform",
        purpose="evidence",
        request_origin="http://localhost:8000",
    )
    conn = made["connection"]
    repo = FormsRepository()
    check("connection created as pending_auth (nothing claimed yet)",
          conn["status"] == ConnectionStatus.PENDING_AUTH.value)
    check("consent URL is a Google authorise URL with offline consent",
          made["authorizeUrl"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
          and "access_type=offline" in made["authorizeUrl"] and "prompt=consent" in made["authorizeUrl"])
    check("entity guidance returned for the connected entity",
          made["guidance"]["entityType"] == "ngo", str(made["guidance"]["entityType"]))

    connection_id = conn["id"]
    client = StubClient([form_response(i, 6) for i in range(6)])
    connection_token(repo, connection_id)
    check("connection token stored for the gate", bool(repo.get_credentials(connection_id).get("refresh_token")))

    first = forms_adapter.sync_connection(
        connection_id, org_id="gate-org", user_id="gate-user", reason="manual", client_factory=stub_factory(client)
    )
    check("first sync materialises one batch", first["status"] == SyncStatus.MATERIALISED.value, str(first.get("message", "")[:80]))
    check("batch reports the response count", first["responseCount"] == 6, str(first["responseCount"]))
    ctx = assessment_adapter._repo.get(assessment_id, org_id="gate-org")
    docs = ctx.document_ids
    check("exactly one document attached for six responses", len(docs) == doc_count_before + 1,
          f"{len(docs)} total")
    collection_doc_id = str(first["documentId"])
    batch_rows = repo.list_batches("gate-org", assessment_id)
    check("batch recorded with its document", len(batch_rows) == 1 and batch_rows[0]["documentId"] == collection_doc_id)

    row = DocumentRepository().get_document(collection_doc_id) or {}
    payload_text = json.dumps(row.get("metadata") or {})
    check("document row is typed as a collection channel, not a plain upload",
          row.get("sourceType") == SourceKind.GOOGLE_FORM.value, str(row.get("sourceType")))
    check("provenance recorded in document metadata",
          "Collection Pipeline" in payload_text and connection_id in payload_text)

    bridged = next((d for d in ctx.uploaded_documents if str(d.id) == collection_doc_id), None)
    check("batch filename records the response count",
          bridged is not None and "responses.csv" in str(getattr(bridged, "name", "")),
          str(getattr(bridged, "name", "")))
    check("self-reported batch cannot reach VERIFIED trust",
          bridged is not None and (bridged.trust_score or 0.0) < 80.0,
          f"trust={getattr(bridged, 'trust_score', None)}")
    check("batch evidence status is not VERIFIED",
          str(getattr(bridged, "evidence_status", "")) != "VERIFIED",
          str(getattr(bridged, "evidence_status", "")))
    check("digest reaches the evidence summary the signals layer reads",
          bridged is not None and (bridged.raw_summary or "").startswith("Collection batch"),
          (bridged.raw_summary or "")[:40])

    csv_text = stored_bytes(collection_doc_id).decode("utf-8", "replace")
    check("stored file is a response matrix, not a narrative",
          "kulima_response_id" in csv_text and csv_text.count("\n") >= 6)
    check("no respondent phone number in the stored evidence file", "+2659911000" not in csv_text)

    again = forms_adapter.sync_connection(
        connection_id, org_id="gate-org", user_id="gate-user", reason="manual", client_factory=stub_factory(client)
    )
    check("re-sync of identical responses is a no-op", again["status"] == SyncStatus.NO_NEW_RESPONSES.value,
          f"new={again['newResponses']}")
    ctx_after = assessment_adapter._repo.get(assessment_id, org_id="gate-org")
    check("no duplicate document was attached", len(ctx_after.document_ids) == len(docs))

    grew = StubClient([form_response(i, 6) for i in range(6)] + [form_response(i, 9) for i in range(6, 9)])
    partial = forms_adapter.sync_connection(
        connection_id, org_id="gate-org", user_id="gate-user", reason="manual", client_factory=stub_factory(grew)
    )
    check("3 new responses below the batch minimum decline honestly",
          partial["status"] == SyncStatus.PENDING_BELOW_MINIMUM.value and partial["pendingCount"] == 3,
          str(partial.get("message", "")[:70]))
    check("declined batch attached no document",
          len(assessment_adapter._repo.get(assessment_id, org_id="gate-org").document_ids) == len(docs))

    ripe = StubClient([form_response(i, 10) for i in range(11)])
    second = forms_adapter.sync_connection(
        connection_id, org_id="gate-org", user_id="gate-user", reason="manual", client_factory=stub_factory(ripe)
    )
    check("second batch attaches once the minimum is reached",
          second["status"] == SyncStatus.MATERIALISED.value and second["responseCount"] == 5,
          f"count={second['responseCount']}")
    two_batches = repo.list_batches("gate-org", assessment_id)
    check("two batches now recorded", len(two_batches) == 2, str(len(two_batches)))
    second_doc = assessment_adapter._repo.get(assessment_id, org_id="gate-org")
    second_record = next((d for d in second_doc.uploaded_documents if str(d.id) == str(second["documentId"])), None)
    check("second batch of the same instrument is still capped below VERIFIED",
          second_record is not None and (second_record.trust_score or 0.0) < 80.0,
          f"trust={getattr(second_record, 'trust_score', None)}")
    check("below-recommended-minimum is reported, not hidden",
          "belowRecommendedMinimum" in second and isinstance(second["belowRecommendedMinimum"], bool))

    # Primary-document guard: a brand new context with no documents at all.
    bare = AssessmentContext(
        assessment_id="gate-bare-assessment",
        assessment_type=AssessmentType.NGO,
        status=AssessmentStatus.INTAKE,
        created_by="gate-user",
    )
    AssessmentRepository().save(bare, org_id="gate-org")
    bare_conn = forms_adapter.create_connection(
        org_id="gate-org", user_id="gate-user", assessment_id=bare.assessment_id,
        form_url=f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform", purpose="evidence",
    )["connection"]
    FormsRepository().set_credentials(bare_conn["id"], {
        "access_token": "gate-access", "refresh_token": "gate-refresh",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    })
    declined = forms_adapter.sync_connection(
        bare_conn["id"], org_id="gate-org", user_id="gate-user", reason="manual",
        client_factory=stub_factory(StubClient([form_response(i, 10) for i in range(11)])),
    )
    check("a form can never be the only evidence (primary-document guard)",
          declined.get("code") == "COLLECTION_REQUIRES_PRIMARY_DOCUMENT", str(declined.get("status")))
    check("guard attaches no document and records no batch",
          len(AssessmentRepository().get(bare.assessment_id, org_id="gate-org").document_ids) == 0
          and repo.list_batches("gate-org", bare.assessment_id) == [])
    check("guard responses are still retained for the next sync", declined["pendingCount"] >= 5)

    # Sheets connector path.
    sheet_conn = forms_adapter.create_connection(
        org_id="gate-org", user_id="gate-user", assessment_id=assessment_id,
        sheet_url=f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit", purpose="follow_up",
    )["connection"]
    FormsRepository().set_credentials(sheet_conn["id"], {
        "access_token": "gate-access", "refresh_token": "gate-refresh",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    })
    headers = ["Timestamp", "Which district did you receive support in?", "How satisfied are you with the service?",
               "Did the programme improve your household?", "Which best describes you?", "Phone number"]
    rows = [
        ["2026-10-05T08:00:00Z", "Mzimba", "4", "Food distribution reached us but training was announced late",
         "Beneficiary / community member", "+265992200001"],
        ["2026-10-05T09:00:00Z", "Mzimba", "5", "The clinic stock-outs are the main problem for our household",
         "Community leader", "+265992200002"],
        ["2026-10-06T08:00:00Z", "Nkhotakota", "3", "Revenue improved after the road repair, reporting is honest",
         "Staff member", "+265992200003"],
        ["2026-10-06T09:00:00Z", "Nkhotakota", "4", "Water point rehabilitation helped the community",
         "Beneficiary / community member", "+265992200004"],
        ["2026-10-07T08:00:00Z", "Mzimba", "2", "Governance is unclear and the funding is uncertain",
         "Partner organisation", "+265992200005"],
        ["2026-10-07T09:00:00Z", "Dedza", "5", "Climate information by radio improved our planting decisions",
         "Customer", "+265992200006"],
    ]
    sheet = forms_adapter.sync_connection(
        sheet_conn["id"], org_id="gate-org", user_id="gate-user", reason="manual",
        client_factory=stub_factory(StubClient([], sheet_rows=(headers, rows))),
    )
    check("Sheets connector path materialises a batch too",
          sheet["status"] == SyncStatus.MATERIALISED.value and sheet["kind"] == SourceKind.GOOGLE_SHEET.value,
          str(sheet.get("status")))
    sheet_doc = str(sheet["documentId"])
    sheet_csv = stored_bytes(sheet_doc).decode("utf-8", "replace")
    check("sheet batch redacts identifiers as well", "+2659922000" not in sheet_csv)
    check("follow_up purpose does not re-run the decision",
          str(sheet.get("runStatus") or "") == "not_retriggered", str(sheet.get("runStatus")))

    listed = forms_adapter.list_connections(org_id="gate-org", assessment_id=assessment_id)
    check("channel list reports connections and batches",
          len(listed["connections"]) >= 2 and len(listed["batches"]) >= 3)
    revoked = forms_adapter.disconnect(connection_id=sheet_conn["id"], org_id="gate-org", user_id="gate-user")
    check("disconnect revokes credentials and keeps evidence",
          revoked["revoked"] is True and len(assessment_adapter._repo.get(assessment_id, org_id="gate-org").document_ids) >= 3)

    return assessment_id, collection_doc_id


# ── Gate 7: reporting and accounting (Phase 7) ───────────────────────────────


def gate_reporting(assessment_id: str, collection_doc_id: str) -> None:
    print("\n[7] Reports: documents and form evidence reported separately")
    collection = UploadedEvidenceRecord(
        id=collection_doc_id,
        filename="ngo-beneficiary-feedback-20261028-0710-6responses.csv",
        source="Google Form Collection Pipeline (ngo-beneficiary-feedback.csv) \u00b7 6 responses \u00b7 self-reported",
        upload_date="2026-10-28T07:10:00+00:00",
        file_type="CSV",
        uploader="gate-user",
        trust_breakdown=TrustScoreBreakdown(final_trust_score=79.0, source_reliability=70.0),
        evidence_status="CORROBORATED",
        raw_summary="Collection batch: NGO Beneficiary Feedback",
    )
    doc_a = UploadedEvidenceRecord(
        id="doc-a", filename="annual_report.pdf", source="Document Ingestion Pipeline (annual_report.pdf)",
        upload_date="2026-10-01T00:00:00+00:00", file_type="TXT", uploader="gate-user",
        trust_breakdown=TrustScoreBreakdown(),
    )
    doc_b = UploadedEvidenceRecord(
        id="doc-b", filename="budget.xlsx", source="Document Ingestion Pipeline (budget.xlsx)",
        upload_date="2026-10-01T00:00:00+00:00", file_type="XLSX", uploader="gate-user",
        trust_breakdown=TrustScoreBreakdown(),
    )
    brief = SimpleNamespace(uploaded_evidence=[doc_a, doc_b, collection], sources=[], evidence_integrity=None)

    acc = collection_accounting(brief)
    check("collection evidence detected by provenance",
          acc["collection_evidence_count"] == 1 and acc["document_evidence_count"] == 2, str(acc))
    check("responses counted separately from records", acc["collection_response_count"] == 6, str(acc))
    check("is_collection_evidence ignores document records",
          not is_collection_evidence(doc_a) and is_collection_evidence(collection))

    line = collection_accounting_line(brief)
    check("collection line reconciles the attached-record total",
          "3 attached evidence record(s) = 2 uploaded document(s) + 1 collection batch" in line, line[:120])
    check("collection line declares self-reported status", "self-reported" in line and "verified" in line.lower())

    combined = evidence_accounting_line(brief)
    check("evidence line still reports document counts and appends collection",
          "Uploaded documents: 3" in combined and "\nEvidence origin:" in combined, combined.splitlines()[0][:90])

    doc_only = SimpleNamespace(uploaded_evidence=[doc_a, doc_b], sources=[], evidence_integrity=None)
    check("document-only reports are unchanged",
          collection_accounting_line(doc_only) == ""
          and "\n" not in evidence_accounting_line(doc_only)
          and evidence_accounting(doc_only)["document_count"] == 2)

    audit_kinds = _audit_event_types()
    check("collection events are first-class audit events",
          {"collection.connected", "collection.synced", "collection.batch_materialised",
           "collection.sync_failed", "collection.disconnected"} <= audit_kinds,
          str(sorted(a for a in audit_kinds if a.startswith("collection."))))


def _audit_event_types() -> set[str]:
    from kulima.core.audit.repository import EVENT_TYPES

    return set(EVENT_TYPES)


# ── Gate 8: durable queue + baseline regression ──────────────────────────────


def gate_queue_and_baseline() -> None:
    print("\n[8] Durable sync job and pipeline baseline")
    from kulima.core.jobs.models import JobKind
    from kulima.core.jobs import runner as jobs_runner

    check("FORM_SYNC exists on the durable queue", JobKind.FORM_SYNC.value == "form_sync")
    source = open(jobs_runner.__file__, encoding="utf-8").read()
    check("runner dispatches FORM_SYNC to the connector",
          "JobKind.FORM_SYNC" in source and "_execute_form_sync_job" in source)
    check("a dead sync job cannot fail a completed assessment (payload key is not assessment_id)",
          "target_assessment_id" in source)
    check("failure propagation still keys only on run_id / assessment_id",
          'payload.get("run_id")' in source.split("async def _execute_job")[0]
          and 'payload.get("assessment_id")' in source.split("async def _execute_job")[0])

    queued = forms_adapter.enqueue_sync(_gate_state["connection_id"], org_id="gate-org", user_id="gate-user", delay_minutes=30)
    check("sync can be queued on the durable runner", queued.get("queued") is True, str(queued)[:80])

    # The scheduler marks a *dead* job's originating run/assessment as failed by
    # reading payload["run_id"] and payload["assessment_id"]. A sync job therefore
    # stores its target under a different key, and its case_id is a synthetic
    # collection scope no assessment row can match, so a failed sync can never
    # retroactively mark a completed assessment as FAILED.
    from kulima.core.jobs.repository import JobRepository

    stored = JobRepository().get(str(queued.get("jobId") or ""))
    sync_payload = dict(stored.payload or {}) if stored else {}
    check("a queued sync job carries no key the dead-job propagator would act on",
          stored is not None
          and "assessment_id" not in sync_payload
          and "run_id" not in sync_payload
          and bool(sync_payload.get("target_assessment_id"))
          and str(getattr(stored, "case_id", "") or "").startswith("collection:"),
          f"keys={sorted(sync_payload)} case_id={getattr(stored, 'case_id', '')!r}")
    dupe = forms_adapter.enqueue_sync(_gate_state["connection_id"], org_id="gate-org", user_id="gate-user", delay_minutes=30)
    check("duplicate queue request is de-duplicated, not doubled",
          dupe.get("queued") is False and dupe.get("deduplicated") is True, str(dupe)[:80])

    disabled = dict(os.environ)
    os.environ["KULIMA_FORMS_ENABLED"] = "false"
    try:
        try:
            forms_adapter.sync_connection(_gate_state["connection_id"], org_id="gate-org")
            check("switched-off channel refuses to sync", False)
        except forms_client.FormsIntegrationError as exc:
            check("switched-off channel refuses to sync", exc.code in {"FORMS_DISABLED", "FORMS_NOT_CONFIGURED"}, exc.code)
    finally:
        os.environ.clear()
        os.environ.update(disabled)

    live("Google OAuth consent, Forms/Sheets API enablement, quota and the live response payload "
         "shape can only be confirmed with a real Google Cloud project (GOOGLE_FORMS_LIVE_VALIDATION).")
    live("Forms API server-side response filtering was not verified against a live project, so the "
         "connector pages and de-duplicates locally (bounded by KULIMA_FORMS_MAX_PAGES / MAX_RESPONSES).")


# ── Runner ───────────────────────────────────────────────────────────────────

_gate_state: dict = {}


def main() -> int:
    print("=" * 78)
    print("KULIMA FLEX - Google Forms / Collection Sources integration gate")
    print("=" * 78)
    print("database:", DB_PATH)
    try:
        gate_config()
        gate_models()
        gate_normalizer()
        gate_trust_guards()
        gate_oauth()
        assessment_id, collection_doc_id = gate_pipeline()
        _gate_state["assessment_id"] = assessment_id
        gate_reporting(assessment_id, collection_doc_id)
        repo = FormsRepository()
        conns = repo.list_connections("gate-org", assessment_id)
        _gate_state["connection_id"] = next(
            (c.id for c in conns if c.kind == SourceKind.GOOGLE_FORM.value and c.status != ConnectionStatus.REVOKED.value),
            conns[0].id if conns else "none",
        )
        gate_queue_and_baseline()
    except Exception as exc:  # noqa: BLE001 — a gate must report, not traceback silently
        import traceback

        FAILED.append(f"unhandled exception: {exc}")
        print("\nUNHANDLED EXCEPTION in gate:")
        traceback.print_exc()
    finally:
        for path in _created_files:
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    print("\n" + "=" * 78)
    print(f"checks passed : {len(PASSED)}")
    print(f"checks failed : {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    for note in LIVE:
        print(f"  LIVE_VALIDATION_REQUIRED: {note[:100]}")
    verdict = "FORMS_INTEGRATION_PASS" if not FAILED and PASSED else "FORMS_INTEGRATION_BLOCKED"
    print(f"VERDICT: {verdict}")
    print("=" * 78)
    return 0 if verdict == "FORMS_INTEGRATION_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
