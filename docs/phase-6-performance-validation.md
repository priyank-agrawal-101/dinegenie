# Phase 6.3 Performance and Reliability

Validation date: 2026-09-19

## Outcome

P6.3 is implemented and approved for the native SQLite release candidate. The benchmark used an
online SQLite backup of the existing production ingestion database, so the source database was not
modified. The snapshot contained 12,372 restaurants.

All local performance targets passed with substantial margin. These results measure an in-process
ASGI application on the development workstation; networked staging and real Groq latency must be
rechecked during Phase 7 before production release.

## Production-volume results

| Operation | Median | p95 | Target |
|---|---:|---:|---:|
| Cached metadata | 1.520 ms | 2.127 ms | Below 300 ms |
| Candidate query | 5.610 ms | 7.066 ms | Diagnostic |
| Deterministic recommendation | 6.672 ms | 7.551 ms | Below 1,000 ms |
| LLM-assisted with simulated 50 ms provider | 66.663 ms | 80.661 ms | Below 8,000 ms |

Load checks:

- Expected deterministic load: 200 requests, concurrency 10, zero failures, p95 47.730 ms,
  292.45 requests/second.
- Provider-failure load: 50 requests, concurrency 10, zero failures, p95 44.227 ms; every response
  used `deterministic_fallback`.

The simulated LLM benchmark validates application overhead and orchestration, not Groq network
performance or account capacity. It does not send billable model requests.

Machine-readable evidence: [phase6-performance.json](../evals/results/phase6-performance.json).

## Query plans

SQLite used the intended indexes:

- Location and rating filters used `idx_restaurants_location_rating`.
- Cuisine lookup used covering index `idx_restaurant_cuisines_lookup`.

The benchmark fails if either index is not selected.

## Reliability controls

- A 10-second whole-recommendation deadline bounds database plus model orchestration.
- The Groq-specific deadline remains 8 seconds and must be shorter than the whole-request deadline.
- Recommendation execution defaults to 32 concurrent slots with a 250 ms bounded queue wait.
- Groq execution defaults to four concurrent slots with a separate 250 ms queue wait.
- Excess API work receives stable `429 RATE_LIMITED`; whole-request expiry receives stable
  `504 REQUEST_TIMEOUT`.
- Provider-capacity exhaustion falls back deterministically without being counted as a provider
  failure or opening the circuit breaker.
- The Groq HTTP client is reused across requests and closed during application shutdown.
- SQLite connections are operation-scoped, have a five-second busy timeout, and are explicitly
  closed. A SQLite connection pool was intentionally not added because it can amplify write-lock
  contention. PostgreSQL pooling is part of P6.4.
- Metadata cache keys include the active dataset version, operation, normalized query, and limit.
- Application shutdown closes model and repository resources.
- The existing rollback test confirms a failed load leaves the previous dataset active and removes
  partially loaded rows.

## Scaling decisions

Redis is not justified by current measurements. Cached metadata and indexed reads are already well
within targets, and adding Redis would introduce invalidation and operational failure modes without
measured benefit. Reconsider only after staging telemetry shows sustained pressure or cache-sharing
needs across multiple replicas.

## Reproduce

Run the production-volume snapshot benchmark without modifying its source database:

```powershell
.\.venv\Scripts\python.exe -m benchmarks.phase6 `
  --database runtime-data\phase2-production\restaurants.db `
  --iterations 30 `
  --load-requests 200
```

Run all checks:

```powershell
.\.venv\Scripts\ruff.exe check apps/api pipelines benchmarks
.\.venv\Scripts\mypy.exe apps/api pipelines benchmarks
.\.venv\Scripts\pytest.exe -q
```

Results:

- Ruff: passed.
- Mypy strict mode: passed for 65 source files.
- Pytest: 130 passed.
- Dependency lock consistency: passed.

## Phase 7 recheck

From the selected deployment region, repeat endpoint load tests with TLS and network routing. Run a
small rate-limit-safe Groq sample and confirm LLM-assisted p95 remains below eight seconds. Treat the
local simulated-provider number only as the application-overhead baseline.
