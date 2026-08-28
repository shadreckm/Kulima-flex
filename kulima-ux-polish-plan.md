# Kulima OS — UX Polish & Enterprise Readiness Plan

## Top-Level Overview

**Goal:** Refine and polish the existing Kulima OS UI/UX to production-grade enterprise quality — without adding new features or rebuilding architecture. The work covers: grouped navigation, terminology standardisation, dashboard restructure, improved empty states, Reports/Decision workflow audit, and visual consistency across all pages.

**Scope:** 8 files modified, 0 new files created, 0 API changes.

**Approach:** Surgical edits to existing TSX files only. Each sub-task is a self-contained file edit. No logic or data flow changes.

---

## Sub-Tasks

---

### Sub-Task 1 — Navigation: Grouped Sections & Unified Dark Theme

**Status:** [ ] pending

**Intent:**
The sidebar currently renders all 11 nav items as one flat list under a single "Navigation" heading. Items like Reports, Analytics, Feedback, and Settings need visual separation into groups. The current-run capsule and footer are already dark-themed; the nav list itself needs group labels and consistent styling throughout.

**Expected Outcomes:**
- Three clearly labelled nav groups in the sidebar: DECISION PIPELINE, INSIGHTS & EXPORTS, SYSTEM
- "Flex" label replaced with "AI Analyst Workspace"
- All sidebar sections share the same `#061C14` dark theme — no white areas
- Footer updated: "Kulima OS" instead of "Kulima Africa VC Brain"
- Brand header workspace indicator removed (redundant since each page has its own header breadcrumb)

**Todo List:**
1. Open `frontend/components/NavigationSidebar/NavigationSidebar.tsx`
2. Replace the flat `NAV_ITEMS` array with three grouped arrays:
   - `PIPELINE_ITEMS`: Dashboard, Runs, AI Analyst Workspace (`/flex`), Signals, Evidence, Decision, Outcomes
   - `INSIGHTS_ITEMS`: Reports, Analytics
   - `SYSTEM_ITEMS`: Feedback, Settings
3. Replace the single navigation render loop with three separate group sections, each with a small uppercase group label (`text-[10px] font-bold text-emerald-500/60 uppercase tracking-widest px-3 mb-1`)
4. Add a `Separator` line (`border-t border-[#0E3627] my-3`) between groups
5. Update the footer text from "Kulima Africa VC Brain" to "Kulima OS"
6. Update the nav item for `/flex` to display "AI Analyst Workspace"

**Relevant Context:**
- File: `frontend/components/NavigationSidebar/NavigationSidebar.tsx` — lines 19–31 (NAV_ITEMS), 109–134 (render loop), 137–140 (footer)
- The sidebar already uses `bg-[#061C14]` — no theme change needed, just structural grouping

---

### Sub-Task 2 — Terminology: Remove Founder/Internal Language

**Status:** [ ] pending

**Intent:**
Replace all OSTX-branded and pilot-internal labels with neutral, white-label-ready enterprise language. This affects the dashboard hero section, labels on OSTX case cards, page titles for feedback, settings, and analytics, and the `PilotWorkspaceShell` description strings.

**Expected Outcomes:**
- "OSTX Validation Cases" → "Pipeline Evaluations"
- "OSTX Presets" badge → "Evaluation Suite"
- "OSTX Core Engine" → "Core Intelligence Engine"
- "Built Today (OSTX Core Engine)" section header → "Active Intelligence Layer"
- "Roadmap (Future Intelligence Layers)" → moved out of dashboard (Sub-Task 3 handles removal)
- "Trust Dial:" label on case cards → "Trust Assessment:"
- "Signal Coverage" metric label → "Verification Coverage"
- `OSTX_CASES` launch descriptions: "Explore end-to-end Flex IC Analyst, Signals Intelligence..." → "Explore the full evaluation pipeline: AI analysis, evidence integrity, signals, and reporting."
- Feedback page title "Pilot Feedback & Validation" → "Evaluation Feedback"
- Feedback page description → "Submit reviewer feedback and confidence ratings against a completed evaluation."
- Settings page title "Pilot Settings" → "Platform Settings"
- Settings page description → "Manage your authenticated session and platform configuration."
- Settings "Pilot Summary" section header → "Platform Summary"
- Analytics page description → "Portfolio analytics derived from completed evaluation runs."
- Reports page description → "Access historical export archive. Download memos, IC reports, signals, due diligence summaries, and executive one-pagers."
- Feedback placeholder `"e.g. SPARC Reviewer / OSTX Judge"` → `"e.g. Investment Committee Member / Program Officer"`

**Todo List:**
1. Edit `frontend/app/dashboard/page.tsx` — update all OSTX labels and "Trust Dial:" text
2. Edit `frontend/app/feedback/page.tsx` — update title, description, placeholder text
3. Edit `frontend/app/settings/page.tsx` — update title, description, section heading
4. Edit `frontend/app/analytics/page.tsx` — update title, description, "Signal Coverage" metric label
5. Edit `frontend/app/reports/page.tsx` — update description

**Relevant Context:**
- `frontend/app/dashboard/page.tsx` lines 97, 113, 116, 119, 156, 174, 200, 227
- `frontend/app/feedback/page.tsx` lines 88–89, 138
- `frontend/app/settings/page.tsx` lines 49–51, 65
- `frontend/app/analytics/page.tsx` lines 59–60, 76
- `frontend/app/reports/page.tsx` lines 62–63

---

### Sub-Task 3 — Dashboard: Remove Roadmap/Built-Today, Add KPI Hero Row

**Status:** [ ] pending

**Intent:**
The dashboard currently opens with the OSTX hero (kept, retitled), then immediately shows two columns: "Built Today" and "Roadmap (Future Intelligence Layers)". These are internal product management artifacts. They must be removed. In their place, a KPI hero row must be added at the top showing the 5 most critical executive metrics above the fold. The metrics grid (currently 8 cards) should be consolidated. The OSTX evaluation cards move below the KPI row.

**Expected Outcomes:**
- Removed: the entire "Built Today / Roadmap" two-column section (lines 169–215 in dashboard/page.tsx)
- Added above the evaluation cards: a 5-column KPI strip showing:
  - Active Evaluations (count of non-archived stored runs + live runs)
  - Average Trust Score (from metrics)
  - Evidence Coverage % (from metrics)
  - Verification Coverage % (formerly Signal Coverage)
  - Decision Accuracy (average score from metrics)
- The existing 8-metric grid (lines 218–234) is trimmed to 4 cards: Stored Runs, Live Runs, Archived Runs, Average Confidence — the 4 that are not already in the KPI strip
- Dashboard page description updated: "Active evaluations, trust distribution, and outcome performance at a glance."
- Empty state for stored runs: "No evaluations available. Upload documents or create a new evaluation." (instead of silent empty)

**Todo List:**
1. Open `frontend/app/dashboard/page.tsx`
2. Delete lines 168–215 (the Built Today / Roadmap section)
3. Insert new KPI hero row as the FIRST section after the error block (before the evaluation cards section)
4. Wrap the Pipeline Evaluations hero section in a collapsed state: add `const [showDemoEvals, setShowDemoEvals] = useState(false)`. Show a small "Load Demo Evaluations" button by default; clicking it expands the 3 preset cards. When collapsed, show only the section title bar with the toggle button.
5. Update the metrics grid to show only 4 cards (remove items already in the KPI row)
6. Update the PilotWorkspaceShell description
7. Update the empty state text for stored runs

**Relevant Context:**
- `frontend/app/dashboard/page.tsx` lines 93–98 (PilotWorkspaceShell props), 168–215 (section to delete), 218–234 (metrics grid), 269–272 (empty state)
- KPI values come from existing `metrics` state and `liveRuns`/`storedRuns` arrays — no new API calls needed

---

### Sub-Task 4 — Empty States: Replace "Choose a stored run…"

**Status:** [ ] pending

**Intent:**
Every workspace with a run selector uses the placeholder "Choose a stored run…". This is developer-level language. It must be replaced with user-facing language. Additionally, when no runs exist at all, a helpful empty state with a CTA should appear instead of a blank select dropdown.

**Expected Outcomes:**
- All four `<option value="">Choose a stored run…</option>` instances replaced with `<option value="">Select Evaluation Target…</option>`
- In Reports: when `runs.length === 0`, show an empty state card: "No evaluations available. Upload documents or create a new evaluation in the Runs workspace."
- In Decision: when `runs.length === 0`, show same empty state card
- In Feedback: when `runs.length === 0`, show same empty state card

**Todo List:**
1. Edit `frontend/app/reports/page.tsx` — update placeholder option, add empty state
2. Edit `frontend/app/feedback/page.tsx` — update placeholder option, add empty state
3. Search for and update the same pattern in `frontend/app/decision/page.tsx` and `frontend/app/evidence/page.tsx`

**Relevant Context:**
- `frontend/app/reports/page.tsx` line 72
- `frontend/app/feedback/page.tsx` line 123
- `frontend/app/decision/page.tsx` line 137
- `frontend/app/evidence/page.tsx` line 135

---

### Sub-Task 5 — Reports & Analytics: Visual Polish & Design System Alignment

**Status:** [ ] pending

**Intent:**
The Reports and Analytics pages use inconsistent Tailwind classes — `shadow`, `border-gray-100`, `rounded`, `font-semibold` — instead of the established design system classes (`shadow-saas`, `border-[#DDE6F0]`, `rounded-[12px]`, `font-extrabold`). These pages look visually different from Evidence and Decision which already use the correct classes. The Reports page action buttons also use `bg-blue-600` which violates the brand colour palette.

**Expected Outcomes:**
- Reports and Analytics pages use `rounded-[12px]`, `border-[#DDE6F0]`, `shadow-saas`, `bg-[#F5F8FC]` consistently
- Report download buttons use `bg-[#0B5D3B] text-white hover:bg-[#08482E]` (brand green) instead of `bg-blue-600`
- Reports section header "Select run" → "Select Evaluation" with design-system label style (`text-xs font-bold uppercase tracking-wider text-slate-700`)
- Analytics section headers use `text-sm font-extrabold text-slate-900 uppercase tracking-wider` to match the rest of the system
- Analytics "Run Mix" renamed to "Portfolio Mix", "Top Runs by Score" renamed to "Top Evaluations by Score"
- Settings page buttons and borders aligned to design system

**Todo List:**
1. Edit `frontend/app/reports/page.tsx` — replace shadow/border/rounded/color classes
2. Edit `frontend/app/analytics/page.tsx` — replace shadow/border/rounded/color classes, rename section headers
3. Edit `frontend/app/settings/page.tsx` — replace shadow/border/rounded/color classes and button styles

**Relevant Context:**
- Design system classes defined in `frontend/tailwind.config.js` and used correctly in `frontend/app/evidence/page.tsx` and `frontend/app/feedback/page.tsx`
- `frontend/app/reports/page.tsx` lines 69–96
- `frontend/app/analytics/page.tsx` lines 64–111
- `frontend/app/settings/page.tsx` lines 54–82

---

### Sub-Task 6 — PilotWorkspaceShell: Top Bar Description & Breadcrumb Polish

**Status:** [ ] pending

**Intent:**
The sticky top header in `PilotWorkspaceShell` renders the description as a truncated single line with no visual weight. On pages where description is important (Dashboard, Decision), it deserves more presence. The breadcrumb "Kulima OS / workspace" is already correct. Minor polish: the Run context pill says "Run #" which is not user-facing language.

**Expected Outcomes:**
- Description text changes from `truncate` to `line-clamp-2` so it never silently hides important context
- Run context pill in header: "Run #xxxxxxxx" → "Evaluation: xxxxxxxx"
- The description in the header is capped at 2 lines and uses `text-slate-400` for softer visual presence

**Todo List:**
1. Edit `frontend/components/PilotWorkspaceShell/PilotWorkspaceShell.tsx`
2. Line 113: change `truncate` to `line-clamp-2 text-slate-400`
3. Lines 103–104: change "Run #" to "Evaluation:" and trim run ID to 12 chars instead of 8

**Relevant Context:**
- `frontend/components/PilotWorkspaceShell/PilotWorkspaceShell.tsx` lines 100–116

---

## White-Label Readiness Assessment

After all sub-tasks complete:

| Area | Before | After |
|---|---|---|
| Navigation grouping | Flat unsorted list | 3 labelled groups |
| Internal branding | "OSTX", "Pilot", "VC Brain" | Neutral enterprise terms |
| Empty states | Silent dropdowns | Guided empty states with CTAs |
| Design system | Inconsistent across Reports/Analytics/Settings | Unified across all pages |
| Dashboard | Internal roadmap visible | Executive KPI-first layout |
| Terminology | "Trust Dial", "Signal Coverage", "Flex" | "Trust Assessment", "Verification Coverage", "AI Analyst Workspace" |
| Footer | "Kulima Africa VC Brain v2.0" | "Kulima OS" |

**Remaining white-label gaps (out of scope, no new features):**
- App title in `layout.tsx` is "Kulima Frontend Prototype" — can be updated in a single line during Sub-Task 2 for completeness
- OSTX case data in `current-run.ts` still uses OSTX run ID prefixes — these are internal test data identifiers, acceptable for now

## Product Maturity Reassessment

After these changes, Kulima OS will present as:
- **Navigation:** Production-grade grouped sidebar matching Notion, Linear, or enterprise SaaS patterns
- **Dashboard:** Executive landing that answers the 4 key questions (active, evidence, trust, outcomes) without scrolling
- **Language:** White-label ready — safe to demo to a fund, NGO, SPARC evaluator, or government program
- **Design system:** Unified — no more blue buttons or unstyled cards on secondary pages
- **Empty states:** Guided — users know what to do when no data exists
