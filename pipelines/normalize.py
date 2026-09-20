"""Pure normalization, validation, identity, and deduplication rules."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

import polars as pl

from pipelines.mapping import SourceMapping
from pipelines.models import CanonicalRestaurant, RejectedRow, TransformationResult

_RATING_PATTERN = re.compile(r"^(?P<rating>\d(?:\.\d+)?)\s*(?:/\s*5)?$")
_COST_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
_UNKNOWN_TOKENS = {"", "-", "new", "n/a", "na", "null"}


def clean_display(value: Any) -> str:
    """Collapse Unicode whitespace while preserving readable display text."""

    if value is None:
        return ""
    return " ".join(str(value).split())


def normalize_text(value: Any) -> str:
    """Create a Unicode-safe matching value."""

    return unicodedata.normalize("NFKC", clean_display(value)).casefold()


def split_values(value: Any) -> list[str]:
    """Split a comma-delimited source field and deduplicate normalized tokens."""

    display_by_normalized: dict[str, str] = {}
    for part in clean_display(value).split(","):
        display = clean_display(part)
        normalized = normalize_text(display)
        if normalized and normalized not in display_by_normalized:
            display_by_normalized[normalized] = display
    return [display_by_normalized[key] for key in sorted(display_by_normalized)]


def parse_rating(value: Any) -> tuple[float | None, bool]:
    """Return normalized rating and whether a non-missing input was invalid."""

    text = normalize_text(value)
    if text in _UNKNOWN_TOKENS:
        return None, False
    match = _RATING_PATTERN.fullmatch(text)
    if not match:
        return None, True
    try:
        rating = Decimal(match.group("rating"))
    except InvalidOperation:
        return None, True
    if not Decimal("0") <= rating <= Decimal("5"):
        return None, True
    return float(rating), False


def parse_cost(value: Any) -> tuple[int | None, bool]:
    """Return a positive INR amount for two and invalid-input status."""

    text = normalize_text(value).replace(",", "")
    if text in _UNKNOWN_TOKENS:
        return None, False
    if not _COST_PATTERN.fullmatch(text):
        return None, True
    try:
        cost = Decimal(text)
    except InvalidOperation:
        return None, True
    if cost != cost.to_integral_value() or not Decimal("0") < cost <= Decimal("100000"):
        return None, True
    return int(cost), False


def parse_votes(value: Any) -> tuple[int, bool]:
    """Return a non-negative vote count and invalid-input status."""

    text = normalize_text(value)
    if text in _UNKNOWN_TOKENS:
        return 0, False
    try:
        votes = int(text)
    except ValueError:
        return 0, True
    return (votes, False) if votes >= 0 else (0, True)


def parse_boolean(value: Any) -> tuple[bool, bool]:
    """Parse strict Yes/No source flags."""

    text = normalize_text(value)
    if text == "yes":
        return True, False
    if text == "no":
        return False, False
    return False, True


def source_identity(source_url: Any, name: str, address: str, location: str) -> str:
    """Prefer normalized source host/path and fall back to identity fields."""

    raw_url = clean_display(source_url)
    parsed = urlsplit(raw_url)
    path = re.sub(r"/+$", "", parsed.path or raw_url.split("?", 1)[0]) or "/"
    if parsed.netloc:
        identity = f"{parsed.netloc.casefold()}{path.casefold()}"
    elif path and path != "/":
        identity = path.casefold()
    else:
        seed = "|".join((normalize_text(name), normalize_text(address), normalize_text(location)))
        identity = f"fallback:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}"
    return identity


def restaurant_id(identity: str) -> str:
    """Create a stable opaque application ID."""

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"rst_{digest}"


def _row_value(row: dict[str, Any], mapping: SourceMapping, field: str) -> Any:
    column = mapping.fields[field]
    return row.get(column) if column is not None else None


def _source_row_id(row: dict[str, Any], mapping: SourceMapping, fallback: int) -> int:
    if mapping.source_row_column is None:
        return fallback
    raw = row.get(mapping.source_row_column)
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return fallback


def _transform_row(
    row: dict[str, Any], mapping: SourceMapping, fallback_row_id: int
) -> tuple[CanonicalRestaurant | None, RejectedRow | None]:
    row_id = _source_row_id(row, mapping, fallback_row_id)
    name = clean_display(_row_value(row, mapping, "name"))
    location = clean_display(_row_value(row, mapping, "location"))
    address = clean_display(_row_value(row, mapping, "address"))
    reasons: list[str] = []
    if not name:
        reasons.append("MISSING_NAME")
    if not location:
        reasons.append("MISSING_LOCATION")
    if not address:
        reasons.append("MISSING_ADDRESS")

    rating, invalid_rating = parse_rating(_row_value(row, mapping, "rating"))
    cost, invalid_cost = parse_cost(_row_value(row, mapping, "cost"))
    votes, invalid_votes = parse_votes(_row_value(row, mapping, "votes"))
    online_order, invalid_online = parse_boolean(_row_value(row, mapping, "online_order"))
    book_table, invalid_booking = parse_boolean(_row_value(row, mapping, "book_table"))
    if invalid_rating:
        reasons.append("INVALID_RATING")
    if invalid_cost:
        reasons.append("INVALID_COST")
    if invalid_votes:
        reasons.append("INVALID_VOTES")
    if invalid_online:
        reasons.append("INVALID_ONLINE_ORDER")
    if invalid_booking:
        reasons.append("INVALID_BOOK_TABLE")
    if reasons:
        return None, RejectedRow(row_id, tuple(sorted(set(reasons))))

    raw_url = clean_display(_row_value(row, mapping, "source_url"))
    identity = source_identity(raw_url, name, address, location)
    cuisines = split_values(_row_value(row, mapping, "cuisines"))
    restaurant_types = split_values(_row_value(row, mapping, "restaurant_types"))
    liked_dishes = split_values(_row_value(row, mapping, "liked_dishes"))
    listing_type = clean_display(_row_value(row, mapping, "listing_type"))
    listing_zone = clean_display(_row_value(row, mapping, "listing_zone"))
    verified_tags = []
    if online_order:
        verified_tags.append("online_order")
    if book_table:
        verified_tags.append("table_booking")

    return (
        CanonicalRestaurant(
            id=restaurant_id(identity),
            source_id=identity,
            source_url=raw_url,
            source_row_ids=[row_id],
            name=name,
            city="Bengaluru",
            location_display=location,
            location_normalized=normalize_text(location),
            listing_zones=[listing_zone] if listing_zone else [],
            address=address,
            cuisines=cuisines,
            cuisine_normalized=[normalize_text(item) for item in cuisines],
            cost_amount=cost,
            currency="INR" if cost is not None else None,
            cost_basis="for_two" if cost is not None else None,
            rating=rating,
            rating_scale=5.0 if rating is not None else None,
            votes=votes,
            restaurant_types=restaurant_types,
            online_order=online_order,
            book_table=book_table,
            liked_dishes=liked_dishes,
            listing_types=[listing_type] if listing_type else [],
            verified_tags=verified_tags,
        ),
        None,
    )


def _merge_values(groups: list[list[str]]) -> list[str]:
    by_normalized: dict[str, str] = {}
    for values in groups:
        for value in values:
            normalized = normalize_text(value)
            if normalized and normalized not in by_normalized:
                by_normalized[normalized] = value
    return [by_normalized[key] for key in sorted(by_normalized)]


def _completeness(record: CanonicalRestaurant) -> tuple[int, int, int]:
    populated = sum(
        (
            record.rating is not None,
            record.cost_amount is not None,
            bool(record.cuisines),
            bool(record.restaurant_types),
            bool(record.address),
        )
    )
    return populated, record.votes, -min(record.source_row_ids)


def _deduplicate(
    records: list[CanonicalRestaurant], rejected: list[RejectedRow]
) -> tuple[list[CanonicalRestaurant], int, int, int]:
    grouped: dict[str, list[CanonicalRestaurant]] = defaultdict(list)
    for record in records:
        grouped[record.id].append(record)

    merged: list[CanonicalRestaurant] = []
    duplicate_groups = 0
    duplicates_removed = 0
    factual_conflicts = 0
    for group in grouped.values():
        if len(group) == 1:
            merged.append(group[0])
            continue
        duplicate_groups += 1
        identity_values = {
            (normalize_text(item.name), normalize_text(item.address), item.location_normalized)
            for item in group
        }
        if len(identity_values) != 1:
            for item in group:
                rejected.append(RejectedRow(item.source_row_ids[0], ("IDENTITY_CONFLICT",)))
            continue

        duplicates_removed += len(group) - 1
        primary = max(group, key=_completeness)
        scalar_signatures = {
            (
                item.rating,
                item.cost_amount,
                item.votes,
                item.online_order,
                item.book_table,
            )
            for item in group
        }
        if len(scalar_signatures) > 1:
            factual_conflicts += 1
        cuisines = _merge_values([item.cuisines for item in group])
        merged.append(
            replace(
                primary,
                source_row_ids=sorted(row_id for item in group for row_id in item.source_row_ids),
                listing_zones=_merge_values([item.listing_zones for item in group]),
                cuisines=cuisines,
                cuisine_normalized=[normalize_text(item) for item in cuisines],
                restaurant_types=_merge_values([item.restaurant_types for item in group]),
                liked_dishes=_merge_values([item.liked_dishes for item in group]),
                listing_types=_merge_values([item.listing_types for item in group]),
                verified_tags=_merge_values([item.verified_tags for item in group]),
            )
        )
    return (
        sorted(merged, key=lambda item: item.id),
        duplicate_groups,
        duplicates_removed,
        factual_conflicts,
    )


def transform_source(frame: pl.DataFrame, mapping: SourceMapping) -> TransformationResult:
    """Transform, validate, quarantine, and deterministically deduplicate source rows."""

    records: list[CanonicalRestaurant] = []
    rejected: list[RejectedRow] = []
    for fallback_row_id, row in enumerate(frame.iter_rows(named=True)):
        record, rejection = _transform_row(row, mapping, fallback_row_id)
        if record is not None:
            records.append(record)
        if rejection is not None:
            rejected.append(rejection)

    merged, duplicate_groups, duplicates_removed, factual_conflicts = _deduplicate(
        records, rejected
    )
    reason_counts = Counter(reason for item in rejected for reason in item.reason_codes)
    return TransformationResult(
        restaurants=merged,
        rejected_rows=sorted(rejected, key=lambda item: item.source_row_id),
        raw_row_count=frame.height,
        duplicate_groups=duplicate_groups,
        duplicates_removed=duplicates_removed,
        factual_conflict_groups=factual_conflicts,
        rejection_reasons=dict(sorted(reason_counts.items())),
    )
