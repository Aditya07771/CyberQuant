# Acceptance Tests and Release Gate

Tests are requirements, not suggestions. External providers must be mocked by default so the suite runs offline. Include unit, API, integration, security and UI/build checks. Never claim a check passed unless it ran.

## Identity and tenant isolation
- Register/login/refresh/logout; password hashes are not reversible; expired/revoked/reused refresh tokens are rejected; role restrictions are enforced.
- Organization A cannot list/read/download/modify organization B's datasets, scans, findings, run results, Parquet artifacts, chat context, jobs, forecasts, alerts, deliveries, remediation tasks or live feed—even with guessed UUIDs.
- Every legacy route is protected and scoped, or removed/deprecated. No route serves global `backend/outputs` to arbitrary users.

## Dataset ingestion and jobs
- CSV bundle, valid ZIP, JSON and Excel formats accepted; existing five-table schema stays compatible.
- Reject missing tables/columns, duplicate IDs, broken FKs, invalid enum/status values, negative costs, CVSS/EPSS out of range, invalid dates, unknown currencies, oversized files and malformed data with stable errors.
- ZIP traversal, absolute paths, symlinks if applicable, duplicate conflicting entries, nested archive abuse, decompression bombs and XML external entities are rejected safely.
- A completed upload creates immutable dataset/version/artifact/job metadata. Repeat requests with the same idempotency key do not duplicate state. Failed job has a safe code and can be retried.
- Output paths are server-generated and dataset/run scoped; one dataset never overwrites another's artifacts. Demo is marked `synthetic_demo` and doesn't overwrite seed files.

## Scanner and threat intelligence
- OpenVAS XML, Nessus JSON and AppSec CSV fixtures parse known findings into normalized rows; malformed/unsupported variants return actionable validation results.
- Re-importing the same observation is idempotent; changed severity/status updates observation history without erasing the original evidence. Unmatched assets require review; IP-only matching does not merge identities.
- Mock FIRST EPSS and CISA KEV clients validate response shape, retries, cache behavior, historical snapshot and stale/unavailable state. A source failure never converts missing score to zero risk.
- A RiskRun records source checksum, parser/enrichment/model/config version, exact threat-intelligence snapshot and random seed.

## Quantitative model
- EPSS annualization boundary tests are correct under the documented assumption; severity remains separate from exploitation probability unless the calibrated model explicitly combines them.
- Every loss component is traceable to a source/assumption and has currency. Negative/NaN/infinite values are rejected or explicitly handled; no silent zero fallback.
- Quantile-fitting tests check requested quantile definitions (e.g. q05/q95 uses matching z-score); generated losses are nonnegative and percentiles monotonic.
- Fixed seeds are reproducible within declared tolerance. `ES95 >= VaR95 >= 0`, `ES99 >= VaR99`, sample count and LEC probability ranges are valid.
- Portfolio VaR/ES are computed from the combined per-iteration portfolio sample, not summed individual VaRs; common-event behavior and independence assumptions are tested/documented.
- Multiple controls cannot silently force risk to zero through additive percentage stacking; required controls/dependencies and budgets are enforced by optimizer. ILP status and greedy baseline are returned clearly.

## Regulatory, alerts and remediation
- Every rule includes verified source, provision, version, effective interval and reviewer metadata. Effective-date tests cover before/during/after applicability.
- A vulnerability by itself cannot create a confirmed breach or numeric fine. Missing evidence produces `needs_review`; maximum statutory cap is never misreported as expected fine.
- Alert policy tests cover each trigger, dedupe, threshold changes, status transitions, assignment, due date, escalation, resolution, closure and reopening on material change.
- SMTP/webhook failures persist with attempts and sanitized errors; retry is bounded and idempotent. `simulated` delivery is never reported as `sent`.
- Audit events are written for auth-sensitive actions, source import, model runs, regulatory review, alert status changes, policy edits and artifact export.

## ML, API and frontend
- Predictor and forecaster report version, feature window, label definition, data sufficiency and validation metrics; evaluation is time-aware and compared with a baseline. Short histories produce `insufficient_data`.
- Dependency graph labels observed versus inferred edges and propagation behavior is deterministic under fixtures.
- API contract tests verify status codes, Pydantic shapes, pagination, auth errors, request IDs, rate limits, scoped queries and no internal path/stack-trace leakage.
- Frontend uses `/api/v1` routes, handles auth expiry/job polling/validation errors, displays source freshness, assumptions, uncertainty, currency, model/run IDs, compliance review state and real-vs-demo event status.

## Commands and release criteria
Run in CI and report actual outputs:
```bash
cd backend && python -m pytest -q
cd ../frontend && npm ci && npm run build
```
Also run migration upgrade from an empty database and from the prior schema; verify rollback/backup strategy. Add a full API integration test with temporary storage/database and mocked threat-intel/email/webhook/LLM providers. Release only if no tenant-isolation failures, all migrations apply, backend suite passes, frontend build succeeds and test documentation reflects the current result.
