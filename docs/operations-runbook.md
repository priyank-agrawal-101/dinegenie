# DineGenie Native Operations Runbook

## Deployment shape

Caddy terminates HTTPS and serves the immutable Vite build. It proxies `/api`, `/health`, and
`/metrics` to one FastAPI worker on loopback. A service manager runs `scripts/start_native.ps1`.
One API writer owns the SQLite database; do not start multiple writers or place the database on a
network share.

## Configuration and secrets

Copy `.env.staging.example` or `.env.production.example` outside the release directory and replace
the example hostnames. Inject `APP_GROQ_API_KEY` from the host secret store at process start. Never
put secrets in `VITE_*`, source control, build arguments, or normal logs. Development, staging,
and production use separate databases, origins, metrics files, keys, and data directories.

## Dataset refresh and rollback

1. Back up the current database with
   `python scripts/sqlite_maintenance.py backup runtime-data/production/restaurants.db backups/restaurants-YYYYMMDD.db`.
2. Run ingestion into a staging runtime root and inspect its manifest, profile, quarantine counts,
   and quality metrics.
3. Stop the API writer, copy the validated database into the production runtime directory, and
   restart. Confirm readiness and active version before enabling traffic.
4. To recover, stop the writer and run `python scripts/sqlite_maintenance.py restore <backup> <database> --confirm`.
   Restore always keeps a timestamped safety copy of the displaced database.

## Application release and rollback

Run `scripts/build_release.ps1`; retain its ZIP, `SHA256SUMS`, previous release directory, database
backup, and environment configuration. On a clean Windows host, extract into a new versioned
directory and run `powershell -ExecutionPolicy Bypass -File scripts/install_native.ps1` to create
the local virtual environment from the locked requirements. Repoint the service and Caddy web
root, restart, then run the release checks. Rollback repoints both to the previous release and
restores the paired dataset only if its schema/data version requires it.

## Health, metrics, and incidents

- `/health/live`: process only; use for restarts.
- `/health/ready`: database and active dataset; use for traffic admission.
- `/metrics`: restrict to the monitoring network.
- Database/dataset failures: keep traffic off, validate the file and active manifest, restore the
  last verified backup, then recheck readiness.
- Groq timeout/rate limit/outage: deterministic fallback is expected. Investigate fallback rate,
  circuit state, account quotas, and latency before changing concurrency or rate limits.
- API error spike: correlate by request ID without logging preference text; roll back if tied to a
  release.

Use `ops/observability/prometheus.yml`, `prometheus-alerts.yml`, and the Grafana dashboard. Cost is
computed from usage and configured per-million-token prices; update both prices whenever the model
changes. Run the versioned evaluation suite after any prompt, schema, model, ranking, or dataset
change and retain its report with the release.

## Product limitations

The snapshot is not live restaurant availability. Unsupported preferences remain explicitly
unverified. The source dataset's unspecified license blocks public distribution until written
authorization or a replacement licensed source is recorded.
