"""Rules from chimera_data.json run as Python checks keyed by the rule's `check`.

Rules whose check type has no implementation are skipped (counted in the
step detail). v1 produces warnings only, never hard failures.
"""

from __future__ import annotations

from collections.abc import Callable

from app.data.loader import parse_range, split_list
from app.models.schemas import AnimalMatch, AnimalReading, RuleWarning
from app.pipeline.context import RunContext

Side = tuple[AnimalReading, AnimalMatch | None]


def _fact(side: Side, key: str) -> str:
    reading, match = side
    if match and match.facts.get(key):
        return match.facts[key]
    if key == "body_plan":
        return reading.body_plan or ""
    return ""


def _plan(side: Side) -> str:
    return _fact(side, "body_plan").lower()


def body_plan_mismatch(a: Side, b: Side) -> bool:
    return bool(_plan(a) and _plan(b) and _plan(a) != _plan(b))


def limb_count_mismatch(a: Side, b: Side) -> bool:
    la, lb = _fact(a, "limb_count"), _fact(b, "limb_count")
    return bool(la and lb and la != lb)


def boneless_parent(a: Side, b: Side) -> bool:
    return any(_plan(s) == "cephalopod" or "no skeleton" in _fact(s, "notable_features") for s in (a, b))


def mass_ratio(a: Side, b: Side) -> bool:
    ra, rb = parse_range(_fact(a, "body_mass_kg")), parse_range(_fact(b, "body_mass_kg"))
    if not ra or not rb:
        return False
    small, large = sorted([ra, rb], key=lambda r: r[1])
    # Compare range bounds, never midpoints: even the extremes are 20x apart.
    return small[1] * 20 < large[0]


def flight_mass(a: Side, b: Side) -> bool:
    flyer = any("flying" in split_list(_fact(s, "locomotion")) for s in (a, b))
    heavy = any((r := parse_range(_fact(s, "body_mass_kg"))) and r[0] > 20 for s in (a, b))
    return bool(flyer and heavy)


def realm_conflict(a: Side, b: Side) -> bool:
    ra, rb = _fact(a, "realm"), _fact(b, "realm")
    if not ra or not rb:
        aquatic = {"aquatic", "cephalopod"}
        return (_plan(a) in aquatic) != (_plan(b) in aquatic) and bool(_plan(a) and _plan(b))
    return ra != rb


def covering_conflict(a: Side, b: Side) -> bool:
    ca, cb = set(split_list(_fact(a, "covering"))), set(split_list(_fact(b, "covering")))
    return bool(ca and cb and not ca & cb)


def class_distance(a: Side, b: Side) -> bool:
    ca, cb = _fact(a, "class"), _fact(b, "class")
    return bool(ca and cb and ca != cb)


def same_genus(a: Side, b: Side) -> bool:
    ga = (a[0].scientific_name or "").split(" ")[0]
    gb = (b[0].scientific_name or "").split(" ")[0]
    return bool(ga and ga == gb) and a[0].scientific_name != b[0].scientific_name


def diet_conflict(a: Side, b: Side) -> bool:
    da, db = _fact(a, "diet"), _fact(b, "diet")
    return bool(da and db and da != db and "carnivore" in (da, db))


CHECKS: dict[str, Callable[[Side, Side], bool]] = {
    f.__name__: f
    for f in (body_plan_mismatch, limb_count_mismatch, boneless_parent, mass_ratio, flight_mass,
              realm_conflict, covering_conflict, class_distance, same_genus, diet_conflict)
}


async def run(ctx: RunContext) -> str:
    readings, matches = ctx.state["readings"], ctx.state["matches"]
    a: Side = (readings["A"], matches.get("A"))
    b: Side = (readings["B"], matches.get("B"))
    rules = ctx.services.data.applicable_rules(set(CHECKS))
    warnings: list[RuleWarning] = []
    for rule in rules:
        try:
            hit = CHECKS[str(rule["check"])](a, b)
        except Exception:  # a bad data row must never fail the run
            hit = False
        if hit:
            severity = "info" if str(rule.get("severity", "warning")) == "info" else "warning"
            warnings.append(RuleWarning(rule_id=str(rule.get("id", "?")), message=str(rule.get("rule", "")),
                                        severity=severity))
    ctx.state["warnings"] = warnings
    skipped = len(ctx.services.data.rules) - len(rules)
    n_warn = sum(1 for w in warnings if w.severity == "warning")
    detail = f"{len(rules)} rules checked, {n_warn} warning{'s' if n_warn != 1 else ''}"
    return detail + (f", {skipped} not automated yet" if skipped else "")
