"""Real hybrids (D1-01) and mythology resemblance (D1-04) for the matched pair."""

from __future__ import annotations

from app.data.loader import HybridMatch, MythMatch, field
from app.models.schemas import MythologyMatch, RealHybrid
from app.pipeline.context import RunContext

HYBRID_FACT_KEYS = ("fertility", "confidence", "generation", "sex_specific_fertility", "occurs_in", "cross", "notes",
                    "documented", "source_url")


def to_real_hybrid(m: HybridMatch, names: dict[str, str]) -> RealHybrid:
    row = m.row
    roles = {m.a.role: ("A", m.a), m.b.role: ("B", m.b)}
    father = roles.get("father")
    mother = roles.get("mother")
    cross = None
    if father and mother:
        cross = f"father: {names[father[0]]} ({father[1].name}) × mother: {names[mother[0]]} ({mother[1].name})"
    facts = {k: str(row[k]) for k in HYBRID_FACT_KEYS if row.get(k) not in (None, "")}
    if cross:
        facts["cross"] = cross
    via = "genus" if "genus" in (m.a.via, m.b.via) else (m.a.via or "id")
    return RealHybrid(
        hybrid_id=field(row, "hybrid_id"),
        name=field(row, "common_name") or field(row, "hybrid_id"),
        facts=facts,
        father=father[1].name if father else None,
        mother=mother[1].name if mother else None,
        cross=cross,
        confidence=str(row["confidence"]) if row.get("confidence") else None,
        fertility=str(row["fertility"]) if row.get("fertility") else None,
        matched_via=via,
    )


def to_myth(m: MythMatch) -> MythologyMatch:
    row = m.row
    verification = str(row.get("verification") or "unverified")
    return MythologyMatch(
        creature_name=str(row.get("creature_name", "")),
        culture=str(row.get("culture", "")),
        component_animals=str(row.get("component_animals", "")),
        component_parts=str(row.get("component_parts", "")),
        has_human_part=str(row.get("has_human_part", "")).lower() == "yes",
        matched=m.matched,
        match_kind=m.how,
        verification=verification,
        # Never present an unverified row as verified (D1-04): only an explicit "verified ..." counts.
        verified=verification.strip().lower().startswith("verified"),
        source_url=str(row.get("source_url", "")),
    )


async def run(ctx: RunContext) -> str:
    matches = ctx.state["matches"]
    a, b = matches.get("A"), matches.get("B")
    ctx.state["real_hybrid"] = None
    ctx.state["real_hybrids"] = []
    ctx.state["mythology"] = []
    if not a or not b:
        return "Skipped: an animal is unmatched"
    data = ctx.services.data
    names = {"A": a.common_name, "B": b.common_name}
    hybrids = [to_real_hybrid(m, names) for m in data.find_hybrids(a.animal_id, b.animal_id)]
    ctx.state["real_hybrids"] = hybrids
    ctx.state["real_hybrid"] = hybrids[0] if hybrids else None
    if len(hybrids) > 1:
        hybrids[0].facts["also_known"] = "|".join(h.name for h in hybrids[1:])
    a_row, b_row = data.by_id(a.animal_id), data.by_id(b.animal_id)
    myths = [to_myth(m) for m in data.find_mythology(a_row[0], b_row[0])] if a_row and b_row else []
    ctx.state["mythology"] = myths
    parts = [f"Real hybrid{'s' if len(hybrids) > 1 else ''}: {', '.join(h.name for h in hybrids)}" if hybrids else "No documented hybrid"]
    if myths:
        parts.append(f"resembles {', '.join(m.creature_name for m in myths[:3])}" + (f" +{len(myths) - 3}" if len(myths) > 3 else ""))
    return "; ".join(parts)


