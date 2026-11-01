"""S3b part 4: growth by edit, an option for coverings only.

S3a V5 (plain host, then one edit growing the covering) gave the axolotl the closest-to-real-hybrid look, but on
the bear the edit also moved the horn to the nose (a rhinoceros) and on the axolotl it changed the tail. So:

- The first pass renders the host WITH its discrete parts (they are never grown by edit): the plan minus its covering.
- One edit turn (previous_response_id) grows only the covering, worded from the plan's transfer record.
- A plan-blind drift check compares the two images (heads, walking legs and tails, from the critics' free
  descriptions): if any count changed, the edit is discarded and the creature falls back to the first-pass
  render of the full plan (the default single-pass compile), so host drift never reaches the user.
"""

from __future__ import annotations

from typing import Any

from app.evolution.genome import SURFACE_TAGS, Genome, Trait
from app.evolution.prompt import ZONE_WORDS, covering_clause

DRIFT_KEYS = ("heads", "walking_legs", "tails")


def has_covering(g: Genome) -> bool:
    return any(t.kind == "covering" and t.extent for t in g.transfers)


def host_first(g: Genome) -> Genome:
    """The plan without its covering: the host's own covering everywhere, discrete parts kept (unconnected)."""
    h = g.model_copy(deep=True)
    cov = next(t for t in h.transfers if t.kind == "covering")
    for tag in SURFACE_TAGS:
        tr = h.traits[tag]
        if tr.op == "PATCH" and tr.donor == cov.donor:
            h.traits[tag] = Trait(op="PICK", donor=h.host, note="growth by edit: the covering is grown in the edit turn")
    h.transfers = [t.model_copy(update={"connects": []}) for t in h.transfers if t.kind != "covering"]
    return h


def instruction(g: Genome, tax: Any) -> str:
    """One edit turn that grows the planned covering from the skin, and keeps everything else."""
    cov = next(t for t in g.transfers if t.kind == "covering")
    where = ", ".join(ZONE_WORDS[z] for z in cov.extent)
    parts = [t.feature for t in g.transfers if t.kind == "part"]
    keep = "the pose, the head and face, the number of legs, the tail"
    if parts:
        keep += ", the " + " and the ".join(parts) + " exactly where and as they are"
    clause = covering_clause(g, tax, cov)
    connect = ""
    if any(cov.feature in t.connects for t in g.transfers if t.kind == "part"):
        connect = " Let the covering run up to the base of the " + " and the ".join(
            t.feature for t in g.transfers if t.kind == "part" and cov.feature in t.connects) + ", so they connect."
    del where  # the clause names the zones
    return f"Now grow the covering: {clause}.{connect} Keep {keep}, the background and everything else the same."


def _counts(d: dict[str, Any]) -> dict[str, Any]:
    return {k: d.get(k) for k in DRIFT_KEYS}


async def drift(before: bytes, after: bytes, critics: dict[str, Any], meter: Any) -> dict[str, Any]:
    """Host drift across the edit: a count that changes in every critic's description (heads, walking legs, tails).
    A critic that fails counts as no evidence; one critic seeing a change while another does not is reported but
    not called drift (the critics disagree on single images about as often)."""
    rows: dict[str, Any] = {}
    changed_by: dict[str, list[str]] = {}
    for name, spark in critics.items():
        try:
            b = _counts(await meter.call("spark", f"drift_before:{name}", spark.describe(before)))
            a = _counts(await meter.call("spark", f"drift_after:{name}", spark.describe(after)))
        except Exception as e:  # noqa: BLE001
            from app.errors import ChimeraError
            from app.models.schemas import ErrorCode

            if isinstance(e, ChimeraError) and e.code == ErrorCode.BUDGET_EXCEEDED:
                raise
            rows[name] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
            continue
        rows[name] = {"before": b, "after": a}
        changed_by[name] = [k for k in DRIFT_KEYS if isinstance(b[k], int) and isinstance(a[k], int) and b[k] != a[k]]
    agreed = sorted(set.intersection(*(set(v) for v in changed_by.values()))) if changed_by else []
    return {"drifted": bool(agreed), "changed": agreed, "by_critic": rows,
            "any_change": sorted({k for v in changed_by.values() for k in v})}
