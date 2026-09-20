"""Structured application logging and request correlation."""

from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestMetrics(Protocol):
    def record_http_request(
        self, method: str, path: str, status_code: int, duration_seconds: float
    ) -> None: ...


_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "additional_preferences",
    "authorization",
    "cookie",
    "groq_api_key",
    "password",
    "preferences",
    "prompt",
    "secret",
    "set_cookie",
}


def _safe_log_value(key: str, value: Any) -> Any:
    normalized = key.casefold().replace("-", "_")
    if normalized in _SENSITIVE_KEYS or normalized.endswith(("_api_key", "_password", "_secret")):
        return _REDACTED
    if isinstance(value, dict):
        return {nested: _safe_log_value(str(nested), item) for nested, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_log_value(key, item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    """Serialize application log records as one JSON object per line."""

    _reserved = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for key, value in record.__dict__.items():
            if key not in self._reserved and not key.startswith("_"):
                payload[key] = _safe_log_value(key, value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Configure root logging once per application instance."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


class RequestContextMiddleware:
    """Attach a trusted request ID and emit one completion event."""

    def __init__(self, app: ASGIApp, metrics: RequestMetrics) -> None:
        self.app = app
        self.metrics = metrics
        self.logger = logging.getLogger("app.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        token: Token[str] = request_id_context.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            method = str(scope.get("method", "OTHER"))
            path = str(scope.get("path", ""))
            self.metrics.record_http_request(method, path, status_code, elapsed_ms / 1000)
            self.logger.info(
                "request_completed",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": elapsed_ms,
                },
            )
            request_id_context.reset(token)
