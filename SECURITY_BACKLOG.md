# Security Backlog — Kulima FLEX

This backlog lists security-critical actions required to operate safely at scale and support enterprise adoption. Items are prioritized with Priority, Effort, Dependencies, and Expected Impact.

---

S-1: Full audit of unsafe HTML usage and templating policy
- Priority: P0
- Effort: M
- Description: Perform a systematic code audit for every place that injects HTML. Enforce a templating policy: static templates + textwrap.dedent for multi-line blocks; always html.escape() dynamic values; add CI lint rule to prevent unsafe patterns.
- Dependencies: Codebase access, owners, CI integration.
- Expected impact: Very High — closes XSS surface and stabilizes rendering.

S-2: Implement Content Security Policy (CSP) and HTTP header hardening
- Priority: P1
- Effort: M
- Description: Add CSP headers, HSTS, secure cookies, and other response header hardening. Coordinate with hosting (Streamlit Cloud / chosen host). Test across browsers.
- Dependencies: Hosting platform configuration, CDN.
- Expected impact: High — reduces attack surface and improves security posture.

S-3: Secrets management & vault integration
- Priority: P0
- Effort: M
- Description: Move all secrets and API keys into a secure vault (AWS Secrets Manager / HashiCorp Vault / Azure Key Vault). Enforce ephemeral tokens for CI, rotate keys on schedule.
- Dependencies: Cloud provider, CI integration.
- Expected impact: Very High — protects credentials and model/GCP/AWS keys.

S-4: SSO / RBAC policy definition and implementation (security side)
- Priority: P0
- Effort: L
- Description: Define secure role model (least privilege), implement SSO connectors (SAML/OIDC) and ensure role enforcement in backend APIs and on export assets.
- Dependencies: Identity provider, engineering integration, tenancy model.
- Expected impact: Very High — required for enterprise adoption.

S-5: Penetration testing and 3rd-party model risk assessment
- Priority: P1
- Effort: M
- Description: Commission a penetration test covering the UI, API, and third-party model usage. Document third-party data sharing risks with LLM vendors and mitigate (minimize PII exposure, tokenization, or redaction).
- Dependencies: Security vendor, test accounts.
- Expected impact: High — necessary for security sign-off.

S-6: Encryption-at-rest and in-transit verification
- Priority: P0
- Effort: M
- Description: Verify all stored artifacts (briefs, exports, logs) are encrypted at rest; ensure TLS for all in-transit connections and verify certificate management.
- Dependencies: Cloud provider settings, KMS, storage lifecycle.
- Expected impact: Very High — required for data protection compliance.

S-7: SIEM / security monitoring & alerting integration
- Priority: P1
- Effort: M
- Description: Ship logs to SIEM (CloudWatch/Datadog/ELK) and set alerting for suspicious activity (repeated failed logins, unusual export counts, or elevated token usage).
- Dependencies: Audit logging (E-4), SIEM vendor.
- Expected impact: High — improves detection & response.

S-8: Audit log immutability & retention policy
- Priority: P0
- Effort: M
- Description: Design log retention and immutability (append-only with protections or WORM storage). Implement retention schedules and exportable audit records for compliance.
- Dependencies: Storage & legal retention policy.
- Expected impact: Very High — enterprise compliance requirement.

S-9: Automated security scans in CI (dependencies & supply chain checks)
- Priority: P1
- Effort: S
- Description: Integrate Snyk/Dependabot/SCA and static scanners into CI to detect vulnerable dependencies and insecure code patterns.
- Dependencies: CI pipeline.
- Expected impact: Medium — prevents regression in dependencies.

S-10: Incident response plan and policy documentation
- Priority: P1
- Effort: M
- Description: Draft IR runbooks, contact lists, communication flows, and breach notification templates. Ensure legal and product teams sign off on DPA-level procedures.
- Dependencies: Legal and leadership input.
- Expected impact: Medium — readiness for incidents.

---

Security acceptance notes
- Mark S-1 and S-4 as blockers for any enterprise pilots. No enterprise pilot should proceed until S-0 items are at least partially addressed.
- Add security sign-off gates for releases touching unsafe HTML or export mechanisms.

