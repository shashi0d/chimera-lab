"""Mock vision + planning adapter.

Identification is deterministic and survives re-encoding: the image's average
hue picks an animal from MOCK_SPECIES. The shipped fixture photos in
`backend/tests/fixtures/images/` are painted in those hues, so dropping
`lion.jpg` really reads as a lion in mock mode.
"""

from __future__ import annotations

import asyncio
import colorsys
import io
from typing import Any

from PIL import Image

from app.adapters.base import current_fault
from app.errors import ChimeraError
from app.models.schemas import AnimalReading, ErrorCode, FieldCard, FusionPlan, PartDonors

# (hue degrees, common name, scientific name, body plan, visible parts)
MOCK_SPECIES: list[tuple[int, str, str, str, list[str]]] = [
    (0, "Scarlet macaw", "Ara macao", "avian", ["head", "beak", "wings", "feathers", "tail", "talons"]),
    (25, "Red fox", "Vulpes vulpes", "quadruped", ["head", "ears", "fur", "legs", "tail"]),
    (40, "Lion", "Panthera leo", "quadruped", ["head", "mane", "fur", "legs", "tail"]),
    (55, "Tiger", "Panthera tigris", "quadruped", ["head", "striped fur", "legs", "tail"]),
    (85, "Green iguana", "Iguana iguana", "quadruped", ["head", "scales", "dewlap", "legs", "tail"]),
    (120, "Poison dart frog", "Dendrobates tinctorius", "quadruped", ["head", "skin", "legs"]),
    (160, "Sea turtle", "Chelonia mydas", "quadruped", ["head", "shell", "flippers"]),
    (195, "Bottlenose dolphin", "Tursiops truncatus", "aquatic", ["head", "rostrum", "fins", "tail fluke"]),
    (220, "Blue whale", "Balaenoptera musculus", "aquatic", ["head", "baleen", "fins", "tail fluke"]),
    (250, "Common octopus", "Octopus vulgaris", "cephalopod", ["mantle", "arms", "suckers", "skin"]),
    (280, "Emperor penguin", "Aptenodytes forsteri", "avian", ["head", "beak", "flippers", "feathers"]),
    (320, "Flamingo", "Phoenicopterus roseus", "avian", ["head", "beak", "wings", "feathers", "legs"]),
]


def _mean_hue(image: bytes) -> tuple[float, float]:
    with Image.open(io.BytesIO(image)) as im:
        small = im.convert("RGB").resize((64, 64))
        pixels = list(small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata())
    # Saturation-weighted circular mean of hue, so backgrounds barely count.
    import math

    sx = sy = wsum = 0.0
    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.45 or v < 0.25:  # ignore backdrop and shadows
            continue
        w = s * v
        sx += math.cos(h * 2 * math.pi) * w
        sy += math.sin(h * 2 * math.pi) * w
        wsum += w
    if wsum == 0:
        return 0.0, 0.0
    hue = (math.degrees(math.atan2(sy, sx)) + 360) % 360
    return hue, wsum / len(pixels)


def species_for_hue(hue: float) -> tuple[int, str, str, str, list[str]]:
    def dist(entry: tuple[int, str, str, str, list[str]]) -> float:
        d = abs(entry[0] - hue) % 360
        return min(d, 360 - d)

    return min(MOCK_SPECIES, key=dist)


class MockVision:
    model_id = "mock-muse-spark"

    def __init__(self, delay_scale: float = 1.0) -> None:
        self.delay_scale = delay_scale

    async def _delay(self, seconds: float) -> None:
        if self.delay_scale > 0:
            await asyncio.sleep(seconds * self.delay_scale)

    async def describe_animal(self, image: bytes, slot: str) -> AnimalReading:
        await self._delay(0.8)
        fault = current_fault.get()
        if fault == "timeout":
            raise ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)
        if fault == "rate_limit":
            raise ChimeraError(ErrorCode.RATE_LIMITED, retry_after_ms=4000)
        if fault == "not_animal" and slot == "B":
            return AnimalReading(
                is_animal=False, confidence=0.93, notes="Looks like a houseplant on a windowsill."
            )
        if fault == "human" and slot == "A":
            return AnimalReading(is_animal=True, contains_human=True, confidence=0.9, notes="A person is visible.")
        hue, strength = await asyncio.to_thread(_mean_hue, image)
        _, common, scientific, plan, parts = species_for_hue(hue)
        return AnimalReading(
            is_animal=True,
            contains_human=False,
            common_name=common,
            scientific_name=scientific,
            confidence=round(min(0.97, 0.75 + strength * 2), 2),
            visible_parts=parts,
            body_plan=plan,
            notes=f"Mock reading from dominant hue {hue:.0f} degrees.",
        )

    async def plan_fusion(self, context: dict[str, Any]) -> FusionPlan:
        await self._delay(0.6)
        readings = context["readings"]
        pins = context.get("donor_pins") or {}
        donors = PartDonors(**{"head": "A", "body": "B", "limbs": "B", "covering": "A", "tail": "A", **pins})
        body_reading = readings[donors.body]
        other = readings["A" if donors.body == "B" else "B"]
        body_plan = body_reading.get("bodyPlan") or other.get("bodyPlan") or "quadruped"
        a_name = (readings[donors.head].get("commonName") or "animal").split()[-1]
        b_name = (body_reading.get("commonName") or "animal").split()[-1]
        return FusionPlan(
            body_plan=body_plan,
            part_donors=donors,
            rationale=(
                f"Keep the {b_name}'s {body_plan} frame so the creature can stand and move, "
                f"and give it the {a_name}'s head and covering as the recognisable signature."
            ),
            name_suggestion=f"{a_name[:3].title()}{b_name[-4:].lower()}",
        )

    async def write_field_card(self, context: dict[str, Any]) -> FieldCard:
        await self._delay(0.7)
        fault = current_fault.get()
        if fault == "timeout":
            raise ChimeraError(ErrorCode.UPSTREAM_TIMEOUT)
        if fault == "rate_limit":
            raise ChimeraError(ErrorCode.RATE_LIMITED, retry_after_ms=4000)
        if fault == "server_error":
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR)
        parents = context["parents"]
        donors = context["part_donors"]
        head = parents[donors["head"]]
        body = parents[donors["body"]]
        genus = (head.get("scientific_name") or "Chimaera x").split()[0]
        epithet = ((body.get("scientific_name") or "x ignota").split() + ["ignota"])[1]
        habitats = sorted({h for p in parents.values() for h in p.get("habitat", [])})
        return FieldCard(
            common_name=context.get("name") or f"{head['common_name']} × {body['common_name']}",
            binomial=f"{genus} {epithet[:4].lower()}oides",
            habitat=(", ".join(habitats[:3]) + " (inherited from both parents)") if habitats else "Unknown: neither parent has habitat data.",
            diet=body.get("diet") or head.get("diet") or "Unknown",
            size="Unknown for the fusion itself; the parents' recorded ranges bound it.",
            behaviour=(
                f"Moves like a {body['common_name'].lower()} and hunts or forages with the senses of a "
                f"{head['common_name'].lower()}. Mock card: written without a model."
            ),
        )
