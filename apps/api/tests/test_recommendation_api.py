from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pipelines.acquire import local_source
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING
from pipelines.models import IngestionResult

from app.core.config import Settings
from app.core.errors import RateLimitError
from app.domain.restaurants import CandidateFilters
from app.main import create_app
from app.repositories.sqlite import SQLiteRestaurantRepository

FIXTURE = Path("data/samples/zomato-phase0-sample.csv")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fixture_application(tmp_path: Path) -> tuple[FastAPI, IngestionResult]:
    result = ingest_source(
        source=local_source(FIXTURE, mode="fixture", repository="test/fixture"),
        mapping=PHASE0_FIXTURE_MAPPING,
        artifact_root=tmp_path / "artifacts",
        database_path=tmp_path / "restaurants.db",
    )
    settings = Settings(environment="test", database_url=f"sqlite:///{result.database_path}")
    return create_app(settings, SQLiteRestaurantRepository(result.database_path)), result


@pytest.mark.anyio
async def test_metadata_and_readiness_use_only_active_dataset(tmp_path: Path) -> None:
    application, ingestion = fixture_application(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        ready = await client.get("/health/ready")
        locations = await client.get("/api/v1/metadata/locations", params={"query": "bana"})
        cuisines = await client.get(
            "/api/v1/metadata/cuisines", params={"location": " Banashankari "}
        )
        unknown = await client.get("/api/v1/metadata/cuisines", params={"location": "Delhi"})
        bands = await client.get("/api/v1/metadata/budget-bands")

    assert ready.json() == {"status": "ready", "dataset_version": ingestion.dataset_version}
    assert locations.json()["values"] == ["Banashankari"]
    assert "Chinese" in cuisines.json()["values"]
    assert unknown.json()["values"] == []
    assert [item["id"] for item in bands.json()["bands"]] == ["low", "medium", "high"]


@pytest.mark.anyio
async def test_recommendations_enforce_all_hard_filters_and_are_stable(tmp_path: Path) -> None:
    application, ingestion = fixture_application(tmp_path)
    payload = {
        "location": "  BANASHANKARI ",
        "budget": {"band": "medium", "currency": "INR"},
        "cuisines": ["Chinese", "THAI", "chinese"],
        "minimum_rating": 4.0,
        "additional_preferences": "online ordering and family-friendly",
        "limit": 5,
    }
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        first = await client.post("/api/v1/recommendations", json=payload)
        second = await client.post("/api/v1/recommendations", json=payload)

    assert first.status_code == 200
    body = first.json()
    assert body["meta"] == {
        "dataset_version": ingestion.dataset_version,
        "ranking_mode": "deterministic",
        "filters_relaxed": [],
        "candidate_count": 2,
        "candidate_limit_applied": False,
    }
    assert [item["restaurant_id"] for item in body["recommendations"]] == [
        item["restaurant_id"] for item in second.json()["recommendations"]
    ]
    for item in body["recommendations"]:
        assert item["location"] == "Banashankari"
        assert item["rating"] >= 4.0
        assert 600 < item["estimated_cost"]["amount"] <= 1500
        assert {value.casefold() for value in item["cuisines"]} & {"chinese", "thai"}
        assert item["unverified_preferences"] == ["family-friendly"]
        assert "online ordering" in item["matched_preferences"]
        assert "does not verify" in item["explanation"]
    assert body["request_id"] == first.headers["x-request-id"]


@pytest.mark.anyio
async def test_no_match_never_relaxes_or_substitutes_bengaluru(tmp_path: Path) -> None:
    application, _ = fixture_application(tmp_path)
    payload = {"location": "Delhi", "budget": {"band": "low"}}
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_MATCHES"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "recommendations" not in response.json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"location": " ", "budget": {"band": "low"}},
        {"location": "X", "budget": {"band": "unknown"}},
        {"location": "X", "budget": {"max_amount": 0}},
        {"location": "X", "budget": {"band": "low", "currency": "USD"}},
        {"location": "X", "budget": {"band": "low"}, "minimum_rating": 4.05},
        {"location": "X", "budget": {"band": "low"}, "limit": 11},
        {"location": "X", "budget": {"band": "low"}, "unexpected": True},
    ],
)
async def test_invalid_inputs_use_stable_contract(tmp_path: Path, payload: dict[str, Any]) -> None:
    application, _ = fixture_application(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert body["request_id"] == response.headers["x-request-id"]
    assert "fields" in body["details"]


@pytest.mark.anyio
async def test_unknown_numeric_values_are_excluded_when_constrained(tmp_path: Path) -> None:
    application, ingestion = fixture_application(tmp_path)
    with sqlite3.connect(ingestion.database_path) as connection:
        connection.execute(
            "UPDATE restaurants SET rating=NULL WHERE dataset_version=? AND name='Jalsa'",
            (ingestion.dataset_version,),
        )
        connection.execute(
            "UPDATE restaurants SET cost_amount=NULL "
            "WHERE dataset_version=? AND name='Spice Elephant'",
            (ingestion.dataset_version,),
        )
    payload = {
        "location": "Banashankari",
        "budget": {"band": "medium"},
        "minimum_rating": 4.0,
    }
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_MATCHES"


@pytest.mark.anyio
async def test_unavailable_database_and_internal_errors_are_redacted(tmp_path: Path) -> None:
    unavailable = create_app(
        Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'missing.db'}")
    )
    async with AsyncClient(
        transport=ASGITransport(app=unavailable, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATASET_UNAVAILABLE"
    assert str(tmp_path) not in response.text


def test_openapi_contract_is_versioned_and_backend_facts_are_read_only(tmp_path: Path) -> None:
    application, _ = fixture_application(tmp_path)
    schema = application.openapi()
    assert "/api/v1/recommendations" in schema["paths"]
    assert "/api/v1/metadata/locations" in schema["paths"]
    request_schema = schema["components"]["schemas"]["RecommendationRequest"]
    result_schema = schema["components"]["schemas"]["RecommendationResult"]
    assert request_schema["additionalProperties"] is False
    assert {"restaurant_id", "name", "rating", "estimated_cost"} <= set(result_schema["properties"])
    assert "name" not in request_schema["properties"]
    error_codes = schema["components"]["schemas"]["ErrorCode"]["enum"]
    assert set(error_codes) == {
        "VALIDATION_ERROR",
        "NO_MATCHES",
        "DATASET_UNAVAILABLE",
        "RATE_LIMITED",
        "REQUEST_TIMEOUT",
        "INTERNAL_ERROR",
    }
    assert RateLimitError().code == "RATE_LIMITED"


def test_repository_budget_boundaries_and_nulls(tmp_path: Path) -> None:
    _, ingestion = fixture_application(tmp_path)
    repository = SQLiteRestaurantRepository(ingestion.database_path)
    low = repository.find_candidates(
        CandidateFilters(
            "basavanagudi", maximum_cost=600, dataset_version=ingestion.dataset_version
        )
    )
    medium = repository.find_candidates(
        CandidateFilters(
            "basavanagudi",
            minimum_cost_exclusive=600,
            maximum_cost=1500,
            dataset_version=ingestion.dataset_version,
        )
    )
    assert {item.cost_amount for item in low} == {550, 600}
    assert medium == []

    with sqlite3.connect(ingestion.database_path) as connection:
        connection.execute(
            "UPDATE restaurants SET cost_amount=NULL, rating=NULL "
            "WHERE dataset_version=? AND name='Redberrys'",
            (ingestion.dataset_version,),
        )
    constrained = repository.find_candidates(
        CandidateFilters(
            "basavanagudi",
            minimum_rating=0,
            maximum_cost=600,
            dataset_version=ingestion.dataset_version,
        )
    )
    assert [item.name for item in constrained] == ["Srinathji's Cafe"]
