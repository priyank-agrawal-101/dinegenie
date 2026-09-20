"""Versioned source-to-canonical column mappings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from pipelines.errors import SchemaError

PRODUCTION_COLUMNS = (
    "url",
    "address",
    "name",
    "online_order",
    "book_table",
    "rate",
    "votes",
    "phone",
    "location",
    "rest_type",
    "dish_liked",
    "cuisines",
    "approx_cost(for two people)",
    "reviews_list",
    "menu_item",
    "listed_in(type)",
    "listed_in(city)",
)

FIXTURE_COLUMNS = (
    "source_row_idx",
    "source_url_path",
    "name",
    "address",
    "location",
    "online_order",
    "book_table",
    "rate",
    "votes",
    "rest_type",
    "cuisines",
    "approx_cost_for_two",
    "listed_in_type",
    "listed_in_city",
)


@dataclass(frozen=True)
class SourceMapping:
    """Explicit schema contract for one source representation."""

    name: str
    version: str
    expected_columns: tuple[str, ...]
    fields: dict[str, str | None]
    source_row_column: str | None = None
    minimum_rows: int = 1

    @property
    def selected_columns(self) -> list[str]:
        columns = [column for column in self.fields.values() if column is not None]
        if self.source_row_column:
            columns.append(self.source_row_column)
        return list(dict.fromkeys(columns))


PRODUCTION_MAPPING = SourceMapping(
    name="zomato_huggingface",
    version="zomato-bengaluru-v1",
    expected_columns=PRODUCTION_COLUMNS,
    minimum_rows=50_000,
    fields={
        "source_url": "url",
        "address": "address",
        "name": "name",
        "online_order": "online_order",
        "book_table": "book_table",
        "rating": "rate",
        "votes": "votes",
        "location": "location",
        "restaurant_types": "rest_type",
        "liked_dishes": "dish_liked",
        "cuisines": "cuisines",
        "cost": "approx_cost(for two people)",
        "listing_type": "listed_in(type)",
        "listing_zone": "listed_in(city)",
    },
)

PHASE0_FIXTURE_MAPPING = SourceMapping(
    name="phase0_fixture",
    version="zomato-bengaluru-v1",
    expected_columns=FIXTURE_COLUMNS,
    source_row_column="source_row_idx",
    fields={
        "source_url": "source_url_path",
        "address": "address",
        "name": "name",
        "online_order": "online_order",
        "book_table": "book_table",
        "rating": "rate",
        "votes": "votes",
        "location": "location",
        "restaurant_types": "rest_type",
        "liked_dishes": None,
        "cuisines": "cuisines",
        "cost": "approx_cost_for_two",
        "listing_type": "listed_in_type",
        "listing_zone": "listed_in_city",
    },
)


def inspect_csv_columns(path: Path) -> tuple[str, ...]:
    """Read source column names without collecting data rows."""

    try:
        return tuple(pl.scan_csv(path, infer_schema_length=1000).collect_schema().names())
    except Exception as exc:  # Polars exposes several parser-specific exceptions.
        raise SchemaError(f"Unable to inspect CSV schema at {path}: {exc}") from exc


def validate_schema(path: Path, mapping: SourceMapping) -> tuple[str, ...]:
    """Require an exact, ordered source schema for safe drift detection."""

    actual = inspect_csv_columns(path)
    if actual != mapping.expected_columns:
        missing = [column for column in mapping.expected_columns if column not in actual]
        unexpected = [column for column in actual if column not in mapping.expected_columns]
        order_changed = not missing and not unexpected and actual != mapping.expected_columns
        raise SchemaError(
            "Source schema does not match mapping "
            f"{mapping.name}@{mapping.version}. Missing={missing}; "
            f"unexpected={unexpected}; order_changed={order_changed}."
        )
    return actual


def load_selected_source(path: Path, mapping: SourceMapping) -> pl.DataFrame:
    """Load only serving-relevant columns while parsing all values as strings."""

    validate_schema(path, mapping)
    overrides = {column: pl.String for column in mapping.selected_columns}
    try:
        frame = pl.read_csv(
            path,
            columns=mapping.selected_columns,
            schema_overrides=overrides,
            null_values=[""],
            infer_schema_length=1000,
        )
    except Exception as exc:
        raise SchemaError(f"Unable to load mapped columns from {path}: {exc}") from exc

    if frame.height < mapping.minimum_rows:
        raise SchemaError(
            f"Source has {frame.height} rows; mapping requires at least {mapping.minimum_rows}."
        )
    return frame
