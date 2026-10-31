"""Section 4.3: assign an operator per trait (R1), then GATE.

Hybrid path: measurements BLEND near the midpoint with modest spread, present-or-
absent features PICK, base color BLEND, pattern OVERLAY at reduced strength,
region donors in coherent groups. Chimera path: host values for measurements,
donor PATCHes at full strength in a few large regions that follow the host body.
"""

from __future__ import annotations

import math
import random
from typing import Any

from app.evolution.data import Animal, Taxonomy, config
from app.evolution.genome import (
    BEYOND,
    MEASUREMENT_TAGS,
    SURFACE_TAGS,
    TRAIT_TAGS,
    LimbPlan,
    LimbSlot,
    Size,
    Trait,
)
from app.evolution.route import Route

BODY_AREA = ("head", "neck", "forequarters", "back", "flanks", "belly", "hindquarters", "legs", "tail")


def baseline_limbs(a: Animal) -> LimbPlan:
    frame = a.frame
    slots = {
        "quadruped": ("legs", "legs"), "winged": ("wings", "legs"), "biped": ("arms", "legs"),
        "finned": ("fins", "fins"), "serpentine": ("none", "none"), "arthropod": ("legs", "legs"),
        "soft_bodied": ("tentacles", "none"), "other": ("legs", "legs"),
    }[frame]
    lp = LimbPlan(forelimbs=LimbSlot(kind=slots[0], donor=a.id), hindlimbs=LimbSlot(kind=slots[1], donor=a.id))
    if lp.forelimbs.kind == "wings":
        lp.wing_use = "powered"
    if slots[1] == "none":
        lp.hindlimbs.donor = None
    if slots[0] == "none":
        lp.forelimbs.donor = None
    return lp


def size_for(r: Route, host: str | None, tax: Taxonomy) -> tuple[Size, list[str]]:
    a, b = r.sire, r.dam
    ma, mb = a.mass_kg, b.mass_kg
    cards: list[str] = []
    flags: list[str] = []
    if r.mode != "hybrid":
        h = tax.animals[host] if host else a
        return Size(mass_kg=h.mass_kg, flags=[] if h.mass_kg else [f"mass unknown for {h.common_name}"]), ["RC-R5-02"]
    rule = (r.pair or {}).get("size") or {"rule": "geomean"}
    if ma is None or mb is None:
        known = ma if ma is not None else mb
        missing = b if ma is not None else a
        return Size(mass_kg=known, flags=[f"mass unknown for {missing.common_name}"]), cards
    if rule["rule"] == "pick":
        mass = tax.animals[rule["donor"]].mass_kg
    elif rule["rule"] == "blend":
        v = rule["value"]
        mass = math.exp(math.log(ma) * (1 - v) + math.log(mb) * v)
    elif rule["rule"] == "beyond":
        mass = max(ma, mb) * rule["factor"]
        flags.append(BEYOND)
        cards.append(rule.get("card", "RC-R2-05"))
    else:
        mass = math.sqrt(ma * mb)
        cards.append("RC-R1-03")
    return Size(mass_kg=round(mass, 1), flags=flags), cards


def _donor_kind(a: Animal) -> str:
    if a.winged:
        return "winged"
    if a.group in ("soft_bodied", "arthropod"):
        return a.group
    return "default"


def _hybrid_traits(r: Route, rng: random.Random) -> tuple[dict[str, Trait], list[str]]:
    a, b = r.sire.id, r.dam.id
    spread = config()["thresholds"]["hybrid_spread"]
    near_mid = lambda: round(0.5 + rng.uniform(-spread, spread), 2)  # noqa: E731
    head_donor = rng.choice([a, b])  # coherent head group (RC-R2-06) and package (RC-R1-11)
    fixed_head = ((r.pair or {}).get("traits") or {}).get("head") or {}
    if fixed_head.get("op") == "PICK" and isinstance(fixed_head.get("donor"), str):
        head_donor = fixed_head["donor"]  # the override's head donor leads the whole head group
    limb_donor = rng.choice([a, b])
    lean = lambda d: round(0.35 if d == a else 0.65, 2)  # noqa: E731  same direction as the group donor
    t: dict[str, Trait] = {
        "size": Trait(op="BLEND", donor=[a, b], value=0.5, note="geometric mean of parent masses"),
        "body": Trait(op="BLEND", donor=[a, b], value=near_mid()),
        "head": Trait(op="PICK", donor=head_donor),
        "face": Trait(op="PICK", donor=head_donor),
        "ears": Trait(op="BLEND", donor=[a, b], value=lean(head_donor)),
        "skull": Trait(op="BLEND", donor=[a, b], value=lean(head_donor)),
        "mane": Trait(op="PICK", donor=head_donor, note="present only if that parent has one"),
        "tail": Trait(op="BLEND", donor=[a, b], value=near_mid()),
        "limbs": Trait(op="BLEND", donor=[a, b], value=lean(limb_donor)),
        "feet": Trait(op="PICK", donor=limb_donor),
        "coat_color": Trait(op="BLEND", donor=[a, b], value=near_mid()),
        "coat_pattern": Trait(op="OVERLAY", donor=head_donor, strength=0.4, region=["flanks", "legs"],
                              note="reduced: the pattern donor does not own the body"),
        "coat_texture": Trait(op="PICK", donor=rng.choice([a, b])),
        "behavior": Trait(op="PICK", donor=head_donor, note="behavior may follow one parent"),
    }
    cards = ["RC-R1-01", "RC-R1-02", "RC-R1-04", "RC-R1-05", "RC-R1-06", "RC-R1-11", "RC-R2-02", "RC-R2-06",
             "RC-R2-07", "RC-R2-15"]
    # Extremes (RC-R1-13, RC-R2-02): at most one measurement beyond both parents, flagged. Never size.
    if rng.random() < 0.2:
        tag = rng.choice(["tail", "ears", "limbs"])
        v = rng.choice([-0.1, 1.1])
        past = r.sire.common_name if v < 0 else r.dam.common_name
        t[tag] = Trait(op="BLEND", donor=[a, b], value=v, flags=[BEYOND],
                       note=f"slightly past the {past.lower()}'s proportions, beyond both parents")
        cards.append("RC-R1-13")
    return t, cards


def _chimera_traits(r: Route, host: Animal, donor: Animal, rng: random.Random) -> tuple[dict[str, Trait], list[str], float]:
    lo, hi = config()["thresholds"]["chimera_donor_share"]
    share = round(rng.uniform(lo, hi), 2)  # drawn per run, never a fixed 50:50 (RC-R5-03)
    k = max(1, min(config()["thresholds"]["max_patches"], round(share * 7)))
    regions = config()["patch_regions"][_donor_kind(donor)][:k]
    h, d = host.id, donor.id
    mythic_swap = r.mode == "mythic" and donor.group == "vertebrate"
    head = d if mythic_swap else h
    t: dict[str, Trait] = {}
    for tag in MEASUREMENT_TAGS:
        t[tag] = Trait(op="PICK", donor=h, note="host value; donor parts scaled to host size")
    t["head"] = Trait(op="PICK", donor=head, note="myth-style head swap" if mythic_swap else None)
    t["face"] = Trait(op="PICK", donor=head)
    t["ears"] = Trait(op="PICK", donor=head)
    t["skull"] = Trait(op="PICK", donor=head)
    t["mane"] = Trait(op="PICK", donor=h, note="present only if the host has one")
    t["limbs"] = Trait(op="PICK", donor=h)
    t["feet"] = Trait(op="PICK", donor=h)
    surface = {"coat_pattern": f"{donor.common_name} pattern", "coat_color": f"{donor.common_name} color",
               "coat_texture": f"{donor.common_name} {donor.covering or 'surface'}"}
    for tag in SURFACE_TAGS:
        t[tag] = Trait(op="PATCH", donor=d, strength=1.0, region=list(regions),
                       note=f"{surface[tag]} in few large patches following the {host.common_name}'s body regions")
    t["behavior"] = Trait(op="PICK", donor=head, note="follows the head donor")
    cards = ["RC-R1-01", "RC-R1-09", "RC-R1-10", "RC-R5-01", "RC-R5-02", "RC-R5-03", "RC-R5-04", "RC-R5-05",
             "RC-R5-06", "RC-R5-07", "RC-R6-02"]
    if mythic_swap:
        cards.append("RC-R7-02")
    sig = config()["signature_parts"].get(donor.frame if donor.frame in ("finned", "serpentine") else donor.group)
    if sig and sig["trait"] in t:
        t[sig["trait"]] = Trait(op="PICK", donor=d, part=sig["part"], note="signature part of the second parent")
        cards.append("RC-R6-05")
    return t, cards, share


def build_traits(r: Route, host_id: str | None, tax: Taxonomy, rng: random.Random) -> dict[str, Any]:
    """Operators for every tag, the starting limb plan and size. Returns a dict of plan fields."""
    if r.mode == "hybrid":
        traits, cards = _hybrid_traits(r, rng)
        frame_animal = tax.animals[host_id] if host_id else r.sire
        limbs = baseline_limbs(frame_animal)
        limbs.forelimbs.donor = None  # hybrid limbs are blended, not one donor
        limbs.hindlimbs.donor = None
        share = None
        if r.pair:
            for tag, spec in r.pair.get("traits", {}).items():
                traits[tag] = Trait(**spec)
            cards += r.pair["cards"]
    else:
        host = tax.animals[host_id]  # type: ignore[index]
        donor = r.dam if host.id == r.sire.id else r.sire
        traits, cards, share = _chimera_traits(r, host, donor, rng)
        limbs = baseline_limbs(host)
        if donor.winged and not host.winged:
            limbs.requested_wings = donor.id  # resolved by the limb-budget check (4.5)
        if traits["tail"].part:
            limbs.appendages.append(f"{traits['tail'].part} (tail)")
    size, size_cards = size_for(r, host_id, tax)
    gate_cards = gate(traits, r, host_id, tax)
    assert set(traits) == set(TRAIT_TAGS)
    return {"traits": traits, "limb_plan": limbs, "size": size, "donor_share": share,
            "cards": cards + size_cards + gate_cards}


def gate(traits: dict[str, Trait], r: Route, host_id: str | None, tax: Taxonomy) -> list[str]:
    """GATE runs before the traits it controls (RC-R1-07, RC-R1-08): a mane only where there is
    hair, a fur pattern only on furred regions."""
    cards: list[str] = []
    covering: dict[str, str] = {}
    base = tax.animals[host_id] if host_id else r.sire
    for reg in BODY_AREA:
        covering[reg] = base.covering
    for tag in SURFACE_TAGS:
        tr = traits[tag]
        if tr.op == "PATCH" and tr.donor:
            for reg in tr.region or []:
                covering[reg] = tax.animals[tr.donor].covering  # type: ignore[index]
    mane = traits["mane"]
    if mane.op == "PICK" and mane.donor:
        donor_cov = tax.animals[mane.donor].covering  # type: ignore[index]
        neck = covering.get("neck", base.covering)
        if donor_cov != "fur" or neck != "fur":
            why = "no hair on the neck" if neck != "fur" else f"the {tax.animals[mane.donor].common_name} has no hair"  # type: ignore[index]
            traits["mane"] = Trait(op="PICK", donor=None, note=f"absent: {why}", flags=["gated"])
            cards += ["RC-R1-07", "RC-R1-08"]
    pat = traits["coat_pattern"]
    if pat.op == "OVERLAY" and pat.donor and pat.region:
        furred = [reg for reg in pat.region if covering.get(reg, base.covering) == "fur" or base.covering != "fur"]
        if furred != pat.region and furred:
            traits["coat_pattern"] = pat.model_copy(update={"region": furred, "flags": [*pat.flags, "gated"]})
            cards += ["RC-R1-07", "RC-R1-08"]
    return cards


def contribution(traits: dict[str, Trait], limbs: LimbPlan, ref: str) -> float:
    """Share of the plan that reads as `ref` (identity_balance, section 3)."""
    total, mine = 0.0, 0.0
    for _tag, tr in traits.items():
        if tr.donor is None:
            continue
        w = 1.0
        if tr.op == "BLEND":
            v = min(1.0, max(0.0, tr.value or 0.0))
            mine += w * ((1 - v) if tr.donor[0] == ref else v)  # type: ignore[index]
        elif tr.op == "PICK":
            mine += w * (1.0 if tr.donor == ref else 0.0)
        elif tr.op == "OVERLAY":
            s = tr.strength or 0.0
            mine += w * (s * 0.5 if tr.donor == ref else 1 - s * 0.5)
        elif tr.op == "PATCH":
            area = min(1.0, len(tr.region or []) / len(BODY_AREA))
            mine += w * (area if tr.donor == ref else 1 - area)
        total += w
    for slot in (limbs.forelimbs, limbs.extra_wings):
        if slot and slot.donor:
            total += 1
            mine += 1.0 if slot.donor == ref else 0.0
    return round(mine / total, 3) if total else 0.5
