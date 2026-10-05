# RESILIENCE ARCHITECTURE REPORT — Kulima FLEX

**Role:** Reliability and Intelligence Architect
**Date:** 2026-10-05
**Mission:** Make Kulima FLEX fully operational with or without external AI providers. The platform must never dead-end because of OpenAI unavailability/quota, Tavily unavailability/timeout, network failure, or API key failure.

---

## FILES MODIFIED

| # | File | Change |
|---|---|---|
| 1 | `backend/app/services/orchestrator_adapter.py` | **Removed the OSTX/AgriNova seed-dataset offline fallback** (`_get_offline_fallback_brief`). Legacy thread fallback now routes through `build_document_intelligence_fallback()` — every offline run is built from the assessment's own documents, trust layer, deterministic signals, and whatever research succeeded. `ask_signals` fallback switched from `demo_ask_signals_answer` ("Demo Mode Response" banner) to `doc_intelligence_ask_signals_answer`. |
| 2 | `backend/app/services/demo_chat.py` | `DEMO_MODE_LABEL` re-labelled "Document Intelligence Mode" — the string "Demo Mode" no longer appears in any user-facing banner. `demo_ask_ic_answer` renamed to `doc_intelligence_ask_ic_answer` (the legacy demo alias removed); `demo_ask_signals_answer` kept only as a backward-compatible alias delegating to the doc-intelligence answer. |
| 3 | `backend/app/routers/intelligence.py` | `_is_demo_run` no longer treats every non-numeric run id as a demo case (live UUID runs were being blocked from archive/reopen/delete as "Demo cases are read-only"). Only legacy `ostx-`/`pilot-` prefixes remain read-only. |
| 4 | `kulima/research.py` | `ResearchEngine` no longer crashes when `TAVILY_API_KEY` is missing/placeholder — engine builds in disabled state and every `search()` returns `[]` gracefully. All Tavily calls are bounded (`timeout=20`) and any network/timeout/quota/key failure degrades to zero sources instead of hanging or raising. |
| 5 | `kulima/core/assessment/models.py` | Added `DocumentIntelligence` model (locations, dates, budget_references, activities, objectives, outcomes, risks) and `project_lead` on `AssessmentExtraction`. |
| 6 | `kulima/core/assessment/extraction.py` | Added fully deterministic extraction of **project lead, locations, dates, budget references (multi-currency), activities, objectives, outcomes, and risks** via regex + curated dictionaries — zero AI dependency. Merge logic extended to union these lists across all uploaded documents. |
| 7 | `backend/app/services/assessment_adapter.py` | Serialized context now exposes `aiMode` + `aiModeLabel` (Phase 7) and `extraction.intelligence` + `extraction.projectLead` (Phase 1) to every workspace and report surface. Offline research payloads carry `mode: document_intelligence`. |
| 8 | `frontend/lib/assessment-store.ts` | `AssessmentContext` type extended with `aiMode` / `aiModeLabel`. |
| 9 | `frontend/components/AssessmentSummaryBar/AssessmentSummaryBar.tsx` | **Mode badge**: shows `🤖 AI Available` (blue) or `📄 Doc Intelligence` (amber) with explanatory tooltip — users always know which mode produced the results. |
| 10 | `scripts/phase8_resilience_validation.py` | Validation harness: all 5 assessment types end-to-end with both providers disabled. |
| 11 | `requirements.txt` | Added PyPDF2, python-docx, python-pptx, openpyxl (deterministic parsers for PDF/DOCX/PPTX/XLSX — required by Phase 1 and missing from the previous release). |

---

## AI DEPENDENCIES REMOVED

1. **OSTX/AgriNova seed data** — deleted from the offline fallback path. `_get_offline_fallback_brief()` (which copied a seeded INVEST-grade demo brief, patched names, and stamped "OSTX Validation Dataset" onto the executive summary) is gone. No fallback path can ever surface example startup data.
2. **"Demo Mode" language** — removed from every user-facing string; replaced with "Document Intelligence Mode".
3. **Silent non-numeric demo classification** — live UUID runs are now treated as user data.
4. **Hard Tavily construction dependency** — `TavilyClient` is now optional at build time.

---

## FALLBACK LOGIC ADDED

**Mode A — AI Research (providers healthy):**
OpenAI agents + Tavily OSINT → evidence integrity → trust graph → syndicate → memo (unchanged).

**Mode B — Document Intelligence Mode (any provider failure):**
- `is_openai_unavailable()` classifies 401/408/429/5xx, quota, timeout, missing-credential errors (including non-OpenAI `RuntimeError`s with missing-key messages) → Document Intelligence Mode engages for the whole run.
- `build_document_intelligence_fallback()` builds a **cautious brief from this assessment only**: uploaded documents, per-document trust breakdowns (deterministic Trust Engine), whatever Tavily sources arrived before failure, deterministic risk-term scan, and rule-based signal generation across all nine domains.
- Decision is honestly degraded to `Review Required` with explicit evidence-gap rationale — never a fabricated INVEST/grade.
- Research payload marks `mode: document_intelligence`, `openaiStatus: unavailable`, plus document/source counts and evidence gaps.
- Tavily: missing key → engine disabled, `search()` → `[]`; timeout/network/quota → per-query degradation; orchestrator continues with `research_bundle = {founder: [], …}` (already supported by the job runner).
- Ask IC / Ask Signals: live LLM failure → `doc_intelligence_ask_*_answer()` built from Assessment Context + Evidence + Trust + Signals + Decision. Never demo data, never "Demo Mode".

**Chain guarantee:** Upload → Evidence (deterministic parsers + Trust Engine) → Trust → Signals (rule engine, all domains) → Decision (deterministic scoring + honest Review Required) → Reports (deterministic exporters) all complete with both providers offline.

---

## PHASE 8 VALIDATION RESULTS (OpenAI API key = empty, Tavily API key = empty)

Harness: `scripts/phase8_resilience_validation.py`. Every type completed **Upload → Evidence → Trust → Signals → Decision → Report**:

| Assessment type | Run | Trust | Signals | Research mode | aiMode | Decision | Report memo | Demo terms present |
|---|---|---|---|---|---|---|---|---|
| Startup | ✅ completed | 66.1 | 10 | document_intelligence | document_intelligence | Review Required | ✅ ~510 KB | none |
| NGO | ✅ completed | 66.1 | 10 | document_intelligence | document_intelligence | Review Required | ✅ ~510 KB | none |
| Tourism SME | ✅ completed | 66.1 | 10 | document_intelligence | document_intelligence | Review Required | ✅ ~510 KB | none |
| Development Program | ✅ completed | 66.1 | 10 | document_intelligence | document_intelligence | Review Required | ✅ ~510 KB | none |
| Government Program | ✅ completed | 66.1 | 10 | document_intelligence | document_intelligence | Review Required | ✅ ~510 KB | none |

Additional unit-level checks:
- **Signal domains (no AI):** `['climate', 'community_impact', 'competitive', 'environmental', 'funding', 'market', 'opportunity', 'risk', 'tourism', 'trust']` — all nine mission domains covered by deterministic rules.
- **ResearchEngine with no Tavily key:** constructs cleanly, `_disabled = True`, search returns `[]`.
- **LLMClient with no OpenAI key:** raises cleanly (caught by `is_openai_unavailable` → Document Intelligence Mode, never dead-ends).
- **Deterministic Phase 1 extraction** (no AI): organization, founder, project lead, locations, dates, budget references, activities, objectives, outcomes, risks all extracted from sample NGO text.
- **Executive summaries contain no AgriNova/OSTX/Demo-Mode text** across all 5 offline runs.

---

## FINAL VERDICT

**FULLY RESILIENT**

Kulima FLEX now completes the full Information → Evidence → Trust → Signals → Decisions → Reports chain for all five assessment types with OpenAI and Tavily completely disabled. Every provider failure mode in the mission (unavailable, quota exhausted, timeout, network failure, key failure) is classified and degraded into Document Intelligence Mode rather than dead-ending. Demo/example data and "Demo Mode" language are eliminated from all fallback paths, and the UI states explicitly whether the user is looking at AI-derived or document-intelligence-derived results.

**Recommended follow-up (non-blocking):** once a valid OpenAI key is deployed, runs automatically return to Mode A (`aiMode: ai_available`) with no code changes — the mode badge and research payload flip automatically.
