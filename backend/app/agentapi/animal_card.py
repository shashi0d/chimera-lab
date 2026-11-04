"""The animal card: one field-guide card per generated image, made on demand.

The card's text is the creature's profile, written when the image was generated (app.agentapi.creature_ai); an image
without one (an older image, or an agent run) gets it written now. Beside the main image the card shows four more
angles of the same creature, made by the image model with the image as the reference. A card is made once per image
(in the background, so a page reload does not lose it); asking again returns the same card. Only a failed card can
be made again.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.util import now_iso

log = logging.getLogger(__name__)

ANGLES: list[tuple[str, str]] = [
    ("front", "seen straight from the front"),
    ("side", "seen from its side, in full profile"),
    ("back", "seen from behind"),
    ("above", "seen in a three-quarter view from above"),
]


def angle_prompt(view: str, profile: dict[str, Any] | None, background: str) -> str:
    who = f" ({profile['summary']})" if profile and profile.get("summary") else ""
    return (f"Show this exact same creature{who}, {view}. Keep its body, proportions, number of limbs, colours, "
            "markings and art style identical to the reference image; only the camera angle changes. Full body in "
            f"frame, no other creatures, no text. {background}").strip()


def is_stale(card: dict[str, Any], stale_seconds: float) -> bool:
    if card.get("status") != "running":
        return False
    try:
        started = datetime.fromisoformat(str(card.get("startedAt")).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (datetime.now(UTC) - started).total_seconds() > stale_seconds


async def make_angles(gen: Any, files: Any, version_id: str, image: bytes, profile: dict[str, Any] | None,
                      background: str) -> tuple[list[dict[str, str]], list[str]]:
    """Four angles in parallel. A failed angle is left out (the card shows the others)."""
    from app.agentapi.files import EXT

    async def one(i: int, key: str, view: str) -> dict[str, str]:
        img = await gen.generate(angle_prompt(view, profile, background), [image], "1:1")
        ext = EXT.get(img.content_type, "webp")
        url = await files.put(f"lab/{version_id}_angle_{i}_{key}.{ext}", img.data, img.content_type)
        return {"view": key, "url": url}

    results = await asyncio.gather(*(one(i, k, v) for i, (k, v) in enumerate(ANGLES, 1)), return_exceptions=True)
    angles = [r for r in results if isinstance(r, dict)]
    errors = [f"{ANGLES[i][0]}: {r}" for i, r in enumerate(results) if isinstance(r, BaseException)]
    return angles, errors


def new_card() -> dict[str, Any]:
    return {"status": "running", "startedAt": now_iso(), "profile": None, "angles": [], "error": None}


async def build_card(a: Any, doc: dict[str, Any], image: bytes) -> dict[str, Any]:
    """The finished card for a version doc: its profile (written now if missing) and its four angles."""
    from app.agentapi.creature_ai import make_profile
    from app.evolution.live import RetryingImageGen

    svc = a.services
    profile = doc.get("profile")
    if not profile:
        context = {"title": doc.get("title"), "style": doc.get("style"), **(doc.get("generation") or {})}
        profile = await make_profile(svc.vision, image, context)
    gen = RetryingImageGen(svc.image_gen, a.settings)
    angles, errors = await make_angles(gen, a.files, doc["id"], image, profile,
                                       str(a.settings.evo_fusion_background).strip())
    if errors:
        log.warning("card %s: %d angle(s) failed: %s", doc["id"], len(errors), "; ".join(errors)[:500])
    if not profile and not angles:
        return {"status": "failed", "error": "The card could not be made. Try again.", "profile": None,
                "angles": [], "finishedAt": now_iso()}
    return {"status": "ready", "profile": profile, "angles": angles, "error": None, "finishedAt": now_iso(),
            "missingAngles": len(ANGLES) - len(angles)}
