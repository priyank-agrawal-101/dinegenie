# Phase 1 Validation Record

- Validation date: 2026-09-13
- Workspace: `E:\Nextleap`
- Scope: project foundation only

## Toolchain Used

- Python: 3.12.14, isolated in the ignored `.venv`
- uv: 0.12.13, portable workspace tool
- Node.js: 22.23.2, portable workspace tool
- npm: 10.9.8
- Browser runner: Playwright 1.63.0 with Chromium

Portable validation tools are stored under ignored `.tools/`; they are not part of the project deliverables.

## Backend Results

| Check | Result |
|---|---|
| Ruff lint | Passed |
| Ruff format check | 16 files already formatted |
| Strict MyPy | Passed; 15 source files checked |
| Pytest | 8 passed |
| Live FastAPI startup | Passed |
| `GET /health/live` | HTTP 200 |
| Response request ID | Present, trusted 32-character ID |
| Structured completion log | Present with request ID, method, path, status, and duration |
| Startup without LLM key | Passed with `APP_LLM_ENABLED=false` |

Observed live body:

```json
{
  "status": "alive",
  "service": "restaurant-recommendation-api",
  "version": "0.1.0",
  "environment": "development"
}
```

## Frontend Results

| Check | Result |
|---|---|
| Clean `npm ci --offline` from lockfile | Passed; 239 packages installed |
| ESLint | Passed with zero warnings |
| Strict TypeScript build check | Passed |
| Vitest component test | 1 passed |
| Vite production build | Passed; 16 modules transformed |
| Playwright Chromium smoke test | 1 passed |

Production build output at validation time:

- HTML: 0.54 kB, 0.32 kB gzip.
- CSS: 3.28 kB, 1.33 kB gzip.
- JavaScript: 221.23 kB, 69.21 kB gzip.

## Lock and Configuration Validation

- `uv.lock` resolves 44 Python packages.
- `requirements.lock` is a hash-pinned production export.
- `requirements-dev.lock` is a hash-pinned development/CI export.
- `apps/web/package-lock.json` was regenerated and verified through a clean `npm ci`.
- `docker-compose.yml`, `.github/workflows/ci.yml`, and `.pre-commit-config.yaml` parse as valid YAML.
- Every Docker `COPY` input exists.
- A repository scan outside ignored dependency/tool directories found no API-key or private-key patterns.

## Environment-Limited Checks

- Docker/Compose was not executed because Docker is not installed on this machine.
- GitHub Actions was not executed because this workspace is not currently a Git repository or connected CI checkout.
- Their definitions were statically parsed, and the same lint, type, test, and web-build commands configured in CI passed locally.

These are execution-environment limitations, not hidden pass claims. Run `docker compose up --build` on a Docker-enabled host and allow the first repository CI run to validate those environments before treating container/CI execution as independently confirmed.
