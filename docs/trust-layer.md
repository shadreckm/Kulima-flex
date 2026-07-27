# Trust Layer

**Evidence Integrity Engine — Specification**

---

## Overview

The Trust Layer is Kulima FLEX's evidence quality subsystem. Its purpose is to evaluate every source collected during OSINT research before that source influences any part of the analysis.

An analysis is only as reliable as the evidence behind it. The Trust Layer exists to make that reliability explicit, measurable, and visible — both to analysts reviewing the output and to the agents generating it.

The Trust Layer has two primary components:

1. **Evidence Integrity Engine (EIE)** — evaluates reliability of collected sources
2. **Trust Graph** — maps founder digital footprint and reputation network

---

## The Problem It Solves

Open-source intelligence on African startups and founders is often:

- Sparse — limited press coverage, few data room documents publicly available
- Inconsistent — conflicting revenue figures across different interviews or profiles
- Unverifiable at scale — manual cross-checking of dozens of sources is not practical

Without evidence quality measurement, an analysis system can produce confident-sounding conclusions from low-quality evidence. The Trust Layer prevents this by making evidence quality a first-class output of every analysis run.

---

## Evidence Integrity Engine (EIE)

### Inputs

- All sources collected by the OSINT research layer: URLs, relevance scores, raw content
- Source metadata: publication date, domain type, geographic context

### Processing Pipeline

1. **Claim Extraction**: The EIE reads each source and extracts discrete factual claims — specific figures, dates, names, assertions about the business, market, or founder.

2. **Cross-Source Comparison**: Claims from different sources are compared. The EIE identifies:
   - Corroborated claims — same fact independently reported across two or more sources (positive signal)
   - Contradictions — materially different versions of the same fact across independent sources (negative signal)
   - Unverified claims — asserted in only one source with no corroboration

3. **Missing Evidence Detection**: The EIE checks for expected categories of information (founder work history, company founding date, revenue or user metrics, regulatory status) and flags any that are entirely absent from the collected evidence.

4. **Score Calculation**: A numeric integrity score (0–100) is calculated based on:
   - Base: corroboration density across collected sources
   - Penalties: unresolvable contradictions, missing expected fact categories
   - Bonuses: well-corroborated claims across high-authority sources

5. **Grade Assignment**: The numeric score maps to a letter grade:

| Grade | Score Range | Interpretation |
|---|---|---|
| A | 85–100 | High confidence — strong corroboration, no material contradictions |
| B | 70–84 | Good confidence — mostly corroborated, minor gaps |
| C | 50–69 | Moderate confidence — some corroboration, notable gaps or minor contradictions |
| D | 30–49 | Low confidence — sparse evidence, significant gaps |
| F | 0–29 | Very low confidence — minimal evidence, unresolvable contradictions |

6. **Evidence Depth Level**: Separate from the integrity score, the EIE classifies the overall richness of collected evidence on a five-level scale:

| Level | Label | Description |
|---|---|---|
| 1 | Thin | Fewer than 3 usable sources, limited factual density |
| 2 | Partial | Some usable sources, key categories missing |
| 3 | Adequate | Core categories covered with reasonable corroboration |
| 4 | Rich | Broad coverage, multiple independent corroborations |
| 5 | Comprehensive | Deep coverage across all expected categories, strong corroboration |

7. **Evidence Consistency Status**: Binary classification:
   - `Consistent` — no material contradictions detected
   - `Inconsistent` — one or more unresolvable material contradictions present

### Outputs

The EIE produces an `EvidenceIntegrityResult` with:

- `integrity_score`: numeric (0–100)
- `reliability_grade`: letter (A–F)
- `evidence_depth`: level (1–5) and label
- `consistency_status`: `Consistent` / `Inconsistent`
- `corroborated_claims`: list of verified facts
- `contradictions`: list of detected conflicts with source attribution
- `missing_evidence_flags`: list of expected fact categories not found
- `verification_checklist`: prioritized list of items for IC follow-up

---

## Trust Graph

The Trust Graph is a network representation of the founder's digital footprint and reputation connections.

### Nodes

- Founder (central node)
- Affiliated organizations (employers, co-founded companies, advisors)
- Referenced individuals (co-founders, board members, investors mentioned)
- Media mentions (publication domains)

### Edges

- Employment or founding relationship
- Advisory relationship
- Investment relationship
- Media coverage

### Outputs

- Graph visualization rendered in the Executive Brief (Tab 1)
- Footprint density score contributing to founder credibility assessment
- Reputation network quality signal

---

## Reliability Rating in the UI

The Reliability Rating is displayed prominently in the Executive Overview tab:

- Large grade badge (A–F) with color coding (green → yellow → orange → red)
- Evidence Depth progress bar
- Evidence Consistency status indicator
- Expandable detailed report showing corroborated claims, contradictions, missing flags, and verification checklist

The rating is also surfaced in:
- Portfolio Intelligence Dashboard (grade distribution chart, risk matrix)
- Portfolio leaderboard (rankable by Reliability Grade)
- Ask IC context (analysts can ask: "Why is the reliability rating low?")
- VC Thesis Engine Evidence Fit calculation

---

## Integration with the Thesis Engine

The Evidence Integrity Engine outputs feed directly into the Thesis Engine's **Evidence Fit** dimension:

```
Evidence Fit = clamp(Reliability Score × Depth Multiplier + Consistency Adjustment, 0, 100)
```

Where:
- `Depth Multiplier` scales based on Evidence Depth level (1.0 at Comprehensive → 0.6 at Thin)
- `Consistency Adjustment` adds a bonus for consistent evidence and a penalty for inconsistent

Evidence Fit contributes 20% weight to the overall Thesis Match score.

**Critical invariant**: Evidence Fit and Thesis Match do not modify the core `recommendation`, `overall_score`, `founder_score`, `startup_score`, or `market_score`. The Trust Layer informs — it does not override.

---

## Implementation Reference

| File | Responsibility |
|---|---|
| `kulima/evidence_integrity.py` | Evidence Integrity Engine — full processing pipeline |
| `kulima/trust_graph.py` | Trust graph construction |
| `kulima/trust_graph_viz.py` | Graph visualization components |
| `kulima/trust_layer_ui.py` | Reliability Rating UI — badges, cards, detailed report |
| `kulima/models.py` | `EvidenceIntegrityResult`, `TrustGraphResult` model definitions |

### Test Coverage

| Test File | Coverage |
|---|---|
| `test_evidence_integrity.py` | EIE claim extraction, contradiction detection, scoring |
| `test_trust_layer_ui.py` | UI component rendering and grade display |
| `test_trust_graph_visualization.py` | Graph construction and visualization |
| `test_db_trust_layer.py` | Trust Layer persistence |
| `test_models_trust_layer.py` | Model validation and serialization |
