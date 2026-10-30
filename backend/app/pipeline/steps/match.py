from __future__ import annotations

from app.data.loader import ChimeraData, field
from app.models.schemas import AnimalMatch, AnimalReading
from app.pipeline.context import RunContext

FACT_FIELDS = ("class", "family", "body_plan", "covering", "habitat", "realm", "diet", "locomotion",
               "limb_count", "notable_features")


def match_reading(data: ChimeraData, reading: AnimalReading) -> AnimalMatch | None:
    hit, how = data.find_by_scientific(reading.scientific_name), "scientific_name"
    if hit is None:
        hit, how = data.find_by_name(reading.common_name), "common_name"
    if hit is None and reading.scientific_name:
        hit, how = data.find_by_genus(reading.scientific_name.split()[0]), "genus"
    if hit is None:
        return None
    row, tier = hit
    animal_id = field(row, "id")
    facts = {k: str(row[k]) for k in FACT_FIELDS if row.get(k)}
    for k, v in data.measurements_for(animal_id).items():
        if k not in ("animal_id", "id") and v:
            facts[k] = str(v)
    return AnimalMatch(
        animal_id=animal_id,
        tier=tier,  # type: ignore[arg-type]
        common_name=field(row, "common_name"),
        scientific_name=field(row, "scientific_name") or None,
        matched_on=how,  # type: ignore[arg-type]
        facts=facts,
    )


async def run(ctx: RunContext) -> str:
    matches = {slot: match_reading(ctx.services.data, r) for slot, r in ctx.state["readings"].items()}
    ctx.state["matches"] = matches
    parts = []
    for slot in ("A", "B"):
        m = matches.get(slot)
        parts.append(f"{slot}: {m.common_name} (tier {m.tier})" if m else f"{slot}: unmatched")
    return ", ".join(parts)
