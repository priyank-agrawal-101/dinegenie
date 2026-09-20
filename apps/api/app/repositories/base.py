"""Provider-neutral restaurant repository contract."""

from __future__ import annotations

from typing import Protocol

from app.domain.restaurants import CandidateFilters, RestaurantRecord


class RestaurantRepository(Protocol):
    def close(self) -> None: ...

    def get_dataset_version(self) -> str | None: ...

    def list_locations(
        self, query: str = "", limit: int = 20, dataset_version: str | None = None
    ) -> list[str]: ...

    def list_cuisines(
        self, location: str | None = None, limit: int = 100, dataset_version: str | None = None
    ) -> list[str]: ...

    def find_candidates(self, filters: CandidateFilters) -> list[RestaurantRecord]: ...

    def get_by_ids(
        self, identifiers: list[str], dataset_version: str | None = None
    ) -> list[RestaurantRecord]: ...
