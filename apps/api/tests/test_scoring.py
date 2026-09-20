from __future__ import annotations

import pytest

from app.api.contracts import BudgetBand, BudgetPreference, RecommendationRequest
from app.core.config import RankingWeights, Settings
from app.domain.restaurants import RestaurantRecord
from app.recommendations.preferences import PreferenceAnalysis
from app.recommendations.scoring import rank_restaurants, score_restaurant
from app.recommendations.service import resolve_budget


def restaurant(
    identifier: str,
    *,
    rating: float | None = 4.0,
    cost: int | None = 600,
    votes: int = 10,
    cuisines: tuple[str, ...] = ("Italian",),
    tags: tuple[str, ...] = (),
) -> RestaurantRecord:
    return RestaurantRecord(
        id=identifier,
        name=identifier,
        city="Bengaluru",
        location="Test",
        address="Address",
        rating=rating,
        cost_amount=cost,
        currency="INR" if cost is not None else None,
        cost_basis="for_two" if cost is not None else None,
        votes=votes,
        cuisines=cuisines,
        verified_tags=tags,
    )


def test_budget_boundaries_and_custom_precedence() -> None:
    settings = Settings()
    low = resolve_budget(
        RecommendationRequest(location="X", budget=BudgetPreference(band=BudgetBand.LOW)), settings
    )
    medium = resolve_budget(
        RecommendationRequest(location="X", budget=BudgetPreference(band=BudgetBand.MEDIUM)),
        settings,
    )
    high = resolve_budget(
        RecommendationRequest(location="X", budget=BudgetPreference(band=BudgetBand.HIGH)), settings
    )
    custom = resolve_budget(
        RecommendationRequest(
            location="X", budget=BudgetPreference(band=BudgetBand.HIGH, max_amount=900)
        ),
        settings,
    )
    assert (low.minimum_exclusive, low.maximum_inclusive) == (None, 600)
    assert (medium.minimum_exclusive, medium.maximum_inclusive) == (600, 1500)
    assert (high.minimum_exclusive, high.maximum_inclusive) == (1500, None)
    assert (custom.minimum_exclusive, custom.maximum_inclusive) == (None, 900)


def test_scores_are_bounded_and_unsupported_preferences_never_rewarded() -> None:
    weights = RankingWeights(rating=0.35, cuisine=0.3, budget=0.2, preference=0.15)
    unsupported = PreferenceAnalysis((), ("family-friendly",))
    score = score_restaurant(
        restaurant("one", rating=5, cost=100, cuisines=("Italian",)),
        cuisines=("italian", "chinese"),
        maximum_cost=600,
        preferences=unsupported,
        weights=weights,
    )
    assert score.features.rating == 1
    assert score.features.cuisine == 0.5
    assert 0 <= score.features.budget <= 1
    assert score.features.preference == 0
    assert 0 <= score.features.total <= 1


def test_supported_preference_evidence_and_stable_tie_breaks() -> None:
    weights = RankingWeights(rating=0.35, cuisine=0.3, budget=0.2, preference=0.15)
    preferences = PreferenceAnalysis(("online_order",), ())
    with_evidence = score_restaurant(
        restaurant("evidence", tags=("online_order",)),
        cuisines=(),
        maximum_cost=600,
        preferences=preferences,
        weights=weights,
    )
    assert with_evidence.features.preference == 1

    ranked = rank_restaurants(
        [restaurant("b", votes=10), restaurant("a", votes=10), restaurant("c", votes=11)],
        cuisines=(),
        maximum_cost=600,
        preferences=PreferenceAnalysis((), ()),
        weights=weights,
    )
    assert [item.restaurant.id for item in ranked] == ["c", "a", "b"]


def test_invalid_weight_sum_is_rejected() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        RankingWeights(rating=0.5, cuisine=0.5, budget=0.5, preference=0.5)
