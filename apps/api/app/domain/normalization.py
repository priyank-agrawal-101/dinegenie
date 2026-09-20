"""Request-side normalization matching ingestion semantics."""

from __future__ import annotations

import unicodedata


def clean_display(value: str) -> str:
    return " ".join(value.split())


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", clean_display(value)).casefold()


def normalize_unique(values: list[str]) -> tuple[str, ...]:
    normalized: dict[str, None] = {}
    for value in values:
        item = normalize_text(value)
        if item:
            normalized[item] = None
    return tuple(normalized)
