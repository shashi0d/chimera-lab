"""Section 4.1 (route the pair) and 4.2 (host and silhouette)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evolution.data import Animal, Taxonomy, known_pairs
from app.evolution.genome import Genome

LABEL_HYBRID = "real hybrid precedent"
LABEL_CLOSE = "speculative hybrid of close relatives, no documented cross"
LABEL_CHIMERA = "speculative chimera, no real-world precedent"
LABEL_MYTHIC = "mythic composite"  # RC-R9-01 vocabulary (was "mythic design")
LABEL_SPECULATIVE = "speculative design, no real-world precedent"
# RC-R9-01: three kinds, never mixed. The plain word "hybrid" is used on the real-hybrid route only.
KIND = {"hybrid": "hybrid", "chimera": "chimera", "mythic": "mythic composite"}
RANKS = ("species", "genus", "family", "order", "class", "beyond class")


def taxonomy_distance(a: Animal, b: Animal) -> dict[str, Any]:
    """The closest shared rank (E4 routing by taxonomy distance). Unknown taxonomy (GBIF down) is 'unknown'."""
    if not (a.taxonomy_known and b.taxonomy_known):
        return {"shared_rank": "unknown", "steps": None}
    if a.scientific_name and a.scientific_name == b.scientific_name:
        return {"shared_rank": "species", "steps": 0}
    for steps, (rank, x, y) in enumerate([("genus", a.genus, b.genus), ("family", a.family, b.family),
                                          ("order", a.order, b.order), ("class", a.tax_class, b.tax_class)], 1):
        if x and x == y:
            return {"shared_rank": rank, "steps": steps}
    return {"shared_rank": "beyond class", "steps": 5}


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
    distance: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str]:
        """Ordered (sire, dam): never sorted (RC-R2-01)."""
        return (self.sire.id, self.dam.id)

    def public(self) -> dict[str, Any]:
        return {"sire": self.sire.id, "dam": self.dam.id, "mode": self.mode, "reason": self.reason,
                "known_pair": self.pair["id"] if self.pair else None, "labels": self.labels, "cards": self.cards,
                "kind": KIND[self.mode], "distance": self.distance}


def _resolve_roles(obj: Any, sire: str, dam: str) -> Any:
    if isinstance(obj, str):
        return {"sire": sire, "dam": dam}.get(obj, obj)
    if isinstance(obj, list):
        return [_resolve_roles(x, sire, dam) for x in obj]
    if isinstance(obj, dict):
        return {k: (_resolve_roles(v, sire, dam) if k in ("donor", "host") else
                    _resolve_roles(v, sire, dam) if isinstance(v, dict) else v) for k, v in obj.items()}
    return obj


def is_real_hybrid(x: Any) -> bool:
    """E2c: the real-hybrid route is a hybrid-mode Route or Genome labeled as a real hybrid precedent
    (a known pair or a cross documented in chimera_data.json). Close relatives with no documented cross are not."""
    return getattr(x, "mode", None) == "hybrid" and LABEL_HYBRID in (getattr(x, "labels", None) or [])


def hybrid_names(pair: dict[str, Any] | None) -> list[str]:
    """The hybrid's own name and its aliases, lowercase ("mule"; "pizzly", "grolar")."""
    if not pair:
        return []
    return [n.lower() for n in [pair.get("name", ""), *(pair.get("prompt") or {}).get("aliases", [])] if n]


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
    """Known pair or documented cross (data files only), then same genus, then myth, else chimera.
    Works for any pair by taxonomy distance; no animal or pair is named here. A model's claim that two
    animals cross (Animal.claims) is never read: it is an unverified claim, not precedent (E4)."""
    r = _route(sire, dam, tax, myth)
    r.distance = taxonomy_distance(sire, dam)
    return r


def _route(sire: Animal, dam: Animal, tax: Taxonomy, myth: bool) -> Route:
    order = ["RC-R2-01"]
    pair = find_known_pair(sire, dam)
    if pair:
        return Route(sire, dam, "hybrid", f"known pair: {pair['name']}", [LABEL_HYBRID],
                     order + ["RC-R2-16", *pair["cards"]], pair, list(pair.get("processes", [])))
    known = sire.taxonomy_known and dam.taxonomy_known  # GBIF down: no precedent can be checked
    if known and tax.documented_hybrid(sire, dam):
        return Route(sire, dam, "hybrid", "documented hybrid in chimera_data.json", [LABEL_HYBRID],
                     order + ["RC-R2-16"], None, ["in-between blend as in real hybrids"])
    if known and sire.genus and sire.genus == dam.genus:
        return Route(sire, dam, "hybrid", f"same genus ({sire.genus}): hybrid candidate", [LABEL_CLOSE],
                     order + ["RC-R2-16", "RC-R1-14"], None, ["in-between blend as in real hybrids"])
    distant = order + ["RC-R1-14", "RC-R2-16", "RC-R5-10"]
    why = ("taxonomy unknown (GBIF unreachable), treated as distant" if not known
           else "distant pair: no documented hybrid and different genus")
    if myth:
        return Route(sire, dam, "mythic", f"{why}; user asked for myth", [LABEL_MYTHIC, LABEL_SPECULATIVE],
                     distant + ["RC-R7-02", "RC-R9-01"], None, ["myth-style part swap, labeled as myth"])
    return Route(sire, dam, "chimera", why, [LABEL_CHIMERA], distant, None,
                 ["chimera patchwork: each region is one parent's tissue"])


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
