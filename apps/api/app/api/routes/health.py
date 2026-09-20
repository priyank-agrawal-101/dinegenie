"""Process health endpoints."""

import sqlite3
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.contracts import ErrorResponse, ReadyResponse
from app.core.errors import DatasetUnavailableError

router = APIRouter(tags=["health"])


class LiveResponse(BaseModel):
    """Liveness response contract."""

    status: Literal["alive"]
    service: str
    version: str
    environment: str


@router.get("/health/live", response_model=LiveResponse)
async def live(request: Request) -> LiveResponse:
    """Report process liveness without checking external dependencies."""

    settings = request.app.state.settings
    return LiveResponse(
        status="alive",
        service=settings.service_name,
        version=request.app.version,
        environment=settings.environment,
    )


@router.get(
    "/health/ready", response_model=ReadyResponse, responses={503: {"model": ErrorResponse}}
)
def ready(request: Request) -> ReadyResponse:
    """Confirm database access and an active dataset without checking the LLM."""

    try:
        version = request.app.state.restaurant_repository.get_dataset_version()
    except sqlite3.Error as exc:
        request.app.state.observability.set_readiness(False)
        raise DatasetUnavailableError() from exc
    if version is None:
        request.app.state.observability.set_readiness(False)
        raise DatasetUnavailableError()
    request.app.state.observability.set_readiness(True)
    return ReadyResponse(status="ready", dataset_version=version)
