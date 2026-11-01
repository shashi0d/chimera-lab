"""Uploads for POST /evo/agent/runs: checked, resized, identified with the v1 identify step, then discarded.

Images are never stored: the bytes live in this request only. Only the identified names go to the job.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.adapters.base import current_fault
from app.errors import ChimeraError
from app.models.schemas import AnimalReading, ErrorCode
from app.pipeline.context import InputImage, RunContext
from app.pipeline.steps import identify as identify_step
from app.services import Services

SLOTS = ("sire", "dam")
V1_SLOT = {"sire": "A", "dam": "B"}
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


async def identify(svc: Services, images: dict[str, bytes], fault: str | None = None) -> dict[str, AnimalReading]:
    """The v1 identify step (app/pipeline/steps/identify.py) over the resized photos, with its spend guard. Its
    refusals are re-worded for the agent API and name the slot as sire or dam."""
    slots = [s for s in SLOTS if s in images]
    ctx = RunContext(run=None, graph=None, services=svc, fault=fault)  # type: ignore[arg-type]
    ctx.inputs = [InputImage(slot=V1_SLOT[s], node_id=s, asset_id="", data=images[s]) for s in slots]
    token = current_fault.set(fault)
    try:
        await identify_step.run(ctx)
    except ChimeraError as exc:
        slot = next((s for s in slots if V1_SLOT[s] == exc.details.get("slot")), None)
        if exc.code == ErrorCode.HUMAN_DETECTED:
            raise refuse(ErrorCode.HUMAN_DETECTED, MSG_HUMAN, slot=slot) from exc
        if exc.code == ErrorCode.NOT_AN_ANIMAL:
            raise refuse(ErrorCode.NOT_AN_ANIMAL, MSG_NOT_ANIMAL, slot=slot) from exc
        raise
    finally:
        current_fault.reset(token)
    readings = ctx.state["readings"]
    return {s: readings[V1_SLOT[s]] for s in slots}


def needs_choice(slot: str, reading: AnimalReading, identified: dict[str, Any]) -> dict[str, Any]:
    options = []
    if reading.common_name:
        options.append({"commonName": reading.common_name, "scientificName": reading.scientific_name,
                        "confidence": round(reading.confidence, 2)})
    return {"status": "needs_choice",
            "choice": {"kind": "identify", "slot": slot, "question": QUESTION[slot], "options": options,
                       "allowOther": True},
            "identified": identified}
