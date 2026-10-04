# Antigravity Master Prompt

You are the implementation agent for this CyberQuant repository. **Implement the target, do not merely analyze it.** Read `AGENTS.md`, `AGENT.md`, `SKILLS.md`, and all `docs/*.md` first. Treat them as the requirements contract.

## Goal
Integrate the old risk engine's valuable capabilities—scanner parsing, EPSS/KEV enrichment, primary/secondary financial losses, regulatory exposure scenarios and operational alerting—into the existing CyberQuant app. Preserve its current asset-level risk, portfolio aggregation, Monte Carlo, ROSI, ILP optimizer, compliance mappings, trends, forecasts, dependency graph, chat and React dashboard. There must be one authoritative risk pipeline.

## Hard constraints
- The supplied code currently has no auth routes and uses shared global output paths. Implement organization-aware auth and tenant-scoped dataset/run storage before exposing any new imported or calculated data.
- No anonymous endpoint may read/write a tenant's datasets, files, Parquet/JSON outputs, forecasts, chat context, risk runs, or alerts.
- All proposed endpoints and entity rules in `docs/API_SPEC.md` and `docs/DATA_MODEL.md` are required. Migrate the frontend to them. If a legacy endpoint remains, make it an authenticated, scoped compatibility adapter.
- Use SQLAlchemy 2.x + Alembic, PostgreSQL for deployment, SQLite for tests/dev, Redis + RQ for durable long-running jobs, and the existing FastAPI/React stack.
- Parse OpenVAS XML safely, Nessus JSON and AppSec CSV. Never trust filenames, archive paths or uploaded content. Store originals with hashes and immutable references.
- Add FIRST EPSS and CISA KEV clients, cache data and record the exact versions/timestamps used in each run. An unavailable feed is `stale`/`unavailable`, never silently a zero or low risk.
- Correct and document risk assumptions in `docs/RISK_MODEL.md`: do not conflate CVSS severity with exploit probability, do not assume controls eliminate risk, do not sum per-asset VaRs as portfolio VaR, and reconcile distribution quantile definitions.
- Implement Indian regulatory exposure as provision-versioned, source-linked, effective-date-aware scenarios with evidence and human review. Do not invent fine amounts or claim a CVE proves a violation.
- Alerts must persist policy, evidence, severity, owner, SLA, dedupe key, delivery attempts and actual delivery state. Mock events/email are clearly labeled simulated.
- Keep ML as decision support. Provide baselines, time-aware evaluation, calibration and insufficient-data states; inferred graph edges and synthetic events must be labeled.
- Never commit secrets. Add a tracked placeholder-only `backend/.env.example`, fix `.gitignore` so the template is tracked while `backend/.env` remains ignored, and remove/rotate any tracked real secret if present; do not print secret values.

## How to execute
1. Inspect the code and existing tests; run baseline tests/build, record blockers.
2. Implement phases in `docs/IMPLEMENTATION_PLAN.md` in order; do not stop at stubs or leave route handlers as TODOs.
3. Add migrations, backend services, Pydantic schemas, routes, frontend integration and tests together.
4. Run backend tests and frontend production build after each major phase. Mock external providers in CI; retain opt-in live integration checks.
5. Finish with all criteria in `docs/ACCEPTANCE_TESTS.md`, or report exact unavoidable blockers with evidence. Do not claim a test passed if it was not executed.

Deliver working code, not a design-only response. Report changed modules, migrations, commands and outputs, required environment variables, and any remaining failure precisely.
