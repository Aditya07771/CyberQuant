# Antigravity Implementation Contract

## Target
Turn this repository into a single, auditable cyber-risk platform that converts security evidence into asset/portfolio financial risk, remediation investment choices, regulatory assessments, and trackable alerts. Implement all requirements in this repository; do not return only recommendations.

## Verified starting state
- Backend: FastAPI in `backend/api/`; quantitative engine in `backend/risk_engine/`; tests in `backend/tests/`.
- Inputs: `assets.csv`, `vulnerabilities.csv`, `threat_events.csv`, `controls.csv`, and `asset_controls.csv`; upload supports CSV bundles, ZIP, JSON and Excel.
- Outputs are currently written/read under a shared `backend/outputs/` path. This is **not safe for multi-user operation** and must become organization/dataset/run scoped.
- Current source has no registration/login/token routes or auth middleware. Do not assume user/session isolation exists. Implement it.
- `backend/api/live_feed.py` produces synthetic events. Retain only as clearly labelled demo mode; production event paths must be evidence-backed.
- `backend/risk_engine/` already provides ingestion, likelihood, frequency, loss magnitude, Monte Carlo simulation, aggregation, controls/ROSI, optimization, compliance mapping, prediction, trend, forecasting and dependency graph modules. Extend these; do not duplicate them.
- `risk_engine/pipeline.py` produces Parquet/JSON results and models are partly heuristic. The regulatory module from the earlier `risk_engine.rar` is not in this repository; implement a new evidence/version-based assessment service rather than copying unvalidated fine formulas.
- `backend/requirements.txt` lists the main runtime dependencies including PuLP. Install declared dependencies before judging related tests.

## Required end state
1. Secure authentication, organization membership and role-based authorization.
2. Durable dataset/version/job/run records and strict tenant isolation for every API, output, uploaded file, chat context, live feed, alert and background task.
3. Native OpenVAS XML, Nessus JSON and AppSec CSV imports normalized to existing asset/vulnerability records.
4. Cached/timestamped FIRST EPSS and CISA KEV enrichment, with stale/unavailable status and bounded retries.
5. One calibrated risk pipeline with separated frequency, success likelihood, primary loss, secondary loss, uncertainty, asset results and a jointly simulated portfolio distribution.
6. Versioned, evidence-driven regulatory applicability/exposure assessments. Legal status is always distinguished from confirmed violations and needs human review.
7. Persisted policy alerts with deduplication, ownership, acknowledgement, escalation, delivery attempts and real-vs-mock status.
8. Control optimization based on calibrated marginal risk reduction, costs, dependencies and constraints; keep the existing ILP and greedy baseline.
9. ML/forecast outputs carry data-sufficiency, validation and provenance metadata and do not silently control risk calculations.
10. React dashboard uses canonical authenticated APIs and displays evidence, assumptions, freshness, uncertainty, risk metrics, controls, assessments and alert lifecycle.
11. Database migrations, a tracked placeholder-only `backend/.env.example` (fix `.gitignore` so it is included while `backend/.env` stays ignored), worker/runtime instructions, CI-ready tests and updated operator documentation. Remove/rotate any tracked real secret without printing it.

## Execution rules
- Follow `docs/IMPLEMENTATION_PLAN.md` phase-by-phase. All phases are required; do not ask the user to choose features or leave the work at a scaffold.
- Use `docs/API_SPEC.md`, `docs/DATA_MODEL.md`, and `docs/RISK_MODEL.md` as the implementation contracts. If current behavior conflicts, update code and tests to meet the target contract.
- Prefer PostgreSQL in deployment and SQLite for local/dev tests, using SQLAlchemy 2.x and Alembic migrations. Use a durable background queue (Redis + RQ) for imports and long simulations. Provide clear local run instructions.
- Preserve old unversioned endpoints only as authenticated, tenant-scoped compatibility adapters while the frontend migrates. No anonymous route may read global risk artifacts.
- Official/current legal and threat-intelligence facts must be checked against the primary sources listed in `docs/SECURITY_COMPLIANCE.md`; record source URL, effective dates and review timestamp.
- Do not overclaim results. If a component cannot be verified due to missing service credentials or unavailable external source, implement its interface and deterministic tests, and report the blocker honestly.

## Delivery report
At completion, summarize: architecture changes, migrations, routes added/changed, model changes, frontend updates, commands run and test/build results, configuration required, and anything still blocked. A blocked external provider must not block local tests or demo mode.
