"""Conservative extraction of source-verifiable optional preferences."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.normalization import clean_display, normalize_text

SUPPORTED_ALIASES = {
    "online_order": ("online order", "online ordering", "delivery"),
    "table_booking": ("table booking", "book table", "reservation"),
}
SUPPORTED_LABELS = {"online_order": "online ordering", "table_booking": "table booking"}
KNOWN_UNSUPPORTED = (
    "family-friendly",
    "family friendly",
    "quick service",
    "quiet",
    "romantic",
    "ambience",
    "dietary",
    "allergen",
    "accessibility",
    "live availability",
    "open now",
)


@dataclass(frozen=True)
class PreferenceAnalysis:
    supported_tags: tuple[str, ...]
    unverified: tuple[str, ...]


def analyze_preferences(value: str | None) -> PreferenceAnalysis:
    if value is None:
        return PreferenceAnalysis((), ())
    normalized = normalize_text(value)
    supported = tuple(
        tag
        for tag, aliases in SUPPORTED_ALIASES.items()
        if any(alias in normalized for alias in aliases)
    )
    unsupported: list[str] = []
    for phrase in KNOWN_UNSUPPORTED:
        if phrase in normalized:
            label = "family-friendly" if phrase == "family friendly" else phrase
            if label not in unsupported:
                unsupported.append(label)
    if not supported and not unsupported:
        unsupported.append(clean_display(value))
    if supported and not unsupported:
        segments = [
            segment for segment in re.split(r"\s*(?:,|;|\band\b)\s*", normalized) if segment
        ]
        for segment in segments:
            if not any(
                alias in segment for aliases in SUPPORTED_ALIASES.values() for alias in aliases
            ):
                unsupported.append(segment)
    return PreferenceAnalysis(supported, tuple(unsupported))
