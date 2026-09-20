"""One shared deadline/retry budget and process-local circuit breaker."""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass

from app.api.contracts import RecommendationRequest, RecommendationResult
from app.core.capacity import CapacityExceededError, ConcurrencyLimiter
from app.core.config import Settings
from app.llm.contracts import ModelError, ModelRanking, ModelTelemetry, RecommendationModel
from app.llm.prompt import build_prompt, validate_output

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Synchronous state transitions on the API event loop; one half-open probe."""

    def __init__(self, threshold: int, cooldown: float):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.opened_at: float | None = None
        self.probing = False
        self.generation = 0

    def acquire(self, now: float) -> int | None:
        if self.opened_at is not None:
            if now - self.opened_at < self.cooldown or self.probing:
                return None
            self.probing = True
        return self.generation

    def success(self, ticket: int) -> None:
        if ticket == self.generation:
            self.failures = 0
            self.opened_at = None
            self.probing = False

    def failure(self, ticket: int, now: float) -> None:
        if ticket != self.generation:
            return
        self.failures += 1
        if self.probing or self.failures >= self.threshold:
            self.opened_at = now
            self.probing = False
            self.generation += 1

    def cancel(self, ticket: int) -> None:
        if ticket == self.generation:
            self.probing = False


@dataclass(frozen=True)
class GatewayResult:
    ranking: ModelRanking | None
    telemetry: ModelTelemetry


class ModelGateway:
    def __init__(self, model: RecommendationModel, settings: Settings):
        self.model = model
        self.settings = settings
        self.breaker = CircuitBreaker(
            settings.llm_circuit_failure_threshold, settings.llm_circuit_cooldown_seconds
        )
        self.capacity = ConcurrencyLimiter(
            settings.llm_concurrency_limit, settings.llm_queue_timeout_seconds
        )

    async def aclose(self) -> None:
        closer = getattr(self.model, "aclose", None)
        if closer is not None:
            await closer()

    async def rank(
        self,
        request: RecommendationRequest,
        candidates: list[RecommendationResult],
        dataset_version: str,
    ) -> GatewayResult:
        started = time.monotonic()
        telemetry = ModelTelemetry(model=self.settings.llm_model)
        ticket: int | None = None
        acquired = False
        ranking = None
        try:
            await self.capacity.acquire()
            acquired = True
            ticket = self.breaker.acquire(started)
            if ticket is None:
                raise ModelError("circuit_open")
            repair = False
            async with asyncio.timeout(self.settings.llm_timeout_seconds):
                for attempt in range(1 + self.settings.llm_max_retries):
                    prompt = build_prompt(
                        request,
                        candidates,
                        min(
                            self.settings.llm_max_prompt_bytes, self.settings.llm_max_prompt_tokens
                        ),
                        repair=repair,
                    )
                    telemetry.attempts += 1
                    received_usage = False
                    try:
                        reply = await self.model.rank_and_explain(prompt)
                        received_usage = True
                        telemetry.input_tokens += reply.input_tokens or 0
                        telemetry.output_tokens += reply.output_tokens or 0
                        telemetry.usage_complete &= (
                            reply.input_tokens is not None and reply.output_tokens is not None
                        )
                        ranking = validate_output(reply.text, candidates, request.limit)
                        break
                    except ModelError as exc:
                        if not received_usage:
                            telemetry.usage_complete = False
                        if (
                            exc.category == "schema"
                            or "grounding" in exc.category
                            or exc.category
                            in (
                                "candidate_ids",
                                "result_count",
                                "output_size",
                            )
                        ):
                            telemetry.validation_failures.append(exc.category)
                        else:
                            telemetry.usage_complete = False
                        if not exc.transient or attempt == self.settings.llm_max_retries:
                            raise
                        repair = exc.category == "schema"
                        remaining = self.settings.llm_timeout_seconds - (time.monotonic() - started)
                        delay = max(0.05, exc.retry_after)
                        if delay >= remaining:
                            raise
                        await asyncio.sleep(delay)
            self.breaker.success(ticket)
        except asyncio.CancelledError:
            telemetry.error_category = "cancelled"
            telemetry.usage_complete = False
            if ticket is not None:
                self.breaker.cancel(ticket)
            raise
        except CapacityExceededError:
            telemetry.error_category = "capacity_limited"
            telemetry.usage_complete = False
        except (ModelError, TimeoutError) as exc:
            telemetry.error_category = exc.category if isinstance(exc, ModelError) else "timeout"
            if telemetry.error_category == "timeout":
                telemetry.usage_complete = False
            if ticket is not None:
                self.breaker.failure(ticket, time.monotonic())
        except Exception:
            # The provider boundary must not turn an adapter bug into a public 500 or
            # leak an exception containing a key/prompt. Do not swallow cancellation.
            telemetry.error_category = "adapter_error"
            telemetry.usage_complete = False
            if ticket is not None:
                self.breaker.failure(ticket, time.monotonic())
        finally:
            if acquired:
                self.capacity.release()
            telemetry.latency_ms = round((time.monotonic() - started) * 1000, 3)
            inputs = self.settings.llm_input_usd_per_million
            outputs = self.settings.llm_output_usd_per_million
            if telemetry.usage_complete and inputs is not None and outputs is not None:
                telemetry.estimated_cost_usd = (
                    telemetry.input_tokens * inputs + telemetry.output_tokens * outputs
                ) / 1_000_000
            logger.info(
                "model_ranking_completed",
                extra={
                    **asdict(telemetry),
                    "dataset_version": dataset_version,
                },
            )
        return GatewayResult(ranking, telemetry)
