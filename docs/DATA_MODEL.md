# Data Model and Storage Contract

Use SQLAlchemy 2.x models + Alembic migrations. PostgreSQL is the deployment system of record; SQLite is supported for local/tests. Every tenant-owned row has `organization_id` or a validated FK path to a tenant-owned parent. Enforce ownership in queries and service methods, not just request schemas.

## Core entities

| Entity | Required fields / invariants |
|---|---|
| `Organization` | UUID, name, default currency, risk appetite thresholds, created/updated timestamps, policy version. |
| `User` | UUID, normalized unique email, Argon2id password hash, active/locked state, timestamps; never store raw passwords. |
| `Membership` | organization/user FKs, role (`owner`, `admin`, `analyst`, `viewer`), unique pair. |
| `RefreshSession` | user/org, hashed refresh token/JTI, expiry, rotated-from/revoked timestamps, device metadata; raw token not stored. |
| `Dataset` | UUID, organization, name, owner, active version, type (`tabular`, `scanner_enriched`, `demo`), status and timestamps. |
| `DatasetVersion` | dataset FK, immutable input schema/version, source checksum, row counts, validation report, currency/time window, created time. |
| `SourceArtifact` | dataset/version, safe storage key, original filename as display-only text, detected format, SHA-256, byte size, uploader, parser version, retention state. |
| `IngestionJob` | dataset/version, task type, idempotency key, state/progress, timestamps, safe error code, retry count. |
| `Asset` | dataset version, stable asset key, hostname/cloud/device identifiers, business unit, criticality 1–5, sensitivity, currency, financial value, downtime/hour cost, OS, exposure and owner. |
| `VulnerabilityFinding` | dataset/version + asset nullable until matched; scanner/source ID, CVE, product/package/version, port/protocol, CVSS version/vector/score, severity, first/last seen, status, evidence ref, parser version, dedupe fingerprint. |
| `ThreatEvent` | dataset/version, asset, observed timestamp, source, event/technique ID, severity, action, downtime, records impacted, source artifact/evidence ref; distinguish simulated from observed. |
| `SecurityControl` | versioned control catalog ID, name/category, cost + currency, candidate effectiveness assumptions by threat/loss component, dependency requirements, evidence/source and validity dates. |
| `AssetControl` | asset/control FKs, deployment status/date, effectiveness evidence, expiry/review time; enforce unique current mapping. |
| `ThreatIntelSnapshot` | CVE, source (`epss`/`cisa_kev`/other), score/percentile or KEV fields, source publication date/version, fetched timestamp, response hash, status/freshness. |
| `RiskRun` | dataset/version, organization, config/model/code version, RNG seed, threat-intel snapshot refs, state, started/finished times, input hash, summary metrics and error code. Immutable after completion except status/audit metadata. |
| `AssetRiskResult` | run + asset, EAL, VaR95/99, ES95/99, loss components, sample count, confidence/data-quality status and driver evidence. |
| `PortfolioRiskResult` | run, portfolio loss distribution artifact key, EAL/VaR/ES/LEC, dependence assumptions, currency and summary. Portfolio quantiles derive from portfolio samples. |
| `ControlScenario` | run, asset/control candidate, cost, before/after EAL and tail risk, marginal reduction, ROSI, assumptions and selection reason. |
| `RegulatoryRule` | jurisdiction, instrument/provision ID, applicability logic/version, effective interval, source URL, verified citation, rule owner/reviewer, review time; no unsourced numeric fine values. |
| `RegulatoryAssessment` | dataset/run, rule version, state (`gap`, `potential_exposure`, `needs_review`, `reviewed`, `not_applicable`), evidence refs, scenario range, deadline, rationale, reviewer/approval timestamps. |
| `RiskAlert` | organization/dataset/run, policy version, severity, category, dedupe key, evidence refs, owner, status, opened/updated/due/closed times. |
| `AlertDelivery` | alert, channel, recipient group, state (`queued`, `sent`, `failed`, `simulated`), attempts, timestamps, provider reference and sanitized error. |
| `RemediationTask` | alert/finding/control refs, owner, priority, due date/SLA, status, action notes, verification evidence and completion time. |
| `AuditEvent` | organization, actor/system identity, action/resource, timestamp, request ID, before/after-safe metadata, source IP where policy allows; append-only. |

## Relationships and constraints
- Organization → memberships, datasets, policies, alerts, audit events. User access to a dataset always resolves through organization membership and role.
- Dataset → immutable DatasetVersions → SourceArtifacts, Jobs, Scans/Findings and RiskRuns. Risk results belong to exactly one completed run and a known dataset version.
- Asset and vulnerability IDs are stable within a dataset version; preserve source IDs and observation history. No silent merge on IP address alone.
- Store money with currency code and `Decimal`/integer minor units in durable records. Simulation arrays may use float64; conversion and rounding rules are explicit. Never mix USD/INR in a calculation.
- Store Parquet/JSON as rebuildable artifacts under generated organization/dataset/run UUID directories. Database metadata is authoritative. Persist artifact checksums, schema version, and retain only keys generated by the server.
- Keep completed risk runs immutable so a historical metric can be reproduced from its input version, model/config version, seed, and threat-intel snapshots.
- Index tenant scope and query keys: `(organization_id, dataset_id)`, `(dataset_id, version_id)`, `cve_id`, `asset_id`, `run_id`, `alert status/severity`, observed time and dedupe key.

## Migration and data retention
- Introduce schema migrations; never mutate the schema only at import/startup.
- Existing CSVs and output files are demo/bootstrap assets. Import them into a named demo dataset, create its version/run records, and do not use the checked-in global output directory for live tenant requests.
- Uploaded source artifacts and audit/alert history need configurable retention. Delete through an audited lifecycle workflow; don't delete evidence still referenced by a run or assessment.
