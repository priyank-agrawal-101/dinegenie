# ADR-002: Apply Deterministic Filtering Before LLM Ranking

- Status: Accepted
- Date: 2026-09-13

## Context

User constraints such as locality, budget, cuisine, and minimum rating are factual and testable. An LLM can improve ordering and explanations but can also invent facts or ignore constraints if given authority over retrieval.

## Decision

Backend code applies all hard filters and computes a deterministic score before any model call. Only the top 10–20 eligible candidates are sent to the model. The model may reorder those IDs and write short explanations; it may not add candidates or define factual fields.

The backend validates the model response, hydrates all restaurant facts from the request-bound dataset version, and returns deterministic results if the model is unavailable or invalid.

## Consequences

- Hard constraints are enforceable through invariant tests.
- Model token use and latency are bounded.
- The product remains useful without an LLM.
- The model cannot discover candidates excluded by deterministic retrieval, so candidate selection quality must be measured independently.

## Alternatives Considered

- Send the full dataset to the LLM: rejected for token cost, latency, privacy, and hallucination risk.
- Let the LLM generate SQL/filters directly: rejected for MVP correctness and security risk.
- No LLM: retained as fallback but does not fully meet the requested human-like recommendation objective.
