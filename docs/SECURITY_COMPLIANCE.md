# Security, Threat Intelligence and Compliance Rules

## App security and isolation
- Implement authentication and organization membership; current supplied API has no auth routes. Use Argon2id password hashes, short-lived access tokens, rotating/revocable refresh tokens, issuer/audience/expiry validation and role checks. Keep refresh credentials protected (HttpOnly/Secure/SameSite cookie with CSRF controls, or equivalent safe design); don't store long-lived secrets in browser localStorage.
- Roles: owner/admin manage membership and policy; analyst import/run/triage; viewer read-only. Enforce access in every service, database query, artifact read, chat, job, alert and WebSocket subscription.
- Use least privilege. Restrict CORS to configured frontend origins; the current wildcard CORS configuration is demo-only. Rate-limit login, uploads, scans, chat, refresh and expensive optimizer calls.
- Store secrets in environment/secret manager. Add `.env.example` placeholders; remove and rotate tracked real secrets; never log environment values, tokens, passwords or raw sensitive payloads.
- Validate upload size, extension/content signature and schema. For ZIP: reject traversal/absolute paths, duplicate conflicting table paths, nested/oversized entries, excessive compression ratios and decompression bombs. Stream uploads where possible; calculate SHA-256. Parse XML with a safe parser (e.g. `defusedxml`), disable external entities, never execute uploaded files/macros, and sanitize errors.
- Use generated UUID storage keys. No user-controlled path segments. Keep files outside public/static directories. Verify tenant ownership before opening a file or result artifact. Add per-org quotas and retention policy.
- Use TLS in deployment, secure headers, dependency scanning, database migrations/backups, audit logging and operational monitoring.

## Threat-intelligence operations
Primary references:
- FIRST EPSS data/API: https://www.first.org/epss/data and https://api.first.org/data/v1/epss
- CISA KEV catalogue: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- CVSS 4.0 specification: https://www.first.org/cvss/v4.0/specification-document

Rules:
- Query FIRST EPSS API for individual/small-batch findings; use daily CSV sync for bulk refresh. Store score, percentile, CVE, source date/fetch time and response/source version. Never put all API calls in dashboard request handling.
- Fetch the official CISA KEV catalogue on a scheduled job and validate schema/checksum. Store date added, required action/due date where provided, catalogue version/fetch time and match state.
- Add bounded timeouts/retries, exponential backoff, rate limiting, cache TTL, failure metrics and manual refresh status. Staleness is visible. Previous successful snapshots remain auditable.
- Treat CVSS, EPSS, KEV, asset exposure and control evidence as different dimensions. No one field proves compromise or directly determines a financial loss amount.

## Regulatory assessment
Primary sources that must be rechecked during implementation and periodically:
- CERT-In Section 70B directions/FAQs: https://www.cert-in.org.in/Directions70B.jsp
- MeitY Acts and Policies: https://www.meity.gov.in/documents/act-and-policies
- MeitY DPDP Rules 2025 and enforcement timeline: https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digit
- NIST CSF 2.0: https://www.nist.gov/cyberframework
- NIST IR 8286 Rev. 1 (published Dec 2025): https://csrc.nist.gov/pubs/ir/8286/r1/final
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework

- Rules must be provision-level, source-linked, versioned, effective-date-aware and reviewed by a qualified compliance/legal owner. Store jurisdiction, sector/applicability predicates, source URL/citation, effective start/end, date last verified, version, evidence needed and reviewer.
- Clearly distinguish a control gap, suspected event, potential exposure scenario, reporting obligation/deadline and confirmed/legal-reviewed conclusion. A scanner finding alone does not establish a breach or statutory violation.
- Do not invent or extrapolate statutory fine formulas. Show statutory caps/ranges only when verified from authoritative text; do not label the maximum as likely or expected penalty. Missing/ambiguous facts return `needs_review` rather than a numeric fine.
- Track incident fact timestamps, discovery time, awareness time, affected data/subjects, impacted system, containment actions, reporting status and deadline evidence where relevant. Deadline generation must cite the actual applicable rule version and require human review.
- Framework mappings (ISO/NIST/CIS/RBI/SEBI) need mapping version, control citation, coverage denominator and evidence status. A mapped control or coverage percentage is not a certification.

## AI/ML and output integrity
- Use time-aware train/test splits and prevent leakage from future outcomes. Report baseline and ML metrics, class balance, precision/recall, PR-AUC where appropriate, calibration, training window, label definition and model version.
- If data are too sparse, return `insufficient_data`; don't fabricate a directional LSTM forecast. Distinguish observed and synthetic live-feed events; mark inferred dependency edges.
- Use LLM output only to explain authorized calculated context. The LLM must not generate authoritative numeric risk values, statutory findings, scanner results or optimizer selections. Validate inputs/outputs and keep untrusted data out of system instructions.
- Log prompts minimally, avoid sending raw sensitive uploads externally, and provide provider/model setting and data-sharing controls.

## Recommended lifecycle states
External feed: `fresh`, `stale`, `unavailable`, `invalid`.
Finding-to-asset: `matched`, `unmatched`, `pending_review`, `rejected`.
Regulatory assessment: `not_applicable`, `gap`, `potential_exposure`, `needs_review`, `reviewed`.
Alert: `open`, `acknowledged`, `in_progress`, `resolved`, `closed`, `reopened`.
Delivery: `queued`, `sent`, `failed`, `simulated`.
