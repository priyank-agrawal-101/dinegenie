# ADR-004: Use a Provider-Neutral LLM Gateway

- Status: Accepted
- Date: 2026-09-13
- Revised: 2026-09-17

## Context

The recommendation product requires model-assisted ranking and explanations, but its correctness and availability must not depend on one provider or model. Model behavior, pricing, availability, and account access can change.

## Decision

Define a provider-neutral `RecommendationModel` interface in the backend and provide a fake implementation for tests.

The first production adapter will use Groq, following the product-owner decision recorded on 2026-09-17. `APP_LLM_PROVIDER` defaults to `groq`, and the credential name is `APP_GROQ_API_KEY`.

No LLM key is used during data, deterministic API, or web-MVP work. The concrete Groq model remains deliberately unset until Phase 5, when the current Groq model catalogue, structured-output behavior, context limits, latency, and cost can be evaluated immediately before live integration. Enabling Groq mode requires both an explicit model and a non-empty key.

## Consequences

- Domain and orchestration logic do not import a provider SDK.
- Tests use deterministic fake outputs.
- Structured output reduces parsing ambiguity but does not replace backend validation.
- A selected model/version will be pinned in the Phase 5 evaluation record; later changes require a recorded evaluation.
- Missing credentials or provider outages do not prevent deterministic recommendations.

Implementation follow-up (2026-09-18): the Groq HTTP adapter, injectable fake, and gateway are
implemented. See [ADR-005](ADR-005-grounded-groq-ranking.md) for the constrained explanation
policy and shared resilience budget. No live model has yet been approved; the original
requirement for an explicit model, server-side key, and recorded evaluation remains in force.

## Alternatives Considered

- Call a provider SDK directly from route handlers: rejected because it couples HTTP, policy, and provider behavior.
- Use an unpinned moving model alias in evaluation/release: rejected because results could change without a code/config review.
- Make the model mandatory: rejected because recommendation availability must survive provider failure.
