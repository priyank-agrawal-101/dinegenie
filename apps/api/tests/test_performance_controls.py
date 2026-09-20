"""Bounded concurrency, deadlines, caching, and graceful-shutdown tests."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pipelines.acquire import local_source
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING

from app.core.config import Settings
from app.domain.restaurants import CandidateFilters, RestaurantRecord
from app.llm.contracts import ModelPrompt, ModelReply
from app.main import create_app
from app.recommendations.metadata import MetadataService
from app.repositories.sqlite import SQLiteRestaurantRepository


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fixture_repository(tmp_path: Path) -> SQLiteRestaurantRepository:
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
    return SQLiteRestaurantRepository(result.database_path)


class BlockingRepository(SQLiteRestaurantRepository):
    def __init__(self, source: SQLiteRestaurantRepository) -> None:
        super().__init__(source.database_path)
        self.started = threading.Event()
        self.release_query = threading.Event()
        self.closed = False

    def find_candidates(self, filters: CandidateFilters) -> list[RestaurantRecord]:
        self.started.set()
        self.release_query.wait(timeout=2)
        return super().find_candidates(filters)

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_recommendation_deadline_returns_stable_504(tmp_path: Path) -> None:
    repository = BlockingRepository(fixture_repository(tmp_path))
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{repository.database_path}",
        rate_limit_enabled=False,
        llm_timeout_seconds=0.01,
        recommendation_timeout_seconds=0.03,
    )
    application = create_app(settings, repository)
    payload = {"location": "Banashankari", "budget": {"band": "medium"}}
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recommendations", json=payload)
    repository.release_query.set()
    await asyncio.sleep(0.02)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "REQUEST_TIMEOUT"
    assert response.headers["x-request-id"]


@pytest.mark.anyio
async def test_recommendation_capacity_rejects_excess_work(tmp_path: Path) -> None:
    repository = BlockingRepository(fixture_repository(tmp_path))
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{repository.database_path}",
        rate_limit_enabled=False,
        llm_timeout_seconds=0.1,
        recommendation_timeout_seconds=1,
        recommendation_concurrency_limit=1,
        recommendation_queue_timeout_seconds=0.02,
    )
    application = create_app(settings, repository)
    payload = {"location": "Banashankari", "budget": {"band": "medium"}}
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        first_task = asyncio.create_task(client.post("/api/v1/recommendations", json=payload))
        assert await asyncio.to_thread(repository.started.wait, 1)
        excess = await client.post("/api/v1/recommendations", json=payload)
        repository.release_query.set()
        first = await first_task

    assert first.status_code == 200
    assert excess.status_code == 429
    assert excess.json()["error"]["code"] == "RATE_LIMITED"


class VersionedMetadataRepository:
    def __init__(self) -> None:
        self.version = "v1"
        self.calls = 0

    def get_dataset_version(self) -> str:
        return self.version

    def list_locations(
        self, query: str = "", limit: int = 20, dataset_version: str | None = None
    ) -> list[str]:
        self.calls += 1
        return [f"{dataset_version}:{query}:{limit}"]

    def list_cuisines(
        self,
        location: str | None = None,
        limit: int = 100,
        dataset_version: str | None = None,
    ) -> list[str]:
        return []

    def find_candidates(self, filters: CandidateFilters) -> list[RestaurantRecord]:
        return []

    def get_by_ids(
        self, identifiers: list[str], dataset_version: str | None = None
    ) -> list[RestaurantRecord]:
        return []

    def close(self) -> None:
        pass


def test_metadata_cache_is_scoped_to_dataset_version() -> None:
    repository = VersionedMetadataRepository()
    service = MetadataService(repository, ttl_seconds=60)

    assert service.locations("Central", 10) == ("v1", ["v1:central:10"])
    assert service.locations("Central", 10) == ("v1", ["v1:central:10"])
    assert repository.calls == 1
    repository.version = "v2"
    assert service.locations("Central", 10) == ("v2", ["v2:central:10"])
    assert repository.calls == 2


@pytest.mark.anyio
async def test_lifespan_closes_repository_and_model_client(tmp_path: Path) -> None:
    repository = BlockingRepository(fixture_repository(tmp_path))

    class ClosableModel:
        closed = False

        async def rank_and_explain(self, prompt: ModelPrompt) -> ModelReply:
            raise AssertionError("model should not be called")

        async def aclose(self) -> None:
            self.closed = True

    model = ClosableModel()
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{repository.database_path}",
        llm_enabled=True,
        llm_model="test-model",
        groq_api_key="test-key-not-real",
    )
    application = create_app(settings, repository, model)

    async with application.router.lifespan_context(application):
        pass

    assert repository.closed
    assert model.closed
