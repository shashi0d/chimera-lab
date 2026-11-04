"""Uploads for POST /evo/agent/runs: checked, resized, identified by the vision model, then discarded.

Images are never stored: the bytes live in this request only. Only the identified names go to the job.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import ChimeraError
from app.models.schemas import AnimalReading, ErrorCode
from app.retry import call_with_retry
from app.services import Services

SLOTS = ("sire", "dam")
VISION_SLOT = {"sire": "A", "dam": "B"}  # the vision adapter's slot labels
MODES = ("realistic", "speculative", "mythic")

MSG_HUMAN = "This looks like a photo of a person. Chimera Lab only uses animal photos."
MSG_NOT_ANIMAL = "We couldn't find an animal in this image."
MSG_TYPE = "Use a JPEG, PNG or WebP image."
MSG_SIZE = "Images must be 8 MB or smaller."
MSG_CORRUPT = "We couldn't read this image. Try another photo."
QUESTION = {"sire": "Which animal is in the first photo?", "dam": "Which animal is in the second photo?"}


def refuse(code: ErrorCode, message: str, status: int = 422, **details: Any) -> ChimeraError:
    return ChimeraError(code, message, retryable=False, details=details).with_status(status)


def sniff(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_bytes(data: bytes, slot: str, max_bytes: int) -> None:
    if len(data) > max_bytes:
        raise refuse(ErrorCode.FILE_TOO_LARGE, MSG_SIZE, 413, slot=slot, maxBytes=max_bytes)
    if sniff(data) is None:  # by content, not by the file name or the declared type
        raise refuse(ErrorCode.UNSUPPORTED_FILE, MSG_TYPE, slot=slot)


def resize(data: bytes, slot: str, max_side: int) -> bytes:
    """Decode (refusing a corrupt file), fix orientation, and shrink before any model call."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((max_side, max_side), Image.LANCZOS)
            out = io.BytesIO()
            im.save(out, "JPEG", quality=90)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise refuse(ErrorCode.IMAGE_CORRUPT, MSG_CORRUPT, slot=slot) from exc


async def prepare(data: bytes, slot: str, svc: Services) -> bytes:
    s = svc.settings
    check_bytes(data, slot, s.evo_max_upload_bytes)
    return await asyncio.to_thread(resize, data, slot, s.evo_identify_max_side)


async def identify(svc: Services, images: dict[str, bytes]) -> dict[str, AnimalReading]:
    """Read each resized photo with the vision model (in parallel, with the shared retry policy). A person or a
    non-animal is refused, naming the slot as sire or dam."""
    st = svc.settings
    slots = [s for s in SLOTS if s in images]

    async def read(slot: str) -> AnimalReading:
        return await call_with_retry(lambda: svc.vision.describe_animal(images[slot], VISION_SLOT[slot]),
                                     timeout=st.identify_timeout_seconds, base_delay=st.retry_base_seconds,
                                     max_attempts=st.retry_max_attempts)

    readings = dict(zip(slots, await asyncio.gather(*(read(s) for s in slots))))
    for slot, reading in readings.items():
        if reading.contains_human:
            raise refuse(ErrorCode.HUMAN_DETECTED, MSG_HUMAN, slot=slot)
        if not reading.is_animal:
            raise refuse(ErrorCode.NOT_AN_ANIMAL, MSG_NOT_ANIMAL, slot=slot)
    return readings


def needs_choice(slot: str, reading: AnimalReading, identified: dict[str, Any]) -> dict[str, Any]:
    options = []
    if reading.common_name:
        options.append({"commonName": reading.common_name, "scientificName": reading.scientific_name,
                        "confidence": round(reading.confidence, 2)})
    return {"status": "needs_choice",
            "choice": {"kind": "identify", "slot": slot, "question": QUESTION[slot], "options": options,
                       "allowOther": True},
            "identified": identified}
