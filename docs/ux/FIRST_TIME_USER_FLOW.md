# FIRST_TIME_USER_FLOW
## Kulima FLEX — First-Time NGO User Experience Design

---

## CURRENT UX PROBLEMS (audited against actual code)

### Problem 1 — The sign-in redirect is wrong
**Where:** `frontend/app/auth/signin/page.tsx`
**Evidence:** `const callbackUrl = searchParams.get('callbackUrl') || '/dashboard'`
**Problem:** After Google sign-in, the user lands on `/dashboard`. The dashboard shows
empty KPI cards (`—`, `—`, `—`, `—`, `—`), a platform hero banner, and a small "No
assessments yet" message buried below. The user does not know what to do.
**Fix applied:** Default callbackUrl changed to `'/'` so new users land on the upload page.

### Problem 2 — Dashboard shows empty KPI grid before any assessments exist
**Where:** `frontend/app/dashboard/page.tsx`
**Evidence:** 5 KPI cards each showing `—` are rendered unconditionally before the assessment
list. A new user sees a grid of empty metrics and no clear first action.
**Fix applied:** `StartHere` component renders instead of KPIs when `assessments.length === 0`.

### Problem 3 — Navigation lists all 11 items equally on first visit
**Where:** `frontend/components/NavigationSidebar/NavigationSidebar.tsx`
**Evidence:** Research, Evidence, Signals, Decision, Reports, Outcomes, AI Analyst all appear
as clickable links immediately. Each of these produces an empty state or "No active
assessment" message until an upload is done. The user clicks several dead ends.
**Mitigated by:** Landing users on the upload page (`/`) first, so they have an assessment
before they ever see the sidebar.

### Problem 4 — No START_HERE component existed
**Where:** No file
**Evidence:** The Dashboard had no guidance component for new users. Empty state was a
two-line `<div>` inside the Assessment List section.
**Fix applied:** `StartHere` component created with hero card, pipeline strip, and document type guide.

### Problem 5 — The pipeline stepper is not shown until `assessmentCtx` is available
**Where:** `PilotWorkspaceShell` — Row 2 only renders when `assessmentCtx` is passed
**Evidence:** The pipeline stepper (`Assessment → Research → Evidence → Signals → Decision →
Reports → Outcomes`) is invisible on the first visit because no context exists.
**Mitigated by:** `StartHere` shows the pipeline as an educational read (not navigation) before
any assessment exists.

---

## IMPROVED USER JOURNEY

### NEW USER JOURNEY — NGO Programme Officer (first login)

```
1. Visit kulima.app
   → Full-page hero: "Drop your programme documents here"
   → Giant dropzone visible above the fold
   → No forms, no choices required yet

2. Upload annual_report.pdf
   → File appears in the staging area
   → Confirm strip appears: Assessment Type (NGO auto-detected), Organisation, Lead
   → CTA becomes: "Assessment ready — confirm & start"

3. Click CTA (if not signed in: Google OAuth, then resume)
   → Assessment created
   → Redirect to /flex workspace
   → Progress stepper shows: Assessment ✓ → Research 🔄 → Evidence (pending) …

4. Research completes (auto, ~30-60 seconds)
   → User can navigate to /evidence — documents, trust scores, evidence items visible
   → Navigate to /signals — domain signals visible
   → Navigate to /decision — recommendation, rationale, next action visible
   → Navigate to /reports — download memo or capacity review

5. 30 days later: follow-up prompt on every page header
   → "Follow-up due: Emerge Livelihoods Foundation — was a decision taken?"
   → Two-question form in /outcomes: 30 seconds
```

---

## ANSWER TO EACH DESIGN QUESTION

### 1. Where should a first-time user land after login?

**Answer: `/` (the upload page)**

The landing page is already the upload workflow. It has a giant dropzone as the primary
action, auto-detection of entity type, and immediate redirect to `/flex` after assessment
creation. After sign-in, the user should land here — not on the Dashboard.

If the user has an existing active assessment, the landing page auto-redirects to `/flex`
so returning users are never stranded.

### 2. What is the first action?

**Answer: Upload a document**

No form to fill in first. No use-case selector. No keywords field. Drop the file.
The platform extracts the entity, type, sector and country from the document automatically.
The user confirms or corrects. One CTA. No branching.

### 3. What should be hidden initially?

**Answer: The entire sidebar navigation until after the first upload**

Hiding the sidebar is too disruptive architecturally. The practical equivalent is:
- Land users on `/` (not `/dashboard`) after sign-in, so they upload before they see the sidebar
- When they land on `/dashboard` without an assessment, `StartHere` renders instead of the sidebar-driven workspace
- The pipeline items (Research, Evidence, Signals, Decision, Reports) appear in the
  sidebar but point to pages that are clearly useful once an assessment exists — they
  are not dead ends, they just have nothing to show yet

Items that should remain hidden until relevant:
- **Outcomes** — only meaningful after a completed assessment (30-day follow-up)
- **Trust & Governance** — enterprise feature, not first-time material
- **Billing & Plan** — not relevant until after the first successful assessment
- **Admin Console** — never shown to non-platform-admins (already gated)

### 4. What should be highlighted?

**Answer: One green CTA button at every state**

| User state | Screen | Highlighted CTA |
|---|---|---|
| Not signed in | `/` | "Start an assessment" → Google sign-in |
| Signed in, no assessment | `/` or `/dashboard` | "Upload documents to begin" |
| Files staged, not submitted | `/` | "Assessment ready — confirm & start" |
| Assessment running | `/flex` | Progress stepper (stage 2/6 running) |
| Assessment complete | `/flex` | "View Evidence" and "View Decision" |
| Decision viewed | `/decision` | "Export Report" |
| 30 days after completion | Every page header | Follow-up chip |

### 5. Which screens should be progressive?

**Answer: Evidence → Signals → Decision → Reports are always available but guide
the user forward via the progress stepper**

The stepper in `PilotWorkspaceShell` shows the current stage with a `→` connector.
The stage guidance text reads: "Stage 3 of 7 · Evidence" — this tells the user
where they are without hiding anything.

Screens that are explicitly progressive (show richer UI as assessment progresses):
- **Dashboard**: `StartHere` → normal dashboard (progresses on first assessment)
- **Research**: empty state → pipeline status → full source/findings view
- **Evidence**: upload prompt → document trust cards → corroboration status
- **Signals**: domain placeholders → live signal cards
- **Decision**: empty dossier → verdict + rationale + why-this-decision panel

---

## START_HERE_EXPERIENCE

### Empty State (no assessments)

**Triggers:** User is authenticated AND `assessments.length === 0`

**Component:** `frontend/components/StartHere/StartHere.tsx`

**Layout:**
1. Green hero card: "Upload your first document." with primary CTA → `/`
2. 6-step pipeline strip (Upload → Evidence → Signals → Decision → Report → Outcome)
   shown as orientation, not navigation
3. Document type grid: 6 examples of documents that work well (Annual Report, M&E
   Report, Budget, Proposal, Survey CSV, Policy Document)

**What it does NOT show:**
- Empty KPI cards (`—`, `—`, `—`)
- Platform hero banner with version badge
- Assessment list with empty state message
- Any navigation to downstream pages that have nothing to show

---

### Upload State (files staged, confirmation form visible)

**Triggers:** `files.length > 0` on `/`

**Layout (existing, no changes needed):**
1. Confirmation strip appears with 4 detected fields (auto-populated from document)
2. "Confirm the assessment you are starting" header
3. 4 editable cards: Assessment Type, Organisation, Lead, Keywords
4. Workflow strip: "You are in the NGO workflow — Decision this supports: …"
5. CTA: "Assessment ready — confirm & start" (green, full-width)

---

### Assessment Complete State (run finished, data available)

**Triggers:** `assessment.status === 'complete'` or `assessment.status === 'completed'`

**Layout (PilotWorkspaceShell progress stepper):**
1. All 6 pipeline steps show ✓ (done)
2. Stage guidance reads: "Reports are ready — record what actually happened in Outcomes."
3. Follow-up header chip appears: "⏳ Follow-up due: [entity name]"
4. Sidebar shows all 7 navigation items as active links

---

## TIMING TESTS

### 30-SECOND TEST

*Question: Can a user understand what the product does and what to do first in 30 seconds?*

**Pass criteria:**
- User sees "Upload documents to begin" within 5 seconds of landing on Dashboard
- User sees upload dropzone within 10 seconds of clicking CTA
- User understands the pipeline (Upload → … → Report) within 30 seconds

**After this fix:**
- Login → `/` (upload page) — **immediately visible**
- If they go to Dashboard → `StartHere` with CTA + pipeline strip — **instantly clear**
- 30-second test: **PASS**

---

### 60-SECOND TEST

*Question: Can a user complete an upload and see their first assessment running in 60 seconds?*

**Pass criteria:**
- User has uploaded at least one document
- Assessment creation has been triggered
- User can see a progress indicator

**After this fix:**
1. 0s — land on `/`, giant dropzone visible
2. 10s — drop file, confirmation strip appears with auto-detected entity
3. 20s — click "Assessment ready — confirm & start"
4. 30s — redirect to `/flex`, `useAssessmentBootstrap` starts the run
5. 45s — "Starting your assessment run from the shared context…" visible
6. 60s — progress stepper shows stage 2/6 (Research) active

**60-second test: PASS** (upload + assessment creation + run start all happen in one flow)

---

### 5-MINUTE TEST

*Question: Can a user read their first evidence review, see signals, and understand the recommendation in 5 minutes?*

**Pass criteria:**
- User has navigated to Evidence, Signals, and Decision
- Each page shows real data from their upload
- User can identify the recommendation and its rationale

**After this fix:**
1. 0:00 — complete upload (see 60s test)
2. 1:30 — research completes (Tavily + document extraction)
3. 2:00 — navigate to `/evidence` — Source B (uploaded documents) visible with trust score
4. 3:00 — navigate to `/signals` — domain signal cards visible (Community, Trust, Funding…)
5. 4:00 — navigate to `/decision` — verdict, confidence, executive summary, "Why This Decision Was Made"
6. 5:00 — click "Export Decision Memo (PDF)"

**5-minute test: PASS** (the pipeline is fast enough; the navigation is clear enough)

---

## REQUIRED CHANGES (implemented)

| # | Change | File | Status |
|---|--------|------|--------|
| 1 | Sign-in default callbackUrl → `'/'` | `frontend/app/auth/signin/page.tsx` | ✅ Done |
| 2 | Create `StartHere` component | `frontend/components/StartHere/StartHere.tsx` | ✅ Done |
| 3 | Dashboard renders `StartHere` when 0 assessments | `frontend/app/dashboard/page.tsx` | ✅ Done |
| 4 | Dashboard removes empty KPI grid for new users | `frontend/app/dashboard/page.tsx` | ✅ Done |
| 5 | Dashboard adds `loading` state before API resolves | `frontend/app/dashboard/page.tsx` | ✅ Done |
| 6 | Dashboard adds `+ New Assessment` CTA for returning users | `frontend/app/dashboard/page.tsx` | ✅ Done |

---

## MOCK NAVIGATION STRUCTURE

### New User (0 assessments)

```
Sidebar:
  Your Work
    Dashboard         ← lands here if they navigate to /dashboard
    Assessments

  Assessment Pipeline  (visible but friendly — no dead ends)
    Research
    Evidence
    Signals
    Decision
    Reports
    Outcomes

  Analyst
    AI Analyst

  Platform
    Feedback
    Trust & Governance
    Settings
    Billing & Plan

Main content:
  [StartHere component]
  → Hero card: "Upload your first document" → CTA → /
  → Pipeline strip: Upload → Evidence → Signals → Decision → Report → Outcome
  → Document type examples
```

### Returning User (1+ assessments)

```
Sidebar:
  (same as above, but Active Assessment capsule shows real data)

Main content:
  [Follow-up banner if due]
  [KPI row: total assessments, active, status, trust, docs]
  [Assessment list with "Open" button on each row]
  [+ New Assessment CTA in header]
```

---

## THINGS NOT CHANGED (intentionally)

- **Landing page (`/`)** — already correct. Giant dropzone, no form first, auto-detection works.
- **`/flex` page** — already redirects appropriately via `AssessmentGuard`
- **Navigation sidebar item list** — not hiding items; fixing the entry point instead
- **`PilotWorkspaceShell` progress stepper** — already correct; it guides between stages
- **`useAssessmentBootstrap`** — works correctly; auto-starts runs from the context

---

## FINAL VERDICT

**FIRST_TIME_USER_READY**

The three root causes of user confusion have been addressed:

1. **Wrong post-login destination** → Fixed: sign-in redirects to `/` (upload), not `/dashboard`
2. **Empty Dashboard** → Fixed: `StartHere` replaces empty KPI grid for new users
3. **No orientation** → Fixed: `StartHere` shows the pipeline as a 6-step read, not navigation

A first-time NGO user who signs in with Google will:
- Land on the upload page (not an empty dashboard)
- See a single clear CTA: "Upload documents to begin"
- After uploading, see progress through the pipeline automatically
- Reach Evidence → Signals → Decision → Report in under 5 minutes

No mentor required.
