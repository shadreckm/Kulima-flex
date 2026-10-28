# Decision Review Framework

The standing meeting that turns a Kulima FLEX assessment into a **Decision → Outcome →
Learning** record. It is deliberately short. It uses screens that already exist, and it
always ends with something written into the platform — a review that produces no record
did not happen.

## Cadence

| Review | When | Duration | Who must be there | What it produces |
|---|---|---|---|---|
| **R1 Readiness** | within 3 days of the assessment completing | 30 min | Decision owner, MEAL/M&E lead, recorder | A verdict you can defend + the decision written into the comment field |
| **R2 Check-in** | Day 30 (the follow-up window) | 15 min | Decision owner + recorder | Follow-up answered: decision taken? recommendation followed? |
| **R3 Drift review** | Day 60 | 15 min | Decision owner | `Update` on the same record, comment prefixed `D60:` |
| **R4 Closure** | Day 75–90, or when the result is known | 30 min | Owner + MEAL + one person who wasn't in R1 | Rated outcome, five lesson fields, **Outcome Review PDF** |

R1 and R4 are the two that matter: R1 makes the decision honest, R4 makes it learnable.

## R1 — Readiness review agenda (30 minutes, in this order)

1. **Open `/decision` on one screen.** Read aloud: the verdict band, the reason, the
   evidence, the confidence, the next action. Nobody speaks until this is read.
2. **Check the evidence base (`/evidence`).** Trust score, evidence grade, and — most
   importantly — *contradictions and unsupported claims*. Ask: *do we agree that these
   are the real gaps, or is the platform missing something we know?*
3. **Check the signals (`/signals`) in profile order.** NGO: Institutional Capacity →
   Programme Performance → Community Reach → Funding Sustainability → Partnership
   Strength → Monitoring Quality. Development programme: same set starting with
   Programme Performance. Tourism: Tourism · Climate · Community · Destination
   Readiness · Visitor Economy. For each: *why does this matter, and what decision
   would change if it did?*
4. **Interrogate the Analyst (`/flex`).** Three questions, in this order:
   *"What evidence is weak?"*, *"What would change this verdict?"*,
   *"What are you most likely wrong about?"* The platform's own
   "what would trigger a lower verdict" statement is on the dossier — test it.
5. **Decide.** Record the decision in the comment field **now**, naming the owner and
   the date. Write the dissent if there is any; dissent is the most under-collected
   outcome data in institutions.
6. **Set the outcome condition.** One sentence: *what will we know by day 90 that tells
   us this worked?* That sentence becomes `what_was_predicted` at R4.

**Verdict bands are written in your language — do not translate them into investment
language in the minutes.** NGO: Strong Capacity / Moderate Capacity / Needs
Strengthening. Development programme: Ready / Requires Support / At Risk. Government:
Effective / Monitor / Intervene. Tourism: Ready for Growth / Build Resilience / High
Risk. Startup: Invest / Observe / Pass.

## R2 / R3 — Check-in and drift

Open the follow-up from the workspace header chip, the dashboard *Pending Follow-Ups*
list, or `/outcomes?focus=<run_id>` (deep link lands on the exact row).

Answer with what is true, not what is flattering:

- **Was a decision taken?** `yes / in_progress / no / unknown`.
- **Was the recommendation followed?** `fully / partially / no / not_yet / unknown`.

`partially followed` is the single most informative answer in the whole system: it means
the platform said something and institutional reality bent it. `not_yet` is honest and is
never counted as failure. `unknown` at day 30 is itself a finding — write why.

At R3, press **Update** on the same record and prefix the comment `D60:`. Never create a
second record for the same decision.

## R4 — Closure review (this is where outcomes are born)

Open the decision row in `/outcomes` and work down the row:

1. **Set the outcome status**: `Successful` / `Partially Successful` / `Unsuccessful`.
   Anything still genuinely open stays `In Progress` — that is not a failure to capture,
   it is a correct record of a decision that has not resolved yet.
2. **Fill the five lesson fields** in the decision-maker's own words:
   - **What Happened** — one concrete sentence with a number, name or date.
   - **What Was Predicted** — paste the sentence you wrote at R1 step 6.
   - **What Was Missed** — what the evidence could not see.
   - **What Worked** — what you would do again.
   - **What Failed** — what you would not.
3. **Save Outcome & Lessons**, then export the **Outcome Review Report** PDF. This is the
   artefact that goes to the board, the donor or the bank.
4. **Re-test the band.** Ask: knowing the outcome, was the original verdict band right,
   too cautious, or too confident? Record that judgement in the comment. This is the
   only way trust calibration gets meaning — the platform computes the rates; only you
   can say whether the verdict deserved the outcome.
5. **Trigger the case study** if the loop is closed
   ([CASE_STUDY_TEMPLATE.md](CASE_STUDY_TEMPLATE.md)).

## Decision hygiene rules

- **One decision, one record.** Never assess the same decision twice to get a nicer
  verdict; the registry will show both and the pilot loses its thread.
- **No retrospective confidence.** Whatever the outcome, do not rewrite the original
  reasoning. Append with `D60:` / `D90:` instead.
- **Evidence beats memory.** If two people remember the decision differently, the record
  wins. That is why the comment is written *in the room*.
- **The person who disagrees signs off too.** A closure review with unrecorded dissent is
  an incomplete record.
- **Re-run when the evidence changes, not when the answer changes.** A new document is a
  reason to re-run; a disappointing verdict is not.

## What "good" looks like at the end of a cycle

| Signal | Evidence in the product |
|---|---|
| Decision was made | `decision_taken = yes` |
| Platform influenced it | `recommendation_followed` is `fully` / `partially`, with a comment naming the memo or a signal |
| Outcome known | rated `outcome_status` |
| Learning exists | all five lesson fields, and the "re-test the band" sentence |
| Institution can defend it | Outcome Review PDF circulated to the board/donor |
| Speed held | mentor's timed log; R1 under 30 minutes, R2 under 15 |

If any row is empty, name it in the weekly operator review as a structural finding
rather than leaving it blank — see
[USER_ADOPTION_DASHBOARD.md](USER_ADOPTION_DASHBOARD.md).
