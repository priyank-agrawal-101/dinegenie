"""Pure deterministic feature scoring and stable ordering."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import RankingWeights
from app.domain.normalization import normalize_text
from app.domain.restaurants import RestaurantRecord
from app.recommendations.preferences import PreferenceAnalysis


@dataclass(frozen=True)
class ScoreFeatures:
    rating: float
    cuisine: float
    budget: float
    preference: float
    total: float


@dataclass(frozen=True)
class ScoredRestaurant:
    restaurant: RestaurantRecord
    features: ScoreFeatures
    matched_cuisines: tuple[str, ...]
    matched_supported_tags: tuple[str, ...]


def _budget_score(cost: int | None, maximum_cost: int | None) -> float:
    if cost is None:
        return 0.0
    if maximum_cost is None:
        return 1.0
    return max(0.0, min(1.0, (maximum_cost - cost) / maximum_cost))


def score_restaurant(
    restaurant: RestaurantRecord,
    *,
    cuisines: tuple[str, ...],
    maximum_cost: int | None,
    preferences: PreferenceAnalysis,
    weights: RankingWeights,
) -> ScoredRestaurant:
    normalized_display = {normalize_text(value): value for value in restaurant.cuisines}
    matched_cuisines = tuple(
        normalized_display[value] for value in cuisines if value in normalized_display
    )
    matched_tags = tuple(
        tag for tag in preferences.supported_tags if tag in restaurant.verified_tags
    )
    rating = (restaurant.rating / 5.0) if restaurant.rating is not None else 0.0
    cuisine = len(matched_cuisines) / len(cuisines) if cuisines else 0.0
    budget = _budget_score(restaurant.cost_amount, maximum_cost)
    preference = (
        len(matched_tags) / len(preferences.supported_tags) if preferences.supported_tags else 0.0
    )
    total = (
        weights.rating * rating
        + weights.cuisine * cuisine
        + weights.budget * budget
        + weights.preference * preference
    )
    return ScoredRestaurant(
        restaurant=restaurant,
        features=ScoreFeatures(rating, cuisine, budget, preference, total),
        matched_cuisines=matched_cuisines,
        matched_supported_tags=matched_tags,
    )


def rank_restaurants(
    restaurants: list[RestaurantRecord],
    *,
    cuisines: tuple[str, ...],
    maximum_cost: int | None,
    preferences: PreferenceAnalysis,
    weights: RankingWeights,
) -> list[ScoredRestaurant]:
    scored = [
        score_restaurant(
            item,
            cuisines=cuisines,
            maximum_cost=maximum_cost,
            preferences=preferences,
            weights=weights,
        )
        for item in restaurants
    ]
    return sorted(
        scored,
        key=lambda item: (
            -item.features.total,
            -(item.restaurant.rating if item.restaurant.rating is not None else -1),
            -item.restaurant.votes,
            item.restaurant.id,
        ),
    )
