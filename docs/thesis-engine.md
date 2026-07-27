# VC Thesis Engine

**Fund Thesis Matching — Specification**

---

## Overview

The VC Thesis Engine evaluates each analyzed deal against a configured fund profile — producing a structured assessment of how well the deal aligns with the fund's mandate.

The Thesis Engine is intentionally separate from the core underwriting pipeline. Its outputs are informational. They do not alter the recommendation, overall score, or any component score produced by the core agents. A deal with an `INVEST` recommendation and low thesis fit is valid. A deal with a `PASS` recommendation and high thesis fit is equally valid. These are independent observations.

---

## Why a Separate Thesis Layer?

Investment analysis and thesis alignment are related but distinct questions.

- **Investment analysis** asks: is this a good deal, given the evidence?
- **Thesis alignment** asks: is this a deal *our fund* should pursue, given our mandate?

Conflating these would make the recommendation meaningless across different fund contexts. A seed fund focused on East African HealthTech and a global crossover fund focused on fintech Series B may analyze the same deal and reach the same investment recommendation — but their thesis alignment will differ completely.

The Thesis Engine makes this distinction explicit and measurable.

---

## Fund Profile

A `FundProfile` defines the fund's investment mandate:

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Fund name |
| `preferred_sectors` | `list[str]` | Sectors the fund actively targets |
| `preferred_stages` | `list[str]` | Investment stages the fund participates in |
| `preferred_geographies` | `list[str]` | Markets where the fund actively invests |
| `check_size_min` | `float` | Minimum check size in USD |
| `check_size_max` | `float` | Maximum check size in USD |
| `exclusions` | `list[str]` | Sectors the fund explicitly excludes |

### Default Fund Profile

The default configuration represents a Pan-African early-stage fund:

- **Preferred sectors**: FinTech, AgTech, HealthTech, ClimateTech, Logistics, EdTech, InsurTech, Mobility
- **Preferred stages**: Pre-Seed, Seed, Series A, Early Stage
- **Preferred geographies**: Nigeria, Kenya, South Africa, Egypt, Ghana, and Pan-Africa
- **Check size**: $50K – $1M
- **Excluded sectors**: Crypto, Gambling, Real Estate, Tobacco, Weapons

---

## Thesis Match Result

A `ThesisMatchResult` contains:

| Field | Type | Description |
|---|---|---|
| `overall_match` | `float` | Composite thesis match score (0–100) |
| `sector_fit` | `str` | High / Medium / Low / Blocked |
| `stage_fit` | `str` | High / Medium / Low |
| `geography_fit` | `str` | High / Medium / Low |
| `evidence_fit` | `str` | High / Medium / Low |
| `status` | `ThesisStatus` | `PASS` / `WARN` / `BLOCK` |
| `notes` | `list[str]` | Human-readable explanations for each dimension |

### Status Definitions

| Status | Condition |
|---|---|
| `PASS` | Overall match ≥ 70 and no BLOCK |
| `WARN` | Overall match 40–69 or notable gaps |
| `BLOCK` | Deal falls in an excluded sector — fund cannot invest |

---

## Scoring Model

### Component Scores (0–100 each)

#### Sector Fit ($S_{sec}$)

| Condition | Score | Label |
|---|---|---|
| Sector in `exclusions` | 0 | Blocked |
| Sector in `preferred_sectors` | 100 | High |
| General/unlisted sector | 65 | Medium |
| Non-preferred sector | 30 | Low |

If `S_sec = 0`, status is immediately set to `BLOCK` and `overall_match = 0`.

#### Stage Fit ($S_{stage}$)

| Condition | Score | Label |
|---|---|---|
| Stage in `preferred_stages` | 100 | High |
| Adjacent stage | 70 | Medium |
| Non-preferred stage | 40 | Low |

#### Geography Fit ($S_{geo}$)

| Condition | Score | Label |
|---|---|---|
| Market in `preferred_geographies` | 100 | High |
| Pan-Africa (general continental) | 70 | Medium |
| Non-preferred market | 40 | Low |

#### Evidence Fit ($S_{ev}$)

Derived from the Evidence Integrity Engine:

```
depth_multiplier = {
    Comprehensive: 1.0,
    Rich:          0.9,
    Adequate:      0.8,
    Partial:       0.7,
    Thin:          0.6
}

consistency_adjustment = {
    Consistent:   +5,
    Inconsistent: -10
}

S_ev = clamp(reliability_score × depth_multiplier + consistency_adjustment, 0, 100)
```

Evidence Fit reflects not whether the deal is good, but whether the evidence quality is sufficient to make a reliable investment judgment.

### Composite Score

$$\text{overall\_match} = \begin{cases}
0.0 & \text{if } S_{sec} = 0 \text{ (Blocked)}\\
0.35 \times S_{sec} + 0.25 \times S_{stage} + 0.20 \times S_{geo} + 0.20 \times S_{ev} & \text{otherwise}
\end{cases}$$

**Weighting rationale**:
- Sector Fit (35%): most decisive — wrong sector = wrong fund
- Stage Fit (25%): highly constraining — check size and portfolio construction depend on stage
- Geography Fit (20%): important but more flexible — funds often expand into adjacent markets
- Evidence Fit (20%): a quality signal — high thesis match with poor evidence quality warrants caution

---

## UI Integration

### Executive Overview (Tab 1)

The Thesis Fit card appears directly below the Reliability Rating card:

- Overall match percentage (e.g., "Thesis Match: 82%")
- Status badge (`PASS` / `WARN` / `BLOCK`) with color coding
- Four-column fit grid: Sector | Stage | Geography | Evidence
- Each cell shows a label (High / Medium / Low / Blocked) with appropriate color
- Expandable section with thesis notes (natural language explanations for each dimension)

### Portfolio Intelligence (Tab 6)

- **Avg Thesis Match** KPI card in the top summary row
- **Fund Thesis Match Status** bar chart (count of PASS / WARN / BLOCK across the portfolio)
- Leaderboard rank option: **Thesis Match** — sorts portfolio by `overall_match` descending

### Ask IC (Tab 4)

The Ask IC context pack includes a `[THESIS_FIT]` section. Analysts can ask:
- "Why is the thesis fit low?"
- "Which funds would be a better thesis match for this deal?"
- "What would change the thesis match to PASS?"

---

## Implementation Reference

| File | Responsibility |
|---|---|
| `kulima/thesis.py` | `evaluate_thesis_match()` — pure domain evaluation function |
| `kulima/models.py` | `FundProfile`, `ThesisMatchResult`, `ThesisStatus` definitions |
| `kulima/trust_layer_ui.py` | `render_thesis_fit_card()` — UI renderer |
| `kulima/agents/orchestrator.py` | Evaluates and attaches `thesis_match` to `InvestmentBrief` |
| `kulima/portfolio_intelligence.py` | Portfolio-level thesis aggregation and charts |
| `kulima/ask_ic.py` | `[THESIS_FIT]` context section for Ask IC |

### Test Coverage

| Test File | Coverage |
|---|---|
| `test_thesis_engine.py` | Sector matching, stage matching, geography matching, exclusion enforcement, Evidence Fit derivation, portfolio aggregation, legacy run compatibility |

---

## Critical Invariants

The following must never be violated:

1. `ThesisMatchResult` does not modify `recommendation`
2. `ThesisMatchResult` does not modify `overall_score`
3. `ThesisMatchResult` does not modify `founder_score`
4. `ThesisMatchResult` does not modify `startup_score`
5. `ThesisMatchResult` does not modify `market_score`
6. `ThesisMatchResult` does not modify `trust_score`
7. A `BLOCK` status means the fund cannot invest — it does not mean the startup is a bad investment
8. Thesis evaluation runs after all core agents have completed — it never interrupts the underwriting pipeline
