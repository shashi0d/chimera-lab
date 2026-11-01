"""S2 part 6: inspect a render against its plan, and fix a structural miss with one plan-worded edit turn.

inspect = SAM presence checks for each planned structural part + the checklist critic for absences, third
animals and separate bodies (ROADMAP 5b):

- Presence ("<donor> wings in place of the front legs", "a curved horn ... on the brow"): passes when the critic
  says yes, or when SAM 3.1 finds the named part (S1: SAM finds named parts reliably). A critic "no" with no SAM
  mask fails.
- Absence ("no wings"), the frame, license compensations and "no whole donor animals on the body": the critic
  decides. An empty SAM mask alone never counts as proof that a part is absent (S1: SAM missed five beetle
  bodies), so SAM never fails an item on its own.
- Count and third animals: from the same checklist call (creatures, animals).

A structural failure gets one Muse Image edit turn (previous_response_id), worded from the plan item ("show the
planned ... as ..."), never from the symptom (S1: "remove the beetle bodies" also removed the planned chitin
plates). Then the image is inspected again; if it still fails, it is kept with a warning.
"""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass
from typing import Any

from PIL import Image

from app.evolution.audit import DROPPED
from app.evolution.data import Taxonomy
from app.evolution.genome import Genome
from app.evolution.parts import dorsal_wings, match, part_owner, surface, wing_spec

PRESENT_FILL = 0.002  # a mask covering at least 0.2 percent of the frame counts as found


@dataclass
class Item:
    text: str  # the yes/no checklist line the critic answers
    kind: str  # frame | head | compensation | absent | part | one_body | surface | pattern | pad
    structural: bool
    sam: str | None = None  # SAM prompt confirming presence (presence items only)
    fix: str = ""  # the edit instruction, worded from the plan item


def _name(tax: Taxonomy, aid: str | None) -> str:
    return tax.animals[aid].common_name.lower() if aid else ""


def _regions(regs: list[str] | None) -> str:
    regs = list(regs or [])
    return regs[0] if len(regs) == 1 else ", ".join(regs[:-1]) + " and " + regs[-1] if regs else "body"


def plan_items(g: Genome, tax: Taxonomy) -> list[Item]:
    """Every visible claim of the plan as a checklist item, structural ones first (frame, head, licenses,
    absences, donor parts, one body), then surface and pattern."""
    host = _name(tax, g.host) if g.host else None
    a, b = _name(tax, g.parents.sire), _name(tax, g.parents.dam)
    lp, t = g.limb_plan, g.traits
    did = g.other(g.host) if g.host else None
    donor = tax.animals[did] if did else None
    items: list[Item] = []
    keep = "keep everything else the same"
    if host:
        items.append(Item(f"a {host} body shape", "frame", True,
                          fix=f"Show the planned {host} body shape and outline; {keep}."))
    else:
        items.append(Item(f"an in-between body of a {a} and a {b}", "frame", True,
                          fix=f"Show the planned in-between body of the {a} and the {b}; {keep}."))
    head = t["head"].donor if isinstance(t["head"].donor, str) else None
    hname = _name(tax, head) if head else None
    items.append(Item(f"a {hname} head with visible eyes" if hname else "one clear head with visible eyes", "head",
                      True, sam=f"{hname} head" if hname and head != g.host else None,
                      fix=f"Show the planned {hname or 'single'} head, fully visible with clear eyes; {keep}."))
    for lic in g.licenses:
        items.append(Item(lic.compensation, "compensation", True,
                          fix=f"Show {lic.compensation}, as planned; {keep}."))
    for flag in g.traits["body"].flags:
        if flag.startswith(DROPPED):
            key = flag[len(DROPPED):]
            where = f"the {host}'s own body" if host else "the body"
            items.append(Item(f"no {key}", "absent", True,
                              fix=f"The plan has no {key}: show {where} there instead; {keep}."))
    if lp.extra_wings and lp.extra_wings.donor:
        items.append(Item(f"four legs plus a separate pair of {_name(tax, lp.extra_wings.donor)} wings", "part", True,
                          sam="wings", fix=f"Show the planned four legs plus a separate pair of "
                          f"{_name(tax, lp.extra_wings.donor)} wings rooted in heavy shoulders; {keep}."))
    elif lp.forelimbs.kind == "wings" and lp.forelimbs.donor and lp.forelimbs.donor != g.host:
        wn = _name(tax, lp.forelimbs.donor)
        items.append(Item(f"{wn} wings in place of the front legs", "part", True, sam="wings",
                          fix=f"Show the planned {wn} wings in place of the front legs, standing on two hind legs; "
                              f"{keep}."))
    for part in dorsal_wings(g, tax):
        owner = part_owner(g, tax, part)
        s = wing_spec(owner) if owner else None
        shape = s.shape if s else "a pair of insect wings"
        items.append(Item(f"{shape} on the back, with four legs", "part", True, sam="wings",
                          fix=f"Show the planned {shape} rising from a raised, plated mount between the shoulder "
                              f"blades, with all four legs kept; {keep}."))
    for tag, tr in t.items():
        if tr.part and isinstance(tr.donor, str) and tr.donor != g.host:
            s = match(tax.animals[tr.donor], tr.part)
            shape = s.shape if s else f"{_name(tax, tr.donor)} {tr.part}"
            items.append(Item(f"{shape} in place of the {tag}", "part", True, sam=(s.part if s else tr.part),
                              fix=f"Show the planned {shape} in place of the {tag}; {keep}."))
    for app_ in lp.appendages:
        if app_.endswith(")") or app_ in dorsal_wings(g, tax):
            continue
        owner = part_owner(g, tax, app_)
        s = match(owner, app_) if owner else None
        shape = s.shape if s else app_
        items.append(Item(shape, "part", True, sam=(s.part if s else app_),
                          fix=f"Show the planned {shape}, on the {host or 'creature'}'s own body; {keep}."))
    tex = t["coat_texture"]
    if donor and host and tex.op == "PATCH" and tex.donor == did:
        dn = _name(tax, did)
        items.append(Item(f"only parts and materials of the {dn}, no whole {dn} animals on the body", "one_body", True,
                          fix=f"Show the planned {dn} contribution only as {surface(donor)} on the {host}'s own body "
                              f"over the {_regions(tex.region)}, not as separate animals; {keep}."))
        items.append(Item(f"{surface(donor)} patches on the {_regions(tex.region)}", "surface", False))
    pat = t["coat_pattern"]
    if pat.op == "OVERLAY" and isinstance(pat.donor, str):
        items.append(Item(f"faint {_name(tax, pat.donor)}-type markings on the {_regions(pat.region)}", "pattern",
                          False))
    elif "plain" in pat.flags:
        items.append(Item("plain coat with no stripes or spots", "pattern", False))
    return _dedupe(items)


def _dedupe(items: list[Item]) -> list[Item]:
    seen, out = set(), []
    for i in items:
        if i.text not in seen:
            seen.add(i.text)
            out.append(i)
    return out


def _fill(mask_png: bytes) -> float:
    with Image.open(io.BytesIO(mask_png)) as im:
        g = im.convert("L").resize((128, 128))
        px = g.tobytes()
    return sum(1 for p in px if p > 127) / len(px)


async def inspect(image: bytes, g: Genome, tax: Taxonomy, items: list[Item], critic: dict[str, Any],
                  third: list[str], seg: Any, meter: Any) -> dict[str, Any]:
    """Judge each structural item from the critic's answers (by order) plus SAM presence checks. `critic` is the
    full-image checklist answer the judge already made for the same items; SAM runs once per presence item."""
    answers = {a["item"]: a["answer"] for a in critic.get("answers") or [] if isinstance(a, dict)}
    rows: list[dict[str, Any]] = []
    for it in items:
        ans = answers.get(it.text, "unclear")
        found: bool | None = None
        fill = None
        if it.sam:
            mask = await meter.call("sam", "inspect", seg.segment(image, it.sam))
            fill = round(_fill(mask), 4)
            found = fill >= PRESENT_FILL
        if not it.structural:
            status = "info"
        elif it.kind in ("part", "head") and found:
            status = "pass"  # SAM confirms presence even if the critic missed it
        elif ans == "yes":
            status = "pass"
        elif ans == "no":
            status = "fail"  # an empty mask never decides on its own; the critic's "no" does
        else:
            status = "unclear"
        rows.append({**asdict(it), "answer": ans, "sam_found": found, "sam_fill": fill, "status": status})
    creatures = int(critic.get("creatures") or 0)
    if creatures > 1:
        host = _name(tax, g.host) if g.host else "the planned body"
        rows.append({"text": "one creature", "kind": "count", "structural": True, "sam": None, "answer": str(creatures),
                     "sam_found": None, "sam_fill": None, "status": "fail",
                     "fix": f"Show one single creature: the {host} with only its planned parts; keep everything else "
                            "the same."})
    if third:
        parts = "; ".join(i.text for i in items if i.kind in ("frame", "head", "part", "surface"))
        rows.append({"text": "only the two parents' features", "kind": "third_animal", "structural": True, "sam": None,
                     "answer": ", ".join(third), "sam_found": None, "sam_fill": None, "status": "fail",
                     "fix": f"Show the creature exactly as planned: {parts}; keep the pose and everything else the "
                            "same."})
    failures = [r for r in rows if r["status"] == "fail"]
    return {"items": rows, "failures": failures, "structural_failures": len(failures),
            "sam_calls": sum(1 for it in items if it.sam)}


def edit_instruction(failures: list[dict[str, Any]], limit: int = 3) -> str:
    """One edit turn for every failed structural item (at most `limit`), each worded from its plan item."""
    fixes = list(dict.fromkeys(f["fix"] for f in failures if f.get("fix")))[:limit]
    return " ".join(fixes)
