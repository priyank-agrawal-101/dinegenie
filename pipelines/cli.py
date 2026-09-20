"""Command-line entry point for reproducible Phase 2 ingestion."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from pipelines.acquire import acquire_huggingface_source, local_source
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING, PRODUCTION_MAPPING
from pipelines.observability import write_ingestion_metrics

DEFAULT_REPOSITORY = "ManikaSaini/zomato-restaurant-recommendation"
DEFAULT_REVISION = "5738e9eda2fad49ad51c6e0ed26e761d9b947133"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Build the canonical restaurant store.")
    value.add_argument("--mode", choices=("huggingface", "local", "fixture"), default="fixture")
    value.add_argument("--source", type=Path)
    value.add_argument("--repository", default=DEFAULT_REPOSITORY)
    value.add_argument("--revision", default=DEFAULT_REVISION)
    value.add_argument("--filename", default="zomato.csv")
    value.add_argument("--configuration", default="default")
    value.add_argument("--split", default="train")
    value.add_argument("--runtime-root", type=Path, default=Path("runtime-data"))
    value.add_argument("--force-download", action="store_true")
    value.add_argument(
        "--metrics-file",
        type=Path,
        help="Prometheus textfile path (defaults below --runtime-root/metrics).",
    )
    return value


def main(arguments: Sequence[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.mode == "huggingface":
        source = acquire_huggingface_source(
            repository=args.repository,
            revision=args.revision,
            filename=args.filename,
            configuration=args.configuration,
            split=args.split,
            raw_root=args.runtime_root / "ingestion" / "raw",
            force_download=args.force_download,
        )
        mapping = PRODUCTION_MAPPING
    else:
        path = args.source
        if args.mode == "fixture":
            path = path or Path("data/samples/zomato-phase0-sample.csv")
            mapping = PHASE0_FIXTURE_MAPPING
        else:
            if path is None:
                raise SystemExit("--source is required in local mode")
            mapping = PRODUCTION_MAPPING
        source = local_source(path, mode=args.mode, repository=args.repository)
    result = ingest_source(
        source=source,
        mapping=mapping,
        artifact_root=args.runtime_root / "ingestion" / "artifacts",
        database_path=args.runtime_root / "restaurants.db",
    )
    metrics_file = args.metrics_file or args.runtime_root / "metrics" / "ingestion.prom"
    write_ingestion_metrics(result, metrics_file)
    print(json.dumps(asdict(result), indent=2, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
