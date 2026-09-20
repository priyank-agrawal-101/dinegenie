"""Repository construction isolated from application domain code."""

from __future__ import annotations

from pathlib import Path

from app.repositories.sqlite import SQLiteRestaurantRepository


def sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// database URLs are supported by the local repository")
    raw = database_url.removeprefix(prefix)
    if not raw:
        raise ValueError("SQLite database URL must include a path")
    return Path(raw)


def build_repository(
    database_url: str, busy_timeout_seconds: float = 5.0
) -> SQLiteRestaurantRepository:
    return SQLiteRestaurantRepository(
        sqlite_path_from_url(database_url), busy_timeout_seconds=busy_timeout_seconds
    )
