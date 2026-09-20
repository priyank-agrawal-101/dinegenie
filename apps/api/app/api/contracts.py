"""Strict public API models for deterministic recommendations."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BudgetBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NO_MATCHES = "NO_MATCHES"
    DATASET_UNAVAILABLE = "DATASET_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class BudgetPreference(StrictModel):
    band: BudgetBand | None = None
    max_amount: int | None = Field(default=None, gt=0, le=100_000)
    currency: Literal["INR"] = "INR"

    @model_validator(mode="after")
    def require_budget_rule(self) -> Self:
        if self.band is None and self.max_amount is None:
            raise ValueError("either band or max_amount is required")
        return self


class RecommendationRequest(StrictModel):
    location: str = Field(min_length=1, max_length=80)
    budget: BudgetPreference
    cuisines: list[str] = Field(default_factory=list, max_length=10)
    minimum_rating: float | None = Field(default=None, ge=0, le=5, multiple_of=0.1)
    additional_preferences: str | None = Field(default=None, max_length=300)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("location")
    @classmethod
    def location_must_have_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("location must contain text")
        return value

    @field_validator("cuisines")
    @classmethod
    def validate_cuisines(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value.strip()) > 60 for value in values):
            raise ValueError("each cuisine must contain 1 to 60 characters")
        return values

    @field_validator("minimum_rating")
    @classmethod
    def finite_rating(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("minimum_rating must be finite")
        return value

    @field_validator("additional_preferences")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        if any(character < " " and character not in "\t\r\n" for character in value):
            raise ValueError("additional_preferences contains control characters")
        return " ".join(value.split())


class EstimatedCost(StrictModel):
    amount: int
    currency: str
    basis: str


class ScoreBreakdown(StrictModel):
    rating: float
    cuisine: float
    budget: float
    preference: float
    total: float


class RecommendationResult(StrictModel):
    restaurant_id: str
    name: str
    location: str
    city: str
    cuisines: list[str]
    rating: float | None
    estimated_cost: EstimatedCost | None
    explanation: str
    matched_preferences: list[str]
    unverified_preferences: list[str]


class RecommendationMeta(StrictModel):
    dataset_version: str
    ranking_mode: Literal["deterministic", "llm_assisted", "deterministic_fallback"]
    filters_relaxed: list[str]
    candidate_count: int
    candidate_limit_applied: bool


class RecommendationResponse(StrictModel):
    request_id: str
    recommendations: list[RecommendationResult]
    meta: RecommendationMeta
    summary: str | None = Field(default=None, max_length=500)


class MetadataResponse(StrictModel):
    dataset_version: str
    values: list[str]


class BudgetBandDefinition(StrictModel):
    id: BudgetBand
    label: str
    minimum_exclusive: int | None
    maximum_inclusive: int | None
    currency: Literal["INR"]
    basis: Literal["for_two"]


class BudgetBandsResponse(StrictModel):
    bands: list[BudgetBandDefinition]


class ReadyResponse(StrictModel):
    status: Literal["ready"]
    dataset_version: str


class ErrorBody(StrictModel):
    code: ErrorCode
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(StrictModel):
    error: ErrorBody
