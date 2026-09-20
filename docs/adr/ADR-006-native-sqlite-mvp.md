# ADR-006: Native SQLite for the MVP Release Candidate

- Status: accepted
- Date: 2026-09-19

## Decision

The approved non-container MVP uses SQLite for development, staging rehearsal, and deployment.
PostgreSQL is not a release dependency for this traffic profile. A move to PostgreSQL requires a
measured concurrency or availability need, a target managed service, a PostgreSQL repository
implementation, migration tests, production-volume query-plan evidence, and publication/rollback
rehearsal before promotion.

## Evidence

The Phase 6 benchmark used the 12,372-row snapshot. Candidate-query p95 was 7.066 ms,
deterministic recommendation p95 was 7.551 ms, and a 200-request/concurrency-10 run had no
failures. SQLite connections are operation-scoped, use a bounded busy timeout, and close during
shutdown. Metadata is cached by dataset version.

## Consequences

- P6.4's PostgreSQL execution checks are not applicable to this native MVP; they are deferred,
  not reported as PostgreSQL validation.
- `scripts/sqlite_maintenance.py` provides integrity-checked backup and guarded restore.
- A single writable API instance owns the SQLite database. Horizontal API writers or multi-node
  dataset publication are unsupported and trigger reevaluation of this decision.
- The dataset license remains a separate blocker for public production distribution.
