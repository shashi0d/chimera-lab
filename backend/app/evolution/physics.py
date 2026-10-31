"""Section 4.5: physical checks (R3) in a fixed order.

1 body-plan class, 2 limb budget, 3 size ceilings, 4 flight anatomy, 5 posture,
6 part rendering. A failed check repairs the plan or adds a visible label; it
never passes silently (RC-R3-12). Every check writes a Check record.
"""

from __future__ import annotations

from app.evolution.data import Taxonomy, config
from app.evolution.genome import Check, Genome, LimbSlot

LABEL_SIX = "six limbs: mythic design, not a plausible animal"
LABEL_BORDERLINE = "borderline flight: size near the soaring limit"
LABEL_NONFLYING = "non-flying wings: display or gliding only"
LABEL_ARTHROPOD = "speculative: arthropod parts at large size (insect breathing limits size)"
LABEL_TENTACLE_LEGS = "speculative: tentacles as weight-bearing legs on a heavy land animal"
CHECK_LABELS = (LABEL_SIX, LABEL_BORDERLINE, LABEL_NONFLYING, LABEL_ARTHROPOD, LABEL_TENTACLE_LEGS)
ORDER = ("body_plan_class", "limb_budget", "size_ceiling", "flight_anatomy", "posture", "part_rendering")


def _note(g: Genome, tag: str, text: str, locked: frozenset[str] = frozenset()) -> bool:
    """Add a rendering note to a trait. Fields fixed by a hard known-pair override are left alone."""
    if tag in locked:
        return False
    tr = g.traits[tag]
    if not tr.note:
        tr.note = text
    elif text not in tr.note:
        tr.note = f"{tr.note}; {text}"
    return True


def _label(g: Genome, label: str) -> None:
    if label not in g.labels:
        g.labels.append(label)


def arthropod_parts(g: Genome, tax: Taxonomy) -> bool:
    ids = {d for tr in g.traits.values() for d in tr.donors()}
    for slot in (g.limb_plan.forelimbs, g.limb_plan.hindlimbs, g.limb_plan.extra_wings):
        if slot and slot.donor:
            ids.add(slot.donor)
    return any(tax.animals[i].group == "arthropod" for i in ids)


def locked_tags(g: Genome, tax: Taxonomy) -> frozenset[str]:
    from app.evolution.route import find_known_pair

    pair = find_known_pair(tax.animals[g.parents.sire], tax.animals[g.parents.dam])
    return frozenset(pair["traits"]) if pair and pair.get("locked") else frozenset()


def run_checks(g: Genome, tax: Taxonomy) -> list[str]:
    th = config()["thresholds"]
    locked = locked_tags(g, tax)
    g.checks = [c for c in g.checks if c.step not in ORDER]
    g.labels = [label for label in g.labels if label not in CHECK_LABELS]
    cards: list[str] = ["RC-R3-12"]
    lp = g.limb_plan
    host = tax.animals[g.host] if g.host else tax.animals[g.parents.sire]
    mass = g.size.mass_kg

    # 1. Body-plan class of the host.
    g.checks.append(Check(step="body_plan_class", result="pass", detail=f"host class: {host.group} ({host.body_plan})"))

    # 2. Limb budget (RC-R3-01, RC-R3-02).
    if lp.requested_wings:
        donor = lp.requested_wings
        name = tax.animals[donor].common_name
        if host.group == "vertebrate" and g.mode == "mythic":
            lp.extra_wings = LimbSlot(kind="wings", donor=donor)
            _label(g, LABEL_SIX)
            g.checks.append(Check(step="limb_budget", result="labeled", cards=["RC-R3-02", "RC-R7-08"],
                                  detail=f"mythic: four legs plus {name} wings, labeled six-limbed"))
            cards += ["RC-R3-02", "RC-R7-08"]
        else:
            lp.forelimbs = LimbSlot(kind="wings", donor=donor)
            g.checks.append(Check(step="limb_budget", result="repaired", cards=["RC-R3-01"],
                                  detail=f"{name} wings take the forelimb slot"))
            cards.append("RC-R3-01")
        lp.requested_wings = None
    elif lp.extra_wings and not (g.mode == "mythic"):
        lp.forelimbs = lp.extra_wings
        lp.extra_wings = None
        g.checks.append(Check(step="limb_budget", result="repaired", cards=["RC-R3-01", "RC-R3-02"],
                              detail="six limbs outside mythic mode: wings moved to the forelimb slot"))
        cards += ["RC-R3-01", "RC-R3-02"]
    else:
        if lp.extra_wings:
            _label(g, LABEL_SIX)
            cards.append("RC-R3-02")
        g.checks.append(Check(step="limb_budget", result="pass", detail=f"{lp.limb_count()} limbs"))

    # 3. Size ceilings (RC-R3-05, RC-R3-09).
    detail = []
    if lp.has_wings() and mass is not None:
        lo, hi = th["wing_borderline_kg"]
        if mass > th["wing_glide_kg"]:
            lp.wing_use = "gliding_or_display"
            detail.append(f"{mass} kg is above about {th['wing_glide_kg']} kg: wings for display or gliding")
        elif mass >= lo:
            lp.wing_use = "borderline"
        else:
            lp.wing_use = "powered"
        if lo <= mass <= hi:
            _label(g, LABEL_BORDERLINE)
            detail.append(f"{mass} kg is in the {lo} to {hi} kg borderline band")
        cards.append("RC-R3-05")
    elif not lp.has_wings():
        lp.wing_use = "none"
    if arthropod_parts(g, tax) and (mass or 0) > th["arthropod_large_kg"]:
        _label(g, LABEL_ARTHROPOD)
        detail.append(f"arthropod parts at {mass} kg")
        cards.append("RC-R3-09")
    g.checks.append(Check(step="size_ceiling", result="labeled" if detail else "pass",
                          detail="; ".join(detail) or "within ceilings", cards=[c for c in ("RC-R3-05", "RC-R3-09") if c in cards]))

    # 4. Flight anatomy (RC-R3-03, RC-R3-04).
    if lp.has_wings():
        if lp.wing_use in ("powered", "borderline"):
            _note(g, "body", "deep keel and heavy flight chest", locked)
            g.checks.append(Check(step="flight_anatomy", result="repaired", cards=["RC-R3-03"],
                                  detail="flyer gets a deep keel and heavy chest"))
        else:
            _label(g, LABEL_NONFLYING)
            g.checks.append(Check(step="flight_anatomy", result="labeled", cards=["RC-R3-03", "RC-R3-04"],
                                  detail="too heavy for its flight muscles: wings labeled non-flying"))
        cards += ["RC-R3-03", "RC-R3-04"]
    else:
        g.checks.append(Check(step="flight_anatomy", result="pass", detail="no wings"))

    # 5. Posture (RC-R3-06 to RC-R3-08).
    limbs = g.traits["limbs"]
    leg_id = limbs.donor if isinstance(limbs.donor, str) else (g.host or g.parents.sire)
    leg = tax.animals[leg_id]
    if "limbs" in locked:
        g.checks.append(Check(step="posture", result="pass", cards=["RC-R2-03"],
                              detail="limbs fixed by a documented known-pair override; posture left as documented"))
    elif mass and leg.mass_kg and mass > leg.mass_kg * th["posture_scale"]:
        if leg.family == "Felidae":
            _note(g, "limbs", "crouched cat stance kept, with heavier leg muscles")
            cards.append("RC-R3-08")
        else:
            _note(g, "limbs", "legs straightened toward an upright posture")
            cards.append("RC-R3-06")
        if mass > th["thick_bones_kg"]:
            _note(g, "limbs", "thicker limb bones")
            cards.append("RC-R3-07")
        g.checks.append(Check(step="posture", result="repaired", cards=[c for c in ("RC-R3-06", "RC-R3-07", "RC-R3-08") if c in cards],
                              detail=f"{mass} kg on legs from a {leg.mass_kg} kg {leg.common_name}"))
    else:
        g.checks.append(Check(step="posture", result="pass", detail="legs match the body size"))

    # 6. Part rendering (RC-R3-10, RC-R3-11).
    soft_parts = [t for t, tr in g.traits.items() if tr.part and ("tentacle" in tr.part or "trunk" in tr.part)]
    for tag in soft_parts:
        _note(g, tag, "jointless and smoothly curving; longer means thinner", locked)
    tentacle_legs = "tentacles" in (lp.forelimbs.kind, lp.hindlimbs.kind) and host.group != "soft_bodied"
    if tentacle_legs and (mass or 0) > th["heavy_land_kg"]:
        _label(g, LABEL_TENTACLE_LEGS)
        cards.append("RC-R3-11")
    if soft_parts or tentacle_legs:
        cards.append("RC-R3-10")
        g.checks.append(Check(step="part_rendering", result="repaired" if not tentacle_legs else "labeled",
                              cards=["RC-R3-10"] + (["RC-R3-11"] if tentacle_legs else []),
                              detail=f"jointless soft parts: {', '.join(soft_parts) or 'legs'}"))
    else:
        g.checks.append(Check(step="part_rendering", result="pass", detail="no soft parts"))
    return cards
