"""Rules from chimera_data.json run as Python checks (D1-02).

Which check a rule runs comes from the rule's own `check` field (sample schema)
or the explicit table in app/data/rule_map.py (real schema). Checks have a
phase:

* ``pair`` checks look at the two parents and run in this step;
* ``plan`` checks look at the fusion the planner chose (body plan + part donors)
  and run at the end of the compile step via ``evaluate(..., phase="plan")``.

Hits are warnings or info notes, never hard failures (v1). The step detail
always reports how many rules were mapped, run and left unmapped, so a data
file that maps nothing is visible instead of silently reporting 0.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from app.data.loader import ChimeraData, parse_range, split_list
from app.data.loader import field as row_field
from app.data.rule_map import RULE_CHECKS
from app.models.schemas import AnimalMatch, AnimalReading, FusionPlan, RealHybrid, RuleWarning
from app.pipeline.context import RunContext

log = logging.getLogger(__name__)

Side = tuple[AnimalReading, AnimalMatch | None]
Phase = Literal["pair", "plan"]
WATER = {"marine", "freshwater"}


@dataclass
class Fusion:
    """Traits the fusion inherits from the planner's donors (used by plan checks)."""

    body_plan: str
    covering: list[str]
    movement: list[str]
    habitat: list[str]
    climate: list[str]
    diet: list[str]


@dataclass
class RuleInput:
    a: Side
    b: Side
    fusion: Fusion | None = None
    hybrids: list[RealHybrid] = field(default_factory=list)
    allowed_body_plans: list[str] = field(default_factory=list)


# A check returns False/None (no hit), True (hit) or a string (hit, with a specific detail).
CheckFn = Callable[[RuleInput], bool | str | None]


@dataclass(frozen=True)
class Check:
    phase: Phase
    fn: CheckFn


# ------------------------------------------------------------------ helpers


def _fact(side: Side, key: str) -> str:
    reading, match = side
    if match and match.facts.get(key):
        return match.facts[key]
    if key == "body_plan":
        return reading.body_plan or ""
    return ""


def _set(side: Side, key: str) -> set[str]:
    return set(split_list(_fact(side, key)))


def _plan(side: Side) -> str:
    return _fact(side, "body_plan").lower()


def _name(side: Side) -> str:
    reading, match = side
    return (match.common_name if match else reading.common_name) or "a parent"


def _both(ri: RuleInput) -> tuple[Side, Side]:
    return ri.a, ri.b


def _union(ri: RuleInput, key: str) -> set[str]:
    return _set(ri.a, key) | _set(ri.b, key)


# ------------------------------------------------------------------ pair checks (two parents)


def body_plan_mismatch(a: Side, b: Side) -> bool:
    return bool(_plan(a) and _plan(b) and _plan(a) != _plan(b))


def limb_count_mismatch(a: Side, b: Side) -> bool:
    la, lb = _fact(a, "limb_count"), _fact(b, "limb_count")
    return bool(la and lb and la != lb)


def boneless_parent(a: Side, b: Side) -> bool:
    return any(_plan(s) == "cephalopod" or "no skeleton" in _fact(s, "notable_features") for s in (a, b))


def mass_ratio(a: Side, b: Side) -> bool:
    """Sample rule: parents more than 20x apart, comparing range bounds (never midpoints)."""
    ra, rb = parse_range(_fact(a, "body_mass_kg")), parse_range(_fact(b, "body_mass_kg"))
    if not ra or not rb:
        return False
    small, large = sorted([ra, rb], key=lambda r: r[1])
    return small[1] * 20 < large[0]


def mass_ratio_1000(a: Side, b: Side) -> str | None:
    """R-A2-03: larger parent's maximum / smaller parent's minimum above 1000x."""
    ra, rb = parse_range(_fact(a, "body_mass_kg")), parse_range(_fact(b, "body_mass_kg"))
    if not ra or not rb:
        return None
    (small_side, small), (large_side, large) = sorted([(a, ra), (b, rb)], key=lambda x: x[1][1])
    if small[0] <= 0:
        return None
    ratio = large[1] / small[0]
    if ratio > 1000:
        return (f"{_name(large_side)} {_fact(large_side, 'body_mass_kg')} kg vs {_name(small_side)} "
                f"{_fact(small_side, 'body_mass_kg')} kg: up to {ratio:,.0f}x")
    return None


def flight_mass(a: Side, b: Side) -> bool:
    flyer = any("flying" in split_list(_fact(s, "locomotion")) or "fly" in _set(s, "movement") for s in (a, b))
    heavy = any((r := parse_range(_fact(s, "body_mass_kg"))) and r[0] > 20 for s in (a, b))
    return bool(flyer and heavy)


def realm_conflict(a: Side, b: Side) -> str | bool:
    ra, rb = _fact(a, "realm"), _fact(b, "realm")
    if ra and rb:  # sample schema
        return ra != rb
    ha, hb = _set(a, "habitat"), _set(b, "habitat")
    if ha and hb:  # real schema: a marine-only parent with a land-only parent
        for marine, land in ((a, b), (b, a)):
            hm, hl = _set(marine, "habitat"), _set(land, "habitat")
            if hm == {"marine"} and not (hl & (WATER | {"wetland"})):
                return f"{_name(marine)} lives only in the sea; {_name(land)} only on land"
        return False
    aquatic = {"aquatic", "cephalopod", "finned"}
    return bool(_plan(a) and _plan(b)) and (_plan(a) in aquatic) != (_plan(b) in aquatic)


def covering_conflict(a: Side, b: Side) -> bool:
    ca, cb = _set(a, "covering"), _set(b, "covering")
    return bool(ca and cb and not ca & cb)


def class_distance(a: Side, b: Side) -> bool:
    ca, cb = _fact(a, "class"), _fact(b, "class")
    return bool(ca and cb and ca != cb)


def same_genus(a: Side, b: Side) -> bool:
    ga = (a[0].scientific_name or "").split(" ")[0]
    gb = (b[0].scientific_name or "").split(" ")[0]
    return bool(ga and ga == gb) and a[0].scientific_name != b[0].scientific_name


def diet_conflict(a: Side, b: Side) -> bool:
    """R-A6-02 (and the sample's diet rule): a meat-eater with a plant- or filter-feeder."""
    meat = {"carnivore", "piscivore"}
    plants = {"herbivore", "filter feeder"}
    da, db = _set(a, "diet"), _set(b, "diet")
    return bool((da & meat and db & plants) or (db & meat and da & plants))


def serpentine_with_quadruped(a: Side, b: Side) -> bool:
    return {_plan(a), _plan(b)} == {"serpentine", "quadruped"}


def shell_with_fur(a: Side, b: Side) -> bool:
    return bool(("shell" in _set(a, "covering") and "fur" in _set(b, "covering"))
                or ("shell" in _set(b, "covering") and "fur" in _set(a, "covering")))


def parents_same_species(a: Side, b: Side) -> str | None:
    ka, kb = _fact(a, "gbif_key"), _fact(b, "gbif_key")
    sa, sb = _fact(a, "scientific_name"), _fact(b, "scientific_name")
    if (ka and ka == kb) or (sa and sa == sb):
        return f"{_name(a)} and {_name(b)} resolve to the same species ({sa or ka})"
    return None


def fly_and_swim_parents(a: Side, b: Side) -> bool:
    return bool(("fly" in _set(a, "movement") and "swim" in _set(b, "movement"))
                or ("fly" in _set(b, "movement") and "swim" in _set(a, "movement")))


def walk_and_swim_parents(a: Side, b: Side) -> bool:
    for walker, swimmer in ((a, b), (b, a)):
        if "walk" in _set(walker, "movement") and "swim" in _set(swimmer, "movement") and "swim" not in _set(walker, "movement"):
            return True
    return False


def _active(side: Side) -> set[str]:
    return _set(side, "active_time") - {"unrecorded"}  # R-A4-P04: unrecorded adds nothing


def active_time_conflict(a: Side, b: Side) -> str | None:
    ta, tb = _active(a), _active(b)
    if ta and tb and not ta & tb:
        return f"{_name(a)} is {'/'.join(sorted(ta))}; {_name(b)} is {'/'.join(sorted(tb))}"
    return None


def active_time_unrecorded(a: Side, b: Side) -> str | None:
    unrec = [_name(s) for s in (a, b) if _set(s, "active_time") == {"unrecorded"}]
    if unrec:
        return f"active time unrecorded for {', '.join(unrec)}: it adds nothing and does not block the fusion"
    return None


def habitat_overlap(a: Side, b: Side) -> str | None:
    ha, hb = _set(a, "habitat"), _set(b, "habitat")
    if ha and hb and not ha & hb:
        return f"no shared habitat: {_name(a)} {'/'.join(sorted(ha))}; {_name(b)} {'/'.join(sorted(hb))}"
    return None


def climate_overlap(a: Side, b: Side) -> str | None:
    ca, cb = _set(a, "climate"), _set(b, "climate")
    if ca and cb and not ca & cb:
        return f"no shared climate: {_name(a)} {'/'.join(sorted(ca))}; {_name(b)} {'/'.join(sorted(cb))}"
    return None


def salinity_conflict(a: Side, b: Side) -> bool:
    for fresh, salt in ((a, b), (b, a)):
        hf, hs = _set(fresh, "habitat"), _set(salt, "habitat")
        if "freshwater" in hf and "marine" not in hf and "marine" in hs and "freshwater" not in hs:
            return True
    return False


def tundra_with_tropical(a: Side, b: Side) -> bool:
    return bool(("tundra" in _set(a, "habitat") and "tropical" in _set(b, "climate"))
                or ("tundra" in _set(b, "habitat") and "tropical" in _set(a, "climate")))


def wetland_parent(a: Side, b: Side) -> str | None:
    wet = [_name(s) for s in (a, b) if "wetland" in _set(s, "habitat")]
    return f"wetland parent: {', '.join(wet)}" if wet else None


def broad_climate_parent(a: Side, b: Side) -> str | None:
    broad = [_name(s) for s in (a, b) if {"temperate", "tropical", "polar"} <= _set(s, "climate")]
    return f"{', '.join(broad)} spans temperate, tropical and polar climates" if broad else None


def metabolic_rate_implausible(a: Side, b: Side) -> str | None:
    for s in (a, b):
        rate, mass = parse_range(_fact(s, "metabolic_rate_w")), parse_range(_fact(s, "body_mass_kg"))
        if rate and mass and rate[1] < 1 and mass[0] > 1:
            return f"{_name(s)}: {_fact(s, 'metabolic_rate_w')} W at {_fact(s, 'body_mass_kg')} kg is implausible"
    return None


def carnivore_piscivore_parent(a: Side, b: Side) -> str | None:
    both = [_name(s) for s in (a, b) if {"carnivore", "piscivore"} <= _set(s, "diet")]
    return f"{', '.join(both)} is carnivore and piscivore" if both else None


KEY_TRAITS = ("body_plan", "covering", "movement", "habitat", "climate", "diet")


def blank_parent_traits(a: Side, b: Side) -> str | None:
    gaps = []
    for s in (a, b):
        if s[1] is None:
            continue  # unmatched parents are reported by the match step
        missing = [k for k in KEY_TRAITS if not _fact(s, k)]
        if missing:
            gaps.append(f"{_name(s)}: {', '.join(missing)} unknown")
    return "; ".join(gaps) or None


def _pair(fn: Callable[[Side, Side], bool | str | None]) -> Check:
    return Check("pair", lambda ri: fn(ri.a, ri.b))


def real_hybrid_direction(ri: RuleInput) -> str | None:
    if not ri.hybrids:
        return None
    parts = [f"{h.name} ({h.cross or 'cross direction unknown'}; fertility {h.fertility or 'unknown'})" for h in ri.hybrids]
    return "documented real hybrid(s): " + "; ".join(parts) + ". This fusion does not inherit their fertility."


# ------------------------------------------------------------------ plan checks (the planned fusion)


def fusion_profile(a: Side, b: Side, plan: FusionPlan) -> Fusion:
    donors = plan.part_donors
    side = {"A": a, "B": b}
    movement = set(split_list(_fact(side[donors.limbs], "movement")))
    if "winged" in plan.body_plan:
        movement.add("fly")
    if plan.body_plan == "finned":
        movement.add("swim")
    diet = split_list(_fact(side[donors.head], "diet"))
    if diet_conflict(a, b):
        diet = ["omnivore"]  # R-A6-02: the default intermediate
    return Fusion(
        body_plan=plan.body_plan,
        covering=split_list(_fact(side[donors.covering], "covering")),
        movement=sorted(movement),
        habitat=split_list(_fact(side[donors.body], "habitat")),
        climate=split_list(_fact(side[donors.body], "climate")),
        diet=diet,
    )


def plan_body_plan_allowed(ri: RuleInput) -> str | None:
    f = ri.fusion
    if f and ri.allowed_body_plans and ("|" in f.body_plan or f.body_plan not in ri.allowed_body_plans):
        return f"planned body plan '{f.body_plan}' is not one of {', '.join(ri.allowed_body_plans)}"
    return None


def covering_from_donor(ri: RuleInput) -> str | None:
    f = ri.fusion
    extra = set(f.covering) - _union(ri, "covering") if f else set()
    return f"covering {', '.join(sorted(extra))} has no donor" if extra else None


def _plan_needs(feature: str, parent_key: str, parent_value: str) -> CheckFn:
    def check(ri: RuleInput) -> str | None:
        f = ri.fusion
        if not f:
            return None
        claimed = feature in f.body_plan if parent_key == "body_plan" else feature in getattr(f, _FUSION_FIELD[parent_key])
        if claimed and not any(parent_value in _fact(s, parent_key) for s in _both(ri)):
            return f"fusion claims {feature} but no parent has it"
        return None

    return check


_FUSION_FIELD = {"covering": "covering", "movement": "movement", "habitat": "habitat", "climate": "climate", "diet": "diet"}


def movement_has_donor(ri: RuleInput) -> str | None:
    f = ri.fusion
    extra = set(f.movement) - _union(ri, "movement") if f else set()
    return f"movement {', '.join(sorted(extra))} has no donor" if extra else None


def diet_from_donor(ri: RuleInput) -> str | None:
    f = ri.fusion
    if not f:
        return None
    extra = set(f.diet) - _union(ri, "diet") - ({"omnivore"} if diet_conflict(ri.a, ri.b) else set())
    return f"diet {', '.join(sorted(extra))} is not a parent's diet" if extra else None


CHECKS: dict[str, Check] = {
    # pair checks shared by both schemas
    **{f.__name__: _pair(f) for f in (
        body_plan_mismatch, limb_count_mismatch, boneless_parent, mass_ratio, mass_ratio_1000, flight_mass,
        realm_conflict, covering_conflict, class_distance, same_genus, diet_conflict, serpentine_with_quadruped,
        shell_with_fur, parents_same_species, fly_and_swim_parents, walk_and_swim_parents, active_time_conflict,
        active_time_unrecorded, habitat_overlap, climate_overlap, salinity_conflict, tundra_with_tropical,
        wetland_parent, broad_climate_parent, metabolic_rate_implausible, carnivore_piscivore_parent,
        blank_parent_traits,
    )},
    "real_hybrid_direction": Check("pair", real_hybrid_direction),
    # plan checks
    "plan_body_plan_allowed": Check("plan", plan_body_plan_allowed),
    "covering_from_donor": Check("plan", covering_from_donor),
    "winged_needs_winged_parent": Check("plan", _plan_needs("winged", "body_plan", "winged")),
    "finned_needs_finned_parent": Check("plan", _plan_needs("finned", "body_plan", "finned")),
    "serpentine_needs_serpentine_parent": Check("plan", _plan_needs("serpentine", "body_plan", "serpentine")),
    "shell_needs_shelled_parent": Check("plan", _plan_needs("shell", "covering", "shell")),
    "movement_has_donor": Check("plan", movement_has_donor),
    "fly_needs_flying_parent": Check("plan", _plan_needs("fly", "movement", "fly")),
    "swim_needs_swimming_parent": Check("plan", _plan_needs("swim", "movement", "swim")),
    "walk_needs_walking_parent": Check("plan", _plan_needs("walk", "movement", "walk")),
    "climb_needs_climbing_parent": Check("plan", _plan_needs("climb", "movement", "climb")),
    "burrow_needs_burrowing_parent": Check("plan", _plan_needs("burrow", "movement", "burrow")),
    "glide_needs_gliding_parent": Check("plan", _plan_needs("glide", "movement", "glide")),
    "polar_needs_polar_parent": Check("plan", _plan_needs("polar", "climate", "polar")),
    "desert_needs_desert_parent": Check("plan", _plan_needs("desert", "habitat", "desert")),
    "diet_from_donor": Check("plan", diet_from_donor),
    "carnivore_needs_carnivore_parent": Check("plan", _plan_needs("carnivore", "diet", "carnivore")),
}

# Every check named in the real-rule map must exist (caught at import, not at run time).
_missing = {c for c, _ in RULE_CHECKS.values()} - set(CHECKS)
if _missing:  # pragma: no cover - guarded by tests
    raise RuntimeError(f"rule_map names unknown checks: {sorted(_missing)}")


# ------------------------------------------------------------------ evaluation


def _severity(rule: dict[str, object]) -> Literal["info", "warning"]:
    explicit = rule.get("severity")
    if not explicit:
        explicit = RULE_CHECKS.get(row_field(rule, "rule_id"), ("", "warning"))[1]  # type: ignore[arg-type]
    return "info" if str(explicit) == "info" else "warning"


def summarize(data: ChimeraData) -> dict[str, int]:
    total = len(data.rules)
    phases = {"pair": 0, "plan": 0}
    for rule in data.rules:
        check = data.rule_check(rule)
        if check in CHECKS:
            phases[CHECKS[check].phase] += 1
    mapped = phases["pair"] + phases["plan"]
    return {"total": total, "mapped": mapped, "pair": phases["pair"], "plan": phases["plan"], "unmapped": total - mapped}


def evaluate(data: ChimeraData, ri: RuleInput, phase: Phase) -> tuple[list[RuleWarning], int]:
    """Run every mapped rule of this phase. Returns (hits, rules run)."""
    hits: list[RuleWarning] = []
    ran = 0
    for rule in data.rules:
        check = CHECKS.get(data.rule_check(rule) or "")
        if check is None or check.phase != phase:
            continue
        ran += 1
        try:
            result = check.fn(ri)
        except Exception:  # a bad data row must never fail the run
            log.exception("rule %s crashed", row_field(rule, "rule_id"))
            result = None
        if result:
            hits.append(RuleWarning(
                rule_id=row_field(rule, "rule_id", "?"),
                message=row_field(rule, "rule_text"),
                severity=_severity(rule),
                detail=result if isinstance(result, str) else None,
            ))
    return hits, ran


async def run(ctx: RunContext) -> str:
    readings, matches = ctx.state["readings"], ctx.state["matches"]
    data = ctx.services.data
    ri = RuleInput(a=(readings["A"], matches.get("A")), b=(readings["B"], matches.get("B")),
                   hybrids=ctx.state.get("real_hybrids", []), allowed_body_plans=data.body_plans)
    warnings, ran = evaluate(data, ri, "pair")
    summary = summarize(data)
    summary["run"] = ran
    summary["hits"] = len(warnings)
    ctx.state["warnings"] = warnings
    ctx.state["rule_input"] = ri
    ctx.state["rules_summary"] = summary
    if summary["total"] == 0:
        return "No rules in the data file"
    if summary["mapped"] == 0:
        log.error("0 of %d rules map to a check", summary["total"])
        return f"0 of {summary['total']} rules map to a check; none could run"
    n_warn = sum(1 for w in warnings if w.severity == "warning")
    n_info = len(warnings) - n_warn
    return (f"{summary['mapped']} of {summary['total']} rules mapped; {ran} run now, {summary['plan']} after planning; "
            f"{n_warn} warning{'s' if n_warn != 1 else ''}, {n_info} note{'s' if n_info != 1 else ''}; "
            f"{summary['unmapped']} unmapped")
