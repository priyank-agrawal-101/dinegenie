"""Prometheus metrics with an intentionally small, controlled label space."""

from __future__ import annotations

from pathlib import Path

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client.exposition import generate_latest

from app.api.contracts import ErrorCode, RecommendationResponse
from app.llm.contracts import PROMPT_VERSION, ModelTelemetry

METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST

_ROUTES = {
    "/health/live": "health_live",
    "/health/ready": "health_ready",
    "/metrics": "metrics",
    "/api/v1/metadata/locations": "metadata_locations",
    "/api/v1/metadata/cuisines": "metadata_cuisines",
    "/api/v1/metadata/budget-bands": "metadata_budget_bands",
    "/api/v1/recommendations": "recommendations",
}


def route_label(path: str) -> str:
    """Collapse arbitrary paths to prevent attacker-controlled label cardinality."""

    return _ROUTES.get(path, "unmatched")


class Observability:
    """Own one isolated registry so application factories and tests never share state."""

    def __init__(self, ingestion_metrics_file: Path) -> None:
        self.registry = CollectorRegistry()
        self.ingestion_metrics_file = ingestion_metrics_file
        self.http_requests = Counter(
            "restaurant_http_requests_total",
            "Completed HTTP requests.",
            ("method", "route", "status"),
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "restaurant_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            ("method", "route"),
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 8, 15),
            registry=self.registry,
        )
        self.application_errors = Counter(
            "restaurant_application_errors_total",
            "Stable application errors returned to clients.",
            ("code",),
            registry=self.registry,
        )
        self.recommendations = Counter(
            "restaurant_recommendation_requests_total",
            "Completed recommendation requests by ranking mode and controlled versions.",
            ("mode", "dataset_version", "prompt_version", "model_version"),
            registry=self.registry,
        )
        self.model_requests = Counter(
            "restaurant_model_requests_total",
            "Completed model ranking operations by bounded outcome category.",
            ("outcome", "model_version", "prompt_version"),
            registry=self.registry,
        )
        self.model_validation_failures = Counter(
            "restaurant_model_validation_failures_total",
            "Rejected model responses by bounded validation category.",
            ("category", "model_version", "prompt_version"),
            registry=self.registry,
        )
        self.model_tokens = Counter(
            "restaurant_model_tokens_total",
            "Reported model tokens by direction.",
            ("direction", "model_version"),
            registry=self.registry,
        )
        self.model_estimated_cost = Counter(
            "restaurant_model_estimated_cost_usd_total",
            "Estimated model cost in USD when complete provider usage is available.",
            ("model_version",),
            registry=self.registry,
        )
        self.readiness = Gauge(
            "restaurant_readiness_status",
            "One when the database is reachable and an active dataset exists.",
            registry=self.registry,
        )
        self.readiness.set(0)

    def record_http_request(
        self, method: str, path: str, status_code: int, duration_seconds: float
    ) -> None:
        route = route_label(path)
        normalized_method = (
            method if method in {"GET", "POST", "PUT", "PATCH", "DELETE"} else "OTHER"
        )
        self.http_requests.labels(normalized_method, route, str(status_code)).inc()
        self.http_duration.labels(normalized_method, route).observe(duration_seconds)

    def record_error(self, code: ErrorCode) -> None:
        self.application_errors.labels(code.value).inc()

    def set_readiness(self, ready: bool) -> None:
        self.readiness.set(1 if ready else 0)

    def record_recommendation(
        self, response: RecommendationResponse, telemetry: ModelTelemetry | None
    ) -> None:
        model_version = telemetry.model if telemetry is not None else "none"
        prompt_version = telemetry.prompt_version if telemetry is not None else "none"
        self.recommendations.labels(
            response.meta.ranking_mode,
            response.meta.dataset_version,
            prompt_version,
            model_version,
        ).inc()
        if telemetry is None:
            return
        outcome = telemetry.error_category or "success"
        self.model_requests.labels(outcome, model_version, PROMPT_VERSION).inc()
        for category in telemetry.validation_failures:
            self.model_validation_failures.labels(category, model_version, PROMPT_VERSION).inc()
        self.model_tokens.labels("input", model_version).inc(telemetry.input_tokens)
        self.model_tokens.labels("output", model_version).inc(telemetry.output_tokens)
        if telemetry.estimated_cost_usd is not None:
            self.model_estimated_cost.labels(model_version).inc(telemetry.estimated_cost_usd)

    def render(self) -> bytes:
        payload = bytearray(generate_latest(self.registry))
        try:
            if self.ingestion_metrics_file.stat().st_size <= 65_536:
                ingestion = self.ingestion_metrics_file.read_bytes()
                if ingestion:
                    eof = b"# EOF\n"
                    if payload.endswith(eof):
                        del payload[-len(eof) :]
                    elif payload and not payload.endswith(b"\n"):
                        payload.extend(b"\n")
                    payload.extend(ingestion)
                    payload.extend(eof)
        except (FileNotFoundError, OSError):
            pass
        return bytes(payload)
