from __future__ import annotations

import asyncio

from app.errors import ChimeraError
from app.models.schemas import AnimalReading, ErrorCode
from app.pipeline.context import RunContext
from app.pipeline.retry import call_with_retry


async def run(ctx: RunContext) -> str:
    s = ctx.services.settings

    async def read(inp) -> AnimalReading:  # type: ignore[no-untyped-def]
        return await call_with_retry(
            lambda: ctx.services.vision.describe_animal(inp.data, inp.slot),
            timeout=s.identify_timeout_seconds,
            base_delay=s.retry_base_seconds,
            max_attempts=s.retry_max_attempts,
            before_attempt=lambda _n: ctx.use_vision(),
            can_retry=ctx.can_use_vision,
        )

    readings = await asyncio.gather(*(read(i) for i in ctx.inputs))
    for inp, reading in zip(ctx.inputs, readings):
        if reading.contains_human:
            raise ChimeraError(
                ErrorCode.HUMAN_DETECTED,
                f"Image {inp.slot} shows a person. Use a photo with only the animal.",
                details={"slot": inp.slot},
            )
        if not reading.is_animal:
            raise ChimeraError(
                ErrorCode.NOT_AN_ANIMAL,
                f"Image {inp.slot} doesn't look like an animal.",
                details={"slot": inp.slot},
            )
    ctx.state["readings"] = {inp.slot: r for inp, r in zip(ctx.inputs, readings)}
    names = [r.common_name or "unknown animal" for r in readings]
    return f"{names[0]} and {names[1]}"
