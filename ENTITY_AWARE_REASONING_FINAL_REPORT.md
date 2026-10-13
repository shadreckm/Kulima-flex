# Entity-Aware Reasoning — Finalization Report

**Date:** 2026-10-12 · **Verdict: ENTITY_AWARE_REASONING_COMPLETE**

## Problem

Despite a complete business plan being uploaded, generated reports could still
say "No evidence exists" / "Unknown startup" / "No product". This pass closed
the remaining reasoning-level gaps beyond the previous structural fixes.

## Files Modified (this pass)

| File | Change |
|---|---|
| `kulima/ask_ic.py` | **Phase 6** — Ask IC system prompt gains the full Source Priority contract (documents ARE evidence; web never overrules; "no evidence exists" banned when [DOCUMENTS] is populated); new "What evidence supports this?" handler returning a Source-A-first evidence map (docs → Assessment Context → Signals → Trust → research-only); context pack restructured — `[DOCUMENTS]` (Source A) gets **half the context budget** (was a quarter), up to 5 documents, and is rendered **before** web sources, which are now explicitly labelled `[EVIDENCE_SOURCES — Source C: corroborative only]`; document-type brief sources surface as `[DS#]` primary citations. |
| `kulima/decision.py` | **Phases 4–5** — entity-aware domain weight profiles (`ENTITY_DOMAIN_WEIGHTS`): Tourism/Climate are 0.16/0.14 (vs 0.09/0.07) for Tourism SMEs; community_impact 0.36 for NGOs/programs; `domain_weights_for()` with inheritance; composite uses the entity profile; active weights exposed in the decision payload for auditability. |
| `backend/app/schemas/dtos.py` | `DecisionSnapshot` gains `entityType` / `entityBand` / `entityRecommendation` / `entityReportTitle`. |
| `backend/app/routers/intelligence.py` | Snapshot surfaces the entity framework verdict + adaptive report title. |
| `kulima/agents/orchestrator.py` | **Reasoning fix** — document Trust Engine scores blended into the *overall* composite (15–35% weight, scaled by dossier size) so transient AI-quality dips can never drown a well-documented entity. |
| `kulima/agents/memo_agent.py` | Degraded skeleton rewritten to be document-grounded: states the provider rate limit explicitly, affirms uploaded documents remain the primary evidence, and never implies "no evidence". |
| `scripts/phase8_kulima_africa_test.py`, `scripts/phase9_tourism_test.py` | Corrected context-fetch endpoints. |

## Reasoning Improvements

1. **Source A drives reasoning everywhere**: extraction → entity profile →
   evidence corpus (chunk text, confidence 0.98, documents-first) → Ask IC
   context pack (half budget, primary section) → memo dossier (named doc
   citations) → fallback narrative.
2. **Trust blend**: document trust feeds both the trust-graph score (60–75%)
   and the overall composite (15–35%) — web thinness can no longer produce
   "unknown entity" verdicts.
3. **Ask IC** answers "What evidence supports this?" with the 5-layer
   Source-A-first evidence map and prefers `[D#]` citations over `[S#]`.

## Report Improvements

- Entity-adaptive titles: Investment Memo / Institutional Capacity Report /
  Program Performance Assessment / Governance Assessment / Tourism Resilience
  Report (verified live: "Tourism Resilience Report" for the tourism run).
- Decision snapshot now exposes the entity framework verdict.

## Signal Improvements

- Entity-specific signal domains generated per entity type with document-first
  attribution; gaps framed as diligence requests, never as "no evidence".

## Decision Improvements

- **Signals now materially change the outcome, not just the display.**
  Verified synthetically: identical risk-heavy signal corpus → Tourism SME
  composite **43.6 → "High Risk"** vs generic profile 49.4 "review_required";
  identical opportunity corpus → Tourism composite 66.6 vs 57.2 generic.
  Tourism (0.14), Climate (0.16) and Community (0.36 for NGOs) are core
  decision drivers in the entity weight profiles.

## Validation Results

### Phase 7 — Kulima Africa ✅

AI-path run (Groq, before its TPD wall): *"Kulima Africa is a **decision
intelligence company** that has developed **evidence-to-decision
infrastructure** to help **NGOs, development programs, DFIs, and government
programs** … **customer discovery** … **market validation** … **funding ask**"* —
served almost entirely from the uploaded document (2 web sources).
Negative phrases: **none**. Trust 72.4.

DI-path runs: *"assessed as a Startup based on 1 uploaded document (Business
Plan)"*, document trust blended (overall 28.5 from raw 19.6), trust 67.2,
risk 30 — never "no evidence".

### Phase 8 — Tourism ✅

Tourism Strategy / Business Plan / Financial Statements → **Tourism SME**
entity; Tourism 57 / Climate 64 / Community 65 — all *"identified in uploaded
primary document"*; trust 66.5, risk 30; decision through the Tourism
Resilience framework; report titled "Tourism Resilience Report"; zero
negative phrases.

### Ask IC ✅

Context pack verified: `[DOCUMENTS — SOURCE A: UPLOADED EVIDENCE (PRIMARY)]`
section carries full document content ahead of labelled corroborative web
sources; system prompt bans "no evidence exists" conclusions when documents
are present.

## Operational Note (non-blocking)

During validation Groq hit its **tokens-per-day** wall (TPD 200k, not a
burst) and other tiers remained quota-exhausted (OpenAI/Gemini 429,
OpenRouter/HF 402). All runs still completed through Document Intelligence
Mode with entity-aware, evidence-first narratives. The structural AI-path
improvements were proven live in the run where Groq had capacity (run 104).
The single-retry logic added this pass softens transient TPM bursts; TPD
exhaustion correctly fails over.

## Final Verdict

**ENTITY_AWARE_REASONING_COMPLETE**
