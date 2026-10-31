"""Section 4.1 (route the pair) and 4.2 (host and silhouette)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evolution.data import Animal, Taxonomy, known_pairs
from app.evolution.genome import Genome

LABEL_HYBRID = "real hybrid precedent"
LABEL_CLOSE = "plausible hybrid of close relatives, no documented cross"
LABEL_CHIMERA = "speculative chimera, no real-world precedent"
LABEL_MYTHIC = "mythic design"
LABEL_SPECULATIVE = "speculative design, no real-world precedent"


@dataclass
class Route:
    sire: Animal
    dam: Animal
    mode: str
    reason: str
    labels: list[str]
    cards: list[str]
    pair: dict[str, Any] | None = None  # known-pair override, roles resolved to animal ids
    processes: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        """Ordered (sire, dam): never sorted (RC-R2-01)."""
        return (self.sire.id, self.dam.id)

    def public(self) -> dict[str, Any]:
        return {"sire": self.sire.id, "dam": self.dam.id, "mode": self.mode, "reason": self.reason,
                "known_pair": self.pair["id"] if self.pair else None, "labels": self.labels, "cards": self.cards}


def _resolve_roles(obj: Any, sire: str, dam: str) -> Any:
    if isinstance(obj, str):
        return {"sire": sire, "dam": dam}.get(obj, obj)
    if isinstance(obj, list):
        return [_resolve_roles(x, sire, dam) for x in obj]
    if isinstance(obj, dict):
        return {k: (_resolve_roles(v, sire, dam) if k in ("donor", "host") else
                    _resolve_roles(v, sire, dam) if isinstance(v, dict) else v) for k, v in obj.items()}
    return obj


def find_known_pair(sire: Animal, dam: Animal) -> dict[str, Any] | None:
    for p in known_pairs():
        hit = sire.id in p["sire"] and dam.id in p["dam"]
        if p.get("either_order"):
            hit = hit or (dam.id in p["sire"] and sire.id in p["dam"])
        if hit and sire.id != dam.id:
            resolved = _resolve_roles(p, sire.id, dam.id)
            resolved["host"] = _resolve_roles(p.get("host"), sire.id, dam.id)
            return resolved
    return None


def route(sire: Animal, dam: Animal, tax: Taxonomy, myth: bool = False) -> Route:
    """KNOWN_PAIRS, then documented or same-genus hybrids, then myth, else chimera."""
    order = ["RC-R2-01"]
    pair = find_known_pair(sire, dam)
    if pair:
        return Route(sire, dam, "hybrid", f"known pair: {pair['name']}", [LABEL_HYBRID],
                     order + ["RC-R2-16", *pair["cards"]], pair, list(pair.get("processes", [])))
    if tax.documented_hybrid(sire, dam):
        return Route(sire, dam, "hybrid", "documented hybrid in chimera_data.json", [LABEL_HYBRID],
                     order + ["RC-R2-16"], None, ["in-between blend as in real hybrids"])
    if sire.genus and sire.genus == dam.genus:
        return Route(sire, dam, "hybrid", f"same genus ({sire.genus})", [LABEL_CLOSE],
                     order + ["RC-R2-16", "RC-R1-14"], None, ["in-between blend as in real hybrids"])
    distant = order + ["RC-R1-14", "RC-R2-16", "RC-R5-10"]
    if myth:
        return Route(sire, dam, "mythic", "distant pair, user asked for myth", [LABEL_MYTHIC, LABEL_SPECULATIVE],
                     distant + ["RC-R7-02"], None, ["myth-style part swap, labeled as myth"])
    return Route(sire, dam, "chimera", "distant pair: no documented hybrid and different genus", [LABEL_CHIMERA],
                 distant, None, ["chimera patchwork: each region is one parent's tissue"])


def choose_host(r: Route, user_host: str | None = None) -> tuple[str | None, list[str], str]:
    """Hybrid: no single host unless the override names a frame donor. Chimera and mythic:
    the more structured body schema, unless the user picks (RC-R6-08, RC-R6-09, RC-R5-02)."""
    if r.mode == "hybrid":
        host = r.pair.get("host") if r.pair else None
        return host, ["RC-R2-06"], ("frame donor from the known-pair override" if host else "no single host: frame is a BLEND")
    if user_host in ("sire", "dam"):
        pick = r.sire if user_host == "sire" else r.dam
        return pick.id, ["RC-R6-01", "RC-R5-02"], f"user picked the {user_host}"
    s, d = r.sire, r.dam
    ranked = sorted([s, d], key=lambda a: (a.structure_rank, a.mass_kg or 0.0, a is s), reverse=True)
    host = ranked[0]
    if s.structure_rank != d.structure_rank:
        why = f"{host.common_name} has the more structured body schema"
    else:
        why = f"equal schema structure; {host.common_name} is the larger animal"
    return host.id, ["RC-R6-08", "RC-R6-09", "RC-R5-02"], why


FRAME_WORDS = {
    "quadruped": "four-legged {name} frame",
    "winged": "upright {name} frame on two legs",
    "biped": "upright two-legged {name} frame",
    "finned": "streamlined {name} frame",
    "serpentine": "long limbless {name} frame",
    "arthropod": "segmented {name} frame",
    "soft_bodied": "soft {name} body",
    "other": "{name} frame",
}


def silhouette(g: Genome, tax: Taxonomy, pair: dict[str, Any] | None = None) -> str:
    """One sentence naming the intended silhouette (RC-R7-06). Recomputed after the physical checks."""
    if pair and pair.get("silhouette"):
        return pair["silhouette"]
    sire, dam = tax.animals[g.parents.sire], tax.animals[g.parents.dam]
    lp = g.limb_plan
    if g.host is None:
        base = f"{FRAME_WORDS[sire.frame].format(name=sire.common_name)} blended with the {dam.common_name}, intermediate in build"
    else:
        host = tax.animals[g.host]
        if host.frame == "quadruped" and lp.forelimbs.kind == "wings":
            base = f"horizontal {host.common_name} frame carried on two hind legs"
        else:
            base = FRAME_WORDS[host.frame].format(name=host.common_name)
    extras: list[str] = []
    if lp.extra_wings:
        extras.append(f"four legs plus a separate pair of {tax.animals[lp.extra_wings.donor].common_name} wings"
                      if lp.extra_wings.donor else "four legs plus a separate pair of wings")
    elif lp.forelimbs.kind == "wings" and g.host and lp.forelimbs.donor and lp.forelimbs.donor != g.host:
        extras.append(f"{tax.animals[lp.forelimbs.donor].common_name} wings in place of the forelegs")
    tail = g.traits.get("tail")
    if tail and tail.part:
        extras.append(f"{tail.part} in place of the tail")
    return base + (", " + ", ".join(extras) if extras else "")
