# Phase 6 Operational Failure Exercises

Date: 2026-09-19

| Exercise | Expected behavior | Evidence |
|---|---|---|
| Database unavailable | Readiness fails; API returns stable `DATASET_UNAVAILABLE`; no internal details leak | `test_health.py`, `test_recommendation_api.py`, `test_observability.py` |
| Missing active dataset | Readiness fails and recommendations return the stable dataset error | `test_health.py`, `test_recommendation_api.py` |
| LLM timeout or rate limit | One bounded retry where eligible, then grounded deterministic fallback | `test_llm.py` |
| Malformed/ungrounded model output | Reject output and return deterministic fallback | `test_llm.py` |
| Sustained provider outage | Circuit opens, provider calls pause, database-backed results continue | `test_llm.py` |
| Failed ingestion/activation | Transaction rolls back and the prior active dataset remains | `test_ingestion.py` |
| Client metadata/API failure | Error is announced, preferences remain, retry recovers | `apps/web/tests/smoke.spec.ts` |

Logs carry request IDs and error categories without preference text. Prometheus metrics separate
API errors, readiness, fallbacks, invalid model output, and ingestion freshness. Alert rules and
recovery actions are in `ops/observability/prometheus-alerts.yml` and
`docs/phase-6-observability.md`.

All exercises are deterministic automated fault injections. They do not disrupt the user's
normal database or call the live Groq service.
