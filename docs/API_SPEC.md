# API Contract

All target endpoints below are required. JSON responses use Pydantic models, UTC timestamps, stable error shape `{"error":{"code":"...","message":"...","request_id":"..."}}`, pagination for collections and explicit currency/status fields. Authentication is required except health/readiness and deliberately public registration/login. Enforce tenant access in the service layer.

## Existing routes in the supplied source

| Current route | Current purpose / required migration |
|---|---|
| `GET /`, `GET /health` | Root/docs redirect and basic health. Add `/readyz` for DB/queue dependencies. |
| `GET /risk/assets`, `/risk/assets/{asset_id}`, `/risk/assets/{asset_id}/drivers` | Asset summaries, detail and explainability; migrate to dataset/run-scoped v1 routes. |
| `GET /risk/business-units`, `/risk/organization`, `/risk/portfolio-lec`, `/risk/trend` | Aggregated metrics and trends; use portfolio simulation artifacts from selected run. |
| `GET /controls/scenarios`, `/controls/roi`, `/controls/optimize?budget=...`, `/controls/frontier` | Scenarios, ROI, optimization and frontier; scope by dataset/run and validate USD budget. |
| `GET /compliance/posture`, `/compliance/gaps` | Framework mapping; return mapping version and coverage denominator. |
| `GET /predictions/vulnerabilities`, `/predictions/threat-forecast?horizon_days=14` | ML outputs; include model/data sufficiency metadata. |
| `GET /risk/dependency-graph`, `/risk/dependency-graph/propagate?breached_asset_id=...` | Graph and scenario propagation; label inferred edges. |
| `POST /api/datasets/upload`, `/api/datasets/upload-json`, `/api/datasets/demo`, `GET /api/datasets/status` | Current data upload/demo/status. Refactor to versioned dataset/job endpoints. |
| `POST /chat` | Risk copilot. Bind all context to the authenticated dataset/run. |
| `GET /api/live-feed/recent`, `WS /ws/live-feed` | Recent events/WebSocket. Scope by dataset/org and visibly label synthetic demo events. |

These legacy routes currently use shared output paths and have no auth in the supplied source. Do not expose that behavior after the migration. Keep legacy routes only as authenticated, scoped adapters while the frontend migrates, then remove them or return a documented deprecation response.

## Target routes

### Authentication and organization
- `POST /api/v1/auth/register` — create a user and organization (or require a valid invite according to deployment policy); never allow arbitrary role escalation.
- `POST /api/v1/auth/login` — credentials → short-lived access token and rotating refresh session.
- `POST /api/v1/auth/refresh` — rotate refresh token; detect reuse and revoke the session family.
- `POST /api/v1/auth/logout` — revoke refresh session.
- `GET /api/v1/auth/me` — user, organization memberships and effective roles.
- `GET /api/v1/organizations/current`, `PATCH /api/v1/organizations/current` — read/update organization settings. Restrict risk appetite/currency changes to owner/admin.
- `GET /api/v1/organizations/current/members`, `POST /api/v1/organizations/current/invitations`, `PATCH /api/v1/organizations/current/members/{user_id}` — role-aware member management.

### Datasets and jobs
- `GET /api/v1/datasets` — authorized dataset list.
- `POST /api/v1/datasets` — multipart bundle (five CSVs, ZIP, JSON or Excel); create dataset/version and ingestion job; return `202` with `dataset_id`, `version_id`, `job_id`.
- `GET /api/v1/datasets/{dataset_id}` and `GET /api/v1/datasets/{dataset_id}/status` — metadata, selected version, validation summary and current job state.
- `POST /api/v1/datasets/{dataset_id}/runs` — queue risk calculation for a selected dataset version/config; return `202` with `run_id`/`job_id`.
- `GET /api/v1/datasets/{dataset_id}/runs` and `GET /api/v1/datasets/{dataset_id}/runs/{run_id}` — history/status, model version, input version and metrics-ready state.
- `GET /api/v1/jobs/{job_id}` — queued/running/succeeded/failed, progress, timestamps and safe error summary.
- `POST /api/v1/datasets/{dataset_id}/scans` — upload one OpenVAS XML, Nessus JSON or supported AppSec CSV; queue parse + enrichment; return `202` and `scan_id`/`job_id`.
- `GET /api/v1/datasets/{dataset_id}/scans` and `GET /api/v1/datasets/{dataset_id}/scans/{scan_id}` — scan history and processing status.
- `GET /api/v1/datasets/{dataset_id}/scans/{scan_id}/findings` — normalized findings, asset matching, enrichment/freshness and evidence refs (paginated).
- `POST /api/v1/datasets/{dataset_id}/scans/{scan_id}/asset-mappings` — analyst-approved unresolved finding-to-asset mappings.

### Risk and analytics (all scoped under `/api/v1/datasets/{dataset_id}/runs/{run_id}`)
- `GET .../risk/assets`, `GET .../risk/assets/{asset_id}`, `GET .../risk/assets/{asset_id}/drivers`
- `GET .../risk/business-units`, `GET .../risk/organization`, `GET .../risk/portfolio-lec`, `GET .../risk/trend`
- `GET .../risk/dependency-graph`, `GET .../risk/dependency-graph/propagate?breached_asset_id=...`
- `GET .../predictions/vulnerabilities`, `GET .../predictions/threat-forecast?horizon_days=14`
- `GET .../controls/scenarios`, `GET .../controls/roi`, `POST .../controls/optimize` with body `{ "budget_usd": number, "constraints": {...} }`, `GET .../controls/frontier`
- `GET .../compliance/posture`, `GET .../compliance/gaps`, `GET .../compliance/assessments`

Risk responses must include `currency`, `run_id`, `model_version`, `input_version`, `calculated_at`, `data_quality`, `uncertainty` and relevant source/assumption references. Return 404 for unknown IDs and 403/404 for cross-tenant resource attempts without confirming another tenant's resource existence.

### Threat intelligence, policy and regulatory rules
- `GET /api/v1/threat-intel/status` — feed status, last successful fetch, source version and stale state.
- `POST /api/v1/threat-intel/refresh` — admin-only queue refresh; never block request waiting on the full feed.
- `GET /api/v1/policies/risk`, `PUT /api/v1/policies/risk` — owner/admin versioned thresholds, SLAs, dedupe windows and notification routing.
- `GET /api/v1/regulatory/rules` — applicable versioned rules with source and effective dates.
- `POST /api/v1/datasets/{dataset_id}/regulatory/assessments` — evaluate evidence against rules; return findings as `gap`, `potential_exposure`, `needs_review` or `reviewed`.
- `POST /api/v1/regulatory/assessments/{assessment_id}/review` — authorized reviewer adds decision, evidence, rationale and audit event.

### Alerts, remediation, chat and live feed
- `GET /api/v1/alerts`, `GET /api/v1/alerts/{alert_id}` — filter by status/severity/owner/dataset, paginated.
- `POST /api/v1/alerts/{alert_id}/acknowledge`, `/assign`, `/escalate`, `/resolve`, `/close` — workflow transitions with role checks and audit events.
- `GET /api/v1/alerts/{alert_id}/deliveries` — per-channel attempts and actual state.
- `GET /api/v1/remediation-tasks`, `POST /api/v1/remediation-tasks`, `PATCH /api/v1/remediation-tasks/{task_id}` — owned remediation tracking, due dates and verified completion evidence.
- `POST /api/v1/chat` — body `{dataset_id, run_id, message, history}`; use only authorized computed context and clearly distinguish calculations from explanation.
- `GET /api/v1/live-feed/recent?dataset_id=...`, `WS /api/v1/ws/live-feed?dataset_id=...` — authorized event stream; event records include `source_type` (`observed` or `synthetic_demo`) and timestamp.

## HTTP behavior
- Use `202 Accepted` for queued work, `201 Created` for persisted resources, `204 No Content` for successful logout/deletion where appropriate.
- `400` invalid input, `401` missing/invalid auth, `403` insufficient role, `404` inaccessible/unknown resource, `409` idempotency/state conflict, `413` upload too large, `422` schema/domain failure, `429` rate limit, `503` unavailable required dependency.
- Never return filesystem paths, secret values, raw tracebacks, raw scanner evidence or cross-tenant identifiers. Use stable error codes and request IDs.
