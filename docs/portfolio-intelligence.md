# Portfolio Intelligence

**Cross-Deal Analytics Dashboard — Specification**

---

## Overview

The Portfolio Intelligence Dashboard provides cross-deal analytics across all stored intelligence runs in the Kulima FLEX database. It transforms what would otherwise be a collection of individual reports into a coherent portfolio view — showing pattern, distribution, risk concentration, and relative standing of every analyzed deal.

Portfolio Intelligence is a read-only analytical layer. It does not modify any stored run, any score, or any recommendation.

---

## Data Source

All data displayed in the Portfolio Intelligence Dashboard is read from the `founders.db` SQLite database — the same database that stores every completed analysis run. No new external API calls are made. No reanalysis is performed.

The dashboard renders on stored runs and updates automatically as new runs are completed.

---

## Dashboard Sections

### 1. KPI Summary Row

Five top-line metrics displayed as metric cards:

| Metric | Description |
|---|---|
| **Total Deals** | Count of all stored intelligence runs |
| **Invest** | Count of runs with recommendation `INVEST` |
| **Co-Invest** | Count of runs with recommendation `CO_INVEST` |
| **Pass** | Count of runs with recommendation `PASS` |
| **Avg Thesis Match** | Mean `overall_match` percentage across all runs with thesis data |

### 2. Portfolio Analytics Charts

Four charts providing distribution and relationship views:

#### Recommendation Distribution
Bar chart showing count of each recommendation category:
`INVEST` | `CO_INVEST` | `OBSERVE` | `FOLLOW_ON_WATCH` | `PASS`

#### Reliability Grade Distribution
Bar chart showing count of each Reliability Grade across the portfolio:
`A` | `B` | `C` | `D` | `F`

#### Sector Breakdown
Bar chart showing deal count by sector/domain. Requires `startup_domain` to be captured in the stored run.

#### Fund Thesis Match Status
Bar chart showing count of `PASS` / `WARN` / `BLOCK` thesis status across all runs with thesis data.

### 3. Score vs. Reliability Scatter Plot

Scatter plot with:
- X-axis: `overall_score` (0–100)
- Y-axis: Reliability Grade (A–F, encoded numerically for the axis)
- Points sized by `confidence_level`
- Points colored by `recommendation` category
- Hoverable labels showing founder name, startup name, score, and grade

Used to identify deals with high scores but low evidence quality, or vice versa.

### 4. Portfolio Risk Matrix

A 2×2 quadrant chart:

|  | High Score | Low Score |
|---|---|---|
| **High Reliability** | IC Priority | High Confidence Pass |
| **Low Reliability** | Further Research | Low Signal |

Deals are plotted by (`overall_score`, `reliability_score`). The quadrant boundary is configurable (default: 70 for score, 70 for reliability).

This chart is the primary IC pipeline prioritization tool.

### 5. Top Deals Leaderboard

A sortable table of all deals, rankable by:

- **Overall Score** (default)
- **Reliability Grade**
- **Thesis Match**
- **Confidence Level**
- **Recommendation** (alphabetical tier ordering)

Table columns: Rank | Startup | Founder | Recommendation | Score | Grade | Thesis Match | Confidence

### 6. IC Pipeline Filter

A filtered view showing only deals meeting active investment criteria:
- Recommendation is `INVEST` or `CO_INVEST`
- Reliability Grade is `A` or `B`

This view is intended for Partner review — the highest-conviction, best-evidenced deals in the portfolio.

---

## Implementation Reference

| File | Responsibility |
|---|---|
| `kulima/portfolio_intelligence.py` | All aggregation logic, chart builders, and dashboard section renderers |
| `kulima/db.py` | `load_all_runs()` — retrieves all stored intelligence runs |
| `kulima/models.py` | `InvestmentBrief`, `ThesisMatchResult` — domain model definitions |
| `app.py` | Tab 6 — mounts the Portfolio Intelligence Dashboard |

### Test Coverage

| Test File | Coverage |
|---|---|
| `test_portfolio_dashboard.py` | KPI aggregation, chart data preparation, risk matrix quadrant assignment, leaderboard sorting, IC pipeline filter |

---

## Design Decisions

### No Reanalysis

Portfolio Intelligence never calls the LLM or the research engine. It reads persisted data and renders analytics. This keeps the dashboard fast, free to load, and consistent — the same run always shows the same data.

### Thesis Match Is Optional

Not all stored runs will have `thesis_match` populated — particularly runs created before the Thesis Engine was introduced. Portfolio Intelligence handles this gracefully: thesis-related metrics are calculated only from runs where thesis data exists, with a count indicator showing how many runs have thesis data vs. total runs.

### Score and Grade Are Independent Axes

The Score vs. Reliability chart and Portfolio Risk Matrix deliberately show score and grade as independent axes. This reflects a core product truth: a high score with low evidence quality deserves a different level of IC confidence than a high score with high evidence quality.

---

## Extending the Dashboard

To add a new chart or metric:

1. Add the aggregation logic to `kulima/portfolio_intelligence.py`
2. Add a rendering function that returns a Plotly figure or Streamlit component
3. Mount the new component in `app.py` Tab 6
4. Add test coverage in `test_portfolio_dashboard.py`

Data for the chart must come from fields already stored in `InvestmentBrief`. If a new metric requires a new field, that field must be added to the model and the persistence layer before the Portfolio Intelligence chart can use it.
