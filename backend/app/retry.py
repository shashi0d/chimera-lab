"""Retry + timeout policy for adapter calls (TASKSHEET Section 5)."""

from __future__ import annotations

import asyncio
import random
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
    """Run `fn` with a per-attempt timeout. Retries RATE_LIMITED, UPSTREAM_TIMEOUT and
    retryable UPSTREAM_ERROR (429, 5xx, timeouts, connection errors) with exponential
    backoff plus jitter (base, 2x, 4x), honouring retryAfterMs (scaled by base so tests
    stay fast). Errors marked non-retryable (400, 401, 403, 404) raise at once. `before_attempt` charges the spend guard; `can_retry` lets
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
            # L1-03: jitter so parallel calls (identify A and B) don't retry in lockstep.
            await asyncio.sleep(delay * (1 + random.uniform(0, 0.25)))
    assert last is not None
    raise last
