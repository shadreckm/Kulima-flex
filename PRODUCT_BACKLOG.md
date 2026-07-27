# Product Backlog — Kulima FLEX

This backlog translates the product-readiness recommendations into prioritized product work. Each item includes Priority, Effort, Dependencies, and Expected Impact.

---

P-1: Demo dataset + guided tour (first-time UX)
- Priority: P0
- Effort: S
- Description: One-click demo mode with a curated sample brief and a 60–90s step-through overlay that introduces the Run button, Executive Overview, Ask IC, Twin Syndicate, and Export.
- Dependencies: Engineering E-7 (demo dataset), marketing copy, sample dataset.
- Expected impact: Very High — dramatically improves first-time conversion and demo throughput.

P-2: "Prepare IC Pack" unified export workflow
- Priority: P0
- Effort: L
- Description: A single UX to select sections and produce a bundled IC package: PDF memo, PPTX slides, raw evidence files, and optional partner notes.
- Dependencies: Engineering E-6 (export pipeline), audit logging (E-4), storage.
- Expected impact: Very High — core investor value (reduces friction for IC preparation).

P-3: Pilot onboarding kit + playbook
- Priority: P0
- Effort: S-M
- Description: Customer success kit containing step-by-step onboarding, sample data, training script, admin checklist, and success metrics for pilot engagements.
- Dependencies: Admin console & demo mode (E-12, E-7), product marketing.
- Expected impact: High — increases pilot win rate and shortens sales cycles.

P-4: Improve information hierarchy & card templates
- Priority: P1
- Effort: M
- Description: Rework key card templates to emphasize primary signal (Recommendation + Conviction) > one-line rationale > key metrics (Thesis Fit, Reliability). Create consistent microcopy for score semantics.
- Dependencies: Design system, UI engineering.
- Expected impact: High — reduces cognitive load and speeds decision-making in ICs.

P-5: Shareable founder readout (founder-facing export)
- Priority: P1
- Effort: M
- Description: A sanitized, founder-friendly export variant with clear remediation steps and anonymized or redacted sensitive content if needed.
- Dependencies: Export pipeline, legal review.
- Expected impact: Medium — extends product use to founders and supports outreach.

P-6: Mobile-first critical flows (Run, Summary, Ask IC)
- Priority: P1
- Effort: M
- Description: Design & deliver simplified mobile views for the core flows, ensuring key actions and reading are accessible on phones.
- Dependencies: Engineering E-8, UX design.
- Expected impact: High — improves partner usage, especially for on-the-go partners.

P-7: IC Pack templates & memo customization options
- Priority: P2
- Effort: M
- Description: Offer templated memo formats selectable at export time (Partner-ready, Founder-friendly, Board-ready) and allow light customization (title, partner note).
- Dependencies: Export pipeline.
- Expected impact: Medium — improves utility for various audiences.

P-8: Pricing model / billing plan definition
- Priority: P2
- Effort: M
- Description: Define pricing tiers for pilot -> paid conversion (credits, seats, runs), and productize metering points.
- Dependencies: Finance & legal, Engineering E-11.
- Expected impact: High — necessary for commercial rollout.

P-9: UX microcopy for Trust Layer and Thesis signals
- Priority: P1
- Effort: S
- Description: Short, consistent explanatory copy for each badge/metric with tooltip text and help links to a glossary.
- Dependencies: UX writers, product owners.
- Expected impact: Medium — reduces confusion.

P-10: Export audit viewer (admin-facing)
- Priority: P1
- Effort: M
- Description: UI surface for viewing who exported what, when, and links to the exported artifacts.
- Dependencies: E-4 audit logging and E-6 export storage.
- Expected impact: High — improves governance and trust for pilots.

---

Product acceptance notes
- Prioritize P-0 items that accelerate demos and pilot conversions.
- For P-1 items, define success metrics (ex: demo->trial conversion rate, time-to-IC-pack creation) to measure impact.

