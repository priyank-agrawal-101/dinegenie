# Phase 2 Validation Record

- Validation date: 2026-09-17
- Workspace: `E:\Nextleap`
- Pipeline version: `2.0.1`
- Scope: pinned data ingestion, canonical artifacts, and SQLite serving store

## API Key Boundary

Phase 2 used no Groq or other LLM API key. The Hugging Face dataset is public. The first planned
Groq credential use is Phase 5, where `APP_GROQ_API_KEY` and an explicit `APP_LLM_MODEL` will be
required only when `APP_LLM_ENABLED=true`.

## Pinned Source Run

The end-to-end command completed successfully:

```powershell
python -m pipelines.cli --mode huggingface --runtime-root runtime-data\phase2-production
```

| Measurement | Result |
|---|---:|
| Source rows | 51,717 |
| Canonical restaurants | 12,372 |
| Deduplicated rows | 38,854 |
| Rejected rows | 491 |
| Rejection rate | 0.949398% |
| Source size | 574,072,999 bytes |

The accounting identity holds: `12,372 + 38,854 + 491 = 51,717`.

- Pinned revision: `5738e9eda2fad49ad51c6e0ed26e761d9b947133`
- Source SHA-256: `4b0c91c37585310d509873dc399fdf739c7d222fcf7a693e4461b23d25a9d43d`
- Active dataset: `ds_865912f73ef54937cea8`
- Canonical Parquet SHA-256: `b3720c7ac4aad0c9a8dfb9f2328b74c22a2b098f0276ebcb2a26b57ecd6ff297`

A repeat run reported both `cache_reused=true` and `artifact_reused=true` with the same canonical
counts and active version.

## Artifact and Database Checks

- The canonical snapshot, source profiles, quarantine JSONL, and manifest were published through
  an atomic staging-directory rename.
- The active SQLite version contains 12,372 rows.
- The prior successful version remains recorded as `previous_version` for rollback.
- Location/rating, location/cost, and cuisine lookup indexes are present.
- Repository tests confirm exact location filtering, rating/cost constraints, any-cuisine matching,
  stable ordering, metadata lists, and ID lookup.
- A simulated failure immediately before activation rolled back the new version and left the prior
  active version unchanged.

## Automated Results

| Check | Result |
|---|---|
| Ruff lint | Passed |
| Ruff format | Passed |
| Strict MyPy | Passed; API and pipeline code |
| Pytest | 27 passed |
| Fixture ingestion repeated | Same dataset version and Parquet hash |
| Pinned-source ingestion repeated | Download and artifact reused |

Docker was not executed because Docker is not installed on this machine. Phase 2's native pipeline
and database path were exercised directly. The dataset license is still unspecified upstream, so
the existing production-use blocker remains in force.
