from pathlib import Path

import pytest
from pipelines.acquire import local_source
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING
from scripts.sqlite_maintenance import backup, restore

FIXTURE = Path("data/samples/zomato-phase0-sample.csv")


def _database(tmp_path: Path) -> Path:
    result = ingest_source(
        source=local_source(FIXTURE, mode="fixture", repository="test/fixture"),
        mapping=PHASE0_FIXTURE_MAPPING,
        artifact_root=tmp_path / "artifacts",
        database_path=tmp_path / "source.db",
    )
    return result.database_path


def test_backup_and_restore_preserve_active_dataset(tmp_path: Path) -> None:
    ingested_database = _database(tmp_path)
    backup_path = tmp_path / "backup.db"
    restored_path = tmp_path / "restored.db"

    backup_result = backup(ingested_database, backup_path)
    restore_result = restore(backup_path, restored_path, confirmed=True)

    assert isinstance(backup_result["active_rows"], int)
    assert backup_result["active_rows"] > 0
    assert restore_result["active_version"] == backup_result["active_version"]
    assert backup_path.with_suffix(".db.json").is_file()


def test_restore_requires_explicit_confirmation(tmp_path: Path) -> None:
    ingested_database = _database(tmp_path)
    with pytest.raises(ValueError, match="requires --confirm"):
        restore(ingested_database, tmp_path / "restored.db", confirmed=False)
