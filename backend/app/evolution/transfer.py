"""S3b part 2: transfer traits, not shapes (RC-R10-15, RC-R10-16).

The S3a review found the engine moving donor *shapes* onto the host: a beetle's shell pasted on a bear, keeping the
beetle's outline, leaving the legs bare, at insect scale, with a horn disconnected from everything else. The fix is
in the plan, not the image: every donor feature gets a transfer record (genome.Transfer).

- Class (a) material or covering: grows on the host and conforms to the host's body. Its extent (body zones) and the
  reason come from the donor's own covering system (data/transfer_rules.json): an exoskeleton covers body and limbs
  with flexible bands at the joints (RC-R10-16); pangolin scales leave the belly and face soft, as on a pangolin.
  Plates are sized to the host and follow its body segments and muscle masses.
- Class (b) homologous structure: a part the host has a matching structure for (same group; a bird's wing is a
  forelimb, Understanding Evolution), placed there and fitted to host scale.
- Class (c) non-homologous structure: never transferred as a shape, only material and function. A beetle's elytra
  are forewings, so on a bear only the cuticle transfers (part of the covering). A beetle's head horn is kept as a
  discrete part only as cuticle grown from the head covering, anchored by function (RC-R10-14).
- Connections: parts and covering from the same donor system connect. A head part makes the covering include the
  head, so the part grows out of head covering that continues into the body covering.
- Identity cues: each discrete part carries a short, positive description of the form that makes it the donor's.

Code derives every transfer in `finish()`; the agent changes them with the typed operations set_transfer_class,
set_extent, connect_features and set_identity_cues (ops.PlanSession), each validated here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.evolution.audit import DROPPED
from app.evolution.data import Animal, Taxonomy
from app.evolution.genome import EXTENT_ZONES, LAYER, SURFACE_TAGS, Genome, Trait, Transfer
from app.evolution.parts import class_entry, dorsal_wings, match, part_owner, surface, wing_spec

RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "transfer_rules.json"
CLASSES = {"a": "material", "b": "homologous", "c": "non_homologous", "material": "material",
           "homologous": "homologous", "non_homologous": "non_homologous"}
NEGATION = re.compile(r"\b(not|no|never|without|unlike|isn't|isnt|nor|instead of)\b", re.I)
MAX_CUES = 160
COVERING = "covering"


@lru_cache
def rules(path: Path = RULES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class TransferError(Exception):
    code: str
    message: str
    field: str | None = None
    hint: str = ""
    valid: list[str] | None = None

    def __str__(self) -> str:
        return self.message


def _name(tax: Taxonomy, aid: str | None) -> str:
    return tax.animals[aid].common_name.lower() if aid else ""


# ------------------------------------------------------------------ the donor features of a plan


TAG_SLOT = {"head": "head", "ears": "head", "skull": "head", "face": "face", "tail": "tail", "limbs": "limbs",
            "feet": "limbs", "mane": "head"}  # where on the host a slot part sits


@dataclass
class Feature:
    feature: str  # the part's class name ("head horn"), or "covering"
    donor: str
    slot: str  # head | face | tail | limbs | wings | back | surface
    shape: str  # class_parts shape (the old wording)


def features(g: Genome, tax: Taxonomy) -> list[Feature]:
    """Every donor feature in the plan: the donor covering, wings, slot parts and appendages."""
    if g.host is None:
        return []
    did = g.other(g.host)
    d = tax.animals[did]
    lp, t = g.limb_plan, g.traits
    out: list[Feature] = []
    w = wing_spec(d)
    if (lp.forelimbs.kind == "wings" and lp.forelimbs.donor == did) or (lp.extra_wings and lp.extra_wings.donor == did):
        out.append(Feature(w.part if w else "wings", did, "wings", w.shape if w else "a pair of wings"))
    for part in dorsal_wings(g, tax):
        s = match(d, part)
        out.append(Feature(s.part if s else "wings", did, "wings", s.shape if s else part))
    for tag, tr in t.items():
        if tr.part and tr.donor == did:
            s = match(d, tr.part)
            out.append(Feature(s.part if s else tr.part, did, TAG_SLOT.get(tag, "surface"), s.shape if s else tr.part))
    for app_ in lp.appendages:
        if app_.endswith(")") or app_ in dorsal_wings(g, tax) or part_owner(g, tax, app_) is not d:
            continue
        s = match(d, app_)
        out.append(Feature(s.part if s else app_, did, s.slot if s else "surface", s.shape if s else app_))
    tex = t["coat_texture"]
    if tex.op == "PATCH" and tex.donor == did:
        out.append(Feature(COVERING, did, "surface", surface(d)))
    seen, uniq = set(), []
    for f in out:
        if f.feature not in seen:
            seen.add(f.feature)
            uniq.append(f)
    return uniq


# ------------------------------------------------------------------ classification and defaults


def homologous_possible(donor: Animal, host: Animal, slot: str) -> bool:
    """(b) needs a matching host structure: both parents are vertebrates (shared limb, head and tail plans), and the
    host's class has the slot (a class whose `never` list holds "tail" has no tail to receive one)."""
    if donor.group != "vertebrate" or host.group != "vertebrate":
        return False
    never = set((class_entry(host) or {}).get("never") or [])
    return not (slot == "tail" and "tail" in never) and slot != "surface"


def default_class(f: Feature, donor: Animal, host: Animal) -> str:
    if f.feature == COVERING:
        return "material"
    return "homologous" if homologous_possible(donor, host, f.slot) else "non_homologous"


def covering_rule(donor: Animal) -> dict[str, Any] | None:
    ext = rules()["covering_extents"]
    return ext.get(f"{donor.tax_class}:{donor.covering}") or ext.get(donor.covering or "")


def anchor_for(f: Feature) -> str:
    a = rules()["anchors"]
    if f.feature == COVERING:
        return "the skin, as the host's own covering"
    return a["parts"].get(f.feature) or a["slots"].get(f.slot, "the skin")


def cue_for(f: Feature, donor: Animal) -> str:
    """A short, positive description of the form that makes the part the donor's: from transfer_rules.json, else the
    class shape with its placement words removed."""
    hit = rules()["cues"].get(f"{donor.tax_class}:{f.feature}")
    if hit:
        return hit
    s = re.sub(r"^(a|an|the|one|two|a pair of|a single)\s+", "", f.shape.strip(), flags=re.I)
    s = re.split(r"\s+(in place of|on the|at the|along the|rising from|between|around the|behind the|beside)\b", s)[0]
    return s.strip().rstrip(",")


def scale_rule(g: Genome, tax: Taxonomy, donor: Animal, rule: dict[str, Any] | None) -> str:
    host = _name(tax, g.host)
    if not rule or not rule.get("plates"):
        return f"sized to the {host}'s body and following its contours"
    unit = "scale" if "scale" in surface(donor) else "plate"
    s = f"each {unit} sized to the {host}'s own body segments and muscle masses, one {unit} per segment or muscle mass"
    return s + (", joined by flexible cuticle at every joint" if rule.get("joints") else "")  # "bands" reads as a pattern


def derive(g: Genome, tax: Taxonomy, policy: str = "rules") -> list[Transfer]:
    """The code's transfer records. policy "rules": covering extent from the donor's covering system
    (transfer_rules.json); "regions": from the plan's own PATCH regions (an older plan, read as it was rendered)."""
    if g.host is None:
        return []
    host = tax.animals[g.host]
    out: list[Transfer] = []
    for f in features(g, tax):
        donor = tax.animals[f.donor]
        cls = default_class(f, donor, host)
        if f.feature == COVERING:
            rule = covering_rule(donor) if policy == "rules" else None
            regions = [z for z in (g.traits["coat_texture"].region or []) if z in EXTENT_ZONES]
            zones, reason = ((list(rule["zones"]), rule["reason"]) if rule else
                             (regions, "plan regions" + (" (as rendered)" if policy == "regions" else
                                                         ": the donor covering is a surface patch, not a body system")))
            out.append(Transfer(feature=COVERING, donor=f.donor, kind="covering", cls="material",
                                anchor=anchor_for(f), extent=zones, extent_reason=reason,
                                scale=scale_rule(g, tax, donor, rule or covering_rule(donor))))
        else:
            out.append(Transfer(feature=f.feature, donor=f.donor, kind="part", cls=cls, anchor=anchor_for(f),
                                identity_cues=cue_for(f, donor)))
    return connect(out, policy)


HEAD_SLOTS = {"head horn", "horns", "head horns", "antlers", "antennae", "crest", "casque", "stalked eyes",
              "external gills"}


def _slot_zone(t: Transfer, feats: dict[str, Feature] | None = None) -> str | None:
    """The covering zone a part grows from."""
    slot = (feats or {}).get(t.feature).slot if feats and t.feature in feats else None
    if t.feature in HEAD_SLOTS or slot in ("head", "face") or "head" in t.anchor or "skull" in t.anchor \
            or "jaw" in t.anchor or "snout" in t.anchor or "forehead" in t.anchor:
        return "head"
    if slot == "tail" or "spine" in t.anchor and "base" in t.anchor:
        return "tail"
    if slot == "limbs" or "limb" in t.anchor or "forelimb" in t.anchor:
        return "legs"
    if "shoulder" in t.anchor:  # wings grow from the shoulders
        return "forequarters"
    return None


def connect(ts: list[Transfer], policy: str = "rules") -> list[Transfer]:
    """Related features of one donor system connect: each part grows from the donor covering (if there is one) in
    the zone it sits in, and that zone joins the covering's extent, so the covering continues into the body. With the
    "regions" policy (an older plan), extents are never changed."""
    cov = next((t for t in ts if t.kind == "covering"), None)
    if cov is None:
        return ts
    for t in ts:
        if t.kind != "part" or t.donor != cov.donor:
            continue
        zone = _slot_zone(t)
        if zone is None:
            continue
        if zone not in cov.extent:
            if policy != "rules" or cov.set_by == "agent":
                continue
            cov.extent = [z for z in EXTENT_ZONES if z in {*cov.extent, zone}]
            cov.extent_reason += f"; {zone} included so the {t.feature} grows from covering that continues into the body"
        if cov.feature not in t.connects:
            t.connects.append(cov.feature)
        if t.feature not in cov.connects:
            cov.connects.append(t.feature)
    return ts


# ------------------------------------------------------------------ the agent's edits (validated)


def _find(ts: list[Transfer], feature: str) -> Transfer:
    key = (feature or "").strip().lower()
    for t in ts:
        if t.feature.lower() == key:
            return t
    raise TransferError("no_such_feature", f"the plan has no donor feature {feature!r}", "feature",
                        valid=[t.feature for t in ts])


def apply_edit(ts: list[Transfer], edit: dict[str, Any], g: Genome, tax: Taxonomy) -> list[Transfer]:
    """One typed edit on a copy of the transfers. Raises TransferError (code, message, field, hint, valid)."""
    ts = [t.model_copy(deep=True) for t in ts]
    op, args = edit["op"], edit["args"]
    host = tax.animals[g.host] if g.host else None
    if op == "set_transfer_class":
        t = _find(ts, args.get("feature", ""))
        cls = CLASSES.get(str(args.get("cls", "")).strip().lower())
        if cls is None:
            raise TransferError("bad_class", f"no transfer class {args.get('cls')!r}", "cls",
                                valid=["material", "homologous", "non_homologous"])
        if t.kind == "covering" and cls != "material":
            raise TransferError("covering_is_material", "a covering transfers as material (RC-R10-15 a)", "cls",
                                valid=["material"])
        if t.kind == "part" and cls == "material":
            raise TransferError("part_is_structure", "a discrete part is a structure (homologous or not); use "
                                "drop_part to keep only its material", "cls", valid=["homologous", "non_homologous"])
        if cls == "homologous" and host is not None:
            slot = next((f.slot for f in features(g, tax) if f.feature == t.feature), "surface")
            if not homologous_possible(tax.animals[t.donor], host, slot):
                raise TransferError("no_homologous_structure", f"the {host.common_name} has no structure matching "
                                    f"the {t.feature} (different body plan or no such slot)", "cls",
                                    hint="a non-homologous part transfers only its material and function",
                                    valid=["non_homologous"])
        t.cls, t.set_by = cls, "agent"
        return ts
    if op == "set_extent":
        t = _find(ts, args.get("feature", ""))
        if t.kind != "covering":
            raise TransferError("not_a_covering", "only a covering has an extent", "feature",
                                valid=[x.feature for x in ts if x.kind == "covering"])
        zones = [str(z).strip().lower() for z in args.get("extent") or []]
        bad = [z for z in zones if z not in EXTENT_ZONES]
        if bad or not zones:
            raise TransferError("bad_extent", f"unknown or empty extent {bad or zones}", "extent",
                                valid=list(EXTENT_ZONES))
        reason = str(args.get("reason") or "").strip()
        if len(reason) < 12:
            raise TransferError("missing_reason", "an extent needs a functional reason (one short sentence)",
                                "reason", hint="for example: the legs stay furred for warmth in a cold habitat")
        rule = covering_rule(tax.animals[t.donor]) or {}
        if rule.get("joints") and "legs" not in zones and "leg" not in reason.lower():
            raise TransferError("unexplained_gap", "an exoskeleton covers the limbs unless a stated functional reason "
                                "limits it (RC-R10-16); say why the legs stay bare", "reason")
        t.extent = [z for z in EXTENT_ZONES if z in zones]
        t.extent_reason, t.set_by = reason, "agent"
        return connect(ts, "agent")
    if op == "connect_features":
        a, b = _find(ts, args.get("a", "")), _find(ts, args.get("b", ""))
        if a.feature == b.feature:
            raise TransferError("same_feature", "a feature cannot connect to itself", "b")
        if a.donor != b.donor:
            raise TransferError("different_donors", "only features of the same donor system connect", "b")
        for x, y in ((a, b), (b, a)):
            if y.feature not in x.connects:
                x.connects.append(y.feature)
            x.set_by = "agent"
        return ts
    if op == "set_identity_cues":
        t = _find(ts, args.get("feature", ""))
        cues = " ".join(str(args.get("cues") or "").split())
        if t.kind != "part":
            raise TransferError("not_a_part", "identity cues describe a discrete part", "feature",
                                valid=[x.feature for x in ts if x.kind == "part"])
        if not 3 <= len(cues) <= MAX_CUES:
            raise TransferError("bad_cues", f"cues are 3 to {MAX_CUES} characters", "cues")
        if NEGATION.search(cues):
            raise TransferError("negative_cues", "describe the part positively (what it is, not what it is not)",
                                "cues", hint="for example: smooth, glossy cuticle, curved upward from the head")
        other = tax.animals[g.other(t.donor)] if t.donor in (g.parents.sire, g.parents.dam) else None
        if other and other.common_name.lower() in cues.lower():
            raise TransferError("names_other_parent", "cues describe the donor's form only", "cues")
        t.identity_cues, t.set_by = cues, "agent"
        return ts
    raise TransferError("unknown_op", f"no transfer operation {op!r}", "op",
                        valid=["set_transfer_class", "set_extent", "connect_features", "set_identity_cues"])


def build(g: Genome, tax: Taxonomy, edits: list[dict[str, Any]] | None = None, policy: str = "rules") -> list[Transfer]:
    ts = derive(g, tax, policy)
    for e in edits or []:
        ts = apply_edit(ts, e, g, tax)
    return ts


SHAPE_ONLY_SLOTS = ("back", "surface")  # a non-homologous part here is a body covering shape (elytra, carapace)


def fold_shapes(g: Genome, tax: Taxonomy) -> list[str]:
    """RC-R10-15 (c): a non-homologous back or surface structure (a beetle's elytra or pronotum on a vertebrate) is
    never transferred as a shape; only its material transfers, as the donor covering. Returns the folded parts."""
    if g.host is None:
        return []
    host = tax.animals[g.host]
    did = g.other(g.host)
    d = tax.animals[did]
    folded = []
    for app_ in list(g.limb_plan.appendages):
        if part_owner(g, tax, app_) is not d:
            continue
        s = match(d, app_)
        if s and s.slot in SHAPE_ONLY_SLOTS and not homologous_possible(d, host, s.slot) and "wing" not in s.part:
            g.limb_plan.appendages.remove(app_)
            flag = f"{DROPPED}{s.part} (RC-R10-15: material only, as the covering)"
            if flag not in g.traits["body"].flags:
                g.traits["body"].flags.append(flag)
            folded.append(s.part)
    if folded and g.traits["coat_texture"].op != "PATCH":
        for tag in SURFACE_TAGS:
            g.traits[tag] = Trait(op="PATCH", donor=did, strength=1.0, region=["back", "flanks"])
    return folded


def sync_regions(g: Genome) -> None:
    """The covering's extent is where its material grows: the coat traits follow it as one layer (RC-R10-06)."""
    cov = next((t for t in g.transfers if t.kind == "covering"), None)
    if cov is None:
        return
    zones = [z for z in cov.extent if z in EXTENT_ZONES]
    for tag in SURFACE_TAGS:
        tr = g.traits[tag]
        if tr.op == "PATCH" and tr.donor == cov.donor and zones:
            flags = [f for f in tr.flags if f != LAYER] + ([LAYER] if len(zones) > 3 else [])
            g.traits[tag] = Trait(op="PATCH", donor=cov.donor, strength=1.0, region=zones, part=tr.part, note=tr.note,
                                  flags=flags)


def covering(g: Genome) -> Transfer | None:
    return next((t for t in g.transfers if t.kind == "covering"), None)


def parts(g: Genome) -> list[Transfer]:
    return [t for t in g.transfers if t.kind == "part"]


def dropped(g: Genome) -> list[str]:
    return [f[len(DROPPED):] for f in g.traits["body"].flags if f.startswith(DROPPED)]
