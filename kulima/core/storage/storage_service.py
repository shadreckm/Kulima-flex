"""Supabase Storage service for document management.

This service provides a unified interface for document storage operations
using Supabase Storage with organization-level isolation and RBAC enforcement.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, BinaryIO

from kulima.config import get_settings

_log = logging.getLogger(__name__)

# Lazy import Supabase client (only when needed)
_supabase_available = False
try:
    from supabase import create_client, Client
    _supabase_available = True
except ImportError:
    _log.debug("Supabase client not available - storage service disabled")


class StorageService:
    """Supabase Storage service for document operations.

    This service manages document uploads, downloads, deletion, and signed URL
    generation with organization-level isolation.
    """

    def __init__(self):
        settings = get_settings()

        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError(
                "Supabase URL and key required for storage service. "
                "Set SUPABASE_URL and SUPABASE_KEY environment variables."
            )

        if not _supabase_available:
            raise RuntimeError(
                "Supabase client library not installed. "
                "Install with: pip install supabase"
            )

        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self.bucket_name = settings.storage_bucket_name or "kulima-documents"

    def _build_path(
        self,
        org_id: str,
        assessment_id: str,
        document_id: str,
        filename: str
    ) -> str:
        """Build storage path for a document.

        Path structure: {org_id}/{assessment_id}/{document_id}/{filename}

        Args:
            org_id: Organization ID
            assessment_id: Assessment ID
            document_id: Document ID
            filename: Original filename

        Returns:
            Storage path string
        """
        return f"{org_id}/{assessment_id}/{document_id}/{filename}"

    def upload_file(
        self,
        org_id: str,
        assessment_id: str,
        document_id: str,
        filename: str,
        file_data: BinaryIO,
        content_type: str,
    ) -> str:
        """Upload a file to Supabase Storage.

        Args:
            org_id: Organization ID for isolation
            assessment_id: Assessment ID
            document_id: Document ID
            filename: Original filename
            file_data: File data as binary stream
            content_type: MIME type of the file

        Returns:
            Storage path of the uploaded file

        Raises:
            RuntimeError: If upload fails
        """
        path = self._build_path(org_id, assessment_id, document_id, filename)

        try:
            self.client.storage.from_(self.bucket_name).upload(
                path=path,
                file=file_data,
                file_options={"content-type": content_type}
            )
            _log.info("Uploaded file to storage: %s", path)
            return path
        except Exception as exc:
            _log.error("Failed to upload file %s: %s", path, exc)
            raise RuntimeError(f"Storage upload failed: {exc}") from exc

    def download_file(self, path: str) -> bytes:
        """Download a file from Supabase Storage.

        Args:
            path: Storage path of the file

        Returns:
            File content as bytes

        Raises:
            RuntimeError: If download fails
        """
        try:
            response = self.client.storage.from_(self.bucket_name).download(path)
            return response
        except Exception as exc:
            _log.error("Failed to download file %s: %s", path, exc)
            raise RuntimeError(f"Storage download failed: {exc}") from exc

    def delete_file(self, path: str) -> None:
        """Delete a file from Supabase Storage.

        Args:
            path: Storage path of the file

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            self.client.storage.from_(self.bucket_name).remove([path])
            _log.info("Deleted file from storage: %s", path)
        except Exception as exc:
            _log.error("Failed to delete file %s: %s", path, exc)
            raise RuntimeError(f"Storage deletion failed: {exc}") from exc

    def generate_signed_url(
        self,
        path: str,
        expires_in_seconds: int = 3600
    ) -> str:
        """Generate a signed URL for temporary file access.

        Args:
            path: Storage path of the file
            expires_in_seconds: URL expiry time in seconds (default: 1 hour)

        Returns:
            Signed URL string

        Raises:
            RuntimeError: If URL generation fails
        """
        try:
            url = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=path,
                expires_in=expires_in_seconds
            )
            return url
        except Exception as exc:
            _log.error("Failed to generate signed URL for %s: %s", path, exc)
            raise RuntimeError(f"Signed URL generation failed: {exc}") from exc

    def list_files(
        self,
        org_id: str,
        assessment_id: Optional[str] = None
    ) -> list[str]:
        """List files in an organization or assessment folder.

        Args:
            org_id: Organization ID
            assessment_id: Optional assessment ID to filter by

        Returns:
            List of file paths

        Raises:
            RuntimeError: If listing fails
        """
        prefix = f"{org_id}/"
        if assessment_id:
            prefix += f"{assessment_id}/"

        try:
            result = self.client.storage.from_(self.bucket_name).list(prefix=prefix)
            return [item["name"] for item in result]
        except Exception as exc:
            _log.error("Failed to list files in %s: %s", prefix, exc)
            raise RuntimeError(f"File listing failed: {exc}") from exc

    def get_file_info(self, path: str) -> dict:
        """Get metadata for a file in storage.

        Args:
            path: Storage path of the file

        Returns:
            Dictionary with file metadata (size, content_type, etc.)

        Raises:
            RuntimeError: If metadata retrieval fails
        """
        try:
            # Supabase doesn't have a direct get_metadata, so we list and filter
            # This is a workaround - in production, use direct metadata API if available
            folder = "/".join(path.split("/")[:-1])
            files = self.client.storage.from_(self.bucket_name).list(prefix=folder)
            for file_info in files:
                if file_info["name"] == path:
                    return file_info
            raise RuntimeError(f"File not found: {path}")
        except Exception as exc:
            _log.error("Failed to get file info for %s: %s", path, exc)
            raise RuntimeError(f"File info retrieval failed: {exc}") from exc
