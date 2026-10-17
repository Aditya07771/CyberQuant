# Required Implementation Plan

All phases are in scope. Complete them in order and keep each phase runnable/testable.

## Phase 0 — Baseline and configuration
- Inventory routes, dependencies, frontend API calls, model assumptions and test behavior. Run baseline backend tests and `npm run build`; record environmental blockers.
- Add tracked placeholder-only `backend/.env.example`, settings validation and environment-specific data/output roots. Fix `.gitignore` (it currently excludes `backend/.env.example`) so the template is tracked while `backend/.env` remains ignored. Ignore real secrets, uploaded customer files, test DBs and generated outputs.
- Add structured error responses, request IDs, UTC timestamps, logging redaction and health/readiness checks.

## Phase 1 — Identity, persistence and tenant isolation
- Add SQLAlchemy 2.x models and Alembic migrations for organizations, users, memberships/roles, refresh sessions, datasets/versions, source artifacts, jobs, runs, alerts and audit events. Keep business result tables/Parquet artifacts linked to dataset/run IDs.
- Add password hashing (Argon2id), short-lived access tokens, rotating/revocable refresh tokens, logout, role checks and organization scoping. Never trust a `user_id`, `org_id`, `dataset_id` or path supplied without checking database ownership.
- Roles: `owner`, `admin`, `analyst`, `viewer`. Owner/admin manage members and policy; analysts upload/run/triage; viewers read only. Enforce authorization in services/dependencies, not only the UI.
- Create output structure under an app-controlled path such as `outputs/{org_uuid}/{dataset_uuid}/{run_uuid}/`. Store the resolved relative artifact key in DB. All API queries must load artifacts by an authorized run, never by a global filename.
- Change current global-output tests/handlers and `DatasetContext`/API client to use the selected authorized dataset. Add cross-tenant denial tests before continuing.

## Phase 2 — Dataset contracts and durable jobs
- Preserve five-table uploads (CSV files, ZIP, JSON, Excel) and validation; create Dataset, DatasetVersion and IngestionJob rows. Validate table columns, dtypes, nonnegative money, FK integrity, duplicate IDs, dates, bounded scores and allowed control ranges.
- Harden ZIP handling against traversal, nested archive abuse, duplicate names, oversized entries and compression bombs; enforce total upload/request limits; sanitize logs/errors; do not trust the client's MIME type.
- Introduce Redis + RQ jobs for data ingestion, scanner import, threat-intelligence enrichment, simulations, ML training and forecast runs. API returns `202 Accepted` with `job_id`; expose status/result endpoints; support failure details safe for users and retry/idempotency keys.
- Keep built-in demo mode as a separate labeled dataset, not a shared output path. Never overwrite canonical seed files with user uploads.

## Phase 3 — Scanner import and threat intelligence
- Implement versioned parsers for OpenVAS XML, Nessus JSON and AppSec CSV under `backend/risk_engine/scanners/`. Use safe XML parsing (e.g. `defusedxml`); parse schema variants explicitly and preserve original source finding IDs/payload references.
- Normalize CVE, CVSS version/vector/score, product/package, port/protocol, host identifiers, discovery/observed timestamps, severity, status and evidence location. Match known assets by stable identifiers; leave unmatched assets unresolved for review. Do not merge assets on IP alone.
- Implement `backend/integrations/threat_intel/epss_client.py`, `kev_client.py`, cache/storage services and feed health. EPSS API is for single/small-batch lookups; use its daily dataset for bulk sync. KEV uses the official CISA catalogue. Bound timeouts/retries, validate source schemas and record `fetched_at`, source date/version and staleness.
- Each `RiskRun` freezes the threat-intelligence snapshot used. If enrichment is unavailable, mark the affected fields and uncertainty explicitly; apply a documented policy instead of assigning 0.

## Phase 4 — Calibrated quantitative model
- Keep `LikelihoodModel`, `FrequencyModel`, `LossMagnitudeModel`, `MonteCarloSimulator` and `RiskAggregator` as the only source of risk numbers. Add schema/config version to every result.
- Separate exploitation probability, technical severity/impact, successful loss-event probability, event frequency and loss magnitude. Do not multiply CVSS into probability as though severity were probability. Use EPSS with an explicitly documented horizon; annualize only under documented assumptions and test boundaries.
- Replace additive-capped control stacking with calibrated, overlapping-effectiveness handling. Controls must reduce the relevant event probability or impact but must not make risk exactly zero just because percentages sum to 100%. Distinguish preventive, detective, response and recovery controls where data allows.
- Model primary losses (downtime, IR, recovery) and conditional secondary losses (data/notification, legal, regulatory, contractual, reputation) as separate components. Prevent double counting. Fit distributions from defined quantiles/most-likely values with consistent quantile semantics; document source and confidence for each assumption.
- Simulate portfolio loss by summing per-iteration asset losses under explicit dependence/common-event scenarios. Compute portfolio VaR/ES from portfolio samples; never sum asset VaRs and label the result portfolio VaR. Preserve an independent-assets baseline and disclose correlation assumptions.
- Output EAL, VaR95/VaR99, ES/CVaR95/99, LEC, component decomposition, model confidence and uncertainty labels. Use reproducible seeds and numerical property tests.

## Phase 5 — Regulatory exposure and evidence
- Add `backend/risk_engine/regulatory/` with a versioned rules registry. Each provision has source URL, jurisdiction, rule citation, effective interval, applicability tests, required evidence, known statutory range/cap where verified, review date and reviewer status.
- Model `control_gap`, `potential_exposure_scenario`, `deadline/obligation`, and `reviewed_assessment` as different statuses. A CVE alone cannot imply personal-data breach, reportable incident, or confirmed statutory violation.
- Verify current requirements against primary government sources before shipping rules. Handle effective dates, amendments and sector-specific applicability. Unverified rules cannot create numeric fines; show `needs_review` and source links instead.
- Keep the old backend's concept of regulatory exposure, not its arbitrary percentage-of-revenue or heuristic floor formulas. Never represent a statutory maximum as the likely fine.

## Phase 6 — Alerting and remediation workflow
- Add persistent `RiskAlert`, `AlertDelivery`, and `RemediationTask` services. Evaluate versioned organization policies after a run or new evidence: KEV + exposed critical assets, risk appetite (EAL/VaR/ES), remediation SLA, approved compliance deadline and feed/model health.
- Deduplicate by organization + policy + asset/finding or incident + relevant time window; reopen/escalate on material change. Store evidence/run/policy refs, severity, owner, due time, status and timestamps.
- Reuse the old email service's HTML/plain-text report format but add SMTP provider configuration and delivery state, bounded retries, sanitized errors, idempotent delivery jobs and mock-vs-real distinction. Add HMAC-signed webhooks with timestamp and replay protection.
- Support acknowledge, assign, escalate, resolve and close workflows with audit events. Delivery success means provider acceptance, not that an end user read the message.

## Phase 7 — Optimizer, analytics, ML and dashboard
- Update control scenarios/ILP to use marginal portfolio risk reduction from the corrected model, costs, dependencies, policy constraints and budget. Keep greedy baseline comparison. Explain selected/rejected controls, cost, estimated risk change, assumptions and residual risk.
- Keep existing trends, predictors, LSTM forecast and dependency graph, but add data-quality/sufficiency status, model version, time-aware holdout evaluation, baselines, calibration and explicit inferred-vs-observed graph edges. ML is decision support, not a substitute for risk calculation.
- Update chat so context and optimizer use only the authorized dataset/run. Treat LLM output as an explanation of calculated data, never as the source of financial/legal values. Don't send sensitive raw artifacts to an LLM unnecessarily.
- Replace synthetic live feed as production default with event ingestion; retain explicit demo/simulation mode with a visible label. Scope WebSocket subscriptions to authorized dataset/org.
- Update React routes and API client to versioned endpoints, auth refresh, dataset selection, job polling, scan status, risk evidence, feed freshness, regulatory review state and alert lifecycle.

## Phase 8 — Release gate
- Complete `docs/ACCEPTANCE_TESTS.md`, database upgrade/rollback checks, frontend production build and API contract checks. Test fresh install from `.env.example` with no external tokens using deterministic mocked providers.
- Add API OpenAPI tags, example payloads, migration/run instructions, worker start command and deployment notes. Report actual test results, not intended results.
