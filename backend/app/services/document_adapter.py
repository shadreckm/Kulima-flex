from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import UploadFile
from kulima.core.documents.models import Document, DocumentType
from kulima.core.documents.repository import DocumentRepository
from .run_repository import RunRepository

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Upload constraints (pre-beta defaults)
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
}
# Explicitly disallowed extensions, even if MIME type is spoofed
DISALLOWED_EXTENSIONS = {".exe", ".bat", ".cmd", ".js", ".ps1", ".msi"}


class InvalidUploadError(Exception):
    """Raised when an uploaded document violates security constraints."""


_doc_repo = DocumentRepository()
_run_repo = RunRepository()


def save_uploaded_file(file: UploadFile, run_uuid: Optional[str] = None, user_id: Optional[str] = None) -> dict:
    """Persist an uploaded file and register it as a Document.

    Security constraints:
    - Max size: 20MB
    - Allowed MIME types only
    - Common executable/script extensions are rejected
    """

    # Basic metadata
    filename = file.filename
    ext = Path(filename).suffix.lower()
    mime_type = file.content_type or "application/octet-stream"

    # MIME/type allowlist + extension denylist
    if mime_type not in ALLOWED_MIME_TYPES or ext in DISALLOWED_EXTENSIONS:
        raise InvalidUploadError("unsupported_file_type")

    # Read content once so we can enforce max size before writing to disk
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise InvalidUploadError("file_too_large")

    doc_id = str(uuid.uuid4())
    target_name = f"{doc_id}{ext}"
    target_path = UPLOAD_DIR / target_name

    # Write file content
    with target_path.open("wb") as out_f:
        out_f.write(content)

    # Resolve run_uuid (api_runs.run_id) to the underlying intelligence_runs.id
    # so that documents are correctly linked to intelligence runs. This allows
    # Evidence Integrity, Trust Graph, and Signals pipelines to treat uploaded
    # documents as part of the same corpus as OSINT.
    resolved_run_id: Optional[int] = None
    if run_uuid:
        info = _run_repo.get_run(run_uuid)
        if info is not None:
            db_id = info.get("db_id")
            if db_id is not None:
                try:
                    resolved_run_id = int(db_id)
                except (TypeError, ValueError):
                    resolved_run_id = None

    # Build Document model and persist minimal metadata
    doc = Document(
        id=doc_id,
        filename=filename,
        mime_type=mime_type,
        doc_type=DocumentType.GENERIC,
        uploaded_by=user_id,
    )
    _doc_repo.save_document(resolved_run_id, doc)

    # Upload audit log
    logger.info(
        "document_upload",
        extra={
            "user_id": user_id,
            "run_uuid": run_uuid,
            "resolved_run_id": resolved_run_id,
            "filename": filename,
            "timestamp": datetime.utcnow().isoformat(),
            "size_bytes": len(content),
        },
    )

    return {"id": doc_id, "name": filename, "url": f"/uploads/{target_name}"}
