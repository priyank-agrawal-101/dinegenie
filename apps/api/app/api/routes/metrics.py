"""Prometheus scrape endpoint."""

import secrets

from fastapi import APIRouter, Request, Response

from app.core.metrics import METRICS_CONTENT_TYPE

router = APIRouter(tags=["operations"])


@router.get("/metrics", include_in_schema=False)
def metrics(request: Request) -> Response:
    if not request.app.state.settings.metrics_enabled:
        return Response(status_code=404)
    settings = request.app.state.settings
    configured_token = (
        settings.metrics_auth_token.get_secret_value() if settings.metrics_auth_token else ""
    )
    token_required = settings.environment in {"staging", "production"} or bool(configured_token)
    if token_required:
        authorization = request.headers.get("authorization", "")
        scheme, separator, supplied_token = authorization.partition(" ")
        supplied = (
            supplied_token.encode("utf-8")
            if separator and scheme.lower() == "bearer"
            else b""
        )
        expected = configured_token.encode("utf-8")
        if not expected or not secrets.compare_digest(supplied, expected):
            return Response(status_code=404)
    try:
        ready = request.app.state.restaurant_repository.get_dataset_version() is not None
    except Exception:
        # A scrape must remain available when its purpose is to report database failure.
        ready = False
    request.app.state.observability.set_readiness(ready)
    return Response(
        content=request.app.state.observability.render(),
        headers={"Content-Type": METRICS_CONTENT_TYPE},
    )
