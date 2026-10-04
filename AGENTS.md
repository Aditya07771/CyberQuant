# Agent Instructions

## Mission
Implement the integrated CyberQuant platform defined in `AGENT.md`, `PROMPT.md`, and `docs/`. Treat the checked-in application as the starting point, not as proof that every described feature is complete. Make code changes, tests, and migrations; do not stop after producing a plan or scaffolding.

## Read first
1. `AGENT.md` — implementation contract and repository-specific facts.
2. `docs/IMPLEMENTATION_PLAN.md` — required order of work.
3. `docs/API_SPEC.md` and `docs/DATA_MODEL.md` — contracts.
4. `docs/RISK_MODEL.md` and `docs/SECURITY_COMPLIANCE.md` — calculation and safety rules.
5. `docs/ACCEPTANCE_TESTS.md` — definition of done.

## Non-negotiable engineering rules
- Preserve the existing React dashboard, five-table dataset workflow, asset/business-unit/organization risk views, Monte Carlo analysis, control ROI/optimization, framework mapping, dependency graph, chat, and trend/forecast modules. Refactor behind stable interfaces instead of duplicating them.
- Use **one authoritative risk pipeline**. Integrate scanner import, threat intelligence, regulatory assessments, and alerts into the existing per-asset pipeline; do not add a disconnected second Monte Carlo engine.
- All data and outputs must be scoped to an authenticated organization and dataset. Never read/write shared global outputs for user requests. Derive paths from authorized database records, never from a user-supplied filesystem path.
- Never claim a feature is implemented because a README describes it. Verify source code, route behavior, and tests.
- Treat simulator data, inferred graph edges, heuristic values, legal scenarios, and ML predictions as such. Label synthetic, stale, approximate, uncalibrated, or human-review-required results clearly.
- Do not invent statutory requirements, fines, deadlines, exploit probabilities, benchmark values, or model performance. Store source/version/date for external facts and assumptions.
- Avoid silent fallback to zero risk. Missing/stale inputs must produce an explicit status, uncertainty or safe error.
- Use type hints, Pydantic request/response models, structured logging, bounded external calls, explicit error handling, database migrations, and focused tests.
- Never commit credentials, live tokens, real `.env` files, private data, or generated customer data. Rotate/remove any exposed secret; provide a tracked `.env.example` with placeholders only. The current `.gitignore` explicitly excludes `backend/.env.example`; fix that exception while keeping `backend/.env` ignored.
- Keep API and UI changes synchronized. Update frontend API calls when canonical routes change.

## Required workflow
1. Inspect imports, configuration, route contracts, data flow and existing tests before editing.
2. Run the baseline tests/build; record environment blockers without misrepresenting them as code failures.
3. Implement in the phase order in `docs/IMPLEMENTATION_PLAN.md`.
4. Add regression tests with every behavior change. Prefer small deterministic fixtures and seeded simulations.
5. Run backend tests, frontend build, and the security/data-isolation tests. Fix failures caused by changes.
6. Update docs and report changed files, commands, results, known limitations and migrations.

## Definition of done
The acceptance criteria in `docs/ACCEPTANCE_TESTS.md` pass, the new canonical `/api/v1` routes are used by the frontend, dataset ownership is enforced end-to-end, and there is no path that returns another tenant's data or reports mock delivery as real delivery.
