"""Fake Muse Image: deterministic pictures, answered through the real Responses API parser.

With reference images it blends them (so a fusion of two photos looks like both); without, it paints a colour
derived from the prompt. Same inputs, same output. `current_fault` simulates refusals, bad data and errors.
"""

from __future__ import annotations

import asyncio
import hashlib
import io

from PIL import Image, ImageChops, ImageOps

from app.adapters.base import GeneratedImage
from app.adapters.meta.client import parse_generate_response
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from tests.fakes.faults import current_fault
from tests.fakes.payloads import responses_payload

SIZE = 512


def _square(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as im:
        return ImageOps.fit(im.convert("RGB"), (SIZE, SIZE), method=Image.Resampling.LANCZOS)


def render(prompt: str, refs: list[bytes]) -> bytes:
    digest = hashlib.sha256(prompt.encode() + b"".join(refs)).digest()
    if refs:
        img = _square(refs[0])
        for r in refs[1:]:
            img = ImageChops.blend(img, _square(r), 0.5)
    else:
        img = Image.new("RGB", (SIZE, SIZE), (digest[0], digest[1], digest[2]))
    out = io.BytesIO()
    img.save(out, "WEBP", quality=80)  # Muse Image returns WebP
    return out.getvalue()


class MockImageGen:
    model_id = "mock-muse-image"

    def __init__(self, delay_scale: float = 1.0) -> None:
        self.delay_scale = delay_scale
        self.turns: dict[str, tuple[str, list[bytes]]] = {}  # response id -> (prompt, refs), for chained edits

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None,
                       previous_response_id: str | None = None) -> GeneratedImage:
        """With previous_response_id, an edit turn on that image (the instruction is added to its prompt)."""
        if previous_response_id and previous_response_id in self.turns:
            base, refs = self.turns[previous_response_id]
            prompt, reference_images = f"{base} {prompt}", refs
        out = await self._generate(prompt, reference_images)
        if out.response_id:
            self.turns[out.response_id] = (prompt, list(reference_images))
        return out

    async def _generate(self, prompt: str, refs: list[bytes]) -> GeneratedImage:
        if self.delay_scale > 0:
            await asyncio.sleep(0.5 * self.delay_scale)
        fault = current_fault.get()
        if fault == "server_error":
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR)
        if fault == "refusal":
            return parse_generate_response(responses_payload(None, "Sorry, I can't create that image."), self.model_id)
        if fault == "corrupt_output":
            return parse_generate_response(responses_payload(b"\x00not-an-image"), self.model_id)
        data = await asyncio.to_thread(render, prompt, refs)
        return parse_generate_response(responses_payload(data), self.model_id)
