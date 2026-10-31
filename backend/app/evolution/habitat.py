"""Section 4.4: habitat step (R4).

Picks a habitat (shared, bridging, or the user's) and adjusts plastic traits only.
The step is idempotent: earlier habitat deltas are undone before new ones apply,
so re-running it on an offspring never compounds. It never touches limb count or
body-plan class (RC-R4-10), and always leaves one visible habitat trait (RC-R4-11).
"""

from __future__ import annotations

import random
import re
from typing import Any

from app.evolution.data import Animal, Taxonomy, coat_pattern, config, pattern_phrase
from app.evolution.genome import Genome, Habitat

PATTERN_FLAG = re.compile(r"^habitat pattern ([+-]\d+\.\d+)$")
MASS_FLAG = re.compile(r"^habitat mass x(\d+\.\d+)$")


def profile(name: str) -> dict[str, Any]:
    profiles = config()["habitat_profiles"]
    if name in profiles:
        return profiles[name]
    return {"openness": "open", "temp": "temperate", "sunny": False}


def choose_habitat(sire: Animal, dam: Animal, rng: random.Random, user: str | None = None) -> tuple[Habitat, list[str]]:
    if user:
        return Habitat(name=user, source="user"), ["RC-R4-09"]
    shared = [h for h in sire.habitats if h in dam.habitats]
    if shared:
        return Habitat(name=rng.choice(shared), source="shared"), []
    a, b = set(sire.habitats), set(dam.habitats)
    for rule in config()["bridging"]:
        if "either" in rule and any((h in a) != (h in b) for h in rule["either"]):
            return Habitat(name=rule["name"], source="bridging"), ["RC-R4-09"]
        if "between" in rule:
            x, y = rule["between"]
            if (x in a and y in b) or (x in b and y in a):
                return Habitat(name=rule["name"], source="bridging"), ["RC-R4-09"]
    first_a = sire.habitats[0] if sire.habitats else "open country"
    first_b = dam.habitats[0] if dam.habitats else "open country"
    return Habitat(name=f"edge of {first_a} and {first_b}", source="bridging"), ["RC-R4-09"]


def _undo(g: Genome) -> None:
    for _tag, tr in list(g.traits.items()):
        keep = []
        for f in tr.flags:
            m = PATTERN_FLAG.match(f)
            if m and tr.strength is not None:
                tr.strength = round(tr.strength - float(m.group(1)), 3)
            elif not m:
                keep.append(f)
        tr.flags = keep
    keep = []
    for f in g.size.flags:
        m = MASS_FLAG.match(f)
        if m and g.size.mass_kg:
            g.size.mass_kg = round(g.size.mass_kg / float(m.group(1)), 1)
        elif not m:
            keep.append(f)
    g.size.flags = keep


def clear_habitat(g: Genome) -> list[str]:
    """Real-hybrid route (E2c, D-056): a documented hybrid is a known animal, not an adapted design, so
    no habitat cue applies. Undoes earlier habitat deltas (a model plan may carry some) and clears the cue."""
    _undo(g)
    g.habitat.adjustments = []
    g.habitat.visible_trait = None
    return []


def apply_habitat(g: Genome, tax: Taxonomy, locked: bool = False) -> list[str]:
    _undo(g)
    before = g.limb_plan.model_dump()
    frame_before = (tax.animals[g.host].frame if g.host else None)
    p = profile(g.habitat.name)
    adj: list[str] = []
    cards: list[str] = []
    visible: list[str] = []

    # Pattern strength (RC-R4-01, RC-R4-02), E2b: the step only scales a pattern a parent already has and
    # never adds markings. Open habitats make it plainer, closed ones a little bolder; with no patterned
    # donor nothing changes. PATCHes stay at full strength (RC-R5-04).
    tr = g.traits["coat_pattern"]
    owner = tr.donor if isinstance(tr.donor, str) and coat_pattern(tr.donor) else None
    if owner and tr.op == "OVERLAY" and tr.strength is not None and not (locked and "coat_pattern" in _locked_tags(g)):
        delta = 0.1 if p["openness"] == "closed" else -0.1
        new = min(1.0, max(0.05, round(tr.strength + delta, 3)))
        applied = round(new - tr.strength, 3)
        if applied:
            tr.strength = new
            tr.flags.append(f"habitat pattern {applied:+.2f}")
            phrase = pattern_phrase(tax.animals[owner].common_name, owner)
            adj.append(f"{'bolder' if applied > 0 else 'fainter'} {phrase} for {'a closed' if applied > 0 else 'an open'} habitat")
            visible.append(adj[-1])
    cards += ["RC-R4-01", "RC-R4-02"]

    # Countershading (RC-R4-05).
    strong = p["openness"] == "open" and p.get("sunny")
    adj.append(f"dark back and light belly ({'strong' if strong else 'mild'} countershading)")
    visible.append(adj[-1])
    cards.append("RC-R4-05")

    # Extremities and size (RC-R4-03, RC-R4-04).
    if p["temp"] == "hot":
        adj.append("larger ears and longer tail for shedding heat")
        visible.insert(0, adj[-1])
        cards.append("RC-R4-04")
    elif p["temp"] == "cold":
        adj.append("shorter ears and tail, dense coat for the cold")
        visible.insert(0, adj[-1])
        cards.append("RC-R4-04")
        if g.size.mass_kg and not locked:
            g.size.mass_kg = round(g.size.mass_kg * 1.05, 1)
            g.size.flags.append("habitat mass x1.05")
            cards.append("RC-R4-03")

    # Eyes (RC-R4-07): bird or reptile head, night or dusk activity.
    head_id = g.traits["head"].donor if isinstance(g.traits["head"].donor, str) else (g.host or g.parents.sire)
    head = tax.animals[head_id]
    if head.tax_class in ("Aves", "Reptilia") and {"nocturnal", "crepuscular"} & set(head.active_time):
        adj.append("larger eyes and pupils for dusk and night activity")
        visible.insert(0, adj[-1])
        cards.append("RC-R4-07")

    # Open water (RC-R4-06): streamlining only for a fast open-water lifestyle.
    if p.get("open_water"):
        host_frame = tax.animals[g.host].frame if g.host else None
        if host_frame == "finned":
            adj.append("streamlined torpedo body and crescent tail for fast open water")
        else:
            adj.append("shoreline lifestyle: no streamlining")
        cards.append("RC-R4-06")

    g.habitat.adjustments = adj
    g.habitat.visible_trait = visible[0]  # RC-R4-11
    cards.append("RC-R4-11")
    after = g.limb_plan.model_dump()
    assert before == after, "habitat step changed the limb plan (RC-R4-10)"
    assert frame_before == (tax.animals[g.host].frame if g.host else None)
    cards.append("RC-R4-10")
    return cards


def _locked_tags(g: Genome) -> set[str]:
    from app.evolution.data import taxonomy
    from app.evolution.route import find_known_pair

    tax = taxonomy()
    pair = find_known_pair(tax.animals[g.parents.sire], tax.animals[g.parents.dam])
    return set(pair["traits"]) if pair and pair.get("locked") else set()
