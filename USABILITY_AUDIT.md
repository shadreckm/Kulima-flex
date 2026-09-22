# USABILITY AUDIT - Kulima FLEX Pilot Readiness

**Date:** 2026-09-22
**Auditor:** Product Adoption Engineer
**Scope:** Usability audit from 5 user personas for pilot testing

---

## PERSONA AUDITS

### 1. NGO PROGRAM MANAGER

**User Journey:** Upload program documents → Get funding decision → Export report

**Issues Identified:**

#### Issue 1: Confusing Entity Type Selection
**Problem:** Landing page shows "Startup" as default, NGO Program Manager must search for "NGO" or "Government Program" in a list of 5 options.
**Impact:** High friction on first interaction, may assume tool is startup-only.
**Fix:** Add "I'm evaluating..." dropdown with visual icons for each entity type, default to empty state requiring selection.
**Priority:** P0

#### Issue 2: Field Labels Don't Match NGO Context
**Problem:** "Founder Name" field appears for NGO selection, confusing for program managers who expect "Program Manager" or "Director."
**Impact:** Users may enter wrong data or abandon intake.
**Fix:** Dynamic field labels based on entity type (NGO → "Program Manager Name", "Program Name" for NGO).
**Priority:** P0

#### Issue 3: "Upload Documents" Doesn't Explain What Documents
**Problem:** Drop zone says "Business plans, reports, proposals" but NGO program managers need "Monitoring reports, impact assessments, donor reports."
**Impact:** Users may upload wrong documents or not know what to upload.
**Fix:** Contextual upload guidance based on entity type (NGO → "Monitoring reports, impact assessments, donor reports, financial statements").
**Priority:** P1

#### Issue 4: "Trust Score" Terminology Alarming
**Problem:** NGOs see "Trust Score" and assume it measures organizational trustworthiness (potentially damaging for funding).
**Impact:** NGOs may refuse to use tool or hide results.
**Fix:** Rename to "Evidence Quality Score" for non-startup entities, with tooltip explaining it measures document completeness not organizational trust.
**Priority:** P0

#### Issue 5: Navigation Sidebar Uses "Runs" Terminology
**Problem:** NGOs expect "Assessments" or "Evaluations," not "Runs."
**Impact:** Confusing navigation, users don't know where to find their work.
**Fix:** Rename "Runs" to "Assessments" for non-startup entities, or use context-aware labeling.
**Priority:** P1

---

### 2. TOURISM SME OWNER

**User Journey:** Upload business documents → Get tourism impact assessment → Understand viability

**Issues Identified:**

#### Issue 6: No Tourism-Specific Onboarding
**Problem:** Tourism SME owners see startup-focused language ("founder," "investor," "funding") throughout the interface.
**Impact:** Owners feel tool isn't designed for tourism, may not see tourism-specific value.
**Fix:** Add tourism-specific welcome message and language variants when tourism_sme is selected.
**Priority:** P0

#### Issue 7: Tourism Signals Buried in General Signals
**Problem:** Tourism SME must navigate to "Signals" page and scroll through generic signals to find tourism-specific metrics.
**Impact:** Key value proposition hidden, users may not find tourism intelligence.
**Fix:** Add dedicated "Tourism Intelligence" section on Decision page for tourism_sme entities, with prominent placement.
**Priority:** P0

#### Issue 8: "Investment Readiness" Irrelevant for Tourism SME
**Problem:** Decision page shows "Investment Readiness Score" which doesn't apply to tourism owners seeking viability assessment.
**Impact:** Confusing, irrelevant metrics dilute value.
**Fix:** Hide "Investment Readiness" for tourism_sme, show "Tourism Viability Score" instead.
**Priority**: P0

#### Issue 9: No Guidance on What Tourism Documents to Upload
**Problem:** Upload guidance is generic, tourism owners don't know if they need "visitor statistics, sustainability reports, destination assessments."
**Impact:** Poor quality uploads, suboptimal results.
**Fix:** Tourism-specific upload checklist with examples ("Visitor data, sustainability certifications, destination impact reports").
**Priority:** P1

#### Issue 10: Report Export Shows Generic Template
**Problem:** Exported report doesn't highlight tourism-specific insights in summary.
**Impact:** Owners can't quickly find tourism value in long reports.
**Fix:** Tourism-specific report template with tourism intelligence summary section upfront.
**Priority:** P1

---

### 3. STARTUP FOUNDER

**User Journey:** Upload pitch deck → Get investment readiness → Understand investor perspective

**Issues Identified:**

#### Issue 11: "Upload Documents" vs "Start Assessment" Confusion
**Problem:** Landing page has both "Upload Documents" action and "Get Started" button that leads to same flow but different labels.
**Impact:** Unclear primary action, cognitive friction.
**Fix:** Single clear CTA "Start Your Assessment" with document upload as step 1.
**Priority:** P1

#### Issue 12: No Progress Indicator During Analysis
**Problem:** After upload, users see "Your decision workspace is ready" but no indication of what's happening next.
**Impact:** Users don't know if analysis is running, confused about next steps.
**Fix:** Clear progress steps: "Analyzing documents → Researching market → Generating signals → Creating decision" with status.
**Priority:** P0

#### Issue 13: "Ask IC" Button Unclear Purpose
**Problem:** "Ask IC" appears in navigation but founders don't know what "IC" means (Intelligence Context).
**Impact:** Valuable feature ignored, users avoid unknown buttons.
**Fix:** Rename to "Ask AI Analyst" with tooltip "Ask questions about your evidence and signals."
**Priority:** P0

#### Issue 14: Evidence Page Shows Technical Terminology
**Problem:** Evidence page uses "Trust Graph," "Entity Extraction," "Source Attribution" without explanation.
**Impact:** Founders can't interpret technical terms, may ignore valuable evidence.
**Fix:** Plain language labels with technical terms in tooltips ("Document Sources" instead of "Source Attribution").
**Priority:** P1

#### Issue 15: No Clear "What Next" After Decision
**Problem:** Decision page shows scores but no guidance on what to do with the decision.
**Impact:** Founders have decision but no action plan, unclear value.
**Fix:** Add "Recommended Next Steps" section based on decision (e.g., "Improve financial documentation," "Strengthen team presentation").
**Priority:** P0

---

### 4. INVESTOR

**User Journey:** Review startup assessments → Compare trust scores → Make funding decision

**Issues Identified:**

#### Issue 16: No Comparison View Between Assessments
**Problem:** Investors must navigate individually through each assessment to compare startups.
**Impact:** Time-consuming, difficult to make portfolio decisions.
**Fix:** Add "Compare Assessments" view with side-by-side trust scores, risk levels, and recommendations.
**Priority:** P0

#### Issue 17: Dashboard Doesn't Show Portfolio-Level Insights
**Problem:** Dashboard shows individual assessments but no portfolio overview (average trust, risk distribution, sector breakdown).
**Impact:** Investors can't see portfolio-level patterns.
**Fix:** Add portfolio summary section to dashboard with aggregate metrics.
**Priority:** P1

#### Issue 18: Trust Score Explained Too Late
**Problem:** Trust score appears on Decision page but explanation of how it's calculated is buried in Evidence page.
**Impact:** Investors don't trust the score without understanding methodology.
**Fix:** Add "How Trust Score is Calculated" tooltip or link on Decision page.
**Priority:** P1

#### Issue 19: No Quick Filter by Trust Score Range
**Problem:** Investors must click into each assessment to see trust score.
**Impact:** Inefficient screening process.
**Fix:** Add trust score filter to Runs/Assessments page (e.g., "Show only 70+ scores").
**Priority:** P1

#### Issue 20: Export Report Doesn't Include Investor Summary
**Problem:** Exported report is long without executive summary for investor review.
**Impact:** Investors must read entire report to get key points.
**Fix:** Add "Investor Executive Summary" at top of exported reports.
**Priority:** P0

---

### 5. ACCELERATOR MANAGER

**User Journey:** Batch evaluate cohort → Track progress → Export cohort report

**Issues Identified:**

#### Issue 21: No Batch Assessment Creation
**Problem:** Accelerator managers must create assessments one by one for each startup.
**Impact:** Extremely time-consuming for cohorts of 10-20 startups.
**Fix:** Add "Batch Import" feature with CSV upload of startup names/URLs.
**Priority:** P0

#### Issue 22: No Cohort View or Grouping
**Problem:** All assessments listed chronologically, no way to group by cohort or program.
**Impact:** Managers can't see cohort progress or compare within cohort.
**Fix:** Add "Cohorts" view with group/filter by program/cohort.
**Priority:** P0

#### Issue 23: "Runs" vs "Assessments" Terminology Confusing
**Problem:** Accelerator managers expect "Cohorts" or "Programs," not "Runs."
**Impact:** Navigation doesn't match mental model.
**Fix:** Context-aware navigation labels (Accelerator context → "Cohorts").
**Priority:** P1

#### Issue 24: No Progress Tracking Over Time
**Problem:** Managers can't see if startups improved trust scores between assessments.
**Impact:** Can't measure program impact or show progress to stakeholders.
**Fix:** Add "Progress Over Time" view showing trust score trends for each startup.
**Priority:** P1

#### Issue 25: No Aggregate Cohort Report
**Problem:** Must export individual reports and manually compile cohort summary.
**Impact:** Time-consuming reporting, manual error risk.
**Fix:** Add "Export Cohort Summary" with aggregate metrics and top performers.
**Priority:** P0

---

## TOP 20 USABILITY FIXES (Priority Order)

### P0 - Critical for Pilot (10 fixes)

1. **Dynamic Entity Type Selection with Visual Icons**
   - Replace text-only entity type selector with visual icons and descriptions
   - Default to empty state requiring selection
   - Files: `frontend/app/page.tsx`

2. **Context-Aware Field Labels**
   - Change "Founder Name" to entity-specific labels (NGO → "Program Manager Name")
   - Change "Startup Name" to entity-specific labels (NGO → "NGO Name")
   - Files: `frontend/lib/entity-types.ts`, `frontend/components/EntityIntakeForm/EntityIntakeForm.tsx`

3. **Rename "Trust Score" to "Evidence Quality Score" for Non-Startups**
   - Keep "Trust Score" for startups, use "Evidence Quality Score" for NGOs, programs
   - Add tooltip explaining it measures document completeness
   - Files: Multiple components showing trust score

4. **Add Clear Progress Steps After Upload**
   - Show "Analyzing documents → Researching market → Generating signals → Creating decision" with status
   - Files: `frontend/app/page.tsx` after upload, add progress component

5. **Rename "Ask IC" to "Ask AI Analyst"**
   - Change navigation label and add tooltip explaining purpose
   - Files: `frontend/components/NavigationSidebar/NavigationSidebar.tsx`

6. **Add Tourism-Specific Intelligence Section**
   - Create dedicated "Tourism Intelligence" section on Decision page for tourism_sme
   - Prominent placement above general signals
   - Files: `frontend/app/decision/page.tsx`

7. **Hide "Investment Readiness" for Non-Startups**
   - Show "Tourism Viability Score" for tourism_sme
   - Show "Program Impact Score" for NGOs/programs
   - Files: `frontend/app/decision/page.tsx`

8. **Add "Recommended Next Steps" to Decision Page**
   - Provide actionable guidance based on decision
   - Files: `frontend/app/decision/page.tsx`

9. **Add "Compare Assessments" View for Investors**
   - Side-by-side comparison of trust scores, risk levels, recommendations
   - Files: New component, `frontend/app/dashboard/page.tsx`

10. **Add Batch Import for Accelerator Managers**
    - CSV upload for cohort creation
    - Files: New component, `frontend/app/dashboard/page.tsx`

### P1 - High Impact for Pilot (10 fixes)

11. **Contextual Upload Guidance by Entity Type**
    - Show specific document examples for each entity type
    - Files: `frontend/app/page.tsx`

12. **Rename "Runs" to "Assessments" Context-Aware**
    - Use "Assessments" for NGOs/programs, "Cohorts" for accelerators
    - Files: `frontend/components/NavigationSidebar/NavigationSidebar.tsx`

13. **Plain Language Labels with Technical Tooltips**
    - "Document Sources" instead of "Source Attribution"
    - Files: `frontend/app/evidence/page.tsx`

14. **Add Portfolio Summary to Dashboard**
    - Aggregate metrics across all assessments
    - Files: `frontend/app/dashboard/page.tsx`

15. **Add Trust Score Explanation on Decision Page**
    - Link or tooltip explaining calculation methodology
    - Files: `frontend/app/decision/page.tsx`

16. **Add Trust Score Filter to Assessments Page**
    - Filter by score range (70+, 50-70, <50)
    - Files: `frontend/app/runs/page.tsx`

17. **Add Investor Executive Summary to Exported Reports**
    - One-page summary at top of reports
    - Files: Export logic

18. **Add Cohorts View for Accelerator Managers**
    - Group/filter by program/cohort
    - Files: `frontend/app/dashboard/page.tsx`

19. **Add Progress Over Time View**
    - Trust score trends for each startup
    - Files: New component, `frontend/app/dashboard/page.tsx`

20. **Add Export Cohort Summary**
    - Aggregate metrics and top performers
    - Files: New component, `frontend/app/dashboard/page.tsx`

---

## DUPLICATE ACTIONS IDENTIFIED

### Duplicates
1. **"Upload Documents" and "Get Started"** on landing page → Same flow, different labels
2. **"Runs" and "Assessments"** → Same concept, different terminology
3. **"Dashboard" and "AI Analyst Workspace"** → Overlapping purpose for different users
4. **Multiple document upload points** → Evidence page, landing page, signals page

### Fix
- Consolidate to single clear action per user intent
- Use context-aware labeling based on entity type
- Centralize document upload to one location per assessment

---

## UNCLEAR TERMINOLOGY IDENTIFIED

### Confusing Terms
1. **"Run"** → Should be "Assessment" or "Evaluation"
2. **"IC"** → Should be "AI Analyst"
3. **"Trust Graph"** → Should be "Document Network"
4. **"Entity Extraction"** → Should be "Key Information"
5. **"Source Attribution"** → Should be "Document Sources"
6. **"Investment Readiness"** → Context-specific (Tourism Viability, Program Impact)
7. **"Signals"** → Should be "Insights" for non-technical users

### Fix
- Plain language labels with technical terms in tooltips
- Context-aware terminology based on entity type
- Glossary or help modal for technical terms

---

## TRUST GAPS IDENTIFIED

### Trust Issues
1. **No explanation of how AI makes decisions** → Black box concern
2. **No data privacy assurance visible** → Security concern
3. **No human verification mention** → Accuracy concern
4. **"Trust Score" sounds like judgment** → Branding concern

### Fix
- Add "How We Analyze" section to landing page
- Add privacy badge to upload zone
- Add "AI-assisted, human-reviewed" language
- Rename "Trust Score" to "Evidence Quality Score"

---

## REPORT ISSUES IDENTIFIED

### Report Problems
1. **No executive summary** → Long, hard to digest
2. **No entity-specific framing** → Generic for all types
3. **No action items** → Decision without next steps
4. **No investor/program summary** → Not audience-tailored

### Fix
- Add executive summary at top
- Entity-specific report templates
- Add "Recommended Actions" section
- Audience-specific summaries (Investor, Program Manager, Owner)

---

## ONBOARDING FRICTION IDENTIFIED

### Friction Points
1. **Entity type selection not obvious** → Confusing first step
2. **No guidance on what to upload** → Wrong documents uploaded
3. **No progress indication** → Users don't know what's happening
4. **No clear next steps** → Unclear where to go after upload
5. **No help or documentation** → Users stuck without guidance

### Fix
- Guided onboarding with step-by-step wizard
- Document checklist by entity type
- Progress indicator with steps
- Clear CTAs and navigation
- Help modal with FAQ

---

## FINAL VERDICT

### BLOCKERS REMAIN ⚠️

**Confidence Level:** Medium

**Justification:**
- 10 P0 fixes required for basic usability across personas
- 10 P1 fixes for improved experience
- Terminology and trust issues will affect pilot adoption
- Onboarding friction will cause drop-off
- No infrastructure changes needed, only UI/UX improvements

**Estimated Time to Complete:** 2-3 weeks

**Deployment Path:**
1. Implement P0 fixes (1 week)
2. Implement P1 fixes (1 week)
3. User testing with each persona (3 days)
4. Iterate based on feedback (2 days)
5. Deploy to pilot

**Pilot Go Condition:**
- All P0 fixes completed
- At least 5 P1 fixes completed
- User testing with each persona successful
- Onboarding friction < 30% drop-off rate

---

## SIGN-OFF

**Auditor:** Product Adoption Engineer
**Date:** 2026-09-22
**Recommendation:** ⚠️ BLOCKERS REMAIN (2-3 weeks of UX work)
**Next Review:** After P0 fixes completed
**Estimated Pilot Ready:** 3 weeks from today
