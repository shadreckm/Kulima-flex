# LEGACY ARCHITECTURE REMOVAL SUMMARY

**Date:** 2026-10-01
**Role:** Chief Technical Architect
**Scope:** Remove all legacy run-based architecture, replace with Assessment Context

---

## PHASE 1: DASHBOARD ✅

**Status:** Converted to Assessment Inventory

**Changes Made:**
- Removed all legacy run-based code blocks (lines 180-224)
- Removed references to `metrics` (from removed `getPilotAnalytics()`)
- Changed KPIs to use Assessment Context data
- Changed links from `?run=` to `?assessmentId=`
- Simplified to show only Assessment Inventory

**Legacy Dependencies Removed:**
- `listStoredRuns()` ✅
- `listLiveRuns()` ✅
- `getPilotAnalytics()` ✅
- `isDemoRunRecord()` ✅
- All legacy run variables ✅

**Assessment Context Compliance:** 100%

---

## PHASE 2: ASSESSMENTS PAGE ✅

**Status:** Converted to Assessment Context

**Changes Made:**
- Fixed `loadRuns()` → `loadAssessments()` function call
- Removed legacy `withBusy()` function
- Removed legacy `archivedRuns` and `activeStoredRuns` variables
- Changed links from `?run=` to `?assessmentId=`
- Simplified to show only Assessment Context inventory

**Legacy Dependencies Removed:**
- `loadRuns()` ✅
- `withBusy()` ✅
- `archivedRuns` ✅
- `activeStoredRuns` ✅
- All legacy run variables ✅

**Assessment Context Compliance:** 100%

---

## PHASE 3: REPORTS ✅

**Status:** Already uses Assessment Context

**Finding:** Reports page already uses `useAssessmentWorkspace()` hook and does not have legacy run dependencies.

**Legacy Dependencies:** None

**Assessment Context Compliance:** 100%

---

## PHASE 4: FEEDBACK ❌

**Status:** NOT converted - Still uses legacy run-based APIs

**Remaining Legacy Dependencies:**
- `listStoredRuns()` (line 8, 74)
- `submitRunFeedback()` (line 9)
- `getRunFeedback()` (line 10)
- `loadCurrentRun()` (line 15, 79)
- `resolveStoredRunId()` (line 15, 80)
- `isDemoRunRecord()` (line 15, 76)
- `StoredRunRecord` type (line 12)

**Required Work:**
- Replace `listStoredRuns()` with `listAssessments()`
- Replace `submitRunFeedback()` with `submitAssessmentFeedback()`
- Replace `getRunFeedback()` with `getAssessmentFeedback()`
- Replace `loadCurrentRun()` with `getActiveAssessment()`
- Remove `resolveStoredRunId()` usage
- Replace `StoredRunRecord` with `AssessmentWorkspacePayload`

**Assessment Context Compliance:** 0%

---

## PHASE 5: ASSESSMENT CONTEXT SCHEMA ❌

**Status:** NOT extended

**Finding:** Client-side `AssessmentWorkspacePayload` type not extended with research, reports, activity, decision, signals fields.

**Required Work:**
- Verify backend Assessment Context schema
- Extend frontend type to match backend
- Ensure type safety across all pages

**Status:** Blocked by backend schema verification

---

## PHASE 6: NAVIGATION ✅

**Status:** Already updated

**Finding:** Navigation already updated to use `/assessments` instead of `/runs`.

**Primary Navigation:**
- Dashboard ✅
- Assessments ✅
- Evidence ✅
- Research ✅
- Signals ✅
- Decision ✅
- Reports ✅

**Secondary Navigation:**
- Feedback ✅
- Activity ✅
- Trust ✅
- Settings ✅
- Billing ✅

**Assessment Context Compliance:** 100%

---

## PHASE 7: VALIDATION ❌

**Status:** Cannot validate - legacy dependencies remain

**Legacy Dependencies Found:** 13 files still have legacy run dependencies

### Files with Legacy Dependencies:
1. `frontend/lib/api.ts` - `listStoredRuns()` function (lines 592, 596, 597)
2. `frontend/lib/assessment-store.ts` - `loadCurrentRun()` (lines 1, 415)
3. `frontend/lib/current-run.ts` - `loadCurrentRun()` (lines 30, 70)
4. `frontend/lib/demo-chat.ts` - legacy imports (lines 1, 4)
5. `frontend/hooks/useCurrentRun.ts` - `useCurrentRun()` hook (lines 8, 13, 22)
6. `frontend/hooks/useAssessmentBootstrap.ts` - legacy imports (lines 11, 66)
7. `frontend/app/evidence/page.tsx` - `listStoredRuns()`, `loadCurrentRun()`, `resolveStoredRunId()`
8. `frontend/app/signals/page.tsx` - `useCurrentRun()` (lines 16, 46)
9. `frontend/app/flex/page.tsx` - `useCurrentRun()` (lines 12, 17)
10. `frontend/app/settings/page.tsx` - `listStoredRuns()` (lines 7, 23)
11. `frontend/app/runs/page.tsx` - `listStoredRuns()` (lines 7, 21)
12. `frontend/app/analytics/page.tsx` - `listStoredRuns()` (lines 6, 27)
13. `frontend/app/feedback/page.tsx` - `listStoredRuns()`, `loadCurrentRun()`, `resolveStoredRunId()` (lines 8, 15, 74, 79, 80)

### Pages with Legacy Dependencies (8 pages):
1. `/evidence` - High priority
2. `/signals` - High priority
3. `/flex` - High priority
4. `/feedback` - High priority
5. `/settings` - Low priority
6. `/runs` - Old route (can be deleted)
7. `/analytics` - Low priority
8. `/navigation` - Minor references in NavigationSidebar

---

## FILES MODIFIED

### Modified Files (2)
1. **`frontend/app/dashboard/page.tsx`** - Fully converted to Assessment Context
2. **`frontend/app/assessments/page.tsx`** - Fully converted to Assessment Context

### Previously Modified Files (from earlier work)
1. **`frontend/components/NavigationSidebar/NavigationSidebar.tsx`** - Updated navigation
2. **`frontend/lib/api.ts`** - Added `listAssessments()` function

---

## LEGACY DEPENDENCIES REMOVED

### Fully Removed (2 pages)
1. **Dashboard** - All legacy run dependencies removed ✅
2. **Assessments** - All legacy run dependencies removed ✅

### Partially Removed (1 page)
3. **Reports** - No legacy dependencies to remove (already compliant) ✅

### Not Removed (8 pages)
4. **Evidence** - Still uses `listStoredRuns()`, `loadCurrentRun()`, `resolveStoredRunId()` ❌
5. **Signals** - Still uses `useCurrentRun()` ❌
6. **Flex** - Still uses `useCurrentRun()` ❌
7. **Feedback** - Still uses `listStoredRuns()`, `loadCurrentRun()`, `resolveStoredRunId()` ❌
8. **Settings** - Still uses `listStoredRuns()` ❌
9. **Runs** - Old route (can be deleted) ❌
10. **Analytics** - Still uses `listStoredRuns()` ❌
11. **NavigationSidebar** - Minor references ❌

---

## ASSESSMENT CONTEXT COMPLIANCE

### Current State: 30% (3/10 pages)

**Compliant Pages (3):**
- `/research` - Uses `getActiveAssessment()` and `getAssessmentWorkspace()`
- `/decision` - Uses `useAssessmentWorkspace()` hook
- `/activity` - Uses governance API

**Newly Compliant (2):**
- `/dashboard` - Uses `listAssessments()` ✅
- `/assessments` - Uses `listAssessments()` ✅

**Non-Compliant (5):**
- `/evidence` - Uses `listStoredRuns()`, `loadCurrentRun()`, `resolveStoredRunId()`
- `/signals` - Uses `useCurrentRun()`
- `/flex` - Uses `useCurrentRun()`
- `/feedback` - Uses `listStoredRuns()`, `loadCurrentRun()`, `resolveStoredRunId()`
- `/settings` - Uses `listStoredRuns()`

**Secondary Pages (2):**
- `/analytics` - Uses `listStoredRuns()`
- `/runs` - Old route (can be deleted)

---

## FINAL VERDICT

### ⚠️ BLOCKERS REMAIN

**Confidence Level:** High

**Justification:**
- Dashboard fully converted to Assessment Context ✅
- Assessments page fully converted to Assessment Context ✅
- Reports already compliant ✅
- Navigation already updated ✅
- However, 5 core pages still have significant legacy run-based dependencies
- 13 files still have legacy run API references
- Feedback page requires full rewrite to use Assessment Context
- Evidence, Signals, Flex pages require full rewrite
- Assessment Context schema not extended
- Cannot validate end-to-end without full migration

**Severity:** High. The platform still has significant legacy run-based dependencies in 5 core pages (50% of core pages).

**Estimated Time to Assessment Context Complete:** 3-4 weeks

**Required Work:**
1. Convert Evidence page to Assessment Context - 2 days
2. Convert Signals page to Assessment Context - 2 days
3. Convert Flex page to Assessment Context - 2 days
4. Convert Feedback page to Assessment Context - 2 days
5. Remove or migrate Settings page dependencies - 1 day
6. Delete old `/runs` route - 0.5 day
7. Delete or migrate `/analytics` route - 0.5 day
8. Extend Assessment Context schema - 1 day
9. Remove legacy API functions - 1 day
10. End-to-end validation - 2 days

---

## RECOMMENDATION

**Option 1: Full Migration (Recommended)**
- Complete the remaining 5 pages migration
- Remove all legacy run-based dependencies
- Delete old routes and API functions
- Validate end-to-end
- **Timeline:** 3-4 weeks
- **Risk:** Medium (requires careful testing)

**Option 2: Incremental Migration**
- Keep legacy run-based APIs alongside Assessment Context
- Migrate pages incrementally with feature flags
- **Timeline:** 5-6 weeks
- **Risk:** Medium (dual state management complexity)

**Option 3: Defer Migration**
- Keep current state
- Focus on new features
- Address legacy debt later
- **Timeline:** N/A
- **Risk:** High (technical debt accumulates)

---

## SIGN-OFF

**Chief Technical Architect:** Legacy Architecture Removal Summary
**Date:** 2026-10-01
**Recommendation:** ⚠️ BLOCKERS REMAIN (High severity)
**Next Review:** After full Assessment Context migration
**Estimated Assessment Context Complete:** 3-4 weeks
**Progress:** 50% (5/10 core pages compliant)
