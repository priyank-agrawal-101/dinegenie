"""Phase 6 security-control tests."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pipelines.acquire import local_source
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.main import create_app
from app.repositories.sqlite import SQLiteRestaurantRepository


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def secured_application(tmp_path: Path, **changes: Any) -> FastAPI:
    result = ingest_source(
        source=local_source(
            Path("data/samples/zomato-phase0-sample.csv"),
            mode="fixture",
            repository="test/fixture",
        ),
        mapping=PHASE0_FIXTURE_MAPPING,
        artifact_root=tmp_path / "artifacts",
        database_path=tmp_path / "restaurants.db",
    )
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{result.database_path}",
        **changes,
    )
    return create_app(settings, SQLiteRestaurantRepository(result.database_path))


@pytest.mark.anyio
async def test_oversized_request_is_rejected_before_json_parsing(tmp_path: Path) -> None:
    application = secured_application(tmp_path, max_request_body_bytes=1024)
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recommendations",
            content=b"{" + b"x" * 1024 + b"}",
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "Request body is too large.",
        "request_id": response.headers["x-request-id"],
        "details": {"maximum_bytes": 1024},
    }


@pytest.mark.anyio
async def test_chunked_body_cannot_bypass_size_limit(tmp_path: Path) -> None:
    application = secured_application(tmp_path, max_request_body_bytes=1024)

    async def chunks() -> AsyncIterator[bytes]:
        yield b"x" * 700
        yield b"x" * 700

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recommendations",
            content=chunks(),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413


@pytest.mark.anyio
async def test_recommendation_limit_is_stricter_than_general_api_limit(tmp_path: Path) -> None:
    application = secured_application(
        tmp_path,
        api_requests_per_window=10,
        recommendation_requests_per_window=2,
        llm_requests_per_window=1,
    )
    payload = {"location": "Delhi", "budget": {"band": "low"}}
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        first = await client.post("/api/v1/recommendations", json=payload)
        second = await client.post("/api/v1/recommendations", json=payload)
        limited = await client.post(
            "/api/v1/recommendations",
            json=payload,
            headers={"Origin": "http://localhost:5173"},
        )
        metadata = await client.get("/api/v1/metadata/budget-bands")

    assert first.status_code == second.status_code == 404
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.headers["retry-after"] == "60"
    assert limited.headers["x-request-id"]
    assert limited.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert metadata.status_code == 200


@pytest.mark.anyio
async def test_cors_allows_configured_origin_and_omits_unknown_origin(tmp_path: Path) -> None:
    application = secured_application(tmp_path, cors_origins="https://app.example.com")
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        allowed = await client.get("/health/live", headers={"Origin": "https://app.example.com"})
        unknown = await client.get("/health/live", headers={"Origin": "https://attacker.example"})

    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" not in unknown.headers


def test_json_formatter_redacts_credentials_and_free_text_preferences() -> None:
    record = logging.makeLogRecord(
        {
            "name": "security-test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "event",
            "args": (),
            "groq_api_key": "secret-key",
            "additional_preferences": "private preference",
            "nested": {"authorization": "Bearer secret", "input_tokens": 12},
        }
    )

    output = json.loads(JsonFormatter().format(record))

    assert output["groq_api_key"] == "[REDACTED]"
    assert output["additional_preferences"] == "[REDACTED]"
    assert output["nested"] == {"authorization": "[REDACTED]", "input_tokens": 12}
    assert "secret-key" not in json.dumps(output)
