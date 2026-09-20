# Phase 3 Validation Record

- Validation date: 2026-09-17
- Workspace: `E:\Nextleap`
- Active dataset: `ds_865912f73ef54937cea8`
- Scope: deterministic recommendation and metadata API

## Implemented Contract

- Strict Pydantic request, result, metadata, budget, and error models.
- Versioned recommendation and metadata routes under `/api/v1`.
- Dataset-versioned metadata caching and version-bound candidate queries.
- Exact normalized locality, inclusive minimum rating, configured budget boundaries, and
  whole-token any-cuisine filtering.
- Deterministic rating, cuisine, budget-fit, and verified-preference feature scores.
- Stable tie-breaking by full score, rating, votes, then restaurant ID.
- Template explanations built only from backend-owned facts.
- Stable `VALIDATION_ERROR`, `NO_MATCHES`, `DATASET_UNAVAILABLE`, `RATE_LIMITED`, and
  `INTERNAL_ERROR` codes.
- Lightweight `/health/ready` check for database access and active dataset state.

The generated FastAPI OpenAPI schema was checked for the versioned paths, strict request schema,
backend-owned result fields, and complete stable error-code enum.

## Full-Dataset Smoke Test

A request for Banashankari, medium budget, Chinese or Thai cuisine, minimum rating 4.0, and five
results returned HTTP 200 with five matching restaurants. Every returned restaurant was in
Banashankari, cost more than INR 600 and no more than INR 1,500 for two, had rating at least 4.0,
and matched Chinese or Thai.

- Candidate count: 6
- Observed in-process request latency: 9.79 ms
- Ranking mode: `deterministic`
- Filters relaxed: none
- Unsupported `family-friendly` preference: explicitly marked unverified
- Groq/API key use: none

Latency is a local single-request observation, not a production benchmark.

## Automated Results

| Check | Result |
|---|---|
| Ruff lint and formatting | Passed |
| Strict MyPy | Passed |
| Pytest | 48 passed |
| Frontend ESLint and TypeScript | Passed |
| Frontend Vitest | 1 passed |
| Frontend production build | Passed |

Tests cover budget boundaries, unknown numeric values, exact hard filters, any-cuisine matching,
score bounds, evidence scoring, stable tie-breaks, deterministic repeat ordering, no-match behavior,
strict validation, request IDs, readiness, temporary SQLite repositories, and OpenAPI compatibility.

Docker was not executed because Docker is unavailable in this environment. Dataset licensing is
still unspecified upstream, so production distribution remains blocked pending clarification.
