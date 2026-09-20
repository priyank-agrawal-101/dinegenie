"""Typed configuration policy tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_llm_key_is_optional_when_feature_is_disabled() -> None:
    settings = Settings(_env_file=None, llm_enabled=False, groq_api_key=None)

    assert settings.llm_enabled is False
    assert settings.groq_api_key is None


def test_groq_key_is_required_when_feature_is_enabled() -> None:
    with pytest.raises(ValidationError, match="APP_GROQ_API_KEY"):
        Settings(
            _env_file=None,
            llm_enabled=True,
            llm_provider="groq",
            llm_model="test-model",
            groq_api_key=None,
        )


def test_empty_groq_key_is_rejected_when_feature_is_enabled() -> None:
    with pytest.raises(ValidationError, match="APP_GROQ_API_KEY"):
        Settings(
            _env_file=None,
            llm_enabled=True,
            llm_provider="groq",
            llm_model="test-model",
            groq_api_key=" ",
        )


def test_groq_model_is_required_when_feature_is_enabled() -> None:
    with pytest.raises(ValidationError, match="APP_LLM_MODEL"):
        Settings(
            _env_file=None,
            llm_enabled=True,
            llm_provider="groq",
            llm_model="",
            groq_api_key="test-key",
        )


def test_wildcard_cors_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="wildcard CORS"):
        Settings(_env_file=None, environment="production", cors_origins="*")


def test_production_requires_an_explicit_cors_origin() -> None:
    with pytest.raises(ValidationError, match="at least one CORS origin"):
        Settings(_env_file=None, environment="production", cors_origins="")


def test_production_requires_rate_limiting() -> None:
    with pytest.raises(ValidationError, match="rate limiting cannot be disabled"):
        Settings(
            _env_file=None,
            environment="production",
            cors_origins="https://app.example.com",
            rate_limit_enabled=False,
        )


def test_production_requires_metrics() -> None:
    with pytest.raises(ValidationError, match="metrics cannot be disabled"):
        Settings(
            _env_file=None,
            environment="production",
            cors_origins="https://app.example.com",
            metrics_enabled=False,
        )


@pytest.mark.parametrize(
    "origin",
    [
        "app.example.com",
        "ftp://app.example.com",
        "https://user@app.example.com",
        "https://app.example.com/path",
    ],
)
def test_invalid_cors_origins_are_rejected(origin: str) -> None:
    with pytest.raises(ValidationError, match="invalid CORS origin"):
        Settings(_env_file=None, cors_origins=origin)


def test_rate_limit_tiers_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="API >= recommendation >= LLM"):
        Settings(
            _env_file=None,
            api_requests_per_window=10,
            recommendation_requests_per_window=11,
        )


def test_cors_origins_are_normalized() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins=" http://localhost:5173, http://127.0.0.1:5173 ",
    )

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_invalid_ranking_weights_fail_configuration() -> None:
    with pytest.raises(ValidationError, match="sum to 1.0"):
        Settings(_env_file=None, ranking_rating_weight=0.5)


def test_budget_thresholds_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="MEDIUM_MAX"):
        Settings(_env_file=None, budget_low_max=1500, budget_medium_max=600)


def test_recommendation_deadline_must_exceed_model_deadline() -> None:
    with pytest.raises(ValidationError, match="RECOMMENDATION_TIMEOUT_SECONDS"):
        Settings(
            _env_file=None,
            recommendation_timeout_seconds=8,
            llm_timeout_seconds=8,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm_provider": "unknown"},
        {"llm_max_retries": 2},
        {"rerank_candidate_limit": 21},
        {"llm_max_completion_tokens": 0},
        {"llm_response_format": "unknown"},
        {"llm_input_usd_per_million": -1},
        {"llm_output_usd_per_million": float("nan")},
        {"recommendation_concurrency_limit": 0},
        {"llm_concurrency_limit": 0},
        {"database_busy_timeout_seconds": 0},
    ],
)
def test_llm_policy_limits_are_validated(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_enabled=False, **overrides)
