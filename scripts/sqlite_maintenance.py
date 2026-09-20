"""Verified backup and restore commands for the native SQLite deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

REQUIRED_TABLES = {"dataset_manifests", "dataset_state", "restaurants"}


def _validate(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with closing(sqlite3.connect(path)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        state = connection.execute(
            "SELECT active_version, previous_version FROM dataset_state WHERE singleton = 1"
        ).fetchone()
        rows = (
            connection.execute(
                "SELECT COUNT(*) FROM restaurants WHERE dataset_version = ?",
                (state[0],),
            ).fetchone()[0]
            if state is not None
            else 0
        )
    missing = REQUIRED_TABLES - tables
    if integrity != "ok" or missing or state is None or state[0] is None or rows < 1:
        raise ValueError(
            f"Invalid serving database: integrity={integrity}, missing={sorted(missing)}, "
            f"active_version={None if state is None else state[0]}, rows={rows}"
        )
    return {"active_version": state[0], "previous_version": state[1], "active_rows": rows}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(source: Path, destination: Path) -> dict[str, object]:
    metadata = _validate(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with (
        closing(sqlite3.connect(source)) as source_db,
        closing(sqlite3.connect(temporary)) as target_db,
    ):
        source_db.backup(target_db)
    _validate(temporary)
    temporary.replace(destination)
    result = {
        **metadata,
        "created_at": datetime.now(UTC).isoformat(),
        "database": str(destination),
        "sha256": _sha256(destination),
    }
    destination.with_suffix(destination.suffix + ".json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def restore(backup_path: Path, destination: Path, *, confirmed: bool) -> dict[str, object]:
    if not confirmed:
        raise ValueError("Restore requires --confirm because it replaces the serving database")
    metadata = _validate(backup_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safety_copy = destination.with_name(
        f"{destination.stem}.pre-restore-{timestamp}{destination.suffix}"
    )
    if destination.exists():
        shutil.copy2(destination, safety_copy)
    temporary = destination.with_suffix(destination.suffix + ".restore-tmp")
    shutil.copy2(backup_path, temporary)
    _validate(temporary)
    temporary.replace(destination)
    return {**metadata, "restored_to": str(destination), "safety_copy": str(safety_copy)}


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("source", type=Path)
    backup_parser.add_argument("destination", type=Path)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("destination", type=Path)
    restore_parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    result = (
        backup(args.source, args.destination)
        if args.command == "backup"
        else restore(args.backup, args.destination, confirmed=args.confirm)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
