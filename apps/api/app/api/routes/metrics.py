"""Prometheus scrape endpoint."""

from fastapi import APIRouter, Request, Response

from app.core.metrics import METRICS_CONTENT_TYPE

router = APIRouter(tags=["operations"])


@router.get("/metrics", include_in_schema=False)
def metrics(request: Request) -> Response:
    if not request.app.state.settings.metrics_enabled:
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
