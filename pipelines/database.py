"""SQLite migration, transactional dataset loading, and activation."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from pipelines.models import ArtifactBundle

FailureHook = Callable[[sqlite3.Connection], None]


def connect_database(path: Path) -> sqlite3.Connection:
    """Open a correctly configured SQLite connection."""

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def apply_migrations(connection: sqlite3.Connection, migration_root: Path | None = None) -> None:
    """Apply ordered, immutable SQL migrations once."""

    root = migration_root or Path(__file__).resolve().parents[1] / "migrations"
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {str(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")}
    for path in sorted(root.glob("[0-9][0-9][0-9]_*.sql")):
        if path.name in applied:
            continue
        connection.executescript(path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (path.name, datetime.now(UTC).isoformat()),
        )
    connection.commit()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def load_and_activate(
    connection: sqlite3.Connection,
    bundle: ArtifactBundle,
    *,
    failure_hook: FailureHook | None = None,
) -> None:
    """Load and activate one immutable version in a single transaction."""

    frame = pl.read_parquet(bundle.snapshot_path)
    expected = int(bundle.manifest["counts"]["canonical_rows"])
    if frame.height != expected or frame.height == 0:
        raise ValueError(f"Snapshot row count {frame.height} does not match manifest {expected}.")

    with connection:
        version = bundle.version
        connection.execute(
            """INSERT INTO dataset_manifests VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(dataset_version) DO UPDATE SET
                 source_sha256=excluded.source_sha256,
                 mapping_version=excluded.mapping_version,
                 pipeline_version=excluded.pipeline_version,
                 manifest_json=excluded.manifest_json,
                 canonical_rows=excluded.canonical_rows,
                 activated_at=excluded.activated_at""",
            (
                version,
                bundle.manifest["source"]["sha256"],
                bundle.manifest["mapping"]["version"],
                bundle.manifest["pipeline_version"],
                _json(bundle.manifest),
                expected,
                datetime.now(UTC).isoformat(),
            ),
        )
        connection.execute("DELETE FROM restaurants WHERE dataset_version = ?", (version,))
        for row in frame.iter_rows(named=True):
            connection.execute(
                """INSERT INTO restaurants VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                (
                    version,
                    row["id"],
                    row["source_id"],
                    row["source_url"],
                    _json(row["source_row_ids"]),
                    row["name"],
                    row["city"],
                    row["location_display"],
                    row["location_normalized"],
                    _json(row["listing_zones"]),
                    row["address"],
                    row["cost_amount"],
                    row["currency"],
                    row["cost_basis"],
                    row["rating"],
                    row["rating_scale"],
                    row["votes"],
                    _json(row["restaurant_types"]),
                    int(row["online_order"]),
                    int(row["book_table"]),
                    _json(row["liked_dishes"]),
                    _json(row["listing_types"]),
                    row["ingested_at"],
                ),
            )
            for display, normalized in zip(row["cuisines"], row["cuisine_normalized"], strict=True):
                connection.execute(
                    "INSERT OR IGNORE INTO cuisines(normalized_name, display_name) VALUES (?, ?)",
                    (normalized, display),
                )
                connection.execute(
                    "INSERT INTO restaurant_cuisines VALUES (?, ?, ?)",
                    (version, row["id"], normalized),
                )
            for tag in row["verified_tags"]:
                connection.execute("INSERT OR IGNORE INTO verified_tags(tag) VALUES (?)", (tag,))
                connection.execute(
                    "INSERT INTO restaurant_verified_tags VALUES (?, ?, ?)",
                    (version, row["id"], tag),
                )

        loaded = connection.execute(
            "SELECT COUNT(*) FROM restaurants WHERE dataset_version = ?", (version,)
        ).fetchone()[0]
        if loaded != expected:
            raise ValueError(f"Loaded row count {loaded} does not match expected {expected}.")
        if failure_hook is not None:
            failure_hook(connection)
        current = connection.execute(
            "SELECT active_version FROM dataset_state WHERE singleton = 1"
        ).fetchone()[0]
        if current != version:
            connection.execute(
                """UPDATE dataset_state SET previous_version = ?, active_version = ?
                   WHERE singleton = 1""",
                (current, version),
            )
