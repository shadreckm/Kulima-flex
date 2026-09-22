# SUPABASE CLOUD READINESS SUMMARY

**Date:** 2026-09-22
**Architect:** Principal Cloud Architect
**Scope:** Supabase migration readiness assessment

---

## DATABASE CHANGES

### Configuration Updates
**File:** `kulima/config.py`
- Added Supabase configuration fields (6 new settings)
- Added feature flag `use_supabase` for gradual migration
- Backward compatible with existing SQLite configuration

### Database Connection Layer
**New File:** `kulima/core/database.py`
- Created `DatabaseConnection` abstract interface
- Implemented `SQLiteConnection` with transaction isolation
- Implemented `SupabaseConnection` via SQLAlchemy
- Factory function `get_database()` for runtime selection
- Utility functions for mode detection

### Migration Updates
**File:** `kulima/core/migrations.py`
- Added migration 009 for Postgres foreign keys (placeholder)
- Added migration 010 for Postgres composite indexes (placeholder)
- Documented Postgres-specific migration strategy

---

## STORAGE CHANGES

### Storage Service Layer
**New Files:**
1. `kulima/core/storage/__init__.py` - Package initialization
2. `kulima/core/storage/storage_service.py` - Supabase Storage service

**StorageService Features:**
- Organization-isolated file paths
- Upload/download/delete operations
- Signed URL generation for secure access
- File listing by org/assessment
- Metadata retrieval
- Error handling and logging

### Storage Architecture
**Bucket Design:**
- Bucket name: `kulima-documents`
- Public access: False (private)
- RLS policies for org isolation
- Service role for full access

**Path Structure:**
```
kulima-documents/
├── {org_id}/
│   ├── {assessment_id}/
│   │   ├── {document_id}/
│   │   │   ├── original
│   │   │   ├── chunks/
│   │   │   └── metadata.json
```

---

## FILES MODIFIED

### New Files (3)
1. `kulima/core/database.py` - Database connection factory
2. `kulima/core/storage/__init__.py` - Storage package
3. `kulima/core/storage/storage_service.py` - Storage service

### Modified Files (2)
1. `kulima/config.py` - Supabase configuration
2. `kulima/core/migrations.py` - Postgres migration placeholders

### Remaining Repository Migrations (12)
The following repositories still use direct SQLite connections and need to be migrated to use `DatabaseConnection`:
1. `kulima/db.py`
2. `kulima/core/assessment/repository.py`
3. `kulima/core/cases/repository.py`
4. `kulima/core/jobs/repository.py`
5. `kulima/core/research/repository.py`
6. `kulima/core/collaboration/repository.py`
7. `kulima/core/dossier/repository.py`
8. `kulima/core/audit/repository.py`
9. `kulima/core/documents/repository.py`
10. `kulima/core/orgs/repository.py`
11. `kulima/core/billing/repository.py`
12. `backend/app/services/run_repository.py`

### Document Flow Updates (3)
The following files need updates for Supabase Storage:
1. `backend/app/routers/documents.py` - Upload/download endpoints
2. `backend/app/services/document_adapter.py` - Document processing
3. `backend/app/main.py` - Remove static file serving

---

## MIGRATION RISKS

### Low Risk ✅
- Feature flag allows instant rollback (`USE_SUPABASE=false`)
- No breaking API changes planned
- Data migration is additive (SQLite → Supabase)
- Storage service has fallback error handling
- Database connection layer is interface-based

### Medium Risk ⚠️
- 12 repositories need migration to `DatabaseConnection`
- Document upload/download flow needs complete rewrite
- Postgres connection pooling needs tuning
- Storage RLS policies need testing in production
- Large file uploads may timeout
- Storage quotas and costs need monitoring

### High Risk ❌
- None identified

### Risk Mitigation
1. **Gradual Migration:** Use feature flag to switch between SQLite/Supabase
2. **Testing:** Deploy with SQLite mode first, then enable Supabase in staging
3. **Monitoring:** Track storage costs, database performance, error rates
4. **Rollback:** Keep SQLite fallback until stable in production
5. **Data Validation:** Run data migration script on production snapshot first

---

## PREVIEW DEPLOYMENT READINESS

### Current State: PARTIALLY READY ⚠️

**Infrastructure Ready:**
- ✅ Database connection layer implemented
- ✅ Storage service implemented
- ✅ Configuration updated
- ✅ Migration placeholders added
- ✅ Backward compatibility maintained

**Incomplete Work:**
- ❌ 12 repositories need `DatabaseConnection` migration
- ❌ Document upload/download flow needs updates
- ❌ Static file serving needs removal
- ❌ Dependencies need installation (SQLAlchemy, Supabase)
- ❌ Data migration script needs implementation
- ❌ Postgres-specific migrations need implementation
- ❌ Storage bucket needs creation in Supabase
- ❌ RLS policies need testing

---

## IMPLEMENTATION ROADMAP

### Week 1: Dependencies & Infrastructure
1. Install SQLAlchemy and Supabase client
2. Create Supabase project and storage bucket
3. Configure environment variables
4. Test database connection in isolation
5. Test storage service in isolation

### Week 2: Repository Migration
1. Migrate 3 repositories as proof of concept
2. Test with feature flag (`USE_SUPABASE=false`)
3. Enable `USE_SUPABASE=true` in staging
4. Migrate remaining 9 repositories
5. Test all database operations

### Week 3: Storage Migration
1. Update document upload endpoint
2. Update document download endpoint
3. Update document adapter
4. Remove static file serving
5. Test document operations end-to-end

### Week 4: Data Migration & Production
1. Implement data migration script
2. Run migration on production snapshot
3. Deploy to staging with Supabase
4. Monitor for 1 week
5. Enable Supabase in production
6. Keep SQLite fallback for 2 weeks

---

## DEPENDENCIES REQUIRED

**Add to `backend/requirements.txt`:**
```
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
supabase>=2.0.0
```

**Add to `requirements.txt`:**
```
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
supabase>=2.0.0
```

---

## ENVIRONMENT VARIABLES REQUIRED

**New Variables:**
```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:[password]@db.your-project.supabase.co:5432/postgres

# Feature Flag
USE_SUPABASE=false  # Start with false, enable after testing

# Storage
STORAGE_BUCKET_NAME=kulima-documents
```

---

## FINAL VERDICT

### BLOCKERS REMAIN ⚠️

**Confidence Level:** Medium

**Justification:**
- Infrastructure foundation is solid (database layer, storage service)
- Configuration and feature flags are in place
- Backward compatibility is maintained
- However, 12 repositories still need migration
- Document flow needs complete rewrite
- Dependencies need installation
- Supabase project and storage bucket need creation
- Data migration script needs implementation

**Remaining Work (Estimated 2-3 weeks):**
1. Install dependencies (1 day)
2. Migrate 12 repositories to `DatabaseConnection` (5 days)
3. Update document upload/download flow (3 days)
4. Implement data migration script (2 days)
5. Test in staging environment (3 days)
6. Deploy to production (2 days)

**Deployment Path:**
1. Install dependencies
2. Create Supabase project and storage bucket
3. Configure environment variables with `USE_SUPABASE=false`
4. Migrate repositories one by one
5. Update document flow
6. Deploy with SQLite mode (verify no regressions)
7. Enable `USE_SUPABASE=true` in staging
8. Run data migration script
9. Test all operations
10. Monitor for 1 week
11. Enable Supabase in production

**Production Go Condition:**
- All 12 repositories migrated
- Document flow updated and tested
- Data migration script tested on production snapshot
- Staging validation successful for 1 week
- Storage RLS policies tested
- Performance metrics acceptable
- No rollbacks needed in staging

---

## SIGN-OFF

**Architect:** Principal Cloud Architect
**Date:** 2026-09-22
**Recommendation:** ⚠️ BLOCKERS REMAIN (2-3 weeks of work)
**Next Review:** After repository migration and document flow updates
**Estimated Completion:** 3 weeks from today
