# ADR-003: Use Versioned Offline Dataset Ingestion

- Status: Accepted
- Date: 2026-09-13

## Context

The source contains 51,717 rows, duplicate listing contexts, missing values, textual ratings/costs, and very large review fields. Loading or cleaning it during user requests would be slow, inconsistent, and difficult to audit.

## Decision

Download a pinned source revision in an offline job. Profile, map, normalize, validate, deduplicate, and write a canonical Parquet snapshot plus manifest. Load the serving database transactionally and activate a new version only after quality gates and indexes succeed.

Retain the previous successful version for rollback. Recommendation requests bind to one active dataset version. Failed ingestion never changes the active version.

The initial pinned source commit is `5738e9eda2fad49ad51c6e0ed26e761d9b947133`.

## Consequences

- Requests are fast and operate on predictable canonical data.
- Data changes are traceable and reversible.
- Storage is required for staged/current/previous artifacts.
- Refreshes are not real-time and must disclose dataset freshness.
- Production use remains blocked until source licensing is clarified.

## Alternatives Considered

- Query Hugging Face on every request: rejected for latency and availability coupling.
- Mutate the active database in place: rejected because partial failures could expose mixed data.
- Commit the raw dataset to the repository: rejected because of size, lineage, and redistribution concerns.
