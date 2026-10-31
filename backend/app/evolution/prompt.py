"""Section 4.6: compile the render prompt from the plan, by code.

Order: silhouette sentence and host frame first (RC-R6-01, RC-R7-06), then the head
(RC-R6-03, RC-R6-04), donor contributions at their planned strengths (RC-R6-02,
RC-R6-05), pattern flow (RC-R7-07), symmetry (RC-R6-07), the visible habitat trait
(RC-R4-11), and one creature on a plain background. Franchise names never appear
(RC-R7-10). Muse Spark may polish the text afterwards; `accept_polish` decides
whether its version is kept.
"""

from __future__ import annotations

import re

from app.evolution.data import Taxonomy, config
from app.evolution.genome import Genome

PROMPT_CARDS = ["RC-R6-01", "RC-R7-06", "RC-R6-03", "RC-R6-04", "RC-R6-02", "RC-R6-05", "RC-R7-07", "RC-R6-07",
                "RC-R4-11", "RC-R7-10"]


def _name(tax: Taxonomy, animal_id: str | None) -> str:
    return tax.animals[animal_id].common_name.lower() if animal_id else "neither parent"


def _regions(regs: list[str] | None) -> str:
    regs = list(regs or [])
    return regs[0] if len(regs) == 1 else ", ".join(regs[:-1]) + " and " + regs[-1]


def strip_franchise(text: str) -> str:
    for name in config()["franchise_blocklist"]:
        text = re.sub(re.escape(name), "", text, flags=re.IGNORECASE)
    return re.sub(r"  +", " ", text)


def has_franchise(text: str) -> bool:
    return any(n.lower() in text.lower() for n in config()["franchise_blocklist"])


def compile_prompt(g: Genome, tax: Taxonomy) -> str:
    a, b = _name(tax, g.parents.sire), _name(tax, g.parents.dam)
    t, lp = g.traits, g.limb_plan
    lines: list[str] = []
    sil = g.silhouette.strip().rstrip(".")
    lines.append(f"Silhouette: {sil[0].upper()}{sil[1:]}.")
    if g.host:
        lines.append(f"Host frame: the {_name(tax, g.host)} sets the outline, body size and overall frame.")
    else:
        lines.append(f"Body frame: an in-between blend of the {a} and the {b}.")
    lines.append(f"A single creature that combines a {a} and a {b}.")

    head = t["head"]
    head_from = (_name(tax, head.donor) if isinstance(head.donor, str)
                 else f"a blend of the {a} and the {b}")
    lines.append(f"Head of the {head_from}, fully visible and uncluttered, with clear, discernible eyes.")

    contrib: list[str] = []
    for tag, tr in t.items():
        if tr.op == "PATCH" and tag == "coat_texture":
            contrib.append(f"{_name(tax, tr.donor)} {tax.animals[tr.donor].covering or 'surface'} in a few large patches "  # type: ignore[index]
                           f"over the {_regions(tr.region)}, at full strength with clean edges, color and surface "
                           f"unchanged inside each patch; {_name(tax, g.host)} coat everywhere else")
        elif tr.op == "OVERLAY":
            pct = int(round((tr.strength or 0) * 100))
            contrib.append(f"faint {_name(tax, tr.donor)} {tag.replace('coat_', '')} at about {pct} percent strength "
                           f"on the {_regions(tr.region)}")
        elif tr.part:
            contrib.append(f"{_name(tax, tr.donor)} {tr.part} in place of the {tag}")
        if tr.donor is None and "gated" in tr.flags:
            continue  # an absent, gated feature is left out rather than named (naming it could invite it)
        if tr.note and tr.op != "PATCH" and tag not in ("size",) and "host value" not in tr.note:
            contrib.append(f"{tag.replace('_', ' ')}: {tr.note}")
    if lp.extra_wings:
        contrib.append(f"four legs plus a separate pair of {_name(tax, lp.extra_wings.donor)} wings on the shoulders")
    elif lp.forelimbs.kind == "wings" and lp.forelimbs.donor and lp.forelimbs.donor != g.host:
        contrib.append(f"{_name(tax, lp.forelimbs.donor)} wings in place of the forelegs, standing on two hind legs")
    if lp.has_wings():
        contrib.append({"powered": "wings sized for flight", "borderline": "large wings, flight looks effortful",
                        "gliding_or_display": "wings held for display or gliding, not powered flight",
                        "none": ""}[lp.wing_use])
    if contrib:
        lines.append("Details: " + "; ".join(c for c in contrib if c) + ".")
    lines.append("Pattern lines and texture flow follow the body outline.")
    lines.append("Bilaterally symmetrical, recognizable limbs, visible sense organs.")
    if g.habitat.visible_trait:
        lines.append(f"Habitat cue ({g.habitat.name}): {g.habitat.visible_trait}.")
    lines.append("One creature, full body, side three-quarter view, plain light background, natural history illustration.")
    return strip_franchise(" ".join(lines))


def accept_polish(original: str, polished: str | None) -> str:
    """Keep Muse Spark's light polish only if the silhouette sentence still leads and nothing banned crept in."""
    if not polished or has_franchise(polished):
        return original
    first = original.split(". ")[0]
    if not polished.startswith(first):
        return original
    if len(polished) > len(original) * 1.5:
        return original
    return polished
