"""Offline tests never opt into real model calls through a developer's .env."""

import pytest


@pytest.fixture(autouse=True)
def disable_live_model_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LLM_ENABLED", "false")
    monkeypatch.setenv("APP_GROQ_API_KEY", "")
