# MVP Product Rules

## Status and Scope

- Status: accepted implementation baseline for Phase 0
- Effective date: 2026-09-13
- Applies to: the initial Zomato restaurant recommendation MVP
- Source profile: [data-profile.md](data-profile.md)

These rules resolve the product decisions listed in Phase 0 of [implementation-plan.md](../implementation-plan.md). They can be changed later through an explicit product decision and matching contract/test updates.

## 1. Dataset Coverage

- The initial dataset covers Bengaluru/Bangalore only.
- The required location input means a Bengaluru locality, using the source `location` field.
- The UI must state that coverage is Bengaluru.
- `listed_in(city)` is a listing zone, not the canonical city.
- Unsupported cities such as Delhi return no coverage guidance; they never fall back silently to Bengaluru.
- Data is a static snapshot. The application must not claim current opening status, availability, menus, or prices.

## 2. Input Rules

| Input | MVP rule |
|---|---|
| Location | Required; one locality selected from active dataset metadata |
| Budget | Required; one band or an optional supported custom maximum |
| Cuisine | Optional multi-select; empty means no cuisine constraint |
| Minimum rating | Optional; `Any` means no rating constraint; otherwise 0–5 using one decimal place |
| Additional preferences | Optional free text, maximum 300 characters |
| Result count | Default 5; minimum 1; maximum 10 |

All user input is untrusted data. It is validated, length-limited, normalized, and never interpreted as system/model instructions.

## 3. Cuisine Matching

- Multiple selected cuisines use **any-match** semantics for MVP eligibility.
- A restaurant is eligible when at least one normalized cuisine token matches.
- Ranking rewards a higher proportion of selected cuisines matched.
- Matching uses whole normalized cuisine tokens, not substrings.
- Aliases are allowed only through a reviewed mapping.
- The UI must say `Matches any selected cuisine` when multiple cuisines are selected.
- A future all-match option requires an explicit contract and UI change.

Examples:

| Requested | Restaurant cuisines | Eligible | Reason |
|---|---|---:|---|
| Italian, Chinese | Italian, Cafe | Yes | Matches Italian |
| Italian, Chinese | North Indian, Chinese | Yes | Matches Chinese |
| Italian, Chinese | Thai, Cafe | No | Matches neither |
| No cuisine | Thai, Cafe | Yes | No cuisine constraint |

## 4. Budget Rules

The source is interpreted as estimated INR cost **for two people**.

| Band | Inclusive rule |
|---|---|
| Low | `cost <= ₹600` |
| Medium | `₹600 < cost <= ₹1,500` |
| High | `cost > ₹1,500` |

- Boundary values belong to exactly one band: ₹600 is low; ₹1,500 is medium.
- A custom maximum, if offered, means `cost <= maximum` and takes precedence over the band after the UI makes that choice explicit.
- Zero, negative, non-finite, and unsupported-currency custom values are invalid.
- The UI label is `Estimated cost for two`.
- A restaurant with unknown cost is excluded whenever a budget constraint is active.
- Currency conversion is out of scope for MVP.

The bands cover the profiled known-cost rows as follows: 37,759 low, 11,833 medium, and 1,779 high. These are product bands, not universal affordability claims.

## 5. Rating Rules

- Ratings use a 5-point scale.
- The minimum-rating constraint is inclusive: a 4.0 restaurant is eligible for a minimum of 4.0.
- Parsed values are compared as decimals.
- Null, empty, `NEW`, and `-` mean unknown, not zero.
- A restaurant with unknown rating is excluded when a minimum rating is active.
- A restaurant with unknown rating may be eligible when the user selects `Any`, but the UI displays `Rating unavailable`.
- Votes may be used as a confidence/tie-break signal but never overwrite or fabricate a rating.

## 6. Optional Preference Rules

MVP optional preferences use a free-text field rather than a predefined tag selector. The text can influence explanations/reranking only within verified candidate facts.

Verified source-backed attributes available for future structured controls:

- Online ordering.
- Table booking.
- Restaurant type.
- Listing type.
- Liked dishes when present.

Not verified for MVP:

- Family-friendly.
- Quick service.
- Quiet, romantic, or good ambience.
- Dietary or allergen safety.
- Accessibility features.
- Live availability or opening status.

Required wording pattern for unsupported preferences:

> The dataset does not verify whether this restaurant is {preference}.

Example:

> The dataset does not verify whether this restaurant is family-friendly or offers quick service.

The system may say that a restaurant matches cuisine, cost, rating, locality, online ordering, table booking, or another source-backed property. It must not convert a review anecdote or model assumption into a verified attribute.

## 7. Candidate Filtering

Hard filters are applied in this order:

1. Active dataset version.
2. Exact normalized locality.
3. Known cost satisfying the selected budget rule.
4. Known rating satisfying the optional minimum.
5. Any-match cuisine constraint, when selected.

Order is an implementation optimization; all active hard filters have equal authority. The LLM cannot override them.

## 8. Ranking Rules

Deterministic ranking is always available. The initial weights are:

```text
0.35 rating score
0.30 cuisine match score
0.20 budget fit score
0.15 verified preference evidence score
```

- Scores remain between 0 and 1.
- Unknown optional evidence scores zero rather than negative.
- Stable tie-break order: total score descending, rating descending with unknown last, votes descending, then stable restaurant ID ascending.
- Model-assisted ranking can reorder only the bounded deterministic candidate set.
- Return no more than the requested count.

Weights are configuration but changes require ranking tests and evaluation results.

## 9. Result Rules

Default result count is 5; maximum is 10.

Every result contains:

- Stable restaurant ID.
- Restaurant name.
- Locality and Bengaluru city context.
- Cuisines, or `Cuisine unavailable`.
- Rating, or `Rating unavailable` when no minimum-rating filter is active.
- Estimated INR cost for two, or `Estimated cost unavailable` only when no budget filter is active.
- A short grounded explanation.
- Matched preferences.
- Unverified preferences.

The API also returns request ID, dataset version, candidate count, ranking mode, and any explicitly applied relaxations.

## 10. No-Match and Relaxation Rules

- No hard filter is relaxed silently.
- The initial response returns `NO_MATCHES` with suggested changes.
- The user must approve a relaxation before a broader search runs.
- Suggested order: broaden cuisine, lower minimum rating by a configured step, then raise budget by a configured percentage.
- Nearby-area expansion is not offered until reliable geospatial mapping exists.
- Every applied change appears in `meta.filters_relaxed` and remains visible in the UI.

## 11. LLM Rules

- The LLM receives only the top 10–20 deterministic candidates.
- It returns candidate IDs and grounded explanation fields through a strict schema.
- It cannot create restaurant IDs or factual display values.
- Backend code validates IDs, count, uniqueness, lengths, and claims before hydration.
- One bounded repair may be attempted for recoverable schema errors.
- Any timeout, provider error, invalid output, unknown ID, unsupported claim, or exhausted repair produces deterministic fallback.
- The application remains usable without LLM credentials when LLM mode is disabled.
- Phase 5's initial grounding policy lets the model select/order approved source-backed
  explanation sentences, not invent or freely paraphrase factual claims. Matched and unverified
  preference lists remain backend-owned. See [ADR-005](adr/ADR-005-grounded-groq-ranking.md).

## 12. Privacy and Content Rules

- `phone`, `reviews_list`, and `menu_item` are excluded from the MVP serving database and LLM prompt.
- Raw optional-preference text is not logged by default.
- Restaurant/source strings are rendered as plain escaped text.
- Dietary and allergen requests receive a limitation message; the system never asserts safety from this dataset.
- Dataset licensing must be clarified before production distribution/use.

## 13. Boundary Examples

| Case | Expected behavior |
|---|---|
| Cost ₹600 with low budget | Included |
| Cost ₹600 with medium budget | Excluded |
| Cost ₹1,500 with medium budget | Included |
| Cost ₹1,501 with medium budget | Excluded |
| Rating 4.0 with minimum 4.0 | Included |
| Rating 3.9 with minimum 4.0 | Excluded |
| Rating `NEW` with minimum 4.0 | Excluded |
| Missing cost with any budget band | Excluded |
| Italian/Chinese requested; Italian/Cafe restaurant | Included |
| Delhi requested | Unsupported coverage; no Bengaluru substitution |
| Family-friendly requested without evidence | May recommend on verified filters, but labels the preference unverified |
| LLM unavailable | Return deterministic recommendations |

## 14. MVP Technical Baseline

- Architecture: modular monolith.
- Local database: SQLite.
- Production database: PostgreSQL when deployed beyond the local prototype.
- Local runtime: Docker Compose or documented native commands.
- Production shape: static web hosting/CDN, stateless API container, managed PostgreSQL, versioned object storage, and secret manager.
- Development web origins: `http://localhost:5173` and `http://127.0.0.1:5173`.
- Production web origins: explicit environment-specific HTTPS origins only; wildcard origins are forbidden.
- End-user authentication: excluded from MVP.
- Public API protection: validation, request/body limits, rate limiting, and no state-changing public ingestion endpoint.
- Initial LLM integration: Groq through a provider-neutral gateway. The concrete Groq model remains unset until Phase 5 evaluates the then-current model catalogue; no API key is used during Phases 2–4.
- Phase 5 implementation is available, but the live model and release evaluation are not yet
  approved. `APP_LLM_MODEL` intentionally has no default; Groq access and live evaluation must
  be confirmed before enabling the feature for use beyond testing.

## 15. Change Control

A change to data coverage, budget thresholds, matching semantics, hard filters, verified attributes, ranking weights, LLM authority, or fallback behavior requires:

1. Product-rule update.
2. API/UI contract review when applicable.
3. Updated boundary and regression tests.
4. Updated evaluation results for ranking/prompt/model changes.
5. Architecture/ADR update when the decision's rationale changes.
