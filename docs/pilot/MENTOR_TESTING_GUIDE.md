# Kulima FLEX — Mentor Testing Checklist

For the person shepherding 1–3 pilot organisations. Your job is **not** to
sell the product. It is to watch a real decision move through it, time the
steps, and record exactly where it fails or lies.

You are also the pilot's **collection engine**: reminders are in-product only, so
nothing gets captured unless you put a human in front of the screen at the right
moment (see [OUTCOME_CAPTURE_STRATEGY.md](OUTCOME_CAPTURE_STRATEGY.md)).

## Profile Reference Card — what "correct" looks like

Never judge one profile by another profile's output. This is the whole matrix:

| Profile | Verdict bands | Signal domains, in order | Their main review |
|---|---|---|---|
| **NGO** | Strong Capacity · Moderate Capacity · Needs Strengthening | Institutional Capacity · Programme Performance · Community Reach · Funding Sustainability · Partnership Strength · Monitoring Quality | Institutional Capacity Review |
| **Development Programme** | Ready · Requires Support · At Risk | Programme Performance · Institutional Capacity · Community Reach · Funding Sustainability · Partnership Strength · Monitoring Quality | Programme Performance Review |
| **Government Programme** | Effective · Monitor · Intervene | Governance · Policy Alignment · Delivery Capacity · Public Value | Governance Review |
| **Tourism SME** | Ready for Growth · Build Resilience · High Risk | Tourism Signals · Climate Signals · Community Signals · Destination Readiness · Visitor Economy Signals | Tourism Resilience Report |
| **Startup** | Invest · Observe · Pass | Founder Risk · Market Readiness · Revenue Potential · Investment Readiness | Investment Committee Report |

Any startup/VC vocabulary (founder, cap table, traction, exit, term sheet, seed
round) appearing in an NGO, programme or government output is `INC-3`, same-day.
The NGO prompt explicitly forbids that language, so when it appears it is a real
defect, not a style choice.

## Ground Rules

- The organisation makes **one real decision** per cycle (funding, partner,
  procurement, scale-up) — not a rehearsal.
- You take notes; they do the clicking. Never fill a form for them.
- Every problem is logged with the incident tags below. Over-claiming
  (a report asserting something the evidence doesn't support) is the most
  serious class — halt and report the same day.

## Timed Observations (record actual clock times)

| Metric | Start the clock | Stop the clock | Target |
|---|---|---|---|
| Time to first completed assessment | first document dropped on `/` | recommendation visible in `/flex` | < 10 min |
| Time to first report | assessment complete | PDF open on their screen | < 1 min |
| Time to first outcome capture | follow-up reminder seen | "Save & done" / one-tap confirmation | < 30 s |
| Follow-up click-through | reminder seen | clicked to the form | note % |

If a step stalls, write down **where** and **what was on screen** — that is
the adoption finding, more valuable than a happy path.

## Walkthrough Checklist (one line each: ✓ / ✗ / note)

1. `/` upload — entity detected correctly (NGO ≠ startup wording anywhere)
2. `/evidence` — their documents appear attributed as documents, not "open research"
3. `/signals` — every signal names a real source; none feel decorative
4. `/decision` — recommendation is one tier, consistent with what `/flex` showed
5. `/reports` — download the memo/one-pager; open it **with** them; ask
   "does this describe you?" — tag wrong-entity framing as INC-3
6. AI Analyst — ask the four accountability questions; check every answer cites
7. `/feedback` — they file at least one real comment unprompted
8. Follow-up surfaces — chip visible in workspace header; one-tap answer works
9. `/outcomes` — Pilot Health + registry row shows their answer inline
10. `/assessments` — every row states profile, plain-language status, trust (or "not
    scored") and verdict (or "pending"); nothing renders as a blank chip
11. Honesty states — unaudited evidence reads `NOT AUDITED`, unscored runs read
    `not scored`, unmeasured calibration reads `NOT MEASURED`. A zero or a blank where
    one of these belongs is `INC-1` class (it fabricates a reading)
12. `/mentor-guide` — describes **their** profile: five profiles named, verdicts in the
    profile's own bands, no score name the product doesn't show
13. Pilot Health denominators — each rate shows its `n=`; empty period reads `NO DATA`
14. Outcome Review download appears **only** after a rating; before that, no download is
    offered and the row says so
15. Deep link — `/outcomes?focus=<run_id>` opens that exact row (this is your escalation
    tool; test it once per organisation)

## Incident Tags (use all five, invent none)

- `INC-1 over-claim` — report/analyst asserts beyond evidence (SEVERE)
- `INC-2 wrong-fact` — extracted something incorrectly
- `INC-3 wrong-entity` — investment language to an NGO, founder-gap on a lodge…
- `FR-1 friction` — confusing, slow, or unreachable (note the seconds)
- `FR-2 gap` — they needed evidence the pack didn't contain

## The 30/60/90 Loop

Day 30: get them to the one-tap answer (ten seconds — if it takes longer,
that is FR-1). Day 60 and 90: open the same record, press Update, prefix the
comment `D60:` / `D90:`. When the result is known, rate the outcome
(Successful / Partially / Unsuccessful) and export the Outcome Review PDF.
**An outcome with a PDF in the pilot binder is the only outcome that counts.**

## Reporting Cadence

- Weekly: counts per org (assessments completed / reports downloaded /
  follow-ups answered) + new incidents — read them from
  [USER_ADOPTION_DASHBOARD.md](USER_ADOPTION_DASHBOARD.md) (§1 Pilot Health, §2 admin)
- Day 45: midpoint interview (from the Pilot Validation Programme, guide I-2)
- Day 90: outcome reviews closed, guide I-3, hand data to the pilot analyst

## Honesty You Must Model

Expect NO DATA and INSUFFICIENT EVIDENCE on calibration views early. Explain
them as designed behaviour. Never present a synthetic or another organisation's
result as this pilot's evidence.

## Your Collection Duty (the rungs you own)

You never answer on their behalf. You make sure a human answers, and that the
answer goes all the way to a rated outcome.

| Rung | Who answers | Your move |
|---|---|---|
| R2 follow-up answered | decision owner | day-30 call, screen shared, one tap then the four fields |
| R4 outcome rated | recorder | closure review — you are in the room, they are clicking |
| R5 lessons written | recorder | ask the five questions in order: happened · predicted · missed · worked · failed |
| R6 loop on paper | you | export the Outcome Review PDF into the pilot binder; trigger the case study |

An organisation with answers but no ratings has **not** succeeded. Report it that way.

## Session Scorecard (fill one row per session, 0/1/2 per item)

`0` failed or misleading · `1` worked with friction · `2` worked clean and fast

| Item | Score | Note (seconds / screen / quote) |
|---|---|---|
| Profile detected correctly | | |
| Evidence attributed to their documents | | |
| Signals cite a real source and explain why it matters | | |
| Verdict in the profile's own bands | | |
| Reason · evidence · confidence · next action all present | | |
| Contradictions / missing evidence surfaced usefully | | |
| Analyst answers cite, or admit it cannot | | |
| Report downloaded and readable by an outsider | | |
| Follow-up answered in < 30 s | | |
| Outcome rated + at least one concrete lesson | | |
| Honesty states shown (no blanks, no invented zeros) | | |
| They returned unprompted / used it again | | |

Twice-out-of-three on any row is a systemic finding for the weekly operator review, not a
one-off note. **Total the row:** ≥ 20 = adoption-ready · 14–19 = needs a targeted session ·
< 14 = the decision was never really in the platform — find out why before the next cycle.

## Session Log Template

```
Org / profile / decision under test .................
Session type (R1 readiness | R2 D30 | R3 D60 | R4 closure) ...
People present + who the named recorder is ..........
Timings: upload→verdict ... report ... capture ... closure ...
Scorecard total ...........  Incidents (INC-1/2/3, FR-1/2) ...
What they said in their own words (quote verbatim) ..
What the platform got wrong or could not see ........
Rungs reached (R2 / R4 / R5 / R6) ...................
Next action + owner + date ..........................
```

