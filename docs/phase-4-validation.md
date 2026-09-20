# Phase 4 Validation Record

- Validation date: 2026-09-18
- Workspace: `E:\Nextleap`
- Scope: Phase 4 deterministic browser MVP, tasks P4.1–P4.6
- Status: implemented and locally validated
- Groq/API key use: none; live integration remains Phase 5

## Implemented Journey

The React client in `apps/web` now uses the Phase 3 API for the complete search journey.
The unrelated root `index.html` and existing production dataset store were preserved.

| Plan task | Implementation |
|---|---|
| P4.1 — Preference form | Searchable Bengaluru locality combobox; API-backed budget bands; custom INR maximum; locality-specific, searchable cuisine multi-select; minimum rating on a 0–5 scale; 300-character preferences field; 1–10 results, default 5 |
| P4.2 — Request state | Typed API client, 20-second request timeout, duplicate-submit guard, cancellation, stale-response protection, retained inputs, loading feedback, metadata retries, safe validation/network/service/rate-limit messages |
| P4.3 — Results | Backend ordering; restaurant name, locality/city, cuisines, rating, currency/cost basis, explanation, matched and unverified preferences; explicit unavailable values; snapshot version and request details |
| P4.4 — Refinement | No-match explanation, submitted-filter summary, suggestions that only change the draft form, and an explicit new search before broader results are requested |
| P4.5 — Accessible layout | Desktop/tablet/mobile layouts, visible focus, native radio/checkbox semantics, keyboard combobox, live status/error announcements, reduced-motion rules, long-text wrapping |
| P4.6 — Tests | Frontend unit/component tests and a three-viewport Playwright suite with a real fixture API, failure injection, keyboard checks, axe audits, and screenshot inspection |

### Product Boundaries

- Coverage is explicitly Bengaluru localities, not arbitrary cities.
- Cuisine matching is any-match; an empty selection means any cuisine.
- Budget bands come from metadata, not a duplicated frontend threshold table.
- A custom maximum sends `band: null` and the chosen `max_amount`.
- Changing locality clears incompatible cuisine selections and announces the change.
- Editing submitted preferences cancels pending work and labels prior results as stale.
- Suggested refinements do not automatically send a request. The user reviews the edited
  form and selects **Find restaurants**. This is a new exact-filter request, not a backend
  automatic relaxation; the UI faithfully displays the returned `meta.filters_relaxed`.
- Restaurant strings are escaped text, not executable HTML. Unsupported traits remain
  unverified. Snapshot ratings/prices are not presented as live availability.
- Form values are retained in component memory, not saved in browser storage.

## Automated Results

| Check | Result |
|---|---|
| Frontend ESLint | Passed, no warnings |
| TypeScript checks | Passed |
| Vitest | 17 tests passed across 3 files |
| Vite production build | Passed |
| Backend regression suite | 48 pytest tests passed |
| Playwright | 12 tests passed: 4 scenarios across 3 viewports |
| Axe WCAG 2 A/AA and WCAG 2.1 AA checks | No violations on initial and result states at all 3 viewports |

The final browser suite completed locally in 25.9 seconds; this is test runtime, not a
production performance benchmark. Frontend linting was also rerun after the keyboard-test
adjustment.

### Unit and Component Coverage

- Required locality and invalid/missing custom budget validation.
- Typed request mapping, custom-maximum precedence, result count, and singular wording.
- Backend ranking preservation, retained inputs, and unverified preference display.
- Duplicate submission prevention, loading state, abort on edit, and ignored late response.
- No-match recovery requiring explicit resubmission.
- Backend validation, budget field errors, unavailable service, rate limiting, and network failure.
- Metadata retry, including keyboard reachability of locality retry.
- Missing rating/cost/cuisine, currency/cost-basis formatting, and escaped source text.
- API error contracts, non-JSON error safety, and duplicate result-ID rejection.

### Real Browser/API Coverage

Playwright prepares a checked-in fixture via the actual ingestion pipeline, starts FastAPI
on `127.0.0.1:8014`, and serves the production web build on `127.0.0.1:4173`.
The fixture store is isolated at `runtime-data/phase4-e2e/restaurants.db`; test startup refuses
to reuse an existing service. LLM mode is explicitly disabled.

1. Select Banashankari, medium budget, and Chinese cuisine: two matching restaurants are
   returned, including Spice Elephant; family-friendly is unverified.
2. Change to low budget: the old results are marked stale; resubmission produces no matches.
3. Choose **Try any cuisine**: the draft changes, but no recommendation request is made.
4. Submit again: Sea Green Cafe and Cuppa are returned; backend filter relaxations remain None.

Separate scenarios inject metadata/search 503 responses and verify successful retry with
retained selections. Deliberately long/HTML-like restaurant text and missing facts are mocked
to test rendering boundaries; these are not claims about the real fixture's contents.

## Accessibility and Visual Review

Validated Chromium viewports:

- Desktop: 1280 × 720.
- Tablet: 768 × 1024.
- Mobile: Pixel 7 emulation, 393 × 851 CSS pixels.
- Additional reflow check: 320-pixel width, plus CSS `zoom: 2` on desktop.

The keyboard sequence exercises locality arrow/Enter selection, Tab into the budget group,
arrow-key budget/custom selection, Tab through cuisine controls, rating, result count,
preferences, and Enter submission. Keyboard locality retry is covered separately. The final
sequence and rendered focus screenshot were reviewed; the primary action has a clear blue
focus outline. A retry control that originally closed on blur was corrected and regression-tested.

Desktop, tablet, mobile, and narrow long-content screenshots were visually inspected. Text
wraps without horizontal page overflow in the tested layouts. Reduced-motion media is emulated
in the long-content scenario; CSS disables animation and smooth scrolling for that preference.

Generated evidence is in the ignored `apps/web/test-results/` directory:

- `smoke-keyboard-search-accessibility-and-responsive-results-{project}/keyboard-focus.png`
- `smoke-keyboard-search-accessibility-and-responsive-results-{project}/search-results.png`
- `smoke-long-source-text-missing-facts-and-zoom-remain-usable-{project}/long-content.png`

These checks are not a full accessibility certification. No screen-reader assistive-technology
session or native browser-menu zoom check was performed; zoom testing used CSS zoom and a
narrow viewport. Firefox, Safari/WebKit, and physical mobile devices were not tested.

## Reproduction

Install the locked Python dependencies and web dependencies described in [README](../README.md).
From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

From `apps/web`, with Node 22 on PATH:

```powershell
npm.cmd run check
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

`npm.cmd`/`npx.cmd` avoid PowerShell script-execution-policy restrictions on Windows.
On macOS/Linux, use `npm`/`npx`. The browser configuration finds the root `.venv`, falls back
to `python`, or accepts a `PYTHON` executable override. `API_PROXY_TARGET` selects the
development/preview backend; `VITE_API_BASE_URL` remains the optional public API URL.

Windows sandbox permissions initially blocked generated build/test-cache writes. The checks
were rerun with permission to update those local artifacts and passed; no source/runtime
data deletion or broad permission change was needed.

## Remaining Boundaries

- CI was updated to provision Python for the real-API browser suite, but remote CI was not run.
- Docker was not run; Docker is unavailable in this environment.
- This phase validates the browser journey against a small reproducible fixture. The prior
  full-dataset API validation remains recorded in [Phase 3 validation](phase-3-validation.md).
- Dataset licensing remains unspecified upstream; production use/distribution is still blocked
  pending clarification.
- No Groq request was made and no API credential was requested or stored. Phase 5 will add
  the provider gateway, grounded LLM ranking, validation, and deterministic fallback.

Phase 4 exit criteria are met for the local deterministic MVP. Stakeholder review can now
exercise the inputs, result ordering, explanations, and refinement flow before adding LLM behavior.
