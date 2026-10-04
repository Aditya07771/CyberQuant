# Implementation Skills and Repository Map

Use these local patterns and commands when implementing the plan. Detailed requirements live in `docs/`.

## File map
- `backend/api/main.py`: current risk read endpoints; move to dataset-scoped `/api/v1` routes.
- `backend/api/upload.py`: current CSV/ZIP/JSON/Excel validation and pipeline launch; extract reusable validators and route work through durable jobs.
- `backend/api/chat.py`: LLM-backed risk copilot; bind its context/optimizer calls to the authorized dataset and run.
- `backend/api/live_feed.py`: currently simulated in-memory feed; add explicit `source=demo` and authenticated dataset scoping.
- `backend/risk_engine/ingest.py`: five-table validation and asset risk base.
- `likelihood.py`, `frequency.py`, `loss_magnitude.py`, `simulate.py`, `aggregate.py`: one quantitative engine; protect interfaces and test distributions/calibration.
- `control_scenarios.py`, `investment_optimizer.py`, `frontier.py`: control what-if, ILP/greedy optimizer and frontier.
- `framework_mapper.py`: framework coverage/gaps; retain mappings with provenance/version.
- `predictor.py`, `threat_forecaster.py`, `trend_generator.py`, `dependency_graph.py`, `drivers.py`: analytical features; add confidence/provenance and data-sufficiency.
- `frontend/src/api/client.js`: central API client; add token handling and `/api/v1` paths here rather than scattering URLs.
- `frontend/src/context/DatasetContext.jsx`: active dataset selection; make it backed by authenticated server state.
- `frontend/src/components/`: dashboard, upload, live feed, forecasts, compliance, optimizer and chat UI.

## Current route inventory
See `docs/API_SPEC.md`. Existing risk routes use shared Parquet files; they must not remain anonymously accessible after tenant-scoped storage is added.

## Commands (run from repository root)
```bash
# Backend
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
python -m pytest -q
python -m risk_engine.pipeline
uvicorn api.main:app --reload --app-dir .

# Frontend (new terminal, repository root)
cd frontend
npm ci
npm run build
npm run dev
```
Use a configured test database and temporary data/output roots during tests; do not overwrite the checked-in demo data. For integration tests, start the API with test settings and deterministic external-service mocks.

## Implementation conventions
- Python 3.11+; use Pydantic v2 schemas, SQLAlchemy 2.x, Alembic and repository service layers.
- Keep handlers thin: validate/authenticate → service → durable state → response.
- Use `Decimal` or integer minor units for persisted money; use `float64` in simulations with explicit conversion and currency metadata.
- Every run records config/model versions, random seed, source dataset version, feed snapshots and execution status.
- Use UTC ISO-8601 timestamps; normalize CVEs to uppercase canonical IDs; validate ranges and foreign keys before running a model.
- Use fixture-based parser tests, fixed seeds for simulation tests, fake EPSS/KEV clients, and a temporary database for tenant-isolation tests.
- Use environment variables only for secrets and deployment-specific values. Provide placeholder-only `backend/.env.example`; fail startup in production if secrets are missing/default.
- Use bounded HTTP timeouts/retries, structured logs and stable error response models. Never return stack traces or raw uploaded file contents to clients.
