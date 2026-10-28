# Outcome Capture Strategy

**Objective:** maximise the number of real decisions that reach a *rated outcome with a
written lesson*, using only surfaces that exist today. Nothing in this document asks for
new code.

The constraint that shapes everything: **reminders are in-product only.** There is no
email or SMS ping. If nobody opens the workspace, nothing gets captured. Therefore
collection is a human operation run by the mentor, not a platform function.

## The capture ladder

Each rung is a strictly harder commitment than the one above. Measure, report and chase
**by rung**, never mixing denominators.

| Rung | Definition (as the product computes it) | Where you see it |
|---|---|---|
| R0 **Assessment run** | a run exists with a decision | `/assessments`, `/outcomes` registry |
| R1 **Decision taken** | `decision_taken = yes` at follow-up | follow-up record |
| R2 **Answered** | `followup_status = answered` (any answer, including "no decision yet") | **Pilot Health** capture rate = answered ÷ total decisions |
| R3 **Followed** | `recommendation_followed ∈ {fully, partially}` ÷ decidable `{fully, partially, no}` — `not_yet` and `unknown` are excluded from the denominator, never counted as failures | Pilot Health followed rate (+ sample size) |
| R4 **Rated outcome** | `outcome_status ∈ {Successful, Partially Successful, Unsuccessful}` | registry row chip; feeds calibration only |
| R5 **Learning written** | at least one of the five lesson fields non-empty; ideally `what_happened` | admin `/admin/outcomes` counts `with_what_happened` / `with_lessons` |
| R6 **Closed loop on paper** | Outcome Review PDF exported + case study drafted | pilot binder |

**R2 without R4 is the failure mode of this pilot.** An answered follow-up with
`Pending` outcome is a half-collected outcome: it proves engagement, not results.

## Where the capture surfaces already live

- **Workspace header chip** — `⏳ Follow-Up Due` / `Followed up ✓`, present on every
  workspace screen without extra clicking.
- **Dashboard** — *Pending Follow-Ups* list with the due date and "30-day check-in".
- **`/outcomes`** — *30-Day Follow-ups Waiting* queue; deep link
  `/outcomes?focus=<run_id>` opens and scrolls straight to that decision's row.
- **`/runs` (assessment history)** — *Follow-up waiting* marker per run.
- **Assessment cards** — follow-up chip per assessment.
- **AI Analyst (`/flex`)** — reminder strip plus the outcome questions
  (*"What happened after this recommendation?"*, *"What changed?"*) answered from the
  stored record.
- **Report exports** — once answered, every report carries the Outcome Snapshot; once
  rated, the **Outcome Review Report** (PDF/TXT) exists.

Because the surfaces are already there, the only lever is **when a human is standing in
front of them**. Design the calendar around meetings, not around the product.

## The four trigger moments (schedule these at kick-off)

1. **The decision meeting itself (day 0–10).** The decision is written into the comment
   field *in the meeting*, before the follow-up window opens. When the decision owner is
   already named in the record, the day-30 question is a confirmation rather than an
   investigation — which is why this habit is worth insisting on.
2. **The day-30 mentor call (15 minutes, screen shared).** The mentor never clicks for
   the user; they talk them through one tap, then the four-field update. One-tap takes
   under ten seconds; the full update under a minute. If it took longer, that is an
   `FR-1` finding.
3. **The monthly operations meeting.** Put "open follow-ups" on the standing agenda.
   Every overdue item is answered *in the room* or given a named owner and a date.
4. **The reporting moment.** When a donor or board paper is being written, the person
   drafting it is walked to `/outcomes` — the Outcome Review PDF is the fastest route to
   a defensible sentence, so capture is pulled by need instead of pushed by nagging.

## Roles

- **Named recorder** (one person per organisation, agreed in writing on day 0). Absence
  of a named recorder is the single largest cause of missing outcomes.
- **Decision owner** answers "was a decision taken / followed" — only they know.
- **Mentor** owns the calendar, the timing log and the escalation; never the answers.
- **Pilot operator** reads the adoption numbers weekly (see
  [USER_ADOPTION_DASHBOARD.md](USER_ADOPTION_DASHBOARD.md)) and runs the escalation ladder.

## Escalation ladder (human, no product change)

| Days past due | Action | Owner |
|---|---|---|
| 0–3 | Deep link sent in the existing channel (WhatsApp/email) with `?focus=` URL | Mentor |
| 4–7 | 10-minute call; answer together on screen | Mentor |
| 8–14 | Escalate to the decision owner, not the recorder | Pilot operator |
| 15–28 | Put it on the organisation's own management-meeting agenda | Pilot lead |
| 28+ | Record it as a structural finding: *who could not be reached and why* — that is pilot data, not failure | Pilot lead |

## Quality bar — what counts as captured

- **Usable answer:** both follow-up questions answered with real values. `unknown` is
  permitted but must be rare and explained in the interview, never used to close a form.
- **Usable rating:** outcome status is one of the three rated values, and the person can
  say in one sentence *why*.
- **Usable lesson:** `what_happened` is at least one concrete sentence in the user's own
  words (a number, a name, a decision, a reversal). Polished summaries are weaker data.
- **Never accepted:** a rating recorded by the mentor on the user's behalf; an outcome
  inferred from a report download; a lesson copied from the platform's own recommendation.

## Targets

| Cohort | R2 answered by D30 | R4 rated by D90 | R5 with lessons |
|---|---|---|---|
| NGOs | ≥ 60 % (programme gate) | ≥ 50 % (programme gate) | ≥ 80 % of rated |
| Development programmes | ≥ 60 % (programme gate) | ≥ 50 % (programme gate) | ≥ 80 % of rated |
| Tourism SMEs | ≥ 70 % (proposed stretch) | ≥ 65 % (proposed stretch) | ≥ 80 % of rated |

Tourism is set higher on purpose: their outcomes resolve inside a season, so they are
the cohort that can produce the first *rated* calibration data. If tourism rates below
NGOs, the problem is our process, not their willingness.

## Honesty rules (non-negotiable)

1. Never present an answered follow-up as an outcome.
2. Never compute or quote a success rate from fewer than ten rated outcomes in a trust
   band — the product says `NOT MEASURED`, and so must every slide.
3. Demo records are excluded from all counts; do not re-add them to reach a target.
4. A missed follow-up is reported as missed. Backfilling with a guess is worse than an
   empty cell, because it silently invalidates the calibration the pilot exists to build.
5. When the outcome is genuinely unknown at day 90, that is recorded as
   `In Progress`/`Pending` and becomes a *finding about decision horizons*, not a gap to
   paper over.

## What this strategy explicitly does not ask for

No email digests, no notification engine, no outcome scoring, no Decision Accuracy
Score, no new fields, no dashboards beyond the two that already exist. If a rung keeps
failing despite the calendar, the finding is **"this rung cannot be captured with the
current product"** — write it that way and hand it to the product backlog as evidence
from the field. That is the most valuable artefact a pilot can produce.
