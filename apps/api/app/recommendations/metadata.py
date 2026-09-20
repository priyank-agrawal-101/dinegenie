"""Dataset-versioned, short-lived metadata queries."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

from app.core.errors import DatasetUnavailableError
from app.domain.normalization import normalize_text
from app.repositories.base import RestaurantRepository


@dataclass
class MetadataCache:
    ttl_seconds: float
    values: dict[tuple[str, str, str, int], tuple[float, list[str]]] = field(default_factory=dict)

    def get(self, key: tuple[str, str, str, int]) -> list[str] | None:
        cached = self.values.get(key)
        if cached is None or cached[0] < time.monotonic():
            self.values.pop(key, None)
            return None
        return list(cached[1])

    def put(self, key: tuple[str, str, str, int], values: list[str]) -> list[str]:
        self.values[key] = (time.monotonic() + self.ttl_seconds, list(values))
        return values


class MetadataService:
    def __init__(self, repository: RestaurantRepository, ttl_seconds: float) -> None:
        self.repository = repository
        self.cache = MetadataCache(ttl_seconds)

    def _version(self) -> str:
        try:
            version = self.repository.get_dataset_version()
        except sqlite3.Error as exc:
            raise DatasetUnavailableError() from exc
        if version is None:
            raise DatasetUnavailableError()
        return version

    def locations(self, query: str, limit: int) -> tuple[str, list[str]]:
        version = self._version()
        normalized = normalize_text(query)
        key = (version, "locations", normalized, limit)
        cached = self.cache.get(key)
        if cached is not None:
            return version, cached
        try:
            values = self.repository.list_locations(normalized, limit, version)
        except sqlite3.Error as exc:
            raise DatasetUnavailableError() from exc
        return version, self.cache.put(key, values)

    def cuisines(self, location: str | None, limit: int) -> tuple[str, list[str]]:
        version = self._version()
        normalized = normalize_text(location) if location else ""
        key = (version, "cuisines", normalized, limit)
        cached = self.cache.get(key)
        if cached is not None:
            return version, cached
        try:
            values = self.repository.list_cuisines(normalized or None, limit, version)
        except sqlite3.Error as exc:
            raise DatasetUnavailableError() from exc
        return version, self.cache.put(key, values)
