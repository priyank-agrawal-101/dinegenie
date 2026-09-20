"""Stable client-safe application errors and handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.contracts import ErrorCode
from app.core.logging import request_id_context

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class DatasetUnavailableError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            ErrorCode.DATASET_UNAVAILABLE, "The restaurant dataset is unavailable.", 503
        )


class NoMatchesError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            ErrorCode.NO_MATCHES,
            "No restaurants matched all selected filters.",
            404,
            {
                "suggestions": [
                    "Broaden the cuisine selection",
                    "Lower the minimum rating",
                    "Choose a less restrictive budget",
                ]
            },
        )


class RateLimitError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(ErrorCode.RATE_LIMITED, "Too many requests. Please try again later.", 429)


class RequestTimeoutError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            ErrorCode.REQUEST_TIMEOUT,
            "The recommendation request exceeded its time limit.",
            504,
        )


def _payload(
    code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id_context.get(),
            "details": details or {},
        }
    }


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def application_error(request: Request, exc: ApplicationError) -> JSONResponse:
        request.app.state.observability.record_error(exc.code)
        return JSONResponse(
            status_code=exc.status_code, content=_payload(exc.code, exc.message, exc.details)
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request.app.state.observability.record_error(ErrorCode.VALIDATION_ERROR)
        details = {
            "fields": [
                {"path": ".".join(str(item) for item in error["loc"]), "type": error["type"]}
                for error in exc.errors()
            ]
        }
        return JSONResponse(
            status_code=422,
            content=_payload(ErrorCode.VALIDATION_ERROR, "Request validation failed.", details),
        )

    @application.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        request.app.state.observability.record_error(ErrorCode.INTERNAL_ERROR)
        logger.exception("unhandled_request_error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_payload(ErrorCode.INTERNAL_ERROR, "An internal error occurred."),
        )
