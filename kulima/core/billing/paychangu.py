"""PayChangu client (Phase 8) — stdlib-only, safe by default.

- ``initiate_payment`` — POST /payment, returns the hosted checkout URL.
- ``verify_payment``   — GET /verify-payment/{tx_ref}.
- ``verify_webhook``   — HMAC-SHA256(raw body, webhook secret), timing-safe
  comparison against the ``Signature`` header (hex or base64 accepted).

When ``PAYCHANGU_SECRET_KEY`` is not configured the client reports
``configured == False`` and callers return a clean 503 instead of failing
mid-payment. No new dependencies: urllib + hmac only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.request
import uuid

_log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.paychangu.com"


class PayChanguError(RuntimeError):
    def __init__(self, code: str, message: str = "", *, status: int | None = None):
        self.code = code
        self.status = status
        super().__init__(message or code)


class PayChanguConfig:
    def __init__(
        self,
        secret_key: str = "",
        webhook_secret: str = "",
        currency: str = "USD",
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 20,
    ) -> None:
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.currency = currency
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "PayChanguConfig":
        return cls(
            secret_key=os.getenv("PAYCHANGU_SECRET_KEY", "").strip(),
            webhook_secret=os.getenv("PAYCHANGU_WEBHOOK_SECRET", "").strip(),
            currency=os.getenv("PAYCHANGU_CURRENCY", "USD").strip().upper() or "USD",
            base_url=os.getenv("PAYCHANGU_API_BASE", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        )


class PayChanguClient:
    def __init__(self, config: PayChanguConfig | None = None) -> None:
        self.config = config or PayChanguConfig.from_env()

    # ── Capabilities ─────────────────────────────────────────────────────

    @property
    def configured(self) -> bool:
        return bool(self.config.secret_key)

    @property
    def webhook_verification_available(self) -> bool:
        return bool(self.config.webhook_secret)

    @staticmethod
    def new_tx_ref(prefix: str = "kulima") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:16]}"

    # ── Payments ─────────────────────────────────────────────────────────

    def initiate_payment(
        self,
        amount: float,
        *,
        tx_ref: str,
        plan: str | None = None,
        org_id: str | None = None,
        callback_url: str = "",
        return_url: str = "",
        description: str = "",
        customer_email: str | None = None,
        customer_name: str | None = None,
        currency: str | None = None,
    ) -> dict:
        if not self.configured:
            raise PayChanguError("not_configured", "PAYCHANGU_SECRET_KEY is not configured")
        body = {
            "amount": f"{amount:.2f}",
            "currency": (currency or self.config.currency),
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization": {
                "title": "Kulima FLEX Subscription",
                "description": description or f"Kulima FLEX {plan or ''} subscription".strip(),
            },
        }
        if customer_email:
            body["customer"] = {"email": customer_email, "name": customer_name or ""}
        if org_id or plan:
            body["meta"] = {"orgId": org_id, "plan": plan}
        payload = self._request("POST", "/payment", body)
        checkout_url = (payload.get("data") or {}).get("checkout_url") if isinstance(payload, dict) else None
        return {
            "txRef": tx_ref,
            "checkoutUrl": checkout_url,
            "status": (payload.get("data") or {}).get("status") if isinstance(payload, dict) else None,
            "raw": payload,
        }

    def verify_payment(self, tx_ref: str) -> dict:
        if not self.configured:
            raise PayChanguError("not_configured", "PAYCHANGU_SECRET_KEY is not configured")
        return self._request("GET", f"/verify-payment/{urllib.parse.quote(str(tx_ref), safe='')}")

    # ── Webhooks ─────────────────────────────────────────────────────────

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> bool:
        """Constant-time HMAC-SHA256 verification of an inbound webhook."""
        secret = self.config.webhook_secret
        if not secret or not signature:
            return False
        try:
            digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256)
            candidates = {digest.hexdigest().lower(), base64.b64encode(digest.digest()).decode("utf-8")}
            provided = signature.strip()
            return any(hmac.compare_digest(candidate, provided) or hmac.compare_digest(candidate, provided.lower()) for candidate in candidates)
        except Exception as exc:  # noqa: BLE001
            _log.warning("paychangu_webhook_verify_failed error=%s", exc)
            return False

    # ── Internals ────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        import urllib.parse  # local import keeps module import side-effect free

        url = f"{self.config.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.config.secret_key}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise PayChanguError("http_error", f"PayChangu returned HTTP {exc.code}: {raw[:300]}", status=exc.code) from exc
        except Exception as exc:  # noqa: BLE001 — network, DNS, timeout
            raise PayChanguError("request_failed", f"PayChangu request failed: {exc}") from exc
        try:
            return json.loads(raw) if raw else {}
        except ValueError as exc:
            raise PayChanguError("invalid_response", "PayChangu returned a non-JSON response") from exc
