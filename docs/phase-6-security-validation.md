# Phase 6.1 Security Controls

Validation date: 2026-09-19

## Outcome

P6.1 runtime controls are implemented and verified. Python and production web dependency scans
found no known vulnerabilities. The client production bundle contains neither the configured Groq
credential nor Groq credential markers.

P6.1 is approved. On 2026-09-19, the project owner selected a non-container runtime path, so a
container-image vulnerability scan is not applicable to this release candidate. Docker is not
required to develop, test, run, or deploy the Python API and static web application directly.

## Implemented controls

- Public request models reject unknown fields and constrain text lengths, list sizes, enums, numeric
  ranges, and result counts.
- Request bodies are limited to 16 KiB by default. Both declared `Content-Length` and streamed bodies
  are checked, so chunked transfer encoding cannot bypass the limit.
- Rate limits use a 60-second window by default: 120 API requests, 30 deterministic recommendation
  requests, and 10 LLM-backed recommendation requests per client address.
- Rate limiting cannot be disabled in production, and configuration must preserve
  `API >= recommendation >= LLM` limits.
- Health endpoints are excluded from rate limiting so orchestrator probes remain reliable.
- Production rejects empty or wildcard CORS configuration. All configured origins must be valid
  HTTP(S) origins without credentials, paths, queries, or fragments.
- Repository values use database parameters. The only dynamic SQL fragments are fixed clauses and
  generated placeholder counts; user data is never interpolated into SQL.
- User preference text is JSON-encoded as untrusted prompt data. Model output is schema-validated,
  candidate-ID constrained, and limited to allowlisted evidence sentences before reaching clients.
- Structured logging redacts credential and free-text preference fields recursively. Provider error
  bodies, prompts, raw model output, and API keys are not logged.
- The Groq credential remains server-side in `APP_GROQ_API_KEY`; only `VITE_*` variables are eligible
  for inclusion in the browser build.

The built-in limiter is process-local. If Phase 7 deploys multiple API workers or replicas, enforce
the same or stricter aggregate quota at the ingress/API gateway; do not rely on summing independent
per-process quotas.

## Automated evidence

Commands run from the repository root unless noted:

```powershell
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\ruff.exe check apps/api pipelines
.\.venv\Scripts\mypy.exe apps/api pipelines
```

Results:

- Pytest: 115 passed.
- Ruff: passed.
- Mypy strict mode: passed for 57 source files.

Web verification from `apps/web`:

```powershell
$env:Path = (Resolve-Path '..\..\.tools\node-v22.23.2-win-x64').Path + ';' + $env:Path
npm.cmd run check
npm.cmd audit --omit=dev --audit-level=high
```

Results:

- ESLint, TypeScript, 19 Vitest tests, and the production build passed.
- NPM production dependency audit: zero known vulnerabilities.
- Content-only scan of `apps/web/dist` found zero exact matches for the configured server key and
  zero `APP_GROQ_API_KEY` or Groq key-pattern matches.

Python production dependency scan:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.tools\uv-cache').Path
$env:UV_PYTHON_INSTALL_DIR = (Resolve-Path '.tools\python').Path
$env:UV_TOOL_DIR = Join-Path (Resolve-Path '.tools').Path 'uv-tools'
.\.tools\uv\uvx.exe pip-audit --requirement requirements.lock --progress-spinner off
```

Result: no known vulnerabilities found.

## Container decision

The repository retains Dockerfiles as optional packaging artifacts, but container packaging is not
part of the approved runtime path. If a later deployment introduces containers, P6.1 must be
reopened and the built image scanned before release.

For a future container deployment, run:

```powershell
docker build --pull --tag restaurant-recommendation-api:phase6 -f apps/api/Dockerfile .
docker scout cves restaurant-recommendation-api:phase6 --only-severity critical,high
```

Alternatively, use Trivy:

```powershell
docker build --pull --tag restaurant-recommendation-api:phase6 -f apps/api/Dockerfile .
trivy image --severity HIGH,CRITICAL --exit-code 1 restaurant-recommendation-api:phase6
```

The future approval rule remains: no unresolved critical or high vulnerabilities. Record any
justified exception with the CVE, affected package, exploitability in the image, owner, and
remediation deadline.
