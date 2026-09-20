"""Machine- and human-readable source profiling."""

from __future__ import annotations

from typing import Any

import polars as pl

from pipelines.errors import SchemaError
from pipelines.mapping import SourceMapping


def build_source_profile(path: str, mapping: SourceMapping) -> dict[str, Any]:
    """Compute exact row/null counts with streaming aggregations."""

    try:
        scan = pl.scan_csv(path, infer_schema_length=1000, null_values=[""])
        schema = scan.collect_schema()
        expressions: list[pl.Expr] = [pl.len().alias("__row_count")]
        for column in schema.names():
            expressions.append(pl.col(column).null_count().alias(column))
        counts = scan.select(expressions).collect(engine="streaming").row(0, named=True)
    except Exception as exc:
        raise SchemaError(f"Unable to profile source CSV {path}: {exc}") from exc

    row_count = int(counts["__row_count"])
    columns = []
    for name, dtype in schema.items():
        null_count = int(counts[name])
        columns.append(
            {
                "name": name,
                "inferred_type": str(dtype),
                "null_count": null_count,
                "null_percentage": round(100 * null_count / row_count, 6) if row_count else 0,
                "mapped": name in mapping.selected_columns,
            }
        )
    return {
        "mapping_name": mapping.name,
        "mapping_version": mapping.version,
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
    }


def profile_markdown(profile: dict[str, Any]) -> str:
    """Render a compact reviewable profile report."""

    lines = [
        "# Generated Source Profile",
        "",
        f"- Mapping: `{profile['mapping_name']}@{profile['mapping_version']}`",
        f"- Rows: {profile['row_count']:,}",
        f"- Columns: {profile['column_count']}",
        "",
        "| Column | Inferred type | Nulls | Null % | Mapped |",
        "|---|---|---:|---:|---:|",
    ]
    for column in profile["columns"]:
        lines.append(
            f"| `{column['name']}` | `{column['inferred_type']}` | "
            f"{column['null_count']:,} | {column['null_percentage']:.3f}% | "
            f"{'Yes' if column['mapped'] else 'No'} |"
        )
    return "\n".join(lines) + "\n"
