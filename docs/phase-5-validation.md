# Phase 5 Validation Record

- Date: 2026-09-18; live follow-up: 2026-09-19
- Workspace: `E:\Nextleap`
- Status: Phase 5 complete; live release evaluation passed on 2026-09-19
- Provider: Groq; `openai/gpt-oss-120b` approved for the bounded Phase 5 scope
- Credential check: local key and model configured and authenticated on 2026-09-19; no secret value was printed

## Live Configuration Follow-up — 2026-09-19

Groq's authenticated models endpoint returned HTTP 200 and listed the configured
`openai/gpt-oss-120b` model as active. The root `.env` passed settings validation.
The initial evaluation enabled Groq only for its own process. The user subsequently enabled
`APP_LLM_ENABLED=true`; an already-running API still requires a restart to reload `.env`.
No credentials were copied into evidence.

Command:

```powershell
$env:PYTHONPATH = 'apps/api'
.\.venv\Scripts\python.exe -m app.evaluation --mode groq --allow-live --require-release --output runtime-data/phase5-eval/groq-evaluation-2026-09-19-v1.json
```

Local evidence: [groq-evaluation-2026-09-19-v1.json](../runtime-data/phase5-eval/groq-evaluation-2026-09-19-v1.json)
(ignored runtime artifact). The original versioned cases, pending judgments, and offline
evidence were preserved. No model approval was inferred from configuration alone.

- 16 cases, three trials each: 48 baseline requests and 48 assisted-path requests.
- 15 assisted-path requests correctly returned no matches without calling Groq.
- Of 33 nonempty requests, seven returned validated live AI-assisted recommendations and
  26 fell back: two `rate_limited`, one `timeout`, and 23 `circuit_open`.
- The runner made 11 provider attempts, including one retry. Circuit-open requests made no
  provider call; later cases, including injection cases, therefore did not exercise live output.
- Both paths had zero hard-filter violations, unknown IDs, count mismatches, and delivered
  unsupported claims. No unsupported model output was rejected in the responses received.
- Assisted-path fallback rate: 78.79%, above the 10% gate. Overall assisted-path p95: 1,595.883 ms;
  that includes fast circuit-open fallbacks and is not a pure model-latency measurement.
- Reported usage: 6,055 input tokens and 3,037 output tokens. Usage is incomplete because of
  failed attempts. Both token-price settings are absent, so estimated cost remains unknown.
- Human relevance judgments and NDCG remain unavailable.

The command exited 1 as expected with `release_passed: false`: model approval, fallback
threshold, complete usage/pricing, and human relevance review remain blockers. The key and
basic live integration work, but full live scenario coverage and Phase 5 sign-off are not
complete. Before another evaluation, account for the account's rate limits (for example,
space evaluation traffic within its quota), confirm pricing, and complete human review.
Keep the production timeout, grounding checks, and release thresholds intact.

### Rate-limit remediation

Groq's [official rate-limit page](https://console.groq.com/docs/rate-limits) was rechecked on
2026-09-19. Its published base row for
`openai/gpt-oss-120b` lists 30 RPM, 1,000 RPD, 8,000 TPM, and 200,000 TPD. Limits apply at the
organization level and the first exhausted dimension blocks the request. The initial seven
successful calls reported 9,092 total tokens, explaining why the 8,000 TPM boundary was reached
well before the 30 RPM boundary.

The evaluation runner now defaults live runs to a 12.5-second interval between request starts.
It reserves 1,500 tokens per call—slightly above the largest successful initial call—and retains
10% TPM headroom. Scheduling waits occur outside the measured recommendation latency and outside
the model's eight-second response deadline. Fake evaluation remains unpaced. The interval is
recorded in every new report and can be explicitly overridden for a verified account-specific
limit. Tests cover the interval calculation and scheduler boundaries.

This addresses evaluation-induced bursting; it does not claim production throughput. Other
organization traffic can still cause fallbacks. Phase 6 must add and load-test API-level admission
control for LLM-backed requests. The prior failed evidence remains unchanged, and a paced live run
with all three trials is still required after pricing and human judgments are complete.

The pacing implementation was verified with a bounded one-trial live smoke test:

```powershell
$env:PYTHONPATH = 'apps/api'
.\.venv\Scripts\python.exe -m app.evaluation --mode groq --allow-live --trials 1 --output runtime-data/phase5-eval/groq-pacing-smoke-2026-09-19-v1.json
```

All 11 eligible requests returned validated `llm_assisted` results: zero fallbacks, 429s,
provider errors, retries, hard-filter violations, unknown IDs, count mismatches, or delivered
unsupported claims. Reported usage was 9,925 input and 5,303 output tokens; the largest call was
1,651 total tokens. Assisted-path p95 was 2,167.934 ms, excluding pacing waits. This confirms the
burst-remediation behavior under the observed test conditions, reducing the smoke-test fallback
rate from the prior run's 78.79% to 0%.

The smoke report remains `release_passed: false`: it has only one trial, the suite has no approved
model declaration, prices were not configured for that run, and human relevance judgments are
pending. Its local report is ignored runtime evidence at
`runtime-data/phase5-eval/groq-pacing-smoke-2026-09-19-v1.json`.

### Pricing configuration

Groq's [official models page](https://console.groq.com/docs/models) was checked on 2026-09-19 for
the configured `openai/gpt-oss-120b` model. It lists USD 0.15 per one million input tokens and
USD 0.60 per one million output tokens. These values are now configured privately as
`APP_LLM_INPUT_USD_PER_MILLION=0.15` and `APP_LLM_OUTPUT_USD_PER_MILLION=0.60` in the ignored
root `.env`. No credential was read into documentation or changed.

The prior smoke report remains immutable and correctly records null cost because pricing was not
configured when it ran. Future evaluation reports will calculate cost from provider-reported token
usage and these configured rates. Prices are time-sensitive and must be rechecked when the model
changes or before a later approval run.

## Final Phase 5 Approval — `restaurant-eval-v2`

The user completed all four relevance grades and reasons across the two required cases. The
review was preserved as [human-judgments-v2.json](../evals/human-judgments-v2.json), paired with
[cases-v2.json](../evals/cases-v2.json), which identifies `openai/gpt-oss-120b` as the model under
approval. The version pair passed offline validation before live execution.

Final evidence: [phase5-groq-v2-final.json](../evals/results/phase5-groq-v2-final.json).

```powershell
$env:PYTHONPATH = 'apps/api'
.\.venv\Scripts\python.exe -m app.evaluation --mode groq --allow-live --require-release --cases evals/cases-v2.json --judgments evals/human-judgments-v2.json --output runtime-data/phase5-eval/groq-evaluation-2026-09-19-v2.json
```

| Metric | Deterministic baseline | Groq-assisted |
|---|---:|---:|
| Requests | 48 | 48 |
| Eligible model requests | — | 33 |
| Hard-filter violations | 0 | 0 |
| Unknown IDs | 0 | 0 |
| Count mismatches | 0 | 0 |
| Delivered/rejected unsupported claims | 0 | 0 |
| Fallback rate | 0% | 0% |
| p95 response latency | 2.052 ms | 2,225.692 ms |
| Human-judged cases | 2 | 2 |
| Mean NDCG | 0.815465 | 0.815465 |
| Reported input/output tokens | 0 / 0 | 29,775 / 16,054 |
| Mean estimated cost per eligible call | USD 0 | USD 0.00042723 |

All 33 eligible requests produced validated AI-assisted responses in one attempt. Total estimated
model cost was USD 0.01409865. Usage was complete, the 12.5-second pacing policy was recorded, and
pacing waits were excluded from response latency. The report has no release blockers and records
`release_passed: true`. No threshold, prompt, schema, or grounding rule was weakened to obtain the
pass. This approval is limited to the pinned fixture, evaluation cases, model, prompt, schema, and
prices in the report; Phase 6 must establish production capacity and operational quality.

## Implemented

The deterministic API now has an optional asynchronous model-enhancement path. Eligible
candidates are selected and scored before model communication. `RecommendationModel` separates
the orchestrator from the Groq HTTP adapter, and tests inject a credential-free fake.

The response uses one of `deterministic`, `llm_assisted`, or `deterministic_fallback`, plus an
optional validated summary. The web client uses the same restaurant cards for all modes and
shows restrained AI/fallback transparency without provider error details.

### Grounding Boundary

- Prompt `restaurant-grounded-v1`; schema `ranked-evidence-v1`.
- At most 20 deterministic candidates; no full-dataset or web search by the model.
- JSON-serialized untrusted preference/candidate data, with no raw previous reply in repairs.
- Strict Pydantic output: exact count, supplied IDs only, uniqueness, bounded explanation
  lengths, exact matched/unverified lists, and no unknown factual fields.
- Explanations select and order one to four approved evidence sentences. Arbitrary paraphrases,
  invented numerical/qualitative claims, URLs, markup, and abusive additions are rejected.
- A summary must be null or the approved source-limitation summary.
- Post-validation hydration reads the original dataset version. Unexpected source changes
  fail closed rather than attaching old explanations to new facts.

This is a deliberately constrained first version, not unrestricted model-authored prose.
The rationale and trade-off are recorded in [ADR-005](adr/ADR-005-grounded-groq-ranking.md).

### Resilience and Privacy

- Default total model deadline: 8 seconds, including retry/repair waits.
- At most one extra call shared between transient retry and schema repair; no nested retries.
- Bounded completion tokens, prompt bytes/conservative token estimate, and provider response size.
- Immediate fallback for unsupported IDs/claims, auth/model rejection, timeout, and transport
  failures; bounded 429/5xx retry respecting the remaining deadline.
- Process-local circuit breaker, one half-open probe, and protection from stale completions.
- HTTP disconnect detection and caller cancellation cancel pending model work.
- Dataset readiness remains healthy during model failure.
- Safe telemetry records model/prompt/schema/dataset versions, latency, attempts, categories,
  token usage, and optional configured-price cost estimates. Missing usage/cost is not fabricated.
- Fixed HTTPS endpoint, no redirects; server-only `SecretStr` credential handling.
- Offline tests override live-model environment flags, preventing a developer's `.env` from
  silently enabling billed calls during tests. Fake mode never selects the Groq adapter.

## Local Validation

| Check | Result |
|---|---|
| Ruff lint | Passed |
| Ruff formatting | Passed |
| Strict MyPy | Passed, 55 source files |
| Pytest | 103 passed |
| Frontend ESLint / TypeScript / production build | Passed |
| Frontend Vitest | 19 passed |
| Playwright Chromium | 15 passed across desktop, tablet, and mobile |
| Axe on initial/results/AI/fallback states | No violations in the tested states |
| Client-bundle marker scan | No Groq endpoint, credential-variable name, or synthetic test-secret marker found |

The browser suite exercises the real fixture API for search/refinement and intercepts responses
for AI/fallback presentation checks. Backend tests exercise the real orchestrator and Groq wire
contract with fake models and HTTP mock transports. Neither is presented as a live provider run.

Coverage includes valid reordering; malformed/truncated/fenced JSON; duplicate JSON keys;
unknown/duplicate/excess/empty IDs; wrong types and extra factual fields; wrong cost/rating;
unsupported traits, unsafe summaries, abusive/HTML/URL output; exact unverified preferences;
prompt injection; schema repair; shared retry exhaustion; authentication/rate-limit/outage
mapping; deadline/cancellation; circuit/probe transitions; prompt/response caps; missing usage;
version-bound hydration; secret-safe telemetry; and evaluation release-gate failures.

AI-assisted desktop and fallback mobile screenshots were visually inspected, alongside the
existing responsive suite. New screenshots are in the ignored directory:

`apps/web/test-results/smoke-AI-assisted-and-fall-419dc-are-accessible-result-cards-{project}/`

Files: `ai-assisted.png` and `fallback.png`. The cards remain readable, and transparency text
does not expose technical provider errors. No physical-device or screen-reader session was run.

## Versioned Offline Evaluation

Final evidence: [phase5-fake-v1-final.json](../evals/results/phase5-fake-v1-final.json).

- Evaluation: `restaurant-eval-v1`.
- Dataset: `ds_874a188dbb2650a1b53f`, seven canonical fixture restaurants.
- Cases: 16, each with explicit expected count and hard constraints.
- Trials: 3 per case per mode; 48 baseline and 48 fake-assisted requests.
- Coverage: two localities, low/medium/high budget behavior, custom boundaries, any-match
  cuisines, rating boundaries, result count, verified/unsupported preferences, Delhi no-coverage,
  and instruction/delimiter injection.

| Metric | Deterministic baseline | Fake-assisted |
|---|---:|---:|
| Hard-filter violations | 0 | 0 |
| Unknown IDs | 0 | 0 |
| Count mismatches | 0 | 0 |
| Delivered unsupported claims | 0 | 0 |
| Empty-result rate | 31.25% | 31.25% |
| Mean local latency | 2.937 ms | 4.177 ms |
| Local p95 latency | 7.534 ms | 9.748 ms |
| Human-judged NDCG | Not available | Not available |

Five cases intentionally have no matches, explaining the 31.25% empty rate. This is not a
production empty-result estimate. Fake latency and zero token/cost values are not Groq
performance or billing estimates. The report also records latency variance and safe policy settings.

The offline report intentionally has `release_passed: false`, with these gates at that time:

1. Live Groq evaluation required.
2. Model approval required.
3. Human relevance review required.

Those statements describe the original offline report only. Human judgments were later completed
and versioned into `restaurant-eval-v2`; the final live report above shows equal mean NDCG rather
than claiming a relevance improvement.

## Groq Documentation Check

Public official documentation was retrieved on 2026-09-18, without credentials:

- [Models](https://console.groq.com/docs/models)
- [Structured outputs](https://console.groq.com/docs/structured-outputs)
- [API compatibility](https://console.groq.com/docs/openai)

These confirm the Groq `/openai/v1` base URL and JSON-object/structured-output options.
Strict structured output is model-dependent; account model availability was not checked.
The current public catalogue labels some Llama models enterprise-only, so availability/pricing
must not be assumed from an older tutorial. No production model default or price was invented.

## Phase 6 Handoff

Phase 5 sign-off is complete and every Phase 5 task is checked in
[implementation-plan.md](../implementation-plan.md). Phase 6 may now begin. Its production
security, observability, API-level rate limiting, load testing, PostgreSQL, accessibility, and
failure-exercise requirements remain unimplemented and must not be inferred from this evaluation.

Remote CI is configured but was not executed. Docker was not run. Full-dataset LLM evaluation,
production deployment, and licensing approval were not performed. Existing production data
and the unrelated root `index.html` were preserved.
