# Phase 7 Release Status

Date: 2026-09-19

## Current outcome

Phase 7 has started. A reproducible native release candidate can be built and operated without
Docker. Version `0.1.0-rc1` passed its local release build and was written as a checksum-protected
ZIP under the ignored `release/` directory. An isolated staging rehearsal returned API readiness
and HTTP 200 from the production web build.

Implemented release assets:

- fail-fast native release builder and versioned ZIP/checksums;
- pinned production/development dependencies;
- environment-separated configuration examples;
- Caddy HTTPS/static-site/reverse-proxy example;
- native API start script with one SQLite writer;
- integrity-checked database backup and guarded restore;
- release-candidate CI with security scans, browser tests, artifact retention, and an environment
  approval gate;
- operations runbook and public-launch checklist.

## Not yet a production deployment

No external host, domain, monitoring destination, or secret manager was supplied, so no external
system was changed. Public deployment is also blocked by the source dataset's unspecified license.
The remaining P7.4 production verification and P7.5 stakeholder sign-offs can only be completed
after those inputs exist. Human screen-reader acceptance is also listed before broad public launch.

The builder prints the release ZIP's SHA-256 after packaging; the value must be copied into the
target environment's release record before promotion.
