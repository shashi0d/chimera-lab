"""S3a part 2: the plan-blind critic protocol for inspect.

S2 showed that one checklist critic that sees plan wording answers "yes" to everything (the run-1 whole-beetle plate
passed). The protocol replaces it for inspect:

a) Describe first. The critic sees only the image and freely describes every body part, attached object and animal
   it sees (`describe`). No plan text reaches this call.
b) Count questions, in the same call after the description: separate bodies or body-shaped objects, heads, walking
   legs, wings, extra limb-like pieces, and the animals seen (code finds any animal other than the two parents).
c) A balanced checklist (`ask`): at least half the questions are phrased so the correct answer is "no". Questions
   name visible features ("a single curved horn rising from the brow"), never plan language ("donor", "patch").
d) Integration questions: does the donor covering grow out of the body with a natural transition, or sit on top
   like separate pieces; does it form one continuous structure where planned, or scattered pieces.
e) Two critics (Spark Open and Meta Spark 1.3) answer the describe call and the checklist independently. Agreement
   decides; disagreement or "unclear" becomes "uncertain", which the agent treats as a fail signal.
f) Code matches each free description against the plan: extras (a structural feature the plan does not have, such
   as wings or gills) and omissions (a planned part nobody described).

Every question carries its expected answer and a fix worded from the plan item (for the one edit turn).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.evolution.audit import DROPPED
from app.evolution.data import Animal, Taxonomy
from app.evolution.genome import Genome
from app.evolution.parts import dorsal_wings, match, part_owner, surface

KEEP = "keep everything else the same"
PROTECTIVE = ("exoskeleton", "shell", "scales", "carapace")  # RC-R10-12: coverings that replace the host's
EXPECTED: dict[str, str] = {}  # question text -> expected answer (read by the mock critic only)

# ------------------------------------------------------------------ questions


@dataclass
class Question:
    id: str
    text: str  # what the critic reads: visible features only
    expect: str  # "yes" | "no"
    group: str  # structure | integration | placement | pattern
    fix: str = ""  # edit instruction worded from the plan item
    sam: str | None = None  # SAM label that can confirm presence (expect "yes" part questions only)


def _name(tax: Taxonomy, aid: str | None) -> str:
    return tax.animals[aid].common_name.lower() if aid else ""


def _regions(regs: list[str] | None) -> str:
    regs = [r.replace("forequarters", "shoulders").replace("hindquarters", "hips") for r in regs or []]
    return regs[0] if len(regs) == 1 else ", ".join(regs[:-1]) + " and " + regs[-1] if regs else "body"


def covering_noun(donor: Animal) -> str:
    """The donor's covering as something visible ("hard, glossy chitin plates with fine seams")."""
    return surface(donor)


def _host_cover(host: Animal | None) -> str:
    return {"fur": "fur", "feathers": "feathers", "scales": "scales"}.get((host.covering if host else "") or "",
                                                                            "skin")


def _donor_patch(g: Genome) -> tuple[str | None, list[str]]:
    tex = g.traits["coat_texture"]
    did = g.other(g.host) if g.host else None
    if did and tex.op == "PATCH" and tex.donor == did:
        return did, list(tex.region or [])
    return None, []


def legs_planned(g: Genome) -> int:
    lp = g.limb_plan
    return sum(2 for s in (lp.forelimbs, lp.hindlimbs) if s.kind == "legs")


def wings_planned(g: Genome, tax: Taxonomy) -> int:
    lp = g.limb_plan
    return 2 if (lp.forelimbs.kind == "wings" or (lp.extra_wings and lp.extra_wings.donor) or dorsal_wings(g, tax)) else 0


def questions(g: Genome, tax: Taxonomy) -> list[Question]:
    """The balanced checklist for one plan: structure, integration, placement and pattern questions, at least half
    of them with the expected answer "no"."""
    host_id = g.host
    host = tax.animals[host_id] if host_id else None
    hn = _name(tax, host_id)
    a, b = _name(tax, g.parents.sire), _name(tax, g.parents.dam)
    parents = [tax.animals[g.parents.sire], tax.animals[g.parents.dam]]
    lp, t = g.limb_plan, g.traits
    body = f"the {hn}'s own body" if hn else "the body"
    cover = _host_cover(host)
    qs: list[Question] = []

    # structure, expected yes
    if hn and not g.known_pair:  # iteration 2: a mule's body is not "a horse body shape" to either critic
        qs.append(Question("frame", f"Is the overall body shape that of a {hn}?", "yes", "structure",
                           f"Show the planned {hn} body shape and outline; {KEEP}."))
    else:
        qs.append(Question("frame", f"Does the body look like one animal mixing a {a} and a {b}?", "yes", "structure",
                           f"Show the planned in-between body of the {a} and the {b}; {KEEP}."))
    head = t["head"].donor if isinstance(t["head"].donor, str) else None
    hd = _name(tax, head)
    qs.append(Question("head", f"Does it have a {hd} head with visible eyes?" if hd else
                       "Does it have one clear head with visible eyes?", "yes", "structure",
                       f"Show the planned {hd or 'single'} head, fully visible with clear eyes; {KEEP}.",
                       sam=f"{hd} head" if hd and head != host_id else None))
    nwings = wings_planned(g, tax)
    if lp.forelimbs.kind == "wings" and lp.forelimbs.donor:
        wn = _name(tax, lp.forelimbs.donor)
        qs.append(Question("wings_front", f"Does it have {wn} wings in place of its front legs?", "yes", "structure",
                           f"Show the planned {wn} wings in place of the front legs, standing on two hind legs; {KEEP}.",
                           sam="wings"))
        qs.append(Question("legs_and_wings", "Does it stand on four walking legs and also have wings?", "no",
                           "structure", f"The plan has wings in place of the front legs: show two hind legs only; "
                                        f"{KEEP}."))
    elif nwings:
        qs.append(Question("wings_extra", "Does it have four walking legs plus a separate pair of wings?", "yes",
                           "structure", f"Show the planned four legs plus a separate pair of wings; {KEEP}.",
                           sam="wings"))
    else:
        qs.append(Question("no_wings", "Are there wings anywhere on the body?", "no", "structure",
                           f"The plan has no wings: show {body} there instead; {KEEP}."))
    for tag, tr in t.items():
        if tr.part and isinstance(tr.donor, str) and tr.donor != host_id:
            s = match(tax.animals[tr.donor], tr.part)
            shape = s.shape if s else f"{_name(tax, tr.donor)} {tr.part}"
            qs.append(Question(f"part_{tag}", f"Is there {_article(shape)} in place of the {tag}?", "yes",
                               "structure", f"Show the planned {shape} in place of the {tag}; {KEEP}.",
                               sam=(s.part if s else tr.part)))
    for app_ in lp.appendages:
        if app_ in dorsal_wings(g, tax):
            continue
        if app_.endswith(")"):  # "tentacles (tail)": a slot part already asked above
            continue
        owner = part_owner(g, tax, app_)
        s = match(owner, app_) if owner else None
        shape = s.shape if s else app_
        qs.append(Question(f"part_{_slug(app_)}", f"Is there {_article(shape)}?", "yes", "structure",
                           f"Show the planned {shape}, on {body}; {KEEP}.", sam=(s.part if s else app_)))

    # structure, expected no
    qs.append(Question("whole_animal", "Is there a whole separate animal, or an animal-shaped object with its own "
                       "head, legs or wing cases, attached to or sitting on the body?", "no", "structure",
                       _one_body_fix(g, tax)))
    qs.append(Question("second_head", "Is there a second head anywhere?", "no", "structure",
                       f"Show one single head, as planned; {KEEP}."))
    if any(p.group == "arthropod" for p in parents) and legs_planned(g):
        qs.append(Question("insect_legs", "Are there jointed, insect-like leg pieces on or along the legs?", "no",
                           "structure", f"Show the {hn or 'creature'}'s own legs with its own {cover}, with no insect "
                                        f"leg pieces; {KEEP}."))
    n = legs_planned(g)
    if n:
        qs.append(Question("extra_legs", f"Does it have more than {n} walking legs?", "no", "structure",
                           f"Show exactly {n} walking legs, as planned; {KEEP}."))
    for flag in t["body"].flags:
        if flag.startswith(DROPPED):
            key = flag[len(DROPPED):]
            if key == "wings" and any(q.id == "no_wings" for q in qs):
                continue
            qs.append(Question(f"dropped_{_slug(key)}", f"Are there {key} anywhere on the body?", "no", "structure",
                               f"The plan has no {key}: show {body} there instead; {KEEP}."))
    exp_concepts, _ = planned_concepts(g, tax)
    for p in parents:
        if p.id == host_id:
            continue
        for feat in p.features:
            c = concepts_in(feat) & set(STRUCTURAL_EXTRAS)
            asked = {x for q in qs if q.expect == "no" for x in concepts_in(q.text)}
            if c and not c & exp_concepts and not c <= asked:
                qs.append(Question(f"unplanned_{_slug(feat)[:30]}", f"Are there {_strip_count(feat)} anywhere on the "
                                   "creature?", "no", "structure",
                                   f"The plan has no {_strip_count(feat)}: show {body} there instead; {KEEP}."))
    mane = t["mane"]
    if "gated" in mane.flags and any(p.tax_class == "Mammalia" for p in parents):
        qs.append(Question("no_mane", "Does it have a full mane of long hair around the head and neck?", "no",
                           "structure", f"The plan has no mane: show the planned neck with no mane; {KEEP}."))

    # pattern (fur hosts only)
    pat = t["coat_pattern"]
    if cover == "fur":
        if "plain" in pat.flags or pat.op == "PATCH" or (pat.op == "PICK" and pat.donor is None):
            qs.append(Question("plain_fur", "Does the fur show stripes or spots?", "no", "pattern",
                               f"Show a plain coat with no stripes or spots, as planned; {KEEP}."))
        elif pat.op == "OVERLAY" and (pat.strength or 0) <= 0.5:
            pn = _name(tax, pat.donor if isinstance(pat.donor, str) else None)
            qs.append(Question("bold_pattern", "Does the fur show bold, high-contrast stripes or spots over most of the "
                               "body, more than faint markings?", "no", "pattern",
                               f"Show only faint {pn}-type markings on the {_regions(pat.region)}, as planned; {KEEP}."))

    # integration and placement: the donor covering on the host
    did, regs = _donor_patch(g)
    if did and hn:
        donor = tax.animals[did]
        noun = covering_noun(donor)
        where = _regions(regs)
        grow_fix = (f"Show the {noun} grown in the skin over the {where}, as one covering that replaces the {hn}'s "
                    f"{cover} there; the {cover} stops at its edge; {KEEP}.")
        pl = noun.split(" with ")[0].endswith("s")
        are, do, it = ("Are there", "Do the", "they") if pl else ("Is there", "Does the", "it")
        # iteration 3: a soft surface patch (skin, feathers) is informational, like the S2 surface item; a
        # protective covering's presence is an integration question
        qs.append(Question("cover_present", f"{are} {noun} on the {where}?", "yes",
                           "integration" if donor.covering in PROTECTIVE else "surface",
                           f"Show the planned {noun} over the {where}; {KEEP}."))
        if donor.covering in PROTECTIVE:  # iteration 2: RC-R10-12 is about protective coverings only; soft skin or
            # feather patches are a surface change, and the owner rated the axolotl skin patches good
            qs.append(Question("grows_out", f"{do} {noun} grow out of the body with a natural transition (for example "
                               f"{cover} stopping at a shield's edge, or skin blending into scales), rather than "
                               "looking attached on top?", "yes", "integration", grow_fix))
            qs.append(Question("on_top", f"{do} {noun} look like {'separate pieces' if pl else 'a separate piece'} "
                               f"attached on top of the {cover}?", "no", "integration", grow_fix))
            one_fix = (f"Show the {noun} as one continuous covering over the {where}, not scattered pieces; the "
                       f"{hn}'s {cover} stays on the belly and legs; {KEEP}.")
            qs.append(Question("continuous", f"Do the {noun} form one continuous structure over the {where}, "
                               "rather than scattered pieces?", "yes", "integration", one_fix))
            qs.append(Question("scattered", f"Are the {noun} scattered as separate pieces over different parts of the "
                               "body?", "no", "integration", one_fix))
            keep_fix = f"Keep the {hn}'s own {cover} on the legs and shoulders; the {noun} only over the {where}; {KEEP}."
            if not {"legs", "forelimbs", "hindlimbs"} & set(regs):
                qs.append(Question("cover_on_legs", f"Are there {noun} on the legs?", "no", "placement", keep_fix))
            if "forequarters" not in regs:
                qs.append(Question("cover_on_shoulders", f"Are there {noun} on the shoulders?", "no", "placement",
                                   keep_fix))
    return _balance(_dedupe(qs), g)


def _one_body_fix(g: Genome, tax: Taxonomy) -> str:
    did, regs = _donor_patch(g)
    hn = _name(tax, g.host)
    if did and hn:
        dn = _name(tax, did)
        return (f"Show the planned {dn} contribution only as {surface(tax.animals[did])} on the {hn}'s own body over "
                f"the {_regions(regs)}, not as separate animals; {KEEP}.")
    return f"Show one single creature with only its planned parts, no separate animals on it; {KEEP}."


def _balance(qs: list[Question], g: Genome) -> list[Question]:
    """At least half the questions expect "no" (c). Neutral no-questions fill the gap."""
    fillers = [Question("human", "Is there a human figure or a human body part?", "no", "structure",
                        f"Show only the creature; {KEEP}."),
               Question("second_creature", "Is there a second, separate creature next to it?", "no", "structure",
                        f"Show one single creature; {KEEP}.")]
    for f in fillers:
        if sum(q.expect == "no" for q in qs) * 2 >= len(qs):
            break
        qs.append(f)
    for q in qs:
        EXPECTED[q.text] = q.expect
    return qs


def _dedupe(qs: list[Question]) -> list[Question]:
    seen, out = set(), []
    for q in qs:
        if q.text not in seen:
            seen.add(q.text)
            out.append(q)
    return out


def _strip_count(feat: str) -> str:
    """"three pairs of feathery external gills on the sides of the head" -> "feathery external gills"."""
    f = re.sub(r"^(a|an|one|two|three|four|five|six) (pairs? of )?", "", feat.lower().strip())
    return re.split(r" (on|in|along|at|of the) ", f)[0]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _article(shape: str) -> str:
    low = shape.lower()
    if low.startswith(("a ", "an ", "the ", "one ", "two ", "three ", "four ", "six ", "eight ")) or low.endswith("s"):
        return shape
    return ("an " if low[:1] in "aeiou" else "a ") + shape


# ------------------------------------------------------------------ counts

COUNT_KEYS = ("separate_bodies", "heads", "walking_legs", "wings", "extra_limb_pieces")


def expected_counts(g: Genome, tax: Taxonomy) -> dict[str, int | None]:
    """What the plan says the critic should count. None: not checked (a planned tentacle tail makes extra limb-like
    pieces expected; a legless body has no leg count)."""
    tentacles = any("tentacle" in (tr.part or "") for tr in g.traits.values()) or any(
        "tentacle" in a for a in g.limb_plan.appendages)
    n = legs_planned(g)
    return {"separate_bodies": 1, "heads": 1, "walking_legs": n or None, "wings": wings_planned(g, tax),
            "extra_limb_pieces": None if tentacles else 0}


# ------------------------------------------------------------------ description matching (f)

CONCEPTS: dict[str, str] = {
    "wings": r"\bwings?\b(?![- ]?(cases?|covers?|cover-like|case-like))|\bwinged\b",  # wing cases are plates
    "gills": r"\bgills?\b",
    "horn": r"\bhorns?\b|\bhorned\b",
    "mane": r"\bmane\b|\bmaned\b",
    "stripes": r"\bstripes?\b|\bstriped\b|\bstriping\b",
    "spots": r"\bspots?\b|\bspotted\b|\brosettes?\b",
    "tentacles": r"\btentacles?\b|\bsuckers?\b",
    "beak": r"\bbeak\b|\bbill\b",
    "feathers": r"\bfeather(s|ed)?\b|\bplumage\b",
    "scales": r"\bscales?\b|\bscaly\b|\bscaled\b",
    "plates": r"\bplates?\b|\bplated\b|\barmou?r(ed)?\b|\bshell\b|\bcarapace\b|\belytra\b|\bwing[- ]cases?\b|\bshields?\b",
    "insect_legs": r"\b(insect|jointed|segmented|arthropod)(-like)?[- ]legs?\b|\binsect[- ]leg\b|\bleg segments?\b",
    "whole_body": (r"\bwhole (beetle|insect|bug|animal)s?\b|\b(beetle|insect|bug)[- ]shaped\b|\bentire (beetle|insect)s?\b"
                   r"|\b(small|several|multiple|two|three|four|five|many) (beetle|insect|bug)s\b"
                   r"|\b(beetle|insect|bug)s? (attached|clinging|sitting|perched|crawling)\b"),
    "antennae": r"\bantenna(e|s)?\b",
}
# Concepts that are a fail signal when they appear but the plan does not have them.
STRUCTURAL_EXTRAS = ("wings", "gills", "horn", "mane", "stripes", "spots", "tentacles", "beak", "insect_legs",
                     "whole_body", "antennae")
CLASS_BASE = {"Aves": {"wings", "beak", "feathers"}, "Mammalia": set(), "Amphibia": set(), "Reptilia": {"scales"},
              "Actinopterygii": {"scales"}}
COVER_CONCEPT = {"feathers": "feathers", "scales": "scales", "exoskeleton": "plates", "shell": "plates"}
MANED = ("Felidae", "Equidae")


def concepts_in(text: str) -> set[str]:
    low = text.lower()
    return {c for c, rx in CONCEPTS.items() if re.search(rx, low)}


NEGATED = re.compile(r"\b(no|not|without|none|lacks?|lacking|nor|neither|absent)\b[^.;:|]*", re.I)


def seen_concepts(text: str) -> set[str]:
    """Concepts a description reports as present (iteration 2): negated clauses ("no distinct spots or stripes",
    "No wings, tentacles, or additional limbs") are dropped, and a "mane" of feathers is a feather ruff."""
    t = NEGATED.sub(" ", text)
    t = re.sub(r"\bmane\b(?=[^.;|]{0,80}feather)", "ruff", t, flags=re.I)
    t = re.sub(r"(feather[^.;|]{0,40})\bmane\b", r"\1ruff", t, flags=re.I)
    # iteration 3: one line along the spine (an equid's dorsal or eel stripe) is not a striped coat pattern
    t = re.sub(r"\b(thin |narrow |dark |faint |single )*(dorsal|eel|spinal|back) stripe\b", "dorsal line", t, flags=re.I)
    return concepts_in(t)


def planned_concepts(g: Genome, tax: Taxonomy) -> tuple[set[str], set[str]]:
    """(expected: concepts the plan explains, required: planned donor parts a description should mention)."""
    host = tax.animals[g.host] if g.host else None
    t, lp = g.traits, g.limb_plan
    exp: set[str] = set()
    req: set[str] = set()
    bodies = [host] if host else [tax.animals[g.parents.sire], tax.animals[g.parents.dam]]
    for a in bodies:
        exp |= CLASS_BASE.get(a.tax_class, set())
        if a.covering in COVER_CONCEPT:
            exp.add(COVER_CONCEPT[a.covering])
        exp |= concepts_in(" ".join(a.features))
    head = t["head"].donor if isinstance(t["head"].donor, str) else None
    if head:
        exp |= CLASS_BASE.get(tax.animals[head].tax_class, set()) & {"beak", "feathers"}
    if wings_planned(g, tax):
        exp.add("wings")
        req.add("wings")
        wd = lp.forelimbs.donor if lp.forelimbs.kind == "wings" else (lp.extra_wings.donor if lp.extra_wings else None)
        if wd and tax.animals[wd].tax_class == "Aves":
            exp.add("feathers")
    else:
        exp.discard("wings")
    for tr in t.values():
        if tr.part and isinstance(tr.donor, str) and tr.donor != g.host:
            c = concepts_in(tr.part) or concepts_in((match(tax.animals[tr.donor], tr.part) or _NoSpec).shape)
            exp |= c
            req |= c & set(STRUCTURAL_EXTRAS)
    for app_ in lp.appendages:
        owner = part_owner(g, tax, app_)
        s = match(owner, app_) if owner else None
        c = concepts_in(app_) | concepts_in(s.shape if s else "")
        exp |= c
        req |= c & set(STRUCTURAL_EXTRAS)
    did, _ = _donor_patch(g)
    if did:
        d = tax.animals[did]
        c = concepts_in(surface(d)) | ({COVER_CONCEPT[d.covering]} if d.covering in COVER_CONCEPT else set())
        exp |= c
        req |= c & {"plates", "scales", "feathers"}
        if c & {"plates", "scales"}:
            exp |= {"plates", "scales"}  # one hard covering is described with either word
    mane = t["mane"]
    if "gated" not in mane.flags and isinstance(mane.donor, str) and tax.animals[mane.donor].family in MANED:
        exp.add("mane")
    elif "gated" in mane.flags:
        exp.discard("mane")
    pat = t["coat_pattern"]
    if pat.op == "OVERLAY":
        exp |= {"stripes", "spots"}
    elif "plain" in pat.flags:
        exp -= {"stripes", "spots"}
    for flag in t["body"].flags:
        if flag.startswith(DROPPED):
            exp -= concepts_in(flag[len(DROPPED):])
    return exp, req


class _NoSpec:
    shape = ""


def description_text(d: dict[str, Any]) -> str:
    parts = " | ".join(f"{p.get('part', '')}: {p.get('looks_like', '')} ({p.get('where', '')})"
                       for p in d.get("parts") or [] if isinstance(p, dict))
    return " | ".join([str(d.get("description") or ""), parts, " | ".join(map(str, d.get("attached_objects") or []))])


def match_description(d: dict[str, Any], g: Genome, tax: Taxonomy) -> dict[str, Any]:
    exp, req = planned_concepts(g, tax)
    seen = seen_concepts(description_text(d))
    extras = sorted((seen - exp) & set(STRUCTURAL_EXTRAS))
    omissions = sorted(req - seen)
    return {"seen": sorted(seen), "expected": sorted(exp), "extras": extras, "omissions": omissions}


# ------------------------------------------------------------------ combining two critics


def combine(outcomes: list[str]) -> str:
    """Per-critic outcomes ("ok", "bad", "unk") -> pass, fail or uncertain. One critic: ok pass, bad fail, unk
    uncertain. Two: agreement decides; disagreement or any unk is uncertain."""
    if outcomes and all(o == "ok" for o in outcomes):
        return "pass"
    if outcomes and all(o == "bad" for o in outcomes):
        return "fail"
    return "uncertain"


def _answer_outcome(ans: str, expect: str) -> str:
    return "unk" if ans not in ("yes", "no") else ("ok" if ans == expect else "bad")


def _third(d: dict[str, Any], g: Genome, tax: Taxonomy, route: Any) -> list[str]:
    from app.evolution.judge import third_animals

    return third_animals({"animals": d.get("animals") or []}, tax.animals[g.parents.sire], tax.animals[g.parents.dam],
                         tax, route)


@dataclass
class Raw:
    """One critic's two answers for one image."""
    describe: dict[str, Any] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)  # question text -> yes | no | unclear
    error: str | None = None


def evaluate(raws: dict[str, Raw], g: Genome, tax: Taxonomy, route: Any = None,
             qs: list[Question] | None = None) -> dict[str, Any]:
    """Score the critics' raw answers against the plan. Pure: calibration re-scores the same raw answers for each
    critic alone and for the pair without new calls."""
    qs = qs if qs is not None else questions(g, tax)
    names = list(raws)
    rows: list[dict[str, Any]] = []
    for q in qs:
        ans = {c: raws[c].answers.get(q.text, "unclear") for c in names}
        rows.append({"source": "checklist", "key": q.id, "text": q.text, "group": q.group, "expect": q.expect,
                     "answers": ans, "status": combine([_answer_outcome(a, q.expect) for a in ans.values()]),
                     "fix": q.fix, "sam": q.sam})
    exp_counts = expected_counts(g, tax)
    for k in COUNT_KEYS:
        want = exp_counts[k]
        if want is None:
            continue
        got = {c: raws[c].describe.get(k) for c in names}
        outs = ["unk" if not isinstance(v, int) else ("ok" if _count_ok(k, v, want) else "bad") for v in got.values()]
        rows.append({"source": "count", "key": k, "text": f"{k.replace('_', ' ')}: {want}", "group": "structure",
                     "expect": want, "answers": got, "status": combine(outs), "fix": _count_fix(k, want, g, tax),
                     "sam": None})
    matches = {c: match_description(raws[c].describe, g, tax) for c in names}
    thirds = {c: _third(raws[c].describe, g, tax, route) for c in names}
    for c in names:
        if raws[c].error:
            rows.append({"source": "error", "key": f"error_{c}", "text": f"{c} failed: {raws[c].error}",
                         "group": "structure", "expect": None, "answers": {c: raws[c].error}, "status": "uncertain",
                         "fix": "", "sam": None})
    extras = sorted({e for m in matches.values() for e in m["extras"]})
    for e in extras:
        outs = ["bad" if e in matches[c]["extras"] else "ok" for c in names]
        rows.append({"source": "description", "key": f"extra_{e}", "text": f"described but not planned: {e}",
                     "group": "structure", "expect": "absent", "answers": {c: e in matches[c]["extras"] for c in names},
                     "status": combine(outs), "fix": _extra_fix(e, g, tax), "sam": None})
    omits = sorted({o for m in matches.values() for o in m["omissions"]})
    for o in omits:
        outs = ["bad" if o in matches[c]["omissions"] else "ok" for c in names]
        rows.append({"source": "description", "key": f"omitted_{o}", "text": f"planned but not described: {o}",
                     "group": "structure", "expect": "present",
                     "answers": {c: o not in matches[c]["omissions"] for c in names}, "status": combine(outs),
                     "fix": f"Show the planned {o} clearly; {KEEP}.", "sam": None})
    animals = sorted({x for v in thirds.values() for x in v})
    if animals:
        outs = ["bad" if thirds[c] else "ok" for c in names]
        rows.append({"source": "description", "key": "third_animal", "text": "an animal other than the two parents",
                     "group": "structure", "expect": "none", "answers": thirds, "status": combine(outs),
                     "fix": _one_body_fix(g, tax), "sam": None})
    signals = [r for r in rows if r["status"] != "pass" and r["group"] != "surface"]  # surface rows: info only
    return {"critics": names, "questions": [asdict(q) for q in qs], "expected_counts": exp_counts, "rows": rows,
            "descriptions": {c: raws[c].describe for c in names}, "matches": matches, "third_animals": thirds,
            "signals": signals, "verdict": "fail" if signals else "pass",
            "balance": {"yes": sum(q.expect == "yes" for q in qs), "no": sum(q.expect == "no" for q in qs)}}


def _count_ok(key: str, got: int, want: int) -> bool:
    if key == "walking_legs":
        return got == want or (want == 4 and got == 3)  # a side view can hide one leg
    return got == want


def _count_fix(key: str, want: int, g: Genome, tax: Taxonomy) -> str:
    hn = _name(tax, g.host) or "creature"
    return {"separate_bodies": _one_body_fix(g, tax),
            "heads": f"Show one single head, as planned; {KEEP}.",
            "walking_legs": f"Show exactly {want} walking legs, as planned; {KEEP}.",
            "wings": (f"The plan has no wings: show the {hn}'s own body there instead; {KEEP}." if want == 0
                      else f"Show exactly one pair of wings, as planned; {KEEP}."),
            "extra_limb_pieces": f"Show the {hn}'s own limbs only, with no extra limb-like pieces; {KEEP}."}[key]


def _extra_fix(concept: str, g: Genome, tax: Taxonomy) -> str:
    hn = _name(tax, g.host) or "creature"
    words = {"insect_legs": "insect leg pieces", "whole_body": "separate animal bodies"}
    return f"The plan has no {words.get(concept, concept)}: show the {hn}'s own body there instead; {KEEP}."


# ------------------------------------------------------------------ running the critics


TRIES = 2  # iteration 2: one retry when an answer is unreadable (cut off at the output cap)


async def _try(meter: Any, purpose: str, make: Any) -> Any:
    from app.errors import ChimeraError
    from app.models.schemas import ErrorCode

    for n in range(TRIES):
        try:
            return await meter.call("spark", purpose, make())
        except ChimeraError as e:
            if e.code == ErrorCode.BUDGET_EXCEEDED or n == TRIES - 1:
                raise
        except (ValueError, KeyError, TypeError):
            if n == TRIES - 1:
                raise
    raise AssertionError("unreachable")


async def run_critic(name: str, spark: Any, image: bytes, qs: list[Question], meter: Any) -> tuple[str, Raw]:
    """One critic, two calls: the free description (plan-blind) first, then the balanced checklist. A failure after
    the retry becomes an "uncertain" row, never a crash (a budget stop is raised)."""
    raw = Raw()
    try:
        raw.describe = await _try(meter, f"describe:{name}", lambda: spark.describe(image))
        got = await _try(meter, f"ask:{name}", lambda: spark.ask(image, [q.text for q in qs]))
        raw.answers = {a["item"]: a["answer"] for a in got.get("answers") or [] if isinstance(a, dict)}
    except Exception as e:  # noqa: BLE001
        from app.errors import ChimeraError
        from app.models.schemas import ErrorCode

        if isinstance(e, ChimeraError) and e.code == ErrorCode.BUDGET_EXCEEDED:
            raise
        raw.error = f"{type(e).__name__}: {str(e)[:160]}"
    return name, raw


async def protocol(image: bytes, g: Genome, tax: Taxonomy, critics: dict[str, Any], meter: Any,
                   route: Any = None) -> tuple[dict[str, Any], dict[str, Raw]]:
    """Run every critic independently (in parallel) and evaluate. Returns (result, raw answers)."""
    qs = questions(g, tax)
    done = await asyncio.gather(*(run_critic(n, s, image, qs, meter) for n, s in critics.items()))
    raws = dict(done)
    return evaluate(raws, g, tax, route, qs), raws


def critics_for(spark: Any) -> dict[str, Any]:
    """The two independent critics: Spark Open (Baseten) and Meta Spark 1.3. Without Baseten, or in mock mode, the
    same adapter answers twice (logged by name)."""
    meta = getattr(spark, "meta", None)
    baseten = getattr(spark, "baseten", None)
    if meta is not None and baseten is not None:
        return {"spark_open": baseten, "meta_spark": meta}
    if meta is not None:
        return {"meta_spark": meta}
    return {"critic_a": spark, "critic_b": spark}
