# User Adoption Dashboard (design-only)

**This document adds no screens.** Every metric below is already computed and displayed
today, on two surfaces. What is specified here is *how to read them as one adoption
system*, what each denominator actually contains, and the weekly routine around them.

| Audience | Surface | Purpose |
|---|---|---|
| Pilot organisation | `/outcomes` → **Pilot Health** (top of the decision registry tab) | "are we closing our own loops?" |
| Pilot operator / lead | `/admin/outcomes` (platform-wide) + `/admin` overview | "which organisation is going quiet, and where?" |

---

## 1. Customer view — Pilot Health (`/outcomes`)

Computed only from the organisation's own decision-registry rows. No inferred data. Empty
measures render `NO DATA`, never a zero.

| Tile label as shown | Exact definition (as implemented) | Read it as |
|---|---|---|
| **… decisions tracked** (header) | count of decision records (demo records excluded) | the size of the sample every other number rests on |
| **Outcome capture rate** | `followup_status = answered` ÷ total decisions | engagement. Below 60 % at day 30 → run the escalation ladder. ⚠ Despite the label, the sub-line is *decisions answered the follow-up* — this is **answer** capture, **not** rated outcomes. Never quote it as an outcome rate. |
| **Decision followed rate** (`n=`) | `fully`+`partially` ÷ decidable (`fully`,`partially`,`no`) — `not_yet` and `unknown` excluded from the denominator | influence on real behaviour. Always quote with its sample size |
| **Outcomes rated** (`rated / total`) | rows with `outcome_status ∈ {Successful, Partially Successful, Unsuccessful}` | the only rows that can produce calibration or a Tier-A story |
| **Days to follow-up** (`n=`) | mean of `answered_at − (decision_snapshot_at ∥ followup_due_at ∥ created_at)` | how long the loop actually takes; target ≈ 30 |
| **Decision velocity** (`n=`) | median `answered_at − created_at` for rows where `decision_taken = yes` | H3 speed evidence, robust to one outlier |

**The gap that matters:** capture rate high, rated outcomes low → the organisation answers
prompts but nobody owns the closure review. Fix with #6 R4, not with more reminders.

## 2. Operator view — `/admin/outcomes` (platform-wide)

All platform-wide, window-selectable (default 30 days). Same definitions as the customer
view, so the two audiences never argue about what a number means.

| Block | Contents |
|---|---|
| **Follow-up completion** | total · answered · pending · **due now** · answered in window |
| **Answer distribution** | counts by `decision_taken` and by `recommendation_followed` — watch the `unknown`/`not_yet` share |
| **Answer lag** | average and median days from decision snapshot to answer |
| **Pending queue, per organisation** | every unanswered follow-up with a signed offset: `overdue N days` vs `due in N days` — this is the call list |
| **Outcome status distribution** | counts by `Pending / In Progress / Completed / Successful / Partially Successful / Unsuccessful` |
| **Lesson richness** | outcomes with a non-empty **What Happened**, and outcomes with any lesson field filled |
| **Feedback** | ratings count, average, share ≥ 4 |
| **Decision learning** | total decisions, completed outcomes, recommendation accuracy, high-trust success rate — plus the **trust-band calibration table** (High 80–100 · Moderate 60–79 · Low 0–59) |
| **Reportability guard** | a band is `reportable` only with ≥ 10 completed outcomes; below that it reads `observation only` |

**Never quote from `/admin` anything you have not checked for the `activityDefinition`
hint** — "active users" is audit-derived, not a login counter, and the platform says so on
the tile. Use the stated definition or don't use the number.

## 3. Supporting signals (not adoption, but explain adoption)

`/analytics` portfolio metrics: **Evidence coverage** = sources ÷ claims (how traceable
their assertions are); **Signal coverage** = completed core narrative sections ÷ 5;
average scores **count unscored runs as zero**, so a partly finished portfolio reads
low. Use these to explain *why* a team's trust scores are modest — not to rank them.

## 4. The weekly operator routine (20 minutes, same time each week)

1. `/admin/outcomes`, window = 30 days. Write down: answered ÷ total, due now, rated
   count, rows with `what_happened`.
2. Sort the pending queue by `overdue` descending. Every organisation with an overdue
   item gets the ladder step matching its age (#5).
3. For each organisation, compare **capture rate** vs **rated outcomes**:
   - high / low → closure review not happening (schedule R4)
   - low / low → nobody is opening the workspace (mentor session, not a product issue)
   - high / high → candidate for a Tier-A story (#8)
4. Record one line per organisation in the sheet below. Never leave a cell blank-blank:
   `not reached`, `no recorder`, `no decision taken`, `outcome unknown` are all valid.
5. Flag any incident where a number on a screen disagreed with the underlying record —
   that is an `INC-1` class bug and outranks every adoption target.

## 5. Offline weekly sheet (the only "dashboard" that needs building — a spreadsheet)

| Org | Profile | Decisions | Answered | Capture % | Rated | Rated % | With lessons | Oldest overdue (days) | Ladder step taken | Story candidate | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|

Rules for the sheet:
- Fill every cell from the two surfaces above. No estimates, no "probably ~70 %".
- Percentages always with their denominator (`3/5 = 60 %`), never bare.
- A blank cell is a finding: write why it is blank.
- Demo or synthetic rows never enter this sheet.

## 6. Interpretation guard rails

1. **Small-N honesty.** With five decisions, one answer moves capture rate 20 points.
   Quote counts alongside rates, always.
2. **No cross-band claims.** A single High-Trust band with fewer than ten rated outcomes
   cannot support "high trust produces better outcomes" — the product prints
   `NOT MEASURED` for exactly this reason, and the pilot report must inherit that restraint.
3. **Rates are not quality.** A 100 % capture rate of `unknown` answers is a broken
   process, not a success. Read the distribution blocks before the rates.
4. **Adoption is a means.** The goal is not a green dashboard; it is rated outcomes with
   lessons. A messy dashboard with four closed loops beats a tidy one with none.
