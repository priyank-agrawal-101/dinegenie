"""Atomic publication of immutable canonical dataset artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import polars as pl

from pipelines import PIPELINE_VERSION
from pipelines.acquire import sha256_file
from pipelines.mapping import SourceMapping
from pipelines.models import ArtifactBundle, SourceMetadata, TransformationResult
from pipelines.profile import profile_markdown


def dataset_version(source: SourceMetadata, mapping: SourceMapping) -> str:
    """Derive a stable version from every input that can change canonical output."""

    seed = f"{source.sha256}|{mapping.name}|{mapping.version}|{PIPELINE_VERSION}"
    return f"ds_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:20]}"


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _write_bytes(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _bundle(directory: Path, manifest: dict[str, Any], *, reused: bool) -> ArtifactBundle:
    return ArtifactBundle(
        version=str(manifest["dataset_version"]),
        directory=directory,
        snapshot_path=directory / "restaurants.parquet",
        quarantine_path=directory / "quarantine.jsonl",
        profile_json_path=directory / "source-profile.json",
        profile_markdown_path=directory / "source-profile.md",
        manifest_path=directory / "manifest.json",
        manifest=manifest,
        reused=reused,
    )


def publish_artifacts(
    *,
    source: SourceMetadata,
    mapping: SourceMapping,
    result: TransformationResult,
    source_profile: dict[str, Any],
    quality: dict[str, float | int],
    artifact_root: Path,
) -> ArtifactBundle:
    """Write a complete version into staging, then publish it with one rename."""

    version = dataset_version(source, mapping)
    destination = artifact_root / version
    manifest_path = destination / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = manifest.get("files", {}).get("restaurants.parquet", {}).get("sha256")
        snapshot = destination / "restaurants.parquet"
        if (
            manifest.get("dataset_version") == version
            and manifest.get("source", {}).get("sha256") == source.sha256
            and isinstance(expected, str)
            and snapshot.is_file()
            and sha256_file(snapshot) == expected
        ):
            return _bundle(destination, manifest, reused=True)
        raise RuntimeError(f"Existing artifact version is incomplete or corrupted: {destination}")

    artifact_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=artifact_root))
    try:
        ingested_at = source.retrieved_at
        rows: list[dict[str, Any]] = []
        for restaurant in result.restaurants:
            restaurant.dataset_version = version
            restaurant.ingested_at = ingested_at
            rows.append(asdict(restaurant))
        snapshot = staging / "restaurants.parquet"
        pl.DataFrame(rows).sort("id").write_parquet(snapshot, compression="zstd")

        quarantine = staging / "quarantine.jsonl"
        quarantine.write_text(
            "".join(
                json.dumps(
                    {"source_row_id": item.source_row_id, "reason_codes": item.reason_codes},
                    sort_keys=True,
                )
                + "\n"
                for item in result.rejected_rows
            ),
            encoding="utf-8",
        )
        profile_json = staging / "source-profile.json"
        _write_bytes(profile_json, _json_bytes(source_profile))
        (staging / "source-profile.md").write_text(
            profile_markdown(source_profile), encoding="utf-8"
        )

        files = {}
        for path in sorted(staging.iterdir()):
            files[path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        published_manifest: dict[str, Any] = {
            "dataset_version": version,
            "created_at": ingested_at,
            "pipeline_version": PIPELINE_VERSION,
            "mapping": {"name": mapping.name, "version": mapping.version},
            "source": source.to_manifest(),
            "counts": quality,
            "rejection_reasons": result.rejection_reasons,
            "files": files,
        }
        _write_bytes(staging / "manifest.json", _json_bytes(published_manifest))
        os.replace(staging, destination)
        return _bundle(destination, published_manifest, reused=False)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
