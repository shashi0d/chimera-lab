"""The creature a Fusion run makes: who its parents are, its image, and how it was made. `POST /evo/lab/versions/
from-run` turns it into image V1 on the canvas."""

from __future__ import annotations

from typing import Any

from app.adapters.base import DbAdapter

KIND = "fusion"


def parent_view(common: str | None, scientific: str | None = None, source: str = "name",
                confidence: float | None = None) -> dict[str, Any]:
    """A parent as the API reports it: a typed name, a photo's identified species, or an earlier creature."""
    return {"commonName": common, "scientificName": scientific, "source": source, "confidence": confidence}


def build_creature(*, creature_id: str, created_at: str, sire: dict[str, Any], dam: dict[str, Any], image_url: str,
                   generation: dict[str, Any], run_id: str, seconds: float) -> dict[str, Any]:
    """`generation` is the Fusion record (prompt, style, parents, references, profile)."""
    profile = generation.get("profile") or {}
    return {
        "creatureId": creature_id, "createdAt": created_at,
        "title": profile.get("name") or f"{sire['commonName']} × {dam['commonName']}",
        "sire": sire, "dam": dam, "imageUrl": image_url, "runId": run_id,
        "plan": generation,  # read by from-run as the image's generation record
        "stats": {"renders": 1, "seconds": seconds},
    }


class Creatures:
    def __init__(self, db: DbAdapter) -> None:
        self.db = db

    async def save(self, view: dict[str, Any], owner: str | None) -> None:
        doc = {"kind": KIND, "creatureId": view["creatureId"], "createdAt": view["createdAt"], "view": view,
               "owner": owner}
        await self.db.put("creatures", view["creatureId"], doc)
