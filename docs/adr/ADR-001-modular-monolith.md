# ADR-001: Use a Modular Monolith for the MVP

- Status: Accepted
- Date: 2026-09-13

## Context

The MVP needs data ingestion, restaurant queries, deterministic ranking, LLM integration, and a web UI. The current repository has no established application runtime or operational platform. The expected workload is read-heavy and does not yet justify independently deployed services.

## Decision

Build one stateless FastAPI backend deployment with explicit internal modules for API routes, domain policies, recommendations, repositories, and LLM adapters. Build the React/Vite web client separately and run ingestion as an offline command/job that shares canonical schema code with the backend.

Use SQLite locally. Use PostgreSQL for a production deployment when concurrency and operational requirements justify it. Keep data-access interfaces storage-independent.

For local development, allow only `http://localhost:5173` and `http://127.0.0.1:5173` as browser origins. Production uses explicit HTTPS origins from environment configuration; wildcard CORS is forbidden.

End-user authentication is excluded from the MVP because the product stores no user accounts or histories. Public endpoints still require validation, body limits, and rate limiting. Dataset ingestion is a controlled job, not a public endpoint.

## Consequences

- Development and deployment remain simple.
- Transactions and request tracing are easier than with multiple services.
- Module boundaries must be enforced in code and tests to avoid a tightly coupled codebase.
- Individual modules can be extracted later if measured scale or ownership requires it.

## Alternatives Considered

- Microservices: rejected for MVP operational overhead.
- Serverless functions only: rejected because ingestion, database connections, and predictable local development need more explicit runtime control.
- Single frontend-only application: rejected because credentials, database access, validation, and LLM calls must remain server-side.
