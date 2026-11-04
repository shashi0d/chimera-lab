"""S3b live runs. One part per invocation (keys from .env; never printed or saved):

    .venv/Scripts/python.exe scripts/s3b_live.py calibrate [label]   # part 5: recalibrate on gold_set_s3b.json
    .venv/Scripts/python.exe scripts/s3b_live.py rescore <folder>    # part 5: re-score cached answers (no calls)
    .venv/Scripts/python.exe scripts/s3b_live.py validate            # part 6: live validation, 2 repeats per run

Caps (runaway guards only, about 3x planned S3b use on top of the shared counter docs/live/budget.json):
images 120, Meta Spark 900, SAM 200, Spark Open 900.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3a_live as S

os.environ.update({"CHIMERA_LIVE_MAX_IMAGES": "120", "CHIMERA_LIVE_MAX_SPARK": "900", "CHIMERA_LIVE_MAX_SAM": "200",
                   "CHIMERA_LIVE_MAX_SPARK_BASETEN": "900"})

from app.adapters.usage import current_step
from app.evolution import critic as C
from app.evolution.genome import Genome, validate_plan

ROOT, BENCH, LIVE = S.ROOT, S.BENCH, S.LIVE
OUT = LIVE / "s3b"
S.OUT = OUT  # recordings go under live/s3b
CAL = BENCH / "calibration_s3b"
GOLD = BENCH / "gold_set_s3b.json"
# Question keys added in S3b; the S3a protocol is the full protocol minus these (same raw answers).
S3B_PREFIXES = ("follows_body", "separate_outline", "sized_to_body", "wrong_scale", "legs_covered", "abrupt_stop",
                "connects_", "separate_", "origin_")


def gold() -> list[dict[str, Any]]:
    return S.r(GOLD)["items"]


def plan_of(item: dict[str, Any]) -> Genome:
    return validate_plan(S.r(ROOT / item["plan"]))


def version(tax: Any) -> str:
    qs = sorted(q.text for i in gold() for q in C.questions(plan_of(i), tax))
    parts = sorted(p for i in gold() for _f, p in C.origin_parts(plan_of(i), tax))
    return hashlib.sha256(json.dumps([S.wording(), qs, parts], sort_keys=True).encode()).hexdigest()[:8]


async def part_calibrate() -> None:
    eng, calls, before = S.setup("calibration_s3b", "s3b_calibrate")
    await S.learned(eng)
    ver = version(eng.tax) + (f"_{sys.argv[2]}" if len(sys.argv) > 2 else "")
    d = CAL / ver
    S.w(d / "wording.json", {**S.wording(), "questions": {i["id"]: [q.text for q in C.questions(plan_of(i), eng.tax)]
                                                          for i in gold()},
                             "parts": {i["id"]: [p for _f, p in C.origin_parts(plan_of(i), eng.tax)] for i in gold()}})
    critics = C.critics_for(eng.spark)
    print("critics:", list(critics), "| version", ver)
    for item in gold():
        key = item["id"].replace("/", "__")
        if (d / f"{key}.json").exists():
            print("cached", item["id"])
            continue
        g = plan_of(item)
        image = (ROOT / item["image"]).read_bytes()
        qs = C.questions(g, eng.tax)
        parts = [p for _f, p in C.origin_parts(g, eng.tax)]
        current_step.set(f"s3b:calibrate:{item['id']}")
        done = await asyncio.gather(*(C.run_critic(n, s, image, qs, S.Meter(), parts) for n, s in critics.items()))
        raws = dict(done)
        S.w(d / f"{key}.json", {"id": item["id"], "questions": [asdict(q) for q in qs], "parts": parts,
                                "raw": {n: asdict(x) for n, x in raws.items()}})
        print("done", item["id"], {n: (x.error or "ok") for n, x in raws.items()})
    S.w(d / "calls.json", S.calls_summary(calls, before))
    rescore(ver)


def _is_s3b(key: str) -> bool:
    return key.startswith(S3B_PREFIXES)


def rescore(ver: str, out_name: str = "scores.json") -> dict[str, Any]:
    from app.evolution.data import taxonomy
    from app.evolution.resolve import animal_from_entry
    from app.evolution.route import route

    tax = taxonomy().copy()
    for k, e in S.r(ROOT / "data" / "learned_animals.json")["animals"].items():
        if k in ("chinese_pangolin", "european_rhinoceros_beetle"):
            tax.add(animal_from_entry(e), [])
    d = CAL / ver
    rows = []
    for item in gold():
        p = d / f"{item['id'].replace('/', '__')}.json"
        if not p.exists():
            continue
        g = plan_of(item)
        data = S.r(p)
        raws = {n: C.Raw(**x) for n, x in data["raw"].items()}
        r_ = route(tax.animals[g.parents.sire], tax.animals[g.parents.dam], tax, myth=g.mode == "mythic")
        qs_all = C.questions(g, tax)
        qs_old = [q for q in qs_all if not _is_s3b(q.id)]
        row = {"id": item["id"], "label": item["label"], "note": item.get("note", "")}
        for sys_name, qs, names in (("s3a_pair", qs_old, list(raws)), *[(f"s3b_{n}", qs_all, [n]) for n in raws],
                                    ("s3b_pair", qs_all, list(raws)), ("s3b_configured", qs_all, list(raws))):
            sub = {n: raws[n] for n in names}
            if sys_name == "s3a_pair":
                sub = {n: C.Raw(describe=x.describe, answers=x.answers, origins={}, error=x.error) for n, x in sub.items()}
            res = C.evaluate(sub, g, tax, r_, qs, decision=None if sys_name == "s3b_configured" else "pair")
            row[sys_name] = {"verdict": res["verdict"], "signals": [(s["key"], s["status"]) for s in res["signals"]]}
        rows.append(row)
    systems = [k for k in rows[0] if k not in ("id", "label", "note")] if rows else []
    metrics = {}
    for s in systems:
        f = [x for x in rows if x["label"] == "fail"]
        gd = [x for x in rows if x["label"] == "good"]
        metrics[s] = {"caught": sum(x[s]["verdict"] == "fail" for x in f), "of_failures": len(f),
                      "false_alarms": sum(x[s]["verdict"] == "fail" for x in gd), "of_goods": len(gd)}
    report = {"version": ver, "metrics": metrics, "rows": rows}
    S.w(d / out_name, report)
    for s, m in metrics.items():
        print(f"{s:16s} caught {m['caught']}/{m['of_failures']}  false alarms {m['false_alarms']}/{m['of_goods']}")
    for x in rows:
        print(f"\n{x['id']} [{x['label']}] {x['note'][:70]}")
        for s in systems:
            print(f"   {s}: {x[s]['verdict']} {x[s]['signals'][:12]}")
    return report


# ------------------------------------------------------------------ part 6: live validation

RUNS = [
    # (key, sire, dam, mode, host, growth, tuned)
    ("beetle_bear_default", "rhinoceros beetle", "brown bear", "speculative", "dam", None, True),
    ("beetle_bear_growth", "rhinoceros beetle", "brown bear", "speculative", "dam", "edit", True),
    ("axolotl_pangolin_default", "axolotl", "chinese pangolin", "realistic", "sire", None, True),
    ("crab_wolf_default", "crab", "grey wolf", "speculative", None, None, False),
    ("indian_pangolin_horse_default", "indian pangolin", "horse", "realistic", "horse", None, False),
    ("tortoise_goat_default", "tortoise", "goat", "realistic", None, None, False),
]
REPEATS = 2


async def choose(eng: Any, name: str) -> tuple[str, str]:
    """(name to use, note). The resolver never guesses: an ambiguous name returns needs_choice with alternatives;
    the validation run takes the first one and records the choice."""
    res = await eng.resolve(name)
    if res.status == "resolved":
        return name, "resolved as given"
    alts = res.alternatives or []
    if not alts:
        return name, f"{res.status}: {res.note} (no alternatives)"
    first = alts[0]
    pick = first.get("scientific_name") or first.get("common_name") or name
    return pick, f"{res.status}: {res.note}; alternatives {[a.get('common_name') or a.get('scientific_name') for a in alts]}; took the first"


async def part_validate() -> None:
    eng, calls, before = S.setup("validation", os.environ.get("S3B_CACHE", "s3b_validate"))  # a fresh cache for reruns
    await S.learned(eng)
    only = sys.argv[2:]  # optional run keys
    summary = []
    for key, sire, dam, mode, host, growth, tuned in RUNS:
        if only and key not in only:
            continue
        tag = os.environ.get("S3B_TAG", "")  # a rerun after a fix is stored beside the original (r1_fix)
        for n in range(1, int(os.environ.get("S3B_REPEATS", REPEATS)) + 1):
            vdir = OUT / "validation" / key / f"r{n}{tag}"
            if (vdir / "doc.json").exists():
                print("cached", key, n)
                continue
            current_step.set(f"s3b:validate:{key}:{n}")
            choices = {}
            for slot_name in (sire, dam):  # an ambiguous name: take the first alternative, as a user picking would
                picked, note = await choose(eng, slot_name)
                if picked != slot_name:
                    choices[slot_name] = {"used": picked, "note": note}
            sire_n, dam_n = choices.get(sire, {}).get("used", sire), choices.get(dam, {}).get("used", dam)
            host_arg = host
            if host not in (None, "sire", "dam"):  # a named host: map to its slot after resolving both parents
                s_ = await eng.resolve(sire_n)
                host_arg = "sire" if s_.animal and s_.animal.common_name.lower() == host else "dam"
            try:
                doc = await eng.fuse(sire_name=sire_n, dam_name=dam_n, mode=mode, host=host_arg, seed=n - 1,
                                     growth=growth)
                doc["name_choices"] = choices
            except Exception as e:  # noqa: BLE001 - recorded, the run continues
                S.w(vdir / "error.json", {"error": f"{type(e).__name__}: {e}",
                                          "resolutions": {k: v.public() for k, v in eng.resolutions.items()}})
                print("ERROR", key, n, type(e).__name__, str(e)[:300])
                continue
            files = eng.services.settings.resolved_local_dir() / "files"
            S.w(vdir / "image.webp", (files / doc["image_key"]).read_bytes())
            if doc.get("first_image_key") and (files / doc["first_image_key"]).exists():
                S.w(vdir / "first_pass.webp", (files / doc["first_image_key"]).read_bytes())
            if (doc.get("growth") or {}).get("edit_image_key"):
                S.w(vdir / "grown_discarded.webp", (files / doc["growth"]["edit_image_key"]).read_bytes())
            S.w(vdir / "plan.json", doc["genome"])
            S.w(vdir / "prompt_compiled.txt", doc["prompt_compiled"])
            S.w(vdir / "prompt_final.txt", doc["prompt"])
            S.w(vdir / "inspect.json", doc["inspect"])
            S.w(vdir / "judge.json", doc["judge"])
            S.w(vdir / "doc.json", {k: v for k, v in doc.items() if k not in ("genome", "judge", "inspect")})
            fails = [(f["key"], f["status"]) for f in doc["inspect"]["before"]["failures"]]
            summary.append({"run": key, "repeat": n, "tuned": tuned, "signals": fails, "warnings": doc["warnings"],
                            "growth": doc.get("growth", {}).get("drift") if doc.get("growth") else None})
            print(key, n, "| signals:", fails, "| warnings:", doc["warnings"])
    S.w(OUT / "validation" / f"calls_{'_'.join(only) or 'all'}.json", {**S.calls_summary(calls, before),
                                                                       "summary": summary})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "rescore":
        rescore(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "rescore.json")
    elif cmd == "calibrate":
        asyncio.run(part_calibrate())
    elif cmd == "validate":
        asyncio.run(part_validate())
    else:
        sys.exit("usage: s3b_live.py calibrate [label] | rescore <folder> [out] | validate [run keys]")
