"""Publication quality gates."""

from __future__ import annotations

from pipelines.errors import QualityGateError
from pipelines.mapping import SourceMapping
from pipelines.models import TransformationResult


def enforce_quality_gates(
    result: TransformationResult,
    mapping: SourceMapping,
    *,
    maximum_rejection_rate: float = 0.05,
) -> dict[str, float | int]:
    """Reject empty or severely degraded transformation results."""

    if result.raw_row_count < mapping.minimum_rows:
        raise QualityGateError(
            f"Source row count {result.raw_row_count} is below required {mapping.minimum_rows}."
        )
    if not result.restaurants:
        raise QualityGateError("No valid canonical restaurants remain after validation.")
    rejection_rate = len(result.rejected_rows) / result.raw_row_count
    if rejection_rate > maximum_rejection_rate:
        raise QualityGateError(
            f"Rejected row rate {rejection_rate:.3%} exceeds {maximum_rejection_rate:.3%}."
        )
    if len({item.id for item in result.restaurants}) != len(result.restaurants):
        raise QualityGateError("Duplicate canonical restaurant IDs remain after deduplication.")
    return {
        "raw_rows": result.raw_row_count,
        "canonical_rows": len(result.restaurants),
        "rejected_rows": len(result.rejected_rows),
        "rejection_rate": round(rejection_rate, 8),
        "duplicate_groups": result.duplicate_groups,
        "duplicates_removed": result.duplicates_removed,
        "factual_conflict_groups": result.factual_conflict_groups,
    }
