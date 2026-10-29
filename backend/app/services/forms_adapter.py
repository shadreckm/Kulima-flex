"""Collection channel service — Google Forms / Sheets → evidence (Forms V1).

This module is the connector layer of the design: it owns OAuth, response
ingestion, normalisation and the *materialisation* of one collected batch into
the existing evidence pipeline. It deliberately owns no scoring, no signal
logic and no report logic. A channel is an ingress, not a pipeline.

The single sink is ``assessment_adapter.attach_documents`` → ``save_uploaded_file``
→ ``UploadedEvidenceRecord`` → orchestrator bridge → ``InvestmentBrief``. Because
of that, documents and forms coexist in one evidence plane and every downstream
stage (Trust, Signals, Decisions, Reports, Outcomes) is consumed unchanged.

Guards enforced here, in the order the design specifies:

* ``COLLECTION_REQUIRES_PRIMARY_DOCUMENT`` — a form cannot be the only evidence
  in an assessment. Response text is influential enough to shift entity
  classification, so at least one uploaded document must already be attached.
* One batch = one document, never one document per response (the document trust
  engine grants corroboration by document count).
* ``duplicate_instrument_count`` (G2) so repeated syncs of the same instrument do
  not buy the multi-source corroboration bonus.
* ``self_reported`` + ``source_ceiling`` (G1) so volume cannot lift a batch to
  ``VERIFIED``.
* Nothing is fabricated: every decline path returns an honest status instead of
  an empty success.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, Sequence

from fastapi import UploadFile
from starlette.datastructures import Headers

from kulima.core.audit import record_event
from kulima.core.forms.client import (
    FormsIntegrationError,
    GoogleCollectionClient,
    build_authorization_url,
    exchange_code,
    refresh_access_token,
    token_is_fresh,
)
from kulima.core.forms.config import FormsConfig, extract_form_id, extract_sheet_id, get_forms_config
from kulima.core.forms.mapping import (
    answers_from_form_response,
    answers_from_sheet_row,
    collection_contract,
    entity_guidance,
    questions_from_metadata,
    schema_hash as compute_schema_hash,
)
from kulima.core.forms.models import (
    CollectionBatch,
    CollectedResponse,
    ConnectionStatus,
    FormConnection,
    FormQuestion,
    SOURCE_KIND_LABELS,
    SyncStatus,
)
from kulima.core.forms.normalizer import (
    annotate_responses,
    batch_filename,
    build_digest,
    parse_timestamp,
    to_csv_bytes,
)
from kulima.core.forms.repository import FormsRepository, get_repo

from . import assessment_adapter

logger = logging.getLogger(__name__)

CALLBACK_PATH = "/api/v1/forms/oauth/callback"
STATE_TTL_SECONDS = 15 * 60

#: Per-process key: an OAuth round-trip spans seconds, so an in-memory key is
#: acceptable, and it fails closed (state rejected) rather than silently
#: accepting a forged callback after a restart.
_EPHEMERAL_STATE_KEY = secrets.token_bytes(32)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _repo() -> FormsRepository:
    return get_repo()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _state_secret() -> bytes:
    for name in ("KULIMA_FORMS_STATE_SECRET", "KULIMA_DOC_ENCRYPTION_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value.encode("utf-8")
    return _EPHEMERAL_STATE_KEY


def _sign_state(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, default=str).encode("utf-8")).decode("ascii")
    sig = hmac.new(_state_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def _state_signature(body: str) -> str:
    return hmac.new(_state_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]


def _read_state(state: str) -> dict[str, Any]:
    """Verify the signed OAuth state. Raises instead of proceeding on doubt."""
    body, _, sig = (state or "").rpartition(".")
    if not body or not sig:
        raise FormsIntegrationError("OAUTH_STATE_INVALID", "Missing OAuth state — restart the connection.", 400)
    if not hmac.compare_digest(_state_signature(body), sig):
        raise FormsIntegrationError(
            "OAUTH_STATE_INVALID",
            "The OAuth state did not match this server (the connection flow may have been restarted). "
            "Please begin the authorisation again.",
            400,
        )
    try:
        payload = json.loads(base64.urlsafe_b64decode(body.encode("ascii")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise FormsIntegrationError("OAUTH_STATE_INVALID", "The OAuth state could not be decoded. Begin again.", 400) from exc
    if not isinstance(payload, dict):
        raise FormsIntegrationError("OAUTH_STATE_INVALID", "Malformed OAuth state. Begin the authorisation again.", 400)
    try:
        issued = float(payload.get("iat") or 0)
    except (TypeError, ValueError):
        issued = 0.0
    if issued and (time.time() - issued) > STATE_TTL_SECONDS:
        raise FormsIntegrationError(
            "OAUTH_STATE_EXPIRED", "The authorisation request expired. Please begin the connection again.", 400
        )
    return payload


def _redirect_uri(config: FormsConfig, request_origin: str) -> str:
    """Google requires an exact match with a registered redirect URI."""
    if config.redirect_uri:
        return config.redirect_uri
    origin = (request_origin or "").rstrip("/")
    if not origin:
        raise FormsIntegrationError(
            "REDIRECT_URI_NOT_CONFIGURED",
            "Set GOOGLE_OAUTH_REDIRECT_URI to the registered callback URL for this deployment.",
            503,
        )
    return f"{origin}{CALLBACK_PATH}"


def _return_base() -> str:
    return os.getenv("KULIMA_FORMS_RETURN_URL", "").strip().rstrip("/")


def _require_enabled(config: FormsConfig) -> None:
    if not config.enabled:
        raise FormsIntegrationError("FORMS_DISABLED", config.degraded_message(), 503)
    if not config.configured:
        raise FormsIntegrationError("FORMS_NOT_CONFIGURED", config.degraded_message(), 503)


def _conn_payload(conn: FormConnection) -> dict[str, Any]:
    return {
        "id": conn.id,
        "assessmentId": conn.assessment_id,
        "kind": conn.kind,
        "kindLabel": SOURCE_KIND_LABELS.get(conn.kind, conn.kind),
        "formId": conn.form_id,
        "sheetId": conn.sheet_id,
        "sheetRange": conn.sheet_range,
        "title": conn.title,
        "purpose": conn.purpose,
        "status": conn.status,
        "evidenceClass": conn.evidence_class,
        "questionCount": len(conn.questions),
        "schemaHash": conn.schema_hash,
        "totalResponses": conn.total_responses,
        "pendingResponses": conn.pending_responses,
        "batchCount": conn.batch_count,
        "lastSyncedAt": conn.last_synced_at,
        "lastError": conn.last_error,
        "note": conn.note,
        "createdAt": _iso(conn.created_at),
    }


def _entity_key(assessment_id: str, org_id: Optional[str], user_id: Optional[str]) -> tuple[str, Any]:
    """Return (entity_type, context) for the target assessment."""
    ctx = assessment_adapter._repo.get(assessment_id, user_id=user_id, org_id=org_id)
    if ctx is None:
        raise FormsIntegrationError("ASSESSMENT_NOT_FOUND", "Assessment context not found for this workspace.", 404)
    raw = getattr(ctx, "assessment_type", None)
    key = str(getattr(raw, "value", raw) or "").strip().lower()
    return key, ctx


# ── Connection lifecycle ─────────────────────────────────────────────────────


def create_connection(
    *,
    org_id: str,
    user_id: Optional[str],
    assessment_id: str,
    form_url: str = "",
    sheet_url: str = "",
    sheet_range: str = "",
    purpose: str = "evidence",
    note: str = "",
    request_origin: str = "",
) -> dict[str, Any]:
    """Register a connection and hand back the consent URL.

    Nothing is claimed at this point: the connection is ``pending_auth`` until
    Google returns a code we can exchange.
    """
    config = get_forms_config()
    _require_enabled(config)

    form_id = extract_form_id(form_url)
    sheet_id = extract_sheet_id(sheet_url)
    if not form_id and not sheet_id:
        raise FormsIntegrationError(
            "INVALID_COLLECTION_URL",
            "Provide a Google Form link (docs.google.com/forms/d/…) or a response spreadsheet link "
            "(docs.google.com/spreadsheets/d/…).",
            400,
        )

    entity_key, ctx = _entity_key(assessment_id, org_id, user_id)
    contract = collection_contract(entity_key)
    kind = "google_form" if form_id else "google_sheet"
    resolved_purpose = "follow_up" if str(purpose or "").strip().lower() == "follow_up" else "evidence"

    repo = _repo()
    existing = repo.find_connection_by_form(org_id, ctx.assessment_id, form_id) if form_id else None
    if existing is not None and sheet_id == existing.sheet_id and existing.status != ConnectionStatus.REVOKED.value:
        conn = existing
    else:
        conn = FormConnection(
            id=str(uuid.uuid4()),
            org_id=org_id,
            assessment_id=ctx.assessment_id,
            kind=kind,
            form_id=form_id,
            sheet_id=sheet_id,
            sheet_range=sheet_range.strip(),
            title="",
            purpose=resolved_purpose,
            status=ConnectionStatus.PENDING_AUTH.value,
            owner_user_id=user_id or "",
            evidence_class=contract.default_evidence_class,
            note=(note or "")[:400],
        )
        repo.save_connection(conn)

    redirect_uri = _redirect_uri(config, request_origin)
    state = _sign_state(
        {"cid": conn.id, "org": org_id, "aid": ctx.assessment_id, "uid": user_id or "", "iat": time.time()}
    )
    authorize_url = build_authorization_url(config, state=state, redirect_uri=redirect_uri)

    record_event(
        "collection.auth_started",
        org_id=org_id,
        user_id=user_id,
        assessment_id=ctx.assessment_id,
        metadata={
            "connectionId": conn.id,
            "kind": conn.kind,
            "purpose": conn.purpose,
            "entityType": entity_key,
            "redirectUri": redirect_uri,
        },
    )

    return {
        "connection": _conn_payload(conn),
        "authorizeUrl": authorize_url,
        "redirectUri": redirect_uri,
        "guidance": entity_guidance(entity_key),
        "credentialBlastRadius": config.credential_blast_radius,
        "consentNote": (
            "Google will ask the form owner to consent. access_type=offline + prompt=consent are required "
            "for a refresh token, without which scheduled sync is impossible."
        ),
    }


def complete_authorization(*, code: str, state: str, redirect_uri: str = "") -> dict[str, Any]:
    """Exchange the authorization code, seal it, and discover the instrument.

    Authorisation is bound to the signed ``state`` (connection + workspace), so
    this entry point cannot be aimed at someone else's connection.
    """
    config = get_forms_config()
    _require_enabled(config)
    if not code:
        raise FormsIntegrationError("OAUTH_CODE_MISSING", "Google returned no authorization code.", 400)

    state_payload = _read_state(state)
    connection_id = str(state_payload.get("cid") or "")
    org_id = str(state_payload.get("org") or "")
    user_id = str(state_payload.get("uid") or "") or None
    if not connection_id or not org_id:
        raise FormsIntegrationError("OAUTH_STATE_INVALID", "The OAuth state carried no connection. Begin again.", 400)

    repo = _repo()
    conn = repo.get_connection(connection_id, org_id=org_id)
    if conn is None:
        raise FormsIntegrationError("CONNECTION_NOT_FOUND", "That collection connection no longer exists.", 404)

    try:
        tokens = exchange_code(config, code=code, redirect_uri=redirect_uri or _redirect_uri(config, ""))
        if not repo.set_credentials(conn.id, tokens):
            raise FormsIntegrationError(
                "CREDENTIAL_STORAGE_UNAVAILABLE",
                "Google authorisation succeeded but this deployment cannot encrypt credential storage "
                "(KULIMA_DOC_ENCRYPTION_KEY is not set), so the token was not saved. Set the key and reconnect.",
                503,
            )
        conn, questions = _refresh_schema(conn, config)
        conn.status = ConnectionStatus.ACTIVE.value
        conn.last_error = ""
        conn.updated_at = _now()
        repo.save_connection(conn)
    except FormsIntegrationError as exc:
        conn.status = ConnectionStatus.ERROR.value
        conn.last_error = exc.message[:400]
        conn.updated_at = _now()
        repo.save_connection(conn)
        record_event(
            "collection.connection_failed",
            org_id=org_id,
            user_id=user_id,
            assessment_id=conn.assessment_id,
            metadata={"connectionId": conn.id, "code": exc.code, "message": exc.message[:280]},
        )
        raise

    record_event(
        "collection.connected",
        org_id=org_id,
        user_id=user_id,
        assessment_id=conn.assessment_id,
        metadata={
            "connectionId": conn.id,
            "kind": conn.kind,
            "title": conn.title,
            "questionCount": len(questions),
            "schemaHash": conn.schema_hash,
            "purpose": conn.purpose,
        },
    )
    return {"connection": _conn_payload(conn), "questionCount": len(questions)}


def disconnect(*, connection_id: str, org_id: str, user_id: Optional[str] = None) -> dict[str, Any]:
    """Revoke a connection. Evidence already materialised stays in the assessment."""
    repo = _repo()
    conn = repo.get_connection(connection_id, org_id=org_id)
    if conn is None:
        raise FormsIntegrationError("CONNECTION_NOT_FOUND", "Collection connection not found.", 404)
    repo.clear_credentials(connection_id)
    repo.revoke_connection(connection_id, org_id=org_id)
    record_event(
        "collection.disconnected",
        org_id=org_id,
        user_id=user_id,
        assessment_id=conn.assessment_id,
        metadata={"connectionId": connection_id, "kind": conn.kind, "title": conn.title},
    )
    return {
        "revoked": True,
        "connection": _conn_payload(repo.get_connection(connection_id, org_id=org_id) or conn),
        "note": "Evidence batches already attached to the assessment remain as documents, with their provenance.",
    }


def list_connections(*, org_id: str, assessment_id: Optional[str] = None, user_id: Optional[str] = None) -> dict[str, Any]:
    config = get_forms_config()
    connections = _repo().list_connections(org_id, assessment_id)
    entity_key = ""
    if assessment_id:
        try:
            entity_key, _ = _entity_key(assessment_id, org_id, user_id)
        except FormsIntegrationError:
            entity_key = ""
    return {
        "enabled": config.enabled,
        "configured": config.configured,
        "message": None if config.configured else config.degraded_message(),
        "connections": [_conn_payload(c) for c in connections],
        "batches": _repo().list_batches(org_id, assessment_id),
        "guidance": entity_guidance(entity_key) if entity_key else None,
        "status": config.status_payload(),
    }


def batches_for(*, org_id: str, assessment_id: Optional[str] = None) -> dict[str, Any]:
    return {"batches": _repo().list_batches(org_id, assessment_id)}


def guidance_for(*, org_id: str, assessment_id: str, user_id: Optional[str] = None) -> dict[str, Any]:
    """Phase 6 surface: how this workspace's entity type should use the channel."""
    entity_key, ctx = _entity_key(assessment_id, org_id, user_id)
    config = get_forms_config()
    return {
        "assessmentId": ctx.assessment_id,
        "entityType": entity_key,
        "guidance": entity_guidance(entity_key),
        "status": config.status_payload(),
    }


def status_payload() -> dict[str, Any]:
    """Channel availability for the UI — never a fake green light."""
    return get_forms_config().status_payload()


# ── Schema discovery ─────────────────────────────────────────────────────────


def _client_factory(config: FormsConfig, access_token: str) -> GoogleCollectionClient:
    return GoogleCollectionClient(config, access_token)


def _access_token(config: FormsConfig, conn: FormConnection, repo: FormsRepository) -> str:
    tokens = repo.get_credentials(conn.id)
    if not tokens.get("refresh_token") and not tokens.get("access_token"):
        raise FormsIntegrationError(
            "AUTH_REQUIRED", "This collection source has not been authorised with Google yet. Reconnect it.", 401
        )
    if tokens.get("access_token") and token_is_fresh(tokens):
        return str(tokens["access_token"])
    refresh = str(tokens.get("refresh_token") or "")
    if not refresh:
        raise FormsIntegrationError(
            "AUTH_EXPIRED",
            "The Google access token expired and no refresh token was stored. Reconnect the form.",
            401,
        )
    rotated = refresh_access_token(config, refresh)
    rotated["refresh_token"] = rotated.get("refresh_token") or refresh
    if not repo.set_credentials(conn.id, rotated):
        raise FormsIntegrationError(
            "CREDENTIAL_STORAGE_UNAVAILABLE",
            "Cannot store the refreshed Google token: KULIMA_DOC_ENCRYPTION_KEY is not set on this deployment.",
            503,
        )
    return str(rotated.get("access_token") or "")


def _refresh_schema(
    conn: FormConnection,
    config: FormsConfig,
    client: Optional[GoogleCollectionClient] = None,
    repo: Optional[FormsRepository] = None,
) -> tuple[FormConnection, list[FormQuestion]]:
    """Read the instrument structure and record it (schema drift becomes visible)."""
    repo = repo or _repo()
    client = client or _client_factory(config, _access_token(config, conn, repo))

    if conn.kind == "google_sheet":
        headers, _rows = client.sheet_rows(conn.sheet_id, conn.sheet_range)
        questions = [
            FormQuestion(key=f"sheet_col_{idx}", title=str(head).strip(), question_type="text")
            for idx, head in enumerate(headers)
            if str(head or "").strip()
        ]
        title = conn.title or "Response sheet"
    else:
        form = client.get_form(conn.form_id)
        questions = questions_from_metadata(form)
        info = form.get("info") if isinstance(form.get("info"), dict) else {}
        title = str(info.get("title") or conn.title or "Google Form")

    if not questions:
        raise FormsIntegrationError(
            "INSTRUMENT_HAS_NO_QUESTIONS",
            "Google returned this instrument without any readable questions. Confirm the form has at least one "
            "question and that the response sheet has a header row.",
            422,
        )

    conn.title = title[:200]
    conn.questions = questions
    conn.schema_hash = compute_schema_hash(questions)
    conn.updated_at = _now()
    repo.save_connection(conn)
    return conn, questions


# ── Ingestion + materialisation ──────────────────────────────────────────────


def _sheet_response_id(row: Sequence[Any], index: int) -> str:
    """Stable id for a linked-sheet row.

    Sheets have no response id, so the row content is hashed. The row index is
    included because two genuinely identical answers must remain two responses;
    the honest cost is that inserting or deleting a row upstream changes the ids
    of the rows after it, which can re-import a previously seen answer once.
    Never silently de-duplicated, and stated in the connector notes.
    """
    joined = "\x1f".join(str(cell or "") for cell in row)
    token = hashlib.sha1(f"{index}\x1f{joined}".encode("utf-8")).hexdigest()[:20]
    return f"sheet-row-{token}"


def _collect_raw(
    conn: FormConnection,
    client: GoogleCollectionClient,
    questions: Sequence[FormQuestion],
    config: FormsConfig,
) -> list[CollectedResponse]:
    """Pull responses from Google and normalise them (no trust arithmetic yet)."""
    if conn.kind == "google_sheet":
        headers, rows = client.sheet_rows(conn.sheet_id, conn.sheet_range)
        collected: list[CollectedResponse] = []
        for idx, row in enumerate(rows):
            if not any(str(cell or "").strip() for cell in row):
                continue
            stamp = parse_timestamp(str(row[0] or "")) if row else ""
            collected.append(
                CollectedResponse(
                    response_id=_sheet_response_id(row, idx),
                    submitted_at=stamp,
                    answers=answers_from_sheet_row(headers, row),
                    raw={"rowIndex": idx},
                )
            )
        return collected[: config.max_responses_per_sync]

    raw, _token = client.iter_responses(
        conn.form_id,
        page_size=min(200, max(1, config.max_responses_per_sync)),
        max_pages=max(1, config.max_pages),
    )
    out: list[CollectedResponse] = []
    for item in raw:
        rid = str(item.get("responseId") or "").strip()
        if not rid:
            continue
        # Forms API v1 stamps responses with ``submittedTime``; the field has
        # also appeared as ``submittedAt`` in other payloads. Either is used,
        # and an absent stamp stays empty rather than being invented.
        stamp = item.get("submittedTime") or item.get("submittedAt") or item.get("startTime") or ""
        out.append(
            CollectedResponse(
                response_id=rid,
                submitted_at=parse_timestamp(str(stamp)),
                answers=answers_from_form_response(item, questions),
            )
        )
    return out[: config.max_responses_per_sync]


def _synthetic_upload(filename: str, payload: bytes) -> UploadFile:
    """A connector-produced document enters the pipeline as an upload would."""
    return UploadFile(
        file=io.BytesIO(payload),
        filename=filename,
        headers=Headers({"content-type": "text/csv"}),
    )


def sync_connection(
    connection_id: str,
    *,
    org_id: str,
    user_id: Optional[str] = None,
    assessment_id: Optional[str] = None,
    reason: str = "manual",
    config: Optional[FormsConfig] = None,
    client_factory: Optional[Callable[[FormsConfig, str], GoogleCollectionClient]] = None,
) -> dict[str, Any]:
    """Sync one connection: pull new responses, then materialise a batch.

    Returns a structured payload whose ``status`` is one of
    ``no_new_responses`` / ``pending_below_minimum`` /
    ``awaiting_primary_documents`` / ``materialised``. Raises
    ``FormsIntegrationError`` for real failures — a decline is not a failure.
    """
    config = config or get_forms_config()
    _require_enabled(config)
    repo = _repo()
    factory = client_factory or _client_factory

    conn = repo.get_connection(connection_id, org_id=org_id)
    if conn is None:
        raise FormsIntegrationError("CONNECTION_NOT_FOUND", "Collection connection not found for this workspace.", 404)
    if conn.status == ConnectionStatus.REVOKED.value:
        raise FormsIntegrationError("CONNECTION_REVOKED", "This collection source was disconnected.", 409)

    target_assessment = assessment_id or conn.assessment_id
    entity_key, ctx = _entity_key(target_assessment, org_id, user_id)
    contract = collection_contract(entity_key)

    try:
        client = factory(config, _access_token(config, conn, repo))
        conn, questions = _refresh_schema(conn, config, client, repo)
        raw = _collect_raw(conn, client, questions, config)

        known = repo.known_response_ids(conn.id)
        fresh = [r for r in raw if r.response_id not in known]
        annotated = annotate_responses(fresh, questions)
        inserted = repo.save_responses(conn, annotated) if annotated else 0

        conn.last_synced_at = _iso(_now())
        conn.last_error = ""
        conn.status = ConnectionStatus.ACTIVE.value
        conn.updated_at = _now()
        repo.save_connection(conn)

        record_event(
            "collection.synced",
            org_id=org_id,
            user_id=user_id,
            assessment_id=conn.assessment_id,
            metadata={
                "connectionId": conn.id,
                "kind": conn.kind,
                "reason": reason,
                "fetched": len(raw),
                "newResponses": inserted,
                "totalResponses": conn.total_responses,
            },
        )

        pending = repo.pending_responses(conn.id)
        base = {
            "connectionId": conn.id,
            "kind": conn.kind,
            "kindLabel": SOURCE_KIND_LABELS.get(conn.kind, conn.kind),
            "title": conn.title,
            "purpose": conn.purpose,
            "assessmentId": conn.assessment_id,
            "fetched": len(raw),
            "newResponses": inserted,
            "pendingCount": len(pending),
            "minBatchSize": config.min_batch_size,
            "recommendedMinimum": contract.minimum_responses,
            "reason": reason,
        }

        if not pending:
            return {**base, "status": SyncStatus.NO_NEW_RESPONSES.value, "materialised": False}

        if len(pending) < max(1, config.min_batch_size):
            return {
                **base,
                "status": SyncStatus.PENDING_BELOW_MINIMUM.value,
                "materialised": False,
                "message": (
                    f"{len(pending)} response(s) collected so far. A batch is attached to the assessment at "
                    f"{config.min_batch_size} responses; keep collecting or sync again later."
                ),
            }

        batch_ids = repo.batch_document_ids(org_id, conn.assessment_id)
        primary = [str(d) for d in (ctx.document_ids or []) if str(d) not in batch_ids]
        if not primary:
            return {
                **base,
                "status": "awaiting_primary_documents",
                "materialised": False,
                "code": "COLLECTION_REQUIRES_PRIMARY_DOCUMENT",
                "message": (
                    "Responses are collected and counted, but no evidence batch was attached yet. This assessment "
                    "has no uploaded document yet — a self-collected form cannot be the only evidence about an "
                    "institution. Attach the primary documents first (for an NGO: proposal, budget, M&E report), "
                    "then sync again."
                ),
            }

        return {**base, **_materialise(conn, pending, questions, config, repo, contract, entity_key, user_id)}

    except FormsIntegrationError as exc:
        conn.status = ConnectionStatus.ERROR.value if exc.code not in {"AUTH_REVOKED"} else conn.status
        conn.last_error = exc.message[:400]
        conn.updated_at = _now()
        try:
            repo.save_connection(conn)
        except Exception:  # noqa: BLE001 — state reporting must not mask the real error
            logger.debug("could not persist collection connection error state", exc_info=True)
        if exc.code in {"AUTH_REVOKED", "GOOGLE_UNAUTHENTICATED"}:
            repo.clear_credentials(conn.id)
        record_event(
            "collection.sync_failed",
            org_id=org_id,
            user_id=user_id,
            assessment_id=conn.assessment_id,
            metadata={"connectionId": conn.id, "code": exc.code, "message": exc.message[:280], "reason": reason},
        )
        raise
    except Exception as exc:  # noqa: BLE001 — never a partial success story
        conn.last_error = str(exc)[:400]
        conn.status = ConnectionStatus.ERROR.value
        conn.updated_at = _now()
        try:
            repo.save_connection(conn)
        except Exception:  # noqa: BLE001
            logger.debug("could not persist collection connection error state", exc_info=True)
        record_event(
            "collection.sync_failed",
            org_id=org_id,
            user_id=user_id,
            assessment_id=conn.assessment_id,
            metadata={"connectionId": conn.id, "message": str(exc)[:280], "reason": reason},
        )
        logger.exception("Collection sync failed unexpectedly for connection %s", connection_id)
        raise FormsIntegrationError("SYNC_FAILED", f"Collection sync failed: {exc}", 500) from exc


def _materialise(
    conn: FormConnection,
    pending: Sequence[CollectedResponse],
    questions: Sequence[FormQuestion],
    config: FormsConfig,
    repo: FormsRepository,
    contract: Any,
    entity_key: str,
    user_id: Optional[str],
) -> dict[str, Any]:
    """Turn one pending window into exactly one evidence document."""
    evidence_class = conn.evidence_class or contract.default_evidence_class
    digest = build_digest(
        conn.title or "Collection",
        list(pending),
        source_kind=conn.kind,
        purpose=conn.purpose,
        evidence_class=evidence_class,
    )
    filename = batch_filename(conn.title or "responses", len(pending))
    payload = to_csv_bytes(list(pending), questions)
    label = f"Google {'Form' if conn.kind == 'google_form' else 'Sheet'} Collection Pipeline ({filename})"

    prior = assessment_adapter._repo.get(conn.assessment_id, org_id=conn.org_id)
    prior_ids = {str(d) for d in ((prior.document_ids if prior is not None else []) or [])}

    result = assessment_adapter.attach_documents(
        conn.assessment_id,
        [_synthetic_upload(filename, payload)],
        user_id,
        org_id=conn.org_id,
        source_type=conn.kind,
        pipeline_label=label,
        summary_text=digest.text,
        self_reported=True,
        source_ceiling=config.self_reported_source_ceiling,
        duplicate_instrument_count=repo.same_connection_batch_count(conn.id),
        extra_metadata={
            "collectionChannel": conn.kind,
            "collectionConnectionId": conn.id,
            "collectionPurpose": conn.purpose,
            "collectionTitle": conn.title,
            "collectionEvidenceClass": evidence_class,
            "collectionResponseCount": len(pending),
            "collectionSchemaHash": conn.schema_hash,
            "collectionVerification": "SELF_REPORTED",
        },
        # Follow-up / outcome surveys inform the record without re-deciding a
        # decision that is already on file (decision history stays immutable).
        rerun=bool(config.auto_rerun) and conn.purpose != "follow_up",
    )

    after_ctx = assessment_adapter._repo.get(conn.assessment_id, org_id=conn.org_id)
    new_ids = [d for d in ((after_ctx.document_ids if after_ctx is not None else []) or []) if str(d) not in prior_ids]
    document_id = str(new_ids[0]) if new_ids else ""

    trust_score: Optional[float] = None
    evidence_status = ""
    if after_ctx is not None:
        for doc in after_ctx.uploaded_documents:
            if str(doc.id) == document_id:
                trust_score = doc.trust_score
                evidence_status = str(doc.evidence_status or "")

    batch = CollectionBatch(
        id=str(uuid.uuid4()),
        connection_id=conn.id,
        org_id=conn.org_id,
        assessment_id=conn.assessment_id,
        response_ids=[r.response_id for r in pending],
        document_id=document_id,
        run_id=str(result.get("runId") or ""),
        filename=filename,
        response_count=len(pending),
        window_start=digest.window_start,
        window_end=digest.window_end,
        trust_score=trust_score,
        evidence_status=evidence_status,
        digest=digest.text,
        created_at=_now(),
    )
    repo.record_batch(batch)
    repo.mark_batched(conn.id, batch.response_ids, batch.id)

    conn.status = ConnectionStatus.ACTIVE.value
    conn.updated_at = _now()
    repo.save_connection(conn)

    record_event(
        "collection.batch_materialised",
        org_id=conn.org_id,
        user_id=user_id,
        assessment_id=conn.assessment_id,
        metadata={
            "connectionId": conn.id,
            "batchId": batch.id,
            "documentId": document_id,
            "responseCount": len(pending),
            "evidenceClass": evidence_class,
            "purpose": conn.purpose,
            "trustScore": trust_score,
            "evidenceStatus": evidence_status,
            "runId": batch.run_id,
            "selfReported": True,
            "sourceCeiling": config.self_reported_source_ceiling,
            "entityType": entity_key,
        },
    )

    below = len(pending) < contract.minimum_responses
    return {
        "status": SyncStatus.MATERIALISED.value,
        "materialised": True,
        "batchId": batch.id,
        "documentId": document_id,
        "filename": filename,
        "responseCount": len(pending),
        "trustScore": trust_score,
        "evidenceStatus": evidence_status,
        "runId": batch.run_id,
        "runStatus": str(result.get("runStatus") or ""),
        "evidenceClass": evidence_class,
        "windowStart": digest.window_start,
        "windowEnd": digest.window_end,
        "respondentMix": digest.respondent_mix,
        "medianResponseTrust": digest.median_trust_score,
        "consistencyFlagged": digest.consistency_flagged,
        "belowRecommendedMinimum": below,
        "message": (
            f"Attached {len(pending)} response(s) as one evidence batch ({filename}). "
            + (
                f"That is below the {contract.minimum_responses} responses this entity type needs before "
                "responses are directional, so the report treats them as indicative only."
                if below
                else "Reports will list this batch as form evidence with its own source attribution."
            )
            + f" {contract.honesty_caveat}"
        ),
        "digestPreview": digest.text[:600],
    }


# ── Scheduled sync (opt-in, durable queue) ───────────────────────────────────


def enqueue_sync(
    connection_id: str,
    *,
    org_id: str,
    user_id: Optional[str] = None,
    delay_minutes: int = 0,
) -> dict[str, Any]:
    """Queue a sync on the durable job runner. Idempotent per minute window."""
    config = get_forms_config()
    _require_enabled(config)
    repo = _repo()
    conn = repo.get_connection(connection_id, org_id=org_id)
    if conn is None:
        raise FormsIntegrationError("CONNECTION_NOT_FOUND", "Collection connection not found.", 404)

    from kulima.core.jobs.models import Job, JobKind, JobStatus
    from kulima.core.jobs.repository import JobRepository

    moment = _now() + timedelta(minutes=max(0, int(delay_minutes)))
    window = moment.strftime("%Y%m%d%H%M")
    job = Job(
        id=str(uuid.uuid4()),
        # Deliberately not a real case id: a dead collection job must never
        # revert an assessment's case lifecycle. The runner treats an unknown
        # case as a no-op.
        case_id=f"collection:{conn.id}",
        kind=JobKind.FORM_SYNC,
        status=JobStatus.QUEUED,
        payload={
            "connection_id": conn.id,
            "org_id": conn.org_id,
            "user_id": user_id,
            "target_assessment_id": conn.assessment_id,
        },
        idempotency_key=f"form-sync:{conn.id}:{window}",
        max_attempts=3,
        run_after=moment,
    )
    try:
        JobRepository().enqueue(job)
    except Exception as exc:  # noqa: BLE001 — duplicate idempotency key is success
        if "idempotency_key" in str(exc) or "UNIQUE" in str(exc).upper():
            return {"queued": False, "deduplicated": True, "connectionId": conn.id, "runAfter": job.run_after.isoformat()}
        raise
    return {"queued": True, "jobId": job.id, "connectionId": conn.id, "runAfter": job.run_after.isoformat()}
