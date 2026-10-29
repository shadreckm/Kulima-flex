"""Stdlib-only Google Forms / Sheets transport (Forms Integration V1).

No new dependency is introduced: ``urllib.request`` + ``json`` are enough for a
read-only REST integration, and keeping the transport this small means the
offline gate suite can exercise the whole channel with a stubbed ``_request``
and no network. ``kulima.core.billing.paychangu`` set this precedent for the
same reason.

Verified surface (Google Forms API v1):

    GET  https://forms.googleapis.com/v1/forms/{formId}
    GET  https://forms.googleapis.com/v1/forms/{formId}/responses
    GET  https://sheets.googleapis.com/v4/spreadsheets/{id}/values/{range}

Scopes are read-only (``forms.body.readonly``, ``forms.responses.readonly``,
``spreadsheets.readonly``). ``prompt=consent`` + ``access_type=offline`` are
required to receive a refresh token, which is what makes scheduled sync
possible after the one-hour access token expires.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .config import FormsConfig

_log = logging.getLogger(__name__)


class FormsIntegrationError(Exception):
    """Domain error with a stable code, an operator message and an HTTP status."""

    def __init__(self, code: str, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _request(url: str, *, method: str = "GET", headers: dict | None = None, body: bytes | None = None, timeout: int = 30) -> tuple[int, dict]:
    """One HTTP call returning (status, parsed-json). Single seam for tests."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed https hosts
            raw = resp.read()
            return resp.status, _loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        payload = _loads(raw)
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise FormsIntegrationError("NETWORK_UNAVAILABLE", f"Google could not be reached: {exc.reason}", 503) from exc
    except Exception as exc:  # noqa: BLE001
        raise FormsIntegrationError("REQUEST_FAILED", f"Request to Google failed: {exc}", 502) from exc


def _loads(raw: bytes | str) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _post_form(url: str, fields: dict[str, str], timeout: int) -> tuple[int, dict]:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    return _request(
        url,
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded", "accept": "application/json"},
        body=data,
        timeout=timeout,
    )


# ── OAuth ────────────────────────────────────────────────────────────────────

def build_authorization_url(config: FormsConfig, *, state: str, redirect_uri: str) -> str:
    """Consent URL for the workspace owner. ``prompt=consent`` is mandatory:
    without it Google issues no refresh token and scheduled sync cannot work."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    return f"{config.auth_uri}?{urllib.parse.urlencode(params)}"


def exchange_code(config: FormsConfig, *, code: str, redirect_uri: str) -> dict:
    """Authorization code → token set (access, refresh, expiry)."""
    if not config.client_id or not config.client_secret:
        raise FormsIntegrationError("NOT_CONFIGURED", "Google OAuth client is not configured on this deployment.", 503)
    status, payload = _post_form(
        config.token_uri,
        {
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        config.request_timeout_seconds,
    )
    if status >= 400 or "access_token" not in payload:
        raise FormsIntegrationError(
            "OAUTH_EXCHANGE_FAILED",
            str(payload.get("error_description") or payload.get("error") or f"token exchange failed ({status})"),
            400,
        )
    return _normalise_token_set(payload)


def refresh_access_token(config: FormsConfig, refresh_token: str) -> dict:
    status, payload = _post_form(
        config.token_uri,
        {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        config.request_timeout_seconds,
    )
    if status >= 400 or "access_token" not in payload:
        code = str(payload.get("error") or "")
        if code in {"invalid_grant", "expired_token"}:
            raise FormsIntegrationError(
                "AUTH_REVOKED",
                "Google authorisation for this form was revoked or expired. Reconnect the form.",
                401,
            )
        raise FormsIntegrationError(
            "TOKEN_REFRESH_FAILED",
            str(payload.get("error_description") or code or f"refresh failed ({status})"),
            502,
        )
    return _normalise_token_set(payload)


def _normalise_token_set(payload: dict) -> dict:
    expires_in = int(payload.get("expires_in") or 3600)
    return {
        "access_token": payload.get("access_token", ""),
        "refresh_token": payload.get("refresh_token", ""),
        "scope": payload.get("scope", ""),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in))).isoformat(),
    }


def token_is_fresh(token_set: dict, *, skew_seconds: int = 120) -> bool:
    raw = token_set.get("expires_at") or ""
    if not raw:
        return False
    try:
        expiry = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc).timestamp() + skew_seconds < expiry.timestamp()


# ── Read surface ─────────────────────────────────────────────────────────────

class GoogleCollectionClient:
    """Read-only client for one authorised connection (Forms and/or Sheets)."""

    def __init__(self, config: FormsConfig, access_token: str) -> None:
        if not access_token:
            raise FormsIntegrationError("NO_ACCESS_TOKEN", "This connection has no usable access token.", 401)
        self.config = config
        self.access_token = access_token

    # -- plumbing ---------------------------------------------------------
    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict:
        query = f"?{urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, '')})}"
        status, payload = _request(
            f"{url}{query}",
            headers={"authorization": f"Bearer {self.access_token}", "accept": "application/json"},
            timeout=self.config.request_timeout_seconds,
        )
        if status >= 400:
            raise FormsIntegrationError(*_map_error(status, payload))
        return payload

    # -- Forms API --------------------------------------------------------
    def get_form(self, form_id: str) -> dict:
        return self._get(f"{self.config.forms_api_base}/forms/{urllib.parse.quote(form_id)}")

    def iter_responses(self, form_id: str, *, page_size: int = 100, max_pages: int = 10) -> tuple[list[dict], str]:
        """Collect up to ``page_size * max_pages`` responses.

        The Forms API has no server-side "since" filter that is safe to assume
        without verifying its filter grammar live, so the connector pages and
        de-duplicates locally against ``form_responses`` — the same stance taken
        in the design's honest-limits section rather than guessing syntax.
        """
        collected: list[dict] = []
        page_token = ""
        pages = 0
        base = f"{self.config.forms_api_base}/forms/{urllib.parse.quote(form_id)}/responses"
        while pages < max(1, max_pages):
            payload = self._get(base, {"pageSize": min(500, max(1, page_size)), "pageToken": page_token})
            collected.extend([r for r in (payload.get("responses") or []) if isinstance(r, dict)])
            page_token = str(payload.get("nextPageToken") or "")
            pages += 1
            if not page_token or len(collected) >= self.config.max_responses_per_sync:
                break
        return collected[: self.config.max_responses_per_sync], page_token

    # -- Sheets API (the linked response sheet path) ----------------------
    def sheet_rows(self, spreadsheet_id: str, range_name: str = "") -> tuple[list[str], list[list[str]]]:
        target = urllib.parse.quote(range_name or "A1:ZZ1000")
        payload = self._get(
            f"{self.config.sheets_api_base}/spreadsheets/{urllib.parse.quote(spreadsheet_id)}/values/{target}"
        )
        rows: Iterable[list[Any]] = payload.get("values") or []
        matrix = [["" if c is None else str(c) for c in row] for row in rows]
        if not matrix:
            return [], []
        return matrix[0], matrix[1:]


def _map_error(status: int, payload: dict) -> tuple[str, str, int]:
    """Google error → (code, operator message, http status). Never a fake success."""
    err = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    message = str(err.get("message") or payload.get("error_description") or payload.get("error") or f"HTTP {status}")
    if status == 401:
        return "GOOGLE_UNAUTHENTICATED", "Google rejected the access token — reconnect this form.", 401
    if status == 403:
        return (
            "GOOGLE_FORBIDDEN",
            "Google refused this read. The form must be owned by, or shared with, the account that authorised it, "
            "and the OAuth client must have the Forms/Sheets APIs enabled.",
            403,
        )
    if status == 404:
        return "FORM_NOT_FOUND", "No form (or response sheet) exists at that id for this account.", 404
    if status == 429:
        return "GOOGLE_RATE_LIMITED", "Google rate limited this workspace. Retry the sync shortly.", 429
    return "GOOGLE_REQUEST_FAILED", message[:280], 502
