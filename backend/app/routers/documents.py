"""Documents API — upload, list, download, export, deletion (Phases 1, 4, 5).

Data ownership contract: documents belong to the customer's workspace.
Every endpoint is workspace-scoped (``org_id``), role-checked through
``require_permission`` and recorded in the audit trail. Deletion is soft by
default (recoverable) with an explicit ``hard=true`` option for complete,
immediate removal from storage.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from kulima.core.audit import record_event
from kulima.core.documents.repository import DocumentRepository
from kulima.core.orgs.models import Permission
from kulima.core.security.encryption import decrypt_bytes, is_encrypted
from kulima.db import IntelligenceRepository

from ..core.auth import OrgContext, get_current_org, require_permission
from ..core.rate_limit import check_rate_limit
from ..schemas.dtos import DocumentResponse
from ..services import assessment_adapter
from ..services.document_adapter import UPLOAD_DIR, InvalidUploadError, save_uploaded_file
from ..services.run_repository import RunRepository

router = APIRouter()

_run_repo = RunRepository()
_brief_repo = IntelligenceRepository()

_doc_repo_cache: DocumentRepository | None = None


def _doc_repo() -> DocumentRepository:
    global _doc_repo_cache
    if _doc_repo_cache is None:
        _doc_repo_cache = DocumentRepository()
    return _doc_repo_cache


def _resolve_run_owner(run_str: str) -> tuple[bool, Optional[str], Optional[str]]:
    """Return (found, owner_user_id, owner_org_id) for a run reference."""
    live_info = _run_repo.get_run(run_str)
    if live_info is not None:
        return True, live_info.get("user_id"), live_info.get("org_id")
    if run_str.isdigit():
        db_run = _brief_repo.get_run(int(run_str))
        if db_run is not None:
            return True, db_run.get("user_id"), db_run.get("org_id")
    return False, None, None


def _owned_document(document_id: str, current: OrgContext) -> dict:
    """Fetch a document, enforcing workspace membership (404 when foreign)."""
    doc = _doc_repo().get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Document not found"})
    org_id = doc.get("orgId")
    if org_id is not None:
        if org_id != current.org_id:
            raise HTTPException(status_code=404, detail={"error": True, "message": "Document not found"})
    elif doc.get("uploadedBy") and doc.get("uploadedBy") not in current.member_ids():
        # Legacy unclaimed row created by someone else — treat as absent.
        raise HTTPException(status_code=404, detail={"error": True, "message": "Document not found"})
    return doc


def _read_document_bytes(doc: dict) -> bytes | None:
    """Read the stored file, decrypting when at-rest encryption was applied."""
    storage_path = doc.get("storagePath")
    if not storage_path:
        return None
    target = (UPLOAD_DIR / str(storage_path)).resolve()
    if UPLOAD_DIR.resolve() not in target.parents or not target.is_file():
        return None
    blob = target.read_bytes()
    if is_encrypted(doc.get("encryption")):
        try:
            return decrypt_bytes(blob)
        except Exception:  # noqa: BLE001 — wrong key / corrupt blob
            raise HTTPException(
                status_code=503,
                detail={"error": True, "message": "This document could not be decrypted. Check the storage encryption key."},
            )
    return blob


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    runId: Optional[str] = Form(None),
    current: OrgContext = Depends(require_permission(Permission.MANAGE_DOCUMENTS)),
):
    check_rate_limit(current.user_id, "documents:upload")

    assessment_id: Optional[str] = None
    if runId:
        run_str = str(runId).strip()
        run_found, existing_user_id, existing_org_id = _resolve_run_owner(run_str)

        # Workspace isolation: the run must belong to this workspace (same-org
        # members share visibility; shared demo rows with no owner stay open).
        if run_found and existing_org_id is not None and existing_org_id != current.org_id:
            raise HTTPException(status_code=403, detail={"error": True, "message": "Access denied: run belongs to another workspace"})
        if run_found and existing_org_id is None and existing_user_id is not None and existing_user_id not in current.member_ids():
            raise HTTPException(status_code=403, detail={"error": True, "message": "Access denied: run belongs to another user"})

        # Bind post-run uploads to the assessment that produced the run.
        try:
            ctx = assessment_adapter.resolve_assessment_for_brief(
                "", "", run_id=run_str, user_id=current.user_id, org_id=current.org_id
            )
            if ctx is not None:
                assessment_id = ctx.assessment_id
        except Exception:  # noqa: BLE001 — binding is best-effort
            assessment_id = None

    try:
        res = save_uploaded_file(
            file,
            run_uuid=runId,
            user_id=current.user_id,
            org_id=current.org_id,
            assessment_id=assessment_id,
        )
    except InvalidUploadError as exc:
        msg = str(exc)
        if msg == "file_too_large":
            raise HTTPException(status_code=400, detail="File too large. Maximum upload size is 25 MB. Please compress or split the document.")
        raise HTTPException(status_code=400, detail="Unsupported file type. Accepted: PDF, DOCX, PPTX, XLSX, CSV, TXT.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return res


@router.get("/")
async def list_documents(
    runId: Optional[str] = Query(default=None),
    assessmentId: Optional[str] = Query(default=None),
    includeDeleted: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Workspace document inventory with retention/security metadata."""
    run_filter = int(runId) if (runId or "").strip().isdigit() else None
    docs = _doc_repo().list_documents(
        org_id=current.org_id,
        run_id=run_filter,
        assessment_id=assessmentId,
        include_deleted=includeDeleted,
        limit=limit,
    )
    return {
        "documents": docs,
        "stats": _doc_repo().document_stats(org_id=current.org_id),
        "orgId": current.org_id,
    }


@router.get("/export")
async def export_documents(
    runId: Optional[str] = Query(default=None),
    assessmentId: Optional[str] = Query(default=None),
    current: OrgContext = Depends(require_permission(Permission.EXPORT)),
):
    """Download every workspace document as a ZIP bundle (Phase 1: export)."""
    run_filter = int(runId) if (runId or "").strip().isdigit() else None
    docs = _doc_repo().list_documents(
        org_id=current.org_id,
        run_id=run_filter,
        assessment_id=assessmentId,
        limit=1000,
    )
    manifest = {
        "orgId": current.org_id,
        "exportedBy": current.user_id,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "documentCount": len(docs),
        "documents": [
            {
                "id": d.get("id"),
                "filename": d.get("filename"),
                "mimeType": d.get("mimeType"),
                "sizeBytes": d.get("sizeBytes"),
                "sha256": d.get("sha256"),
                "uploadedAt": d.get("uploadedAt"),
                "expiresAt": d.get("expiresAt"),
                "visibility": d.get("visibility"),
            }
            for d in docs
        ],
    }
    bundle = io.BytesIO()
    exported = 0
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for doc in docs:
            blob = _read_document_bytes(doc)
            if blob is None:
                continue
            safe_name = f"{doc.get('id')}__{doc.get('filename') or 'document'}"
            archive.writestr(safe_name, blob)
            exported += 1
    payload = bundle.getvalue()
    record_event(
        "document.exported",
        org_id=current.org_id,
        user_id=current.user_id,
        run_id=runId,
        assessment_id=assessmentId,
        metadata={"documents": len(docs), "filesIncluded": exported, "bytes": len(payload), "format": "zip"},
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="kulima-documents-{stamp}.zip"'},
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    return _owned_document(document_id, current)


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current: OrgContext = Depends(require_permission(Permission.VIEW)),
):
    """Download a single stored document (audited, decrypted in-memory)."""
    check_rate_limit(current.user_id, "documents:download")
    doc = _owned_document(document_id, current)
    if doc.get("deletedAt"):
        raise HTTPException(status_code=404, detail={"error": True, "message": "Document not found"})
    if DocumentRepository.is_expired(doc):
        raise HTTPException(
            status_code=410,
            detail={"error": True, "message": "This document has passed its retention window and is no longer available."},
        )
    blob = _read_document_bytes(doc)
    if blob is None:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Stored file not found"})
    record_event(
        "document.downloaded",
        org_id=current.org_id,
        user_id=current.user_id,
        run_id=doc.get("runId"),
        assessment_id=doc.get("assessmentId"),
        document_id=doc.get("id"),
        metadata={"filename": doc.get("filename"), "sizeBytes": doc.get("sizeBytes")},
    )
    filename = str(doc.get("filename") or "document")
    return Response(
        content=blob,
        media_type=doc.get("mimeType") or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    hard: bool = Query(default=False, description="true = permanent purge; false = soft delete"),
    current: OrgContext = Depends(require_permission(Permission.DELETE_DATA)),
):
    """Delete a document. Soft by default; ``hard=true`` removes it completely."""
    check_rate_limit(current.user_id, "documents:delete")
    doc = _owned_document(document_id, current)

    if hard:
        storage_path = doc.get("storagePath")
        file_removed = False
        if storage_path:
            target = (UPLOAD_DIR / str(storage_path)).resolve()
            try:
                if target.is_file() and UPLOAD_DIR.resolve() in target.parents:
                    target.unlink()
                    file_removed = True
            except OSError:
                pass
        removed = _doc_repo().hard_delete_document(document_id)
        if not removed:
            raise HTTPException(status_code=404, detail={"error": True, "message": "Document not found"})
        record_event(
            "document.deleted",
            org_id=current.org_id,
            user_id=current.user_id,
            run_id=doc.get("runId"),
            assessment_id=doc.get("assessmentId"),
            document_id=document_id,
            metadata={"mode": "hard", "filename": doc.get("filename"), "fileRemoved": file_removed},
        )
        return {"deleted": True, "mode": "hard", "documentId": document_id, "fileRemoved": file_removed}

    soft = _doc_repo().soft_delete_document(document_id, deleted_by=current.user_id)
    if not soft:
        raise HTTPException(status_code=404, detail={"error": True, "message": "Document not found"})
    record_event(
        "document.deleted",
        org_id=current.org_id,
        user_id=current.user_id,
        run_id=doc.get("runId"),
        assessment_id=doc.get("assessmentId"),
        document_id=document_id,
        metadata={"mode": "soft", "filename": doc.get("filename")},
    )
    return {"deleted": True, "mode": "soft", "documentId": document_id, "recoverable": True}

