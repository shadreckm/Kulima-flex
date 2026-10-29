"""Google Forms / Sheets collection configuration (Forms Integration V1).

Stdlib-only, safe by default — the same contract ``kulima.core.billing.paychangu``
follows, and for the same reason: a pilot deployment must be able to run with
this channel switched off and get a clean, diagnosable "not configured" answer
instead of a half-wired integration.

Everything is opt-in:

``KULIMA_FORMS_ENABLED``
    Master switch. When unset (the default) no route accepts a sync and the UI
    reports the channel as unavailable. Nothing else in the platform changes.

``GOOGLE_OAUTH_CLIENT_ID`` / ``GOOGLE_OAUTH_CLIENT_SECRET``
    OAuth client issued for the project that owns the form. Without them the
    connector cannot read a form, and says so.

``GOOGLE_OAUTH_REDIRECT_URI``
    Must match an authorized redirect URI of the OAuth client exactly.

The ceilings (``self_reported_source_ceiling`` / ``self_reported_trust_ceiling``)
encode guard G1/G2 of the collection design: responses a programme collects
about itself are self-reported structured data. Volume must never buy them the
authority of an audited or institutionally corroborated document, so a
collection batch cannot be classified ``VERIFIED`` by arithmetic alone.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from kulima.config import get_settings

FORMS_SCOPE_BODY = "https://www.googleapis.com/auth/forms.body.readonly"
FORMS_SCOPE_RESPONSES = "https://www.googleapis.com/auth/forms.responses.readonly"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

DEFAULT_SCOPES: tuple[str, ...] = (
    FORMS_SCOPE_BODY,
    FORMS_SCOPE_RESPONSES,
    SHEETS_SCOPE,
)

_AUTH_TRUE = {"1", "true", "yes", "on"}

# Self-reported structured collections sit at authority tier T5 of the
# collection design. 70 mirrors the existing "Structured data export" rung of
# the document trust ladder, so a form batch is treated as survey-grade
# evidence whether it arrived through upload or through a connector.
SELF_REPORTED_SOURCE_CEILING = 70.0
# 79 keeps the weighted score strictly below the VERIFIED threshold (80) that
# ``document_adapter._extract_signals_and_evidence`` applies.
SELF_REPORTED_TRUST_CEILING = 79.0


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, "").strip().lower() in _AUTH_TRUE if name in os.environ else default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class FormsConfig:
    """Resolved collection-channel configuration (read once per call)."""

    enabled: bool
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = DEFAULT_SCOPES
    auth_uri: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    forms_api_base: str = "https://forms.googleapis.com/v1"
    sheets_api_base: str = "https://sheets.googleapis.com/v4"
    request_timeout_seconds: int = 30
    max_responses_per_sync: int = 500
    max_pages: int = 10
    min_batch_size: int = 5
    poll_minutes: int = 0
    use_jobs: bool = False
    auto_rerun: bool = True
    self_reported_source_ceiling: float = SELF_REPORTED_SOURCE_CEILING
    self_reported_trust_ceiling: float = SELF_REPORTED_TRUST_CEILING
    db_path: str = field(default="", repr=False)

    @property
    def configured(self) -> bool:
        """A channel is only usable when switched on AND credentialed."""
        return bool(self.enabled and self.client_id and self.client_secret)

    @property
    def credential_blast_radius(self) -> str:
        """Honest label shown next to the consent screen link (design G4)."""
        return "read-only access to the forms and response sheets this workspace authorises"

    def missing_required_secrets(self) -> list[str]:
        missing: list[str] = []
        if not self.enabled:
            missing.append("KULIMA_FORMS_ENABLED")
        if not self.client_id:
            missing.append("GOOGLE_OAUTH_CLIENT_ID")
        if not self.client_secret:
            missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
        return missing

    def degraded_message(self) -> str:
        """The single sentence the UI shows when the channel is not live."""
        if not self.enabled:
            return (
                "Collection channels are switched off (KULIMA_FORMS_ENABLED is not set). "
                "Documents remain the primary evidence source."
            )
        return (
            "Google OAuth client is not configured on this deployment "
            "(GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET), so no form can "
            "be authorised yet. Documents remain the primary evidence source."
        )

    def status_payload(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "missing": self.missing_required_secrets(),
            "minBatchSize": self.min_batch_size,
            "maxResponsesPerSync": self.max_responses_per_sync,
            "pollMinutes": self.poll_minutes,
            "usesDurableQueue": self.use_jobs,
            "autoRerun": self.auto_rerun,
            "credentialBlastRadius": self.credential_blast_radius,
            "message": None if self.configured else self.degraded_message(),
        }

    @classmethod
    def from_env(cls) -> "FormsConfig":
        scopes_raw = os.getenv("GOOGLE_OAUTH_SCOPES", "").strip()
        scopes = tuple(s.strip() for s in scopes_raw.split(",") if s.strip()) or DEFAULT_SCOPES
        return cls(
            enabled=_flag("KULIMA_FORMS_ENABLED"),
            client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
            client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
            redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip(),
            scopes=scopes,
            request_timeout_seconds=_int("KULIMA_FORMS_HTTP_TIMEOUT", 30),
            max_responses_per_sync=_int("KULIMA_FORMS_MAX_RESPONSES", 500),
            max_pages=_int("KULIMA_FORMS_MAX_PAGES", 10),
            min_batch_size=_int("KULIMA_FORMS_MIN_BATCH_SIZE", 5),
            poll_minutes=_int("KULIMA_FORMS_POLL_MINUTES", 0),
            use_jobs=_flag("KULIMA_FORMS_USE_JOBS"),
            auto_rerun=_flag("KULIMA_FORMS_AUTO_RERUN", default=True),
            self_reported_source_ceiling=_float("KULIMA_FORMS_SOURCE_CEILING", SELF_REPORTED_SOURCE_CEILING),
            self_reported_trust_ceiling=_float("KULIMA_FORMS_TRUST_CEILING", SELF_REPORTED_TRUST_CEILING),
            db_path=get_settings().db_path,
        )


def get_forms_config() -> FormsConfig:
    """Fresh read per call — env is the single source of truth (no caching)."""
    return FormsConfig.from_env()


def extract_form_id(raw: str) -> str:
    """Accept a Form URL or a bare key and return the form id.

    Supported shapes:
      https://docs.google.com/forms/d/1AbCdEf.../viewform
      https://docs.google.com/forms/d/e/1FAIpQLSf.../viewform
      https://script.google.com/macros/s/.../exec  (not a form → returned as-is)
      1AbCdEf...  (already an id)
    """
    import re

    text = (raw or "").strip()
    if not text:
        return ""
    m = re.search(r"/forms/d/(?:e/)?([\w-]{12,})", text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w-]{12,}", text):
        return text
    return ""


def extract_sheet_id(raw: str) -> str:
    """Accept a Spreadsheet URL or id and return the spreadsheet id."""
    import re

    text = (raw or "").strip()
    if not text:
        return ""
    m = re.search(r"/spreadsheets/d/([\w-]{20,})", text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w-]{20,}", text):
        return text
    return ""
