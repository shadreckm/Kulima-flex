"""Encrypted storage metadata + optional at-rest encryption (Phase 5).

Every stored document gets a metadata envelope recorded in the ``documents``
table (``encryption_json``):

    {
      "scheme": "aes-256-gcm" | "provider-disk-at-rest",
      "algorithm": "AES-256-GCM" | None,
      "encrypted": bool,
      "sha256": "<hex digest>",
      "sizeBytes": int,
      "keyRef": "<sha256(key)[:12]>" | None,   # never the key itself
      "createdAt": "<iso>"
    }

At-rest encryption is applied when BOTH are true:

1. the ``cryptography`` package is importable, and
2. ``KULIMA_DOC_ENCRYPTION_KEY`` is configured.

Otherwise files rely on provider disk encryption (Render/managed volume) and
the metadata records that fact explicitly — the gap is visible, never silent.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

SCHEME_PLAIN = "provider-disk-at-rest"
SCHEME_AESGCM = "aes-256-gcm"


class EncryptionUnavailable(RuntimeError):
    """Raised when encrypted storage is requested but cannot be provided."""


def encryption_key() -> bytes | None:
    """Derive a 32-byte key from KULIMA_DOC_ENCRYPTION_KEY (if configured)."""
    raw = os.environ.get("KULIMA_DOC_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encryption_key_configured() -> bool:
    return encryption_key() is not None


def cryptography_available() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def key_ref() -> str | None:
    key = encryption_key()
    if key is None:
        return None
    return hashlib.sha256(key).hexdigest()[:12]


def is_encrypted(metadata: dict | None) -> bool:
    return bool(metadata and metadata.get("encrypted"))


def build_storage_metadata(data: bytes, *, extra: dict | None = None) -> dict:
    """Create the storage metadata envelope for a document payload."""
    encrypted = cryptography_available() and encryption_key() is not None
    metadata = {
        "scheme": SCHEME_AESGCM if encrypted else SCHEME_PLAIN,
        "algorithm": "AES-256-GCM" if encrypted else None,
        "encrypted": encrypted,
        "sha256": hashlib.sha256(data).hexdigest(),
        "sizeBytes": len(data),
        "keyRef": key_ref() if encrypted else None,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        metadata.update(extra)
    return metadata


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt with AES-256-GCM; output = 12-byte nonce || ciphertext."""
    key = encryption_key()
    if key is None:
        raise EncryptionUnavailable("KULIMA_DOC_ENCRYPTION_KEY is not configured")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:  # noqa: BLE001
        raise EncryptionUnavailable("cryptography package is not installed") from exc
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt_bytes(blob: bytes) -> bytes:
    """Reverse ``encrypt_bytes`` (nonce-prefixed AES-256-GCM)."""
    key = encryption_key()
    if key is None:
        raise EncryptionUnavailable("KULIMA_DOC_ENCRYPTION_KEY is not configured")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:  # noqa: BLE001
        raise EncryptionUnavailable("cryptography package is not installed") from exc
    nonce, ciphertext = blob[:12], blob[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)
