"""Document & data security primitives (Phase 5).

- ``tavily_guard`` — single choke point that guarantees Tavily (and any
  external research provider) only ever receives public, metadata-only
  queries: organization name, founder name, sector, country, and public
  company information.
- ``encryption``   — encrypted storage metadata (scheme, algorithm, hash,
  size, key reference) with optional AES-256-GCM at-rest encryption when
  the ``cryptography`` package and ``KULIMA_DOC_ENCRYPTION_KEY`` are present.
"""

from .encryption import (
    EncryptionUnavailable,
    build_storage_metadata,
    decrypt_bytes,
    encrypt_bytes,
    encryption_key_configured,
    is_encrypted,
)
from .tavily_guard import (
    ALLOWED_RESEARCH_FIELDS,
    SensitiveQueryError,
    TavilyGuard,
    guard,
)

__all__ = [
    "ALLOWED_RESEARCH_FIELDS",
    "SensitiveQueryError",
    "TavilyGuard",
    "guard",
    "EncryptionUnavailable",
    "build_storage_metadata",
    "decrypt_bytes",
    "encrypt_bytes",
    "encryption_key_configured",
    "is_encrypted",
]
