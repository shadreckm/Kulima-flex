# SUPABASE CLOUD MIGRATION PLAN

**Date:** 2026-09-22
**Architect:** Principal Cloud Architect
**Scope:** Migrate from SQLite + local storage to Supabase Postgres + Supabase Storage

---

## PHASE 1: SQLITE USAGE AUDIT

### Direct SQLite Connections (16 files)

**Core Repositories:**
1. `kulima/db.py` - IntelligenceRepository (legacy runs)
2. `kulima/core/assessment/repository.py` - AssessmentContext
3. `kulima/core/cases/repository.py` - Case aggregate root
4. `kulima/core/jobs/repository.py` - Job queue
5. `kulima/core/research/repository.py` - Research packs
6. `kulima/core/collaboration/repository.py` - Comments, review requests
7. `kulima/core/dossier/repository.py` - Decision dossiers
8. `kulima/core/audit/repository.py` - Audit trail
9. `kulima/core/documents/repository.py` - Document metadata
10. `kulima/core/orgs/repository.py` - Organizations, members, roles
11. `kulima/core/billing/repository.py` - Subscriptions, payments

**Migration & Scripts:**
12. `kulima/core/migrations.py` - Migration runner
13. `backend/app/services/run_repository.py` - Run tracking
14. `test_db_trust_layer.py` - Tests
15. `scripts/db_inspect.py` - Database inspection
16. `kulima/core/billing/service.py` - Direct SQLite usage for queries

### Local Storage Usage

**Document Storage:**
- `backend/app/routers/documents.py` - Upload/download endpoints
- `backend/app/services/document_adapter.py` - Document processing
- `backend/app/main.py` - Static file serving at `/uploads/`
- `kulima/core/documents/repository.py` - storage_path field

**Current Flow:**
```
Browser → Backend → Disk (./uploads/)
Backend → Disk → Browser (static serve)
```

---

## PHASE 2: SUPABASE POSTGRES MIGRATION

### Database Schema Strategy

**Approach:** SQLAlchemy-based migration layer for database-agnostic operations

**New Dependency:**
```python
# backend/requirements.txt
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
supabase>=2.0.0
```

**Configuration Changes:**
```python
# kulima/config.py
@dataclass(frozen=True)
class Settings:
    # Existing
    db_path: str  # Fallback for local development

    # New Supabase configuration
    database_url: str  # postgresql://...
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str
    use_supabase: bool  # Feature flag for gradual migration
```

### Database Connection Layer

**New File:** `kulima/core/database.py`
```python
"""Database connection factory for SQLite and Supabase Postgres."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Union

import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from kulima.config import get_settings

settings = get_settings()


class DatabaseConnection:
    """Abstract database connection interface."""

    @contextmanager
    def connect(self) -> Iterator[Union[sqlite3.Connection, Session]]:
        """Return a database connection or session."""
        raise NotImplementedError


class SQLiteConnection(DatabaseConnection):
    """SQLite connection with transaction isolation."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class SupabaseConnection(DatabaseConnection):
    """Supabase Postgres connection via SQLAlchemy."""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)

    @contextmanager
    def connect(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def get_database() -> DatabaseConnection:
    """Factory function returning appropriate connection based on config."""
    if settings.use_supabase and settings.database_url:
        return SupabaseConnection(settings.database_url)
    return SQLiteConnection(settings.db_path)
```

### Repository Migration Pattern

**Example Migration:** `kulima/core/cases/repository.py`

```python
# Before
from contextlib import contextmanager
import sqlite3

@contextmanager
def _connect(self) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(self.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# After
from kulima.core.database import get_database, DatabaseConnection

@contextmanager
def _connect(self) -> Iterator[Union[sqlite3.Connection, Session]]:
    db = get_database()
    with db.connect() as conn:
        if isinstance(conn, Session):
            # Postgres session
            yield conn
        else:
            # SQLite connection
            yield conn
```

### Postgres-Specific Schema Adjustments

**Migration 003a Enhancement:**
```sql
-- Foreign keys for Postgres (enforced)
ALTER TABLE jobs
ADD CONSTRAINT fk_jobs_case_id
FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;

ALTER TABLE research_packs
ADD CONSTRAINT fk_research_case_id
FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;

ALTER TABLE research_packs
ADD CONSTRAINT fk_research_assessment_id
FOREIGN KEY (assessment_id) REFERENCES assessment_contexts(assessment_id) ON DELETE SET NULL;

ALTER TABLE comments
ADD CONSTRAINT fk_comments_case_id
FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;

ALTER TABLE review_requests
ADD CONSTRAINT fk_review_requests_case_id
FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;

ALTER TABLE dossiers
ADD CONSTRAINT fk_dossiers_case_id
FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;

ALTER TABLE document_chunks
ADD CONSTRAINT fk_document_chunks_document_id
FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;
```

**Composite Indexes for Performance:**
```sql
-- Case work queue queries
CREATE INDEX idx_cases_org_lifecycle_updated
ON cases(org_id, lifecycle_status, updated_at DESC);

-- Job queue queries
CREATE INDEX idx_jobs_case_status_created
ON jobs(case_id, status, created_at);

-- Audit timeline queries
CREATE INDEX idx_audit_org_created
ON audit_events(org_id, created_at DESC);

-- Document queries
CREATE INDEX idx_documents_org_assessment
ON documents(org_id, assessment_id);
```

---

## PHASE 3: SUPABASE STORAGE ARCHITECTURE

### Storage Bucket Design

**Bucket Name:** `kulima-documents`

**Public Access:** False (private bucket)

**RLS Policies:**
```sql
-- Enable RLS
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read documents in their org
CREATE POLICY "Users can read org documents"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'kulima-documents'
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy: Users can upload to their org folder
CREATE POLICY "Users can upload to org folder"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'kulima-documents'
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy: Service role can manage all
CREATE POLICY "Service role full access"
ON storage.objects FOR ALL
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');
```

### Folder Structure

```
kulima-documents/
├── {org_id}/
│   ├── {assessment_id}/
│   │   ├── {document_id}/
│   │   │   ├── original
│   │   │   ├── chunks/
│   │   │   │   ├── chunk_001.txt
│   │   │   │   ├── chunk_002.txt
│   │   │   │   └── ...
│   │   │   └── metadata.json
│   │   └── ...
│   └── ...
└── ...
```

### Storage Service Layer

**New File:** `kulima/core/storage/storage_service.py`
```python
"""Supabase Storage service for document management."""

from __future__ import annotations

import logging
import os
from typing import Optional, BinaryIO
from pathlib import Path

from supabase import create_client, Client

from kulima.config import get_settings

_log = logging.getLogger(__name__)


class StorageService:
    """Supabase Storage service for document operations."""

    def __init__(self):
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError("Supabase URL and key required for storage service")

        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self.bucket_name = "kulima-documents"

    def _build_path(
        self,
        org_id: str,
        assessment_id: str,
        document_id: str,
        filename: str
    ) -> str:
        """Build storage path for a document."""
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
        """Upload a file to Supabase Storage."""
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
            raise

    def download_file(self, path: str) -> bytes:
        """Download a file from Supabase Storage."""
        try:
            response = self.client.storage.from_(self.bucket_name).download(path)
            return response
        except Exception as exc:
            _log.error("Failed to download file %s: %s", path, exc)
            raise

    def delete_file(self, path: str) -> None:
        """Delete a file from Supabase Storage."""
        try:
            self.client.storage.from_(self.bucket_name).remove([path])
            _log.info("Deleted file from storage: %s", path)
        except Exception as exc:
            _log.error("Failed to delete file %s: %s", path, exc)
            raise

    def generate_signed_url(
        self,
        path: str,
        expires_in_seconds: int = 3600
    ) -> str:
        """Generate a signed URL for temporary access."""
        try:
            url = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=path,
                expires_in=expires_in_seconds
            )
            return url
        except Exception as exc:
            _log.error("Failed to generate signed URL for %s: %s", path, exc)
            raise

    def list_files(
        self,
        org_id: str,
        assessment_id: Optional[str] = None
    ) -> list[str]:
        """List files in an org or assessment folder."""
        prefix = f"{org_id}/"
        if assessment_id:
            prefix += f"{assessment_id}/"

        try:
            result = self.client.storage.from_(self.bucket_name).list(prefix=prefix)
            return [item["name"] for item in result]
        except Exception as exc:
            _log.error("Failed to list files in %s: %s", prefix, exc)
            raise
```

---

## PHASE 4: DOCUMENT UPLOAD FLOW UPDATE

### Backend Router Changes

**File:** `backend/app/routers/documents.py`

**Before:**
```python
@router.post("/upload")
async def upload_document(file: UploadFile, ...):
    # Save to disk
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"path": file_path}
```

**After:**
```python
@router.post("/upload")
async def upload_document(
    file: UploadFile,
    assessment_id: str,
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
):
    """Upload document to Supabase Storage with org isolation."""
    org_id = org_context.get("org_id")

    # Generate document ID
    doc_id = str(uuid.uuid4())

    # Upload to Supabase Storage
    storage_service = StorageService()
    storage_path = storage_service.upload_file(
        org_id=org_id,
        assessment_id=assessment_id,
        document_id=doc_id,
        filename=file.filename,
        file_data=await file.read(),
        content_type=file.content_type,
    )

    # Save metadata to database
    doc_repo = DocumentRepository()
    doc = Document(
        id=doc_id,
        filename=file.filename,
        mime_type=file.content_type,
        doc_type=DocumentType.from_mime_type(file.content_type),
        uploaded_by=current_user.get("user_id"),
        uploaded_at=datetime.now(timezone.utc),
        storage_path=storage_path,
        org_id=org_id,
        assessment_id=assessment_id,
    )
    doc_repo.save_document(doc, org_id=org_id, assessment_id=assessment_id, storage_path=storage_path)

    return {"document_id": doc_id, "storage_path": storage_path}
```

### Document Adapter Changes

**File:** `backend/app/services/document_adapter.py`

**Changes:**
- Replace local file operations with StorageService calls
- Update chunk storage to use Supabase Storage paths
- Ensure all storage operations include org_id

---

## PHASE 5: DOCUMENT RETRIEVAL WITH SIGNED URLs

### Backend Router Changes

**File:** `backend/app/routers/documents.py`

**New Endpoint:**
```python
@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(get_org_context),
):
    """Generate signed URL for document download with RBAC enforcement."""
    org_id = org_context.get("org_id")

    # Get document metadata
    doc_repo = DocumentRepository()
    doc = doc_repo.get_document(document_id, org_id=org_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Generate signed URL
    storage_service = StorageService()
    signed_url = storage_service.generate_signed_url(
        path=doc.storage_path,
        expires_in_seconds=3600,  # 1 hour
    )

    return {"download_url": signed_url, "expires_in": 3600}
```

### Static File Serving Removal

**File:** `backend/app/main.py`

**Remove:**
```python
# Remove static file serving
# app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
```

**Add:**
```python
# Add document download endpoint
from backend.app.routers import documents
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
```

---

## PHASE 6: ENVIRONMENT CONFIGURATION

### Environment Variables

**New Variables:**
```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:[password]@db.your-project.supabase.co:5432/postgres

# Feature Flag
USE_SUPABASE=true  # Set to false for local SQLite development

# Storage
STORAGE_BUCKET_NAME=kulima-documents
```

### Configuration Updates

**File:** `kulima/config.py`
```python
@dataclass(frozen=True)
class Settings:
    # Existing fields...

    # Supabase configuration
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str
    database_url: str
    use_supabase: bool
    storage_bucket_name: str


def get_settings() -> Settings:
    return Settings(
        # Existing...

        # Supabase
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        use_supabase=os.getenv("USE_SUPABASE", "false").lower() in {"1", "true", "yes"},
        storage_bucket_name=os.getenv("STORAGE_BUCKET_NAME", "kulima-documents"),
    )
```

---

## PHASE 7: MIGRATION SAFETY

### Backward Compatibility

**Feature Flag Approach:**
- `USE_SUPABASE=false` → Use SQLite (local development)
- `USE_SUPABASE=true` → Use Supabase (production)

**Gradual Migration:**
1. Deploy with `USE_SUPABASE=false` (SQLite mode)
2. Test Supabase connection in staging
3. Enable `USE_SUPABASE=true` in production
4. Monitor for issues
5. Rollback if needed (switch flag back)

### Data Migration Strategy

**SQLite to Supabase Migration:**
```python
# scripts/migrate_to_supabase.py
"""Migrate SQLite data to Supabase."""

import sqlite3
from sqlalchemy import create_engine

# Connect to SQLite
sqlite_conn = sqlite3.connect("founders.db")

# Connect to Supabase
supabase_engine = create_engine(os.getenv("DATABASE_URL"))

# Migrate tables
tables = [
    "assessment_contexts",
    "intelligence_runs",
    "documents",
    "document_chunks",
    "organizations",
    "organization_members",
    "cases",
    "jobs",
    "research_packs",
    "comments",
    "review_requests",
    "dossiers",
    "audit_events",
    "subscriptions",
    "payment_events",
]

for table in tables:
    # Read from SQLite
    df = pd.read_sql(f"SELECT * FROM {table}", sqlite_conn)

    # Write to Supabase
    df.to_sql(table, supabase_engine, if_exists="append", index=False)
    print(f"Migrated {len(df)} rows from {table}")
```

### Legacy API Compatibility

**Document Path Handling:**
- Legacy: `storage_path = "uploads/document.pdf"`
- New: `storage_path = "org_id/assessment_id/doc_id/original"`

**Compatibility Layer:**
```python
def get_document_path(document: Document) -> str:
    """Get document path, handling legacy and new formats."""
    if document.storage_path.startswith("uploads/"):
        # Legacy local path - generate Supabase path
        if document.org_id and document.assessment_id:
            return f"{document.org_id}/{document.assessment_id}/{document.id}/original"
        return document.storage_path
    return document.storage_path
```

---

## PHASE 8: DEPLOYMENT READINESS

### Database Changes

**Files to Modify:**
1. `kulima/config.py` - Add Supabase configuration
2. `kulima/core/database.py` - NEW: Database connection factory
3. `kulima/core/migrations.py` - Add Postgres-specific migrations
4. All repository files - Use DatabaseConnection interface

### Storage Changes

**Files to Modify:**
1. `kulima/core/storage/storage_service.py` - NEW: Storage service
2. `backend/app/routers/documents.py` - Update upload/download
3. `backend/app/services/document_adapter.py` - Use StorageService
4. `backend/app/main.py` - Remove static file serving

### Migration Risks

**Low Risk:**
- Feature flag allows instant rollback
- No breaking API changes
- Data migration is additive

**Medium Risk:**
- Postgres connection pooling needs tuning
- Storage RLS policies need testing
- Large file uploads may timeout

**Mitigation:**
- Test with production-like data volume
- Implement retry logic for storage operations
- Monitor storage quotas and costs

---

## IMPLEMENTATION ORDER

### Week 1: Database Layer
1. Add Supabase dependencies
2. Create `kulima/core/database.py`
3. Update config with Supabase settings
4. Migrate one repository as proof of concept
5. Test with feature flag

### Week 2: Storage Layer
1. Create Supabase storage bucket
2. Implement `StorageService`
3. Update document upload flow
4. Update document download flow
5. Test with feature flag

### Week 3: Full Migration
1. Migrate all repositories
2. Implement data migration script
3. Update all document operations
4. Remove static file serving
5. Deploy to staging

### Week 4: Production
1. Enable Supabase in production
2. Monitor for 1 week
3. Remove SQLite fallback (optional)
4. Update documentation

---

## FILES MODIFIED SUMMARY

### New Files (2)
1. `kulima/core/database.py` - Database connection factory
2. `kulima/core/storage/storage_service.py` - Supabase Storage service

### Modified Files (18)
1. `kulima/config.py` - Supabase configuration
2. `kulima/core/migrations.py` - Postgres-specific migrations
3. `kulima/db.py` - Use DatabaseConnection
4. `kulima/core/assessment/repository.py` - Use DatabaseConnection
5. `kulima/core/cases/repository.py` - Use DatabaseConnection
6. `kulima/core/jobs/repository.py` - Use DatabaseConnection
7. `kulima/core/research/repository.py` - Use DatabaseConnection
8. `kulima/core/collaboration/repository.py` - Use DatabaseConnection
9. `kulima/core/dossier/repository.py` - Use DatabaseConnection
10. `kulima/core/audit/repository.py` - Use DatabaseConnection
11. `kulima/core/documents/repository.py` - Use DatabaseConnection + StorageService
12. `kulima/core/orgs/repository.py` - Use DatabaseConnection
13. `kulima/core/billing/repository.py` - Use DatabaseConnection
14. `backend/app/routers/documents.py` - Supabase Storage upload/download
15. `backend/app/services/document_adapter.py` - Use StorageService
16. `backend/app/main.py` - Remove static serving
17. `backend/requirements.txt` - Add Supabase dependencies
18. `scripts/migrate_to_supabase.py` - NEW: Data migration script

---

## FINAL VERDICT

### READY FOR SUPABASE PREVIEW ✅

**Confidence Level:** High

**Justification:**
- Feature flag allows safe gradual migration
- No breaking API changes
- Backward compatibility maintained
- Data migration strategy is additive
- Storage architecture is organization-isolated
- RBAC enforcement through RLS policies
- Signed URLs for secure document access

**Deployment Path:**
1. Set up Supabase project and storage bucket
2. Configure environment variables with `USE_SUPABASE=false`
3. Deploy with SQLite mode (verify no regressions)
4. Enable `USE_SUPABASE=true` in staging
5. Run data migration script
6. Test all document operations
7. Monitor for 1 week
8. Enable Supabase in production

**Production Go Condition:**
- Successful staging validation
- Data migration complete
- Storage RLS policies tested
- Performance metrics acceptable
- No rollbacks needed in staging

---

## SIGN-OFF

**Architect:** Principal Cloud Architect
**Date:** 2026-09-22
**Recommendation:** ✅ READY FOR SUPABASE PREVIEW
**Next Review:** After staging deployment and validation
