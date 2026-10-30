from __future__ import annotations

import asyncio
import hashlib
import io

from PIL import Image, UnidentifiedImageError

from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.pipeline.context import RunContext


async def run(ctx: RunContext) -> str:
    async def load(inp) -> None:  # type: ignore[no-untyped-def]
        meta = await ctx.services.db.get("assets", inp.asset_id)
        if meta is None:
            raise ChimeraError(ErrorCode.IMAGE_CORRUPT, f"Image {inp.slot} is missing. Upload it again.",
                               details={"slot": inp.slot})
        inp.data = await ctx.services.storage.get(meta["storageKey"])
        inp.sha256 = hashlib.sha256(inp.data).hexdigest()
        try:
            with Image.open(io.BytesIO(inp.data)) as im:
                im.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ChimeraError(ErrorCode.IMAGE_CORRUPT, f"Image {inp.slot} could not be read.",
                               details={"slot": inp.slot}) from exc

    await asyncio.gather(*(load(i) for i in ctx.inputs))
    if ctx.inputs[0].sha256 == ctx.inputs[1].sha256:
        raise ChimeraError(ErrorCode.DUPLICATE_INPUTS, "Both inputs are the same image.")
    return "Two distinct images loaded"
