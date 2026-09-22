# PRODUCTION READINESS AUDIT - Kulima FLEX Enterprise Decision Management System

**Date:** 2026-09-22
**Auditor:** Principal Production Readiness Engineer
**Scope:** Complete production readiness assessment before deployment

---

## EXECUTIVE SUMMARY

**VERDICT: NO-GO FOR PRODUCTION DEPLOYMENT**

The enterprise implementation has critical security, data integrity, and operational issues that must be resolved before production deployment. While the architecture is sound, several critical and high-risk issues require immediate fixes.

---

## CRITICAL ISSUES

### 1. DATABASE MIGRATION FAILURES
**Severity:** CRITICAL
**Impact:** Production deployment will fail, data loss risk

**Issue:** Migration 007 attempts to alter audit_events table but the table may not exist in all environments. The migration assumes audit_events exists but it's created by the audit repository itself.

**File:** `kulima/core/migrations.py` lines 191-196
```python
"007_add_audit_extensions": """
    -- This migration is handled by the audit repository's _initialize method
    -- which safely adds columns using PRAGMA table_info checks.
    -- The audit_events table is created by the audit repository itself.
    -- We ensure the audit repository initializes on startup to add new columns.
    """,
```

**Fix Required:**
```python
"007_add_audit_extensions": """
    -- Create audit_events table if it doesn't exist (for new installations)
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        org_id TEXT,
        user_id TEXT,
        run_id TEXT,
        assessment_id TEXT,
        document_id TEXT,
        case_id TEXT,
        metadata_json TEXT,
        ip_hash TEXT,
        user_agent TEXT,
        created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_audit_org_created ON audit_events(org_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_assessment ON audit_events(assessment_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(case_id, created_at DESC);
""",
```

### 2. JOB RUNNER LIFECYMANAGEMENT RACE CONDITION
**Severity:** CRITICAL
**Impact:** Job processing may deadlock, system hangs

**Issue:** JobRunner.start() creates asyncio task but doesn't await it. In FastAPI lifespan, this creates a fire-and-forget task that may not properly initialize before requests arrive.

**File:** `backend/app/main.py` lines 64-65
```python
self._task = asyncio.create_task(self._worker_loop())
```

**Fix Required:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for enterprise features."""
    # Startup
    global _job_runner
    if JOB_RUNNER_AVAILABLE:
        try:
            _job_runner = JobRunner()
            # Start and wait for initialization
            await _job_runner.start()
            # Give it a moment to initialize
            await asyncio.sleep(0.1)
            print("Enterprise JobRunner started successfully")
        except Exception as exc:
            print(f"Failed to start JobRunner: {exc}")
            _job_runner = None

    yield

    # Shutdown
    if _job_runner:
        try:
            await _job_runner.stop()
            print("Enterprise JobRunner stopped successfully")
        except Exception as exc:
            print(f"Failed to stop JobRunner: {exc}")
```

### 3. SQLITE WRITE CONCURRENCY IN PRODUCTION
**Severity:** CRITICAL
**Impact:** Database corruption under load, data loss

**Issue:** All repositories use SQLite without proper transaction isolation. The job runner, multiple API requests, and background writes will cause write contention and potential database corruption.

**Files:** All repository files use basic `sqlite3.connect()` without `BEGIN IMMEDIATE`

**Fix Required:**
All repository `_connect()` methods must use:
```python
@contextmanager
def _connect(self) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(self.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("BEGIN IMMEDIATE")  # Critical for write safety
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### 4. MISSING FOREIGN KEY CONSTRAINTS
**Severity:** CRITICAL
**Impact:** Data integrity violations, orphaned records

**Issue:** New tables lack foreign key constraints despite relationships. SQLite allows this but Postgres will fail.

**Files:** All migration schemas

**Example Fix:**
```sql
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    ...
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);
```

---

## HIGH RISKS

### 5. CASE LIFECYCLE TRANSITION WITHOUT AUDIT
**Severity:** HIGH
**Impact:** No audit trail for critical state changes

**Issue:** CaseService.transition_lifecycle() doesn't record audit events for lifecycle transitions.

**File:** `kulima/core/cases/service.py` transition_lifecycle method

**Fix Required:**
```python
from kulima.core.audit import record_event

# In transition_lifecycle method after successful transition:
record_event(
    "case.lifecycle_changed",
    org_id=org_id,
    user_id=actor_id,
    case_id=case_id,
    metadata={
        "from_status": case.lifecycle_status.value,
        "to_status": new_status.value,
        "transition_by": actor_id,
    },
)
```

### 6. DOCUMENT RETENTION NOT ENFORCED
**Severity:** HIGH
**Impact:** Storage leaks, compliance violations

**Issue:** DocumentRepository has retention logic but no cleanup job. Expired documents accumulate forever.

**File:** `kulima/core/documents/repository.py`

**Fix Required:**
Add cleanup job in JobRunner:
```python
async def _execute_retention_cleanup_job(self, job: Job) -> dict[str, any]:
    """Clean up expired documents."""
    from kulima.core.documents.repository import DocumentRepository
    doc_repo = DocumentRepository()
    expired_count = doc_repo.cleanup_expired_documents()
    return {"expired_documents_cleaned": expired_count}
```

### 7. TENANCY ISOLATION GAPS
**Severity:** HIGH
**Impact:** Cross-organization data access possible

**Issue:** Several repository methods lack org_id filtering or have nullable org_id without proper fallbacks.

**Files:** Multiple repository files

**Specific Issues:**
- `CaseRepository.list_active_for_user()` doesn't enforce org_id when None
- `JobRepository.list_for_case()` has no org_id validation
- `CollaborationRepository` methods lack org_id scope validation

**Fix Required:**
All read methods must enforce:
```python
if org_id is None:
    raise ValueError("org_id required for production security")
```

### 8. RBAC ENFORCEMENT INCOMPLETE
**Severity:** HIGH
**Impact:** Privilege escalation possible

**Issue:** Case router endpoints have conditional AUTH_AVAILABLE that bypasses role checks in testing mode. This pattern could be exploited.

**File:** `backend/app/routers/cases.py`

**Fix Required:**
Remove AUTH_AVAILABLE bypasses or make them environment-gated:
```python
if not AUTH_AVAILABLE or os.getenv("KULIMA_SKIP_AUTH") != "true":
    # Enforce role checks
```

### 9. JOB RUNNER DEAD JOB HANDLING COMMENTED OUT
**Severity:** HIGH
**Impact:** Failed jobs leave cases in limbo state

**Issue:** JobRunner._handle_dead_job() is commented out, meaning dead jobs don't trigger case recovery.

**File:** `kulima/core/jobs/runner.py` lines 267-274

**Fix Required:**
Uncomment and implement proper system user credentials:
```python
async def _handle_dead_job(self, case_id: str) -> None:
    """Handle a job that has exceeded max attempts."""
    _log.warning("Handling dead job for case %s - reverting to DRAFT", case_id)
    case = self.case_service.get_case(case_id)
    if case:
        # Use system user for recovery transitions
        from kulima.core.orgs.models import Role
        self.case_service.transition_lifecycle(
            case_id, 
            CaseLifecycleStatus.DRAFT, 
            "system_recovery", 
            Role.ADMIN,  # System has admin privileges for recovery
            org_id=case.org_id
        )
```

### 10. MISSING BEGIN IMMEDIATE IN CRITICAL SECTIONS
**Severity:** HIGH
**Impact:** Database deadlocks under concurrent load

**Issue:** JobRepository.claim_job() does complex UPDATE with subquery but no transaction isolation.

**File:** `kulima/core/jobs/repository.py` claim_job method

**Fix Required:**
```python
def claim_job(self, worker_id: str, lease_duration_seconds: int = 300) -> Optional[Job]:
    with self._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")  # Add this
        try:
            # existing claim logic
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

---

## MEDIUM RISKS

### 11. POSTGRES MIGRATION PATH NOT DEFINED
**Severity:** MEDIUM
**Impact:** Cannot migrate from SQLite to Postgres

**Issue:** All migrations use SQLite-specific syntax. No Postgres migration path defined.

**Fix Required:**
Create Postgres migration variants or use SQLAlchemy for database-agnostic migrations.

### 12. EVIDENCE GRAPH TABLES UNUSED
**Severity:** MEDIUM
**Impact:** Dead code, storage waste

**Issue:** Evidence graph tables created but never populated by any service.

**Files:** Migration 006 creates evidence_nodes/evidence_edges tables

**Fix Required:**
Either implement EvidenceGraphService or remove migration 006.

### 13. ASSESSMENT CONTEXT BACKWARD COMPATIBILITY
**Severity:** MEDIUM
**Impact:** Legacy assessments may fail to load

**Issue:** AssessmentDocument model added new required fields that legacy data won't have.

**File:** `kulima/core/assessment/models.py`

**Fix Required:**
Make new fields optional with defaults:
```python
status: DocumentStatus = DocumentStatus.UPLOADED
trust_contribution: float = 0.0
evidence_count: int = 0
extraction_confidence: float = 0.0
```

### 14. BILLING ENFORCEMENT OFF BY DEFAULT
**Severity:** MEDIUM
**Impact:** No quota enforcement in production

**Issue:** Billing checks only work when KULIMA_BILLING_ENFORCEMENT=true, but this may be forgotten in production.

**File:** `kulima/core/billing/service.py`

**Fix Required:**
Add environment validation:
```python
if os.getenv("ENVIRONMENT") == "production" and not enforcement_enabled():
    _log.critical("BILLING ENFORCEMENT DISABLED IN PRODUCTION")
    raise RuntimeError("Billing enforcement required in production")
```

### 15. JOB RUNNER ERROR HANDLING SWALLOWS EXCEPTIONS
**Severity:** MEDIUM
**Impact:** Errors hidden, difficult debugging

**Issue:** JobRunner worker loop catches all exceptions with bare except.

**File:** `kulima/core/jobs/runner.py` line 102

**Fix Required:**
```python
except Exception as exc:
    _log.exception("JobRunner worker loop error: %s", exc)
    # Add structured error reporting
    if os.getenv("ENVIRONMENT") == "production":
        # Send to error monitoring service
        pass
    await asyncio.sleep(self.poll_interval)
```

---

## LOW RISKS

### 16. MISSING INDEX ON COMMON QUERIES
**Severity:** LOW
**Impact:** Performance degradation at scale

**Issue:** Some common query patterns lack composite indexes.

**Fix Required:**
Add indexes for:
- `cases(org_id, lifecycle_status, updated_at)`
- `jobs(case_id, status, created_at)`

### 17. NO CONNECTION POOLING
**Severity:** LOW
**Impact:** Connection overhead under load

**Issue:** Each repository call creates new SQLite connection.

**Fix Required:**
Implement connection pooling for Postgres migration.

### 18. ASSESSMENT DUPLICATION PREVENTION WEAK
**Severity:** LOW
**Impact:** Possible duplicate assessments

**Issue:** No idempotency check on assessment creation.

**Fix Required:**
Add idempotency key to assessment_contexts table.

### 19. JOB ID GENERATION NOT THREAD-SAFE
**Severity:** LOW
**Impact:** Potential UUID collisions (theoretical)

**Issue:** UUID generation is safe but could use more robust method.

**Fix Required:**
Use UUIDv7 for better database friendliness.

### 20. MISSING HEALTH CHECK FOR JOB RUNNER
**Severity:** LOW
**Impact:** Cannot monitor job processing health

**Issue:** No endpoint to check JobRunner status.

**Fix Required:**
Add health check endpoint:
```python
@app.get("/health/jobs")
async def jobs_health():
    if _job_runner and _job_runner._running:
        return {"status": "healthy", "worker_id": _job_runner.worker_id}
    return {"status": "unhealthy"}, 503
```

---

## DEPLOYMENT CHECKLIST

### DATABASE MIGRATION
- [ ] Fix migration 007 to create audit_events table
- [ ] Add foreign key constraints to all new tables
- [ ] Add BEGIN IMMEDIATE to all repository connections
- [ ] Create Postgres migration path
- [ ] Test migration on production-like data snapshot

### JOB SYSTEM
- [ ] Fix JobRunner lifecycle management in FastAPI lifespan
- [ ] Implement dead job handling
- [ ] Add transaction isolation to claim_job
- [ ] Add job runner health check endpoint
- [ ] Test job recovery after crash

### TENANCY & RBAC
- [ ] Remove AUTH_AVAILABLE bypasses in production
- [ ] Add org_id required validation to all read methods
- [ ] Add audit logging to case lifecycle transitions
- [ ] Test cross-org access attempts

### DOCUMENT STORAGE
- [ ] Implement document retention cleanup job
- [ ] Add orphaned file detection
- [ ] Test encryption/decryption failure paths

### BILLING
- [ ] Add production enforcement validation
- [ ] Test quota enforcement at scale
- [ ] Verify grace period expiry logic

### MONITORING
- [ ] Add job queue depth monitoring
- [ ] Add database connection monitoring
- [ ] Add error tracking integration
- [ ] Add performance metrics

---

## PERFORMANCE ESTIMATES

### 100 Assessments
- **Database Size:** ~50MB
- **Job Queue:** Minimal load
- **Concurrent Users:** 10-20
- **Bottlenecks:** None expected

### 1,000 Assessments  
- **Database Size:** ~500MB
- **Job Queue:** Moderate load
- **Concurrent Users:** 50-100
- **Bottlenecks:** SQLite write contention becomes apparent

### 100 Concurrent Users
- **Database Size:** Variable
- **Job Queue:** High load
- **Concurrent Users:** 100
- **Bottlenecks:** 
  - SQLite write contention (CRITICAL)
  - Job runner throughput
  - API response times

**RECOMMENDATION:** Must migrate to Postgres before 100 concurrent users.

---

## ENVIRONMENT & DEPLOYMENT

### CRITICAL ENVIRONMENT VARIABLES
```
NEXTAUTH_SECRET=required
DATABASE_URL=required (Postgres for production)
TAVILY_API_KEY=required
OPENAI_API_KEY=required
KULIMA_BILLING_ENFORCEMENT=true (production)
ENVIRONMENT=production
```

### STORAGE REQUIREMENTS
- **Document Storage:** 10GB initial, 100GB for 1000 assessments
- **Database Storage:** 1GB initial, 10GB for 1000 assessments
- **Backup Requirements:** Daily snapshots, point-in-time recovery

### BACKGROUND WORKERS
- **JobRunner:** Required (1 instance per deployment)
- **Scaling:** Multiple instances possible with proper database locking
- **Monitoring:** Required for job queue depth and processing latency

---

## FINAL VERDICT

### **NO-GO FOR PRODUCTION DEPLOYMENT**

**Critical Blockers:**
1. Database migration failures (migration 007)
2. JobRunner lifecycle management issues
3. SQLite write concurrency (production safety)
4. Missing foreign key constraints

**Must Fix Before Production:**
- All 4 critical issues
- All 10 high-risk issues
- Postgres migration path
- Connection pooling
- Comprehensive monitoring

**Estimated Fix Time:** 2-3 weeks for full production readiness

**Recommended Path:**
1. Fix critical issues (1 week)
2. Implement Postgres migration (1 week) 
3. Add monitoring and testing (1 week)
4. Staged rollout with canary testing

---

## EXACT FILES REQUIRING IMMEDIATE FIXES

1. `kulima/core/migrations.py` - Fix migration 007
2. `backend/app/main.py` - Fix JobRunner lifespan
3. All repository files - Add BEGIN IMMEDIATE
4. All migration schemas - Add foreign keys
5. `kulima/core/cases/service.py` - Add audit logging
6. `kulima/core/documents/repository.py` - Add cleanup job
7. `backend/app/routers/cases.py` - Remove auth bypasses
8. `kulima/core/jobs/runner.py` - Implement dead job handling
9. `kulima/core/jobs/repository.py` - Add transaction isolation
10. `kulima/core/billing/service.py` - Add production validation

---

## SIGN-OFF

**Auditor:** Principal Production Readiness Engineer
**Date:** 2026-09-22
**Recommendation:** Address critical and high issues before production deployment
**Next Review:** After critical fixes completed
