# Phase 7 Release Checklist

## Release-candidate automation

- [x] Locked Python and Node dependencies.
- [x] Native release builder runs lint, formatting, types, tests, and optimized web build.
- [x] Runtime liveness/readiness and Prometheus telemetry.
- [x] Separate safe staging/production configuration examples.
- [x] HTTPS/static hosting example and single-writer native topology.
- [x] Integrity-checked SQLite backup and guarded restore.
- [x] Dataset quality gate and transactional activation.
- [x] Operations, failure, evaluation, cost, and rollback runbooks.
- [x] CI release-candidate checks and an approval-gated promotion record.

## Required before public production launch

- [ ] Obtain and record dataset redistribution/production-use permission, or replace the source.
- [ ] Select a host, domain, HTTPS endpoint, monitoring destination, and secret manager.
- [ ] Install the release as managed Caddy and API services with a least-privilege service account.
- [ ] Perform staging backup/restore plus application rollback rehearsal on that target.
- [ ] Complete human NVDA or Narrator acceptance of the primary workflow.
- [ ] Run production liveness/readiness, representative searches, AI and forced-fallback checks.
- [ ] Verify production logs, metrics, dashboard, and alert delivery.
- [ ] Record application, dataset, migration, prompt, schema, and model versions.
- [ ] Obtain product, engineering, data, security, and accessibility sign-off.

Phase 7 is therefore active and release-candidate-ready, but not publicly deployed or signed off.
