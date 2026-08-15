# OSTX Investor Demo Pack

**Product:** Kulima OS  
**Audience:** Judges, investors, pilot users  
**Mode:** Offline-ready validation dataset (no OpenAI credits required)

---

## Implementation Verification

| Item | Status | Evidence |
|---|---|---|
| Report Downloads Fixed | ✅ | PDF/TXT memo, full report, signals, due diligence, one-pager via `/reports` |
| Coverage Metrics Fixed | ✅ | Analytics uses full run payloads; Evidence Coverage + Signal Coverage render |
| Offline Demo Mode Active | ✅ | Orchestrator falls back to OSTX template when live LLM/OSINT fails |
| URL Run Sync Active | ✅ | `?run=` works on Flex/Signals/Evidence/Reports; stable IDs registered |
| OSTX Validation Cases Loaded | ✅ | AgriNova / GreenLink / SolarHarvest seeded + live deep-links |

### Stable demo deep-links

| Case | Stored Run | Live URL ID |
|---|---|---|
| AgriNova Malawi | `#30` (local DB may vary) | `ostx-agrinova-malawi` |
| GreenLink Foods | next id | `ostx-greenlink-foods` |
| SolarHarvest Cooperative | next id | `ostx-solarharvest-cooperative` |

Example routes:

- `/flex?run=ostx-agrinova-malawi`
- `/signals?run=ostx-greenlink-foods`
- `/evidence?run=30`
- `/reports?run=30`

Refresh locally:

```bash
python scripts/seed_demo_data.py --refresh --prepare-demo
```

---

## Case 1 — AgriNova Malawi

| Field | Value |
|---|---|
| Founder | Dr. Chimwemwe Phiri |
| Sector / Geo / Stage | AgTech / Malawi–SADC / Seed |
| Outcome | **INVEST** |
| Trust Score | **88** (target band 85–95) |
| Overall Score | 86 |
| Integrity | Grade **A** / 92 |
| Confidence | High (0.89) |

### Signals
- Founder strength: USAID agronomy track record
- Traction: 14,000 farmers, $1.2M ARR, 310% YoY
- Thesis match: 91% PASS
- Residual signal: MWK FX exposure (medium)

### Evidence
- 5+ corroborating sources (ministry registry, USAID, partner rails)
- Zero contradictions
- Comprehensive evidence depth
- Trust graph density high (institutions + payments partner)

### Reports
- IC Memo, Full IC Report, Signals Report, Due Diligence Summary, Executive One-Pager

### Analytics contribution
- Drives Invest count, lifts average trust/score, full signal coverage

### Decision Snapshot
- Verdict: INVEST
- Reliability: A / 92
- Next action: Allocate $350K Seed check

---

## Case 2 — GreenLink Foods

| Field | Value |
|---|---|
| Founder | Kondwani Banda |
| Sector / Geo / Stage | Urban Ag / Zambia / Pre-Seed |
| Outcome | **OBSERVE** |
| Trust Score | **64** (target band 55–70) |
| Overall Score | 62 |
| Integrity | Grade **C** / 68 |
| Confidence | Medium (0.72) |

### Signals
- Active hydroponic production
- Power-grid / diesel cost vulnerability (HIGH)
- Customer concentration (top-2 = 65%)
- Syndicate dissent elevated (28%)

### Evidence
- Material contradiction: claimed 30 retail partners vs 12 verified
- Unsupported nutrient-yield claim
- Moderate depth, conflicts status

### Reports
- Full export suite available from stored brief

### Analytics contribution
- Observe bucket; raises average contradictions / unsupported claims

### Decision Snapshot
- Verdict: OBSERVE
- Reliability: C / 68
- Next action: 6-month watch; solar hybrid milestone

---

## Case 3 — SolarHarvest Cooperative

| Field | Value |
|---|---|
| Founder | Blessings Mtonga |
| Sector / Geo / Stage | CleanEnergy / Mozambique / Pre-Seed |
| Outcome | **PASS** |
| Trust Score | **32** (target band 20–40) |
| Overall Score | 28 |
| Integrity | Grade **F** / 34 |
| Confidence | Low (0.45) |

### Signals
- Critical: unverified government mini-grid concession
- Critical: corporate registration gap
- Sparse-mode disclosure active

### Evidence
- ARENE gazette non-match vs deck claim (HIGH contradiction)
- Unsupported subscriber + financial claims
- Thin corpus / major conflicts

### Reports
- Exports still generate (transparency over silence)

### Analytics contribution
- Pass bucket; lowers coverage averages intentionally (honest sparse case)

### Decision Snapshot
- Verdict: PASS
- Reliability: F / 34
- Next action: Decline and archive

---

## Pilot exploration pack (offline browsing)

Additional seeded cases for pilots (not OSTX extremes):

| Startup | Outcome | Purpose |
|---|---|---|
| NilePay Logistics | OBSERVE | FinTech corridor mid-case |
| FarmStack Kenya | CO-INVEST | Healthy follow/co-invest contrast |
| HealthBridge Lagos | PASS | Thin-evidence PASS without regulatory drama |

---

## What each surface shows

1. **Runs** — all six demo cases visible to signed-in pilots (shared `user_id=NULL` rows)
2. **Evidence** — integrity grade, contradictions, sources, checklist
3. **Signals** — generated from stored brief (no live LLM required for summary panel)
4. **Reports** — download PDF/TXT from stored brief
5. **Analytics** — cohort KPIs from persisted runs only
6. **Flex Decision Snapshot** — verdict / confidence / reliability / risks / next action
