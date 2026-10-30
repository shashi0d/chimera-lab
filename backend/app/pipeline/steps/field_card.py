"""F2: field-guide card steps: load_creature -> write_card -> store_card."""

from __future__ import annotations

from typing import Any

from app.data.loader import split_list
from app.errors import ChimeraError
from app.models.schemas import Creature, ErrorCode, FieldCard, RunResult
from app.pipeline.context import RunContext
from app.pipeline.retry import call_with_retry

PROVENANCE = "Generated fusion. Not a real animal."
MEASURE_KEYS = ("body_mass_kg", "body_length_m")


async def load_creature(ctx: RunContext) -> str:
    doc = await ctx.services.db.get("creatures", str(ctx.state["creature_id"]))
    if doc is None:
        raise ChimeraError(ErrorCode.NOT_FOUND, "This creature can't be found anymore. Fuse again, then write the card.")
    creature = Creature.model_validate(doc)
    asset = await ctx.services.db.get("assets", creature.asset_id)
    if asset is None:
        raise ChimeraError(ErrorCode.NOT_FOUND, "This creature's image can't be found anymore.")
    ctx.state["creature"] = creature
    ctx.state["image_url"] = await ctx.services.storage.get_url(str(asset["storageKey"]))
    return creature.spec.name or "Creature loaded"


def card_context(creature: Creature) -> dict[str, Any]:
    spec = creature.spec
    parents: dict[str, dict[str, Any]] = {}
    for p in spec.parents:
        facts = p.match.facts if p.match else {}
        parents[p.slot] = {
            "common_name": (p.match.common_name if p.match else p.reading.common_name) or f"animal {p.slot}",
            "scientific_name": (p.match.scientific_name if p.match else p.reading.scientific_name),
            "habitat": split_list(facts.get("habitat")),
            "diet": facts.get("diet"),
            "measurements": {k: facts[k] for k in MEASURE_KEYS if facts.get(k)},
        }
    return {
        "name": spec.name,
        "body_plan": spec.body_plan,
        "part_donors": spec.part_donors.model_dump(),
        "parents": parents,
        "real_hybrid": spec.real_hybrid.name if spec.real_hybrid else None,
        "rule_warnings": [w.message for w in spec.warnings if w.severity == "warning"],
    }


def size_line(context: dict[str, Any]) -> str:
    """Parents' recorded ranges, quoted verbatim (never averaged)."""
    parts = []
    for p in context["parents"].values():
        m = p["measurements"]
        if m.get("body_mass_kg"):
            parts.append(f"{p['common_name']} {m['body_mass_kg']} kg")
    return "Parents: " + "; ".join(parts) + "." if parts else ""


async def write_card(ctx: RunContext) -> str:
    s = ctx.services.settings
    context = card_context(ctx.state["creature"])
    card: FieldCard = await call_with_retry(
        lambda: ctx.services.vision.write_field_card(context),
        timeout=s.identify_timeout_seconds,
        base_delay=s.retry_base_seconds,
        max_attempts=s.retry_max_attempts,
        before_attempt=lambda _n: ctx.use_vision(),
        can_retry=ctx.can_use_vision,
    )
    ranges = size_line(context)
    if ranges and ranges not in card.size:
        card.size = f"{card.size} {ranges}".strip()
    # Fixed point: provenance is ours, never the model's.
    hybrid = context["real_hybrid"]
    card.provenance = PROVENANCE + (f" Its parents have a documented real hybrid, the {hybrid}." if hybrid else "")
    ctx.state["card"] = card
    return card.binomial


async def store_card(ctx: RunContext) -> str:
    creature: Creature = ctx.state["creature"]
    card: FieldCard = ctx.state["card"]
    doc = creature.dump()
    doc["card"] = card.dump()
    await ctx.services.db.put("creatures", creature.creature_id, doc)
    ctx.state["result"] = RunResult(
        asset_id=creature.asset_id, creature_id=creature.creature_id, image_url=ctx.state["image_url"],
        spec=creature.spec, card=card,
    )
    return "Card saved with the creature"
