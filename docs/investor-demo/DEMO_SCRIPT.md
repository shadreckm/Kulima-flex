# OSTX 5-Minute Demo Script

Goal: prove Kulima OS can run an end-to-end IC workflow offline, differentiate three deals, and export decision artifacts.

**Prep (60 seconds before stage):**
1. Sign in to Kulima OS
2. Confirm Runs page shows AgriNova, GreenLink, SolarHarvest
3. Keep this tab ready: `/runs`
4. Optional backup URLs:
   - `/flex?run=ostx-agrinova-malawi`
   - `/evidence?run=<AgriNova id>`
   - `/reports?run=<AgriNova id>`

---

## Minute 0:00–0:30 — Open with the problem

**Say:**
> “African dealflow fails in diligence, not in ambition. Kulima OS is an investor operating system that turns sparse public evidence into an IC-ready decision: Invest, Observe, or Pass — with trust and evidence integrity attached.”

**Click:** Dashboard

**Show:** Pilot metrics strip (Invest / Observe / Pass counts, Evidence Coverage, Signal Coverage)

---

## Minute 0:30–1:30 — Flagship INVEST case (AgriNova)

**Click:** Runs → select **AgriNova Malawi**  
**Or open:** `/flex?run=ostx-agrinova-malawi`

**Say:**
> “This is AgriNova Malawi. Strong market, strong founder, strong evidence. Trust Score 88. Recommendation: INVEST.”

**Show:**
1. Decision Snapshot (verdict, confidence, reliability A)
2. Top reasons / next action ($350K Seed)

**Click:** Evidence workspace for AgriNova

**Say:**
> “Integrity Grade A. No contradictions. Multiple institutional sources. This is what conviction looks like.”

---

## Minute 1:30–2:40 — OBSERVE contrast (GreenLink)

**Click:** Runs → **GreenLink Foods**  
**Or:** `/signals?run=ostx-greenlink-foods`

**Say:**
> “Same product, different evidence reality. GreenLink is operating — but Trust is 64 and the system says OBSERVE.”

**Show:**
1. Signals / red flags: power vulnerability, concentration
2. Evidence contradiction: 30 claimed retail partners vs 12 verified

**Say:**
> “Kulima does not force a false Invest. It creates a milestone watchlist — solar hybrid and contract verification — before capital moves.”

---

## Minute 2:40–3:40 — PASS with receipts (SolarHarvest)

**Click:** Runs → **SolarHarvest Cooperative**  
**Or:** `/evidence` with SolarHarvest selected

**Say:**
> “Third case: SolarHarvest. Trust 32. PASS.”

**Show:**
1. Integrity Grade F / sparse mode
2. ARENE concession contradiction
3. Critical red flags

**Say:**
> “This is the competitive advantage. Most tools summarize decks. Kulima refuses to launder weak evidence into a green score.”

---

## Minute 3:40–4:30 — Reports + Analytics close

**Click:** Reports → AgriNova → Download **Memo PDF** (and optionally Signals PDF)

**Say:**
> “Every completed run already has IC exports: memo, full report, signals, diligence summary, one-pager — generated from stored intelligence, not a slide template.”

**Click:** Analytics

**Say:**
> “Pilot analytics are derived from stored runs only. Coverage metrics are honest — thin cases pull coverage down, which is exactly what investors should see.”

---

## Minute 4:30–5:00 — Ask + close

**Optional if time:** On Flex for AgriNova, ask:
> “Why is this Invest instead of Observe?”

(If offline LLM is unavailable, answer from Decision Snapshot / Narrative — do not stall.)

**Close:**
> “Kulima OS is ready for OSTX judges and pilot users today: offline demo mode, URL-synced runs, validation cases loaded, and an evidence-first decision workflow. We are not asking you to believe a score — we are showing you the evidence path behind it.”

---

## Demo do’s / don’ts

**Do**
- Lead with AgriNova, then contrast GreenLink, then SolarHarvest
- Click Evidence at least once
- Download one PDF live

**Don’t**
- Start a fresh live analysis unless API keys are confirmed
- Apologize for OBSERVE/PASS — they are the product
- Spend time in Settings or incomplete WIP screens

---

## Emergency fallback (if UI auth hiccups)

1. Streamlit surface (`app.py`) with seeded `founders.db`
2. Narrate from `docs/investor-demo/NARRATIVE.md`
3. Show pre-downloaded AgriNova memo PDF from Reports if already cached
