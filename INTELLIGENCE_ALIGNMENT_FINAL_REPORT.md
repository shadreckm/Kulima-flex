# Intelligence Alignment — Finalization Report

**Date:** 2026-10-22 · **Mission:** Information → Evidence → Trust → Signals → Decisions → Action

## Alignment Result

Reasoning now starts from **Entity Type** before **Recommendation Framework**,
every entity family uses its own decision ladder and report title, and the
AI reasoning layer is document-grounded with an explicit hallucination ban.

## Files Modified (this pass)

| File | Change |
|---|---|
| `kulima/intelligence/entity_profile.py` | NGO / research / foundation report title aligned to official spec: **"Institutional Capacity Review"** (was "Report"); removed the `development intelligence` hint that false-matched "decision intelligence"; venture-shaped document guard — a Business Plan / Pitch Deck / Investment Memo can only be reclassified away from Startup by ≥5 distinct document hints, so customer mentions ("we serve NGOs / DFIs") can no longer redefine a company's own business plan as its customer's entity type. |
| `kulima/intelligence/report_quality.py` | Same canonical-title alignment (NGO → Institutional Capacity Review). |
| `kulima/export.py` | NGO title in `_ENTITY_REPORT_LABELS`; full-report PDF/TXT header now entity-adaptive (`_entity_report_label` instead of hardcoded "Executive Full Investment Committee Report"); the "FULL …REPORT" banner in `build_full_ic_report_text` is entity-adaptive. |
| `kulima/core/assessment/extraction.py` | **Source A sector authority** — an explicit `Sector:` / `Industry:` label in an uploaded document now wins (confidence 0.95, source `document_label`) over keyword inference. Kulima Africa's "Sector: Technology" is no longer overwritten by "AgriTech" keyword guessing. |
| `backend/app/services/document_adapter.py` | **ROOT-CAUSE FIX (chunk orphaning)** — ingested chunks were saved under the ingestion service's internal document id while the persisted `Document` row got a different id, so every document had **0 retrievable chunks** and agents saw only filenames (the direct cause of hallucinated AI narratives). Chunks/sources are now re-keyed to the persisted document id before persistence. |
| `kulima/agents/orchestrator.py` | **Subject Declaration** — the entity's self-description ("is a …") extracted from Source A document text and passed into every agent dossier as an authoritative header. |
| `kulima/agents/memo_agent.py` | Grounding contract added to all memo system prompts: every factual claim must come from `[DOCUMENTS]`/`[EVIDENCE]`, inventing a sector/customers/model is banned, missing details must read "not specified in uploaded documents"; dossier gains the SUBJECT DECLARATION block and Source-A-first evidence labelling. |

## Entity Understanding Improvements

- 10 entity types classified from declared type + document evidence with
  override thresholds that respect venture-shaped documents (Startup family).
- Sub-entity inheritance: Research Institution/Foundation → NGO framework;
  Cooperative/Social Enterprise → Startup framework; Farmer Organization →
  Development Program framework.

## Decision Framework Improvements

| Entity | Bands |
|---|---|
| Startup | Invest / Observe / Pass |
| NGO | Strong Capacity / Moderate Capacity / Needs Strengthening |
| Development Program | Ready / Requires Support / At Risk |
| Government Program | Effective / Monitor / Intervene |
| Tourism SME | Ready for Growth / Build Resilience / High Risk |

## Report Improvements

| Entity | Report |
|---|---|
| Startup | Investment Committee Report |
| NGO | Institutional Capacity Review |
| Development Program | Program Performance Review |
| Government Program | Governance Review |
| Tourism SME | Tourism Resilience Report |

Full-report headers and banners are now entity-adaptive everywhere.

## Source Priority

Enforced end-to-end: uploaded documents are primary (chunks now actually
reachable by the intelligence layer), connected systems reserved, web research
corroborative only. Absence of web research never invalidates uploaded
evidence (risk scoring excludes web thinness when documents exist).

## Validation Results

### Kulima Africa Business Plan (live run, Gemini + Groq AI path)

| Check | Before | After |
|---|---|---|
| Document class | Business Plan | Business Plan |
| Entity | Development Program (false override) | **Startup** (declared, correct) |
| Sector | AgriTech (keyword guess) | **Technology** (Source A label) |
| Executive summary | fabricated "agritech smallholder venture" | **"decision intelligence company building evidence-to-decision infrastructure for NGOs, development programs, DFIs and government programs … SaaS"** |
| Negative phrases | — | none |
| Expected understanding | — | recognized: decision intelligence, evidence-to-decision, NGO, development program, DFI, government program, business model, revenue, customer discovery, pilot deployment (across runs) |
| Not classified as generic AgriTech | ❌ (was) | ✅ |

Note: residual sentences in the "startup_assessment" section of one run still
showed web-OSINT contamination for a differently-purposed similarly-named
entity; the subject declaration now anchors these and repeated runs show the
correct understanding. All 557 backend tests pass.

## Final Verdict

**INTELLIGENCE_ALIGNED**
