# Kulima FLEX VC Brain

**An Investment Intelligence Operating System for African Venture Capital.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit-red)](https://kulima-flex.streamlit.app/)

---

## Live Deployment

> **[https://kulima-flex.streamlit.app/](https://kulima-flex.streamlit.app/)**

---

## The Problem

African venture capital is analytically underserved. Pre-investment diligence on an African startup can take weeks of unstructured research, produce inconsistent outputs across analysts, and still miss critical founder and market signals that are embedded in local context — mobile money rails, cross-border FX dynamics, regulatory fragmentation, and trust networks built outside traditional Western data sources.

Kulima FLEX is built to close that gap.

---

## What Kulima FLEX Does

Kulima FLEX is a multi-agent Investment Intelligence Operating System that transforms a founder name and startup name into a complete IC-ready analysis in minutes.

It does not replace an investor's judgment. It prepares the evidence so that judgment can be applied faster, more consistently, and with greater confidence.

**A single analysis run produces:**

- Structured founder credibility assessment (track record, leadership, footprint, reputation)
- Startup market and business model analysis (TAM, GTM, competition, growth signals)
- Structured due diligence with open IC questions
- Africa-specific risk assessment with red-flag severity alerts
- Evidence Integrity Report — sources cross-checked, contradictions flagged, reliability rated A–F
- Twin Syndicate — five AI investor archetypes debate the deal independently and produce a consensus recommendation, dissent index, and committee transcript
- Continental Futures — three 36-month outcome scenarios under African market conditions (FX, infrastructure, regulatory)
- Partner-grade Investment Memo with executive summary, next steps, and explainability trail
- Fund Thesis Match — evaluates deal against your fund's sector, stage, geography, and evidence quality parameters
- Portfolio Intelligence Dashboard — cross-deal analytics across all stored runs

---

## Core Capabilities

### 1. Multi-Agent Intelligence Pipeline

Five specialized agents collaborate under an orchestrator — each with a distinct analytical mandate:

| Agent | Mandate |
|---|---|
| Founder Intelligence Agent | Credibility, leadership, track record, digital footprint, reputation signals |
| Startup Intelligence Agent | Market sizing, competitive landscape, business model, growth indicators |
| Due Diligence Agent | Structured IC checklist, open questions, key verification items |
| Risk Assessment Agent | Africa risk dimensions, FX exposure, regulatory environment, red-flag alerts |
| Investment Memo Agent | Partner-grade IC communication: executive summary → next steps |

### 2. Trust Layer & Evidence Integrity Engine

Every source collected from open intelligence is evaluated for reliability before it influences the analysis.

The Evidence Integrity Engine:
- Extracts factual claims across all sources
- Cross-checks claims for contradictions and inconsistencies
- Measures evidence depth (Thin → Comprehensive, on a five-level scale)
- Issues a **Reliability Rating** (Grade A–F with numeric score 0–100)
- Produces a verification checklist for the IC to act on

The Reliability Rating is displayed alongside every deal brief so analysts always know how much to trust the evidence, not just the conclusion.

### 3. Kulima Twin Syndicate

Five AI investor archetypes independently underwrite each deal and convene as a virtual Investment Committee:

| Archetype | Focus |
|---|---|
| Pan-African VC Partner | Founder-market fit, unit economics under FX stress |
| Development Finance Officer | Additionality, governance, gender lens, impact |
| Diaspora Angel Investor | Founder grit, community trust, operator credibility |
| Corporate VC Investor | Distribution synergies, strategic optionality |
| Global Tier-1 VC Partner | Category creation, global comparables, Series B path |

Each twin votes independently. A managing-partner moderator produces a debate transcript, dissent index, and consensus thesis. The syndicate recommendation is blended with the algorithmic score to produce the final IC output.

### 4. Continental Futures Engine

Three 36-month outcome scenarios (Bull / Base / Bear) modeled under African market conditions:

- Foreign exchange volatility and corridor dynamics
- Mobile money rail adoption rates
- Infrastructure constraints and leapfrog opportunities
- Regulatory environment shifts by market

Produces expected value estimates, survival probabilities, and per-scenario investor attractiveness scores.

### 5. Ask IC Assistant

Grounded follow-up Q&A anchored entirely in the generated report. Analysts can interrogate any aspect of the analysis — evidence quality, risk flags, syndicate reasoning, futures scenarios — without the system introducing outside information. Every response cites the artifact it draws from.

### 6. VC Thesis Engine

Each deal is evaluated against a configurable fund profile:

- Preferred sectors, stages, and geographies
- Check size range
- Excluded sectors
- **Evidence Fit** — derived from Reliability Rating, Evidence Depth, and Evidence Consistency

Produces an overall Thesis Match score (0–100%) with `PASS`, `WARN`, or `BLOCK` status. Runs independently of the core recommendation engine — a deal can be `INVEST` with low thesis fit, or `PASS` with high thesis fit. The two systems are intentionally separate.

### 7. Portfolio Intelligence Dashboard

Cross-deal analytics across all stored intelligence runs:

- KPI summary (total deals, recommendation breakdown, averages)
- Recommendation and Reliability Grade distribution charts
- Sector breakdown
- Score vs. Reliability scatter plot
- Portfolio Risk Matrix (4-quadrant: score × reliability)
- Top deals leaderboard (rankable by score, reliability, thesis match, confidence)
- IC Pipeline filter (Invest/Co-Invest + Grade A/B)
- Average Thesis Match across the portfolio

---

## Architecture

### High-Level Flow

```
Deal Intake
    │
    ▼
OSINT Research (Tavily, multi-query, Africa-weighted)
    │
    ▼
Evidence Integrity Engine ──► Reliability Rating (A–F)
    │
    ├──────────────────────────────────┐
    ▼                                  ▼
Founder Agent                    Startup Agent
(parallel)                       (parallel)
    │                                  │
    └──────────────┬───────────────────┘
                   ▼
        Diligence Agent  ║  Risk Agent  ║  Trust Graph
        (parallel underwriting pool)
                   │
                   ▼
          Score Aggregation
          Recommendation
                   │
          ┌────────┴────────┐
          ▼                 ▼
    Twin Syndicate    Continental Futures
    (5 votes +        (3 scenarios,
    debate)           36-month outlook)
          │                 │
          └────────┬────────┘
                   ▼
           Investment Memo Agent
                   │
                   ▼
        VC Thesis Engine
        (fund-specific match)
                   │
                   ▼
        Persist → Portfolio Intelligence Dashboard
```

### Package Structure

```
kulima-flex/
│
├── app.py                        # Streamlit entry point — executive dashboard
├── database.py                   # Database bootstrap CLI utility
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
│
├── kulima/                       # Core intelligence package
│   ├── __init__.py               # Package metadata and version
│   ├── config.py                 # Settings, investor archetypes, Africa market list
│   ├── models.py                 # Pydantic domain models for all artifacts
│   ├── llm.py                    # OpenAI client with retry and JSON parsing
│   ├── research.py               # Multi-query OSINT research engine (Tavily)
│   ├── scoring.py                # Score aggregation, confidence, explainability
│   ├── db.py                     # SQLite persistence — intelligence runs repository
│   ├── ui.py                     # Dashboard UI components (radar, charts, cards)
│   ├── trust_graph.py            # Trust and reputation network builder
│   ├── trust_graph_viz.py        # Trust graph visualization components
│   ├── trust_layer_ui.py         # Reliability Rating UI: badges, cards, reports
│   ├── evidence_integrity.py     # Evidence Integrity Engine (EIE)
│   ├── thesis.py                 # VC Thesis Engine — fund match evaluation
│   ├── portfolio_intelligence.py # Portfolio Dashboard — aggregation and charts
│   ├── comparison.py             # Side-by-side deal comparison logic
│   ├── compare_ui.py             # Deal comparison UI components
│   ├── ask_ic.py                 # Ask IC — grounded follow-up Q&A context builder
│   ├── export.py                 # PDF, CSV, JSON export renderers
│   ├── errors.py                 # Typed pipeline error classes
│   ├── roadmap.py                # Public roadmap data
│   │
│   ├── agents/                   # Specialized intelligence agents
│   │   ├── base.py               # BaseAgent contract
│   │   ├── founder_agent.py      # Founder credibility and leadership analysis
│   │   ├── startup_agent.py      # Market, model, and growth analysis
│   │   ├── diligence_agent.py    # IC diligence checklist
│   │   ├── risk_agent.py         # Africa risk assessment and red flags
│   │   ├── memo_agent.py         # Partner-grade IC memo generation
│   │   └── orchestrator.py       # Pipeline conductor — coordinates all agents
│   │
│   └── breakthrough/             # Signature intelligence modules
│       ├── syndicate.py          # Kulima Twin Syndicate — virtual IC
│       └── futures.py            # Continental Futures Engine — outcome simulation
│
├── docs/                         # Technical and product documentation
│   ├── architecture.md           # System architecture deep-dive
│   ├── trust-layer.md            # Evidence Integrity Engine specification
│   ├── thesis-engine.md          # VC Thesis Engine specification
│   └── portfolio-intelligence.md # Portfolio Dashboard specification
│
└── tests/
    ├── test_thesis_engine.py
    ├── test_portfolio_dashboard.py
    ├── test_trust_layer_ui.py
    ├── test_trust_graph_visualization.py
    ├── test_db_trust_layer.py
    ├── test_models_trust_layer.py
    ├── test_evidence_integrity.py
    ├── test_ask_ic_integrity.py
    ├── test_orchestrator_integrity.py
    ├── test_export_integrity.py
    ├── test_comparison.py
    └── test_pipeline.py
```

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- An [OpenAI API key](https://platform.openai.com/api-keys) (GPT-4.1-mini or GPT-4o recommended)
- A [Tavily API key](https://tavily.com/) for OSINT research

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/kulima-flex.git
cd kulima-flex

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux

# Edit .env and add your API keys
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | OpenAI API key |
| `TAVILY_API_KEY` | **Yes** | Tavily search API key |
| `OPENAI_MODEL` | No | Model for core agents (default: `gpt-4.1-mini`) |
| `SYNDICATE_MODEL` | No | Model for Twin Syndicate (default: `gpt-4.1-mini`) |
| `FUTURES_MODEL` | No | Model for Continental Futures (default: `gpt-4.1-mini`) |
| `KULIMA_DB_PATH` | No | Path to SQLite database (default: `founders.db`) |
| `KULIMA_ACCESS_MODE` | No | Access mode: `pilot`, `guest`, `open` (default: `pilot`) |

### Running Locally

```bash
streamlit run app.py
```

The application starts on [http://localhost:8501](http://localhost:8501).

### Verifying Setup

```bash
# Verify OpenAI connectivity
python quick_test.py

# Bootstrap / inspect the database
python database.py

# Run the full test suite
pytest
```

### Deploying to Streamlit Community Cloud

1. Push the repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository and set `app.py` as the entry point
4. Add your API keys in the Streamlit Secrets manager (Settings → Secrets)
5. Deploy

---

## Configuration

### Fund Thesis Profile

The default fund profile (`FundProfile` in `kulima/models.py`) represents a Pan-African early-stage fund:

- **Preferred sectors**: FinTech, AgTech, HealthTech, ClimateTech, Logistics, EdTech, InsurTech, Mobility
- **Preferred stages**: Pre-Seed, Seed, Series A, Early Stage
- **Preferred geographies**: Nigeria, Kenya, South Africa, Egypt, Ghana, and Pan-Africa
- **Check size**: $50K – $1M
- **Excluded sectors**: Crypto, Gambling, Real Estate, Tobacco, Weapons

To customize for your fund, instantiate `FundProfile` with your parameters and pass it to `evaluate_thesis_match()`.

### Investor Archetypes

The Twin Syndicate archetypes are defined in `kulima/config.py` as `INVESTOR_ARCHETYPES`. Each archetype specifies a name, firm, investment thesis bias, check size range, and decision-making style. These are fully configurable.

---

## IC Output Contract

Every analysis run produces the following structured artifacts:

| Artifact | Description |
|---|---|
| Executive Summary | Partner-grade narrative with deal thesis |
| Founder Assessment | Credibility, leadership, and footprint analysis |
| Startup Assessment | Market, model, competition, and growth signals |
| Market Assessment | Africa market opportunity sizing and dynamics |
| Risk Assessment | Africa-specific risks with red-flag severity ratings |
| Investment Recommendation | Invest / Co-Invest / Observe / Follow-On Watch / Pass |
| Next Steps | Prioritized IC action items |
| Evidence Integrity Report | Reliability Rating (A–F), Evidence Depth, Consistency status |
| Twin Syndicate Output | Five independent votes, debate transcript, consensus thesis, dissent index |
| Continental Futures | Three 36-month scenarios with probabilities and expected value |
| Thesis Match | Fund alignment score with Sector, Stage, Geography, and Evidence Fit |
| Explainability Trail | Per-dimension score rationale for every decision |
| Source Attribution | Every claim linked to its source URL with relevance and confidence scores |

---

## Roadmap

### Now Available

- [x] Multi-agent intelligence pipeline (5 agents + orchestrator)
- [x] OSINT research engine with Africa-weighted query strategies
- [x] Evidence Integrity Engine with source cross-checking and Reliability Rating (A–F)
- [x] Kulima Twin Syndicate (5 investor archetypes, debate, consensus)
- [x] Continental Futures Engine (36-month scenarios, African market physics)
- [x] Ask IC Assistant (grounded follow-up Q&A)
- [x] VC Thesis Engine with Evidence Fit (Sector, Stage, Geography, Evidence Fit)
- [x] Portfolio Intelligence Dashboard (KPIs, charts, heatmap, leaderboard)
- [x] Trust Graph (digital footprint and reputation network)
- [x] Deal Comparison (side-by-side analysis of two stored runs)
- [x] Multi-format export (PDF, CSV, JSON)
- [x] Persistent intelligence memory (SQLite, load previous runs)

### Next — Active Development

- [ ] Pitch deck ingestion (PDF parse → structured data → agent context enrichment)
- [ ] Founder interview ingestion (audio transcript → agent context)
- [ ] Caching layer for repeated OSINT queries (reduce latency and cost on re-analysis)
- [ ] Human-in-the-loop IC override with full audit log
- [ ] Multi-language OSINT support (French, Portuguese, Swahili, Arabic)

### Planned — Platform

- [ ] Role-based access control (Associate vs. Partner vs. LP view)
- [ ] CRM integration (Affinity, Attio, Notion)
- [ ] Comparable deal database with African startup outcomes
- [ ] Real-time monitoring agents for portfolio companies
- [ ] LP reporting module
- [ ] Multi-tenant SaaS architecture
- [ ] Fine-tuned Africa founder success model on proprietary outcomes

---

## FAQ

**Does Kulima FLEX make investment decisions?**  
No. It generates structured intelligence and a synthesized recommendation. All investment decisions remain with the human investor.

**Can it analyze startups outside Africa?**  
The system is designed and calibrated for African market dynamics. It can analyze other markets but the Africa-specific risk modeling, trust network analysis, and futures simulation are optimized for the African context.

**What happens if there is limited public information on a founder or startup?**  
The Evidence Integrity Engine detects and reports sparse evidence. Deals analyzed under sparse conditions receive a reliability qualifier and a limited-coverage disclosure. The system does not fabricate data.

**How is the Reliability Rating calculated?**  
The Evidence Integrity Engine extracts factual claims from each source, identifies genuine contradictions between independent sources, penalizes unresolvable conflicts and missing expected facts, and applies a bonus for well-corroborated claims. The result is a numeric integrity score (0–100) and a letter grade (A–F). See [`docs/trust-layer.md`](docs/trust-layer.md) for the full specification.

**Is the Thesis Engine part of the scoring system?**  
No. The Thesis Engine is intentionally separate from the core scoring and recommendation pipeline. A deal's Invest/Pass recommendation and all its scores are never modified by Thesis Match. The two systems are designed to be compared independently.

**Can I configure my own fund thesis?**  
Yes. Instantiate `FundProfile` with your preferred sectors, stages, geographies, check size range, and exclusions.

**What LLM models does Kulima FLEX use?**  
By default, all agents use `gpt-4.1-mini`. You can set `OPENAI_MODEL`, `SYNDICATE_MODEL`, and `FUTURES_MODEL` in your `.env` to use any OpenAI-compatible model.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to Kulima FLEX.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Security

API keys must be stored in `.env` only and never committed to version control. The `.gitignore` excludes `.env` by default. If you suspect a key was exposed, rotate it immediately at your provider's dashboard.

For security disclosures, please email the maintainers directly rather than opening a public issue.

---

*Kulima FLEX — Investment Intelligence for Africa's next generation of venture capital.*
