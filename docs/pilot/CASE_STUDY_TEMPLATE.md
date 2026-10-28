# Case Study Template

One closed loop = one case study. A case study is **not** marketing copy; it is a
transcription of a record that already exists in the platform, written in the
organisation's own words and traceable line by line.

**Rule: every sentence in a case study must be attributable to a specific artefact.**
If you cannot name the screen or document it came from, it does not go in.
**No case study before R4 (rated outcome + Outcome Review PDF).** An assessment without
an outcome is a demo, and demos are excluded from the pilot data.

## Header block

| Field | Source (where it is read from) |
|---|---|
| Organisation / programme name (or agreed anonymity label) | intake |
| Entity profile — NGO · Development Programme · Government Programme · Tourism SME · Startup | `/assessments` row |
| Sector, country | assessment context |
| Review generated | `/reports` — Institutional Capacity Review / Programme Performance Review / Governance Review / Tourism Resilience Report / Investment Committee Report |
| Decision under review (one sentence, theirs) | comment field at R1 |
| Date of decision · date of follow-up · date of outcome | record timestamps |
| Author · approver · date approved | this document |

## 1. The decision they actually faced

Their words, one short paragraph. Who decides, what was on the table, what the deadline
was. Quote from the decision comment verbatim where possible.

## 2. The evidence they brought

List the uploaded documents by name (as `/evidence` shows them): annual report,
programme review, logframe export, indicator table, occupancy summaries, bank paper.
State the **trust score**, **evidence grade** and **verification status** exactly as the
platform shows them — including `INSUFFICIENT EVIDENCE` or `not audited` where that is
what it says. A modest trust score on thin documents is a legitimate finding and often
the most credible part of the story.

## 3. What the platform surfaced

Three items max, each in this form:

> **Signal / finding** — *why it mattered* — *which source it came from* (their document
> or clearly-labelled public research).

Include at least one **negative or uncomfortable** item: a contradiction between sources,
an unsupported claim, a gap the documents could not close. A case study with only praise
is not believable and is not this product.

## 4. The verdict and the disagreement

- Verdict band in the profile's own language (Strong Capacity / Ready / Effective /
  Ready for Growth / Invest — with the middle and lower bands named too).
- **Confidence and evidence basis as displayed** — never rounded up.
- What the decision team **disagreed with**. Dissent is mandatory content; if there was
  none, say so and note that as a finding about the review process.
- If they re-tested the band at R4: *"in hindsight the band was right / too cautious /
  too confident"* with their sentence.

## 5. What changed because of it

Concrete actions taken — reallocation, partner change, revised budget ask, renovation
timing, staffing decision — with dates. This is the difference between "we read a report"
and "decision intelligence". Tie to `recommendation_followed`:

- `fully` — what was done exactly as recommended.
- `partially` — what was taken, what was bent, and why (the most valuable paragraph in
  the whole corpus).
- `no` / `not_yet` — what stopped it. An honest "we did not act" is a publishable case
  study if the reason is real.

## 6. Outcome

| Field | Value as recorded |
|---|---|
| Outcome status | Successful · Partially Successful · Unsuccessful |
| What happened | verbatim from the lesson field |
| What was predicted | verbatim |
| What was missed | verbatim |
| What worked | verbatim |
| What failed | verbatim |
| Days from assessment to decision · to follow-up · to rated outcome | from the record / mentor's timing log |

**Never** state a quantified impact ("+18 %", "reached 12,000 more households") unless the
organisation wrote that number somewhere in the record or supplies their own source. The
platform does not measure their impact and will not claim it did.

## 7. Learning (the paragraph that earns its keep)

Two to four sentences answering: *what will this institution do differently next time,
and what should the next assessment have looked for?* This is the "Learning" leg of
Decision → Outcome → Learning and the only part that compounds.

## 8. Evidence appendix

- Outcome Review Report PDF (the primary source of truth).
- The profile review PDF as circulated.
- Screenshots only where a number needs context.
- The verbatim comment trail (`D60:` / `D90:`).

## Honesty checklist — all must be ✓ before circulation

- [ ] Every figure appears in the record or an organisation-supplied source.
- [ ] Trust score, grade and confidence are shown as displayed, including empties.
- [ ] At least one limitation, gap, contradiction or dissent is named.
- [ ] No other organisation's result, no demo record, no synthetic example is used.
- [ ] Outcome is **rated**; if it is not, this is an assessment note, not a case study.
- [ ] No aggregate success rate is quoted from fewer than ten rated outcomes in a band —
      the correct wording is "observation only".
- [ ] The organisation approved the exact text in writing (name, role, date).
- [ ] Anonymity/branding choice respected; withdrawal route stated in the approval mail.

## Approval block

> Approved for use as a Kulima FLEX pilot case study.
> Name: ______________________  Role: ______________________  Date: __________
> Identifiable / anonymised (circle one). Quotations permitted verbatim: yes / no.
> Withdrawal: any quotation may be removed on request at any time.

---

### Worked micro-example — FICTIONAL, DO NOT CIRCULATE

Structured so the shape is clear. **This is not pilot evidence and must never be quoted.**

> *Profile: NGO, East Africa. Decision: whether to redesign a grant renewal around two
> counties. Documents: annual report, mid-term evaluation, logframe export. Trust score
> displayed as recorded, evidence grade C, two contradictions flagged between the
> narrative reach figure and the indicator table. Verdict: Moderate Capacity — the
> renewal case rested on an unverifiable reach claim. Action: leadership re-cut the
> renewal around verified indicators (followed: partially — the county reallocation
> happened, the M&E staffing line did not, because of a hiring freeze). Outcome at day 88:
> Partially Successful. Lesson recorded: "corroborate reach figures in a second document
> before a funder asks." No aggregate improvement rate is claimed — too few rated
> outcomes exist to compute one.*
