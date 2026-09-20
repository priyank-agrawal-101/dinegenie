"""Provider-neutral contracts. Raw model text is never a public API response."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

PROMPT_VERSION = "restaurant-grounded-v1"
SCHEMA_VERSION = "ranked-evidence-v1"


class ModelRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    restaurant_id: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=900)
    matched_preferences: list[str] = Field(max_length=20)
    unverified_preferences: list[str] = Field(max_length=20)


class ModelRanking(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recommendations: list[ModelRecommendation] = Field(min_length=1, max_length=10)
    summary: str | None = Field(max_length=500)


@dataclass(frozen=True)
class ModelPrompt:
    system: str
    user: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class ModelReply:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ModelError(Exception):
    """Only stable categories, never provider messages, prompts, or credentials."""

    def __init__(self, category: str, *, transient: bool = False, retry_after: float = 0):
        super().__init__(category)
        self.category = category
        self.transient = transient
        self.retry_after = retry_after


class RecommendationModel(Protocol):
    async def rank_and_explain(self, prompt: ModelPrompt) -> ModelReply: ...


@dataclass
class ModelTelemetry:
    model: str
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    attempts: int = 0
    latency_ms: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usage_complete: bool = True
    estimated_cost_usd: float | None = None
    error_category: str | None = None
    validation_failures: list[str] = field(default_factory=list)
