import asyncio

import pytest

from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.pipeline.retry import call_with_retry


async def test_retries_retryable_then_succeeds():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR)
        return "ok"

    assert await call_with_retry(fn, timeout=1, base_delay=0.001, max_attempts=3) == "ok"
    assert len(calls) == 3


async def test_non_retryable_raises_immediately():
    calls = []

    async def fn():
        calls.append(1)
        raise ChimeraError(ErrorCode.MODEL_REFUSED)

    with pytest.raises(ChimeraError) as e:
        await call_with_retry(fn, timeout=1, base_delay=0.001, max_attempts=3)
    assert e.value.code == ErrorCode.MODEL_REFUSED and len(calls) == 1


async def test_timeout_maps_to_upstream_timeout():
    async def fn():
        await asyncio.sleep(1)

    with pytest.raises(ChimeraError) as e:
        await call_with_retry(fn, timeout=0.01, base_delay=0.001, max_attempts=2)
    assert e.value.code == ErrorCode.UPSTREAM_TIMEOUT


async def test_budget_stops_retries_and_surfaces_original_error():
    budget = {"left": 1}
    calls = []

    def charge(_n):
        budget["left"] -= 1

    async def fn():
        calls.append(1)
        raise ChimeraError(ErrorCode.RATE_LIMITED, retry_after_ms=10)

    with pytest.raises(ChimeraError) as e:
        await call_with_retry(fn, timeout=1, base_delay=0.001, max_attempts=3, before_attempt=charge,
                              can_retry=lambda: budget["left"] > 0)
    assert e.value.code == ErrorCode.RATE_LIMITED and len(calls) == 1


async def test_honours_retry_after_scaled_by_base():
    seen = []

    async def fn():
        seen.append(asyncio.get_event_loop().time())
        if len(seen) == 1:
            raise ChimeraError(ErrorCode.RATE_LIMITED, retry_after_ms=4000)
        return 1

    await call_with_retry(fn, timeout=1, base_delay=0.01, max_attempts=2)
    assert seen[1] - seen[0] >= 0.035  # 4s * 0.01 scale
