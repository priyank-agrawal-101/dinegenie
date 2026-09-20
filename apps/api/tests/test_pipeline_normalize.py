from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from pipelines.errors import SchemaError
from pipelines.mapping import PHASE0_FIXTURE_MAPPING, load_selected_source, validate_schema
from pipelines.normalize import (
    normalize_text,
    parse_boolean,
    parse_cost,
    parse_rating,
    parse_votes,
    restaurant_id,
    source_identity,
    split_values,
    transform_source,
)

FIXTURE = Path("data/samples/zomato-phase0-sample.csv")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("4.1/5", (4.1, False)), ("NEW", (None, False)), ("-", (None, False)), ("6", (None, True))],
)
def test_rating_boundaries(raw: str, expected: tuple[float | None, bool]) -> None:
    assert parse_rating(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1,200", (1200, False)), (None, (None, False)), ("0", (None, True)), ("12.5", (None, True))],
)
def test_cost_boundaries(raw: str | None, expected: tuple[int | None, bool]) -> None:
    assert parse_cost(raw) == expected


def test_other_normalizer_boundaries() -> None:
    assert normalize_text("  CAFÉ\tRoad ") == "café road"
    assert split_values("Cafe, cafe, North Indian") == ["Cafe", "North Indian"]
    assert parse_votes("0") == (0, False)
    assert parse_votes("-1") == (0, True)
    assert parse_boolean("Yes") == (True, False)
    assert parse_boolean("maybe") == (False, True)


def test_fixture_mapping_and_deduplication_are_stable() -> None:
    validate_schema(FIXTURE, PHASE0_FIXTURE_MAPPING)
    frame = load_selected_source(FIXTURE, PHASE0_FIXTURE_MAPPING)
    first = transform_source(frame, PHASE0_FIXTURE_MAPPING)
    second = transform_source(frame, PHASE0_FIXTURE_MAPPING)

    assert first.raw_row_count == 8
    assert len(first.restaurants) == 7
    assert first.duplicates_removed == 1
    assert [item.id for item in first.restaurants] == [item.id for item in second.restaurants]
    san_churro = next(item for item in first.restaurants if item.name == "San Churro Cafe")
    assert san_churro.listing_types == ["Buffet", "Cafes"]
    assert san_churro.source_row_ids == [2, 14]


def test_schema_drift_fails_before_transformation(tmp_path: Path) -> None:
    drifted = tmp_path / "drifted.csv"
    drifted.write_text("unexpected,column\nvalue,value\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="Missing=.*name"):
        validate_schema(drifted, PHASE0_FIXTURE_MAPPING)


def test_stable_identity_prefers_source_url() -> None:
    identity = source_identity("https://Example.com/Restaurant/?tracking=1", "A", "B", "C")
    assert identity == "example.com/restaurant"
    assert restaurant_id(identity) == restaurant_id(identity)


def test_malformed_rows_are_quarantined_without_source_values() -> None:
    row = {
        "source_row_idx": "99",
        "source_url_path": "",
        "name": "",
        "address": "Address",
        "location": "Location",
        "online_order": "Maybe",
        "book_table": "No",
        "rate": "8/5",
        "votes": "-1",
        "rest_type": "Cafe",
        "cuisines": "Cafe",
        "approx_cost_for_two": "0",
        "listed_in_type": "Cafe",
        "listed_in_city": "Zone",
    }
    result = transform_source(pl.DataFrame([row]), PHASE0_FIXTURE_MAPPING)
    assert not result.restaurants
    rejection = result.rejected_rows[0]
    assert rejection.source_row_id == 99
    assert set(rejection.reason_codes) == {
        "INVALID_COST",
        "INVALID_ONLINE_ORDER",
        "INVALID_RATING",
        "INVALID_VOTES",
        "MISSING_NAME",
    }
    assert not hasattr(rejection, "source_values")
