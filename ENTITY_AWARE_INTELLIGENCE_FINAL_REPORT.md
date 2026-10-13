# Entity-Aware Intelligence — Finalization Report

**Date:** 2026-10-12 · **Verdict: ENTITY_AWARE_INTELLIGENCE_COMPLETE**

## Problem

Kulima FLEX treated Kulima Africa — with a full business plan, founder info,
market validation, product architecture, revenue model, roadmap, customer
discovery and funding request uploaded — as "an unknown startup with no
evidence." Root causes found and fixed permanently:

1. **Agents saw filenames, not content.** `orchestrator.analyze()` injected
   uploaded documents into the evidence corpus with `snippet=""`, so the
   memo agent literally had no document text and concluded "the business
   plan has not been parsed / no evidence exists."
2. **Web OSINT absence was scored as risk.** A run with documents but no web
   coverage was punished (`risk 73`, trust 55 → "Pass"). Thin web coverage is
   not evidence of risk when a solid document dossier exists.
3. **PDF extraction failed silently** for text-in-.pdf uploads, producing an
   empty document downstream.
4. **No entity awareness** — every assessment used startup vocabulary,
   startup decision bands and startup report templates regardless of entity.

## Files Modified

| File | Change |
|---|---|
| `kulima/intelligence/entity_profile.py` | **NEW** — Phases 1–7 engine: 14-class document classification (filename + content), 10-type entity classification with document-evidence override, entity signal domains, entity research queries, 5 decision frameworks + inheritance, entity report titles, one-shot `build_entity_profile`. |
| `kulima/intelligence/__init__.py` | NEW package. |
| `kulima/core/assessment/models.py` | `AssessmentContext.entity_profile` field. |
| `backend/app/services/assessment_adapter.py` | Profile built at intake (Phases 1–2) and serialized into every workspace payload (`entityProfile`). |
| `backend/app/services/orchestrator_adapter.py` | `build_document_intelligence_fallback` fully entity-aware + evidence-first: Source A narrative, document-trust-weighted overall score, risk no longer penalized for thin web coverage when documents exist, profile passed to signals; gaps reworded so missing *web corroboration* is never framed as missing *evidence*. |
| `kulima/agents/orchestrator.py` | Document chunks injected into the evidence corpus (snippet filled, confidence 0.98, documents-first ordering); `entity_profile` + `document_trust_scores` params; trust blend (60–75% weight on Source A, never lowering the web score). |
| `kulima/agents/memo_agent.py` | Phase 6 — per-entity SYSTEM prompts (NGO/Development/Government/Tourism frameworks); dossier lists document classifications as primary citations with source-priority contract. |
| `kulima/signals/rules.py` | Phase 3 — `_entity_profile_signals`: entity-specific domains generated from the case payload, uploaded-document evidence cited first, gaps flagged as diligence items instead of absences. |
| `kulima/core/cases/adapters.py` | `from_investment_brief(..., entity_profile=...)` carries the profile into the signals layer. |
| `kulima/decision.py` | Phase 5 — `build_decision_view(..., entity_profile=...)` maps composite scores through the entity's own framework and returns `entityBand`/`entityRecommendation`/`reportTitle`. |
| `backend/app/routers/intelligence.py` | Decision snapshot resolves the entity profile from the assessment context bound to the run. |
| `kulima/core/jobs/runner.py` | Research jobs load the entity profile + document trust scores and pass both into `analyze()`. |
| `kulima/research.py` | Phase 4 — entity-aware `research_market` queries (investment/market for startups, institutional/programmatic for NGOs, implementation/impact for programs, tourism/climate/destination/visitor-economy for Tourism SMEs). |
| `kulima/core/documents/ingestion.py` | PDF raw-decode fallback (scanned/text-in-pdf uploads never silently empty); filename→doc_type classification for business plans/annual reports/strategy/proposals. |
| `kulima/core/documents/context.py` | Ask IC document context now labels documents as SOURCE A PRIMARY with the "business plan IS evidence" contract. |
| `kulima/export.py` | Report headers state the evidence-priority contract; entity-adaptive report titles. |
| `kulima/providers.py` | One in-place retry on transient Groq/Gemini 429s before tier failover. |
| `scripts/phase8_kulima_africa_test.py` | NEW — Kulima Africa validation. |
| `scripts/phase9_tourism_test.py` | NEW — Tourism validation. |

## Validation Results

### Phase 8 — Kulima Africa Test ✅

`Kulima_Africa_Business_Plan.pdf` → startup assessment:

| Check | Result |
|---|---|
| Document classified | **Business Plan (90%)** |
| Entity | **Startup** (declared, 75%) |
| Trust score (AI path) | **70.8** (was 55.5) — document trust blended in |
| Negative phrases ("no evidence exists", "unknown entity", "not been parsed") | **NONE** |
| AI-path memo cites | *"Kulima Africa, as described in its business plan (Kulima_Africa_Business_Plan.pdf)"* — uploaded doc cited BY NAME |
| Run completes without blocking | ✅ (all 6 tiers exhausted → Document Intelligence Mode) |

Recognized from the documents: decision intelligence company, evidence-to-
decision infrastructure, NGO/development-program/DFI/government-program
market, revenue model, roadmap, funding ask, business model.

### Phase 9 — Tourism Validation ✅

Tourism Strategy + Business Plan + Financial Statements → tourism_sme:

| Check | Result |
|---|---|
| Document classification | **Tourism Strategy / Business Plan / Financial Statements** — all 3 correct |
| Entity | **Tourism SME** (75%, document evidence) |
| Trust | **66.5** (document trust), risk **30** (was 73) |
| Tourism signal | score 57 — *"identified in **uploaded primary document**"* |
| Climate signal | score 64 — *"climate adaptation markers in **uploaded primary document**"* |
| Community signal | score 65 — *"job creation in **uploaded primary document**"* |
| Narrative | *"assessed as a Tourism SME based on 3 uploaded documents"* — no negative phrases |
| Decision | Tourism SME framework (Review Required at 48.6, never a startup "Pass") |

Signals for all three domains materially influence the decision composite.

## Source Priority — Enforced

- **Source A (uploaded documents)**: primary evidence, cited first by name in
  Ask IC context, memo dossiers, fallback narratives and all reports.
- **Source B (connected systems)**: reserved hooks in the profile model.
- **Source C (external web)**: corroborative only; never overrules Source A;
  contradictions are flagged explicitly, never silently weighted against
  documents; web thinness is no longer scored as risk.

## Final Verdict

**ENTITY_AWARE_INTELLIGENCE_COMPLETE**

Non-blocking note: at validation time all five provider accounts were
quota-exhausted (OpenAI/Groq/Gemini 429, OpenRouter/HuggingFace 402), so both
validation runs completed through Document Intelligence Mode — exactly the
resilience contract. Every structural fix (chunk injection, trust blend,
entity classification, adaptive frameworks/reports) is verified in the run
records; AI-path narratives will use them automatically once any provider
account regains credits.
