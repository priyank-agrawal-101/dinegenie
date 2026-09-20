"""Typed records shared by ingestion pipeline stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceMetadata:
    """Lineage for one immutable source file."""

    path: Path
    repository: str
    configuration: str
    split: str
    revision: str
    filename: str
    retrieved_at: str
    sha256: str
    size_bytes: int
    mode: str
    cache_reused: bool = False

    def to_manifest(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("path")
        return payload


@dataclass
class CanonicalRestaurant:
    """Canonical restaurant record ready for artifact/database storage."""

    id: str
    source_id: str
    source_url: str
    source_row_ids: list[int]
    name: str
    city: str
    location_display: str
    location_normalized: str
    listing_zones: list[str]
    address: str
    cuisines: list[str]
    cuisine_normalized: list[str]
    cost_amount: int | None
    currency: str | None
    cost_basis: str | None
    rating: float | None
    rating_scale: float | None
    votes: int
    restaurant_types: list[str]
    online_order: bool
    book_table: bool
    liked_dishes: list[str]
    listing_types: list[str]
    verified_tags: list[str]
    dataset_version: str = ""
    ingested_at: str = ""


@dataclass(frozen=True)
class RejectedRow:
    """Non-sensitive quarantine record."""

    source_row_id: int
    reason_codes: tuple[str, ...]


@dataclass
class TransformationResult:
    """Transformation output and quality counters."""

    restaurants: list[CanonicalRestaurant]
    rejected_rows: list[RejectedRow]
    raw_row_count: int
    duplicate_groups: int
    duplicates_removed: int
    factual_conflict_groups: int
    rejection_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactBundle:
    """Paths and manifest for one immutable canonical dataset version."""

    version: str
    directory: Path
    snapshot_path: Path
    quarantine_path: Path
    profile_json_path: Path
    profile_markdown_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    reused: bool


@dataclass(frozen=True)
class IngestionResult:
    """Public result returned by the ingestion command."""

    dataset_version: str
    source_path: Path
    artifact_directory: Path
    database_path: Path
    raw_rows: int
    canonical_rows: int
    rejected_rows: int
    duplicates_removed: int
    cache_reused: bool
    artifact_reused: bool
