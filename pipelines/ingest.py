"""End-to-end Phase 2 ingestion orchestration."""

from __future__ import annotations

from pathlib import Path

from pipelines.artifacts import publish_artifacts
from pipelines.database import apply_migrations, connect_database, load_and_activate
from pipelines.mapping import SourceMapping, load_selected_source
from pipelines.models import IngestionResult, SourceMetadata
from pipelines.normalize import transform_source
from pipelines.profile import build_source_profile
from pipelines.quality import enforce_quality_gates


def ingest_source(
    *,
    source: SourceMetadata,
    mapping: SourceMapping,
    artifact_root: Path,
    database_path: Path,
) -> IngestionResult:
    """Validate, publish, transactionally load, and activate one source."""

    frame = load_selected_source(source.path, mapping)
    profile = build_source_profile(str(source.path), mapping)
    transformed = transform_source(frame, mapping)
    quality = enforce_quality_gates(transformed, mapping)
    bundle = publish_artifacts(
        source=source,
        mapping=mapping,
        result=transformed,
        source_profile=profile,
        quality=quality,
        artifact_root=artifact_root,
    )
    connection = connect_database(database_path)
    try:
        apply_migrations(connection)
        load_and_activate(connection, bundle)
    finally:
        connection.close()
    return IngestionResult(
        dataset_version=bundle.version,
        source_path=source.path,
        artifact_directory=bundle.directory,
        database_path=database_path,
        raw_rows=transformed.raw_row_count,
        canonical_rows=len(transformed.restaurants),
        rejected_rows=len(transformed.rejected_rows),
        duplicates_removed=transformed.duplicates_removed,
        cache_reused=source.cache_reused,
        artifact_reused=bundle.reused,
    )
