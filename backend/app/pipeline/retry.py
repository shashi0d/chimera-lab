"""Retry + timeout policy for adapter calls (TASKSHEET Section 5)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.errors import RETRYABLE, ChimeraError
from app.models.schemas import ErrorCode

T = TypeVar("T")


async def call_with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    timeout: float,
    base_delay: float,
    max_attempts: int,
    before_attempt: Callable[[int], Awaitable[None] | None] | None = None,
    can_retry: Callable[[], bool] | None = None,
) -> T:
    """Run `fn` with a per-attempt timeout. Retries RATE_LIMITED / UPSTREAM_* with
    exponential backoff (base, 2x, 4x), honouring retryAfterMs (scaled by base so
    tests stay fast). `before_attempt` charges the spend guard; `can_retry` lets
    the guard stop retrying and surface the original error instead."""
    last: ChimeraError | None = None
    for attempt in range(max_attempts):
        if attempt > 0 and can_retry is not None and not can_retry():
            break
        if before_attempt is not None:
            maybe = before_attempt(attempt)
            if maybe is not None:
                await maybe
        try:
            return await asyncio.wait_for(fn(), timeout=timeout)
        except TimeoutError:
            last = ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)
        except ChimeraError as exc:
            if exc.code not in RETRYABLE or not exc.retryable:
                raise
            last = exc
        if attempt < max_attempts - 1:
            delay = base_delay * (2**attempt)
            if last.retry_after_ms:
                delay = max(delay, last.retry_after_ms / 1000 * base_delay)
            await asyncio.sleep(delay)
    assert last is not None
    raise last
