"""S5 part 3: the fixed benchmark (data/evo_benchmark.json) and its scores, computed in code from saved results.

A creature's saved folder (docs/evolution/live/s5/<case>/<agent|fixed>/) holds, among others:
    inspect_final.json   the final image's full inspect record (rows, failures, both critics' descriptions)
    meta.json            case, kind, wall_seconds, renders, edits, tool_calls, calls by provider
Scores:
    full_match           every critic item passes (no failing or uncertain row)
    failures             total, structure, identity, integration (row groups, below)
    identity             per parent: does the deciding critic's (Meta Spark) "which animals" answer name it;
                         Spark Open's answer is information, and the donor part's own origin answer is listed too
    cost                 renders, edits, tool calls, calls per provider, wall time
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.evolution.data import DATA

BENCHMARK = DATA / "evo_benchmark.json"
GROUPS = {"structure": ("structure",), "identity": ("identity",),
          "integration": ("integration", "coverage", "placement", "pattern", "connection")}
DECIDES, INFO = "meta_spark", "spark_open"


def cases() -> list[dict[str, Any]]:
    return json.loads(BENCHMARK.read_text(encoding="utf-8"))["cases"]


def names_parent(common_name: str, said: list[str] | str | None) -> bool:
    """The answer names this parent: its full common name, or its last word (plural allowed), as a whole word.
    "Chinese pangolin" is named by "pangolin"; "seahorse" does not name a horse."""
    items = [said] if isinstance(said, str) else list(said or [])
    full = common_name.lower().strip()
    head = full.split()[-1]
    pats = [re.compile(rf"(?<![a-z]){re.escape(w)}(?:e?s)?(?![a-z])") for w in (full, head)]
    return any(p.search(str(s).lower()) for s in items for p in pats)


def group_of(row: dict[str, Any]) -> str | None:
    g = row.get("group")
    return next((k for k, v in GROUPS.items() if g in v), None)


def score(folder: Path, sire: str, dam: str) -> dict[str, Any]:
    """The scores of one saved creature (agent or fixed pipeline)."""
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    insp = json.loads((folder / "inspect_final.json").read_text(encoding="utf-8"))
    fails = list(insp.get("failures") or [])
    split = {k: 0 for k in GROUPS}
    other = 0
    for r in fails:
        k = group_of(r)
        if k:
            split[k] += 1
        else:
            other += 1
    descs = insp.get("descriptions") or {}
    ident = {}
    for slot, name in (("sire", sire), ("dam", dam)):
        ident[slot] = {"parent": name,
                       "named": names_parent(name, (descs.get(DECIDES) or {}).get("animals")),
                       "named_by_spark_open": names_parent(name, (descs.get(INFO) or {}).get("animals")),
                       "meta_animals": (descs.get(DECIDES) or {}).get("animals"),
                       "spark_open_animals": (descs.get(INFO) or {}).get("animals")}
    origins = [{"key": r["key"], "expect": r.get("expect"), "answers": r.get("answers"), "status": r.get("status")}
               for r in insp.get("items") or [] if str(r.get("key", "")).startswith("origin_")]
    calls = meta.get("calls_by_provider") or {}
    return {"case": meta["case"], "kind": meta["kind"], "full_match": not fails,
            "failures": {"total": len(fails), **split, **({"other": other} if other else {})},
            "failure_keys": [f"{r['key']} ({r.get('group')}, {r.get('status')})" for r in fails],
            "identity": ident, "both_parents_named": all(v["named"] for v in ident.values()),
            "donor_part_origin": origins,
            "renders": meta.get("renders"), "edits": meta.get("edits"), "tool_calls": meta.get("tool_calls"),
            "calls_by_provider": {p: sum(v.values()) if isinstance(v, dict) else v for p, v in calls.items()},
            "calls_total": sum(sum(v.values()) if isinstance(v, dict) else v for v in calls.values()),
            "wall_seconds": meta.get("wall_seconds"), "host": meta.get("host"), "note": meta.get("note")}


def score_all(root: Path) -> dict[str, Any]:
    """Every saved case for both systems, plus totals (full matches out of 11, average failures, cost)."""
    rows: dict[str, dict[str, Any]] = {}
    for c in cases():
        for kind in ("agent", "fixed"):
            f = root / c["id"] / kind
            if (f / "meta.json").exists() and (f / "inspect_final.json").exists():
                rows.setdefault(c["id"], {})[kind] = score(f, c["sire"], c["dam"])
    totals = {}
    for kind in ("agent", "fixed"):
        got = [r[kind] for r in rows.values() if kind in r]
        n = len(got) or 1
        prov: dict[str, int] = {}
        for g in got:
            for p, v in g["calls_by_provider"].items():
                prov[p] = prov.get(p, 0) + v
        totals[kind] = {
            "creatures": len(got), "full_matches": sum(g["full_match"] for g in got),
            "both_parents_named": sum(g["both_parents_named"] for g in got),
            "avg_failures": round(sum(g["failures"]["total"] for g in got) / n, 2),
            "avg_by_group": {k: round(sum(g["failures"][k] for g in got) / n, 2) for k in GROUPS},
            "avg_renders": round(sum(g["renders"] or 0 for g in got) / n, 2),
            "avg_tool_calls": (round(sum(g["tool_calls"] or 0 for g in got) / n, 2) if kind == "agent" else None),
            "avg_calls_by_provider": {p: round(v / n, 2) for p, v in sorted(prov.items())},
            "avg_calls": round(sum(g["calls_total"] for g in got) / n, 2),
            "avg_wall_seconds": round(sum(g["wall_seconds"] or 0 for g in got) / n, 1)}
    return {"cases": rows, "totals": totals}
