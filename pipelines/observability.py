"""Atomic Prometheus textfile metrics for the offline ingestion process."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from pipelines.models import IngestionResult


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def ingestion_metrics(result: IngestionResult, completed_at: float | None = None) -> str:
    timestamp = time.time() if completed_at is None else completed_at
    rejection_rate = result.rejected_rows / result.raw_rows if result.raw_rows else 0
    version = _escape_label(result.dataset_version)
    lines = [
        (
            "# HELP restaurant_ingestion_last_success_timestamp_seconds "
            "Unix time of the last successful ingestion."
        ),
        "# TYPE restaurant_ingestion_last_success_timestamp_seconds gauge",
        f"restaurant_ingestion_last_success_timestamp_seconds {timestamp:.3f}",
        "# HELP restaurant_ingestion_rows Number of rows in the last successful ingestion.",
        "# TYPE restaurant_ingestion_rows gauge",
        f'restaurant_ingestion_rows{{kind="raw"}} {result.raw_rows}',
        f'restaurant_ingestion_rows{{kind="accepted"}} {result.canonical_rows}',
        f'restaurant_ingestion_rows{{kind="rejected"}} {result.rejected_rows}',
        "# HELP restaurant_ingestion_rejection_ratio Rejected rows divided by raw rows.",
        "# TYPE restaurant_ingestion_rejection_ratio gauge",
        f"restaurant_ingestion_rejection_ratio {rejection_rate:.12g}",
        (
            "# HELP restaurant_ingestion_dataset_info "
            "Active dataset version from the last successful ingestion."
        ),
        "# TYPE restaurant_ingestion_dataset_info gauge",
        f'restaurant_ingestion_dataset_info{{dataset_version="{version}"}} 1',
    ]
    return "\n".join(lines) + "\n"


def write_ingestion_metrics(
    result: IngestionResult, destination: Path, completed_at: float | None = None
) -> None:
    """Replace the textfile atomically so scrapers never observe a partial write."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}-", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(ingestion_metrics(result, completed_at))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
