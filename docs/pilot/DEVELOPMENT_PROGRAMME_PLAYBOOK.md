# Kulima FLEX — Development Programme Pilot Playbook

For the team running a funded programme — multi-site, logframe-driven, reporting to a
donor on a fixed rhythm. Your decisions are about **delivery and adaptation**, not about
whether your organisation is investable. The platform reads your programme documents and
answers in your own framework:

- Verdict bands: **Ready · Requires Support · At Risk** (score ≥ 72 / ≥ 55 / below).
- Signal domains, in the order your reviews ask them: **Programme Performance ·
  Institutional Capacity · Community Reach · Funding Sustainability ·
  Partnership Strength · Monitoring Quality**.
- Your main export: the **Programme Performance Review** (plus Decision Memo,
  Signals report, Due Diligence Summary, Executive One-Pager in PDF or TXT).

One real programme decision per cycle. A rehearsal produces a record with no outcome.

## What to Upload

Pick the decision you face in the next quarter and bring the documents that decision
actually rests on:

- Mid-term, end-of-phase or annual **programme review** / evaluation
- **Logframe or theory-of-change export** with indicator definitions
- **M&E / MEAL quality report**: indicator verification, data-quality audit
- Site or county performance tables (indicator tables are accepted as documents)
- Partner and sub-grantee reporting; consortium/MoU documentation
- Budget-versus-expenditure and pipeline/burn-rate reporting

Add a **second independent source for your most load-bearing claim** (e.g. reach
figures in the review *and* in the indicator table). One source supports a signal;
two corroborate it — that is what raises a document from *Corroborated* toward
*Verified* and lifts the trust score.

## Decisions to Run Through the Platform

1. **Continuation or redesign at phase end** — does the review surface what the
   donor's appraisal panel will probe?
2. **Reallocation between sites/counties** — is delivery evidence strong enough to
   justify moving resources?
3. **Scale-up vs consolidation** — capacity, partnership and monitoring evidence
   together, not activity counts alone.
4. **Partner continuation or replacement** — implementing-partner delivery evidence.
5. **Adaptation decision** — a programme change triggered by monitoring findings:
   *did the change work?* This is the highest-value case for outcome capture.

## What to Verify (mark ✓ / ✗ / note; tag with the mentor's incident codes)

- **Language.** Nowhere should this read like a startup or IC review: no "founder",
  no "cap table", no "traction", no "exit". ✗ → `INC-3 wrong-entity`.
- **Programme Performance signals** cite delivered targets, milestones, outputs and
  outcomes **from your documents**, with the document named as the source — not
  labelled as open research. `INC-2 wrong-fact` if a figure is attributed wrongly.
- **Monitoring Quality** reflects your real MEAL system: indicator definitions,
  verification status, baselines. If your own M&E lead says "our data is stronger than
  this picture", that is a finding worth logging — rate the match 1–5 against your
  system of record.
- **Community Reach** shows beneficiary numbers and geography as evidence items, with
  gaps where a document does not prove them.
- **Funding Sustainability** surfaces burn rate, pipeline and donor concentration as
  risks. If the finance lead says "we already knew that", check whether the platform
  quantified it the same way you do.
- **Contradictions and unsupported claims** (`/evidence`) catch the thing every
  programme team knows but never writes down — the reach figure in the newsletter that
  the indicator table does not support. A contradiction caught here is a *win*, not a
  complaint.
- **AI Analyst** — ask *"What evidence is weak?"* and *"What would move this from
  Requires Support to Ready?"* It must name the missing evidence, not reassure you.

## Targets, Logframes and the MEAL Tab

The MEAL dashboard in `/outcomes` counts what is recorded. It deliberately shows
**target: not set** — delivery targets belong to *your* logframe, not to Kulima. Enter
your own targets in the normal place; use the platform for the decision trail:
which decision was taken, was it followed, what happened, what did we learn.

## Your 90-Day Calendar

| When | Who | Act | Proof |
|---|---|---|---|
| Day 0–3 | M&E lead | Upload review + logframe + indicator tables + partner reports; confirm profile is **Development Programme** | `/evidence` per-document trust lines |
| Day 3–5 | Programme Manager | `/decision`: read reason · evidence · confidence · next action; ask the Analyst the two hard questions above | Decision Memo circulated |
| Day 5–10 | Programme Manager / ISD | **Take the real decision** at the scheduled management or review meeting; write it into the comment field | Meeting minute referencing the memo |
| Day 30 | Named recorder | Answer follow-up: decision taken? followed? (`fully / partially / no / not_yet / unknown`) | `✓ Follow-up recorded` |
| Day 45 | Mentor | Midpoint interview; check **Pilot Health** capture rate | Incident list updated |
| Day 60 | Recorder | **Update** same record, comment prefixed `D60:` | Comment trail |
| Day 75–90 | Recorder | Rate outcome (Successful / Partially Successful / Unsuccessful) + five lesson fields → **Save Outcome & Lessons**; export **Outcome Review Report** | PDF + donor-facing Programme Performance Review |
| Day 90 | Analyst | Case study from the closed loop only | Draft approved by the programme |

## What This Playbook Is Testing

- **H2 recommendation quality** — did the verdict match what the review committee
  concluded independently?
- **H4 confidence change** — did the team's confidence in the decision go up, and by
  how much? Record it honestly in the comment as `CONF(pre)=x CONF(post)=y` on the 1–5
  scale the mentor asks verbally; there is no confidence field, and we will not invent one.
- **H1 followed rate** — programme decisions often get *partially* followed after
  donor negotiation. "Partially" is a correct, valuable answer; it is counted as
  followed. "Too early to tell" is never counted as not followed.
- **Learning loop** — a programme that records *"we reallocated, coverage rose in two
  counties, we missed the retention drop"* is the evidence that institutional
  decision-making here is closed-loop. That sentence — not a dashboard — is the
  deliverable.

## Judge Honesty, Not Flattery

A thin document set producing a modest trust score and a visible evidence gap is a
**correct result**. `INSUFFICIENT EVIDENCE` where you hoped for a success rate is a
**pass**. Your most valuable finding is any sentence in any export that claims more
than your programme documents support — log it as `INC-1` the same day.
