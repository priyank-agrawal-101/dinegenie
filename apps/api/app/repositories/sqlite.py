"""SQLite implementation of the restaurant repository contract."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.domain.restaurants import CandidateFilters, RestaurantRecord


class SQLiteRestaurantRepository:
    def __init__(self, database_path: Path, busy_timeout_seconds: float = 5.0) -> None:
        self.database_path = database_path
        self.busy_timeout_seconds = busy_timeout_seconds

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=self.busy_timeout_seconds)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_seconds * 1_000)}")
        return connection

    def close(self) -> None:
        """SQLite connections are operation-scoped, so no shared pool remains to close."""

    def get_dataset_version(self) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT active_version FROM dataset_state WHERE singleton = 1"
            ).fetchone()
        return str(row[0]) if row and row[0] else None

    def list_locations(
        self, query: str = "", limit: int = 20, dataset_version: str | None = None
    ) -> list[str]:
        bounded = max(1, min(limit, 100))
        version = dataset_version or self.get_dataset_version()
        if version is None:
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT MIN(location_display) FROM restaurants
                   WHERE dataset_version = ?
                     AND location_normalized LIKE ?
                   GROUP BY location_normalized ORDER BY location_normalized LIMIT ?""",
                (version, f"{query.casefold()}%", bounded),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def list_cuisines(
        self, location: str | None = None, limit: int = 100, dataset_version: str | None = None
    ) -> list[str]:
        bounded = max(1, min(limit, 250))
        version = dataset_version or self.get_dataset_version()
        if version is None:
            return []
        parameters: list[Any] = [version]
        location_clause = ""
        if location is not None:
            location_clause = "AND r.location_normalized = ?"
            parameters.append(location.casefold())
        parameters.append(bounded)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""SELECT MIN(c.display_name) FROM restaurant_cuisines rc
                    JOIN restaurants r
                      ON r.dataset_version=rc.dataset_version AND r.id=rc.restaurant_id
                    JOIN cuisines c ON c.normalized_name=rc.cuisine_normalized
                    WHERE r.dataset_version=?
                    {location_clause}
                    GROUP BY c.normalized_name ORDER BY c.normalized_name LIMIT ?""",
                parameters,
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _records(
        self, connection: sqlite3.Connection, sql: str, parameters: list[Any]
    ) -> list[RestaurantRecord]:
        records = []
        for row in connection.execute(sql, parameters).fetchall():
            cuisines = tuple(json.loads(row["cuisines_json"]))
            tags = tuple(json.loads(row["tags_json"]))
            records.append(
                RestaurantRecord(
                    id=row["id"],
                    name=row["name"],
                    city=row["city"],
                    location=row["location_display"],
                    address=row["address"],
                    rating=row["rating"],
                    cost_amount=row["cost_amount"],
                    currency=row["currency"],
                    cost_basis=row["cost_basis"],
                    votes=row["votes"],
                    cuisines=cuisines,
                    verified_tags=tags,
                )
            )
        return records

    @staticmethod
    def _select() -> str:
        return """SELECT r.id, r.name, r.city, r.location_display, r.address, r.rating,
            r.cost_amount, r.currency, r.cost_basis, r.votes,
            COALESCE((SELECT json_group_array(c.display_name) FROM restaurant_cuisines rc
              JOIN cuisines c ON c.normalized_name=rc.cuisine_normalized
              WHERE rc.dataset_version=r.dataset_version AND rc.restaurant_id=r.id),
              '[]') cuisines_json,
            COALESCE((SELECT json_group_array(rv.tag) FROM restaurant_verified_tags rv
              WHERE rv.dataset_version=r.dataset_version AND rv.restaurant_id=r.id), '[]') tags_json
            FROM restaurants r"""

    def find_candidates(self, filters: CandidateFilters) -> list[RestaurantRecord]:
        clauses = [
            "r.dataset_version=?",
            "r.location_normalized=?",
        ]
        version = filters.dataset_version or self.get_dataset_version()
        if version is None:
            return []
        parameters: list[Any] = [version, filters.location_normalized.casefold()]
        if filters.minimum_rating is not None:
            clauses.append("r.rating IS NOT NULL AND r.rating>=?")
            parameters.append(filters.minimum_rating)
        if filters.maximum_cost is not None:
            clauses.append("r.cost_amount IS NOT NULL AND r.cost_amount<=?")
            parameters.append(filters.maximum_cost)
        if filters.minimum_cost_exclusive is not None:
            clauses.append("r.cost_amount IS NOT NULL AND r.cost_amount>?")
            parameters.append(filters.minimum_cost_exclusive)
        if filters.cuisines:
            placeholders = ",".join("?" for _ in filters.cuisines)
            clauses.append(
                "EXISTS (SELECT 1 FROM restaurant_cuisines f "
                "WHERE f.dataset_version=r.dataset_version "
                f"AND f.restaurant_id=r.id AND f.cuisine_normalized IN ({placeholders}))"
            )
            parameters.extend(item.casefold() for item in filters.cuisines)
        parameters.append(max(1, min(filters.limit, 250)))
        sql = self._select() + " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY r.rating DESC, r.votes DESC, r.id LIMIT ?"
        with closing(self._connect()) as connection:
            return self._records(connection, sql, parameters)

    def get_by_ids(
        self, identifiers: list[str], dataset_version: str | None = None
    ) -> list[RestaurantRecord]:
        if not identifiers:
            return []
        unique = list(dict.fromkeys(identifiers))[:250]
        placeholders = ",".join("?" for _ in unique)
        version = dataset_version or self.get_dataset_version()
        if version is None:
            return []
        sql = (
            self._select()
            + f" WHERE r.dataset_version=? AND r.id IN ({placeholders}) ORDER BY r.id"
        )
        with closing(self._connect()) as connection:
            return self._records(connection, sql, [version, *unique])
