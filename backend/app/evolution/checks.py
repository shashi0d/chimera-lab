"""Hard cards filter candidates; soft cards add score penalties (RC-R8-10, section 4.8).

`hard_violations` runs on every plan before rendering (RC-R8-03): the seed plan,
each offspring, and each edit. A plan with any violation is never rendered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evolution.data import Taxonomy, cards, config
from app.evolution.genome import BEYOND, HEAD_GROUP, MEASUREMENT_TAGS, SURFACE_TAGS, Genome
from app.evolution.physics import LABEL_ARTHROPOD, LABEL_SIX, arthropod_parts
from app.evolution.route import LABEL_CHIMERA, LABEL_SPECULATIVE, Route, find_known_pair, is_real_hybrid


@dataclass
class Violation:
    card: str
    detail: str

    def public(self) -> dict[str, str]:
        return {"card": self.card, "detail": self.detail}


def _keys(obj: Any) -> list[str]:
    if isinstance(obj, dict):
        return [k for k in obj] + [k2 for v in obj.values() for k2 in _keys(v)]
    if isinstance(obj, list):
        return [k for v in obj for k in _keys(v)]
    return []


def _speculative(labels: list[str]) -> bool:
    return any(lbl in (LABEL_CHIMERA, LABEL_SPECULATIVE) for lbl in labels)


def hard_violations(g: Genome, r: Route, tax: Taxonomy) -> list[Violation]:
    out: list[Violation] = []
    sire, dam = g.parents.sire, g.parents.dam

    # RC-R1-01: no field assigns dominance; neither parent owns the whole creature.
    if any("domin" in k.lower() for k in _keys(g.model_dump())):
        out.append(Violation("RC-R1-01", "a plan field assigns dominance"))
    donors = {d for tr in g.traits.values() for d in tr.donors()}
    for slot in (g.limb_plan.forelimbs, g.limb_plan.hindlimbs, g.limb_plan.extra_wings):
        if slot and slot.donor:
            donors.add(slot.donor)
    if not {sire, dam} <= donors:
        out.append(Violation("RC-R1-01", "every trait comes from one parent"))

    # RC-R2-01: parent order is stored as given, never sorted or swapped.
    if (sire, dam) != r.key:
        out.append(Violation("RC-R2-01", f"parent order changed: {(sire, dam)} != {r.key}"))

    # RC-R1-14, RC-R2-16, RC-R5-10, RC-R2-11: mode comes from routing only; distant pairs are speculative.
    if g.mode != r.mode:
        pair_cards = (r.pair or {}).get("cards", [])
        card = "RC-R2-11" if "RC-R2-11" in pair_cards else ("RC-R2-16" if r.mode == "hybrid" else "RC-R1-14")
        out.append(Violation(card, f"mode {g.mode} differs from routed mode {r.mode}"))
    if r.mode != "hybrid":
        if g.mode == "hybrid":
            out.append(Violation("RC-R2-16", "distant pair on the hybrid path"))
        if not _speculative(g.labels):
            for c in ("RC-R1-14", "RC-R5-10"):
                out.append(Violation(c, "distant pair without the speculative label"))

    # RC-R2-03: donkey sire x horse dam matches the mule override field by field.
    pair = find_known_pair(tax.animals[sire], tax.animals[dam])
    if pair and pair.get("locked"):
        for tag, spec in pair["traits"].items():
            want = {k: v for k, v in spec.items() if v is not None}  # same as exclude_none below
            have = g.traits[tag].model_dump(exclude_none=True, exclude_defaults=True)
            if have != want:
                out.append(Violation(pair["cards"][0], f"{tag}: {have} != override {want}"))
        rule = pair.get("size", {})
        if rule.get("rule") == "pick":
            want_mass = tax.animals[rule["donor"]].mass_kg
            if want_mass and abs((g.size.mass_kg or 0) - want_mass) > 0.5:
                out.append(Violation(pair["cards"][0], f"size {g.size.mass_kg} kg != {want_mass} kg"))

    # RC-R3-01, RC-R3-02: a vertebrate host with wings keeps no forelegs unless mythic with the label.
    host = tax.animals[g.host] if g.host else tax.animals[sire]
    lp = g.limb_plan
    if host.group == "vertebrate" and lp.has_wings():
        six = lp.extra_wings is not None or (lp.forelimbs.kind == "legs" and lp.hindlimbs.kind == "legs" and lp.has_wings())
        if six and not (g.mode == "mythic" and LABEL_SIX in g.labels):
            out.append(Violation("RC-R3-02", "four legs plus wings outside mythic mode or without the label"))
            out.append(Violation("RC-R3-01", "wings must take the forelimb slot"))

    # RC-R3-09: arthropod parts at large size force the speculative label with the reason.
    if arthropod_parts(g, tax) and (g.size.mass_kg or 0) > config()["thresholds"]["arthropod_large_kg"]:
        if LABEL_ARTHROPOD not in g.labels:
            out.append(Violation("RC-R3-09", "arthropod parts at large size without the labeled reason"))

    # RC-R5-01: chimera regions are one parent's tissue: no BLEND inside a PATCH region.
    if g.mode in ("chimera", "mythic"):
        patch_regions = {reg for tr in g.traits.values() if tr.op == "PATCH" for reg in tr.region or []}
        for tag, tr in g.traits.items():
            if tr.op != "BLEND":
                continue
            if tag in SURFACE_TAGS:
                out.append(Violation("RC-R5-01", f"{tag} is blended on the chimera path"))
            elif set(tr.region or []) & patch_regions:
                out.append(Violation("RC-R5-01", f"{tag} blends inside a patch region"))
    return out


def soft_penalties(g: Genome, r: Route, tax: Taxonomy) -> tuple[list[dict[str, Any]], float]:
    """Each violated soft card subtracts weight x severity (section 4.8). Returns (items, normalized)."""
    book = cards()
    hits: list[tuple[str, float, str]] = []
    t = g.traits
    if g.mode == "hybrid":
        main = lambda tr: tr.donor if isinstance(tr.donor, str) else None  # noqa: E731
        pkg = {main(t["face"]), main(t["coat_pattern"])} - {None}
        if len(pkg) > 1:
            hits.append(("RC-R1-11", 0.5, "face and pigment pattern from different parents"))
        heads = {main(t[x]) for x in HEAD_GROUP if t[x].op == "PICK"} - {None}
        if len(heads) > 1:
            hits.append(("RC-R2-06", 0.5, "head group split between parents"))
        for tag, tr in t.items():
            body_owner = g.host
            if tr.op == "OVERLAY" and tr.donor != body_owner and (tr.strength or 0) > 0.6:
                hits.append(("RC-R2-07", 0.5, f"{tag} pattern too strong for a non-body donor"))
        if r.pair and "RC-R2-08" in r.pair.get("cards", []):  # the pair's own card, from data (E4: no names in code)
            if (t["mane"].strength or (1.0 if t["mane"].donor else 0.0)) >= 0.7 and (t["coat_pattern"].strength or 0) >= 0.7:
                hits.append(("RC-R2-08", 1.0, "full mane plus full stripes"))
    beyond = sum(BEYOND in tr.flags for tag, tr in t.items() if tag in MEASUREMENT_TAGS)
    if beyond > len(MEASUREMENT_TAGS) * config()["thresholds"]["beyond_share_max"]:
        hits.append(("RC-R2-02", 1.0, f"{beyond} measurements beyond both parents"))
    if BEYOND in g.size.flags and not (r.pair and (r.pair.get("size") or {}).get("rule") == "beyond"):
        hits.append(("RC-R2-05", 1.0, "size beyond both parents without a documented case"))
    for tag, tr in t.items():
        if tr.op == "PATCH":
            if len(tr.region or []) > config()["thresholds"]["max_patches"]:
                hits.append(("RC-R1-10", 0.5, f"{tag}: too many patches"))
            if tr.strength is not None and tr.strength < 1.0:
                hits.append(("RC-R5-04", 0.5, f"{tag}: donor patch below full strength"))
    if g.mode == "chimera" and g.host and t["head"].donor not in (g.host, None):
        hits.append(("RC-R7-02", 0.7, "myth-style head swap outside mythic mode"))
    if not g.habitat.visible_trait and not is_real_hybrid(r):  # E2c: real hybrids get no habitat cue
        hits.append(("RC-R4-11", 1.0, "no visible habitat trait"))
    if g.host and tax.animals[g.host].group == "soft_bodied" and tax.animals[g.other(g.host)].structure_rank > 0:
        hits.append(("RC-R6-09", 1.0, "soft-bodied host for a structured partner"))
    if g.mode == "chimera" and abs(g.identity_balance - 0.5) < 0.01:
        hits.append(("RC-R5-03", 0.3, "an even 50:50 chimera"))
    items = [{"card": c, "weight": book[c].weight, "severity": s, "penalty": round(book[c].weight * s, 3), "detail": d}
             for c, s, d in hits]
    total = sum(i["penalty"] for i in items)
    return items, round(min(1.0, total / 3.0), 3)
