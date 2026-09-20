"""Small, dependency-free HTTP security controls for the public API."""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.contracts import ErrorCode
from app.core.config import Settings
from app.core.logging import request_id_context


class FixedWindowRateLimiter:
    """Process-local fixed-window limiter with bounded stale-key cleanup."""

    def __init__(self, window_seconds: int) -> None:
        self.window_seconds = window_seconds
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._checks = 0

    def check(self, identity: str, bucket: str, limit: int, now: float) -> int | None:
        key = (identity, bucket)
        cutoff = now - self.window_seconds
        requests = self._requests[key]
        while requests and requests[0] <= cutoff:
            requests.popleft()
        if len(requests) >= limit:
            return max(1, math.ceil(requests[0] + self.window_seconds - now))
        requests.append(now)
        self._checks += 1
        if self._checks % 1_000 == 0:
            self._discard_stale(cutoff)
        return None

    def _discard_stale(self, cutoff: float) -> None:
        stale = [
            key for key, values in self._requests.items() if not values or values[-1] <= cutoff
        ]
        for key in stale:
            self._requests.pop(key, None)


class SecurityControlsMiddleware:
    """Enforce request-size and per-client rate policies before route work begins."""

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.settings = settings
        self.clock = clock
        self.limiter = FixedWindowRateLimiter(settings.rate_limit_window_seconds)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        if self.settings.rate_limit_enabled and path.startswith("/api/"):
            retry_after = self._check_rate_limit(scope, path)
            if retry_after is not None:
                await self._error(
                    scope,
                    send,
                    status_code=429,
                    code=ErrorCode.RATE_LIMITED,
                    message="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
                return

        if scope.get("method") in {"POST", "PUT", "PATCH"}:
            body = await self._bounded_body(scope, receive, send)
            if body is None:
                return
            delivered = False

            async def replay_body() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await self.app(scope, replay_body, send)
            return

        await self.app(scope, receive, send)

    def _check_rate_limit(self, scope: Scope, path: str) -> int | None:
        client = scope.get("client")
        identity = str(client[0]) if client else "unknown"
        now = self.clock()
        retry_after = self.limiter.check(
            identity, "api", self.settings.api_requests_per_window, now
        )
        if retry_after is not None or path != "/api/v1/recommendations":
            return retry_after
        if self.settings.llm_enabled:
            return self.limiter.check(
                identity, "recommendations-llm", self.settings.llm_requests_per_window, now
            )
        return self.limiter.check(
            identity,
            "recommendations",
            self.settings.recommendation_requests_per_window,
            now,
        )

    async def _bounded_body(self, scope: Scope, receive: Receive, send: Send) -> bytes | None:
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                declared_length = int(raw_length)
            except ValueError:
                await self._invalid_length(scope, send)
                return None
            if declared_length < 0:
                await self._invalid_length(scope, send)
                return None
            if declared_length > self.settings.max_request_body_bytes:
                await self._too_large(scope, send)
                return None

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            body.extend(message.get("body", b""))
            if len(body) > self.settings.max_request_body_bytes:
                await self._too_large(scope, send)
                return None
            if not message.get("more_body", False):
                return bytes(body)

    async def _invalid_length(self, scope: Scope, send: Send) -> None:
        await self._error(
            scope,
            send,
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid Content-Length header.",
        )

    async def _too_large(self, scope: Scope, send: Send) -> None:
        await self._error(
            scope,
            send,
            status_code=413,
            code=ErrorCode.VALIDATION_ERROR,
            message="Request body is too large.",
            details={"maximum_bytes": self.settings.max_request_body_bytes},
        )

    @staticmethod
    async def _error(
        scope: Scope,
        send: Send,
        *,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        response = JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id_context.get(),
                    "details": details or {},
                }
            },
            headers=headers,
        )
        await response(scope, _empty_receive, send)


async def _empty_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}
