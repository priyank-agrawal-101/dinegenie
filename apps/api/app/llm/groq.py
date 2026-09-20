"""Isolated Groq HTTP adapter. No SDK defaults or implicit retries."""

import json
import math
from typing import Any

import httpx

from app.core.config import Settings
from app.llm.contracts import ModelError, ModelPrompt, ModelReply

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqRecommendationModel:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.client = httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            timeout=settings.llm_timeout_seconds,
            follow_redirects=False,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def rank_and_explain(self, prompt: ModelPrompt) -> ModelReply:
        key = self.settings.groq_api_key
        if key is None:
            raise ModelError("configuration")
        response_format: dict[str, Any] = {"type": "json_object"}
        if self.settings.llm_response_format == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "restaurant_ranking",
                    "strict": True,
                    "schema": prompt.schema,
                },
            }
        try:
            # Fixed HTTPS destination, no redirects, no environment proxy credentials.
            async with self.client.stream(
                "POST",
                ENDPOINT,
                headers={
                    "Authorization": f"Bearer {key.get_secret_value()}",
                },
                json={
                    "model": self.settings.llm_model,
                    "messages": [
                        {"role": "system", "content": prompt.system},
                        {"role": "user", "content": prompt.user},
                    ],
                    "response_format": response_format,
                    "temperature": 0,
                    "max_completion_tokens": self.settings.llm_max_completion_tokens,
                    "stream": False,
                },
            ) as response:
                status = response.status_code
                if status != 200:
                    category = (
                        "rate_limited"
                        if status == 429
                        else (
                            "authentication"
                            if status in (401, 403)
                            else ("provider_unavailable" if status >= 500 else "provider_rejected")
                        )
                    )
                    try:
                        delay = float(response.headers.get("retry-after", "0"))
                    except ValueError:
                        delay = self.settings.llm_timeout_seconds
                    if not math.isfinite(delay) or delay < 0:
                        delay = self.settings.llm_timeout_seconds
                    raise ModelError(
                        category, transient=status == 429 or status >= 500, retry_after=delay
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 128000:
                        raise ModelError("output_size")
        except httpx.TimeoutException as exc:
            raise ModelError("timeout") from exc
        except httpx.RequestError as exc:
            # A dropped connection can have incurred cost: do not blindly retry it.
            raise ModelError("network") from exc
        try:
            payload = json.loads(body)
            choice = payload["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ModelError("incomplete_or_refused")
            content = choice["message"]["content"]
            model = payload["model"]
            if not isinstance(content, str) or not isinstance(model, str):
                raise ValueError("wrong type")
            if model != self.settings.llm_model:
                raise ModelError("model_mismatch")
            usage = payload.get("usage") or {}
            inputs, outputs = usage.get("prompt_tokens"), usage.get("completion_tokens")
            for value in (inputs, outputs):
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError("invalid usage")
            return ModelReply(content, model, inputs, outputs)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise ModelError("provider_response") from exc
