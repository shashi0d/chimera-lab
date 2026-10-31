"""Section 4.6: compile the render prompt from the plan, by code.

Order: silhouette sentence and host frame first (RC-R6-01, RC-R7-06), then the head
(RC-R6-03, RC-R6-04), donor contributions at their planned strengths (RC-R6-02,
RC-R6-05), pattern flow (RC-R7-07), symmetry (RC-R6-07), the visible habitat trait
(RC-R4-11), and one creature on a plain background. Franchise names never appear
(RC-R7-10). Muse Spark may polish the text afterwards; `check_polish` decides
whether its version is kept.

E2b (third-animal leakage): a pattern is only ever named as "<donor>-type <type>"
from the parents' own data, or as "plain coat, no stripes or spots". Plan notes that
mention patterns, or contradict the limb plan or mane, are left out.

E2c (real-hybrid route): a documented hybrid is a known animal, so its prompt opens with
the hybrid's name and cross, describes the frame in host terms in full, then names the
other parent once in one grouped clause of features. No habitat cue (D-056).
"""

from __future__ import annotations

import re

from app.evolution.data import PLAIN_COAT, Taxonomy, config, pattern_phrase
from app.evolution.genome import Genome
from app.evolution.route import find_known_pair, is_real_hybrid

PROMPT_CARDS = ["RC-R6-01", "RC-R7-06", "RC-R6-03", "RC-R6-04", "RC-R6-02", "RC-R6-05", "RC-R7-07", "RC-R6-07",
                "RC-R4-11", "RC-R7-10"]

BARE_PATTERN = re.compile(r"\b(patterns?|patterned|markings?)\b", re.IGNORECASE)
PATTERN_WORDS = re.compile(r"\b(patterns?|patterned|markings?|stripes?|striped|spots?|spotted|rosettes?|blotch\w*|"
                           r"bands?|banded|barring|zebra\w*|leopard\w*)\b", re.IGNORECASE)


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


# ------------------------------------------------------------------ patterns (E2b)


def _pattern_parts(g: Genome, tax: Taxonomy) -> list[tuple[str, str]]:
    """(donor-type phrase, where) for every pattern the plan really carries."""
    t = g.traits["coat_pattern"]
    parts: list[tuple[str, str]] = []
    if isinstance(t.donor, str) and (ph := pattern_phrase(_name(tax, t.donor), t.donor)):
        if t.op == "OVERLAY":
            pct = int(round((t.strength or 0) * 100))
            parts.append((ph, f"at about {pct} percent strength on the {_regions(t.region)}"))
        elif t.op == "PATCH":
            parts.append((ph, f"only inside the {_name(tax, t.donor)} patches"))
        else:
            parts.append((ph, "across the coat"))
    if t.op == "PATCH" and g.host and (ph := pattern_phrase(_name(tax, g.host), g.host)):
        parts.append((ph, f"on the {_name(tax, g.host)} coat elsewhere"))
    return parts


def pattern_clause(g: Genome, tax: Taxonomy) -> str:
    """The only place a pattern is named: donor plus type, or the plain-coat sentence."""
    parts = _pattern_parts(g, tax)
    if not parts:
        return PLAIN_COAT
    t = g.traits["coat_pattern"]
    faint = t.op == "OVERLAY" and (t.strength or 0) <= 0.5
    return "; ".join(f"{'faint ' if faint and i == 0 else ''}{ph} {where}" for i, (ph, where) in enumerate(parts))


def plan_conflicts(text: str, g: Genome) -> list[str]:
    """Statements in `text` that contradict the plan's limb plan or mane."""
    low = text.lower()
    lp, out = g.limb_plan, []
    wings = lp.has_wings()
    if wings and re.search(r"\b(four|4) (\w+ )?(legs|legged)\b|\bfour-legged\b|\bno (forelimb-to-wing|wings?)\b|\bwingless\b",
                           low) and not lp.extra_wings:
        out.append("four legs or no wings, but the limb plan has wings in the forelimb slot")
    if not wings and re.search(r"\bwings?\b", low) and not re.search(r"\bno wings?\b|\bwingless\b", low):
        out.append("wings, but the limb plan has none")
    tentacles = any("tentacle" in a for a in lp.appendages) or any(t.part == "tentacles" for t in g.traits.values())
    if not tentacles and re.search(r"\btentacles?\b", low):
        out.append("tentacles, but the plan has none")
    mane = g.traits["mane"].donor is not None
    says_none = re.search(r"\bmaneless\b|\bwithout (a )?mane\b|\bno mane\b|\bmane (is )?(absent|gated)", low)
    if not mane and re.search(r"\bmanes?\b", low) and not says_none:
        out.append("a mane, but the mane is absent")
    if mane and says_none and not re.search(r"\bor no mane\b|\breduced mane\b", low):
        out.append("no mane, but the plan has one")
    return out


# ------------------------------------------------------------------ compile


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _cap(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def hybrid_opener(g: Genome, tax: Taxonomy) -> str:
    """'A mule (donkey sire x horse mare), a real hybrid animal.'"""
    a, b = _name(tax, g.parents.sire), _name(tax, g.parents.dam)
    pair = find_known_pair(tax.animals[g.parents.sire], tax.animals[g.parents.dam])
    spec = (pair or {}).get("prompt") or {}
    cross = spec.get("cross") or f"{a} sire x {b} dam"
    name = pair["name"] if pair else f"{a} x {b} hybrid"
    article = "An" if name[0] in "aeiou" else "A"
    return f"{article} {name} ({cross}), a real hybrid animal."


def compile_real_hybrid(g: Genome, tax: Taxonomy) -> str:
    """Real-hybrid route (E2c): name and cross, frame in host terms, donor features grouped and named once."""
    a, b = _name(tax, g.parents.sire), _name(tax, g.parents.dam)
    pair = find_known_pair(tax.animals[g.parents.sire], tax.animals[g.parents.dam])
    spec = (pair or {}).get("prompt") or {}
    host = _name(tax, g.host) if g.host else None
    if spec.get("frame"):
        frame = spec["frame"].replace("{host}", host or "parent")
    elif host:
        frame = f"{host}-sized body, {host} proportions"
    else:
        frame = f"in-between body of the {a} and the {b}, a blend of both parents' proportions"
    features = list(spec.get("donor_features") or [])
    donor = g.other(g.host) if g.host else None
    body = _cap(frame)
    if features and donor:
        body += f", with the {_name(tax, donor)}'s {_join(features)}"
    lines = [hybrid_opener(g, tax), f"{body}; {pattern_clause(g, tax)}.", *([license_clause(g)] if g.licenses else []),
             "Head fully visible and uncluttered, with clear, discernible eyes.",
             "Bilaterally symmetrical, recognizable limbs, visible sense organs.", prosaic_line(),
             "One creature, full body, side three-quarter view, plain light background, natural history illustration."]
    return strip_franchise(" ".join(lines))


def prosaic_line() -> str:
    """R9 section 4 (RC-R9-15): ordinary detail in every mode, so the one impossible element is believable."""
    return f"Prosaic detail: {config()['prosaic_detail']}."


def license_clause(g: Genome) -> str:
    """E4 (4.5c): each declared license is shown with its compensation."""
    return "Declared fiction: " + "; ".join(f"{lic.rule}, shown with {lic.compensation}" for lic in g.licenses) + "."


def compile_prompt(g: Genome, tax: Taxonomy) -> str:
    if is_real_hybrid(g):
        return compile_real_hybrid(g, tax)
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
        if tag == "coat_pattern":
            continue  # compiled by code only (pattern_clause)
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
        note = tr.note or ""
        if PATTERN_WORDS.search(note) or plan_conflicts(note, g):
            continue  # patterns are named only by pattern_clause; a note never contradicts the plan
        if note and tr.op != "PATCH" and tag not in ("size",) and "host value" not in note:
            contrib.append(f"{tag.replace('_', ' ')}: {note}")
    contrib.append(pattern_clause(g, tax))
    for app_ in lp.appendages:
        if not app_.endswith("(tail)"):  # E4: e.g. donor external gills, kept as display frills outside realistic mode
            contrib.append(f"{app_}, small display frills" if "gills" in app_ else app_)
    if lp.extra_wings:
        contrib.append(f"four legs plus a separate pair of {_name(tax, lp.extra_wings.donor)} wings on the shoulders")
    elif lp.forelimbs.kind == "wings" and lp.forelimbs.donor and lp.forelimbs.donor != g.host:
        contrib.append(f"{_name(tax, lp.forelimbs.donor)} wings in place of the forelegs, standing on two hind legs")
    if lp.has_wings():
        contrib.append({"powered": "wings sized for flight", "borderline": "large wings, flight looks effortful",
                        "gliding_or_display": "wings held for display or gliding, not powered flight",
                        "none": ""}[lp.wing_use])
    lines.append("Details: " + "; ".join(c for c in contrib if c) + ".")
    parts = _pattern_parts(g, tax)
    lines.append(f"The {parts[0][0]} follow the body outline." if parts else "Coat texture flows along the body outline.")
    if g.licenses:
        lines.append(license_clause(g))
    lines.append("Bilaterally symmetrical, recognizable limbs, visible sense organs.")
    if g.habitat.visible_trait and not BARE_PATTERN.search(g.habitat.visible_trait):
        lines.append(f"Habitat cue ({g.habitat.name}): {g.habitat.visible_trait}.")
    lines.append(prosaic_line())
    lines.append("One creature, full body, side three-quarter view, plain light background, natural history illustration.")
    return strip_franchise(" ".join(lines))


# ------------------------------------------------------------------ polish check


def _other_animal_names(g: Genome, tax: Taxonomy) -> list[str]:
    """Common names (and their head words) of every animal in the data that is not a parent."""
    parents = {g.parents.sire, g.parents.dam}
    parent_words = {w for p in parents for w in tax.animals[p].common_name.lower().replace("-", " ").split()}
    names: set[str] = set()
    for a in tax.animals.values():
        if a.id in parents:
            continue
        full = a.common_name.lower()
        names.add(full)
        head = full.replace("-", " ").split()[-1]
        if head not in parent_words and len(head) > 2:
            names.add(head)
    return sorted(names, key=len, reverse=True)


def _mentions(text: str, name: str) -> bool:
    return re.search(rf"\b{re.escape(name)}s?\b", text, re.IGNORECASE) is not None


def added_animals(original: str, polished: str, g: Genome, tax: Taxonomy) -> list[str]:
    return [n for n in _other_animal_names(g, tax) if _mentions(polished, n) and not _mentions(original, n)]


def check_polish(original: str, polished: str | None, g: Genome, tax: Taxonomy) -> str | None:
    """None if Spark's polish can be used; otherwise why the compiled prompt is used instead."""
    if not polished:
        return "empty polish"
    if has_franchise(polished):
        return "franchise name"
    if not polished.startswith(original.split(". ")[0]):
        return "silhouette sentence changed"
    if len(polished) > len(original) * 1.5:
        return "too long"
    if extra := added_animals(original, polished, g, tax):
        return f"adds an animal that is not a parent: {', '.join(extra)}"
    if new := sorted(set(plan_conflicts(polished, g)) - set(plan_conflicts(original, g))):
        return f"contradicts the plan: {'; '.join(new)}"
    if len(BARE_PATTERN.findall(polished)) > len(BARE_PATTERN.findall(original)):
        return "adds a bare pattern or markings phrase"
    return None


def accept_polish(original: str, polished: str | None, g: Genome, tax: Taxonomy) -> tuple[str, str | None]:
    """(prompt to render, rejection reason or None). A rejected polish falls back to the compiled prompt."""
    reason = check_polish(original, polished, g, tax)
    return (original, reason) if reason else (polished or original, None)
