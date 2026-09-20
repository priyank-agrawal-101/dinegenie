# Recommendation Evaluations

Phase 5 provides a credential-free safety suite and an explicitly enabled live Groq runner.

## Files

- `cases-v1.json`: 16 cases, expected constraints/counts, version/hash pins, and release thresholds.
- `human-judgments-v1.json`: the completed initial human review record.
- `cases-v2.json` and `human-judgments-v2.json`: the approval pair identifying
  `openai/gpt-oss-120b` as the evaluated model.
- `results/phase5-groq-v2-final.json`: passing three-trial live approval evidence.
- `results/phase5-fake-v1-final.json`: final local baseline/fake evidence, 3 trials per case.
- `results/phase5-fake-v1.json`: preserved preliminary evidence before the final release-gate fields.

The fixture covers two Bengaluru localities and has only seven canonical restaurants. It
includes expected no-match high-budget and unsupported-city cases; it cannot establish broad
full-dataset recommendation quality. Expand/version the suite before production approval.

## Offline Run

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pipelines.cli --mode fixture --runtime-root runtime-data/phase5-eval
$env:PYTHONPATH = 'apps/api'
.\.venv\Scripts\python.exe -m app.evaluation --mode fake --output runtime-data/phase5-eval/new-offline-report.json
```

Output files are exclusive-create: existing evidence is never overwritten. Safety/count
violations return a nonzero exit code. Fake runs always have `release_passed: false`, even
when all safety checks pass. Their zero usage/cost values are fake behavior, not Groq pricing.

## Human Review

The initial review was completed and preserved in the version-2 approval pair. For future versions,
review the selected cases against the pinned fixture in the application.
Score each listed restaurant from 0 (irrelevant) to 3 (excellent), explaining each grade.
Set `reviewer` and `status: reviewed` only after actual human review. Preserve disagreements
and adjudicate before finalizing grades; do not replace disagreement with automatic scores.

The runner computes NDCG only when the entire candidate pool for a judged case has valid
grades and reasons. At least two judged cases are required for this initial release gate.
The final v2 report covers two fully judged cases. New or changed cases require a new human review;
do not carry scores across changed candidate pools without confirmation.

## Live Groq Run

1. Check current model availability in your Groq account. Store `APP_GROQ_API_KEY` and
   `APP_LLM_MODEL` in the ignored root `.env`; never paste the key into chat or a command.
2. Set both `APP_LLM_INPUT_USD_PER_MILLION` and `APP_LLM_OUTPUT_USD_PER_MILLION` to the
   selected model's current prices. Missing prices produce null estimates and block release.
3. Select `APP_LLM_RESPONSE_FORMAT=json_schema` only for a model with documented strict
   structured-output support; otherwise use `json_object` plus backend validation.
4. Use an explicitly versioned suite with `approved_model` set to the model under approval.
   Keep the original pending-approval evidence; update hashes/versions after prompt/schema changes.
5. Run the bounded evaluation below. It sends 33 initial model requests for the 11 nonempty
   cases over three trials, with at most one retry/repair each (maximum 66 calls). It may incur cost.

The live runner defaults to a 12.5-second minimum interval between request starts. This is based
on Groq's published base limits for `openai/gpt-oss-120b` (30 RPM, 1,000 RPD, 8,000 TPM, and
200,000 TPD), the observed upper successful call size of about 1,452 tokens, a 1,500-token
planning allowance, and 10% TPM headroom. The TPM calculation is the binding constraint:
`60 * 1,500 / (8,000 * 0.90) = 12.5 seconds`; the 30 RPM constraint alone would require only
two seconds. Limits are organization-wide, so other applications using the same organization
still consume the allowance.

```powershell
$env:PYTHONPATH = 'apps/api'
.\.venv\Scripts\python.exe -m app.evaluation --mode groq --allow-live --require-release --cases evals/cases-v2.json --judgments evals/human-judgments-v2.json --output runtime-data/phase5-eval/groq-evaluation-v3.json
```

`--allow-live` is mandatory; the runner never turns a fake run into a live call automatically.
`--require-release` returns nonzero until all release gates pass. Review failed gates rather
than weakening safety thresholds to obtain a pass. Re-run with a new output filename.

Scheduling waits occur before the measured recommendation request, so they do not inflate model
latency. Override the interval only when the Groq account Limits page shows a different allowance:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation --mode groq --allow-live --request-interval-seconds 12.5 --cases evals/cases-v2.json --judgments evals/human-judgments-v2.json --output runtime-data/phase5-eval/groq-evaluation-v3.json
```

Groq applies limits at the organization level and enforces whichever limit is reached first.
Successful responses expose remaining/reset request and token headers; HTTP 429 responses expose
`retry-after`, which the gateway already respects when it fits within the bounded request deadline.
Pacing prevents the normal evaluation sequence from intentionally reaching 429. It does not hide
genuine provider failures, guarantee capacity consumed by another process, or replace Phase 6 load
testing and API-level admission control.

Default gates: zero hard-filter violations, unknown IDs, count mismatches, delivered unsupported
claims, or rejected unsupported model claims; at least three trials; at most 10% fallback on
nonempty requests; p95 under 8 seconds; mean estimated model cost at most USD 0.02; no NDCG
regression on reviewed cases. The runner records token totals, incomplete usage, and latency
variance, along with safe configuration and application/dataset/prompt/model versions.

These are initial engineering gates, not proof of production quality or an approved budget.
Public deployment remains contingent on broader evaluation, Phase 6 hardening, and licensing.
