# Enterprise Readiness Backlog — Kulima FLEX

This backlog focuses on the product and operational work required to support enterprise pilots and paid customers. Each item includes Priority, Effort, Dependencies, and Expected Impact.

---

ER-1: Tenant isolation architecture & implementation
- Priority: P0
- Effort: XL
- Description: Define and implement multi-organization data isolation — choices: row-level security, per-tenant schema, per-tenant cluster, or hybrid. Include storage segregation for exports and backup/restore strategy per tenant.
- Dependencies: Engineering E-2, Security S-3, S-6, legal.
- Expected impact: Very High — prerequisite for enterprise adoption.

ER-2: SSO (SAML/OIDC) onboarding flow + RBAC & provisioning
- Priority: P0
- Effort: L
- Description: Implement SSO integration templates for common IdPs (Okta, Azure AD, Google Workspace). Provide SAML metadata exchange UI and allow JIT provisioning or SCIM sync for users and groups.
- Dependencies: S-4, E-3, tenant model.
- Expected impact: Very High — critical enterprise requirement.

ER-3: Admin console — tenant management, feature flags, and user management
- Priority: P1
- Effort: L
- Description: A secure admin UI for creating/managing tenants, assigning seats, managing feature flags, and inspecting export and usage logs.
- Dependencies: ER-1 (tenant model), E-4 (audit logs), E-11 (metering).
- Expected impact: High — reduces manual operational overhead for pilots.

ER-4: Billing & usage metering (billing MVP)
- Priority: P1
- Effort: M
- Description: Implement a metering pipeline to produce per-tenant usage reports (runs, token consumption, exports) and a billing export or simple invoice CSV. Include seat-based and credits-based models support.
- Dependencies: E-11, ER-3.
- Expected impact: High — necessary to transact with customers.

ER-5: Audit & compliance pack (SOC2 readiness spike)
- Priority: P0
- Effort: M-L
- Description: Prepare the artifacts, policies, and gap analysis for SOC2 (or equivalent). Produce an initial compliance pack: policies, manifests, access logs, encryption posture, and incident response.
- Dependencies: S-1..S-8 (security items), legal.
- Expected impact: Very High — enterprise procurement often requires SOC2/DPA.

ER-6: SLA & operational runbooks (on-call, incident handling)
- Priority: P1
- Effort: M
- Description: Define service levels for response times and availability. Build runbooks for common incidents (model provider outage, job worker failure, export failures) and define on-call rotations.
- Dependencies: Observability & monitoring (E-10, S-7), operations staff.
- Expected impact: High — builds trust with customers.

ER-7: Data residency & per-tenant KMS / key management
- Priority: P1
- Effort: L
- Description: Support tenant requests for data residency and per-tenant encryption keys (bring-your-own-key or per-tenant KMS configuration).
- Dependencies: Cloud provider capabilities, S-6.
- Expected impact: High — required for large multinationals and regulated customers.

ER-8: Pilot onboarding capability & sandbox provisioning (fast path)
- Priority: P0
- Effort: S
- Description: Capability to create sandbox tenants with demo data, default feature flags, and pre-configured sample exports for quick pilot setup.
- Dependencies: ER-1, ER-3.
- Expected impact: High — shortens time-to-value for pilot customers.

ER-9: Legal agreements: DPA / Terms of Service / Privacy Policy
- Priority: P1
- Effort: M
- Description: Draft and finalize legal documents required for enterprise pilots (DPA) and public-facing terms. Get sign-off from legal counsel.
- Dependencies: Legal, product leadership.
- Expected impact: High — contractual prerequisite.

ER-10: Integration surface (Slack/Teams/Calendar) and identity provisioning
- Priority: P2
- Effort: M
- Description: Enable basic enterprise integrations for notifications, meeting scheduling, and calendar invites for ICs.
- Dependencies: APIs, admin console.
- Expected impact: Medium — enhances operational utility.

---

Enterprise acceptance notes
- ER-1 and ER-2 are blockers for enterprise pilots — treat as critical path.
- Prepare a customer-ready pilot checklist (ER-8 + P-3) that sales/CS can follow.

