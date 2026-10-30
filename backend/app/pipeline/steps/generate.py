from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

from app.adapters.base import GeneratedImage
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.pipeline.context import RunContext
from app.pipeline.retry import call_with_retry


async def run(ctx: RunContext) -> str:
    s = ctx.services.settings
    spec = ctx.state["spec"]

    async def attempt() -> GeneratedImage:
        out = await ctx.services.image_gen.generate(spec.prompt, [i.data for i in ctx.inputs], "1:1")
        try:
            with Image.open(io.BytesIO(out.data)) as im:
                im.load()
                ctx.state["generated_size"] = im.size
        except (UnidentifiedImageError, OSError) as exc:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image model returned a broken image.") from exc
        return out

    generated = await call_with_retry(
        attempt,
        timeout=s.generate_timeout_seconds,
        base_delay=s.retry_base_seconds,
        max_attempts=s.retry_max_attempts,
        before_attempt=lambda _n: ctx.use_generation(),
        can_retry=ctx.can_generate,
    )
    ctx.state["generated"] = generated
    return f"Image ready ({ctx.generations} generation{'s' if ctx.generations != 1 else ''})"
