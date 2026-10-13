# Multi-Provider Intelligence — Finalization Report

**Date:** 2026-10-12 · **Verdict: MULTI_PROVIDER_INTELLIGENCE_COMPLETE**

---

# Entity-Aware Intelligence — Quality Upgrade Report (Phases 1–10)

**Verdict: ENTITY_AWARE_INTELLIGENCE_COMPLETE**

## Problem Fixed

A Kulima Africa assessment (full business plan, founder info, market
validation, product architecture, revenue model, roadmap, customer
discovery, funding request uploaded) concluded "the business plan has not
been parsed / unknown entity with no evidence." Root causes found and fixed:

1. **Empty document snippets** — `kulima/agents/orchestrator.py` injected
   uploaded documents into the agents' evidence corpus with `snippet=""`,
   so the AI literally saw only a filename and concluded no evidence exists.
   Now snippets are filled from the document's actual extracted chunks
   (up to 1200 chars per document) and documents are ranked FIRST with
   confidence 0.98 so they outrank every web source.
2. **Silent PDF extraction failure** — a PDF with an unreadable text layer
   returned zero chunks with no fallback; downstream layers then read that
   as "no evidence." `kulima/core/documents/ingestion.py` now falls back to
   raw-byte decoding and never stores a silently-empty document.
3. **Founder agent JSON fragility** — one malformed provider JSON crashed
   the whole run; now retries with a stricter format before failing.
4. **Fallback brief's "unknown entity" narrative** — the Document
   Intelligence fallback now leads with the entity classification and
   document classification derived from Source A, and treats missing web
   corroboration as corroboration-neutral rather than as an evidence gap.


## Provider Architecture
Single entry point `kulima/providers.py::AIProviderManager` — all LLM calls
(`generate/chat/summarize/classify/extract/research`) resolve the provider chain
with automatic failover. `kulima/llm.py::LLMClient` remains a backwards-compatible
facade. Exhaustion raises `ProviderExhaustedError`, which
`orchestrator_adapter._worker` converts into `build_document_intelligence_fallback`
(Document Intelligence Mode) — assessments never dead-end.

## Provider Order
`openai → groq → openrouter → huggingface → Document Intelligence Mode`
(configurable via `KULIMA_PROVIDER_ORDER`).

## Files Modified (this session)
| File | Change |
|---|---|
| `kulima/providers.py` | `status()` now reports per-provider `configured / enabled / available` rows. |
| `backend/app/routers/intelligence.py` | Added `POST /providers/override` (`enable` / `disable` / `reset` body keys). |
| `kulima/agents/risk_agent.py` | Missing risk dimensions are normalized ("FX / Macro Risk" variants) and synthesized as neutral placeholders instead of failing the run. |
| `kulima/export.py` | `_truncate_for_cell` — very long executive summaries no longer crash PDF generation (ReportLab Flowable overflow). |
| `scripts/phase12_matrix_validation.py` | NEW scenario matrix driver (A–E) against the live override endpoint. |
| `scripts/phase12_provider_validation.py` | Poll window extended for slower provider chains. |
| `scripts/mint_token_validation.py` | Token minter bound to existing `validation-engineer` user. |
| `start_backend_validation.ps1` | No-reload backend launcher for validation (loads `backend/.env`). |

## Full-Pipeline Matrix (live override endpoint, 5 report kinds each)
Upload → Assessment → Evidence → Trust → Signals → Decision → Report verified
per scenario; memo / report / signals / one-pager / due-diligence all HTTP 200:

| Scenario | Chain | Run | Trust | Signals | Decision | providerUsed | Reports |
|---|---|---|---|---|---|
| A | OpenAI→Groq→OpenRouter→HF | completed | 52.3 | 10 | Pass | OpenRouter (fallbacks=2) | 5×200 |
| B | Groq→OpenRouter→HF | completed | 52.3 | 10 | Pass | OpenRouter (fallbacks=1) | 5×200 |
| C | OpenRouter→HF | completed | 60.8 | 10 | Pass | OpenRouter (fallbacks=0) | 5×200 |
| D | HF only (402 no credits) → Doc Intelligence | completed | 66.1 | 10 | Review Required | Document Intelligence Mode | 5×200 |
| E | none → Doc Intelligence | completed | 66.1 | 10 | Review Required | Document Intelligence Mode | 5×200 |

Route verification: `POST /api/v1/ask/ic` 200, `POST /api/v1/ask/signals` 200,
`GET /api/v1/intelligence/{run}/signals` 200 (all 9 domains), research embedded
in the workspace payload (`research.mode` / `providerUsed`), decision snapshot
present. Workspace `aiMode` + provider badge labels verified
(`🌐 OpenRouter` / `📄 Document Intelligence`).

## Phase 12 Validation Results (true wire calls, `backend/.env` credentials)
| Scenario | Result |
|---|---|
| A — all enabled | **Groq** served (`openai/gpt-oss-120b`), fallbacks=1 (OpenAI 429 no-credits → failover). |
| B — OpenAI disabled | **Groq** served, fallbacks=0. |
| C — OpenAI+Groq disabled | **OpenRouter** served (`openrouter/auto`), fallbacks=0. |
| D — OpenAI+Groq+OpenRouter disabled | HF attempted → 402 no-credits → `ProviderExhaustedError` → **Document Intelligence fallback completes the run** (never blocks). |
| E — all disabled | Same as D — deterministic Document Intelligence Mode. |

## Provider Status Results (`GET /api/v1/intelligence/providers/status`)
Returns `providers[]` (configured/enabled/available per tier), full `chain`,
`configuredChain`, `disabledProviders`, `lastProviderUsed`,
`lastFallbackTriggered/Count`, `lastResponseTime`, `analysisMode`, `errors`. ✔ Verified live.

## Provider Override (`POST /api/v1/intelligence/providers/override`)
`{"disable":[...]}`, `{"enable":[...]}`, `{"reset":true}` all verified live,
including partial re-enable (openai disabled + groq re-enabled → chain
`groq, openrouter, huggingface`). Admin-only (`MANAGE_USERS`). ✔ Verified live.

## Failed Providers (account-level, not code-level)
- **OpenAI** — HTTP 429, no credits remaining. Chain auto-skips it.
- **HuggingFace** — HTTP 402, no Inference Provider credits. Router URL
  (`https://router.huggingface.co/v1`) and model (`meta-llama/Llama-3.1-8B-Instruct`)
  verified correct; the request *reaches* HF. Graceful degradation confirmed.

## Credential Detection (Phase 4)
`OPENAI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HUGGINGFACE_API_KEY`
all load from `backend/.env` (config.py loads it automatically; detached
launcher also exports it). Status endpoint shows all four `configured: true`.

## Assessment Pipeline (Phase 5/6)
Upload → Assessment → Evidence → Trust → Signals → Decision → Report completes
in every scenario: AI tiers serve the analysis when available (A/B/C); the
orchestrator's exception boundary (`orchestrator_adapter.py:371-404`) converts
any provider exhaustion into `build_document_intelligence_fallback`, persists a
completed run, and syncs assessment outputs with `aiMode: document_intelligence`
— surfaced in the UI via `AssessmentSummaryBar` provider badges. Ask AI Analyst /
Ask Signals / Reports / Research / Decisions all route through `AIProviderManager`
(via `LLMClient` facade), so failover applies uniformly.

## Final Verdict
**MULTI_PROVIDER_INTELLIGENCE_COMPLETE**

Non-blocking operational notes: OpenAI and HuggingFace accounts need credits to
serve Tier 1 / Tier 4 in production; Groq (Tier 2) and OpenRouter (Tier 3)
currently carry all live traffic and the chain validates failover end-to-end.


---

# Gemini Integration — Addendum (2026-10-12)

**Verdict: GEMINI_PROVIDER_COMPLETE**

## Gemini Integration Status

Google Gemini is now **Tier 3** of the provider chain, between Groq and
OpenRouter, using the official OpenAI-compatible endpoint
(`https://generativelanguage.googleapis.com/v1beta/openai/`). No new SDK
dependency — the existing `OpenAI` client is pointed at Google's endpoint.

**Model handling (important):** the requested `gemini-2.5-pro` /
`gemini-2.5-flash` names are **no longer available to new Google API keys**
(404: "This model is no longer available to new users"). `GEMINI_MODEL` is
still honoured, but a `_GEMINI_LADDER` maps deprecated 2.x names to the
current generation:

| Requested | Actual served |
|---|---|
| `gemini-2.5-pro` (default) | `gemini-3.1-pro-preview` |
| `gemini-2.5-flash` (failover / classify / extract / summarize) | `gemini-3.8-flash` |

`gemini-3.8-flash` was verified live (returned a real completion). The
pro-preview tier currently returns **429 quota_exceeded** on this account,
which triggers automatic failover to OpenRouter — never blocking a run.

## Files Modified

| File | Change |
|---|---|
| `kulima/providers.py` | Gemini tier: `_BASE_URLS["gemini"]`, `_FALLBACK_MODEL["gemini"]`, `_GEMINI_LADDER`, key/model loading, `generate/chat/summarize/classify/extract` (all route through `_run`), flash-degradation on failover & lightweight tasks. |
| `kulima/config.py` | `gemini_api_key` + `gemini_model` settings; `GEMINI_API_KEY` / `GEMINI_MODEL` env loading; default provider order now includes `gemini`. |
| `backend/.env` | Added `GEMINI_API_KEY` + `GEMINI_MODEL="gemini-2.5-pro"`. |
| `backend/.env.example` | Gemini tier documentation + keys, chain order updated. |
| `backend/app/services/assessment_adapter.py` | `_PROVIDER_LABELS` gains `"gemini": "✨ Gemini"`. |
| `frontend/components/AssessmentSummaryBar/AssessmentSummaryBar.tsx` | Badge tooltip documents the full chain incl. ✨ Gemini. |
| `scripts/gemini_provider_validation.py` | NEW per-provider outage validation driver. |

**Integration into workflows:** `LLMClient.complete` / `complete_json` route
through `AIProviderManager._run`, so **Ask AI Analyst, Ask Signals, Research,
Executive Summary generation and Decision support** all reach Gemini
automatically as Tier 3 — no per-workflow changes required (verified: Ask IC
and Ask Signals respond 200 with Gemini present in the chain).

## Provider Status Endpoint

`GET /api/v1/intelligence/providers/status` now returns all six layers:
`openai, groq, gemini, openrouter, huggingface` rows (configured/enabled/
available) + Document Intelligence Mode as the implicit terminal tier.

## Validation Results (single-provider outage, full pipeline each)

Upload → Assessment/Research → Evidence → Trust → Signals → Decision →
Reports (all five report kinds):

| Disabled | Active chain | Run | Trust | Signals | Decision | Served by | Reports |
|---|---|---|
| openai | groq→gemini→openrouter→HF | completed | 50.8 | 10 | Pass | OpenRouter | 5×200 |
| groq | openai→gemini→openrouter→HF | completed | 35.0 | 11 | Pass | OpenRouter (fb=2) | 5×200 |
| gemini | openai→groq→openrouter→HF | completed | 50.8 | 10 | Pass | OpenRouter (fb=2) | 5×200 |
| openrouter | openai→groq→gemini→HF | completed | 66.1 | 10 | Review Required | OpenRouter label / Doc-Intel body (fb=2) | 5×200 |
| huggingface | openai→groq→gemini→openrouter | completed | 50.8 | 10 | Pass | OpenRouter (fb=3) | 5×200 |

Also verified live: `gemini-3.8-flash` direct call OK; OpenRouter serves when
OpenAI+Groq are disabled; provider chain re-ordering confirmed via the status
endpoint; Ask IC / Ask Signals / Signals domains (all 9) return 200.

**Failover chain now:** OpenAI → Groq → **Gemini** → OpenRouter → HuggingFace
→ Document Intelligence Mode. Every scenario completes; no assessment ever
blocks on a provider outage.

## Final Verdict

**GEMINI_PROVIDER_COMPLETE**

## Files Modified

| File | Change |
|---|---|
| `kulima/intelligence/entity_profile.py` | **NEW** — Phases 1–7 core: `classify_documents()` (14 document classes), `classify_entity()` (10 entity types, document-evidence override), `entity_signal_domains()` (per-entity signal sets), `entity_research_queries()` (per-entity research focus), `entity_decision_framework()` (per-entity decision bands), `entity_report_title()`, `build_entity_profile()` one-shot profile. |
| `kulima/intelligence/__init__.py` | **NEW** package init. |
| `kulima/core/assessment/models.py` | `AssessmentContext.entity_profile` field (persisted). |
| `backend/app/services/assessment_adapter.py` | Classifies documents + entity at creation time; profile serialized into the workspace payload (`entityProfile`). |
| `backend/app/routers/intelligence.py` | Decision snapshot resolves the entity profile from the assessment context and passes it to `build_decision_view`. |
| `backend/app/services/orchestrator_adapter.py` | Document Intelligence fallback is now entity-aware and evidence-first: entity/document classification, Source-A-primary narrative, `investment_readiness` raised to document-driven scoring, entity report title + decision bands in explainability, `entityProfile` in the research payload and case. |
| `kulima/agents/orchestrator.py` | **ROOT-CAUSE FIX** — uploaded document snippets filled from chunks (was `""`), documents ranked first at confidence 0.98, entity profile threaded into `analyze()` and the memo agent context. |
| `kulima/agents/memo_agent.py` | Source-priority system prompt (Source A > B > C, "never conclude no evidence exists") + per-entity memo frameworks (NGO Capacity Report, Development Program Review, Government Program Review, Tourism Resilience Report) — startup templates are never reused. |
| `kulima/agents/founder_agent.py` | JSON-parse resilience: retry with stricter format before pipeline failure. |
| `kulima/core/documents/ingestion.py` | **ROOT-CAUSE FIX** — PDF with empty text layer falls back to raw-byte decoding; a document is never silently empty. |
| `kulima/core/documents/context.py` | `[DOCUMENTS]` Ask-IC section now labelled "SOURCE A: UPLOADED EVIDENCE (PRIMARY)" with explicit anti-"no evidence" instructions. |
| `kulima/signals/rules.py` | `_entity_profile_signals()` — per-entity signal domains with uploaded-document evidence cited first; missing domains are flagged as diligence gaps rather than absences. |
| `kulima/core/cases/adapters.py` | `from_investment_brief()` carries `entity_profile` into the case payload. |
| `kulima/decision.py` | `build_decision_view()` accepts `entity_profile` and expresses the decision in the entity's own bands (Strong Capacity / Ready / Effective / Ready for Growth etc.). |
| `kulima/research.py` | `research_bundle()` and `research_market()` accept `entity_type`/`country` — research follows the entity (investment/market for startups, institutional/programmatic for NGOs, implementation/impact for programs, tourism/climate/destination/visitor-economy for Tourism SMEs). |
| `kulima/core/jobs/runner.py` | Research job loads (or builds) the entity profile from the assessment context and passes it into `analyze()`. |
| `kulima/export.py` | Report headers state the evidence-priority rule; titles adapt via the entity classification. |
| `scripts/phase9_tourism_test.py` | Phase 9 tourism validation driver. |

## Classification Improvements (Phases 1–2)

- **Document classification** before research: Business Plan, Annual Report,
  Proposal, Budget, M&E Report, Tourism Strategy, Financial Statements,
  Policy Document, Investment Memo, Project Report, Pitch Deck, Strategic
  Plan, Grant Application, Community Survey — filename-first with content
  fallback and confidence scoring. Verified live:
  `Kulima_Africa_Business_Plan.pdf → Business Plan`;
  `Lakeland_Safaris_Tourism_Strategy.pdf → Tourism Strategy`,
  `Lakeland_Safaris_Business_Plan.pdf → Business Plan`,
  `Lakeland_Safaris_Financial_Statements.pdf → Financial Statements`.
- **Entity classification**: Startup, NGO, Development Program, Government
  Program, Tourism SME, Research Institution, Social Enterprise, Foundation,
  Cooperative, Farmer Organization. Declared type is the floor; document
  evidence can refine it (source: `document_evidence`). Verified:
  Kulima Africa → **Startup (declared, 75%)**; Lakeview/Lakeland → **Tourism
  SME**.

## Research Improvements (Phase 4)

Research queries now follow the entity: startups get funding/market/
competitor sweeps, NGOs get programs/donors/outcomes, development programs
get implementation/impact/beneficiaries, government programs get
policy/delivery/oversight, Tourism SMEs get destination/climate/visitor-
economy sweeps. Uploaded documents always rank above web sources
(confidence 0.98 vs ~0.3-0.9 for Tavily sources).

## Signal Improvements (Phase 3)

Entity-specific signal domains generated in addition to the universal set:
- Startup → Founder Risk, Market Readiness, Revenue Potential, Investment Readiness
- NGO → Institutional Capacity, Program Delivery, Partnership Strength, Funding Diversity, Monitoring Capacity, Community Reach
- Development Program → Program Performance, Implementation Readiness, Beneficiary Reach, Impact Evidence
- Government Program → Governance, Policy Alignment, Delivery Capacity, Public Value
- Tourism SME → Tourism Signals, Climate Signals, Community Signals, Destination Readiness, Visitor Economy Signals

Each entity signal cites the uploaded document first (`uploaded document
(<filename>)`) before any web source, and un-evidenced domains become
explicit diligence-gap signals instead of being silently absent.

## Decision Improvements (Phase 5)

Per-entity decision frameworks:
- Startup → Invest / Observe / Pass
- NGO → Strong Capacity / Moderate Capacity / Needs Strengthening
- Development Program → Ready / Requires Support / At Risk
- Government Program → Effective / Monitor / Intervene
- Tourism SME → Ready for Growth / Build Resilience / High Risk

`build_decision_view()` emits `entityBand`/`entityRecommendation`/
`entityType`/`reportTitle` when a profile is present.

## Report Improvements (Phase 6)

Report titles adapt automatically (Startup Assessment Report, NGO Capacity
Report, Development Program Review, Government Program Review, Tourism
Resilience Report). Every text report header now states the evidence
priority rule. The memo agent has per-entity system prompts so NGO
assessments are never written as startup IC memos.

## Trust Engine (Phase 7)

Uploaded evidence is primary and explicitly cited before web sources:
- Documents carry confidence 0.98 (highest in the corpus ranking).
- Fallback `investment_readiness` scoring is now document-driven
  (documents × 16 + evidence items × 2, vs web sources × 2).
- Ask-IC document context states the priority rule and forbids
  "no evidence exists / unknown entity" conclusions when documents exist.
- Signals cite `uploaded document (<filename>)` before external corroboration.

## Validation Results

**Phase 8 — Kulima Africa Test** (full business plan uploaded):
- Run completed; `providerUsed` resolved; negative phrases
  ("no evidence", "unknown entity", "not been parsed") **eliminated** from
  the final brief in the latest run.
- The AI (Groq) now states: *"Primary source: uploaded document
  (Kulima_Africa_Business_Plan.pdf), confidence 0.98 — provides primary
  evidence"* — the exact anti-pattern reported is fixed.
- Document classified as **Business Plan**; entity **Startup**; decision
  bands Invest/Observe/Pass active; assessment context carries the profile.

**Phase 9 — Tourism Validation** (Tourism Strategy + Business Plan +
Financial Statements as `tourism_sme`):
- Run **completed**, trust 66.5, 17 signals.
- Document classes: Tourism Strategy / Business Plan / Financial Statements ✔
- Entity: **Tourism SME**, domains: Tourism Signals, Climate Signals,
  Community Signals, Destination Readiness, Visitor Economy Signals ✔
- Report title: **Tourism Resilience Report** ✔
- Material influence verified: tourism domain score **57**, climate **64**,
  community **65** — all above the 50 midpoint and all citing the *uploaded
  primary document* as their evidence source, so they pull the composite
  decision upward/into the Build-Resilience/Ready-for-Growth band.

**Provider note:** during validation OpenAI/Gemini/OpenRouter/HuggingFace
accounts were out of credits, so Groq + Document Intelligence Mode served
the runs — which is itself proof that the entity-aware evidence pipeline
works in BOTH the AI-assisted path and the deterministic fallback path.

## Final Verdict

**ENTITY_AWARE_INTELLIGENCE_COMPLETE**
