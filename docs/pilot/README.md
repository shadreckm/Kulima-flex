# Kulima FLEX — PILOT_SUCCESS_SYSTEM

The operating system for the pilot. Nothing here is a feature request and nothing
here needs new code: every instrument in this folder runs on surfaces that exist
today. The single job of this system is to convert real decisions into
**Decision → Outcome → Learning** as completely as possible.

```
Decision taken   →   recorded in the 30-day follow-up        (decision_taken)
Outcome known    →   recorded in the decision registry       (outcome_status)
Learning made    →   recorded in the lesson fields + Outcome Review PDF
```

## The instruments

| # | Document | Who uses it | When |
|---|---|---|---|
| 1 | [PILOT_USER_GUIDE.md](PILOT_USER_GUIDE.md) | Every pilot user | Day 0, then weekly |
| 2 | [NGO_TESTING_GUIDE.md](NGO_TESTING_GUIDE.md) — NGO Pilot Playbook | NGO programme lead + MEAL | Full 90-day cycle |
| 3 | [DEVELOPMENT_PROGRAMME_PLAYBOOK.md](DEVELOPMENT_PROGRAMME_PLAYBOOK.md) | Programme manager + M&E team | Full 90-day cycle |
| 4 | [TOURISM_TESTING_GUIDE.md](TOURISM_TESTING_GUIDE.md) — Tourism SME Pilot Playbook | Owner / GM | Fast cycle, one season |
| 5 | [OUTCOME_CAPTURE_STRATEGY.md](OUTCOME_CAPTURE_STRATEGY.md) | Pilot operator + mentors | Continuous |
| 6 | [DECISION_REVIEW_FRAMEWORK.md](DECISION_REVIEW_FRAMEWORK.md) | Executive Director / committee | Day 30, 60, 90 |
| 7 | [CASE_STUDY_TEMPLATE.md](CASE_STUDY_TEMPLATE.md) | Pilot analyst | After each closed loop |
| 8 | [SUCCESS_STORY_FRAMEWORK.md](SUCCESS_STORY_FRAMEWORK.md) | Pilot lead + comms | From verified records only |
| 9 | [USER_ADOPTION_DASHBOARD.md](USER_ADOPTION_DASHBOARD.md) | Pilot operator | Weekly review |
| 10 | [MENTOR_TESTING_GUIDE.md](MENTOR_TESTING_GUIDE.md) — Mentor Testing Checklist | Mentor per organisation | Every session |

## The one data model you need to know

There are **two separate records** per decision, and people confuse them constantly:

**Follow-up answer** (the 30-day check-in) — `decision_taken`,
`recommendation_followed`, free-text comment.
Values are fixed: taken = `yes / in_progress / no / unknown`;
followed = `fully / partially / no / not_yet / unknown`.
*"Answered" is not the same as "rated".*

**Outcome record** (the decision registry row) — `outcome_status` =
`Pending / In Progress / Completed / Successful / Partially Successful / Unsuccessful`,
plus five lesson fields: **What Happened, What Was Predicted, What Was Missed,
What Worked, What Failed**.
Only `Successful`, `Partially Successful` and `Unsuccessful` count as **rated**,
and only rated outcomes feed trust calibration and unlock the Outcome Review Report.

Capture target for every pilot decision: **answered AND rated AND lessons written.**
An answered follow-up with no rating is a half-collected outcome.

## Hard rules for everyone on this system

1. **Never record a number you did not observe.** The platform already refuses to
   fabricate — `NOT MEASURED`, `NO DATA`, `not scored`, `not audited` are correct
   outputs. A pilot report that fills those gaps by hand destroys the thing being tested.
2. **Calibration needs ten rated outcomes in a trust band** before its rate means
   anything. Below that, say "observation only". This is enforced in the product; do not
   override it in a slide.
3. **Reminders are in-product only.** There is no email or SMS ping. If a user does not
   open the workspace, the follow-up does not happen — which is why the mentor, not the
   platform, owns collection (see #5).
4. **One real decision per cycle**, not a rehearsal. A rehearsal produces a record with
   no outcome to learn from.
5. **Demo records are excluded** from the outcomes registry and from every adoption
   figure. Never reintroduce them into a report.
6. **Nothing in this folder justifies a new feature.** If a gap can only be closed by
   building, it is a pilot finding, not a ticket.

## Pilot-level success gates (the programme's own numbers)

- **≥ 60 %** of decisions answered by the Day-30 follow-up.
- **≥ 50 %** of decisions carrying a *rated* outcome by Day-90.
- Every closed loop produces one case study (#7); a case study with no Outcome Review
  PDF is not closed.
- The five hypotheses (H1 followed-rate +20pp, H2 recommendation quality, H3 decision
  speed — ≤ 14 days for Tourism, H4 decision-maker confidence change, H5 trust from
  honesty ratings) are measured from these records and the mentor's timed observations,
  never from a demo run.
