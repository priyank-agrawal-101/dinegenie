"""Health endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_liveness_returns_process_status_and_request_id() -> None:
    application = create_app()
    transport = ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "restaurant-recommendation-api",
        "version": "0.1.0",
        "environment": "development",
    }
    assert len(response.headers["x-request-id"]) == 32


@pytest.mark.anyio
async def test_liveness_ignores_untrusted_inbound_request_id() -> None:
    application = create_app()
    transport = ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/health/live",
                headers={"X-Request-ID": "untrusted"},
            )

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "untrusted"
