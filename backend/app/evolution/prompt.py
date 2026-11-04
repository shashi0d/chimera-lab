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
from typing import Any

from app.evolution.audit import dropped_parts
from app.evolution.data import PLAIN_COAT, Taxonomy, config, pattern_phrase
from app.evolution.genome import BEYOND, Genome
from app.evolution.parts import dorsal_wings, match, part_owner, surface, wing_spec
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
    for key in dropped_parts(g):  # E4: a part realistic mode dropped never comes back through a note
        stem = key.split()[-1].rstrip("s")
        if re.search(rf"\b{re.escape(stem)}s?\b", low):
            out.append(f"{key}, but the plan dropped them")
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


ZONE_WORDS = {"head": "crown of the head", "neck": "neck", "forequarters": "shoulders", "back": "back",
              "flanks": "flanks", "belly": "belly", "hindquarters": "hips", "legs": "legs", "tail": "tail"}


def _covering(g: Genome) -> Any:
    return next((t for t in g.transfers if t.kind == "covering"), None)


def _uncovered(g: Genome, cov: Any) -> list[str]:
    """Host zones the covering leaves to the host (the face always stays the host's, so its senses stay visible)."""
    return ["face"] + [ZONE_WORDS[z] for z in ZONE_WORDS if z not in cov.extent and z != "head"]


def covering_clause(g: Genome, tax: Taxonomy, cov: Any) -> str:
    """S3b default for a donor covering (RC-R10-12, 15, 16): the V2 replacement wording (the owner's best in S3a)
    built from the transfer record: material, extent, host-scaled plates and joints, conforming to the host's body.
    No donor-icon shape words (no elytra, shields or domes): the covering takes the host's shape."""
    host = _name(tax, g.host)
    cover = surface(tax.animals[g.host])
    if cov.host_shell:  # S3c (RC-R10-17): on a turtle host the covering grows on the skin, never over the shell
        from app.evolution.transfer import shell_host

        cover = (shell_host(tax.animals[g.host]) or {}).get("skin", "scaly skin")
    material = surface(tax.animals[cov.donor])
    where = _join([ZONE_WORDS[z] for z in cov.extent])
    if cov.form == "material_only":  # S5 (D1): the host's own covering stays; the donor gives its look only
        donor = _name(tax, cov.donor)
        return (f"the {host}'s own {cover} stays {cover} everywhere, and over the {where} it takes the {donor}'s "
                f"colors, gloss, surface texture and pattern; the {host}'s body outline is unchanged")
    kept = _join(_uncovered(g, cov) if not cov.host_shell else ["face"])
    verb = "keeps" if kept == "face" else "keep"
    stops = "stop" if cover.split(" with ")[0].endswith("s") else "stops"
    # S3c: a covering never changes a part's length or shape (a bear's short tail stays short when covered)
    outline = (f"; every covered part keeps the {host}'s own length and shape"
               + (f", and the tail stays the {host}'s own tail" if "tail" in cov.extent and not _donor_tail(g) else ""))
    shell = f"; {cov.host_shell}" if cov.host_shell else ""
    return (f"{material} in its own colors, grown from the skin as the {host}'s own covering over the {where}: it "
            f"replaces the {host}'s {cover} there and conforms to the {host}'s body, {cov.scale}{outline}; the {cover} "
            f"{stops} at the covering's edge, and the {kept} {verb} the {host}'s own {cover}{shell}")


def _donor_tail(g: Genome) -> bool:
    tail = g.traits.get("tail")
    return bool(tail and tail.part and tail.donor != g.host)


def part_phrase(g: Genome, tax: Taxonomy, t: Any, shape: str, place: str) -> str:
    """S3b: a discrete part from its transfer record. Homologous: its shape where the host has the matching
    structure, fitted to host size. Non-homologous: grown from its functional anchor, out of the donor covering
    when they connect, described by its identity cues."""
    host = _name(tax, g.host)
    cov = _covering(g)
    if t.cls == "homologous":
        return f"{shape}{place}, fitted to the {host}'s size"
    noun = t.feature if t.feature.endswith("s") else f"a {t.feature}"
    grown = f"{noun} grown from {t.anchor}"
    if cov is not None and cov.feature in t.connects and cov.form != "material_only":
        grown += ", out of the covering, which continues from there into the body covering"
    return f"{grown}: {t.identity_cues}" if t.identity_cues else grown


def donor_clause(g: Genome, tax: Taxonomy) -> str | None:
    """S2 (E4c): everything the non-host parent gives, in one grouped clause that names it once. Parts are
    described as materials and shapes on the host's own body (class_parts.json), so the image model draws parts,
    not whole donor animals ("beetle bodies on the shoulders" in E4)."""
    if g.host is None:
        return None
    did = g.other(g.host)
    d, t, lp = tax.animals[did], g.traits, g.limb_plan
    host = _name(tax, g.host)
    bits: list[str] = []
    if t["head"].donor == did:
        bits.append("its head, fully visible, with clear, discernible eyes")
    wing = wing_spec(d)
    wing_shape = wing.shape if wing else "its wings"
    if lp.forelimbs.kind == "wings" and lp.forelimbs.donor == did:
        bits.append(f"{wing_shape} in place of the forelegs, standing on two hind legs")
    if lp.extra_wings and lp.extra_wings.donor == did:
        bits.append(f"a separate pair of {wing_shape} rooted in heavy shoulders, four legs kept")
    for part in dorsal_wings(g, tax):
        s = match(d, part)
        bits.append(f"{s.shape if s else 'a pair of insect wings'} on a raised, plated mount between the shoulder "
                    "blades, all four legs kept")
    if lp.has_wings() or dorsal_wings(g, tax):
        use = "gliding_or_display" if dorsal_wings(g, tax) and not lp.has_wings() else lp.wing_use
        bits.append({"powered": "wings sized for flight", "borderline": "large wings, flight looks effortful",
                     "gliding_or_display": "wings held for display or gliding, not powered flight",
                     "none": ""}[use])
    tr_by = {x.feature: x for x in g.transfers if x.kind == "part"}
    for tag, tr in t.items():
        if tr.part and tr.donor == did:
            s = match(d, tr.part)
            shape, xf = (s.shape if s else tr.part), tr_by.get(s.part if s else tr.part)
            bits.append(part_phrase(g, tax, xf, shape, f" in place of the {tag}") if xf else f"{shape} in place of the {tag}")
    for app_ in lp.appendages:
        if app_.endswith(")") or app_ in dorsal_wings(g, tax) or part_owner(g, tax, app_) is not d:
            continue
        s = match(d, app_)
        shape = s.shape if s else app_[len(d.common_name) + 1:]
        xf = tr_by.get(s.part if s else app_)
        if s and "gill" in s.part:
            bits.append(f"{shape}, as small display frills")
        else:
            bits.append(part_phrase(g, tax, xf, shape, "") if xf else shape)
    tex = t["coat_texture"]
    cov = _covering(g)
    if cov is not None and cov.donor == did and cov.extent:
        bits.append(covering_clause(g, tax, cov))
        pat = t["coat_pattern"]
        if pat.op == "PATCH" and pat.donor == did and (ph := pattern_phrase(_name(tax, did), did)):
            bits.append(f"{ph} on the covering")
    elif tex.op == "PATCH" and tex.donor == did:
        bits.append(f"{surface(d)} in its own colors, in a few large patches over the {_regions(tex.region)}, with "
                    "clean edges, color and surface unchanged inside each patch")
        pat = t["coat_pattern"]
        if pat.op == "PATCH" and pat.donor == did and (ph := pattern_phrase(_name(tax, did), did)):
            bits.append(f"{ph} only inside those patches")  # E2b: a pattern is always "<donor>-type <type>"
    for tag, tr in t.items():
        if tr.op == "OVERLAY" and tr.donor == did and tag != "coat_pattern":
            pct = int(round((tr.strength or 0) * 100))
            bits.append(f"a faint {tag.replace('coat_', '')} at about {pct} percent strength on the {_regions(tr.region)}")
    bits = [b for b in bits if b]
    if not bits:
        return None
    return f"from the {_name(tax, did)}, as parts and materials on the {host}'s own body: " + "; ".join(bits)


def host_clause(g: Genome, tax: Taxonomy) -> str:
    """The host's own body, coat and any host pattern (S2: the donor is named only in donor_clause)."""
    host = _name(tax, g.host)
    did = g.other(g.host) if g.host else None
    pat = g.traits["coat_pattern"]
    own = pattern_phrase(host, g.host)
    skin = surface(tax.animals[g.host]) if g.host else "coat"
    cov = _covering(g)
    if cov is not None and cov.donor == did and cov.host_shell:  # S3c (RC-R10-17): the shell is skeleton, kept
        coat = "its own shell over the shoulders, back, flanks, belly and hips, and its own scaly skin on the face"
    elif cov is not None and cov.donor == did and cov.extent and cov.form == "material_only":  # S5 (D1)
        coat = f"its own {skin} over the whole body, colored as below"
    elif cov is not None and cov.donor == did and cov.extent:  # S3b: the donor covering takes the rest
        where = _join(_uncovered(g, cov))
        coat = f"its own {skin} with {own} on the {where}" if own else f"its own {skin} on the {where}, {PLAIN_COAT}"
    elif pat.op == "OVERLAY" and pat.donor == did and (ph := pattern_phrase(_name(tax, did), did)):
        pct = int(round((pat.strength or 0) * 100))
        coat = f"its own {skin} with a faint {ph} at about {pct} percent strength on the {_regions(pat.region)}"
    elif own:
        coat = f"its own {skin} with {own} everywhere outside the patches"
    else:
        coat = f"its own {skin} everywhere else, {PLAIN_COAT}"
    return f"{host} body and legs, with {coat}"


def compile_prompt(g: Genome, tax: Taxonomy) -> str:
    if is_real_hybrid(g):
        return compile_real_hybrid(g, tax)
    if g.host is not None:
        return compile_hosted(g, tax)
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
    contrib += beyond_details(g, tax)  # S2: structured fields only; trait notes never reach the prompt
    contrib.append(pattern_clause(g, tax))
    contrib += code_details(g)
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


def code_details(g: Genome) -> list[str]:
    """S2: the code-made visual details (render_details), minus anything that would contradict the plan.
    Trait notes, which a model plan may have written, are never read."""
    return [d for d in g.render_details if not PATTERN_WORDS.search(d) and not plan_conflicts(d, g)]


def beyond_details(g: Genome, tax: Taxonomy) -> list[str]:
    """Hybrid extremes from the structured BLEND value (RC-R1-13), not from a note."""
    out = []
    for tag, tr in g.traits.items():
        if tr.op == "BLEND" and BEYOND in tr.flags and isinstance(tr.donor, list) and tr.value is not None:
            past = tr.donor[0] if tr.value < 0 else tr.donor[1]
            out.append(f"{tag.replace('_', ' ')} slightly past the {_name(tax, past)}'s proportions, beyond both parents")
    return out


def compile_hosted(g: Genome, tax: Taxonomy) -> str:
    """Chimera and mythic plans (a host frame): silhouette, host, head, then the host clause and ONE grouped
    donor clause (S2, E4c), license compensations, the habitat cue and the fixed closing lines."""
    a, b = _name(tax, g.parents.sire), _name(tax, g.parents.dam)
    host = _name(tax, g.host)
    sil = g.silhouette.strip().rstrip(".")
    lines = [f"Silhouette: {_cap(sil)}.", f"Host frame: the {host} sets the outline, body size and overall frame.",
             f"A single creature that combines a {a} and a {b}."]
    head_from_host = g.traits["head"].donor == g.host
    lines.append(f"Head of the {host}, fully visible and uncluttered, with clear, discernible eyes." if head_from_host
                 else "Head fully visible and uncluttered, with clear, discernible eyes.")
    details = [host_clause(g, tax)]
    if group := donor_clause(g, tax):
        details.append(group)
    details += code_details(g)
    lines.append("Details: " + "; ".join(details) + ".")
    cov = _covering(g)
    if cov is not None and cov.extent and cov.form == "material_only":
        lines.append("The donor's colors and sheen follow the host's own coat and body shape.")
    elif cov is not None and cov.extent:
        joints = "joint" in cov.scale
        lines.append("The covering follows the body's own shape" + (" and bends at every joint." if joints else "."))
    else:
        lines.append("Coat texture and patches follow the body outline.")
    if g.licenses:
        lines.append(license_clause(g))
    lines.append("Bilaterally symmetrical, recognizable limbs, visible sense organs.")
    if g.habitat.visible_trait and not BARE_PATTERN.search(g.habitat.visible_trait):
        lines.append(f"Habitat cue ({g.habitat.name}): {g.habitat.visible_trait}.")
    lines.append(prosaic_line())
    lines.append("One creature, full body, side three-quarter view, plain light background, natural history illustration.")
    return strip_franchise(" ".join(lines))
