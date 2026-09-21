"""Tavily egress guard — Phase 6 (Tavily Safety).

Contract: an external research provider may receive ONLY

- Organization Name
- Founder Name
- Sector
- Country
- Public Company Information

and never the full uploaded document, financial statements, customer data,
or any other sensitive content.

Defence in depth: the guard is applied inside ``ResearchEngine.search`` —
the single egress choke point — so even a future caller that assembles a
query from raw document text cannot leak it to Tavily. Sensitive tokens
(emails, phone numbers, monetary amounts, long digit sequences, sensitive
document phrases) are redacted and the query is length-capped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

ALLOWED_RESEARCH_FIELDS: tuple[str, ...] = (
    "organization_name",
    "founder_name",
    "sector",
    "country",
    "public_company_info",
)

MAX_QUERY_CHARS = 300
MAX_FIELD_CHARS = 120


class SensitiveQueryError(ValueError):
    """Raised when a query cannot be sanitised for external egress."""


# ── Redaction patterns (PII & sensitive financial content) ──────────────────

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+\d[\d\s().\-]{6,}\d|\b0\d{2,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4}\b)")
_CURRENCY_RE = re.compile(
    r"(?:USD|KES|MWK|ZAR|NGN|GHS|EUR|GBP|TZS|UGX|ZMW|RWF|\$|€|£|¥)\s?\d[\d,._]*"
    r"(?:\s?(?:million|billion|m|bn|k))?",
    re.IGNORECASE,
)
_LONG_DIGITS_RE = re.compile(r"\b\d{6,}\b")
_URL_CREDENTIALS_RE = re.compile(r"https?://[^\s/]+:[^\s/@]+@\S+")

_SENSITIVE_PHRASES = (
    "financial statement",
    "balance sheet",
    "income statement",
    "cash flow statement",
    "bank account",
    "account number",
    "swift code",
    "iban",
    "tax return",
    "payroll",
    "salary",
    "invoice",
    "confidential",
    "internal memo",
    "customer data",
    "shareholder register",
    "cap table",
)
_SENSITIVE_RE = re.compile(
    "|".join(re.escape(p) for p in _SENSITIVE_PHRASES),
    re.IGNORECASE,
)

_REDACTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", _EMAIL_RE),
    ("url_credentials", _URL_CREDENTIALS_RE),
    ("phone", _PHONE_RE),
    ("amount", _CURRENCY_RE),
    ("long_number", _LONG_DIGITS_RE),
    ("sensitive_phrase", _SENSITIVE_RE),
)


@dataclass
class GuardReport:
    """Outcome of sanitising one outbound query."""

    query: str
    redactions: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    original_length: int = 0

    @property
    def safe(self) -> bool:
        return not self.redactions and not self.truncated

    @property
    def redaction_total(self) -> int:
        return sum(self.redactions.values())


class TavilyGuard:
    """Sanitises every outbound external-research payload."""

    allowed_fields = ALLOWED_RESEARCH_FIELDS
    max_query_chars = MAX_QUERY_CHARS
    max_field_chars = MAX_FIELD_CHARS

    # ── Public API ───────────────────────────────────────────────────────

    def sanitize_field(self, value: str | None, *, max_len: int | None = None) -> str:
        """Clean a single allowed field (name, sector, country)."""
        if not value:
            return ""
        cleaned = " ".join(str(value).split())
        report = self._redact(cleaned)
        cleaned = report.query
        return cleaned[: max_len or self.max_field_chars].strip()

    def build_query(
        self,
        *,
        organization_name: str = "",
        founder_name: str = "",
        sector: str = "",
        country: str = "",
        public_company_info: str = "",
    ) -> str:
        """Assemble a metadata-only query from the five allowed fields."""
        parts = [
            self.sanitize_field(organization_name),
            self.sanitize_field(founder_name),
            self.sanitize_field(sector),
            self.sanitize_field(country),
            self.sanitize_field(public_company_info),
        ]
        return " ".join(p for p in parts if p).strip()

    def inspect(self, query: str) -> GuardReport:
        """Redact sensitive tokens and cap length. Never raises."""
        original = query or ""
        report = self._redact(original)
        if len(report.query) > self.max_query_chars:
            report.query = report.query[: self.max_query_chars].rstrip()
            report.truncated = True
        report.original_length = len(original)
        return report

    def sanitize_query(self, query: str) -> str:
        """Return the safe query string sent to external providers."""
        report = self.inspect(query)
        if report.redaction_total or report.truncated:
            _log.info(
                "tavily_guard_sanitized redactions=%s truncated=%s len=%s->%s",
                report.redactions,
                report.truncated,
                report.original_length,
                len(report.query),
            )
        return report.query

    def assert_safe(self, query: str) -> str:
        """Strict mode: raise when the query still carries sensitive content."""
        report = self.inspect(query)
        if not report.safe:
            raise SensitiveQueryError(
                f"Query contains sensitive content ({report.redactions}) and was blocked from external egress."
            )
        return report.query

    def is_safe(self, query: str) -> bool:
        return self.inspect(query).safe

    # ── Internals ────────────────────────────────────────────────────────

    def _redact(self, query: str) -> GuardReport:
        report = GuardReport(query=query or "")
        for label, pattern in _REDACTION_RULES:
            cleaned, count = pattern.subn(f"[redacted-{label}]", report.query)
            if count:
                report.query = cleaned
                report.redactions[label] = report.redactions.get(label, 0) + count
        return report


# Shared instance — imported by ResearchEngine (single egress choke point).
guard = TavilyGuard()
