"""Restaurant read models and deterministic candidate filters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateFilters:
    location_normalized: str
    minimum_rating: float | None = None
    minimum_cost_exclusive: int | None = None
    maximum_cost: int | None = None
    cuisines: tuple[str, ...] = ()
    limit: int = 50
    dataset_version: str | None = None


@dataclass(frozen=True)
class RestaurantRecord:
    id: str
    name: str
    city: str
    location: str
    address: str
    rating: float | None
    cost_amount: int | None
    currency: str | None
    cost_basis: str | None
    votes: int
    cuisines: tuple[str, ...]
    verified_tags: tuple[str, ...]
