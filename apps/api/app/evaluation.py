"""Versioned offline/live evaluation. Never promotes fake results to a release pass."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import __version__
from app.api.contracts import RecommendationRequest, RecommendationResponse
from app.core.config import Settings
from app.core.errors import NoMatchesError
from app.llm.contracts import PROMPT_VERSION, SCHEMA_VERSION, ModelRanking
from app.llm.fake import FakeRecommendationModel
from app.llm.gateway import ModelGateway
from app.llm.groq import GroqRecommendationModel
from app.llm.prompt import SYSTEM, validate_output
from app.recommendations.orchestrator import recommend_with_model
from app.recommendations.service import prepare_recommendations
from app.repositories.sqlite import SQLiteRestaurantRepository

GROQ_BASE_REQUESTS_PER_MINUTE = 30
GROQ_BASE_TOKENS_PER_MINUTE = 8_000
EVALUATION_TOKENS_PER_REQUEST = 1_500
EVALUATION_RATE_LIMIT_HEADROOM = 0.90


def recommended_live_interval_seconds() -> float:
    """Conservatively pace the current Groq model under its published base limits."""

    rpm_interval = 60 / GROQ_BASE_REQUESTS_PER_MINUTE
    token_interval = (
        60
        * EVALUATION_TOKENS_PER_REQUEST
        / (GROQ_BASE_TOKENS_PER_MINUTE * EVALUATION_RATE_LIMIT_HEADROOM)
    )
    return max(rpm_interval, token_interval)


def next_request_delay(last_started: float | None, interval: float, now: float) -> float:
    """Return scheduler wait without putting it inside the model's response deadline."""

    if last_started is None:
        return 0
    return max(0, last_started + interval - now)


def hard_violations(response: RecommendationResponse, constraints: dict[str, Any]) -> int:
    violations = 0
    for item in response.recommendations:
        cost = item.estimated_cost.amount if item.estimated_cost else None
        valid = item.location == constraints["location"]
        if "cost_gt" in constraints:
            valid &= cost is not None and cost > constraints["cost_gt"]
        if "cost_lte" in constraints:
            valid &= cost is not None and cost <= constraints["cost_lte"]
        if "rating_gte" in constraints:
            valid &= item.rating is not None and item.rating >= constraints["rating_gte"]
        if "any_cuisines" in constraints:
            valid &= bool(set(item.cuisines) & set(constraints["any_cuisines"]))
        valid &= set(constraints.get("unverified_contains", [])) <= set(item.unverified_preferences)
        violations += not valid
    return violations


def ndcg(identifiers: list[str], grades: dict[str, int]) -> float | None:
    if not identifiers or any(identifier not in grades for identifier in identifiers):
        return None
    ordered = [grades[identifier] for identifier in identifiers]
    ideal = sorted(grades.values(), reverse=True)[: len(ordered)]
    dcg = sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(ordered))
    best = sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal))
    return dcg / best if best else 1.0


def judged_grades(judgments: dict[str, Any], case_id: str) -> dict[str, int]:
    if judgments.get("status") != "reviewed" or not judgments.get("reviewer"):
        return {}
    records = judgments.get("cases", {}).get(case_id, {})
    if not records or any(
        type(item.get("grade")) is not int or not 0 <= item["grade"] <= 3 or not item.get("reason")
        for item in records.values()
    ):
        return {}
    return {identifier: item["grade"] for identifier, item in records.items()}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    times = sorted(row["latency_ms"] for row in rows)
    relevance = [row["ndcg"] for row in rows if row["ndcg"] is not None]
    calls = [row for row in rows if row["telemetry"] is not None]
    complete_cost = all(row["telemetry"]["estimated_cost_usd"] is not None for row in calls)
    nonempty = [row for row in rows if row["ids"]]
    return {
        "requests": len(rows),
        "empty_result_rate": sum(not row["ids"] for row in rows) / len(rows),
        "mean_latency_ms": statistics.mean(times),
        "p95_latency_ms": times[math.ceil(0.95 * len(times)) - 1],
        "latency_stddev_ms": statistics.pstdev(times),
        "hard_filter_violations": sum(row["hard_filter_violations"] for row in rows),
        "unknown_ids": sum(row["unknown_ids"] for row in rows),
        "count_mismatches": sum(row["count_mismatch"] for row in rows),
        "delivered_unsupported_claims": sum(row["delivered_unsupported_claims"] for row in rows),
        "rejected_unsupported_output_rate": sum(
            any("grounding" in error for error in row["telemetry"]["validation_failures"])
            for row in calls
        )
        / len(calls)
        if calls
        else 0,
        "fallback_rate": sum(row["mode"] == "deterministic_fallback" for row in nonempty)
        / len(nonempty)
        if nonempty
        else 0,
        "mean_ndcg": statistics.mean(relevance) if relevance else None,
        "human_judged_cases": len({row["case_id"] for row in rows if row["ndcg"] is not None}),
        "input_tokens_reported": sum(row["telemetry"]["input_tokens"] for row in calls),
        "output_tokens_reported": sum(row["telemetry"]["output_tokens"] for row in calls),
        "usage_complete": all(row["telemetry"]["usage_complete"] for row in calls),
        "mean_estimated_cost_usd": statistics.mean(
            row["telemetry"]["estimated_cost_usd"] for row in calls
        )
        if calls and complete_cost
        else (0 if not calls else None),
    }


def release_blockers(report: dict[str, Any], thresholds: dict[str, float]) -> list[str]:
    baseline, assisted = report["baseline"], report["assisted"]
    blockers = []
    if report["execution_mode"] != "groq":
        blockers.append("live_groq_evaluation_required")
    if not report["approved_model"] or report["model"] != report["approved_model"]:
        blockers.append("model_approval_required")
    if report["trials"] < 3:
        blockers.append("at_least_three_trials_required")
    for mode in ("baseline", "assisted"):
        for metric in (
            "hard_filter_violations",
            "unknown_ids",
            "count_mismatches",
            "delivered_unsupported_claims",
        ):
            if report[mode][metric]:
                blockers.append(f"{mode}_{metric}")
    if assisted["rejected_unsupported_output_rate"] > 0:
        blockers.append("unsupported_model_claims")
    if assisted["p95_latency_ms"] > thresholds["max_p95_ms"]:
        blockers.append("latency_threshold")
    if assisted["fallback_rate"] > thresholds["max_fallback_rate"]:
        blockers.append("fallback_threshold")
    if assisted["mean_estimated_cost_usd"] is None or not assisted["usage_complete"]:
        blockers.append("complete_usage_and_pricing_required")
    elif assisted["mean_estimated_cost_usd"] > thresholds["max_mean_cost_usd"]:
        blockers.append("cost_threshold")
    if min(baseline["human_judged_cases"], assisted["human_judged_cases"]) < 2:
        blockers.append("human_relevance_review_required")
    elif assisted["mean_ndcg"] - baseline["mean_ndcg"] < thresholds["min_ndcg_delta"]:
        blockers.append("relevance_regression")
    return blockers


async def evaluate(
    suite: dict[str, Any],
    judgments: dict[str, Any],
    repository: SQLiteRestaurantRepository,
    config: Settings,
    mode: str,
    trials: int,
    request_interval_seconds: float = 0,
) -> dict[str, Any]:
    if suite["dataset_version"] != repository.get_dataset_version():
        raise ValueError("Evaluation dataset version mismatch; ingest the pinned fixture.")
    if suite["prompt_version"] != PROMPT_VERSION or suite["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Prompt/schema changed; version and review the evaluation suite.")
    prompt_hash = hashlib.sha256(SYSTEM.encode()).hexdigest()
    schema_hash = hashlib.sha256(
        json.dumps(ModelRanking.model_json_schema(), sort_keys=True).encode()
    ).hexdigest()
    if suite["prompt_sha256"] != prompt_hash or suite["schema_sha256"] != schema_hash:
        raise ValueError("Prompt/schema content changed; update versioned evaluation evidence.")
    if (
        judgments["dataset_version"] != suite["dataset_version"]
        or judgments["evaluation_version"] != suite["evaluation_version"]
    ):
        raise ValueError("Judgment version mismatch.")
    gateway = ModelGateway(
        FakeRecommendationModel() if mode == "fake" else GroqRecommendationModel(config), config
    )
    rows: dict[str, list[dict[str, Any]]] = {"baseline": [], "assisted": []}
    last_model_started: float | None = None
    for case in suite["cases"]:
        request = RecommendationRequest.model_validate(case["request"])
        try:
            candidates = prepare_recommendations(request, repository, config).recommendations
        except NoMatchesError:
            candidates = []
        candidate_ids = {item.restaurant_id for item in candidates}
        grades = judged_grades(judgments, case["id"])
        if grades and not set(grades) <= candidate_ids:
            raise ValueError("Human judgments contain candidates outside the pinned case.")
        if set(grades) != candidate_ids:
            grades = {}  # Do not compute biased partial-pool NDCG.
        for label in rows:
            enabled = label == "assisted"
            for trial in range(trials):
                if enabled and candidates and request_interval_seconds:
                    delay = next_request_delay(
                        last_model_started, request_interval_seconds, time.monotonic()
                    )
                    if delay:
                        await asyncio.sleep(delay)
                    last_model_started = time.monotonic()
                started = time.perf_counter()
                telemetry = None
                response = None
                try:
                    response, telemetry = await recommend_with_model(
                        request,
                        repository,
                        config.model_copy(update={"llm_enabled": enabled}),
                        gateway if enabled else None,
                    )
                except NoMatchesError:
                    pass
                latency = (time.perf_counter() - started) * 1000
                ids = [item.restaurant_id for item in response.recommendations] if response else []
                unsupported = 0
                if response and response.meta.ranking_mode == "llm_assisted":
                    raw = {
                        "recommendations": [
                            item.model_dump(
                                include={
                                    "restaurant_id",
                                    "explanation",
                                    "matched_preferences",
                                    "unverified_preferences",
                                }
                            )
                            for item in response.recommendations
                        ],
                        "summary": response.summary,
                    }
                    try:
                        validate_output(json.dumps(raw), candidates, request.limit)
                    except Exception:
                        unsupported = 1
                rows[label].append(
                    {
                        "case_id": case["id"],
                        "trial": trial + 1,
                        "ids": ids,
                        "mode": response.meta.ranking_mode if response else "no_matches",
                        "latency_ms": round(latency, 3),
                        "ndcg": ndcg(ids, grades),
                        "hard_filter_violations": hard_violations(response, case["constraints"])
                        if response
                        else 0,
                        "unknown_ids": len(set(ids) - candidate_ids),
                        "count_mismatch": len(ids) != case["expected_count"],
                        "delivered_unsupported_claims": unsupported,
                        "telemetry": asdict(telemetry) if telemetry else None,
                    }
                )
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "application_version": __version__,
        "evaluation_version": suite["evaluation_version"],
        "dataset_version": suite["dataset_version"],
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "schema_sha256": schema_hash,
        "approved_model": suite["approved_model"],
        "execution_mode": mode,
        "model": config.llm_model,
        "trials": trials,
        "baseline": summarize(rows["baseline"]),
        "assisted": summarize(rows["assisted"]),
        "rows": rows,
        "policy": {
            "budget_low_max": config.budget_low_max,
            "budget_medium_max": config.budget_medium_max,
            "ranking_weights": config.ranking_weights.model_dump(),
            "candidate_query_limit": config.candidate_query_limit,
            "rerank_candidate_limit": config.rerank_candidate_limit,
            "timeout_seconds": config.llm_timeout_seconds,
            "max_retries": config.llm_max_retries,
            "max_completion_tokens": config.llm_max_completion_tokens,
            "max_prompt_tokens": config.llm_max_prompt_tokens,
            "max_prompt_bytes": config.llm_max_prompt_bytes,
            "response_format": config.llm_response_format,
            "input_usd_per_million": config.llm_input_usd_per_million,
            "output_usd_per_million": config.llm_output_usd_per_million,
            "evaluation_request_interval_seconds": request_interval_seconds,
        },
    }
    report["release_blockers"] = release_blockers(report, suite["thresholds"])
    report["release_passed"] = not report["release_blockers"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "groq"), default="fake")
    parser.add_argument("--allow-live", action="store_true", help="Allow billed Groq requests.")
    parser.add_argument("--require-release", action="store_true")
    parser.add_argument("--cases", type=Path, default=Path("evals/cases-v1.json"))
    parser.add_argument("--judgments", type=Path, default=Path("evals/human-judgments-v1.json"))
    parser.add_argument(
        "--database", type=Path, default=Path("runtime-data/phase5-eval/restaurants.db")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, choices=range(1, 6), default=3)
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        help=(
            "Minimum time between live model request starts. Defaults to the conservative "
            "published-base-limit interval for Groq mode and zero for fake mode."
        ),
    )
    args = parser.parse_args()
    if args.mode == "groq" and not args.allow_live:
        parser.error(
            "Groq evaluation requires --allow-live; it sends bounded, potentially billed requests."
        )
    # Never overwrite an existing evidence record.
    if args.output.exists():
        parser.error("Output exists; choose a new versioned result filename.")
    if args.request_interval_seconds is not None and (
        not math.isfinite(args.request_interval_seconds)
        or not 0 <= args.request_interval_seconds <= 300
    ):
        parser.error("--request-interval-seconds must be between 0 and 300.")
    request_interval_seconds = (
        args.request_interval_seconds
        if args.request_interval_seconds is not None
        else (recommended_live_interval_seconds() if args.mode == "groq" else 0)
    )
    try:
        config = (
            Settings(llm_enabled=True)
            if args.mode == "groq"
            else Settings(
                _env_file=None,
                llm_enabled=False,
                llm_model="fake-grounded-v1",
                groq_api_key=None,
                llm_input_usd_per_million=0,
                llm_output_usd_per_million=0,
            ).model_copy(update={"llm_enabled": True})
        )
    except ValueError:
        parser.error(
            "Set server-side APP_GROQ_API_KEY and APP_LLM_MODEL locally; "
            "never paste secrets into output."
        )
    suite = json.loads(args.cases.read_text(encoding="utf-8"))
    judgments = json.loads(args.judgments.read_text(encoding="utf-8"))
    try:
        report = asyncio.run(
            evaluate(
                suite,
                judgments,
                SQLiteRestaurantRepository(args.database),
                config,
                args.mode,
                args.trials,
                request_interval_seconds,
            )
        )
    except ValueError as exc:
        parser.error(str(exc))
    report["cases_sha256"] = hashlib.sha256(args.cases.read_bytes()).hexdigest()
    report["judgments_sha256"] = hashlib.sha256(args.judgments.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2)
        target.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    unsafe = any(
        report[mode][metric]
        for mode in ("baseline", "assisted")
        for metric in (
            "hard_filter_violations",
            "unknown_ids",
            "count_mismatches",
            "delivered_unsupported_claims",
        )
    )
    return 1 if unsafe or (args.require_release and not report["release_passed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
