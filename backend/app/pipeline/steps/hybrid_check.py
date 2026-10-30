from __future__ import annotations

from app.data.loader import field
from app.models.schemas import RealHybrid
from app.pipeline.context import RunContext


async def run(ctx: RunContext) -> str:
    a, b = ctx.state["matches"].get("A"), ctx.state["matches"].get("B")
    ctx.state["real_hybrid"] = None
    if not a or not b:
        return "Skipped: an animal is unmatched"
    rows = ctx.services.data.find_hybrids(a.animal_id, b.animal_id)
    if not rows:
        return "No documented hybrid"
    row = rows[0]
    facts = {k: str(v) for k, v in row.items() if k not in ("id", "name") and v not in (None, "")}
    if len(rows) > 1:
        facts["also_known"] = "|".join(field(r, "common_name") for r in rows[1:])
    ctx.state["real_hybrid"] = RealHybrid(hybrid_id=field(row, "id"), name=field(row, "common_name"), facts=facts)
    return f"Real hybrid exists: {field(row, 'common_name')}"
