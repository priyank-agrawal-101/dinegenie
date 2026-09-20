# Zomato Dataset Profile

## Status

- Profile date: 2026-09-13
- Phase: 0 — Discovery and Architecture Decisions
- Dataset: `ManikaSaini/zomato-restaurant-recommendation`
- Repository: <https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation>
- Pinned source commit: `5738e9eda2fad49ad51c6e0ed26e761d9b947133`
- Access: public, not gated, not disabled
- Configuration: `default`
- Split: `train`
- Profile status: accepted for implementation discovery
- Production-use status: blocked until dataset licensing/attribution rights are clarified

## Evidence and Method

This profile was created from the live Hugging Face repository metadata, dataset-server split/size/statistics endpoints, and selected rows returned by the dataset-server row APIs. The data was inspected read-only; the complete source CSV was not copied into this repository.

Official endpoints used:

- Repository metadata: <https://huggingface.co/api/datasets/ManikaSaini/zomato-restaurant-recommendation>
- Splits: <https://datasets-server.huggingface.co/splits?dataset=ManikaSaini%2Fzomato-restaurant-recommendation>
- Size: <https://datasets-server.huggingface.co/size?dataset=ManikaSaini%2Fzomato-restaurant-recommendation>
- Statistics: <https://datasets-server.huggingface.co/statistics?dataset=ManikaSaini%2Fzomato-restaurant-recommendation&config=default&split=train>
- Rows: <https://datasets-server.huggingface.co/rows?dataset=ManikaSaini%2Fzomato-restaurant-recommendation&config=default&split=train>

The dataset server reported `partial: false` for its size and statistics results. Exact post-normalization uniqueness and full-dataset duplicate counts remain Phase 2 pipeline outputs because the remote filtering index did not complete successfully during this profile.

## Repository and Size Summary

| Property | Observed value |
|---|---|
| Repository files | `.gitattributes`, `zomato.csv` |
| Dataset card/README | Not present |
| License metadata/tag | Not present |
| Rows | 51,717 |
| Columns | 17 |
| Original data bytes reported by dataset server | 574,072,999 bytes |
| Converted Parquet bytes | 151,552,748 bytes across two files |
| In-memory bytes estimated by dataset server | 575,611,664 bytes |
| Repository `usedStorage` reported by Hub API | 725,625,747 bytes |
| Configurations | `default` |
| Splits | `train` |
| Last modified reported by Hub API | 2026-01-12T13:10:17Z |

The differing byte totals describe different storage representations and should not be treated as contradictory.

## Coverage Finding

The data is a Bengaluru/Bangalore restaurant snapshot, not a multi-city India dataset:

- Sample source URLs use the `/bangalore/` path.
- Sample addresses end in Bangalore.
- `location` contains 93 Bengaluru localities such as BTM, Indiranagar, Whitefield, and Jayanagar.
- `listed_in(city)` contains 30 browsing/listing zones such as Banashankari and Koramangala blocks. Despite its name, this is not a true city field.

MVP consequence: the UI must present Bengaluru coverage and use `location` as a locality filter. A Delhi search cannot be fulfilled by this source and must not silently return Bengaluru restaurants.

## Source Schema Profile

Null statistics are exact values returned by the Hugging Face statistics endpoint for all 51,717 rows.

| Source column | Source type | Null count | Null % | Observed profile and interpretation |
|---|---:|---:|---:|---|
| `url` | string | 0 | 0.000% | Zomato URL, 180–538 characters; query contains listing context |
| `address` | string | 0 | 0.000% | 6–346 characters; branch/location evidence |
| `name` | string | 0 | 0.000% | 2–159 characters |
| `online_order` | string label | 0 | 0.000% | `Yes`: 30,444; `No`: 21,273 |
| `book_table` | string label | 0 | 0.000% | `Yes`: 6,449; `No`: 45,268 |
| `rate` | string label | 7,775 | 15.034% | 64 raw labels due to spacing variants plus `NEW` and `-` |
| `votes` | int64 | 0 | 0.000% | Min 0, max 16,832, mean 283.70, median 41 |
| `phone` | string | 1,208 | 2.336% | May contain multiple numbers/newlines; not needed for MVP serving |
| `location` | string label | 21 | 0.041% | 93 distinct locality labels |
| `rest_type` | string label | 227 | 0.439% | 93 raw values/combinations |
| `dish_liked` | string | 28,078 | 54.292% | Very sparse; 2–134 characters when present |
| `cuisines` | string | 45 | 0.087% | Comma-separated; 3–86 characters when present |
| `approx_cost(for two people)` | string label | 346 | 0.669% | 70 raw values; comma-formatted numeric INR amounts |
| `reviews_list` | string | 0 | 0.000% | Serialized reviews; 2–1,284,117 characters; `[]` is not null |
| `menu_item` | string | 0 | 0.000% | Serialized menu data; median length 2 indicates many `[]` values |
| `listed_in(type)` | string label | 0 | 0.000% | 7 listing categories |
| `listed_in(city)` | string label | 0 | 0.000% | 30 listing zones; not a true city field |

## Rating Profile

- Rating scale: 5, encoded as strings such as `4.1/5` and `4.1 /5`.
- Valid numeric range observed: 1.8–4.9.
- Valid numeric rating rows: 41,665.
- Mean among parseable numeric ratings: approximately 3.700.
- Null rows: 7,775.
- `NEW` rows: 2,208.
- `-` rows: 69.
- Total unrated/unusable for a minimum-rating filter: 10,052 rows.

Normalization rule:

1. Trim whitespace.
2. Treat null, empty, `NEW`, and `-` as unknown.
3. Remove an optional whitespace-separated `/5` suffix.
4. Parse with decimal semantics.
5. Reject values outside 0–5.
6. Preserve the original string for lineage but serve the parsed decimal.

`NEW` is not rating zero and must not be treated as below-average evidence when no minimum rating is supplied.

## Cost Profile

The source column explicitly names the basis as **for two people**. Values are consistent with Indian rupee amounts for Bengaluru restaurants; the MVP records currency as `INR` based on the India/Bengaluru source context.

- Present rows: 51,371.
- Missing rows: 346.
- Distinct raw values: 70.
- Minimum parsed amount: ₹40.
- Maximum parsed amount: ₹6,000.
- Formatting includes thousands separators, for example `1,500`.

Distribution under the MVP budget bands:

| Band | Rule | Rows with known cost | Share of known-cost rows |
|---|---|---:|---:|
| Low | `cost <= 600` | 37,759 | 73.50% |
| Medium | `600 < cost <= 1,500` | 11,833 | 23.03% |
| High | `cost > 1,500` | 1,779 | 3.46% |

Normalization rule:

1. Trim whitespace.
2. Remove comma group separators.
3. Parse as a non-negative decimal.
4. Store `currency = INR` and `cost_basis = for_two` for this pinned mapping.
5. Keep missing values null.
6. Do not compare records with unknown or incompatible currency/basis.

## Location and City Mapping

| Concept | Decision |
|---|---|
| User-facing city | `Bengaluru` for this dataset version |
| Searchable locality | Source `location` |
| Listing zone | Source `listed_in(city)`, retained as `listing_zone` only |
| Address | Source `address` |

`listed_in(city)` must not populate canonical `city`; values such as `Koramangala 6th Block` show that it represents a listing page/zone. Phase 2 must verify the Bangalore URL/address assumption across the complete source before assigning the constant canonical city.

## Duplicate and Identity Findings

The source is denormalized around Zomato listing contexts. A verified sample duplicate demonstrates the pattern:

- Source rows 2 and 14 are the same `San Churro Cafe` branch.
- Both have the same name, address, locality, rating, votes, cost, cuisines, restaurant type, online-order flag, table-booking flag, and URL path `/SanchurroBangalore`.
- They differ in `listed_in(type)` (`Buffet` versus `Cafes`) and in the URL's `context` query parameter.

Identity decision:

1. Retain the complete raw source URL for lineage.
2. Derive `source_identity_path` from the URL host/path after removing query and fragment, normalizing host case, and removing a trailing slash.
3. Use the normalized source URL path as the preferred source identity when present.
4. Use a SHA-256 hash of normalized `name + address + location` as a fallback identity only when no usable URL path exists.
5. Preserve genuinely distinct branches even when names match.
6. Merge duplicate listing rows deterministically, union multi-valued classifications, and record all source row references.
7. Treat conflicting factual values as a data-quality conflict, not a value the LLM may resolve.

The Phase 2 full ingestion report must quantify exact duplicate groups and conflicts. Phase 0 establishes the observed pattern and stable-identity strategy, not the final count.

## Optional Preferences Supported by Source Evidence

| Preference | Evidence source | MVP status |
|---|---|---|
| Online ordering | `online_order` | Verified structured filter/tag |
| Table booking | `book_table` | Verified structured filter/tag |
| Restaurant format/type | `rest_type` | Verified after token normalization |
| Listing category | `listed_in(type)` | Verified classification, not a quality claim |
| Liked dishes | `dish_liked` | Display/search signal only when present; 54.292% missing |
| Specific cuisine | `cuisines` | Verified structured filter after tokenization |
| Family-friendly | Only anecdotal review text | Unsupported as a verified MVP attribute |
| Quick service | Only anecdotal review text | Unsupported as a verified MVP attribute |
| Quiet/romantic/good ambience | Only anecdotal review text | Unsupported as a verified MVP attribute |
| Dietary/allergen safety | No reliable structured evidence | Unsupported; never assert safety |
| Current open/closed status | No verified current field | Unsupported; never claim live availability |

`reviews_list` is excluded from MVP recommendation and prompt inputs. It is unstructured user-authored content, extremely large, occasionally encoding-corrupted, and may contain personal data or prompt-like text. Using it later requires a separate privacy, safety, extraction, and evidence design.

## Proposed Source-to-Canonical Mapping

| Canonical field | Source/derivation | Required | Transformation |
|---|---|---:|---|
| `id` | Derived | Yes | Stable internal ID from normalized source identity |
| `source_id` | URL path | Yes after derivation | Normalize host/path; strip query and fragment |
| `source_row_ids` | Dataset row indexes | Yes | Preserve all merged row references |
| `name` | `name` | Yes | Trim/collapse whitespace; preserve Unicode |
| `city` | Dataset scope | Yes | `Bengaluru`, after whole-source validation |
| `location_display` | `location` | Yes | Trim/collapse whitespace |
| `location_normalized` | `location` | Yes | Unicode normalize and case-fold |
| `listing_zones` | `listed_in(city)` | No | Union values across duplicate rows |
| `address` | `address` | Yes | Trim/collapse whitespace |
| `cuisines` | `cuisines` | No | Split on reviewed delimiter, trim, alias-map, deduplicate |
| `cost_amount` | `approx_cost(for two people)` | No | Remove commas and parse decimal |
| `currency` | Dataset scope | With known cost | `INR` |
| `cost_basis` | Column semantics | With known cost | `for_two` |
| `rating` | `rate` | No | Parse numeric `/5`; null for null/`NEW`/`-` |
| `rating_scale` | Column semantics | With known rating | `5` |
| `votes` | `votes` | No | Validate non-negative integer |
| `restaurant_types` | `rest_type` | No | Split reviewed combinations and deduplicate |
| `online_order` | `online_order` | Yes | Strict `Yes`/`No` to boolean |
| `book_table` | `book_table` | Yes | Strict `Yes`/`No` to boolean |
| `liked_dishes` | `dish_liked` | No | Tokenize only for display/search; do not infer traits |
| `listing_types` | `listed_in(type)` | No | Union values across duplicate rows |
| `source_url` | `url` | Yes | Retain raw value for lineage; validate safe HTTPS before linking |
| `dataset_version` | Pinned commit + artifact hash | Yes | Assigned during publication |
| `ingested_at` | Pipeline clock | Yes | UTC timestamp |

Excluded from the MVP serving model: `phone`, `reviews_list`, and `menu_item`. They may remain in the immutable raw source but should not be copied into the recommendation database without a later approved use case.

## Data-Quality Rules for Phase 2

Publication must fail when:

- Any required source column is absent.
- No valid rows remain.
- A stable ID collision remains unresolved.
- The new row count drops materially beyond the approved threshold.
- Parsed rating/cost validity drops materially from this baseline.
- Values violate canonical range/type rules.
- Artifact and manifest hashes disagree.
- Activation would produce a mixed or partial dataset version.

The baseline null percentages in this document should be used as drift references, not permanent acceptance thresholds.

## Representative Sample

The repository includes [zomato-phase0-sample.csv](../data/samples/zomato-phase0-sample.csv), containing eight selected, non-sensitive source observations. It excludes phone numbers, review text, menus, and volatile URL query strings. It includes a confirmed duplicate listing pair for identity testing.

The sample is suitable for Phase 0 documentation and early mapping tests. Phase 2 should add purpose-built synthetic fixtures for nulls, `NEW`, `-`, malformed values, Unicode, conflicts, and failure cases.

## Risks and Open Blockers

### Production Licensing Blocker

The repository metadata contains no license tag and the repository exposes no dataset card or license file. This confirms that licensing is **unspecified**, not that the data is free for production use. Production deployment, redistribution, or commercial use must remain blocked until the owner/source supplies terms that permit the intended use.

### Data Freshness

No reliable observation date or refresh cadence is supplied. The product must identify the dataset as a static snapshot and must not claim current price, opening status, or availability.

### Source Fidelity

The data includes duplicate listing contexts, substantial missing ratings and liked dishes, and observed character-encoding corruption inside review content. These constraints are reflected in the canonical mapping and product rules.
