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
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

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


HEAD_RE = re.compile(r"Reference image (\d) shows [^.]*\. Use it only for the [^.]*\bhead\b")


def head_donor_index(prompt: str) -> int:
    """Which reference the prompt assigns the head to (the real model reads the same sentence)."""
    m = HEAD_RE.search(prompt)
    return int(m.group(1)) - 1 if m else 0


def render_plate(prompt: str, refs: list[bytes]) -> bytes:
    seed = int(hashlib.sha256(b"".join(hashlib.sha256(r).digest() for r in refs)).hexdigest()[:8], 16)
    inner = SIZE
    h = head_donor_index(prompt) if len(refs) > 1 else 0
    a = _square(refs[h], inner)  # head donor
    b = _square(refs[1 - h] if len(refs) > 1 else refs[0], inner)  # body donor
    body = ImageOps.autocontrast(b, cutoff=1)
    head = ImageOps.autocontrast(a, cutoff=1)
    fused = Image.composite(head, body, _blob_mask(inner, seed))
    # Shared tone so the two halves read as one animal.
    toned = ImageChops.blend(fused, ImageOps.colorize(ImageOps.grayscale(fused), INK, PAPER), 0.28)

    # Full-bleed: the UI supplies the plate frame and the "Generated fusion" caption (PV1-08).
    plate = toned.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    plate.save(out, "JPEG", quality=90)
    return out.getvalue()


class MockImageGen:
    model_id = "mock-muse-image"

    def __init__(self, delay_scale: float = 1.0) -> None:
        self.delay_scale = delay_scale

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None) -> GeneratedImage:
        fault = current_fault.get()
        seed = int(hashlib.sha256(b"".join(reference_images) + prompt.encode()).hexdigest()[:4], 16)
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
