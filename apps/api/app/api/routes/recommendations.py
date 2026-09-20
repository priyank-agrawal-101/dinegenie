"""Deterministic recommendation endpoint."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.api.contracts import ErrorResponse, RecommendationRequest, RecommendationResponse
from app.core.capacity import CapacityExceededError
from app.core.errors import RateLimitError, RequestTimeoutError
from app.llm.contracts import ModelTelemetry
from app.recommendations.orchestrator import recommend_with_model

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    responses={
        404: {"model": ErrorResponse, "description": "No hard-filter matches"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        422: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Dataset unavailable"},
        504: {"model": ErrorResponse, "description": "Request deadline exceeded"},
    },
)
async def create_recommendations(
    payload: RecommendationRequest, request: Request
) -> RecommendationResponse:
    async def disconnected() -> None:
        while not await request.is_disconnected():
            await asyncio.sleep(0.1)

    async def execute() -> tuple[RecommendationResponse, ModelTelemetry | None]:
        capacity = request.app.state.recommendation_capacity
        try:
            await capacity.acquire()
        except CapacityExceededError as exc:
            raise RateLimitError() from exc
        try:
            try:
                async with asyncio.timeout(
                    request.app.state.settings.recommendation_timeout_seconds
                ):
                    return await recommend_with_model(
                        payload,
                        request.app.state.restaurant_repository,
                        request.app.state.settings,
                        request.app.state.model_gateway,
                    )
            except TimeoutError as exc:
                raise RequestTimeoutError() from exc
        finally:
            capacity.release()

    work = asyncio.create_task(execute())
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((work, watcher), return_when=asyncio.FIRST_COMPLETED)
        if work not in done:
            work.cancel()
            raise asyncio.CancelledError()
        response, telemetry = work.result()
        request.app.state.observability.record_recommendation(response, telemetry)
        return response
    finally:
        watcher.cancel()
        if not work.done():
            work.cancel()
        await asyncio.gather(work, watcher, return_exceptions=True)
