"""FastAPI application factory and process entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes.health import router as health_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.recommendations import router as recommendations_router
from app.core.capacity import ConcurrencyLimiter
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.metrics import Observability
from app.core.security import SecurityControlsMiddleware
from app.llm.contracts import RecommendationModel
from app.llm.gateway import ModelGateway
from app.llm.groq import GroqRecommendationModel
from app.recommendations.metadata import MetadataService
from app.repositories.base import RestaurantRepository
from app.repositories.factory import build_repository

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    repository: RestaurantRepository | None = None,
    model: RecommendationModel | None = None,
) -> FastAPI:
    """Create a configured API instance."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(running_app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application_started",
            extra={"environment": resolved_settings.environment},
        )
        try:
            yield
        finally:
            gateway = running_app.state.model_gateway
            if gateway is not None:
                await gateway.aclose()
            running_app.state.restaurant_repository.close()
            logger.info("application_stopped")

    application = FastAPI(
        title="Restaurant Recommendation API",
        version=__version__,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.observability = Observability(resolved_settings.ingestion_metrics_file)
    application.state.model_gateway = (
        ModelGateway(model or GroqRecommendationModel(resolved_settings), resolved_settings)
        if resolved_settings.llm_enabled
        else None
    )
    application.state.restaurant_repository = repository or build_repository(
        resolved_settings.database_url,
        resolved_settings.database_busy_timeout_seconds,
    )
    application.state.recommendation_capacity = ConcurrencyLimiter(
        resolved_settings.recommendation_concurrency_limit,
        resolved_settings.recommendation_queue_timeout_seconds,
    )
    application.state.metadata_service = MetadataService(
        application.state.restaurant_repository, resolved_settings.metadata_cache_seconds
    )
    application.add_middleware(
        SecurityControlsMiddleware,
        settings=resolved_settings,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    # Request context is outermost so security rejections also receive a trusted request ID.
    application.add_middleware(
        RequestContextMiddleware,
        metrics=application.state.observability,
    )
    application.include_router(health_router)
    application.include_router(metadata_router)
    application.include_router(recommendations_router)
    application.include_router(metrics_router)
    register_error_handlers(application)
    return application


app = create_app()
