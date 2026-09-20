"""Local Phase 6 performance, query-plan, load, and fallback benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sqlite3
import statistics
import tempfile
import time
from collections.abc import Awaitable, Callable, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from pipelines.acquire import local_source
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING

from app.core.config import Settings
from app.domain.restaurants import CandidateFilters
from app.llm.contracts import ModelError, ModelPrompt, ModelReply
from app.llm.fake import FakeRecommendationModel
from app.main import create_app
from app.recommendations.metadata import MetadataService
from app.repositories.sqlite import SQLiteRestaurantRepository

FIXTURE = Path("data/samples/zomato-phase0-sample.csv")
PAYLOAD = {
    "location": "Banashankari",
    "budget": {"band": "medium"},
    "cuisines": ["Chinese"],
    "minimum_rating": 4.0,
    "limit": 2,
}


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.999999)))
    return ordered[index]


def timings(operation: Callable[[], Any], iterations: int) -> dict[str, float]:
    durations = []
    for _ in range(iterations):
        started = time.perf_counter()
        operation()
        durations.append((time.perf_counter() - started) * 1_000)
    return {
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(percentile(durations, 0.95), 3),
        "max_ms": round(max(durations), 3),
    }


async def async_timings(
    operation: Callable[[], Awaitable[Response]], iterations: int
) -> dict[str, float]:
    durations = []
    for _ in range(iterations):
        started = time.perf_counter()
        response = await operation()
        if response.status_code != 200:
            raise RuntimeError(f"benchmark request failed with status {response.status_code}")
        durations.append((time.perf_counter() - started) * 1_000)
    return {
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(percentile(durations, 0.95), 3),
        "max_ms": round(max(durations), 3),
    }


class DelayedGroundedModel(FakeRecommendationModel):
    def __init__(self, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    async def rank_and_explain(self, prompt: ModelPrompt) -> ModelReply:
        await asyncio.sleep(self.delay_seconds)
        return await super().rank_and_explain(prompt)


class FailingModel:
    async def rank_and_explain(self, prompt: ModelPrompt) -> ModelReply:
        raise ModelError("provider_unavailable")


async def load(
    client: AsyncClient,
    total: int,
    concurrency: int,
    expected_mode: str,
) -> dict[str, float | int]:
    semaphore = asyncio.Semaphore(concurrency)

    async def one() -> tuple[float, int, str]:
        async with semaphore:
            started = time.perf_counter()
            response = await client.post("/api/v1/recommendations", json=PAYLOAD)
            duration = (time.perf_counter() - started) * 1_000
            body = response.json()
            mode = body.get("meta", {}).get("ranking_mode", "error")
            return duration, response.status_code, mode

    started = time.perf_counter()
    outcomes = await asyncio.gather(*(one() for _ in range(total)))
    elapsed = time.perf_counter() - started
    durations = [item[0] for item in outcomes]
    failures = sum(item[1] != 200 or item[2] != expected_mode for item in outcomes)
    return {
        "requests": total,
        "concurrency": concurrency,
        "failures": failures,
        "p95_ms": round(percentile(durations, 0.95), 3),
        "requests_per_second": round(total / elapsed, 2),
    }


def query_plans(database_path: Path, version: str) -> dict[str, list[str]]:
    with closing(sqlite3.connect(database_path)) as connection:
        location_rating = connection.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM restaurants "
            "WHERE dataset_version=? AND location_normalized=? AND rating>=? LIMIT ?",
            (version, "banashankari", 4.0, 200),
        ).fetchall()
        cuisine = connection.execute(
            "EXPLAIN QUERY PLAN SELECT restaurant_id FROM restaurant_cuisines "
            "WHERE dataset_version=? AND cuisine_normalized=? LIMIT ?",
            (version, "chinese", 200),
        ).fetchall()
    return {
        "location_rating": [str(row[3]) for row in location_rating],
        "cuisine": [str(row[3]) for row in cuisine],
    }


async def benchmark(
    output: Path,
    iterations: int,
    load_requests: int,
    source_database: Path | None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="restaurant-phase6-") as temporary:
        root = Path(temporary)
        database_path = root / "restaurants.db"
        if source_database is None:
            ingestion = ingest_source(
                source=local_source(FIXTURE, mode="fixture", repository="benchmark/fixture"),
                mapping=PHASE0_FIXTURE_MAPPING,
                artifact_root=root / "artifacts",
                database_path=database_path,
            )
            dataset_version = ingestion.dataset_version
            dataset_rows = ingestion.canonical_rows
            dataset_kind = "fixture"
        else:
            if not source_database.is_file():
                raise FileNotFoundError(source_database)
            with (
                closing(sqlite3.connect(source_database)) as source,
                closing(sqlite3.connect(database_path)) as destination,
            ):
                source.backup(destination)
            snapshot = SQLiteRestaurantRepository(database_path)
            active_version = snapshot.get_dataset_version()
            if active_version is None:
                raise RuntimeError("benchmark database has no active dataset")
            dataset_version = active_version
            with closing(sqlite3.connect(database_path)) as connection:
                dataset_rows = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM restaurants WHERE dataset_version=?",
                        (dataset_version,),
                    ).fetchone()[0]
                )
            dataset_kind = "database_snapshot"
        repository = SQLiteRestaurantRepository(database_path)
        base_settings: dict[str, Any] = {
            "_env_file": None,
            "environment": "test",
            "log_level": "WARNING",
            "database_url": f"sqlite:///{database_path}",
            "rate_limit_enabled": False,
            "metrics_enabled": True,
            "ingestion_metrics_file": root / "missing.prom",
        }
        metadata = MetadataService(repository, ttl_seconds=30)
        metadata.locations("b", 20)
        metadata_result = timings(lambda: metadata.locations("b", 20), iterations)
        filters = CandidateFilters(
            "banashankari",
            minimum_rating=4.0,
            maximum_cost=1500,
            cuisines=("chinese",),
            limit=200,
            dataset_version=dataset_version,
        )
        repository.find_candidates(filters)
        candidate_result = timings(lambda: repository.find_candidates(filters), iterations)

        deterministic = create_app(Settings(**base_settings), repository)
        async with deterministic.router.lifespan_context(deterministic):
            async with AsyncClient(
                transport=ASGITransport(app=deterministic), base_url="http://benchmark"
            ) as client:
                await client.post("/api/v1/recommendations", json=PAYLOAD)
                deterministic_result = await async_timings(
                    lambda: client.post("/api/v1/recommendations", json=PAYLOAD), iterations
                )
                expected_load = await load(client, load_requests, 10, "deterministic")

        assisted_settings = Settings(
            **base_settings,
            llm_enabled=True,
            llm_model="fake-grounded-v1",
            groq_api_key="benchmark-not-a-real-key",
            llm_max_retries=0,
        )
        assisted = create_app(
            assisted_settings, repository, DelayedGroundedModel(delay_seconds=0.05)
        )
        async with assisted.router.lifespan_context(assisted):
            async with AsyncClient(
                transport=ASGITransport(app=assisted), base_url="http://benchmark"
            ) as client:
                assisted_result = await async_timings(
                    lambda: client.post("/api/v1/recommendations", json=PAYLOAD), iterations
                )

        fallback = create_app(assisted_settings, repository, FailingModel())
        async with fallback.router.lifespan_context(fallback):
            async with AsyncClient(
                transport=ASGITransport(app=fallback), base_url="http://benchmark"
            ) as client:
                failure_load = await load(
                    client, min(load_requests, 50), 10, "deterministic_fallback"
                )

        plans = query_plans(database_path, dataset_version)
        report: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "environment": {
                "kind": "local_in_process_asgi",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "dataset_kind": dataset_kind,
                "dataset_rows": dataset_rows,
            },
            "iterations": iterations,
            "benchmarks": {
                "metadata_cached": metadata_result,
                "candidate_query": candidate_result,
                "deterministic_recommendation": deterministic_result,
                "llm_assisted_simulated_50ms_provider": assisted_result,
            },
            "load": {"expected_deterministic": expected_load, "provider_failure": failure_load},
            "query_plans": plans,
            "targets": {
                "metadata_p95_under_300ms": metadata_result["p95_ms"] < 300,
                "deterministic_p95_under_1000ms": deterministic_result["p95_ms"] < 1000,
                "simulated_llm_p95_under_8000ms": assisted_result["p95_ms"] < 8000,
                "fallback_zero_failures": failure_load["failures"] == 0,
                "location_index_used": any(
                    "idx_restaurants_location_rating" in line for line in plans["location_rating"]
                ),
                "cuisine_index_used": any(
                    "idx_restaurant_cuisines_lookup" in line for line in plans["cuisine"]
                ),
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--output", type=Path, default=Path("evals/results/phase6-performance.json"))
    value.add_argument("--iterations", type=int, default=30)
    value.add_argument("--load-requests", type=int, default=200)
    value.add_argument(
        "--database",
        type=Path,
        help="Optional SQLite database to snapshot for a production-volume read-only benchmark.",
    )
    return value


def main(arguments: Sequence[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.iterations < 5 or args.load_requests < 10:
        raise SystemExit("iterations must be >= 5 and load requests must be >= 10")
    report = asyncio.run(benchmark(args.output, args.iterations, args.load_requests, args.database))
    print(json.dumps(report, indent=2))
    return 0 if all(report["targets"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
