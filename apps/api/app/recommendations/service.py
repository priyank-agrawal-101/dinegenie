"""Deterministic recommendation orchestration."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.api.contracts import (
    BudgetBand,
    EstimatedCost,
    RecommendationMeta,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationResult,
)
from app.core.config import Settings
from app.core.errors import DatasetUnavailableError, NoMatchesError
from app.core.logging import request_id_context
from app.domain.normalization import normalize_text, normalize_unique
from app.domain.restaurants import CandidateFilters
from app.recommendations.preferences import (
    SUPPORTED_LABELS,
    PreferenceAnalysis,
    analyze_preferences,
)
from app.recommendations.scoring import ScoredRestaurant, rank_restaurants
from app.repositories.base import RestaurantRepository


@dataclass(frozen=True)
class BudgetConstraint:
    label: str
    minimum_exclusive: int | None
    maximum_inclusive: int | None


def resolve_budget(request: RecommendationRequest, settings: Settings) -> BudgetConstraint:
    if request.budget.max_amount is not None:
        return BudgetConstraint("custom budget", None, request.budget.max_amount)
    if request.budget.band == BudgetBand.LOW:
        return BudgetConstraint("low budget", None, settings.budget_low_max)
    if request.budget.band == BudgetBand.MEDIUM:
        return BudgetConstraint(
            "medium budget", settings.budget_low_max, settings.budget_medium_max
        )
    return BudgetConstraint("high budget", settings.budget_medium_max, None)


def _explanation(
    item: ScoredRestaurant,
    request: RecommendationRequest,
    budget: BudgetConstraint,
    preferences: PreferenceAnalysis,
) -> tuple[str, list[str], list[str]]:
    restaurant = item.restaurant
    facts = [f"Located in {restaurant.location}, {restaurant.city}."]
    matched = ["location", "budget"]
    if item.matched_cuisines:
        cuisines = ", ".join(item.matched_cuisines)
        facts.append(f"Matches the requested cuisine: {cuisines}.")
        matched.extend(item.matched_cuisines)
    if request.minimum_rating is not None and restaurant.rating is not None:
        facts.append(
            f"Its {restaurant.rating:.1f}/5 rating meets the {request.minimum_rating:.1f} minimum."
        )
        matched.append("minimum rating")
    if restaurant.cost_amount is not None:
        facts.append(
            f"The estimated INR {restaurant.cost_amount:,} cost for two fits the {budget.label}."
        )
    for tag in item.matched_supported_tags:
        label = SUPPORTED_LABELS[tag]
        facts.append(f"The source verifies {label}.")
        matched.append(label)
    for preference in preferences.unverified:
        facts.append(f"The dataset does not verify whether this restaurant is {preference}.")
    return " ".join(facts), matched, list(preferences.unverified)


def prepare_recommendations(
    request: RecommendationRequest,
    repository: RestaurantRepository,
    settings: Settings,
) -> RecommendationResponse:
    try:
        version = repository.get_dataset_version()
        if version is None:
            raise DatasetUnavailableError()
        location = normalize_text(request.location)
        cuisines = normalize_unique(request.cuisines)
        budget = resolve_budget(request, settings)
        candidates = repository.find_candidates(
            CandidateFilters(
                location_normalized=location,
                minimum_rating=request.minimum_rating,
                minimum_cost_exclusive=budget.minimum_exclusive,
                maximum_cost=budget.maximum_inclusive,
                cuisines=cuisines,
                limit=settings.candidate_query_limit,
                dataset_version=version,
            )
        )
    except sqlite3.Error as exc:
        raise DatasetUnavailableError from exc
    if not candidates:
        raise NoMatchesError()

    preferences = analyze_preferences(request.additional_preferences)
    ranked = rank_restaurants(
        candidates,
        cuisines=cuisines,
        maximum_cost=budget.maximum_inclusive,
        preferences=preferences,
        weights=settings.ranking_weights,
    )
    rerank_ready = ranked[: settings.rerank_candidate_limit]
    selected = rerank_ready
    results = []
    for item in selected:
        restaurant = item.restaurant
        explanation, matched, unverified = _explanation(item, request, budget, preferences)
        cost = None
        if (
            restaurant.cost_amount is not None
            and restaurant.currency is not None
            and restaurant.cost_basis is not None
        ):
            cost = EstimatedCost(
                amount=restaurant.cost_amount,
                currency=restaurant.currency,
                basis=restaurant.cost_basis,
            )
        results.append(
            RecommendationResult(
                restaurant_id=restaurant.id,
                name=restaurant.name,
                location=restaurant.location,
                city=restaurant.city,
                cuisines=list(restaurant.cuisines),
                rating=restaurant.rating,
                estimated_cost=cost,
                explanation=explanation,
                matched_preferences=matched,
                unverified_preferences=unverified,
            )
        )
    return RecommendationResponse(
        request_id=request_id_context.get(),
        recommendations=results,
        meta=RecommendationMeta(
            dataset_version=version,
            ranking_mode="deterministic",
            filters_relaxed=[],
            candidate_count=len(candidates),
            candidate_limit_applied=len(candidates) == settings.candidate_query_limit,
        ),
    )


def recommend(
    request: RecommendationRequest,
    repository: RestaurantRepository,
    settings: Settings,
) -> RecommendationResponse:
    """Credential-free baseline, also used by the versioned evaluation runner."""
    response = prepare_recommendations(request, repository, settings)
    return response.model_copy(
        update={"recommendations": response.recommendations[: request.limit]}
    )
