"""S3c (owner decision D4): one declared identity part per donor.

The S3b held-out pairs showed the identity problem: a crab donor gave a wolf a long segmented tail (a class-level
part from the Malacostraca list, but a crab's abdomen is tucked under its body), and the plated wolf read as a
woodlouse. The fix is a general rule, not a patch:

- An identity part is chosen from the donor's own diagnostic traits (its visible features, in their listed order),
  with the source of those traits or a model-estimated mark. It must be a part the donor actually has in that form:
  a class part counts only when the donor's own features name it. Only a donor with no recorded features at all
  falls back to its class list, marked as such.
- A covering is material, never an identity part, and never changes a body part's length or shape. A shape that
  folds into the covering (elytra, a carapace) is not a part either.
- Speculative and mythic modes: each donor that has no homologous structure on the host (an arthropod on a
  vertebrate) may keep exactly one donor-shaped part, the declared identity part, anchored by function (RC-R10-14)
  and listed in the fiction budget. Every other donor-shaped part is dropped (its material stays in the covering).
- Realistic mode: no donor-shaped part; identity is shown by color, texture and material only.

Vertebrate donors on vertebrate hosts keep the existing part rules (their parts are homologous, RC-R10-15 b).
The agent picks a different identity part with `set_identity_part(donor, part, reason)`; it is validated here
against the same candidates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.evolution.audit import _drop as _drop_flag
from app.evolution.data import Animal, Taxonomy, norm
from app.evolution.genome import Check, Genome, IdentityPart, Trait
from app.evolution.parts import forbidden, match, part_owner, specs

IDENTITY_MODES = ("speculative", "mythic")
NOT_PARTS = ("surface",)  # coverings and their materials
SHAPE_SLOTS = ("back",)  # a non-homologous back shape folds into the covering (RC-R10-15 c)
ADDABLE = ("head", "face", "tail", "limbs")  # where code may add a missing identity part (wings stay with the limb plan)
D4 = "D4: one identity part per donor"
QUALIFIER = re.compile(r"\s*[,(]?\s*\b(in|of)\s+(adult\s+|mature\s+|breeding\s+)?(males?|females?|adults?|juveniles?)\b\)?", re.I)


@dataclass(frozen=True)
class Candidate:
    part: str
    slot: str
    job: str
    feature: str  # the donor's own words ("" for the class-list fallback)
    source: str

    def public(self) -> dict[str, str]:
        return {"part": self.part, "slot": self.slot, "job": self.job, "feature": self.feature, "source": self.source}


def needs_identity(donor: Animal, host: Animal) -> bool:
    """D4 applies where the donor has no homologous structure on the host (different body plans)."""
    return donor.group != "vertebrate" or host.group != "vertebrate"


def candidates(donor: Animal) -> list[Candidate]:
    """The donor's possible identity parts, most diagnostic first: each of its own visible features that names a
    class part (not a covering, not a back shape that folds into the covering). With no recorded features, the
    class list, marked model-estimated."""
    out: list[Candidate] = []
    seen: set[str] = set()
    src = donor.source_of("visible_features", "features")
    for feat in donor.features:
        feat = QUALIFIER.sub("", feat).strip()  # "long curved head horn in males": the form, not who carries it
        s = match(donor, feat)
        if s is None or forbidden(donor, feat) or s.slot in NOT_PARTS or s.slot in SHAPE_SLOTS or s.part in seen:
            continue
        seen.add(s.part)
        out.append(Candidate(s.part, s.slot, s.job, feat, src))
    if not donor.features:
        for s in specs(donor):
            if s.slot in NOT_PARTS or s.slot in SHAPE_SLOTS or s.part in seen:
                continue
            seen.add(s.part)
            out.append(Candidate(s.part, s.slot, s.job, "", "model-estimated (class_parts.json class list; the "
                                 "donor's own visible features are not recorded)"))
    return out


def find(donor: Animal, part: str) -> Candidate | None:
    key = norm(part)
    for c in candidates(donor):
        if norm(c.part) == key or (c.feature and key and key in norm(c.feature)):
            return c
    s = match(donor, part)
    return next((c for c in candidates(donor) if s and c.part == s.part), None)


class IdentityError(ValueError):
    def __init__(self, code: str, message: str, valid: list[str] | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.valid = code, message, valid


def validate_pick(donor: Animal, part: str) -> Candidate:
    """An agent's pick must be one of the donor's own diagnostic parts."""
    c = find(donor, part)
    if c is None:
        valid = [x.part for x in candidates(donor)]
        raise IdentityError("not_a_donor_part", f"the {donor.common_name}'s own traits do not name a {part!r} in a form "
                            "that can be an identity part (coverings and back shapes are material, not parts)", valid)
    return c


# ------------------------------------------------------------------ the plan's donor parts


def _donor_parts(g: Genome, tax: Taxonomy, did: str) -> list[tuple[str, str, str]]:
    """(kind, key, class part) for each donor-shaped part: kind "trait" (key = tag) or "appendage" (key = text)."""
    d = tax.animals[did]
    out: list[tuple[str, str, str]] = []
    for tag, tr in g.traits.items():
        if tr.part and tr.donor == did:
            s = match(d, tr.part)
            out.append(("trait", tag, s.part if s else tr.part))
    for a in g.limb_plan.appendages:
        if a.endswith(")"):
            continue  # "<part> (tail)" mirrors a trait part
        if part_owner(g, tax, a) is d:
            s = match(d, a)
            out.append(("appendage", a, s.part if s else a[len(d.common_name) + 1:]))
    lp = g.limb_plan
    for slot in ("forelimbs", "extra_wings"):
        ls = getattr(lp, slot)
        if ls is not None and ls.kind == "wings" and ls.donor == did:
            s = next((x for x in specs(d) if x.slot == "wings"), None)
            out.append(("limb", slot, s.part if s else "wings"))
    return out


def _drop(g: Genome, tax: Taxonomy, kind: str, key: str, part: str, why: str) -> None:
    from app.evolution.genome import LimbSlot

    host = g.host or g.parents.sire
    lp = g.limb_plan
    if kind == "trait":
        g.traits[key] = Trait(op="PICK", donor=host, note=f"host {key}: {why}")
        lp.appendages = [a for a in lp.appendages if not a.endswith(f"({key})")]
    elif kind == "appendage":
        lp.appendages = [a for a in lp.appendages if a != key]
    else:
        if key == "forelimbs":
            lp.forelimbs = LimbSlot(kind="legs", donor=host)
        else:
            lp.extra_wings = None
        lp.requested_wings = None
    _drop_flag(g, part, frozenset())  # the usual "dropped part: <key>" flag, read by the prompt and the checklist
    g.checks.append(Check(step="identity", result="adjusted", detail=f"{part} dropped: {why}",
                          cards=["RC-R10-15"]))


AGENT_NOTE = "set by the agent"


def _cleared_by_agent(g: Genome, c: Candidate) -> bool:
    from app.evolution.audit import DROPPED, part_key

    if f"{DROPPED}{part_key(c.part)}" in g.traits["body"].flags:
        return True
    tag = {"tail": "tail", "head": "head", "face": "face"}.get(c.slot)
    return bool(tag and AGENT_NOTE in (g.traits[tag].note or ""))


def _add(g: Genome, tax: Taxonomy, donor: Animal, c: Candidate) -> None:
    if c.slot == "tail":
        g.traits["tail"] = Trait(op="PICK", donor=donor.id, part=c.part, note=f"identity part ({D4})")
        g.limb_plan.appendages = [a for a in g.limb_plan.appendages if not a.endswith("(tail)")]
        g.limb_plan.appendages.append(f"{c.part} (tail)")
    else:
        g.limb_plan.appendages.append(f"{donor.common_name.lower()} {c.part}")


def apply(g: Genome, tax: Taxonomy, picks: dict[str, tuple[str, str]] | None = None) -> list[str]:
    """Choose and enforce the identity part of the non-host donor. `picks`: {donor id: (part, reason)} from the
    agent. Mutates g (parts dropped or added, g.identity_parts set). Returns the cards applied."""
    g.identity_parts = []
    if g.host is None:
        return []
    host = tax.animals[g.host]
    did = g.other(g.host)
    donor = tax.animals[did]
    have = _donor_parts(g, tax, did)
    if not needs_identity(donor, host):  # homologous parts follow the existing rules: declare, never add or drop
        present = {p for _k, _key, p in have}
        pick = (picks or {}).get(did)
        c = validate_pick(donor, pick[0]) if pick else next((x for x in candidates(donor) if x.part in present), None)
        if c is not None and c.part in present and g.design_mode in IDENTITY_MODES:
            g.identity_parts = [IdentityPart(donor=did, part=c.part, slot=c.slot, job=c.job, feature=c.feature,
                                             source=c.source, set_by="agent" if pick else "code",
                                             reason=pick[1] if pick else f"the {donor.common_name}'s own diagnostic "
                                             f"part already in the plan ({c.feature or 'class list'})")]
        return []
    if g.design_mode not in IDENTITY_MODES:
        for kind, key, part in have:
            _drop(g, tax, kind, key, part, "D4: realistic mode shows the donor by color, texture and material only")
        return ["RC-R10-15"]
    pick = (picks or {}).get(did)
    cands = candidates(donor)
    chosen: Candidate | None = None
    set_by, reason = "code", ""
    if pick:
        chosen, set_by, reason = validate_pick(donor, pick[0]), "agent", pick[1]
    else:
        present = {p for _k, _key, p in have}
        order = cands if donor.features else sorted(cands, key=lambda c: c.part not in present)  # fallback: keep
        for c in order:  # the plan's own class part first, since nothing says the donor lacks it in that form
            # code adds a missing part only when the donor's own features name it; a class-list fallback keeps one
            if c.part in present or (c.slot in ADDABLE and c.feature):
                chosen = c
                break
        if chosen is not None:
            reason = (f"the first of the {donor.common_name}'s own diagnostic features that names a part it has in "
                      f"that form: {chosen.feature!r}" if chosen.feature else
                      f"no visible features recorded for the {donor.common_name}: first part of its class list")
    for kind, key, part in have:
        if chosen is None or part != chosen.part:
            _drop(g, tax, kind, key, part, f"{D4}; {('the identity part is the ' + chosen.part) if chosen else 'none found'}")
    if chosen is None:
        return ["RC-R10-15"]
    if not any(p == chosen.part for _k, _key, p in have):
        if _cleared_by_agent(g, chosen):  # the agent gave this slot back to the host, or dropped this part
            g.checks.append(Check(step="identity", result="adjusted", cards=["RC-R10-15"],
                                  detail=f"identity part {chosen.part} not added: the agent cleared it"))
            return ["RC-R10-15"]
        _add(g, tax, donor, chosen)
    g.identity_parts = [IdentityPart(donor=did, part=chosen.part, slot=chosen.slot, job=chosen.job,
                                     feature=chosen.feature, source=chosen.source, reason=reason, set_by=set_by)]
    return ["RC-R10-14", "RC-R10-15"]


def public(g: Genome) -> list[dict[str, Any]]:
    return [p.model_dump() for p in g.identity_parts]
