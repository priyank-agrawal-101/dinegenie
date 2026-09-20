# Phase 6.2 Observability

Validation date: 2026-09-19

## Outcome

P6.2 is implemented and approved. The API exposes Prometheus-compatible metrics at `/metrics`,
the offline ingestion command publishes atomic textfile metrics, and checked-in Grafana and
Prometheus alert definitions distinguish API, database, model, and data failures.

The implementation remains native and does not require Docker. Prometheus and Grafana are optional
operations services; the application itself continues to run with Python and Node.js.

## Signals

| Concern | Signal |
|---|---|
| Request volume and errors | `restaurant_http_requests_total` |
| Endpoint latency | `restaurant_http_request_duration_seconds` |
| Stable application errors and no matches | `restaurant_application_errors_total` |
| Deterministic, assisted, and fallback usage | `restaurant_recommendation_requests_total` |
| Provider outcomes | `restaurant_model_requests_total` |
| Invalid model output | `restaurant_model_validation_failures_total` |
| Token usage | `restaurant_model_tokens_total` |
| Estimated model cost | `restaurant_model_estimated_cost_usd_total` |
| Database and active-dataset readiness | `restaurant_readiness_status` |
| Ingestion freshness | `restaurant_ingestion_last_success_timestamp_seconds` |
| Accepted, rejected, and raw rows | `restaurant_ingestion_rows` |
| Ingestion rejection rate | `restaurant_ingestion_rejection_ratio` |

Recommendation telemetry is tagged with controlled dataset, prompt, and configured model versions.
HTTP metrics map paths to a fixed route vocabulary. User locations, preferences, request IDs,
restaurant IDs, arbitrary URLs, and exception messages are not metric labels.

## Native operation

Start the API normally, then inspect the scrape endpoint:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/metrics | Select-Object -ExpandProperty Content
```

The ingestion CLI writes `runtime-data/metrics/ingestion.prom` after a successful publication:

```powershell
.\.venv\Scripts\python.exe -m pipelines.cli --mode fixture
```

The API appends that bounded textfile to `/metrics`. If the API runs from another working
directory, set `APP_INGESTION_METRICS_FILE` to the file's absolute path.

For production, expose `/metrics` only to the internal monitoring network. Use
[prometheus.yml](../ops/observability/prometheus.yml), load
[prometheus-alerts.yml](../ops/observability/prometheus-alerts.yml), and import
[grafana-dashboard.json](../ops/observability/grafana-dashboard.json).

## Alert runbooks

### RestaurantApiReadinessDown

Check `/health/ready`, database reachability, and whether `dataset_state` has an active version.
Restore database access or reactivate the last verified dataset. Do not restart repeatedly when the
dataset itself is absent.

### RestaurantApiHighErrorRate

Split failures by route and stable application error code, correlate affected requests using the
JSON log `request_id`, and inspect the first exception without copying credentials or request bodies.
Rollback the latest application change if the increase aligns with a release.

### RestaurantModelProviderFailures

Break down `restaurant_model_requests_total` by outcome and configured model version. Confirm Groq
status, account limits, model availability, and circuit-breaker behavior. Deterministic fallback
should remain healthy; disable LLM mode if failures are sustained.

### RestaurantFallbackRateHigh

Confirm database recommendations remain successful, then inspect model outcomes, latency, invalid
output categories, and Groq rate limits. Avoid increasing retries because that can amplify cost and
provider pressure.

### RestaurantIngestionStale

Check the ingestion scheduler and the timestamp of `runtime-data/metrics/ingestion.prom`. Run the
pinned ingestion manually, review its quality report, and activate output only after all gates pass.

### RestaurantIngestionRejectionRateHigh

Compare the new source schema and rejection reasons with the pinned mapping. Do not relax quality
gates merely to clear the alert; correct the mapping or reject the source revision.

## Validation evidence

```powershell
.\.venv\Scripts\ruff.exe check apps/api pipelines
.\.venv\Scripts\mypy.exe apps/api pipelines
.\.venv\Scripts\pytest.exe -q
```

Results:

- Ruff: passed.
- Mypy strict mode: passed for 61 source files.
- Pytest: 121 passed.
- Grafana dashboard JSON and Prometheus alert YAML parsed successfully.
- Tests exercised readiness, validation errors, no matches, deterministic fallback, invalid model
  output, token/cost counters, version labels, ingestion metrics, and sensitive-label exclusions.
