# dinegenie
AI-Powered Restaurant Recommendation System (Zomato Use Case)

# AI-Powered Restaurant Recommendation System

This repository contains the implementation foundation for a Bengaluru restaurant recommendation application. It combines deterministic filtering and scoring with an optional, grounded LLM reranking layer.

Project specifications:

- [Simplified project document](docs/project-document.md)
- [Problem statement](problemStatement.md)
- [Architecture](architecture.md)
- [Implementation plan](implementation-plan.md)
- [Edge-case catalogue](edge-case.md)
- [Dataset profile](docs/data-profile.md)
- [MVP product rules](docs/product-rules.md)

## Current Status

- Phase 0: complete.
- Phase 1: complete; application foundation and quality gates are in place.
- Phase 2: complete; pinned ingestion, canonical artifacts, and the SQLite serving store are in place.
- Phase 3: complete; deterministic recommendations, metadata APIs, and readiness checks are in place.
- Phase 4: complete; responsive search, recommendations, explicit refinement, and browser accessibility checks are in place. See [validation record](docs/phase-4-validation.md).
- Phase 5: complete; the grounded Groq path, fallback, human review, pricing, and paced three-trial
  live release evaluation passed. See [validation record](docs/phase-5-validation.md).
- Phase 6: complete for the approved native single-instance MVP. See the consolidated
  [validation record](docs/phase-6-validation.md).
- Phase 7: in progress; the native release candidate, local staging rehearsal, CI promotion gate,
  HTTPS example, backup/restore, and operations runbook are ready. External production launch and
  stakeholder sign-off remain pending. See the [release status](docs/phase-7-release-status.md).
- Dataset production use is blocked until the source's unspecified license is clarified.

The existing root `index.html` is unrelated and intentionally preserved. The application web client lives in `apps/web`.

## Architecture at a Glance

```text
Browser -> React web client -> FastAPI -> recommendation modules -> restaurant store
                                              |
                                              +-> optional LLM gateway

Hugging Face source -> offline ingestion -> canonical Parquet -> restaurant store
```

The API applies every hard constraint before any model call. The LLM can only reorder supplied candidate IDs and write grounded explanations. When the model is disabled or unavailable, deterministic results remain available.

## Prerequisites

For native development:

- Python 3.12.x
- Node.js 22.x and npm
- Git

Optional:

- Docker with Docker Compose v2
- PostgreSQL for production-parity work in later phases

## Configuration

Copy `.env.example` to `.env` and adjust values as needed. Defaults run without an LLM credential because `APP_LLM_ENABLED=false`.

Never commit `.env` or API keys.

## Native Backend Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.lock
python -m uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000
```

Verify liveness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
```

Run backend checks:

```powershell
ruff check apps/api pipelines
ruff format --check apps/api pipelines
mypy apps/api pipelines
pytest
```

## Build the Restaurant Store

Run the fast checked-in fixture pipeline without network access:

```powershell
python -m pipelines.cli --mode fixture
```

Build from the pinned public Hugging Face revision (about 574 MB):

```powershell
python -m pipelines.cli --mode huggingface
```

Both commands require no API key. They create an ignored, versioned Parquet snapshot, source
profile, manifest, quarantine report, and queryable `runtime-data/restaurants.db`. Repeated runs
verify and reuse identical source and artifact content.

## Deterministic Recommendation API

After building the restaurant store and starting the API, inspect the contract at
<http://127.0.0.1:8000/docs>. Core endpoints are:

- `POST /api/v1/recommendations`
- `GET /api/v1/metadata/locations`
- `GET /api/v1/metadata/cuisines`
- `GET /api/v1/metadata/budget-bands`
- `GET /health/ready`

Example request:

```json
{
  "location": "Banashankari",
  "budget": {"band": "medium", "currency": "INR"},
  "cuisines": ["Chinese", "Thai"],
  "minimum_rating": 4.0,
  "additional_preferences": "online ordering and family-friendly",
  "limit": 5
}
```

Phases 3 and 4 are fully deterministic and do not use a Groq API key. Live Groq integration starts in Phase 5.

## Optional Groq Ranking (Phase 5)

The server-side gateway is implemented. The default remains `APP_LLM_ENABLED=false`, so the
application works without a key. To try live ranking, privately configure the ignored root
`.env` with `APP_GROQ_API_KEY`, an account-supported `APP_LLM_MODEL`, and then set
`APP_LLM_ENABLED=true` and restart the API. Do not put credentials in `VITE_` settings or chat.

Groq can order only eligible candidates and compose explanations from verified evidence
sentences. Every response is validated before display. Provider failures return the standard
ranked results with `ranking_mode: deterministic_fallback`; readiness remains dataset-based.
The default model deadline is 8 seconds, with at most one shared transient retry/schema repair.

See [.env.example](.env.example) for token, response-format, circuit-breaker, and optional
pricing settings, [ADR-005](docs/adr/ADR-005-grounded-groq-ranking.md) for the grounding policy,
and [evaluation instructions](evals/README.md) for the credential-free and live release checks.
After an initial burst exposed the account's token limit, rate-aware pacing produced 11/11
validated AI-assisted responses in a smoke test. The subsequent three-trial release evaluation
approved `openai/gpt-oss-120b` for this Phase 5 scope with 33/33 eligible requests assisted,
zero fallback, and no safety or relevance regression. Production capacity remains Phase 6 work.

## Native Web Setup

From `apps/web`:

```powershell
npm ci
npm run dev
```

The development site is served at <http://127.0.0.1:5173>. Vite proxies `/api` and `/health` to the backend at <http://127.0.0.1:8000>.

Build the restaurant store before searching, and keep the API running in a separate terminal.
Choose a suggested Bengaluru locality, then set budget, cuisines, minimum rating, optional
preferences, and result count. Custom maximum amounts replace the selected budget band.
No-match suggestions only edit the form; select **Find restaurants** to run the revised search.
Results retain backend order, distinguish matched from unverified preferences, and expose
snapshot details without implying live availability. Form selections stay in memory only.

Run web checks:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npx playwright install chromium
npm run test:e2e
```

`npm run check` combines lint, type checking, component tests, and production build.
Browser tests also require the Python dependencies above. Playwright automatically builds an
isolated fixture store in `runtime-data/phase4-e2e`, starts its API on port **8014**, and serves
the production web build on port **4173**. Both ports must be free; existing services are not
reused. It selects the root `.venv` Python if present, otherwise `python`; set `PYTHON` to
override the executable. The normal restaurant store is not replaced.

The browser suite covers desktop, tablet, and mobile Chromium, the real API search/refinement
journey, injected service failures, keyboard navigation, axe accessibility checks, and narrow
layout/zoom checks. Screenshots are written to the ignored `apps/web/test-results/` directory.

## Operational Metrics

The API exposes Prometheus-compatible operational metrics at <http://127.0.0.1:8000/metrics>.
The ingestion CLI atomically updates `runtime-data/metrics/ingestion.prom`, which the API includes
in that endpoint. Production should restrict this endpoint to its monitoring network.

Native Prometheus alert rules and a Grafana dashboard are in `ops/observability`. Setup and alert
runbooks are documented in [the Phase 6 observability record](docs/phase-6-observability.md).

## Docker Compose

Docker Compose builds the web and API containers without requiring an LLM key:

```powershell
docker compose up --build
```

Open <http://127.0.0.1:5173> and verify API liveness at <http://127.0.0.1:8000/health/live>.

Stop the stack without deleting persisted runtime data:

```powershell
docker compose down
```

Runtime database files are stored in the ignored `runtime-data/` directory.

## Repository Layout

```text
apps/api/           FastAPI application and tests
apps/web/           React/Vite application and tests
data/manifests/     Small dataset lineage manifests
data/samples/       Small test/profile fixtures
docs/               Product, data, and architecture decisions
evals/              Versioned recommendation evaluation cases
migrations/         Versioned serving-store migrations
pipelines/          Offline ingestion, validation, and publication code
runtime-data/       Ignored local generated state
```

## Environment Variables

All backend variables use the `APP_` prefix. Important settings include:

- `APP_ENVIRONMENT`
- `APP_DATABASE_URL`
- `APP_DATABASE_BUSY_TIMEOUT_SECONDS`
- `APP_CORS_ORIGINS`
- `APP_DATASET_REPOSITORY`
- `APP_DATASET_REVISION`
- `APP_LLM_ENABLED`
- `APP_LLM_PROVIDER`
- `APP_LLM_MODEL`
- `APP_GROQ_API_KEY` — first required in Phase 5, immediately before live Groq model calls
- `APP_RECOMMENDATION_TIMEOUT_SECONDS`
- `APP_RECOMMENDATION_CONCURRENCY_LIMIT`
- `APP_LLM_CONCURRENCY_LIMIT`
- `APP_METRICS_ENABLED`
- `APP_INGESTION_METRICS_FILE`

The browser build optionally accepts `VITE_API_BASE_URL`. An empty value uses same-origin paths
and the development/preview proxy. `API_PROXY_TARGET` is a server-side Vite setting for the
proxy destination (default `http://127.0.0.1:8000`); it is not a browser credential. Never put
Groq or other secrets in `VITE_` variables.

## Quality Gates

CI is configured for backend linting, formatting, strict type checking, tests, frontend linting,
TypeScript checks, component tests, production build, and the Chromium browser/accessibility
suite against a fixture API. Pre-commit runs the fast backend and frontend checks when their
corresponding files change. Local validation does not imply a remote CI or Docker run.

`uv.lock` is the complete Python resolution, `requirements.lock` is the hash-pinned production export used by the API container, and `requirements-dev.lock` is the hash-pinned development/CI export.
