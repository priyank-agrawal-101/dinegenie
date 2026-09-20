"""Async LLM enhancement over a database-owned deterministic candidate snapshot."""

import sqlite3

from starlette.concurrency import run_in_threadpool

from app.api.contracts import RecommendationRequest, RecommendationResponse
from app.core.config import Settings
from app.core.errors import DatasetUnavailableError
from app.llm.contracts import ModelTelemetry
from app.llm.gateway import ModelGateway
from app.recommendations.service import prepare_recommendations
from app.repositories.base import RestaurantRepository


async def recommend_with_model(
    request: RecommendationRequest,
    repository: RestaurantRepository,
    settings: Settings,
    gateway: ModelGateway | None,
) -> tuple[RecommendationResponse, ModelTelemetry | None]:
    prepared = await run_in_threadpool(prepare_recommendations, request, repository, settings)
    baseline = prepared.model_copy(
        update={"recommendations": prepared.recommendations[: request.limit]}
    )
    if not settings.llm_enabled or gateway is None:
        return baseline, None
    outcome = await gateway.rank(request, prepared.recommendations, prepared.meta.dataset_version)
    if outcome.ranking is None:
        baseline.meta = baseline.meta.model_copy(update={"ranking_mode": "deterministic_fallback"})
        return baseline, outcome.telemetry
    ids = [item.restaurant_id for item in outcome.ranking.recommendations]
    try:
        hydrated = await run_in_threadpool(
            repository.get_by_ids, ids, prepared.meta.dataset_version
        )
    except sqlite3.Error as exc:
        raise DatasetUnavailableError() from exc
    source = {item.restaurant_id: item for item in prepared.recommendations}
    records = {item.id: item for item in hydrated}
    if set(records) != set(ids):
        raise DatasetUnavailableError()
    results = []
    for selected in outcome.ranking.recommendations:
        original = source[selected.restaurant_id]
        record = records[selected.restaurant_id]
        # Publication changes cannot mix versions. Unexpected in-place mutation is also
        # rejected instead of attaching explanations to facts different from the prompt.
        if (
            record.name != original.name
            or record.location != original.location
            or record.city != original.city
            or list(record.cuisines) != original.cuisines
            or record.rating != original.rating
            or (
                original.estimated_cost is not None
                and (
                    record.cost_amount != original.estimated_cost.amount
                    or record.currency != original.estimated_cost.currency
                    or record.cost_basis != original.estimated_cost.basis
                )
            )
        ):
            raise DatasetUnavailableError()
        # Factual fields are database-owned; only validated text/order cross this boundary.
        results.append(original.model_copy(update={"explanation": selected.explanation}))
    return prepared.model_copy(
        update={
            "recommendations": results,
            "summary": outcome.ranking.summary,
            "meta": prepared.meta.model_copy(update={"ranking_mode": "llm_assisted"}),
        }
    ), outcome.telemetry
