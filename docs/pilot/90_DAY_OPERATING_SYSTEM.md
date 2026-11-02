# Kulima FLEX — 90-Day Pilot Operating System

**Cohort:** 5 NGOs · 3 Development Programmes · 3 Tourism SMEs (11 organisations)  
**Duration:** Day 0 through Day 90  
**Operating principle:** one real decision per organisation; one traceable chain from
evidence to a human decision, a recorded outcome, and learning.

This is the cohort operator's runbook. The detailed product steps and cohort-specific
tests remain in the [Pilot User Guide](PILOT_USER_GUIDE.md), [NGO Playbook](NGO_TESTING_GUIDE.md),
[Development Programme Playbook](DEVELOPMENT_PROGRAMME_PLAYBOOK.md), and
[Tourism SME Guide](TOURISM_TESTING_GUIDE.md). Use the existing platform; record human
operations, payment evidence, incidents, and consent in a restricted pilot operations
register. Do not put credentials, payment-card details, or unnecessary personal data in
that register.

## 1. Cohort operating model

### Roles

| Role | Accountable for |
|---|---|
| Executive sponsor | Approves pilot scope, pricing/comping policy, risk acceptance, and the Day-90 continue/renew decision. |
| Pilot lead | Owns the 11-organisation roster, weekly executive dashboard, escalation, incident triage, and decisions on pause/resume. |
| Two mentors (recommended) | Each owns a named list of 5–6 organisations; facilitates reviews, records timings and incidents, and follows up without answering or entering customer answers on their behalf. |
| Organisation decision owner | Selects and makes the real decision; records dissent and the decision comment. |
| Evidence holder | Supplies the source documents and checks provenance and evidence gaps. |
| Named recorder | Enters the organisation's follow-up answers, outcome, and lessons. Name one primary and one backup at kickoff. |
| Finance / billing owner | Approves the price and contract terms, reconciles each claimed payment against provider-side evidence and the bank statement, and reports verified revenue. |
| Case-study owner | Drafts only from closed loops, obtains written approval for the exact text, and honours anonymity and withdrawal choices. |

Mentors must never take a decision, invent or infer an outcome, enter answers for a
customer, or mark a payment as verified based on a browser redirect or screenshot alone.

### Cohort roster

Create one restricted roster row per organisation before kickoff. Required fields:
organisation ID and profile; mentor and backup; sponsor/contact; decision owner; evidence
holder; recorder and backup; timezone and contact channel; planned decision date; consent
status; commercial status (paid / comped / no charge); price/contract version if
applicable; last contact; health state; next action and owner.

Use the platform's organisation ID as the join key. Do not mix demo, synthetic, or
internal test records into cohort metrics.

## 2. Weekly plan

The weekly review runs at the same time every week: **20 minutes on the operator
dashboard**, followed by organisation-specific mentor actions. The pilot lead sends a
one-page decision log after the review: metric, denominator, issue, owner, due date,
decision, and whether the issue is closed. “No data” is a reportable state, not zero.

| Week / days | Cohort activity | NGO and development programme emphasis | Tourism SME emphasis | Exit evidence |
|---|---|---|---|---|
| **W1 · D0–6** | Confirm 11 organisations, contacts, consent, mentor assignments, pilot terms, and escalation channels. Name decision owner, evidence holder, and recorder plus backup. Complete account access and a short orientation. Select exactly one real decision per organisation. | Select an upcoming grant, partner, programme adaptation, reallocation, or continuation decision. Identify the logframe and system-of-record owner. | Select a live seasonal decision (pricing, staffing, energy, renovation, or partnership); note its real deadline. | Complete roster; signed participation/terms; consent choice; named roles; decision question and expected resolution date; access checked. |
| **W2 · D7–13** | Upload only decision-relevant source material; complete first real assessment. Check that entity profile, evidence attribution, signals, and verdict use the correct institutional language. Log defects the same day. | Upload annual/programme review, M&E/logframe, indicators, partner reports, and budget evidence. Cross-check a load-bearing claim against an independent source. | Upload occupancy/revenue summaries, financing paper, community agreement, and short plan; record evidence limitations rather than filling gaps. | Assessment run ID; document/source list; evidence-holder review; profile and language pass/fail; completion time; incidents with owner and severity. |
| **W3 · D14–20** | Hold R1 decision review within 3 days of completion where feasible. Read evidence, signals, uncertainty, rationale, next action, and challenge the Analyst. Circulate the profile-appropriate report. | Compare delivery, reach, funding, partnership, and monitoring evidence with the organisation's own M&E record. | Confirm tourism, climate, and community signals are sourced; ensure workflow does not slow the business decision. | Decision owner records real decision, dissent, date, and expected outcome in the platform; report delivery confirmed; pre-confidence and task time recorded. |
| **W4 · D21–27** | Check all organisations have made, scheduled, or explicitly deferred the decision. Resolve onboarding/access blockers; do not create a second assessment to obtain a preferred verdict. | Confirm governance/committee date, recorder capacity, and D30 calendar hold. | Check decision against the seasonal deadline; escalate a decision at risk of missing its window. | 11/11 decision states accounted for (made, scheduled, deferred with reason); unresolved items named and dated. |
| **W5 · D28–34** | D30 follow-up window opens for early W1–W2 records. Mentor contacts the owner/recorder through the agreed channel; customer records decision-taken and recommendation-followed. | Review both follow-up answers; partial follow-through and not-yet are valid, distinct values. | Target a phone-friendly one-tap answer; record what happened without forcing an outcome before the season resolves. | Answered/eligible count by organisation and profile; unanswered due list with next contact and owner. |
| **W6 · D35–41** | Run the overdue ladder (0–3 days: link; 4–7: short call; 8–14: decision-owner escalation). Review product friction and classify incidents vs training needs. | Check whether unanswered records reflect recorder ownership, meeting cadence, or genuinely unknown decisions. | Confirm the assessment did not delay a 48-hour decision; log actual elapsed time. | Each overdue item has a dated action and named owner; blocker codes and time-to-resolution recorded. |
| **W7 · D42–48** | Day-45 midpoint interview with each organisation; review customer effort, trust, and intended use. Reconcile platform figures to records. | Check evidence usefulness to the board/donor/MEAL process and any missing baseline. | Check in-season outcomes, bookings/operating evidence, and the validity of speed claims. | Midpoint interview record; customer health status; confidence post-score; source-of-truth discrepancies escalated. |
| **W8 · D49–55** | Resolve training, access, and workflow issues; keep product defects in an incident log. Confirm D60 updates and expected outcome dates. Review payment exceptions independently of adoption. | Schedule recorder with programme/management calendar; confirm monitoring data are accessible. | Identify which decisions can honestly be rated by D60 vs those awaiting season closure. | D60 review invitations; outstanding issues have a disposition; payment ledger reconciliation current. |
| **W9 · D56–62** | D60 update on the same record; prefix comment `D60:`. Re-answering updates the existing follow-up; never duplicate a decision. | Capture partial implementation, donor changes, and emerging delivery evidence. | Capture actual operational response and early season evidence without treating an early signal as final outcome. | D60 answered count and comment trail; unresolved items remain Pending/In Progress with reason. |
| **W10 · D63–69** | Review closure readiness, evidence quality, outcome owner, and case-study eligibility. Arrange closure sessions for resolved decisions. | Gather decision minutes and current verified indicators; do not substitute activity counts for outcomes. | Schedule an end-of-season review when the business has meaningful results. | Per-decision closure date or reason unresolved; no unverified numbers promoted to results. |
| **W11 · D70–76** | Start R4 closure for decisions whose results are known. Recorder rates status and fills five lesson fields; export Outcome Review PDF. | Compare predicted vs observed programme results and record what the M&E evidence could not establish. | Rate only where the season's result is observable; use In Progress/Pending if it is not. | Rated status, written lesson(s), Outcome Review PDF, re-tested verdict, and recorded dissent where applicable. |
| **W12 · D77–83** | Close remaining resolved records; conduct a second overdue escalation. Draft Tier-A candidate case studies only from eligible closed loops. Ask for exact-text approval. | Identify donor/board decision evidence and limitations. | Prioritise S5 speed and seasonality evidence if an eligible outcome exists. | Closure coverage; case-study evidence appendix; written approval or explicit not-yet-approved status. |
| **W13 · D84–90** | Finalise verified metrics, reconcile payments, interview decision owners, present the cohort review, and make continue/renew/stop recommendations. Record open actions with owners and dates. | Compare results across NGO and development cohorts without pooling unlike baselines. | Assess speed, in-season outcomes, and renewal decision before the next relevant season. | Signed Day-90 review; final dashboard; renew/continue/stop decision; retention and next-quarter plan; case-study consent status. |

Calendar weeks are relative to cohort Day 0. For a late-starting organisation, retain the
cohort-level reporting dates but schedule its D30/D60/D90 events against its own
assessment/decision record; show the offset instead of silently shifting its metric
window.

## 3. Mentor plan

### Cadence and service standard

- **Two mentors recommended**, each with 5–6 named organisations and a named backup.
- **Kickoff:** one 60-minute session per organisation. Confirm roles, one real decision,
  permissions, source documents, consent, contact channel, and commercial status.
- **Weeks 2–3:** one 30-minute assessment/evidence review and one 30-minute R1 meeting.
  Keep the R1 meeting within 3 days of completion where the decision calendar allows.
- **Weekly:** review the queue; contact only organisations with a due action, blocker, or
  planned milestone. Record date, channel, result, next owner, and date in the roster.
- **D30:** 15-minute screen-share check-in per eligible decision. The customer enters
  their own answers. Mentor explains fields, does not select answers.
- **D45:** 30-minute midpoint interview per organisation; check trust, usefulness,
  friction, baseline change, and renewal intent.
- **D60:** 15-minute update for each eligible decision; customer updates the same record
  with `D60:` comment.
- **D75–90:** 30-minute R4 closure session for resolved decisions; 15-minute checkpoint
  for genuinely unresolved decisions. Do not force a rating.
- **Day 90:** 30-minute closeout interview per organisation and a cohort synthesis.

Batch cohorts into two mentor portfolios. Reserve 20% of mentor capacity for overdue
follow-up, incident triage, and rescheduling; do not allocate every hour to scheduled
meetings.

### Mentor session checklist

1. Confirm the speaker is the decision owner, evidence holder, or named recorder.
2. Ask the organisation to navigate and operate the platform; observe without taking
   over. Record time-on-task and any help required.
3. Ask what is useful, wrong, missing, or overstated; capture direct quotes only with
   permission.
4. Link each product claim to a source. Report factual/evidence over-claim immediately
   as a high-priority incident; do not “fix” the customer's record to make it look
   better.
5. End with one named owner, next action, due date, and contact channel.

### Escalation and incident handling

| Trigger | Action |
|---|---|
| Access or workflow blocks an active decision | Mentor logs reproduction steps and impact, alerts pilot lead same day, and offers a documented workaround only if safe. |
| A report materially overstates, misattributes, or fabricates evidence | Stop circulation; preserve assessment/run ID and source; notify pilot lead and organisation; classify as critical pending triage. Resume only after review and a corrected artefact. |
| Follow-up 0–3 days overdue | Send deep link in the agreed channel. |
| 4–7 days overdue | Offer a 10-minute call; customer enters answers. |
| 8–14 days overdue | Escalate to decision owner and pilot lead. |
| 15–28 days overdue | Ask the organisation to put it on its management agenda. |
| 28+ days overdue | Record unreachable/structural reason; do not backfill or count it answered. |
| Payment or invoice does not reconcile | Pause revenue claim and any related upgrade/renewal claim; finance owner investigates against provider and bank records. |

## 4. Outcome tracking plan

### Unit, lifecycle, and sources of truth

The primary measurement unit is an **eligible real decision record**, not an organisation,
user, assessment count, report download, or demo. Aim for one decision per organisation
(11 planned records); disclose the actual denominator if an organisation has none or
more than one. Keep the system's follow-up and outcome record linked to the same run.

| Stage | Required action | System of record / proof |
|---|---|---|
| Baseline (before advice) | Record decision question, decision date/deadline, current alternative, pre-confidence (1–5), existing decision-time baseline and source, intended measurable result, outcome horizon, and baseline evidence owner. | Restricted pilot register and source references; do not add unmeasured values to platform fields. |
| Decision | Named human records decision taken, date, reason, dissent, owner, expected result, and whether recommendation was followed. | Decision record/comment and meeting minute reference. |
| D30 | Record `decision_taken` (`yes / in_progress / no / unknown`) and `recommendation_followed` (`fully / partially / no / not_yet / unknown`), with factual comment. | `/outcomes` follow-up record. `unknown` is answered if submitted; `not_yet` is not counted as failure. |
| D60 | Update the same record, use `D60:` prefix, and capture drift/early evidence. | Same decision record; no duplicate record. |
| Closure (normally D75–90) | Rate only when known: Successful / Partially Successful / Unsuccessful. Otherwise Pending/In Progress with expected resolution date and reason. Complete all five lesson fields and re-test the original verdict. | Outcome record, five lesson fields, Outcome Review PDF, and supporting source. |
| Learning | Capture what changed, what was missed, what the institution will do differently, product gap, and any dissent. | Outcome record + closure minutes; pilot register links to both. |

**Definition guardrails:** “answered” is not “rated”; “rated” is not necessarily
“successful”; Completed is settled for some platform aggregates but is not one of the
three rated outcomes used for pilot rating targets; report download is not customer
adoption; decision followed is not proof of impact.

### Targets by profile

Targets below apply to **eligible decision records** in each profile, excluding demos.
Show numerator and denominator with each percentage.

| Profile | Eligible records planned | Answered by D30 | Rated by D90 | Lessons on rated outcomes |
|---|---:|---:|---:|---:|
| NGOs | 5 | ≥60% → at least 3/5 | ≥50% → at least 3/5 | ≥80% of rated records |
| Development Programmes | 3 | ≥60% → at least 2/3 | ≥50% → at least 2/3 | ≥80% of rated records |
| Tourism SMEs | 3 | ≥70% → at least 3/3 (stretch) | ≥65% → at least 2/3 (stretch) | ≥80% of rated records |
| **Cohort** | **11** | **Report the cohort total and all three strata; profile targets imply at least 8/11 answered.** | **Report the cohort total and all three strata; profile targets imply at least 7/11 rated.** | **Report numerator and denominator, not a pooled unsupported claim.** |

If fewer than 11 eligible real decisions exist, recalculate counts from the eligible
denominator, report both planned and actual denominators, and retain the profile targets
as percentages. Never manufacture a decision to fill the denominator.

### Learning hypotheses

| Hypothesis | Measurement |
|---|---|
| **H1 — recommendation followed** | Record pre-pilot comparison only if a defensible, sourced baseline exists. Otherwise report observed fully/partially followed ÷ decidable answers with `n`; treat the existing +20 percentage-point hypothesis as untested until there is a valid comparator. |
| **H2 — recommendation quality** | At closure, ask whether the original band was right, too cautious, or too confident; preserve the rationale and outcome evidence. Report observations, not an accuracy rate, below the calibration minimum. |
| **H3 — decision speed** | Measure elapsed time from documented decision question/complete evidence to human decision. Compare with a dated, sourced prior-cycle baseline; do not infer speed from report-generation time. Tourism target: decision cycle ≤14 days where the business decision horizon permits; independently preserve the 48-hour operational constraint. |
| **H4 — decision-maker confidence** | Record the same decision owner's pre- and post-review confidence on a 1–5 scale, at the same meeting; report paired `n` and change. Self-report is not a measured platform effect. |
| **H5 — trust from honesty** | Ask whether the system accurately represented evidence limits and whether the decision owner trusted the basis, not just the verdict. Record score, quote permission, and reasons. |

Do not present a trust-band calibration/success rate unless that trust band has at least
10 rated outcomes. With 11 planned records across multiple profiles, this is unlikely;
use **“observation only / NOT MEASURED”** when the rule is not met.

## 5. Payment validation plan

Separate **commercial intent**, **invoice/payment processing**, and **verified cash
revenue**. Do not promise monetisation or infer willingness to pay from product use.

### Before inviting the cohort

1. Executive sponsor and finance approve the offer: price, currency, billing period,
   taxes/fees, included services, refund/cancellation terms, payment due date, and
   who may authorise exceptions.
2. Mark each organisation **paid**, **comped**, or **no charge** in the roster, with
   reason, approver, value of any discount, contract/version, and dates. Comped and
   no-charge accounts are not revenue.
3. Verify the production billing configuration with a controlled test before accepting
   a real payment. The provider API secret and webhook signing secret must be configured
   when using those paths; secrets must remain in the deployment secret manager.
4. **Do not treat a return-page redirect as payment proof.** Disable hosted-link
   auto-confirm unless it is backed by an independently verified provider result.
   The production path must require successful provider verification or a valid signed
   webhook, bind the event to the correct transaction, organisation, plan, amount, and
   currency, and be idempotent on retries. Confirm the effective deployed setting; a
   source-file default is not evidence of production configuration.
5. Reconcile at least one approved, low-value end-to-end payment before representing
   the revenue dashboard as validated: provider-side successful transaction, signed
   webhook or provider verification, internal ledger event, subscription state, and
   bank settlement. If a safe live test is unavailable, state that live revenue
   validation is outstanding and do not claim production validation.

### Per-transaction controls

Finance maintains a reconciliation row containing organisation ID, invoice ID, price
version, transaction reference, expected/actual amount, expected/actual currency,
provider status, signed webhook or verification evidence reference, ledger event,
subscription state, settlement date, fees/refund, reviewer, and exception status. Store
no card data or secret/signature values in the register.

- Match amount and currency to the approved invoice; investigate partials, duplicates,
  unexplained differences, refunds, and chargebacks.
- Count **verified gross collected** only after successful provider confirmation; report
  bank settlement separately as net settled. Keep fees, refunds, taxes, and FX explicit.
- A `checkout_initiated`, pending, cancelled, failed, demo, or redirect-only event is
  not collected revenue.
- Customer activation, admin-reported ledger totals, and payment-provider confirmation
  are separate signals. A mismatch opens an exception and blocks the revenue claim.
- Weekly, two people (preparer and reviewer) reconcile the billing ledger to provider
  transactions; reconcile provider settlement to bank statements at month-end and D90.
- Test duplicate webhook/retry, wrong organisation, wrong amount/currency, invalid
  signature, pending, failure, cancellation, refund, and return-without-provider-proof.
  Each must remain non-success unless a valid verified payment exists.

### Revenue validation outputs

Report, by organisation and cohort:

1. Number offered paid terms; number signed; number invoiced; number with verified
   successful payment; number settled; number comped/no-charge; and number with an
   unresolved exception.
2. Verified gross collected, refunds, fees, net settled, currency, and period.
3. Renewal/paid-conversion intent separately from cash. “Willingness to pay” requires an
   explicit price-specific commitment or signed offer, not a positive interview.

## 6. Case-study plan

1. Maintain a candidate list for all 11 decisions with status: not eligible, waiting for
   outcome, eligible to draft, approval requested, approved, withdrawn, or published.
2. Begin a case only after a **rated outcome**, at least one written lesson, and an
   Outcome Review PDF exist. No launch/demo example is pilot evidence.
3. Use the existing [Case Study Template](CASE_STUDY_TEMPLATE.md) and
   [Success Story Framework](SUCCESS_STORY_FRAMEWORK.md). Trace every sentence and
   number to an artefact or organisation-supplied source.
4. Include evidence limitations, a contradiction/gap, the human decision and dissent,
   what changed, outcome and lesson. Never imply that the model made the decision or
   that the platform measured social/economic impact it did not measure.
5. Assign evidence tier before drafting: Tier A (rated outcome + lesson + PDF +
   organisation sign-off), Tier B (follow-up only; internal/in-progress), Tier C
   (engagement only; not a result), Tier X (demo/synthetic; exclude).
6. Ask all organisations for a case-study conversation; seek written, exact-text
   approval only for eligible drafts. Record named/anonymised choice, quote permission,
   approver and date, review-by date, and withdrawal route. No approval means no
   circulation.
7. Day-90 stretch objective: **three Tier-A case studies**—one S1 (caught a flaw), one
   S2 (closed loop), one S5 (Tourism speed)—only if the cohort actually produced the
   evidence and approvals. Do not lower eligibility to meet the count. Otherwise report
   the count and why candidates remain ineligible.

## 7. Customer success plan

### Success outcomes by organisation

At kickoff, agree one customer-defined job-to-be-done and an observable proof of value:
e.g. decision defensibility, faster decision, surfaced evidence gap, clearer programme
adaptation, or seasonal operational decision. Record the customer's baseline/source and
who will judge value. Do not prescribe “positive” verdicts or outcomes.

### Health and intervention

Each week's executive dashboard assigns every organisation:

- **Green:** named roles active; a real decision and next milestone are on schedule;
  no unresolved high-impact issue.
- **Amber:** missed milestone, missing role/source, low engagement, unclear customer
  value, or a due follow-up; named recovery action and date required.
- **Red:** organisation unreachable after escalation, material evidence/report defect,
  unresolved access/security/privacy issue, payment exception presented as revenue, or
  customer intent to stop; pilot lead contacts sponsor and sets pause/continue decision.

Health is an operational judgement with a written reason, not an inferred product score.
An organisation can be healthy while its verdict is negative or its outcome is
unsuccessful.

### Operating success practices

- Every customer meeting ends with “what happened / owner / due date”.
- Use existing channels and in-product reminders; no assumption of email/SMS automation.
- Review first-value time, user effort, support contacts, accessibility/mobile friction,
  and whether the product improved a live decision.
- Escalate privacy, consent, access-control, or material factual-integrity concerns
  immediately to the pilot lead; pause affected use while assessed.
- At D45 and D90, ask the decision owner whether they would use it again, for which
  decision, and what must change. Record verbatim reasons with permission.

## 8. Renewal plan

Renewal is a decision, not a default and not a proxy for product satisfaction. Start
commercial planning at D60 and complete a documented decision by D90.

| Timing | Action |
|---|---|
| **D45** | Ask whether the customer expects another relevant decision in the next 90 days; identify budget owner, procurement steps, security/legal requirements, and unresolved value questions. No pressure to commit. |
| **D60** | Present a customer-specific evidence review: decisions processed, time-on-task, reports actually used, outcomes known vs unresolved, support/incident record, and known limitations. Share only verified payment data. |
| **D70–80** | If requested, provide a written renewal offer with approved price/version, scope, dates, service boundaries, data handling, cancellation, and payment terms. Track sent/accepted/declined/no decision. |
| **D81–89** | Confirm signer and procurement status. Resolve material objections; do not convert verbal interest into contracted recurring revenue. |
| **D90** | Record signed renewal, explicit decline, or pending decision with owner/date. Renewals count only when a valid contract/order is signed; paid renewal counts as revenue only after the payment validation controls pass. |

Record renewal funnel separately: eligible to renew, offer requested, offer sent, signed,
paid/settled, declined, pending, and reason. A comped extension is retention, not revenue.

## 9. Success metrics

| Metric | Day-90 success test | Interpretation |
|---|---|---|
| Cohort mobilisation | 11/11 have named decision owner, evidence holder, recorder/backup, mentor, and commercial status. | A missing role is an onboarding gap, not user failure. |
| Real decision chain | Each denominator is an eligible real decision record; target one per organisation. Report records and organisations separately. | Exclude demo/synthetic and disclose any organisation without a real decision. |
| D30 follow-up | NGOs ≥3/5; Development Programmes ≥2/3; Tourism SMEs ≥3/3 stretch; show answered `n/N` and answer distribution. | Answered is not rated; unknown can be an answer but is not evidence of follow-through. |
| Rated outcomes by D90 | NGOs ≥3/5; Development Programmes ≥2/3; Tourism SMEs ≥2/3 stretch; show `n/N` and unresolved records. | A genuinely unresolved result stays In Progress/Pending. |
| Learning | ≥80% of rated outcomes have a concrete “What Happened” lesson; track all five fields separately. | Empty lessons are not silently inferred from reports. |
| Closed loops | Count decisions with follow-up, rated outcome, lesson, and Outcome Review PDF; report `n/N`. | A case-study candidate is not a closed loop until required evidence exists. |
| User independence | For assessment, evidence review, signals, decision, report, and follow-up, record task completion, elapsed time, assistance needed, and failure. | Mentor observing is allowed; mentor completing the step for the user is not independent completion. |
| Customer value | Paired confidence `n` and change; decision time with comparable baseline `n`; explicit reuse intent and reason. | Self-report and small samples are labelled; no causal claim without a valid comparator. |
| Report quality | Profile/language checks passed; no unresolved material wrong-fact or over-claim incident at publication. | A modest score or candid evidence gap may be a valid positive trust finding. |
| Case studies | Tier-A count, profile, story type, approval status; stretch 3 (S1/S2/S5) only when evidence permits. | No approval or insufficient outcomes means no public story. |
| Payment integrity | 100% of claimed collected revenue independently verified; zero redirect-only/demo/pending events represented as cash; no unexplained reconciliation exceptions. | If no fee was charged, report zero verified revenue and the actual price-specific commitments separately. |
| Renewal | Signed renewals / eligible organisations; paid renewals / verified paid offers; reasons for decline and pending. | Interest, comping, or verbal intent is not a signed renewal or revenue. |

## 10. Failure metrics and stop/escalation triggers

Failure metrics are not averaged away. The pilot lead reports count, denominator, impact,
owner, due date, and disposition.

| Failure measure / trigger | Response |
|---|---|
| Fewer than the profile D30 answer target, or unanswered items without an owner | Run the overdue ladder; interview the recorder/decision owner; mark unreachable or no recorder honestly. |
| Fewer than the profile rated-outcome target at D90 | Report unresolved count and reason by profile. Do not label pending as unsuccessful or create a case study. |
| User needs mentor to complete any core step | Mark that step as staff-assisted, record why, and test whether training, access, or product design caused it. |
| Any fabricated, materially unsupported, or misattributed report claim | Stop report circulation and affected case study; escalate same day; preserve artefacts; resume only after documented triage/correction. |
| Any cross-organisation data exposure, unauthorised access, or consent breach | Immediate pause for affected organisation; notify designated security/privacy owner and sponsor; follow incident process before resuming. |
| Any payment activation without provider verification/signed webhook or any claimed revenue that fails reconciliation | Freeze the revenue claim and affected activation/renewal decision; escalate to finance and pilot lead; correct ledger/dashboard narrative. |
| Unresolved high-severity issue blocks a real decision, or repeats across organisations | Pilot lead decides pause, scope reduction, or stop; communicate to affected organisations. |
| Customer withdraws consent or requests removal | Stop use of affected quote/story immediately; honour withdrawal and record completion; retain operational metrics only where lawful and permitted. |
| Calendar time exceeds the decision's real deadline or Tourism processing delays a 48-hour decision | Log exact wait and cause; do not call the workflow successful because a report eventually arrived. |
| Satisfaction/renewal intent is positive but there is no real use, outcome evidence, or price-specific commitment | Record as positive sentiment only; do not count as success, impact, conversion, or willingness to pay. |

## 11. Executive dashboard

### Weekly cohort snapshot (one row per organisation)

| Org ID / profile | Mentor | Health + reason | Decision / run ID | Decision due | Users / recorder active | Core steps completed independently | Follow-up `answered / eligible` | Rated `n / eligible` | Lessons `n / rated` | Oldest overdue | Incidents open by severity | Commercial state | Verified paid / settled | Renewal stage | Next action · owner · due |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| … one row for each of 5 NGOs, 3 Development Programmes, and 3 Tourism SMEs … | | | | | | | | | | | | | | | |

Use `NO DATA`, `not reached`, `no decision`, `no recorder`, `not applicable`,
`comped`, or `pending` with a reason where a cell would otherwise be blank. Avoid
customer-sensitive detail in broad executive circulation.

### Cohort top-line

| Area | Weekly value to show |
|---|---|
| Cohort | 11 planned; active / paused / withdrawn count; organisation health count G/A/R; one-line change since last week. |
| Workflow | Eligible decisions; assessments completed; reports circulated; user-independent completion by core step; assistance and failure counts. |
| Follow-up | D30 answered / eligible with `n/N`, split NGO / Development / Tourism; due now; overdue by 0–3, 4–7, 8–14, 15–28, 28+ days. |
| Outcomes | Rated / eligible by profile; Pending/In Progress; lessons written; closed loops; sample-size caveat and reportability. |
| Customer success | Median first-value time where measured; paired confidence `n`; sourced decision-speed comparisons `n`; support/incidents; use-again intent with `n`. |
| Evidence quality | Open incidents by Critical/High/Medium/Low; report claims paused/corrected; document/provenance gaps. |
| Billing | Paid / comped / no-charge accounts; invoiced; provider-verified; bank-settled; gross, fees, refunds, net; reconciliation exceptions. |
| Case studies | Ineligible / waiting / eligible / drafted / approved / withdrawn; Tier-A count and consent status. |
| Renewal | Eligible, offer requested/sent, signed, paid, declined, pending; reason for each non-renewal. |
| Decisions required | Maximum three decisions: ask, owner, due date, consequence if not decided. |

### Dashboard rules

1. Refresh from `/admin`, `/admin/outcomes`, `/admin/billing`, `/admin/ai-health`, and
   customer `/outcomes`; reconcile exceptional payment claims to provider and bank
   evidence.
2. Use the same time window and definitions week to week. The admin active-user figure
   is audit-derived activity, not a login counter; state its definition.
3. Always show numerator, denominator, profile, and sample size. Do not pool profiles
   when their thresholds or decision horizons differ.
4. Keep cumulative cohort totals separate from a rolling 30-day view; label both.
5. Hide no failures behind a composite score. A red issue remains visible until an
   owner verifies closure.
6. Share a redacted executive summary; detailed payment, personal, and source-document
   information stays access-controlled.

## 12. Day-90 executive decision

At Day 90 the sponsor chooses one outcome and records rationale:

- **Continue / renew:** no unresolved critical trust, privacy, access, or payment-integrity
  issue; customers have a documented next decision; at least one defensible value signal
  is evidenced; renewal scope and commercial terms are approved.
- **Continue with conditions:** value is credible but defined fixes, missing outcomes,
  or procurement steps remain; name owner, budget, deadline, and a review date.
- **Pause:** a material issue makes continued use or a commercial claim unsafe until
  resolved.
- **Stop:** the cohort does not demonstrate a defensible customer job-to-be-done, users
  cannot complete the workflow at an acceptable level of assistance, or risks exceed
  the value.

The final memo includes this dashboard, cohort/profile denominators, payment
reconciliation status, unresolved outcomes, customer quotations only where permitted,
case-study approvals, incidents, and the signed decision. Small samples and unknowns
remain visible.
