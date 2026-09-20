from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pipelines.acquire import local_source, sha256_file
from pipelines.artifacts import publish_artifacts
from pipelines.database import apply_migrations, connect_database, load_and_activate
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING, load_selected_source
from pipelines.models import ArtifactBundle
from pipelines.normalize import transform_source
from pipelines.profile import build_source_profile
from pipelines.quality import enforce_quality_gates

from app.domain.restaurants import CandidateFilters
from app.repositories.sqlite import SQLiteRestaurantRepository

FIXTURE = Path("data/samples/zomato-phase0-sample.csv")


def _publish(path: Path, root: Path) -> ArtifactBundle:
    source = local_source(path, mode="fixture", repository="test/fixture")
    transformed = transform_source(
        load_selected_source(path, PHASE0_FIXTURE_MAPPING), PHASE0_FIXTURE_MAPPING
    )
    return publish_artifacts(
        source=source,
        mapping=PHASE0_FIXTURE_MAPPING,
        result=transformed,
        source_profile=build_source_profile(str(path), PHASE0_FIXTURE_MAPPING),
        quality=enforce_quality_gates(transformed, PHASE0_FIXTURE_MAPPING),
        artifact_root=root,
    )


def test_full_fixture_ingestion_is_reproducible_and_queryable(tmp_path: Path) -> None:
    source = local_source(FIXTURE, mode="fixture", repository="test/fixture")
    first = ingest_source(
        source=source,
        mapping=PHASE0_FIXTURE_MAPPING,
        artifact_root=tmp_path / "artifacts",
        database_path=tmp_path / "restaurants.db",
    )
    first_hash = sha256_file(first.artifact_directory / "restaurants.parquet")
    second = ingest_source(
        source=source,
        mapping=PHASE0_FIXTURE_MAPPING,
        artifact_root=tmp_path / "artifacts",
        database_path=tmp_path / "restaurants.db",
    )
    second_hash = sha256_file(second.artifact_directory / "restaurants.parquet")

    assert first.dataset_version == second.dataset_version
    assert first_hash == second_hash
    assert second.artifact_reused is True
    manifest = json.loads((first.artifact_directory / "manifest.json").read_text())
    assert manifest["counts"]["canonical_rows"] == 7
    assert (
        manifest["counts"]["canonical_rows"]
        + manifest["counts"]["duplicates_removed"]
        + manifest["counts"]["rejected_rows"]
        == manifest["counts"]["raw_rows"]
    )

    repository = SQLiteRestaurantRepository(first.database_path)
    assert repository.get_dataset_version() == first.dataset_version
    assert repository.list_locations() == ["Banashankari", "Basavanagudi"]
    candidates = repository.find_candidates(
        CandidateFilters("banashankari", minimum_rating=4.0, maximum_cost=800, cuisines=("thai",))
    )
    assert [item.name for item in candidates] == ["Spice Elephant"]
    assert repository.get_by_ids([candidates[0].id])[0].cuisines


def test_failed_load_does_not_change_active_version(tmp_path: Path) -> None:
    first_path = tmp_path / "first.csv"
    first_path.write_bytes(FIXTURE.read_bytes())
    second_path = tmp_path / "second.csv"
    second_path.write_text(
        FIXTURE.read_text(encoding="utf-8").replace("Jalsa", "Jalsa Updated", 1),
        encoding="utf-8",
    )
    first = _publish(first_path, tmp_path / "artifacts")
    second = _publish(second_path, tmp_path / "artifacts")
    connection = connect_database(tmp_path / "restaurants.db")
    apply_migrations(connection)
    load_and_activate(connection, first)

    def fail(_: sqlite3.Connection) -> None:
        raise RuntimeError("simulated pre-activation failure")

    try:
        load_and_activate(connection, second, failure_hook=fail)
    except RuntimeError:
        pass
    active = connection.execute(
        "SELECT active_version FROM dataset_state WHERE singleton=1"
    ).fetchone()[0]
    second_rows = connection.execute(
        "SELECT COUNT(*) FROM restaurants WHERE dataset_version=?", (second.version,)
    ).fetchone()[0]
    connection.close()
    assert active == first.version
    assert second_rows == 0


def test_query_plan_uses_location_index(tmp_path: Path) -> None:
    source = local_source(FIXTURE, mode="fixture", repository="test/fixture")
    result = ingest_source(
        source=source,
        mapping=PHASE0_FIXTURE_MAPPING,
        artifact_root=tmp_path / "artifacts",
        database_path=tmp_path / "restaurants.db",
    )
    connection = sqlite3.connect(result.database_path)
    plan = connection.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM restaurants "
        "WHERE dataset_version=? AND location_normalized=? AND rating>=?",
        (result.dataset_version, "banashankari", 4.0),
    ).fetchall()
    connection.close()
    assert any("idx_restaurants_location_rating" in str(row) for row in plan)
