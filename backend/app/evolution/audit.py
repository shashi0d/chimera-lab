"""Section 4.5b: the function audit (R9 section 2). Runs after the physical checks, before the render.

Functions: breathing, feeding, support, movement, heat, senses (no reproduction: fertility cannot be seen,
and a mule is a real, generally sterile animal). Each ends as pass, repaired, labeled or licensed, with the
cards used. Where an R3, R4, R6 or R9 card covers the case, code decides and cites the card; otherwise the
function is `pending` and Muse Spark judges every uncovered function in one call before the render
("model-judged"). A failed function never passes silently (RC-R9-02, RC-R3-12).

Problems that R9 3.2 lists as bendable become `Need`s. The fiction budget (fiction.py) decides for each one:
license it (with its compensation), repair it, or label it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evolution.data import Animal, Taxonomy, config
from app.evolution.genome import FUNCTIONS, AuditItem, Genome
from app.evolution.habitat import profile
from app.evolution.physics import (
    LABEL_ARTHROPOD,
    LABEL_NONFLYING,
    LABEL_SIX,
    LABEL_TENTACLE_LEGS,
    arthropod_parts,
    locked_tags,
)
from app.evolution.route import Route, is_real_hybrid

TEETH = ("grinding teeth", "bladed teeth", "mixed teeth", "pointed teeth")
TEETH_FIT = {"grinding teeth": ("herbivore", "omnivore"), "bladed teeth": ("carnivore", "omnivore", "piscivore"),
             "mixed teeth": ("omnivore", "carnivore", "herbivore", "insectivore"),
             "pointed teeth": ("carnivore", "insectivore", "piscivore", "omnivore")}
KNOWN_BREATHING = ("lungs", "gills", "external gills and lungs", "skin and lungs", "tracheae", "book lungs")
FUNCTION_TRAIT = {"breathing": "body", "feeding": "head", "support": "limbs", "movement": "limbs",
                  "heat": "coat_texture", "senses": "head"}
OXYGEN_NOTE = "the oxygen explanation for giant insects is debated, not settled (RC-R9-09)"


@dataclass
class Need:
    """A bendable rule (evo_config `bendable`) this plan needs to bend. fiction.py settles it."""
    id: str
    function: str
    detail: str


def _note(g: Genome, tag: str, text: str, locked: frozenset[str]) -> bool:
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


def body_animals(g: Genome, tax: Taxonomy) -> list[Animal]:
    """Whose body (and so whose breathing system) the creature has: the host, or both parents in a hybrid."""
    return [tax.animals[g.host]] if g.host else [tax.animals[g.parents.sire], tax.animals[g.parents.dam]]


def head_animal(g: Genome, tax: Taxonomy) -> Animal:
    d = g.traits["head"].donor
    if isinstance(d, list):
        d = d[0]
    return tax.animals[d or g.host or g.parents.sire]


def is_wet(g: Genome) -> bool:
    p = profile(g.habitat.name)
    return bool(p.get("wet") or p.get("water"))


def _a(word: str) -> str:
    return "an" if word[:1] in "aeiou" else "a"


def _check(g: Genome, step: str):  # noqa: ANN202
    return next((c for c in g.checks if c.step == step), None)


def part_job(part: str, wet: bool) -> str | None:
    """The job of a donated part (RC-R9-12), or None when it has none here."""
    for key, spec in config()["part_jobs"].items():
        if key in part:
            if spec.get("needs") == "water" and not wet:
                return None
            return spec["job"]
    return None


DROPPED = "dropped part: "


def part_key(part: str) -> str:
    """The part_jobs key a part matches ("axolotl external gills on ..." -> "external gills"), else the part."""
    return next((k for k in config()["part_jobs"] if k in part), part)


def dropped_parts(g: Genome) -> list[str]:
    """Parts realistic mode dropped (E4 live fix): kept as body flags so the prompt and checklist know."""
    return [f[len(DROPPED):] for f in g.traits["body"].flags if f.startswith(DROPPED)]


def _drop(g: Genome, part: str, locked: frozenset[str]) -> None:
    """Record a dropped part and strip model-note clauses that would bring it back into the prompt."""
    key = part_key(part)
    stem = key.split()[-1].rstrip("s")
    body = g.traits["body"]
    if f"{DROPPED}{key}" not in body.flags:
        g.traits["body"] = body.model_copy(update={"flags": [*body.flags, f"{DROPPED}{key}"]})
    for tag, tr in g.traits.items():
        if tag in locked or not tr.note or stem not in tr.note.lower():
            continue
        kept = [c for c in tr.note.split(";") if stem not in c.lower()]
        g.traits[tag] = tr.model_copy(update={"note": ";".join(kept).strip() or None})


def donor_parts(g: Genome) -> list[tuple[str, str]]:
    """(where, part) for every signature part a non-host donor adds."""
    out: list[tuple[str, str]] = []
    for tag, tr in g.traits.items():
        if tr.part and tr.donor and tr.donor != g.host:
            out.append((f"traits.{tag}", tr.part))
    for i, a in enumerate(g.limb_plan.appendages):
        if not any(a.startswith(p) for _w, p in out):  # "jointed tail segments (tail)" repeats the tail part
            out.append((f"appendages.{i}", a))
    return out


# ------------------------------------------------------------------ the six functions


def _breathing(g: Genome, tax: Taxonomy, locked: frozenset[str], needs: list[Need]) -> AuditItem:
    body = body_animals(g, tax)
    organs = [a.breathing for a in body]
    wet = is_wet(g)
    if any(o not in KNOWN_BREATHING for o in organs):
        return AuditItem(function="breathing", result="pending", source="model-judged",
                         detail=f"breathing organ not covered by a card ({', '.join(o or 'unknown' for o in organs)})")
    land = not wet or g.limb_plan.wing_use == "powered"
    names = " and ".join(a.common_name for a in body)
    if all(o == "gills" for o in organs) and land:
        needs.append(Need("land_gills", "breathing", f"the {names} body breathes only with gills, on land"))
        return AuditItem(function="breathing", result="labeled", cards=["RC-R9-03"],
                         detail=f"gills alone cannot serve a land creature; the {names} body breathes with gills")
    gill_parts = [(w, p) for w, p in donor_parts(g) if "gill" in p]
    if gill_parts and land:
        if g.design_mode == "realistic":  # RC-R9-12: no job in air, so dropped
            for where, part in sorted(gill_parts, reverse=True):
                if where.startswith("appendages."):
                    g.limb_plan.appendages.pop(int(where.split(".")[1]))
                _drop(g, part, locked)
            return AuditItem(function="breathing", result="repaired", cards=["RC-R9-03", "RC-R9-12"],
                             detail=f"external gills would collapse in air and have no job in a {g.habitat.name} "
                                    f"habitat, so they are dropped; the creature breathes with the {names}'s lungs")
        return AuditItem(function="breathing", result="pass", cards=["RC-R9-03"],
                         detail=f"breathes with the {names}'s {organs[0]}; the donor's external gills are kept as "
                                "display frills and do not serve breathing in air")
    item = AuditItem(function="breathing", result="pass", cards=["RC-R9-03"] if wet else [],
                     detail=f"{' and '.join(sorted(set(organs)))} suit a {'water' if wet else 'land'} habitat")
    # Breathing at size (RC-R9-07): the body scaled well above its own size needs bigger breathing surfaces.
    th = config()["thresholds"]
    mass = g.size.mass_kg or 0
    small = [a for a in body if a.mass_kg and mass > a.mass_kg * th["posture_scale"]]
    if small and "body" not in locked:
        _note(g, "body", "deep chest and large nostrils for the larger body", locked)
        return AuditItem(function="breathing", result="repaired", cards=["RC-R9-07"],
                         detail=f"{mass} kg body built on a {small[0].mass_kg} kg {small[0].common_name} frame: "
                                "deep chest and large nostrils added")
    return item


def _feeding(g: Genome, tax: Taxonomy) -> AuditItem:
    head = head_animal(g, tax)
    mp, diet = head.mouthparts, (head.diet or "").split("|")[0]
    beh = g.traits["behavior"]
    repaired = ""
    if isinstance(beh.donor, str) and beh.donor != head.id and "behavior" not in locked_tags(g, tax):
        other = tax.animals[beh.donor]
        if (other.diet or "").split("|")[0] != diet:
            g.traits["behavior"] = beh.model_copy(update={"donor": head.id, "note": "follows the head donor's diet"})
            repaired = f"behavior moved from the {other.common_name} to the {head.common_name}, whose mouth does the eating"
    if mp == "beak":
        return AuditItem(function="feeding", result="repaired" if repaired else "pass", cards=["RC-R9-04", "RC-R9-05"],
                         detail=(repaired + "; " if repaired else "") + f"{head.common_name} beak, {diet or 'diet unknown'}: "
                                "beak shape is never a reason to reject (it explains under 12 percent of diet)")
    if mp in TEETH and diet:
        fits = diet in TEETH_FIT[mp]
        if fits:
            return AuditItem(function="feeding", result="repaired" if repaired else "pass", cards=["RC-R9-04"],
                             detail=(repaired + "; " if repaired else "") + f"{mp} fit {_a(diet)} {diet} diet")
        return AuditItem(function="feeding", result="labeled", cards=["RC-R9-04"],
                         detail=f"{mp} do not match {_a(diet)} {diet} diet: flagged")
    return AuditItem(function="feeding", result="pending", source="model-judged",
                     detail=f"{head.common_name} mouthparts ({mp or 'unknown'}) are not covered by a card")


def _support(g: Genome, tax: Taxonomy, needs: list[Need]) -> AuditItem:
    th = config()["thresholds"]
    if LABEL_TENTACLE_LEGS in g.labels:
        needs.append(Need("tentacle_legs", "support", "tentacles carry a heavy land body"))
        return AuditItem(function="support", result="labeled", cards=["RC-R3-11"],
                         detail="tentacles as weight-bearing legs on a heavy land animal")
    if arthropod_parts(g, tax):
        host = tax.animals[g.host] if g.host else tax.animals[g.parents.sire]
        length = host.length_m
        if LABEL_ARTHROPOD in g.labels:
            needs.append(Need("arthropod_large", "support", f"arthropod parts at {g.size.mass_kg} kg"))
            return AuditItem(function="support", result="labeled", cards=["RC-R3-09", "RC-R9-08"],
                             detail=f"arthropod parts at {g.size.mass_kg} kg, far above the Meganeura scale "
                                    f"(about 70 cm); {OXYGEN_NOTE}")
        if length is not None and length <= config()["insect_part_free_length_m"]:
            return AuditItem(function="support", result="pass", cards=["RC-R9-08"],
                             detail=f"insect parts on a {length} m body, within the Meganeura scale: no license needed")
    posture = _check(g, "posture")
    if posture and posture.result == "repaired":
        return AuditItem(function="support", result="repaired", cards=[*posture.cards, "RC-R9-06"],
                         detail=f"{posture.detail}: legs changed shape to carry the weight")
    mass = g.size.mass_kg or 0
    return AuditItem(function="support", result="pass", cards=["RC-R9-06"] if mass > th["heavy_land_kg"] else [],
                     detail=posture.detail if posture else "legs match the body size")


def _movement(g: Genome, tax: Taxonomy, locked: frozenset[str], needs: list[Need]) -> AuditItem:
    lp = g.limb_plan
    cards: list[str] = []
    notes: list[str] = []
    result = "pass"
    if lp.extra_wings:
        needs.append(Need("six_limbs", "movement", "four legs plus a separate pair of wings"))
        result, cards = "labeled", ["RC-R3-02"]
        notes.append("four legs plus wings: six limbs")
    fa = _check(g, "flight_anatomy")
    if lp.has_wings() and fa:
        cards += [*fa.cards, "RC-R9-13"]
        notes.append(fa.detail)
        if fa.result == "repaired" and result == "pass":
            result = "repaired"
        elif LABEL_NONFLYING in g.labels and result == "pass":
            result = "labeled"
    # Anatomy matches ability (RC-R9-13): a digging behavior needs digging forelimbs.
    beh = g.traits["behavior"]
    beh_animal = tax.animals[beh.donor] if isinstance(beh.donor, str) else None
    limbs = g.traits["limbs"]
    limb_animal = tax.animals[limbs.donor] if isinstance(limbs.donor, str) else None
    if beh_animal and "burrow" in beh_animal.movement and limb_animal and "burrow" not in limb_animal.movement:
        if _note(g, "limbs", "thick forelimbs and strong shoulders for digging", locked):
            notes.append(f"digs like the {beh_animal.common_name}: thick forelimbs and strong shoulders added")
            cards.append("RC-R9-13")
            result = "repaired" if result == "pass" else result
    # Every donor part has a job (RC-R9-12); gills are judged under breathing.
    wet = is_wet(g)
    for where, part in donor_parts(g):
        if "gill" in part:
            continue
        job = part_job(part, wet)
        if job:
            notes.append(f"{part}: {job}")
            continue
        cards.append("RC-R9-12")
        if g.design_mode == "realistic":
            if where.startswith("traits."):
                tag = where.split(".")[1]
                host = g.host or g.parents.sire
                g.traits[tag] = g.traits[tag].model_copy(update={"donor": host, "part": None,
                                                                 "note": f"host {tag}: the donor part had no job"})
            else:
                g.limb_plan.appendages.remove(part)
            _drop(g, part, locked)
            notes.append(f"{part} had no job here and was dropped")
            result = "repaired" if result == "pass" else result
        else:
            notes.append(f"{part} has no clear job here (kept outside realistic mode, soft penalty)")
    if not notes:
        kinds = (lp.forelimbs.kind, lp.hindlimbs.kind)
        notes.append("walks on four legs" if kinds == ("legs", "legs") else f"moves on its {kinds[0]} and {kinds[1]}")
    return AuditItem(function="movement", result=result, cards=list(dict.fromkeys(cards)), detail="; ".join(notes))


def _heat(g: Genome, r: Route) -> AuditItem:
    if is_real_hybrid(r):
        return AuditItem(function="heat", result="pass", detail="a documented animal: no habitat step (D-056)")
    if g.habitat.name not in config()["habitat_profiles"]:
        return AuditItem(function="heat", result="pending", source="model-judged",
                         detail=f"habitat {g.habitat.name!r} has no profile, so no card covers its heat balance")
    temp = profile(g.habitat.name)["temp"]
    adj = [a for a in g.habitat.adjustments if "ears" in a or "coat" in a or "tail" in a]
    if temp in ("hot", "cold") and adj:
        return AuditItem(function="heat", result="repaired", cards=["RC-R4-03", "RC-R4-04", "RC-R4-11"],
                         detail=f"{temp} habitat: {'; '.join(adj)}")
    return AuditItem(function="heat", result="pass", cards=["RC-R4-11"],
                     detail=f"{temp} {g.habitat.name} habitat: no heat adjustment needed")


def _senses(g: Genome, tax: Taxonomy) -> AuditItem:
    head = head_animal(g, tax)
    return AuditItem(function="senses", result="pass", cards=["RC-R6-03", "RC-R6-04"],
                     detail=f"{head.common_name} head and eyes kept fully visible")


def run_audit(g: Genome, tax: Taxonomy, r: Route) -> tuple[list[str], list[Need]]:
    """Fill g.audit (code part) and return (cards, needs for the fiction budget). Idempotent on a finished plan."""
    locked = locked_tags(g, tax)
    needs: list[Need] = []
    items = [_breathing(g, tax, locked, needs), _feeding(g, tax), _support(g, tax, needs),
             _movement(g, tax, locked, needs), _heat(g, r), _senses(g, tax)]
    g.audit = items
    assert [i.function for i in items] == list(FUNCTIONS)
    cards = ["RC-R9-02"] + [c for i in items for c in i.cards]
    return list(dict.fromkeys(cards)), needs


def uncovered(g: Genome) -> list[str]:
    return [i.function for i in g.audit if i.result == "pending"]


def plan_text(g: Genome, tax: Taxonomy) -> str:
    """The plan in plain words for the one model judgment (no ids, no JSON)."""
    sire, dam = tax.animals[g.parents.sire], tax.animals[g.parents.dam]
    head = head_animal(g, tax)
    body = body_animals(g, tax)
    bits = [f"Parents: {sire.common_name} and {dam.common_name}.", f"Silhouette: {g.silhouette}.",
            f"Body from: {' and '.join(a.common_name for a in body)}; about {g.size.mass_kg} kg.",
            f"Head from: {head.common_name} (mouthparts: {head.mouthparts or 'unknown'}; diet: {head.diet or 'unknown'}).",
            f"Breathing organs of the body: {', '.join(a.breathing or 'unknown' for a in body)}.",
            f"Habitat: {g.habitat.name}.",
            f"Limbs: {g.limb_plan.forelimbs.kind} and {g.limb_plan.hindlimbs.kind}"
            + (f", plus {', '.join(g.limb_plan.appendages)}" if g.limb_plan.appendages else "") + "."]
    return " ".join(bits)


def apply_judgment(g: Genome, judged: list[dict[str, str]] | None, error: str | None = None) -> list[str]:
    """Merge the model judgment into the pending audit items. A missing judgment is labeled, never a pass."""
    locked: frozenset[str] = frozenset()
    by_fn = {j["function"]: j for j in judged or []}
    for i, item in enumerate(g.audit):
        if item.result != "pending":
            continue
        j = by_fn.get(item.function)
        if j is None:
            g.audit[i] = item.model_copy(update={"result": "labeled", "detail": f"{item.detail}; model judgment "
                                                 f"unavailable ({error or 'no answer'}), so not shown to work"})
            _label(g, f"unchecked: {item.function} not confirmed")
            continue
        detail = j["detail"]
        if "oxygen" in detail.lower() and "debated" not in detail.lower():
            detail = f"{detail} ({OXYGEN_NOTE})"
        if j["result"] == "repaired" and j.get("repair"):
            _note(g, FUNCTION_TRAIT[item.function], j["repair"], locked)
            detail = f"{detail}; repair: {j['repair']}"
        if j["result"] == "labeled":
            _label(g, f"speculative: {item.function} may not work as planned")
        g.audit[i] = item.model_copy(update={"result": j["result"], "detail": detail})
    return []


def audit_public(g: Genome) -> list[dict[str, Any]]:
    return [i.model_dump() for i in g.audit]


__all__ = ["Need", "run_audit", "uncovered", "plan_text", "apply_judgment", "audit_public", "LABEL_SIX"]
