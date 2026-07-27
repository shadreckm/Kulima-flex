# Architecture

**Kulima FLEX VC Brain — System Architecture**

---

## Overview

Kulima FLEX is a multi-agent intelligence pipeline that converts unstructured startup information into structured, IC-ready investment analysis. It is designed as an Investment Intelligence Operating System — not a single AI call, but a coordinated sequence of specialized agents, an evidence integrity layer, a virtual investment committee, a futures simulation engine, and a persistent portfolio intelligence layer.

The system is built on the following principles:

- **Separation of concerns.** Each analytical function (founder assessment, risk, diligence, memo) is owned by a distinct agent with a bounded mandate.
- **Evidence first.** Every factual claim is sourced and evaluated for reliability before it influences the analysis. The system never presents conclusions without a traceability path.
- **Africa specificity.** The risk model, investor archetypes, market taxonomy, futures simulation, and OSINT query strategies are calibrated for African market dynamics — not generic global assumptions.
- **Additive intelligence layers.** The Trust Layer, Thesis Engine, and Portfolio Intelligence are layered on top of the core pipeline. They do not modify core scores or recommendations.

---

## Component Map

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py                               │
│            Streamlit Executive Dashboard                     │
│  Tab 1: Brief  │ Tab 2: Syndicate │ Tab 3: Futures           │
│  Tab 4: Ask IC │ Tab 5: Compare  │ Tab 6: Portfolio          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               kulima/agents/orchestrator.py                  │
│                    Pipeline Conductor                        │
└───┬─────────┬──────────┬──────────┬──────────┬─────────────┘
    │         │          │          │          │
    ▼         ▼          ▼          ▼          ▼
Founder   Startup   Diligence   Risk      Memo
Agent     Agent     Agent       Agent     Agent
    │         │          │          │          │
    └────────────────────┴──────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │   Score Aggregation  │
         │   kulima/scoring.py  │
         └──────────┬───────────┘
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   Twin Syndicate       Continental Futures
   5 investor votes     3 scenarios × 36 months
   kulima/breakthrough/ kulima/breakthrough/
   syndicate.py         futures.py
          │                   │
          └─────────┬─────────┘
                    ▼
         ┌──────────────────────┐
         │   Thesis Engine      │
         │   kulima/thesis.py   │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  kulima/db.py        │
         │  Intelligence Repo   │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Portfolio Intell.   │
         │  kulima/portfolio_   │
         │  intelligence.py     │
         └──────────────────────┘
```

---

## Module Reference

### Entry Points

| File | Purpose |
|---|---|
| `app.py` | Streamlit application — all six tabs, state management, UI composition |
| `database.py` | CLI utility to bootstrap or inspect the SQLite database |

### Core Package (`kulima/`)

| Module | Responsibility |
|---|---|
| `config.py` | Environment variables, investor archetype definitions, Africa market list |
| `models.py` | Pydantic domain models — typed contracts for all pipeline artifacts |
| `llm.py` | OpenAI client wrapper with retry logic, JSON parsing, and error handling |
| `research.py` | Multi-query OSINT research engine powered by Tavily |
| `scoring.py` | Score aggregation, confidence calculation, explainability trace |
| `db.py` | SQLite persistence — save and load intelligence runs |
| `errors.py` | Typed pipeline exception hierarchy |

### Trust Layer

| Module | Responsibility |
|---|---|
| `evidence_integrity.py` | Evidence Integrity Engine — claim extraction, cross-checking, reliability scoring |
| `trust_graph.py` | Digital footprint and reputation network builder |
| `trust_graph_viz.py` | Trust graph visualization rendering |
| `trust_layer_ui.py` | Reliability Rating UI components — badges, cards, evidence report |

### Intelligence Agents (`kulima/agents/`)

| Module | Responsibility |
|---|---|
| `base.py` | `BaseAgent` abstract class — agent contract |
| `founder_agent.py` | Founder credibility, leadership, track record, and digital footprint |
| `startup_agent.py` | Market sizing, business model, competition, and growth signals |
| `diligence_agent.py` | Structured IC checklist with open questions |
| `risk_agent.py` | Africa-specific risk dimensions and red-flag alerts |
| `memo_agent.py` | Partner-grade IC memo generation |
| `orchestrator.py` | Full pipeline coordination — runs agents, assembles `InvestmentBrief` |

### Breakthrough Modules (`kulima/breakthrough/`)

| Module | Responsibility |
|---|---|
| `syndicate.py` | Kulima Twin Syndicate — five investor archetype debate and vote |
| `futures.py` | Continental Futures Engine — 36-month scenario simulation |

### Platform Features

| Module | Responsibility |
|---|---|
| `thesis.py` | VC Thesis Engine — fund thesis match evaluation with Evidence Fit |
| `portfolio_intelligence.py` | Portfolio Dashboard — KPIs, charts, risk matrix, leaderboard |
| `comparison.py` | Side-by-side deal comparison logic |
| `compare_ui.py` | Deal comparison UI components |
| `ask_ic.py` | Ask IC Assistant — grounded follow-up Q&A context builder |
| `export.py` | PDF, CSV, and JSON export renderers |
| `roadmap.py` | Public roadmap data source |
| `ui.py` | Shared dashboard UI components (radar chart, syndicate bars, score cards) |

---

## Data Flow — Single Analysis Run

1. **Intake**: User submits founder name, startup name, and domain via the Streamlit form.
2. **OSINT Research**: `research.py` runs multiple Africa-weighted search queries via Tavily. Sources are collected with URLs, relevance scores, and raw content.
3. **Evidence Integrity**: `evidence_integrity.py` processes all collected sources. Claims are extracted, cross-checked for contradictions, and scored. A Reliability Rating (A–F) is produced.
4. **Parallel Agent Analysis**: The orchestrator dispatches `FounderAgent`, `StartupAgent`, `DiligenceAgent`, and `RiskAgent` in parallel. Each receives the research context and evidence integrity metadata.
5. **Score Aggregation**: `scoring.py` assembles per-dimension scores into `founder_score`, `startup_score`, `market_score`, and `overall_score`. A recommendation (`INVEST` / `CO_INVEST` / `OBSERVE` / `FOLLOW_ON_WATCH` / `PASS`) is derived.
6. **Trust Graph**: `trust_graph.py` builds a reputation and footprint network from the research evidence.
7. **Twin Syndicate**: `syndicate.py` invokes five investor archetypes independently. Each underwrites the deal against their thesis and votes. A moderator agent produces the debate transcript, dissent index, and consensus thesis.
8. **Continental Futures**: `futures.py` generates Bull, Base, and Bear scenarios across 36 months under African market conditions.
9. **Memo Generation**: `memo_agent.py` produces the partner-grade IC memo from all assembled context.
10. **Thesis Evaluation**: `thesis.py` evaluates Sector Fit, Stage Fit, Geography Fit, and Evidence Fit against the configured `FundProfile`. Produces a `ThesisMatchResult` with overall match percentage and status.
11. **Persistence**: The complete `InvestmentBrief` is serialized and written to SQLite via `db.py`.
12. **Dashboard Render**: `app.py` reads the `InvestmentBrief` and renders all six tabs.

---

## Key Design Decisions

### Why SQLite, not a hosted database?

Kulima FLEX is designed to run locally or on Streamlit Community Cloud without infrastructure dependencies. SQLite is sufficient for fund-scale workloads (hundreds to low thousands of analysis runs). A PostgreSQL migration path is a planned platform step.

### Why are scores separated from the Thesis Engine?

The Thesis Engine is intentionally isolated from the core scoring pipeline. A deal's recommendation is based on analytical merit. Thesis fit is a fund-specific filter applied afterward. Conflating the two would make the recommendation impossible to interpret across different fund mandates.

### Why five investor archetypes in the Syndicate?

The five archetypes cover the five most common African startup capital sources: local VC, development finance, diaspora angel, corporate VC, and global crossover. This ensures the deal is stress-tested against all investor perspectives likely to be present in an actual IC room.

### Why is the Evidence Integrity Engine separate from the research layer?

OSINT research produces raw sources. Evidence integrity is a judgment about those sources — their reliability, consistency, and depth. Separating these concerns allows either layer to evolve independently and prevents evidence quality bias from leaking into the research collection logic.

---

## Configuration Reference

All runtime configuration is managed through `kulima/config.py` reading from environment variables. See [`.env.example`](../.env.example) for the full variable list.

The `Settings` dataclass validates required secrets on startup. If `OPENAI_API_KEY` or `TAVILY_API_KEY` is missing, the application surfaces a clear configuration error rather than a cryptic API failure.

---

## Extension Points

To add a new intelligence agent:
1. Create a new file in `kulima/agents/` inheriting from `BaseAgent`
2. Implement the `analyze()` method with a typed return
3. Register it in `orchestrator.py`
4. Add corresponding fields to `InvestmentBrief` in `models.py`
5. Write tests in `tests/`

To add a new export format:
1. Add a renderer function to `kulima/export.py`
2. Wire it into the export section of `app.py`
