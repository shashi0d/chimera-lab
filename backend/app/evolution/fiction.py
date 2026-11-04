"""Section 4.5c: the fiction budget (R9 section 3; RC-R9-10, RC-R9-11).

A license is a declared exception to a named card that R9 3.2 lists as bendable (evo_config `bendable`).
It always carries a compensation, written into the plan and the render prompt. Budget per design mode:
realistic 0, speculative 1, mythic 3 (evo_config `fiction_budget`). Needs beyond the budget are repaired
where a repair exists, otherwise labeled; licenses go first to needs that cannot be repaired. The honesty
rules and the believability floor (evo_config `never_licensable`) can never be licensed, in any mode.
"""

from __future__ import annotations

from typing import Any

from app.evolution.audit import Need, _label, _note
from app.evolution.data import Taxonomy, config
from app.evolution.genome import Genome, License
from app.evolution.physics import LABEL_SIX, locked_tags

LABEL_LAND_GILLS = "speculative: gills on a land creature (gills collapse in air)"


def bendable() -> dict[str, dict[str, Any]]:
    return {b["id"]: b for b in config()["bendable"]}


def never_licensable() -> set[str]:
    nl = config()["never_licensable"]
    return set(nl["honesty"]) | set(nl["floor"])


def budget(mode: str) -> int:
    return int(config()["fiction_budget"][mode])


def make_license(need_id: str, reason: str, compensation: str | None = None) -> License:
    """The only way a license is made. Refuses anything R9 3.2 does not list, and every honesty or floor rule.
    S2: an agent's `add_license` may word the compensation itself; otherwise the data's wording is used."""
    spec = bendable().get(need_id)
    if spec is None:
        raise ValueError(f"{need_id!r} is not a bendable rule (R9 3.2)")
    if spec["card"] in never_licensable():
        raise ValueError(f"{spec['card']} is an honesty or believability-floor rule and can never be licensed")
    return License(id=need_id, card=spec["card"], rule=spec["rule"],
                   compensation=(compensation or spec["compensation"]).strip(), reason=reason)


RESPIRATORY_WORDS = ("breathing opening", "spiracle", "gill slit", "gill opening", "breathing hole", "air hole")


def _arthropod_donor(g: Genome, tax: Taxonomy) -> Any:
    """The parent whose arthropod parts the license covers: the non-host arthropod parent (or either one)."""
    ids = [p for p in (g.parents.sire, g.parents.dam) if tax.animals[p].group == "arthropod"]
    non_host = [p for p in ids if p != g.host]
    pick = (non_host or ids or [None])[0]
    return tax.animals[pick] if pick else None


def visible_breathing(donor: Any) -> str | None:
    """S3c: the outside sign of the donor's own breathing organ (evo_config visible_breathing), or None."""
    return (config().get("visible_breathing") or {}).get((donor.breathing or "").strip().lower()) if donor else None


def trait_compensation(need_id: str, g: Genome, tax: Taxonomy) -> tuple[str, str]:
    """S3c: (compensation, where its clauses came from). A license's compensation is built from the donor's own
    resolved traits, never from its phylum: the respiratory clause is added only when the donor's breathing trait
    has an outside sign (tracheae: spiracles; a crab's gills sit under the carapace, so nothing)."""
    spec = bendable()[need_id]
    base = spec["compensation"]
    if spec.get("compensation_from_traits") != "breathing":
        return base, "evo_config.json bendable"
    donor = _arthropod_donor(g, tax)
    if donor is None:
        return base, "evo_config.json bendable (no arthropod donor)"
    src = donor.source_of("breathing")
    clause = visible_breathing(donor)
    name = donor.common_name.lower()
    if clause:
        return f"{base} and {clause}", f"respiratory clause from the {name}'s breathing ({donor.breathing}; {src})"
    return base, (f"no respiratory clause: the {name} breathes with {donor.breathing or 'an unrecorded organ'} "
                  f"({src}), which shows nothing on the outside")


def respiratory_claim_error(text: str, g: Genome, tax: Taxonomy) -> str | None:
    """S3c: an agent's compensation may name a visible breathing organ only if the donor's own trait has one."""
    low = (text or "").lower()
    if not any(w in low for w in RESPIRATORY_WORDS):
        return None
    donor = _arthropod_donor(g, tax) or (tax.animals[g.other(g.host)] if g.host else None)
    if donor is not None and visible_breathing(donor):
        return None
    what = f"{donor.common_name} breathes with {donor.breathing or 'an unrecorded organ'}" if donor else "no donor"
    return f"the compensation names a visible breathing opening, but the {what} ({donor.source_of('breathing') if donor else ''})"


def check_licensable(card: str) -> bool:
    return card not in never_licensable() and any(b["card"] == card for b in bendable().values())


def _compensate(g: Genome, lic: License, locked: frozenset[str]) -> None:
    """Write the compensation into the plan (the prompt reads g.licenses too)."""
    _note(g, "body", lic.compensation, locked, visual=False)  # the prompt shows it via license_clause
    if "leg" in lic.compensation or "tentacle" in lic.compensation:
        _note(g, "limbs", lic.compensation, locked, visual=False)


def _repair(g: Genome, need: Need, locked: frozenset[str]) -> str | None:
    """Repair a need without a license. None when no repair exists (it stays labeled)."""
    if not bendable()[need.id]["repairable"]:
        return None
    lp = g.limb_plan
    if need.id == "six_limbs" and lp.extra_wings:
        lp.forelimbs, lp.extra_wings = lp.extra_wings, None
        g.labels = [x for x in g.labels if x != LABEL_SIX]
        return "over budget: the wings take the forelimb slot instead (four limbs)"
    if need.id == "insect_wings":  # S2 (E4c): over budget, the insect wings are dropped
        from app.evolution.audit import _drop

        part = need.detail.removesuffix(" on a vertebrate body")
        if part in lp.appendages:
            lp.appendages.remove(part)
        _drop(g, part, locked)
        return "over budget: the insect wings are dropped (all four legs stay)"
    if need.id == "land_gills":
        _note(g, "body", "lungs assumed; gills reduced to small vestigial slits", locked)
        g.labels = [x for x in g.labels if x != LABEL_LAND_GILLS]
        return "lungs assumed; gills reduced to vestigial slits"
    return None


def _set_audit(g: Genome, function: str, result: str, extra: str, cards: list[str]) -> None:
    for i, item in enumerate(g.audit):
        if item.function == function:
            g.audit[i] = item.model_copy(update={"result": result, "detail": f"{item.detail}; {extra}",
                                                 "cards": list(dict.fromkeys([*item.cards, *cards]))})


def settle(g: Genome, needs: list[Need], tax: Taxonomy, requests: list[tuple[str, str]] | None = None) -> list[str]:
    """Grant licenses up to the mode's budget, repair the rest where possible, label what is left.
    S2: `requests` [(bendable id, compensation)] are an agent's add_license calls; they take the budget first,
    in order, with the agent's compensation wording. Unrequested needs follow (unrepairable first)."""
    locked = locked_tags(g, tax)
    g.licenses = []
    spec = bendable()
    order = list(spec)
    asked = {rid: comp for rid, comp in requests or []}
    first = [rid for rid, _c in requests or []]
    ranked = sorted(needs, key=lambda n: (n.id not in asked, first.index(n.id) if n.id in asked else 0,
                                          spec[n.id]["repairable"], order.index(n.id)))
    allowed = budget(g.design_mode)
    cards: list[str] = ["RC-R9-10"]
    for n, need in enumerate(ranked):
        card = spec[need.id]["card"]
        if n < allowed:
            comp, why = (asked[need.id], "the agent's wording") if asked.get(need.id) else trait_compensation(
                need.id, g, tax)
            lic = make_license(need.id, f"{need.detail}; compensation: {why}", comp)
            g.licenses.append(lic)
            _compensate(g, lic, locked)
            _set_audit(g, need.function, "licensed", f"licensed: {lic.rule}, shown with {lic.compensation}",
                       [card, "RC-R9-10"])
            continue
        fixed = _repair(g, need, locked)
        if fixed:
            _set_audit(g, need.function, "repaired", fixed, [card, "RC-R9-10"])
        else:
            if need.id == "land_gills":
                _label(g, LABEL_LAND_GILLS)
            _set_audit(g, need.function, "labeled",
                       f"not repairable and over the {g.design_mode} budget of {allowed}: labeled speculative",
                       [card, "RC-R9-10"])
    if g.design_mode == "mythic" and g.licenses:
        n = len(g.licenses)
        _label(g, f"mythic composite with {n} declared license{'s' if n > 1 else ''}: believability drops with "
                  "each extra license")
        cards.append("RC-R9-11")
    return cards

