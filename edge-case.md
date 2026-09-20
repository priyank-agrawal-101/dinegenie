# AI-Powered Restaurant Recommendation System — Edge-Case Catalogue

## 1. Purpose

This document is the corner-case and failure-scenario catalogue for [implementation-plan.md](implementation-plan.md). It also inherits the system boundaries and safety rules from [architecture.md](architecture.md) and the requirements in [problemStatement.md](problemStatement.md).

It is intended to drive implementation decisions, automated tests, evaluation cases, operational exercises, and release sign-off. New cases discovered during implementation must be added here with an expected behavior before the related code is considered complete.

## 2. Classification

### Severity

| Severity | Meaning |
|---|---|
| Critical | Can expose secrets, corrupt/publish invalid data, return invented restaurants, or violate a hard user constraint |
| High | Breaks the primary recommendation journey, removes fallback, or makes results materially misleading |
| Medium | Degrades usability, relevance, diagnostics, accessibility, or performance without invalidating core results |
| Low | Cosmetic, uncommon, or low-impact behavior that should still be deterministic |

### Primary Test Level

| Code | Test level |
|---|---|
| U | Unit test |
| D | Data-contract or ingestion test |
| I | API/database integration test |
| E | Browser end-to-end or accessibility test |
| M | Live or fake-model evaluation |
| O | Operational, deployment, load, or recovery exercise |

## 3. Non-Negotiable System Invariants

The following properties must hold across every case:

1. A returned restaurant satisfies every active hard filter.
2. Every returned restaurant ID belongs to the candidate set selected by backend code.
3. Restaurant name, location, cuisine, rating, cost, and source fields come from the active serving dataset, never from the LLM.
4. No filter is silently relaxed. Any relaxation is explicit, recorded, and user-approved when required by product rules.
5. Missing data remains unknown; it is never converted to zero, false, or a favorable value.
6. Unsupported preferences are labelled unverified and never presented as facts.
7. Failed ingestion cannot replace the last successful active dataset.
8. Invalid, unavailable, or slow LLM behavior produces deterministic fallback results when the database is healthy.
9. Client errors do not reveal credentials, prompts, SQL, stack traces, or internal provider details.
10. Every response is traceable through a request ID and active dataset version.

Any test that detects an invariant violation is release-blocking.

## 4. Phase 0 — Discovery and Decision Edge Cases

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P0-01 | Hugging Face repository does not exist or is private | Stop discovery with an actionable access error; do not scaffold a fabricated schema | High | O |
| P0-02 | Dataset repository exists but has multiple configurations or splits | Record and explicitly select the intended configuration/splits | High | D |
| P0-03 | Dataset revision changes between profiling and implementation | Pin the reviewed revision; require a new profile for a different revision | High | D |
| P0-04 | Dataset has no stated license | Block production use until licensing is clarified; local exploration may be separately documented | Critical | O |
| P0-05 | Expected field is absent | Mark it unavailable or revise the canonical mapping; do not infer a substitute silently | High | D |
| P0-06 | Multiple columns could represent location or cost | Compare examples and document the selected mapping and rationale | High | D |
| P0-07 | Rating uses more than one scale | Normalize only with an explicit source rule or separate the populations | Critical | D |
| P0-08 | Cost currency or basis is unclear | Store basis/currency as unknown and do not expose budget matching until resolved | Critical | D |
| P0-09 | Restaurant name and location are not sufficient to identify duplicates | Define a composite identity rule and quantify collision risk | High | D |
| P0-10 | Optional preference such as `family-friendly` has no supporting field | Treat it as unverified; never add a verified tag from intuition | High | D |
| P0-11 | Cuisine matching semantics are undecided | Default to documented `any` matching and prevent contradictory API/UI behavior | Medium | U |
| P0-12 | Budget band boundary belongs to two bands | Use inclusive/exclusive boundaries with exact documented examples | High | U |
| P0-13 | Dataset is too large for local memory | Profile and transform in streaming/batched mode; do not rely on whole-file loading | Medium | O |
| P0-14 | Dataset contains personal data unexpectedly | Stop publication and perform a privacy review before retaining or serving it | Critical | O |
| P0-15 | Source examples contradict documentation | Treat actual profiled data as evidence and record the discrepancy | High | D |

## 5. Phase 1 — Project Foundation Edge Cases

### 5.1 Environment and Configuration

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P1-01 | Required backend environment variable is absent | Startup fails fast with the variable name and safe remediation; no secret value is printed | High | I |
| P1-02 | Optional LLM key is absent while LLM mode is disabled | Application starts and deterministic recommendations remain available | High | I |
| P1-03 | LLM mode is enabled but its credential is absent | Startup or feature readiness reports a configuration error; deterministic mode remains possible if configured | High | I |
| P1-04 | Environment contains an invalid URL, integer, enum, or duration | Typed settings reject it before serving requests | High | U |
| P1-05 | `.env` or generated database is accidentally staged | Ignore rules and secret scanning fail the quality gate | Critical | O |
| P1-06 | Backend and web use different API schema versions | CI contract check fails before merge | High | I |
| P1-07 | Developer uses a different Python or Node version | Tooling reports supported versions and fails clearly when incompatible | Medium | O |
| P1-08 | Dependency lockfile and manifest disagree | Reproducible install/CI check fails rather than silently updating | Medium | O |
| P1-09 | Port is already in use | Startup reports the conflicting port and permits documented override | Medium | O |
| P1-10 | Windows and Linux path handling differs | Use platform-safe paths; local and container smoke tests both pass | Medium | O |

### 5.2 Startup and Health

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P1-11 | Database is unavailable during startup | Liveness can remain healthy; readiness is false and recommendation calls return a stable service error | High | I |
| P1-12 | No active dataset exists | Readiness is false with an internal diagnostic; client receives `DATASET_UNAVAILABLE` | High | I |
| P1-13 | LLM provider is down | Liveness and database readiness remain healthy; recommendation path falls back after Phase 5 | High | I |
| P1-14 | Application receives shutdown during an active request | Stop accepting new work and allow bounded graceful completion | Medium | O |
| P1-15 | Frontend is opened before API is ready | Show a recoverable service-unavailable state, not a blank screen | Medium | E |
| P1-16 | Root `index.html` already exists and is unrelated | New web app stays under `apps/web`; existing file is not overwritten implicitly | Medium | O |

## 6. Phase 2 — Data Foundation Edge Cases

### 6.1 Dataset Acquisition

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P2-01 | Network fails before download begins | Fail with a retryable acquisition error; do not create a published artifact | High | D |
| P2-02 | Network fails mid-download | Discard or quarantine the partial file and retain the previous valid input | High | D |
| P2-03 | Remote content changes under the same revision/reference | Hash mismatch prevents reuse and publication until reviewed | Critical | D |
| P2-04 | Cached download is corrupt | Verify hash/readability, invalidate the cache entry, and reacquire | High | D |
| P2-05 | Dataset has zero rows | Fail the quality gate and retain the prior active dataset | Critical | D |
| P2-06 | A selected split is missing | Fail mapping with the missing split named explicitly | High | D |
| P2-07 | Download is far larger than expected | Enforce configured resource limits and stop safely before exhausting disk | High | O |
| P2-08 | Disk fills during acquisition | Fail atomically, clean temporary artifacts safely, and preserve published data | Critical | O |
| P2-09 | Retried acquisition runs concurrently | Use locks or unique staging paths so runs cannot overwrite each other | High | O |
| P2-10 | Test fixture accidentally points to production-size data | Test mode enforces fixture size/path constraints | Medium | D |

### 6.2 Schema and Mapping Drift

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P2-11 | Required source column is renamed | Fail mapping; require a versioned mapping update | Critical | D |
| P2-12 | Column type changes from numeric to text | Explicit parser handles known formats or quality gate fails | High | D |
| P2-13 | New unknown columns appear | Ignore safely while recording them in the profile; do not auto-map | Low | D |
| P2-14 | Two mapped source columns have the same name after normalization | Mapping validation fails as ambiguous | High | D |
| P2-15 | Rows contain nested objects/lists unexpectedly | Use an explicit flattening rule or quarantine; never stringify into factual fields silently | High | D |
| P2-16 | Source column mixes currencies or rating scales | Split/normalize only with row-level evidence; otherwise quarantine or mark unknown | Critical | D |
| P2-17 | Schema differs across splits | Validate and map each included split before concatenation | High | D |
| P2-18 | Mapping file is syntactically valid but refers to absent columns | Preflight mapping validation stops ingestion | High | D |
| P2-19 | Old pipeline reads a newer mapping version | Reject incompatible versions rather than producing partial records | High | D |
| P2-20 | Columns contain values outside profiled assumptions | Quality report flags drift and configured thresholds decide publication | High | D |

### 6.3 Text Normalization

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P2-21 | Leading, trailing, repeated, tab, or newline whitespace | Normalize search values while retaining a clean display value | Medium | U |
| P2-22 | Same location differs only by case | Match through case-folded normalized values | High | U |
| P2-23 | Unicode forms differ, such as composed/decomposed accents | Apply a documented Unicode normalization form before matching | High | U |
| P2-24 | Location includes punctuation or alternate spacing | Normalize documented harmless variants without merging genuinely different places | Medium | U |
| P2-25 | City and neighborhood share the same name | Preserve hierarchy and avoid merging records based only on a label | High | D |
| P2-26 | Value contains only whitespace | Treat as missing, not a valid name/location/cuisine | High | U |
| P2-27 | Restaurant name contains emoji or non-Latin script | Preserve valid Unicode and render safely | Medium | U/E |
| P2-28 | Text contains HTML or script markup | Store as plain text and escape on display | Critical | U/E |
| P2-29 | Text is extremely long | Enforce storage/display limits and quarantine or truncate only under an explicit rule | Medium | D |
| P2-30 | Null is represented as `null`, `N/A`, `NA`, `-`, or similar text | Convert only approved tokens to null; do not erase legitimate names | High | U |

### 6.4 Rating, Cost, and Vote Parsing

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P2-31 | Rating is `NEW`, `-`, empty, or null | Store null and exclude when a minimum rating is active | High | U/I |
| P2-32 | Rating contains `/5` or surrounding text | Parse only documented patterns and retain the configured scale | High | U |
| P2-33 | Rating uses comma decimal notation | Parse only if the source locale supports it; otherwise quarantine | Medium | U |
| P2-34 | Rating is negative or above the scale | Quarantine or null it and report a range violation | Critical | D |
| P2-35 | Floating-point boundary is `3.999999` for a 4.0 minimum | Compare normalized decimal values using documented precision, not binary float surprises | High | U |
| P2-36 | Cost contains currency symbols and thousands separators | Strip recognized formatting and parse as decimal | High | U |
| P2-37 | Cost is `Free`, `Varies`, a range, or descriptive text | Store null or a separately modelled range only under an approved rule | High | U |
| P2-38 | Cost is zero | Accept only if zero is meaningful and documented; otherwise flag as invalid | High | D |
| P2-39 | Cost is negative | Reject as invalid | Critical | U |
| P2-40 | Cost is unreasonably high | Flag through an upper-bound quality rule without silently clamping | High | D |
| P2-41 | Cost includes decimals | Preserve decimal precision; format for display separately | Medium | U |
| P2-42 | Cost currency differs by row | Store row currency when evidenced; do not compare across currencies without conversion policy | Critical | D/I |
| P2-43 | Cost basis differs by row | Store explicit basis and prevent misleading budget comparisons across incompatible bases | Critical | D/I |
| P2-44 | Vote count contains suffixes such as `1.2K` | Parse only a documented format or store null | Medium | U |
| P2-45 | Vote count is negative or fractional | Reject or null with a quality reason | Medium | U |
| P2-46 | Rating is present but has zero votes | Keep rating but treat vote confidence carefully; do not invent confidence | Medium | U |
| P2-47 | Numeric field is `NaN` or infinity | Reject as non-finite and never serialize it to JSON | High | U/I |

### 6.5 Cuisine and Tag Normalization

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P2-48 | Cuisine field is empty | Store no cuisines and exclude when cuisine is a hard filter | High | U/I |
| P2-49 | Cuisine has duplicate values | Deduplicate while preserving stable display order | Medium | U |
| P2-50 | Cuisine uses mixed delimiters | Support only profiled delimiters and report unparsed residue | Medium | U |
| P2-51 | Cuisine contains aliases such as `North Indian` variants | Use a reviewed alias map; preserve original display lineage | High | D |
| P2-52 | Cuisine is a substring of another cuisine | Match normalized tokens, not substring text | High | U/I |
| P2-53 | Restaurant has dozens of cuisine labels | Enforce sensible processing/display limits without losing source traceability | Medium | D/E |
| P2-54 | Verified tag is inferred from restaurant name | Do not mark it verified without a documented rule and evidence | High | D |
| P2-55 | Tags contradict each other | Retain evidence and flag the row; do not let the LLM resolve factual contradictions | High | D |

### 6.6 Identity and Deduplication

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P2-56 | Source ID is missing | Generate a stable identity hash from approved normalized fields | High | U |
| P2-57 | Same source ID appears for different restaurants | Fail uniqueness or apply a documented source-specific disambiguation rule | Critical | D |
| P2-58 | Same restaurant has branches in multiple locations | Preserve separate branch records | High | D |
| P2-59 | Duplicate rows differ only in whitespace/case | Collapse deterministically | Medium | D |
| P2-60 | Duplicate rows disagree on rating or cost | Resolve using documented precedence, retain lineage, and report the conflict | High | D |
| P2-61 | Identity hash collision occurs | Detect the collision and add deterministic disambiguation; never overwrite | Critical | D |
| P2-62 | Reordered source rows generate different IDs | Stable IDs remain identical across runs | High | D |
| P2-63 | Restaurant is renamed in a later dataset version | Follow approved identity policy; do not accidentally merge unrelated businesses | Medium | D |

### 6.7 Artifact Publication and Database Loading

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P2-64 | Process crashes while writing Parquet | Temporary artifact remains unpublished; active snapshot is unchanged | Critical | O |
| P2-65 | Manifest hash does not match artifact | Publication fails | Critical | D |
| P2-66 | Manifest is missing required lineage fields | Publication fails | High | D |
| P2-67 | Database load fails halfway | Transaction rolls back completely | Critical | I |
| P2-68 | Index creation fails after load | New version is not activated | High | I |
| P2-69 | Two ingestion jobs attempt activation | Serialize activation and select exactly one complete version | Critical | O |
| P2-70 | API reads during dataset activation | Requests see either old or new complete version, never a mixed state | Critical | I/O |
| P2-71 | New dataset has an extreme row-count drop | Quality threshold blocks activation pending review | Critical | D |
| P2-72 | Rollback version is missing/corrupt | Activation is blocked until a valid recovery point exists, per release policy | High | O |
| P2-73 | SQLite database is locked | Retry only bounded transient failures and return a clear operational error | Medium | I |
| P2-74 | PostgreSQL and SQLite ordering differ on ties | Application applies an explicit deterministic secondary order | High | I |
| P2-75 | Migration is applied twice | Migration mechanism is idempotent or reports already applied safely | High | I |
| P2-76 | Older application reads a newer incompatible schema | Readiness fails instead of serving misinterpreted data | Critical | I |

## 7. Phase 3 — Deterministic Recommendation API Edge Cases

### 7.1 Request Validation

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P3-01 | Body is empty or malformed JSON | Return a stable 4xx validation error with request ID | Medium | I |
| P3-02 | Content type is unsupported | Return 415 or the documented validation response | Medium | I |
| P3-03 | Unknown top-level fields are supplied | Reject under strict schema or ignore only according to documented compatibility policy | Medium | I |
| P3-04 | Location is missing, null, empty, or whitespace | Reject as invalid | High | U/I |
| P3-05 | Location exceeds maximum length | Reject before database query | High | U/I |
| P3-06 | Location contains wildcard or SQL syntax | Treat as plain data and use parameterized queries | Critical | I |
| P3-07 | Location differs only by case or harmless whitespace | Normalize to the same query value | High | U/I |
| P3-08 | Location is well-formed but unavailable | Return no match or a validated suggestion; do not fuzzy-match silently | Medium | I |
| P3-09 | Budget band is unknown | Reject with allowed values | Medium | U/I |
| P3-10 | Custom maximum is negative, zero, non-finite, or non-numeric | Reject according to approved budget rules | High | U/I |
| P3-11 | Band and custom maximum conflict | Apply documented precedence or reject ambiguity; never choose silently | High | U/I |
| P3-12 | Currency differs from supported dataset currency | Reject or convert only through an explicit exchange-rate policy | Critical | U/I |
| P3-13 | Cuisine array is absent | Apply documented optional/default behavior | Medium | I |
| P3-14 | Cuisine array is empty | Treat as no cuisine constraint, if approved; do not match nothing accidentally | High | U/I |
| P3-15 | Cuisine array contains duplicates/case variants | Normalize and deduplicate | Medium | U/I |
| P3-16 | Cuisine count exceeds the cap | Reject before query/prompt construction | Medium | I |
| P3-17 | Cuisine contains an unknown value | Return no match or field validation based on contract; never substring-match | Medium | I |
| P3-18 | Minimum rating is below zero or above scale | Reject | High | U/I |
| P3-19 | Minimum rating has excessive decimal precision | Normalize or reject according to documented precision | Medium | U/I |
| P3-20 | Minimum rating is exactly a boundary | Include restaurants equal to the minimum | High | U/I |
| P3-21 | Optional preference is empty or whitespace | Normalize to absent | Low | U |
| P3-22 | Optional preference exceeds maximum length | Reject before logging or model use | High | I |
| P3-23 | Optional preference contains HTML/script | Treat as plain text, escape in UI, and never execute | Critical | I/E |
| P3-24 | Optional preference contains control characters or invalid Unicode | Reject or normalize safely; never break logs/JSON | High | U/I |
| P3-25 | Result limit is missing | Apply documented default | Low | U/I |
| P3-26 | Result limit is zero, negative, fractional, or above maximum | Reject | Medium | U/I |
| P3-27 | Request is extremely large | Reject through body-size and field limits before expensive processing | High | I |
| P3-28 | Same JSON key occurs multiple times | Parser behavior is documented; security tests verify no constraint ambiguity | High | I |

### 7.2 Filtering and Candidate Selection

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P3-29 | Restaurant has null rating and a minimum is set | Exclude it | Critical | U/I |
| P3-30 | Restaurant has null cost and a budget is set | Exclude it | Critical | U/I |
| P3-31 | Restaurant cost equals the maximum | Include it under an inclusive maximum rule | High | U/I |
| P3-32 | Restaurant rating equals the minimum | Include it | High | U/I |
| P3-33 | Restaurant matches location text but belongs to another city | Use structured normalized location/city policy; do not rely on broad substring search | Critical | I |
| P3-34 | Restaurant matches one of several requested cuisines under `any` policy | Include and score the proportion matched | High | U/I |
| P3-35 | Product rule changes to `all` cuisines | Require all normalized tokens and update contract tests | High | U/I |
| P3-36 | Cuisine is present only as part of another word | Do not match | High | U/I |
| P3-37 | No restaurant matches all hard filters | Return `NO_MATCHES` plus suggestions; do not silently relax | Critical | I/E |
| P3-38 | Only fewer results than requested match | Return all valid matches with accurate result count | Medium | I |
| P3-39 | Candidate query reaches its safety cap before scoring | Apply deterministic database ordering and expose an internal truncation metric | High | I/O |
| P3-40 | Active dataset changes during a request | Bind the request to one dataset version/snapshot | Critical | I/O |
| P3-41 | Requested location has trailing neighborhood qualifier | Apply only a documented hierarchy/alias rule | Medium | U/I |
| P3-42 | All matching restaurants lack cuisine display text | Return only if no cuisine filter is active; display unknown clearly | Medium | I/E |
| P3-43 | Data contains duplicate active IDs unexpectedly | Fail safely or deduplicate by ID; never return duplicate cards | Critical | I |

### 7.3 Scoring and Ordering

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P3-44 | All feature scores are equal | Use explicit stable tie-breakers | High | U |
| P3-45 | Score weight is negative, missing, or non-finite | Configuration validation fails at startup | High | U/I |
| P3-46 | Weights do not sum to one | Normalize only if explicitly designed; otherwise reject configuration | Medium | U |
| P3-47 | Rating scale differs from expected | Use row/source scale or fail data validation; do not compare raw incompatible ratings | Critical | U/D |
| P3-48 | Budget maximum is very high | Budget-fit score remains bounded and does not dominate unexpectedly | Medium | U |
| P3-49 | Exact budget fit versus much cheaper restaurant | Apply documented fit policy consistently | Medium | U |
| P3-50 | Optional preference has no evidence | Give zero evidence score and mark unverified | Critical | U/I |
| P3-51 | Votes are missing | Do not penalize as zero unless the scoring policy says so | Medium | U |
| P3-52 | Deterministic score calculation produces rounding ties | Round only for display; order with full decimal plus stable tie-break | High | U |
| P3-53 | Same request is repeated | Return identical deterministic order for the same active dataset/configuration | High | I |
| P3-54 | Database engine changes | Ordering remains stable through explicit sort fields | High | I |

### 7.4 API, Metadata, and Error Behavior

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P3-55 | Location autocomplete query is empty | Return a bounded default list or validation response per contract | Low | I |
| P3-56 | Autocomplete query is one common character | Enforce a result cap and deterministic ordering | Medium | I |
| P3-57 | Metadata cache belongs to an old dataset | Cache key/version invalidates it after activation | High | I |
| P3-58 | Cuisine metadata is requested for unknown location | Return an empty list, not a server error | Low | I |
| P3-59 | Database timeout occurs | Return a stable 5xx service error and log internal cause with request ID | High | I |
| P3-60 | Client disconnects during query | Cancel work where safe and avoid noisy false-error logging | Medium | O |
| P3-61 | Duplicate requests arrive concurrently | Process independently or use safe cache; never share mutable request state | High | I/O |
| P3-62 | Internal exception contains SQL or path details | Redact client response; retain safe diagnostic server-side | Critical | I |
| P3-63 | Request ID header is malicious or too long | Generate a trusted internal ID and sanitize any accepted external correlation ID | High | I |
| P3-64 | JSON serializer encounters decimal/date types | Serialize through the declared schema consistently | Medium | I |
| P3-65 | Response contains null optional fields | Use the documented representation consistently; UI handles it | Medium | I/E |
| P3-66 | Unsupported API version is requested | Return a stable 404/compatibility response, not a different schema | Medium | I |
| P3-67 | Readiness check is called at high frequency | Keep it lightweight and bounded | Medium | O |
| P3-68 | Error occurs after a partial response starts | Avoid streaming the MVP response; fail atomically | High | I |

## 8. Phase 4 — Web MVP Edge Cases

### 8.1 Form Inputs

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P4-01 | Metadata loads slowly | Show an accessible loading state and prevent invalid selection | Medium | E |
| P4-02 | Metadata request fails | Show retry guidance and do not replace the form with a blank screen | High | E |
| P4-03 | User types a location not in the selector | Validate against the chosen contract and explain how to select a supported location | Medium | E |
| P4-04 | User pastes leading/trailing whitespace | Normalize before validation/submission | Low | E |
| P4-05 | Cuisine options change after location changes | Clear or flag now-invalid selections explicitly | High | E |
| P4-06 | User selects many cuisines rapidly | Deduplicate state and submit only the final valid selection | Medium | E |
| P4-07 | Custom budget is selected without an amount | Show inline validation and block submission | Medium | E |
| P4-08 | Browser locale formats numbers with commas | Parse/display according to the supported locale without changing numeric value | Medium | E |
| P4-09 | Minimum rating control is keyboard-operated | Provide correct increments, labels, and value announcements | High | E |
| P4-10 | Optional text reaches its maximum | Show count and prevent excess input or return a clear validation message | Low | E |
| P4-11 | Browser autofill supplies stale values | Revalidate all fields before submission | Medium | E |
| P4-12 | JavaScript is disabled | Provide a basic unsupported message or document the requirement; never show a misleading working form | Low | E |

### 8.2 Submission and Async State

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P4-13 | User double-clicks submit | Send one active request | Medium | E |
| P4-14 | User changes filters while a request is pending | Cancel or mark the old response stale so it cannot overwrite newer results | High | E |
| P4-15 | Responses arrive out of order | Render only the response associated with the latest active request | Critical | E |
| P4-16 | User navigates away during a request | Cancel/ignore safely without state update errors | Medium | E |
| P4-17 | Network goes offline before submission | Show a recoverable connectivity message and preserve inputs | High | E |
| P4-18 | Network drops after submission | Show retry guidance and preserve inputs; do not duplicate silently | High | E |
| P4-19 | API returns validation errors after client validation passed | Map field errors safely and retain form values | Medium | E |
| P4-20 | API returns non-JSON error body | Show a generic safe error with request ID when available | Medium | E |
| P4-21 | Session receives a rate-limit response | Explain when to retry without exposing provider details | Medium | E |
| P4-22 | Browser refreshes on results page | Restore only non-sensitive state if designed; otherwise return to a clear initial state | Low | E |

### 8.3 Result Rendering

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P4-23 | Rating is unknown | Display `Rating unavailable`, not `0` | High | E |
| P4-24 | Cost is unknown | Display `Estimated cost unavailable`, not free | Critical | E |
| P4-25 | Cost basis is unknown | Avoid `for two` or `per person` wording | Critical | E |
| P4-26 | Restaurant name/cuisine is extremely long | Wrap or truncate accessibly without breaking layout | Medium | E |
| P4-27 | Restaurant text includes HTML | Render escaped text only | Critical | E |
| P4-28 | Explanation is absent in deterministic/failure mode | Show a grounded template explanation or omit the section cleanly | Medium | E |
| P4-29 | Unverified preferences exist | Display them separately from matched preferences | High | E |
| P4-30 | Fewer results than requested are returned | Show the actual count without filling with invalid alternatives | High | E |
| P4-31 | Results contain duplicate IDs due to upstream defect | Defensively avoid duplicate keys/cards and emit an error signal; backend defect remains release-blocking | High | E/I |
| P4-32 | Dataset version/freshness is missing | Do not fabricate it; show unavailable details and record contract violation | Medium | E |
| P4-33 | Currency uses a non-default symbol | Format using returned currency, not a hard-coded rupee symbol | High | E |
| P4-34 | Decimal cost/rating requires rounding | Preserve source value semantics and use consistent display precision | Medium | E |

### 8.4 Empty, Responsive, and Accessible States

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P4-35 | No exact matches exist | Show actionable suggestions without applying them automatically | Critical | E |
| P4-36 | User approves one relaxation | Resubmit with the exact visible change and record it in response metadata | High | E |
| P4-37 | User rejects suggestions | Preserve original filters and no-match state | Low | E |
| P4-38 | Screen reader receives new results | Announce result count once without reading the entire page unexpectedly | High | E |
| P4-39 | Error and loading state change rapidly | Manage live regions so announcements are accurate and not duplicated | Medium | E |
| P4-40 | Keyboard focus after submission | Move focus to an appropriate result/error heading or provide a predictable announcement | High | E |
| P4-41 | Modal/popover selector closes | Restore focus to its trigger | High | E |
| P4-42 | Text is zoomed to 200–400% | Content remains usable without two-dimensional scrolling for the core flow | High | E |
| P4-43 | Viewport is very narrow or landscape mobile | Controls and cards remain readable and tappable | Medium | E |
| P4-44 | User requests reduced motion | Disable nonessential transitions/animations | Medium | E |
| P4-45 | High-contrast or forced-colors mode is active | Focus, selection, errors, and buttons remain distinguishable | High | E |
| P4-46 | Color alone communicates matched/unverified state | Add text/icons with accessible labels | High | E |

## 9. Phase 5 — LLM Edge Cases

### 9.1 Prompt Construction and Injection

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P5-01 | User says `ignore prior instructions` | Treat it solely as preference text; model cannot expand candidates or alter rules | Critical | M |
| P5-02 | User asks for hidden prompts, keys, or system data | Model refuses/ignores; response schema contains recommendations only | Critical | M |
| P5-03 | User embeds JSON/XML delimiters in text | Proper serialization/delimiting prevents structure escape | Critical | U/M |
| P5-04 | Restaurant source text contains prompt-like instructions | Treat candidate fields as data, never instructions | Critical | M |
| P5-05 | Optional text requests a restaurant outside candidates | Return only supplied candidate IDs or fall back | Critical | M |
| P5-06 | Optional text conflicts with hard filters | Hard filters win; model cannot reintroduce excluded restaurants | Critical | M |
| P5-07 | Optional text asks for unsupported factual traits | Mark unverified; do not claim a match | Critical | M |
| P5-08 | Candidate set is empty | Do not call the model | High | U/I |
| P5-09 | Candidate set has one restaurant | Model may explain it, but must not add alternatives | High | M |
| P5-10 | Candidate prompt would exceed token cap | Reduce through documented deterministic truncation or skip to fallback | High | U/I |
| P5-11 | User input is in another language | Preserve safe text; generate in supported language policy or state limitations | Medium | M |
| P5-12 | Candidate names contain non-Latin text | Preserve IDs/text and validate output normally | Medium | M |

### 9.2 Model Output Validation

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P5-13 | Model returns prose instead of JSON | One bounded repair if allowed, then deterministic fallback | High | U/M |
| P5-14 | JSON is truncated or malformed | Repair once or fall back; never stream partial result | High | U/M |
| P5-15 | Required field is missing | Reject the model output | High | U/M |
| P5-16 | Unknown extra fields are returned | Reject or ignore under strict documented schema; never expose unsafe fields | Medium | U |
| P5-17 | Model returns an unknown restaurant ID | Reject entire model ranking and fall back | Critical | U/M |
| P5-18 | Model returns a valid ID twice | Reject or deterministically deduplicate only under documented policy; fallback preferred | High | U/M |
| P5-19 | Model omits some candidates | Accept if result count remains valid; hydrate only returned IDs | Medium | U |
| P5-20 | Model returns more than requested | Reject or safely truncate only after validating order and IDs | High | U |
| P5-21 | Model returns zero recommendations despite valid candidates | Treat as invalid and fall back | High | U/M |
| P5-22 | Model changes name, cost, rating, or cuisine | Ignore model factual fields; hydrate all facts from the database | Critical | U/M |
| P5-23 | Explanation states a wrong numeric value | Reject/sanitize through grounding checks and fall back if unsafe | Critical | M |
| P5-24 | Explanation claims family-friendly/quiet/fast service without evidence | Reject the claim or output; mark preference unverified | Critical | M |
| P5-25 | Explanation contains a URL not in source data | Reject or strip according to policy | High | M |
| P5-26 | Explanation contains markdown/HTML/script | Render as plain text and enforce content limits | Critical | U/E |
| P5-27 | Explanation is empty | Use grounded deterministic explanation or fall back | Medium | U |
| P5-28 | Explanation is excessively long | Reject or boundedly truncate only without changing meaning; prefer schema length enforcement | Medium | U/M |
| P5-29 | Explanation uses abusive or discriminatory language | Reject through content validation/policy and fall back | Critical | M |
| P5-30 | Model order violates a hard filter | Impossible candidates should not be present; validator rejects any violation | Critical | U/M |
| P5-31 | Model output has wrong types, nulls, or non-finite numbers | Schema validation fails and fallback runs | High | U |
| P5-32 | Model wraps JSON in code fences | Parser follows documented strict/repair behavior, then validates | Medium | U |
| P5-33 | Repair response introduces different IDs | Reject and fall back; repair never widens candidate set | Critical | U/M |
| P5-34 | Candidate dataset version changed before hydration | Hydrate from the request-bound version or discard and recompute | Critical | I |

### 9.3 Provider Failure and Fallback

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P5-35 | Provider times out | Cancel the call at the configured deadline and return deterministic fallback | High | I/M |
| P5-36 | Provider returns 429 | Honor bounded retry policy and fall back without exposing provider details | High | I |
| P5-37 | Provider returns transient 5xx | Retry at most as configured, then fall back | High | I |
| P5-38 | Provider authentication fails | Do not retry repeatedly; alert internally and fall back | Critical | I/O |
| P5-39 | Provider rejects the selected model | Record configuration failure and fall back | High | I/O |
| P5-40 | Provider safety filter blocks the request | Return deterministic fallback and safe telemetry | High | I/M |
| P5-41 | Network connection drops after request submission | Bound retry to avoid duplicated cost and fall back | High | I |
| P5-42 | Provider is very slow but succeeds after client disconnect | Cancel/ignore result and avoid writing shared state | Medium | O |
| P5-43 | Circuit breaker is open | Skip the provider immediately and return fallback | High | I/O |
| P5-44 | Circuit breaker half-open probe succeeds/fails | Transition state deterministically and avoid a traffic surge | High | O |
| P5-45 | Fallback template lacks optional explanation data | Use only verified features and remain grammatically correct | Medium | U/E |
| P5-46 | LLM flag is disabled at runtime | Deterministic mode works and reports the correct ranking mode | High | I |

### 9.4 Evaluation Edge Cases

Implementation clarifications added during Phase 5:

- A transient failure followed by invalid JSON shares one retry/repair budget: no third call.
- An older in-flight success must not close a circuit opened by newer failures.
- A provider response with unknown token usage must not be reported as a zero-cost call.
- A numeric claim using a valid number for the wrong purpose is still rejected by exact
  evidence-sentence validation, not accepted merely because the number appears in source facts.
- Evaluation pacing must satisfy the stricter of RPM and TPM; for the current Groq model, TPM is
  the binding limit. Scheduling waits stay outside measured model latency and its response deadline.
- Groq limits are organization-wide, so traffic from another process can still produce 429s during
  a paced run. Such fallbacks remain visible and cannot be removed from evaluation evidence.
- Repeated evaluation runs must also remain within RPD and TPD; pacing a single run does not reset
  daily allowances or authorize unlimited paid calls.
- A fake evaluation or unreviewed human-label template must never produce a release pass.
- A model's unexpected identity or changed prompt/schema content requires re-evaluation.

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P5-47 | Evaluation result is nondeterministic across runs | Use repeated trials and report variance; never hide regressions behind one run | Medium | M |
| P5-48 | Model or prompt changes without evaluation version update | CI/release gate fails | High | O |
| P5-49 | Evaluation set contains restaurants absent from active dataset | Pin dataset version or regenerate the case explicitly | High | M |
| P5-50 | LLM relevance improves but constraint violations appear | Reject the release; hard constraints take priority | Critical | M |
| P5-51 | Unsupported-claim rate is non-zero | Investigate and block according to zero-tolerance factual policy | Critical | M |
| P5-52 | Provider cost or latency spikes | Fail the configured release threshold or select deterministic mode/model adjustment | High | M/O |
| P5-53 | Evaluation covers only popular cities/cuisines | Expand cases before claiming general quality | Medium | M |
| P5-54 | Human relevance judges disagree | Record agreement and adjudicate rather than averaging away hard constraints | Medium | M |

## 10. Phase 6 — Hardening Edge Cases

### 10.1 Security and Privacy

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P6-01 | SQL injection payload appears in any filter | Parameterized query treats it as data | Critical | I |
| P6-02 | XSS payload appears in dataset or user text | API serializes safely and UI renders plain escaped text | Critical | I/E |
| P6-03 | Oversized nested JSON is submitted | Body/depth limits reject before expensive parsing | High | I |
| P6-04 | Request floods target metadata endpoints | Rate limits and caches protect the service | High | O |
| P6-05 | Distributed requests target the LLM endpoint | Rate limits/cost controls activate without leaking shared state | Critical | O |
| P6-06 | CORS request comes from an unknown origin | Production policy rejects it | High | I |
| P6-07 | Error message includes an environment variable or key | Redaction prevents client/log exposure | Critical | I/O |
| P6-08 | Optional preference contains email, phone, or other personal data | Do not log raw text by default; apply retention/redaction policy | Critical | I/O |
| P6-09 | Malicious value injects newlines into logs | Structured logging safely escapes it | High | I |
| P6-10 | Dependency has a critical vulnerability | Release gate fails until remediated or explicitly risk-accepted | Critical | O |
| P6-11 | Container runs with excessive privileges | Harden runtime and fail security review | High | O |
| P6-12 | Secret is present in frontend build-time environment | Build scan fails | Critical | O |
| P6-13 | Source URL uses an unsafe scheme | Allow-list `http`/`https` or omit link rendering | High | U/E |
| P6-14 | Host/header spoofing affects generated links | Use trusted configuration and proxy settings | High | I |

### 10.2 Observability

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P6-15 | Request has no inbound correlation ID | Generate one | Medium | I |
| P6-16 | Same request ID is reused maliciously | Keep trusted internal trace uniqueness | Medium | I |
| P6-17 | Metrics use restaurant/user text as labels | Review/test prevents high-cardinality or sensitive labels | High | O |
| P6-18 | Logging backend is unavailable | Request path degrades safely without crashing; local bounded behavior is defined | High | O |
| P6-19 | Token/cost metadata is missing from provider response | Record unknown rather than zero | Medium | I |
| P6-20 | Clock skew affects latency or timestamps | Use monotonic timing for durations and UTC for events | Medium | U/O |
| P6-21 | Alert fires repeatedly during a sustained outage | Deduplicate/rate-limit alerts while preserving incident visibility | Medium | O |
| P6-22 | Dataset activation occurs without metric update | Activation transaction/event updates observable version state | High | O |
| P6-23 | Health endpoint itself becomes expensive | Keep checks bounded and separate deep diagnostics | High | O |

### 10.3 Performance, Concurrency, and Storage

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P6-24 | Many users request a common location simultaneously | Pooling, indexes, and bounded concurrency meet target without correctness changes | High | O |
| P6-25 | Connection pool is exhausted | Queue/fail within a deadline and return a stable service error | High | O |
| P6-26 | One query becomes pathological | Database/application timeout cancels it and protects other requests | High | O |
| P6-27 | Cache stampede follows dataset activation | Versioned cache warmup/locking prevents overload | Medium | O |
| P6-28 | Cached response uses old dataset version | Versioned keys prevent stale cross-version results | Critical | I/O |
| P6-29 | Identical requests contain sensitive free text | Do not use unsafe shared caching; hash only under an approved privacy design | High | O |
| P6-30 | Redis/cache is unavailable | Fall back to database and remain correct | Medium | I/O |
| P6-31 | Database replica is stale after activation | Route version-sensitive reads appropriately or wait before activation | Critical | O |
| P6-32 | Disk usage grows from snapshots/logs | Retention and monitoring prevent exhaustion while preserving rollback minimums | High | O |
| P6-33 | Load test uses unrealistic hot-cache behavior | Test cold/warm caches and mixed locations separately | Medium | O |
| P6-34 | Client retries after timeout while original still runs | Requests remain idempotent/read-only and bounded | Medium | O |

### 10.4 Accessibility and Compatibility

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P6-35 | Browser lacks a nonessential modern feature | Core form/results degrade gracefully or supported-browser message appears | Medium | E |
| P6-36 | Screen reader/browser combination announces duplicate updates | Adjust live regions and focus strategy | High | E |
| P6-37 | Touch target is too small | Meet accessible target sizing for primary controls | Medium | E |
| P6-38 | RTL or long translated-like text appears | Layout does not overlap even if localization is post-MVP | Low | E |
| P6-39 | User has very slow CPU/network | Loading state remains responsive and requests remain cancellable | Medium | E |

## 11. Phase 7 — Deployment and Release Edge Cases

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| P7-01 | Container image builds differently on another machine | Lockfiles and pinned base image produce reproducible behavior | High | O |
| P7-02 | Production migration is incompatible with current app | Use expand/contract ordering or stop deployment before traffic switch | Critical | O |
| P7-03 | Migration succeeds but application deployment fails | Old app remains compatible or rollback procedure restores service | Critical | O |
| P7-04 | Application deploys before required dataset exists | Readiness blocks traffic and release verification fails | High | O |
| P7-05 | New dataset is valid but new app is not | Roll back the app or dataset to a tested compatible pair | Critical | O |
| P7-06 | Secret is missing or mounted at the wrong path | Deployment fails readiness with a safe diagnostic | High | O |
| P7-07 | Secret is rotated while instances run | New connections use rotation strategy without exposing or corrupting requests | High | O |
| P7-08 | DNS/TLS/CDN configuration is incorrect | Smoke checks fail before production promotion | Critical | O |
| P7-09 | Static client and API deploy versions are incompatible | Contract/version check blocks rollout or supports safe compatibility window | High | O |
| P7-10 | Rolling deployment serves mixed API versions | Maintain backward-compatible contracts during the rollout | High | O |
| P7-11 | Readiness passes before migrations/cache/data are ready | Readiness includes all serving prerequisites | Critical | O |
| P7-12 | Liveness is tied to external LLM health | Correct it so provider failure does not restart healthy instances | High | O |
| P7-13 | Rollback artifact or image is unavailable | Block promotion until a verified rollback target exists | Critical | O |
| P7-14 | Backup exists but cannot be restored | Release/recovery gate fails until restore is rehearsed | Critical | O |
| P7-15 | Production smoke test creates excessive LLM cost | Use a bounded tagged test and cleanly report it | Medium | O |
| P7-16 | Deployment is interrupted halfway | Automation resumes or rolls back idempotently | Critical | O |
| P7-17 | Multiple operators trigger a deployment | Concurrency control permits one promotion at a time | High | O |
| P7-18 | Observability is unavailable after deployment | Stop promotion or roll back according to release policy | High | O |
| P7-19 | Dataset license/attribution is omitted in production | Release gate fails | Critical | O |
| P7-20 | Production configuration uses development CORS/debug settings | Configuration validation/security check fails | Critical | O |
| P7-21 | System clock/time zone differs between services | Persist UTC and render localized time only at UI boundaries | Medium | O |
| P7-22 | Rollback restores app but not compatible schema/data | Use a version compatibility matrix and rehearse paired rollback | Critical | O |

## 12. Cross-Cutting Business Edge Cases

| ID | Scenario | Expected behavior | Severity | Test |
|---|---|---|---|---|
| X-01 | User requests contradictory cuisines or preferences | Apply explicit hard cuisine semantics; describe soft conflicts without inventing a resolution | Medium | I/M |
| X-02 | User asks for a rating higher than the dataset scale | Reject with the valid scale | High | U/I |
| X-03 | User asks for a budget below every valid restaurant | Return no match and transparent suggestions | High | I/E |
| X-04 | User expects live price/opening/availability | UI disclosure states dataset limitations and avoids live claims | High | E |
| X-05 | Two restaurants share the same display name | Show location/branch context and retain distinct IDs | High | I/E |
| X-06 | Restaurant data is stale | Display dataset freshness/version and do not present as real-time | High | E |
| X-07 | Highly rated restaurant has very few votes | Apply documented confidence/tie-break policy without hiding the rating | Medium | U/M |
| X-08 | Popularity systematically crowds out relevant cuisine/budget matches | Hard constraints and feature weights preserve relevance; evaluation monitors distribution | High | M |
| X-09 | There are valid matches but all have unknown optional traits | Return them with those traits marked unverified | High | I/M |
| X-10 | User enters dietary/allergen requirements | Treat as unsupported unless verified data exists; never assert safety | Critical | I/M/E |
| X-11 | User asks for exact distance/travel time without geospatial data | Do not estimate; state it cannot be verified | High | M/E |
| X-12 | User asks for "best" with no rating/cuisine/budget | Apply a documented default ranking and explain its basis | Medium | U/I |
| X-13 | No cuisine is selected | Follow documented no-cuisine-filter behavior consistently | Medium | I/E |
| X-14 | Results span incompatible cost bases | Avoid direct ranking/comparison or label clearly according to policy | Critical | I/E |
| X-15 | Source data contains a closed restaurant | Unless source supplies closure status, do not claim it is open; disclose freshness | High | D/E |

## 13. Minimum Boundary-Value Test Matrix

Each numeric/string limit requires tests immediately below, at, and immediately above the boundary.

| Field/control | Minimum cases |
|---|---|
| Location | missing, empty, whitespace, 1 character, maximum length, maximum plus 1, Unicode, unavailable value |
| Cuisine list | missing, empty, 1 value, duplicate values, maximum count, maximum plus 1, unknown value |
| Minimum rating | null, 0, valid minimum, exact restaurant rating, maximum scale, below 0, above scale, non-finite |
| Budget maximum | null, 0, band boundary minus 1, exact boundary, boundary plus 1, negative, decimal, non-finite |
| Optional preference | missing, empty, whitespace, maximum length, maximum plus 1, HTML, prompt injection, invalid Unicode |
| Result limit | missing/default, 1, maximum, 0, negative, fractional, maximum plus 1 |
| Cost parser | null, zero, decimal, separators, currency symbol, range, negative, huge value, unknown currency/basis |
| Rating parser | null, numeric, decimal, `/5`, `NEW`, `-`, negative, above scale, `NaN`, infinity |

## 14. Required Composite Scenarios

Single-field tests are insufficient. The following combinations must be represented in integration, browser, or evaluation suites:

1. Exact location, cuisine, rating boundary, and budget boundary all match one restaurant.
2. Location/cuisine match but cost is unknown while budget is active.
3. Location/budget match but rating is unknown while minimum rating is active.
4. Multiple cuisines with partial matches under the approved `any` policy.
5. No exact matches with several possible relaxations; none applied automatically.
6. Valid deterministic candidates plus prompt-injection text.
7. Valid candidates plus unsupported family-friendly/quiet/quick-service preferences.
8. LLM returns valid IDs in a different order with grounded explanations.
9. LLM returns one unknown ID mixed with valid IDs; entire model result is rejected.
10. LLM times out after deterministic scoring; fallback order and facts remain correct.
11. Dataset activates while concurrent recommendation requests are running.
12. Metadata cache is populated before dataset activation and queried afterward.
13. Two restaurants have identical scores, names, and ratings but different stable IDs.
14. User submits twice, changes filters, and receives network responses out of order.
15. Mobile keyboard-only/screen-reader flow reaches form errors and updated results.
16. Database slows down while provider is healthy; deadline still bounds the entire request.
17. Provider fails repeatedly, circuit opens, and deterministic results continue.
18. New ingestion fails its quality gate while the existing application serves the previous dataset.
19. Application rollback occurs after a database migration and dataset activation.
20. Source text and user text both contain hostile markup/instructions; neither executes or overrides policy.

## 15. Edge-Case Test Data Rules

- Use small, versioned synthetic fixtures for malformed and adversarial rows.
- Include at least two cities, repeated location names, branches, duplicate names, and multi-cuisine restaurants.
- Include null and malformed ratings/costs without altering the production dataset.
- Include Unicode, emoji, non-Latin scripts, punctuation, and long values.
- Include verified and unsupported preference tags.
- Never place real secrets or unnecessary personal data in fixtures or snapshots.
- Keep expected normalized records and scores explicit so regressions are reviewable.
- Pin dataset, configuration, prompt, and model versions for evaluation results.
- Seed or mock nondeterministic components in unit/integration tests.
- Run a smaller critical suite on every change and the complete live-model/operational suite before release.

## 16. Triage Rules

When an edge case fails:

1. Stop release immediately for any invariant, Critical, data-publication, hard-filter, secret-exposure, unknown-ID, or unsupported-factual-claim failure.
2. Record the request ID, dataset version, application version, prompt version, and model version where applicable.
3. Reduce the failure to a safe fixture or fake-model response.
4. Add a deterministic regression test before or with the fix.
5. Update this catalogue if the scenario or expected behavior was previously missing or ambiguous.
6. Re-run the affected phase gate plus all invariant tests.

## 17. Edge-Case Release Gate

The release is blocked until:

- [ ] Every Critical case applicable to the release has an automated test or rehearsed operational check.
- [ ] All invariant tests pass with zero exceptions.
- [ ] Dataset failure and rollback scenarios preserve the last valid active version.
- [ ] Numeric and length boundary suites pass.
- [ ] No-match behavior never relaxes constraints silently.
- [ ] LLM tests show zero unknown restaurant IDs and zero hard-filter violations.
- [ ] Unsupported restaurant traits, dietary claims, and live availability are never asserted without evidence.
- [ ] Timeout, malformed-output, provider-outage, and circuit-breaker cases return deterministic fallback.
- [ ] Async UI tests prove stale responses cannot replace current results.
- [ ] Security tests cover injection, XSS, oversized input, secrets, CORS, and rate limits.
- [ ] Accessibility tests cover keyboard, focus, announcements, contrast, zoom, and reduced motion.
- [ ] Deployment tests cover migration compatibility, partial failure, rollback, restore, and version pairing.
- [ ] Any deferred Medium/Low case has an owner, reason, and tracked follow-up.
