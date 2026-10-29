"""Collection channels: Google Forms / Sheets ingestion (Forms Integration V1).

A channel is an *ingress*, not a pipeline. Everything produced here terminates
at ``backend.app.services.document_adapter.save_uploaded_file`` — the same entry
point an uploaded document uses — so Trust, Signals, Decisions, Reports and
Outcomes are consumed unchanged, and documents and forms coexist by
construction.

Live in V1: ``document`` (existing), ``google_form``, ``google_sheet``.
Registered but not live (design COLLECTION_LAYER_V1): ``kobo``, ``whatsapp``,
``ussd``, ``api``.
"""

from .client import (
    FormsIntegrationError,
    GoogleCollectionClient,
    build_authorization_url,
    exchange_code,
    refresh_access_token,
    token_is_fresh,
)
from .config import (
    SELF_REPORTED_SOURCE_CEILING,
    SELF_REPORTED_TRUST_CEILING,
    FormsConfig,
    extract_form_id,
    extract_sheet_id,
    get_forms_config,
)
from .mapping import (
    answers_from_form_response,
    answers_from_sheet_row,
    collection_contract,
    detect_respondent_type,
    entity_guidance,
    questions_from_metadata,
    schema_hash,
)
from .models import (
    LIVE_KINDS,
    CollectionBatch,
    CollectionDigest,
    CollectionPurpose,
    CollectedAnswer,
    CollectedResponse,
    ConnectionStatus,
    EvidenceClass,
    FormConnection,
    FormQuestion,
    SourceKind,
    SyncStatus,
)
from .normalizer import (
    annotate_responses,
    batch_filename,
    build_digest,
    to_csv_bytes,
)
from .repository import FormsRepository, get_repo

__all__ = [
    # config
    "FormsConfig",
    "get_forms_config",
    "extract_form_id",
    "extract_sheet_id",
    "SELF_REPORTED_SOURCE_CEILING",
    "SELF_REPORTED_TRUST_CEILING",
    # models
    "SourceKind",
    "LIVE_KINDS",
    "EvidenceClass",
    "CollectionPurpose",
    "ConnectionStatus",
    "SyncStatus",
    "FormQuestion",
    "CollectedAnswer",
    "CollectedResponse",
    "CollectionDigest",
    "FormConnection",
    "CollectionBatch",
    # mapping
    "collection_contract",
    "entity_guidance",
    "questions_from_metadata",
    "schema_hash",
    "answers_from_form_response",
    "answers_from_sheet_row",
    "detect_respondent_type",
    # normalizer
    "annotate_responses",
    "batch_filename",
    "build_digest",
    "to_csv_bytes",
    # client
    "FormsIntegrationError",
    "GoogleCollectionClient",
    "build_authorization_url",
    "exchange_code",
    "refresh_access_token",
    "token_is_fresh",
    # repository
    "FormsRepository",
    "get_repo",
]
