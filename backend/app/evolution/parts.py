"""S2 (E4c): class part lists (data/class_parts.json, "model-estimated, reviewed").

Every donor part (a trait's signature part, an appendage, a wing request) and every saved trait of a learned
animal must belong to the animal's class. An invalid donor part is replaced by the donor's most recognizable
valid part: the first of the donor's own visible features that names a valid part, else the class's first
listed part. Parts are described to the image model as materials and shapes ("shape"), never by the donor's
name, so the model draws a part and not the whole donor animal.

Classes outside the file (jellyfish, starfish) are not checked; the check says so.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.evolution.data import DATA, Animal

PARTS_PATH = DATA / "class_parts.json"
NOT_COVERED = "class not covered by class_parts.json"
SIGNATURE_SLOTS = ("head", "face", "back", "tail", "wings")  # where a donated signature part can sit


@dataclass(frozen=True)
class PartSpec:
    cls: str
    part: str
    slot: str
    shape: str
    job: str
    aliases: tuple[str, ...]

    def names(self) -> tuple[str, ...]:
        return (self.part, *self.aliases)


@lru_cache
def class_parts() -> dict[str, Any]:
    return json.loads(PARTS_PATH.read_text(encoding="utf-8"))


def class_key(tax_class: str) -> str | None:
    data = class_parts()
    key = data["class_aliases"].get(tax_class, tax_class)
    return key if key in data["classes"] else None


def class_entry(a: Animal | str) -> dict[str, Any] | None:
    key = class_key(a if isinstance(a, str) else a.tax_class)
    return class_parts()["classes"][key] if key else None


def specs(a: Animal | str) -> list[PartSpec]:
    entry = class_entry(a)
    if entry is None:
        return []
    cls = class_key(a if isinstance(a, str) else a.tax_class) or ""
    return [PartSpec(cls, p["part"], p["slot"], p["shape"], p["job"], tuple(p["aliases"])) for p in entry["parts"]]


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase.lower())}\b", text.lower()) is not None


def match(a: Animal | str, text: str) -> PartSpec | None:
    """The class part `text` names (the longest matching name wins), or None."""
    best: tuple[int, PartSpec] | None = None
    for s in specs(a):
        for n in s.names():
            if _has(text, n) and (best is None or len(n) > best[0]):
                best = (len(n), s)
    return best[1] if best else None


def forbidden(a: Animal | str, text: str) -> list[str]:
    """Words in `text` naming a part the class cannot have (outside a valid part's own name)."""
    entry = class_entry(a)
    if entry is None:
        return []
    low = text.lower()
    hit = match(a, text)
    if hit:  # a valid part's own words never count against it ("tail" inside "segmented tail" for a lobster)
        for n in sorted(hit.names(), key=len, reverse=True):
            low = re.sub(rf"\b{re.escape(n.lower())}\b", " ", low)
    return [w for w in entry["never"] if _has(low, w)]


def valid_part(a: Animal, text: str) -> bool:
    """A donor part must name a part of its class and nothing the class cannot have. Uncovered classes pass."""
    if class_entry(a) is None:
        return True
    return match(a, text) is not None and not forbidden(a, text)


def best_part(a: Animal, slots: tuple[str, ...] = SIGNATURE_SLOTS) -> PartSpec | None:
    """The donor's most recognizable valid part: its own visible features first, then the class order."""
    for feature in a.features:
        s = match(a, feature)
        if s and s.slot in slots and not forbidden(a, feature):
            return s
    return next((s for s in specs(a) if s.slot in slots), None)


def surface(a: Animal) -> str:
    """The donor's covering as a material ("hard, glossy chitin plates with fine seams")."""
    data = class_parts()
    entry = class_entry(a) or {}
    cov = a.covering or "skin"
    return (entry.get("surfaces") or {}).get(cov) or data["surfaces"].get(cov) or cov


def wing_spec(a: Animal) -> PartSpec | None:
    return next((s for s in specs(a) if s.slot == "wings"), None)


def flies_with_wings(a: Animal) -> bool:
    """A donor that brings wings: a winged body plan (birds, bats), or a flying animal whose class has wings
    (an insect that flies)."""
    return a.winged or ("fly" in a.movement and wing_spec(a) is not None)


def job(text: str, a: Animal | None) -> str | None:
    s = match(a, text) if a is not None else None
    return s.job if s else None


# ------------------------------------------------------------------ saved traits


def check_traits(cls: str, traits: dict[str, Any]) -> list[dict[str, Any]]:
    """Corrections a learned animal's saved traits need to fit its class: [{field, was, now, reason}]."""
    entry = class_entry(cls)
    if entry is None:
        return []
    out: list[dict[str, Any]] = []
    plans = list(traits.get("body_plan") or [])
    keep = [p for p in plans if p in entry["body_plans"]]
    if keep != plans or not keep:
        out.append({"field": "body_plan", "was": plans, "now": keep or entry["body_plans"][:1],
                    "reason": f"{cls} body plans are {', '.join(entry['body_plans'])} (class_parts.json)"})
    for f, allowed in (("covering", "coverings"), ("mouthparts", "mouthparts"), ("breathing", "breathing")):
        v = traits.get(f)
        if v and v not in entry[allowed]:
            out.append({"field": f, "was": v, "now": entry[allowed][0],
                        "reason": f"{v!r} is not a {cls} {f.rstrip('s') if f != 'mouthparts' else f} "
                                  f"(allowed: {', '.join(entry[allowed])})"})
    feats = list(traits.get("visible_features") or [])
    bad = [f for f in feats if forbidden(cls, f)]
    if bad:
        out.append({"field": "visible_features", "was": feats, "now": [f for f in feats if f not in bad],
                    "reason": f"names a part a {cls} cannot have: " + "; ".join(
                        f"{f!r} ({', '.join(forbidden(cls, f))})" for f in bad)})
    return out


def apply_corrections(traits: dict[str, Any], fixes: list[dict[str, Any]]) -> dict[str, Any]:
    out = dict(traits)
    for f in fixes:
        out[f["field"]] = f["now"]
    return out


# ------------------------------------------------------------------ donor parts in a plan

DORSAL = "on a dorsal mount"


def _an(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def part_owner(g: Any, tax: Any, text: str) -> Animal | None:
    """The parent an appendage text belongs to: it starts with that parent's common name (or, as a model plan may
    write it, its id: "european_rhinoceros_beetle head horn"; S3b validation finding)."""
    low = text.lower()
    for pid in (g.parents.sire, g.parents.dam):
        if low.startswith(tax.animals[pid].common_name.lower() + " ") or low.startswith(pid.lower() + " "):
            return tax.animals[pid]
    return None


def normalize_appendages(g: Any, tax: Any) -> None:
    """Rewrite an id-prefixed appendage to the parent's common name, so every reader sees one spelling."""
    out = []
    for a in g.limb_plan.appendages:
        for pid in (g.parents.sire, g.parents.dam):
            if a.lower().startswith(pid.lower() + " "):
                a = tax.animals[pid].common_name.lower() + a[len(pid):]
                break
        if a not in out:
            out.append(a)
    g.limb_plan.appendages = out


def dorsal_wings(g: Any, tax: Any) -> list[str]:
    """Appendages that are a non-vertebrate donor's wings on a vertebrate body (a body-plan license)."""
    out = []
    for a in g.limb_plan.appendages:
        owner = part_owner(g, tax, a)
        s = match(owner, a) if owner else None
        if owner and owner.group != "vertebrate" and s and s.slot == "wings":
            out.append(a)
    return out


def dorsal_part(a: Animal) -> str:
    s = wing_spec(a)
    return f"{a.common_name.lower()} {s.part if s else 'wings'} {DORSAL}"


def fix_parts(g: Any, tax: Any) -> list[Any]:
    """S2 (E4c): every donor part must belong to its donor's class. An invalid part is replaced by the donor's
    most recognizable valid part (a tail-slot part stays in the tail trait; any other part becomes an
    appendage), or removed when the class has none. Returns Check records; mutates g."""
    from app.evolution.genome import Check, LimbSlot

    checks: list[Any] = []
    host = g.host or g.parents.sire

    def replace(owner: Animal, bad: str) -> tuple[str | None, str]:
        spec = best_part(owner)
        if spec is None:
            return None, f"{bad!r} is not {_an(owner.tax_class)} {owner.tax_class} part and the class lists no replacement: removed"
        return spec.part, (f"{bad!r} is not {_an(owner.tax_class)} {owner.tax_class} part; replaced by the {owner.common_name}'s "
                           f"{spec.part} (class_parts.json)")

    for tag, tr in list(g.traits.items()):
        if not (tr.part and isinstance(tr.donor, str) and tr.donor != host):
            continue
        owner = tax.animals[tr.donor]
        if valid_part(owner, tr.part):
            continue
        bad = tr.part
        g.limb_plan.appendages = [x for x in g.limb_plan.appendages if x != f"{bad} ({tag})"]
        new, why = replace(owner, bad)
        spec = match(owner, new) if new else None
        if spec and spec.slot == tag:
            g.traits[tag] = tr.model_copy(update={"part": new})
            g.limb_plan.appendages.append(f"{new} ({tag})")
        else:
            g.traits[tag] = tr.model_copy(update={"donor": host, "part": None, "op": "PICK", "region": None,
                                                  "strength": None, "value": None,
                                                  "note": f"host {tag}: the donor part did not fit its class"})
            if new:
                g.limb_plan.appendages.append(f"{owner.common_name.lower()} {new}")
        checks.append(Check(step="class_parts", result="repaired", cards=["RC-R6-05"], detail=why))

    for text in list(g.limb_plan.appendages):
        if text.endswith(")"):
            continue  # "<part> (tail)" mirrors a trait part, checked above
        owner = part_owner(g, tax, text)
        if owner is None or valid_part(owner, text):
            continue
        g.limb_plan.appendages.remove(text)
        new, why = replace(owner, text[len(owner.common_name) + 1:])
        if new and f"{owner.common_name.lower()} {new}" not in g.limb_plan.appendages:
            g.limb_plan.appendages.append(f"{owner.common_name.lower()} {new}")
        checks.append(Check(step="class_parts", result="repaired", cards=["RC-R6-05"], detail=why))

    lp = g.limb_plan
    for name in ("forelimbs", "hindlimbs", "extra_wings"):
        slot = getattr(lp, name)
        if not slot or not slot.donor or slot.donor == host or slot.kind in ("legs", "arms", "none"):
            continue
        owner = tax.animals[slot.donor]
        m = match(owner, slot.kind)
        if class_entry(owner) is None or (m is not None and m.slot in ("limbs", "wings")):
            continue
        base = tax.animals[host]
        if name == "extra_wings":
            lp.extra_wings = None
        else:
            setattr(lp, name, LimbSlot(kind="legs" if base.frame != "finned" else "fins", donor=host))
        checks.append(Check(step="class_parts", result="repaired", cards=["RC-R6-05"],
                            detail=f"{slot.kind} are not a {owner.tax_class} limb; the {name} go back to the host"))
    return checks
