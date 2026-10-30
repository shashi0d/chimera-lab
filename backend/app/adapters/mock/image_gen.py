"""Mock image generation.

Instead of a fixed fixture, it paints a deterministic "specimen plate" from
the two reference images (A's head region blended over B's body), so mock
screenshots look like a fusion and the same inputs always give the same
output. See DECISIONS.md D-007.
"""

from __future__ import annotations

import asyncio
import hashlib
import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.adapters.base import GeneratedImage, current_fault
from app.errors import ChimeraError
from app.models.schemas import ErrorCode

SIZE = 1024
PAPER = (241, 235, 222)
INK = (31, 42, 36)


def _square(data: bytes, size: int) -> Image.Image:
    with Image.open(io.BytesIO(data)) as im:
        return ImageOps.fit(im.convert("RGB"), (size, size), method=Image.Resampling.LANCZOS)


def _blob_mask(size: int, seed: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    cx = size * (0.36 + (seed % 7) / 100)
    cy = size * (0.38 + (seed % 5) / 100)
    r = size * 0.27
    d.ellipse([cx - r, cy - r * 0.9, cx + r, cy + r * 0.9], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(size * 0.05))


def render_plate(prompt: str, refs: list[bytes]) -> bytes:
    seed = int(hashlib.sha256(b"".join(hashlib.sha256(r).digest() for r in refs)).hexdigest()[:8], 16)
    inner = SIZE - 128
    a = _square(refs[0], inner)
    b = _square(refs[1] if len(refs) > 1 else refs[0], inner)
    body = ImageOps.autocontrast(b, cutoff=1)
    head = ImageOps.autocontrast(a, cutoff=1)
    fused = Image.composite(head, body, _blob_mask(inner, seed))
    # Shared tone so the two halves read as one animal.
    toned = ImageChops.blend(fused, ImageOps.colorize(ImageOps.grayscale(fused), INK, PAPER), 0.28)

    plate = Image.new("RGB", (SIZE, SIZE), PAPER)
    plate.paste(toned, (64, 40))
    d = ImageDraw.Draw(plate)
    d.rectangle([63, 39, 64 + inner, 40 + inner], outline=INK, width=2)
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    d.text((64, SIZE - 70), f"GENERATED FUSION  ·  MOCK  ·  PLATE {seed % 1000:03d}", fill=INK, font=font)
    out = io.BytesIO()
    plate.save(out, "JPEG", quality=90)
    return out.getvalue()


class MockImageGen:
    model_id = "mock-muse-image"

    def __init__(self, delay_scale: float = 1.0) -> None:
        self.delay_scale = delay_scale

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None) -> GeneratedImage:
        fault = current_fault.get()
        seed = int(hashlib.sha256(b"".join(reference_images)).hexdigest()[:4], 16)
        if self.delay_scale > 0:
            await asyncio.sleep((2.0 + (seed % 2000) / 1000) * self.delay_scale)
        if fault == "server_error":
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR)
        if fault == "refusal":
            raise ChimeraError(ErrorCode.MODEL_REFUSED, "The image model declined this request.")
        if fault == "corrupt_output":
            return GeneratedImage(data=b"\x00not-an-image", content_type="image/jpeg", model=self.model_id)
        data = await asyncio.to_thread(render_plate, prompt, reference_images)
        return GeneratedImage(data=data, content_type="image/jpeg", model=self.model_id)
