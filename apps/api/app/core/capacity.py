"""Bounded asynchronous admission control."""

from __future__ import annotations

import asyncio


class CapacityExceededError(Exception):
    """No execution slot became available within the bounded queue wait."""


class ConcurrencyLimiter:
    def __init__(self, limit: int, queue_timeout_seconds: float) -> None:
        self.limit = limit
        self.queue_timeout_seconds = queue_timeout_seconds
        self._semaphore = asyncio.Semaphore(limit)

    async def acquire(self) -> None:
        try:
            async with asyncio.timeout(self.queue_timeout_seconds):
                await self._semaphore.acquire()
        except TimeoutError as exc:
            raise CapacityExceededError() from exc

    def release(self) -> None:
        self._semaphore.release()
