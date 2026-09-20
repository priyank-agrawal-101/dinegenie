# ADR-005: Constrain Groq Explanations to Verified Evidence

- Status: accepted implementation policy; live model approval pending
- Date: 2026-09-18
- Related: [ADR-004](ADR-004-provider-neutral-llm-gateway.md), [product rules](../product-rules.md)

## Decision

Use the existing `httpx` dependency in an isolated Groq adapter behind the asynchronous
`RecommendationModel` protocol. No provider SDK is imported by domain or route code.
Production configuration accepts Groq only; fake models are injected explicitly by tests
and the offline evaluation runner, never selected through a production environment flag.

Groq may select and order exactly the requested number of restaurants (or all available
candidates when fewer exist) from the top 10–20 deterministic candidates. It cannot change
eligibility, factual fields, verified matches, or unverified preferences.

Version 1 deliberately uses **evidence-constrained explanations**, not unrestricted prose.
The backend builds complete approved sentences from numeric facts, verified preference
matches, and generic limitation language. The model selects and orders one to four of these
sentences. The validator requires exact sentence composition and exact preference lists.
This prevents incorrect numbers, unsupported qualitative claims, negations, URLs, markup,
and abusive additions from reaching the user. Only one approved optional summary is allowed.

This limits stylistic variety but establishes an enforceable grounding boundary. A number
matcher alone cannot establish that “family-friendly” or “allergen-safe” is true. Arbitrary
paraphrasing requires a new policy/prompt version, grounding strategy, and release evaluation.

## Resilience and Resource Policy

- Fixed HTTPS Groq endpoint; no redirects or inherited HTTP proxy configuration.
- JSON-object mode by default; opt into strict JSON-schema mode only for a supported model.
- Default 8-second total model deadline, including retry/repair waits.
- At most two calls total: the original plus either one transient retry or one schema repair.
  A repair does not create a second retry budget and never includes raw prior model text.
- 429/5xx responses may retry within the remaining deadline. Authentication/model errors,
  disconnected transports, timeouts, unknown IDs, and failed grounding fall back immediately.
- Respect numeric `Retry-After`; invalid/date-form headers conservatively consume the remaining
  budget rather than retrying early. Long waits do not block useful deterministic results.
- Candidate count, prompt byte/token upper bounds, output tokens, and response bytes are capped.
  Prompt estimation uses UTF-8 bytes plus framing/schema overhead as a conservative byte-BPE
  token upper bound. Oversized prompts fall back rather than silently dropping evidence.
- Process-local circuit breaker: three failed ranking requests open it for 30 seconds;
  one half-open probe is allowed. Older in-flight completions cannot close a newly opened circuit.
  Multiple API workers have separate breakers; shared/distributed protection is Phase 6 work.
- Caller cancellation and detected HTTP disconnects cancel model work. Cancellation is not a
  provider failure. Cancellation cannot refund tokens already processed by Groq.
- Readiness depends on the dataset, not Groq availability.

## Data and Telemetry

Candidates are loaded under a request-bound dataset version. After validation, selected IDs
are read from that same version and factual fields are checked against the original snapshot.
Missing or unexpectedly mutated source records fail as dataset unavailable; facts from a new
active version are never mixed into an old prompt's result.

Telemetry contains configured model, prompt/schema versions, dataset version, attempts,
latency, safe error categories, reported token usage, and optional estimated USD cost.
Raw prompts, optional user text, model replies, credentials, and provider error bodies are
not logged. Unknown token usage is marked incomplete, and unknown cost is null, not zero.

## Evaluation and Approval

`evals/cases-v1.json` pins the fixture version, prompt/schema content hashes, expected hard
constraints, and thresholds. The runner measures baseline and assisted output across repeated
trials. Fake-model results prove wiring and invariants only, not Groq quality or improved relevance.

Human judgments remain explicitly pending, and the approved model remains null until reviewed.
The release gate rejects fake runs, missing model approval, missing human relevance scores,
insufficient trials, safety regressions, incomplete cost accounting, excessive fallback/latency,
or degraded relevance. Production distribution also remains blocked by the source license.
