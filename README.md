# Kulima FLEX

**AI Investment Intelligence Operating System for Africa**

> From a single Streamlit script to a multi-agent IC room that researches, scores, debates, simulates, and memos African venture deals — with source attribution and explainable conviction.

---

## Why this wins

| Judge lens | How Kulima FLEX scores |
|---|---|
| Technical Complexity | 5 specialized agents + orchestrator, trust graph, OSINT research layer, persistence |
| Innovation | **Kulima Twin Syndicate** — five AI investor twins debate & vote like a live IC |
| Communication | Partner-grade IC memo (Exec Summary → Next Steps) |
| Creativity | **Continental Futures Engine** — 36-month Africa-physics outcome simulation |
| Scalability | Modular `kulima/` package, repo pattern, agent contracts, env-driven config |
| Business Impact | Compresses days of pre-IC work into minutes for Africa-focused funds |
| UX | Executive dashboard, DNA radar, syndicate votes, red-flag alerts, memory |

### Breakthrough feature judges haven't seen

**Kulima Twin Syndicate** clones five African-capital archetypes into a virtual Investment Committee:

1. Pan-African early-stage VC  
2. DFI / development finance  
3. Diaspora angel  
4. Corporate strategic (CVC)  
5. Global Series A crossover  

Each twin independently underwrites, votes, states conditions, then a managing-partner moderator produces a debate transcript, dissent index, and consensus thesis — **purpose-built for African deal physics**, not a generic ChatGPT wrapper.

Paired with the **Continental Futures Engine** (bull / base / bear under FX, regulatory, infrastructure, and mobile-money rails).

---

## Quick start

```bash
cd "Kulima vc brain"
python -m venv venv
# Windows:
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Add OPENAI_API_KEY and TAVILY_API_KEY to .env
streamlit run app.py
```

Smoke tests:

```bash
python quick_test.py   # OpenAI
python test.py         # Tavily
python database.py     # schema bootstrap
```

---

## Architecture

```
app.py                          # Executive Streamlit OS
database.py                     # DB bootstrap CLI
kulima/
  config.py                     # Settings + investor archetypes
  models.py                     # Pydantic domain models
  llm.py                        # OpenAI client + JSON parsing
  research.py                   # Tavily OSINT research engine
  scoring.py                    # Scores, confidence, explainability
  trust_graph.py                # Digital footprint / reputation graph
  db.py                         # SQLite intelligence repository
  ui.py                         # Dashboard visuals (radar, charts)
  agents/
    base.py
    founder_agent.py            # Credibility, leadership, reputation
    startup_agent.py            # Market, model, growth, readiness
    diligence_agent.py          # IC diligence checklist
    risk_agent.py               # Africa risk physics + red flags
    memo_agent.py               # Partner-grade communication
    orchestrator.py             # Full pipeline conductor
  breakthrough/
    syndicate.py                # AI Investor Twin Syndicate
    futures.py                  # Continental Futures Engine
```

### Pipeline

```
Intake → OSINT Research
      → Founder Agent ∥ Startup Agent
      → Diligence Agent → Risk Agent
      → Trust Graph
      → Twin Syndicate (5 votes + debate)
      → Continental Futures (36m scenarios)
      → Memo Agent (IC paper)
      → Persist + Executive Dashboard
```

---

## Deep audit of the original codebase

### What existed
- Monolithic `app.py` (~300 lines): one Tavily search, one GPT call, heuristic scores, SQLite dump
- `database.py`: table create only
- Hardcoded API keys in `test.py` and `.vscode/mcp.json` (**critical security issue**)
- No agents, no explainability, no Africa thesis, no investor UX beyond raw markdown

### Gaps vs hackathon criteria
1. **Technical complexity** — single linear script  
2. **Innovation** — commodity “search + summarize”  
3. **Communication** — unstructured free text  
4. **Creativity** — no signature feature  
5. **Scalability** — no package boundaries  
6. **Business impact** — toy demo, not IC workflow  
7. **UX** — form + blob of text  

### What we transformed
Everything above → Investment Intelligence OS with modular agents, breakthrough syndicate, futures simulation, visual scorecards, source attribution, and partner-grade outputs.

---

## File-by-file implementation map

| File | Purpose |
|---|---|
| `app.py` | Executive dashboard & deal intake |
| `kulima/agents/orchestrator.py` | Multi-agent pipeline |
| `kulima/agents/founder_agent.py` | Founder credibility / leadership / footprint |
| `kulima/agents/startup_agent.py` | Market / competition / model / readiness |
| `kulima/agents/diligence_agent.py` | Structured diligence + open questions |
| `kulima/agents/risk_agent.py` | Risk dimensions + red flags |
| `kulima/agents/memo_agent.py` | IC memo sections |
| `kulima/breakthrough/syndicate.py` | Twin Syndicate IC |
| `kulima/breakthrough/futures.py` | 36-month outcome simulator |
| `kulima/trust_graph.py` | Trust / reputation network |
| `kulima/research.py` | Multi-query Tavily OSINT |
| `kulima/ui.py` | Radar, syndicate bars, futures charts |
| `kulima/db.py` | Persistent intelligence runs |
| `kulima/models.py` | Typed contracts for all outputs |
| `kulima/scoring.py` | Aggregation + explainability |
| `kulima/llm.py` / `config.py` | Model + Africa investor personas |

---

## IC output contract (every run)

1. Executive Summary  
2. Founder Assessment  
3. Startup Assessment  
4. Market Assessment  
5. Risk Assessment  
6. Investment Recommendation  
7. Next Steps  

Plus: scorecards, confidence level, red flags, syndicate votes, futures scenarios, trust graph, sources, explainability trail.

---

## Features shipped for the hackathon (NOW)

- [x] Multi-agent architecture (5 agents + orchestrator)  
- [x] Founder intelligence (credibility, leadership, footprint, reputation)  
- [x] Startup intelligence (market, competition, model, growth, readiness)  
- [x] Due diligence + risk agents with red-flag alerts  
- [x] Trust graph  
- [x] Twin Syndicate (breakthrough)  
- [x] Continental Futures Engine  
- [x] Executive dashboard + DNA radar + visual votes  
- [x] Explainable AI + source attribution + confidence  
- [x] Partner-grade memo sections  
- [x] Persistent founder memory  

## Features AFTER the hackathon

- Live founder interview ingestion (audio → transcript → agent context)  
- CRM / Affinity / Attio sync  
- Multi-deal portfolio heatmaps & LP reporting  
- Human-in-the-loop IC override with audit log  
- Fine-tuned Africa founder success model on proprietary outcomes  
- Multi-language OSINT (FR/PT/SW/AR)  
- Real-time news monitoring agents  
- Role-based access for associates vs partners  
- Export to PDF IC pack / Notion  

---

## Prioritized roadmap

### P0 — Demo day (done)
Ship OS, syndicate, futures, dashboard, memo, security hygiene (env keys).

### P1 — 48 hours post-hackathon
- Parallelize agent LLM calls (asyncio / threads)  
- PDF IC pack export  
- Caching layer for repeated OSINT queries  
- Stronger Africa sector taxonomies (fintech, agritech, health, climate, logistics)

### P2 — Pilot with one fund
- Primary data rooms (pitch deck parse)  
- Comparable deal database  
- Partner feedback loop → score calibration  

### P3 — Platform
- Multi-tenant SaaS, billing, API, webhook alerts on red flags  

---

## Security note

API keys must live in `.env` only. The previous hardcoded Tavily key in `test.py` / MCP config has been removed. **Rotate that key** if it was ever committed or shared.

---

## Team lens (how we designed this)

- **Sequoia / a16z / YC** — conviction narrative, founder quality, clear Invest/Pass  
- **McKinsey** — structured diligence dimensions and next steps  
- **Palantir** — OSINT fusion, risk graph, red-flag severity  
- **MIT AI** — multi-agent decomposition + futures simulation  
- **Ex-CIA OSINT** — source attribution, footprint analysis, trust network  

---

Built for Africa. Tuned for Investment Committees. Designed to win.
