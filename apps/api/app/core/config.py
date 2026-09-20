"""Typed application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]


class RankingWeights(BaseModel):
    """Validated deterministic feature weights."""

    model_config = ConfigDict(frozen=True)

    rating: float = Field(ge=0, le=1)
    cuisine: float = Field(ge=0, le=1)
    budget: float = Field(ge=0, le=1)
    preference: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_unit_sum(self) -> Self:
        if abs(sum((self.rating, self.cuisine, self.budget, self.preference)) - 1.0) > 1e-9:
            raise ValueError("ranking weights must sum to 1.0")
        return self


class Settings(BaseSettings):
    """Environment-backed runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "restaurant-recommendation-api"
    environment: Environment = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite:///./runtime-data/restaurants.db"
    database_busy_timeout_seconds: float = Field(default=5.0, ge=0.1, le=60)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_request_body_bytes: int = Field(default=16_384, ge=1_024, le=1_048_576)
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    api_requests_per_window: int = Field(default=120, ge=1, le=100_000)
    recommendation_requests_per_window: int = Field(default=30, ge=1, le=10_000)
    llm_requests_per_window: int = Field(default=10, ge=1, le=1_000)

    dataset_repository: str = "ManikaSaini/zomato-restaurant-recommendation"
    dataset_revision: str = "5738e9eda2fad49ad51c6e0ed26e761d9b947133"

    budget_low_max: int = Field(default=600, gt=0)
    budget_medium_max: int = Field(default=1500, gt=0)
    ranking_rating_weight: float = Field(default=0.35, ge=0, le=1)
    ranking_cuisine_weight: float = Field(default=0.30, ge=0, le=1)
    ranking_budget_weight: float = Field(default=0.20, ge=0, le=1)
    ranking_preference_weight: float = Field(default=0.15, ge=0, le=1)
    candidate_query_limit: int = Field(default=200, ge=10, le=1000)
    rerank_candidate_limit: int = Field(default=20, ge=10, le=20)
    metadata_cache_seconds: float = Field(default=30.0, ge=0, le=3600)
    recommendation_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    recommendation_queue_timeout_seconds: float = Field(default=0.25, gt=0, le=10)
    recommendation_concurrency_limit: int = Field(default=32, ge=1, le=1_000)

    llm_enabled: bool = False
    llm_provider: Literal["groq"] = "groq"
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    llm_queue_timeout_seconds: float = Field(default=0.25, gt=0, le=10)
    llm_concurrency_limit: int = Field(default=4, ge=1, le=100)
    llm_max_completion_tokens: int = Field(default=2500, ge=128, le=8192)
    llm_max_prompt_bytes: int = Field(default=48000, ge=1000, le=128000)
    llm_max_prompt_tokens: int = Field(default=24000, ge=1000, le=64000)
    llm_response_format: Literal["json_object", "json_schema"] = "json_object"
    llm_max_retries: int = Field(default=1, ge=0, le=1)
    llm_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    llm_circuit_cooldown_seconds: float = Field(default=30, gt=0, le=600)
    llm_input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    llm_output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    groq_api_key: SecretStr | None = None

    metrics_enabled: bool = True
    ingestion_metrics_file: Path = Path("runtime-data/metrics/ingestion.prom")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize and validate the configured log level."""

        normalized = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized configured web origins."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ranking_weights(self) -> RankingWeights:
        return RankingWeights(
            rating=self.ranking_rating_weight,
            cuisine=self.ranking_cuisine_weight,
            budget=self.ranking_budget_weight,
            preference=self.ranking_preference_weight,
        )

    @model_validator(mode="after")
    def validate_runtime_policy(self) -> Self:
        """Reject unsafe or incomplete feature configuration."""

        if self.environment == "production":
            if not self.cors_origin_list:
                raise ValueError("at least one CORS origin is required in production")
            if "*" in self.cors_origin_list:
                raise ValueError("wildcard CORS origins are forbidden in production")
            if not self.rate_limit_enabled:
                raise ValueError("rate limiting cannot be disabled in production")
            if not self.metrics_enabled:
                raise ValueError("metrics cannot be disabled in production")
        for origin in self.cors_origin_list:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"invalid CORS origin: {origin!r}")
        if not (
            self.api_requests_per_window
            >= self.recommendation_requests_per_window
            >= self.llm_requests_per_window
        ):
            raise ValueError(
                "rate limits must satisfy API >= recommendation >= LLM requests per window"
            )
        if self.budget_medium_max <= self.budget_low_max:
            raise ValueError("APP_BUDGET_MEDIUM_MAX must exceed APP_BUDGET_LOW_MAX")
        if self.recommendation_timeout_seconds <= self.llm_timeout_seconds:
            raise ValueError(
                "APP_RECOMMENDATION_TIMEOUT_SECONDS must exceed APP_LLM_TIMEOUT_SECONDS"
            )
        _ = self.ranking_weights
        if self.llm_enabled and self.llm_provider == "groq":
            key = self.groq_api_key.get_secret_value().strip() if self.groq_api_key else ""
            if not key:
                raise ValueError("APP_GROQ_API_KEY is required when Groq LLM mode is enabled")
            if not self.llm_model.strip():
                raise ValueError("APP_LLM_MODEL is required when Groq LLM mode is enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings object."""

    return Settings()
