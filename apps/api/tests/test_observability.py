"""Phase 6 observability metrics and artifact tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pipelines.acquire import local_source
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING
from pipelines.models import IngestionResult
from pipelines.observability import ingestion_metrics, write_ingestion_metrics

from app.core.config import Settings
from app.core.metrics import Observability
from app.llm.contracts import PROMPT_VERSION, ModelReply
from app.llm.fake import FakeRecommendationModel
from app.main import create_app
from app.repositories.sqlite import SQLiteRestaurantRepository


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fixture_store(tmp_path: Path) -> tuple[IngestionResult, SQLiteRestaurantRepository]:
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
    return result, SQLiteRestaurantRepository(result.database_path)


@pytest.mark.anyio
async def test_http_errors_readiness_and_labels_are_exported(tmp_path: Path) -> None:
    result, repository = fixture_store(tmp_path)
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{result.database_path}",
        ingestion_metrics_file=tmp_path / "missing.prom",
    )
    application = create_app(settings, repository)
    sensitive_location = "Private User Location 12345"
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        assert (await client.get("/health/live")).status_code == 200
        assert (await client.get("/health/ready")).status_code == 200
        invalid = await client.post("/api/v1/recommendations", json={})
        no_match = await client.post(
            "/api/v1/recommendations",
            json={"location": sensitive_location, "budget": {"band": "low"}},
        )
        metrics = await client.get("/metrics")

    body = metrics.text
    assert invalid.status_code == 422 and no_match.status_code == 404
    assert 'route="health_live",status="200"' in body
    assert 'route="health_ready",status="200"' in body
    assert 'code="VALIDATION_ERROR"' in body
    assert 'code="NO_MATCHES"' in body
    assert "restaurant_readiness_status 1.0" in body
    assert sensitive_location not in body
    assert "restaurant_id" not in body and "request_id" not in body
    assert metrics.headers["content-type"].startswith("text/plain; version=")


@pytest.mark.anyio
async def test_fallback_versions_validation_tokens_and_cost_are_exported(tmp_path: Path) -> None:
    result, repository = fixture_store(tmp_path)
    model_name = "observability-test-model"
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{result.database_path}",
        llm_enabled=True,
        llm_model=model_name,
        groq_api_key="test-key-not-real",
        llm_max_retries=0,
        llm_input_usd_per_million=1,
        llm_output_usd_per_million=2,
        ingestion_metrics_file=tmp_path / "missing.prom",
    )
    model = FakeRecommendationModel([ModelReply("not-json", model_name, 100, 25)])
    application = create_app(settings, repository, model)
    payload = {
        "location": "Banashankari",
        "budget": {"band": "medium"},
        "cuisines": ["Chinese"],
        "limit": 2,
    }
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recommendations", json=payload)
        metrics = await client.get("/metrics")

    body = metrics.text
    assert response.status_code == 200
    assert response.json()["meta"]["ranking_mode"] == "deterministic_fallback"
    assert f'dataset_version="{result.dataset_version}"' in body
    assert f'prompt_version="{PROMPT_VERSION}"' in body
    assert f'model_version="{model_name}"' in body
    assert (
        'restaurant_model_requests_total{model_version="observability-test-model",outcome="schema"'
        in body
    )
    assert 'category="schema"' in body
    assert 'direction="input",model_version="observability-test-model"} 100.0' in body
    assert 'direction="output",model_version="observability-test-model"} 25.0' in body
    assert (
        "restaurant_model_estimated_cost_usd_total"
        '{model_version="observability-test-model"} 0.00015' in body
    )


@pytest.mark.anyio
async def test_metrics_remain_available_when_database_is_unready(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'missing.db'}",
        ingestion_metrics_file=tmp_path / "missing.prom",
    )
    application = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        metrics = await client.get("/metrics")

    assert metrics.status_code == 200
    assert "restaurant_readiness_status 0.0" in metrics.text


def test_ingestion_metrics_are_atomic_and_include_quality_signals(tmp_path: Path) -> None:
    result = IngestionResult(
        dataset_version='ds_test"version',
        source_path=Path("source.csv"),
        artifact_directory=Path("artifacts"),
        database_path=Path("restaurants.db"),
        raw_rows=100,
        canonical_rows=94,
        rejected_rows=5,
        duplicates_removed=1,
        cache_reused=False,
        artifact_reused=False,
    )
    destination = tmp_path / "metrics" / "ingestion.prom"

    write_ingestion_metrics(result, destination, completed_at=1_700_000_000)

    assert destination.read_text(encoding="utf-8") == ingestion_metrics(
        result, completed_at=1_700_000_000
    )
    body = destination.read_text(encoding="utf-8")
    assert 'kind="accepted"} 94' in body
    assert 'kind="rejected"} 5' in body
    assert "restaurant_ingestion_rejection_ratio 0.05" in body
    assert 'dataset_version="ds_test\\"version"' in body
    assert not list(destination.parent.glob(f".{destination.name}-*"))

    rendered = Observability(destination).render().decode("utf-8")
    assert "restaurant_ingestion_rejection_ratio 0.05" in rendered
    assert rendered.count("# EOF") == 1
    assert rendered.endswith("# EOF\n")


def test_dashboard_and_alert_artifacts_cover_each_failure_domain() -> None:
    dashboard = json.loads(
        Path("ops/observability/grafana-dashboard.json").read_text(encoding="utf-8")
    )
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert {"Readiness", "Application errors", "Model outcomes", "Ingestion age (hours)"} <= titles

    alerts = Path("ops/observability/prometheus-alerts.yml").read_text(encoding="utf-8")
    for subsystem in ("api", "database", "model", "data"):
        assert f"subsystem: {subsystem}" in alerts
    for forbidden in ("location", "restaurant_id", "request_id", "preferences"):
        assert "{" + forbidden + "=" not in alerts
