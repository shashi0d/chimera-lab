"""S3a live runs. One part per invocation (keys from .env; never printed or saved):

    .venv/Scripts/python.exe scripts/s3a_live.py calibrate     # part 3: old critic vs the plan-blind protocol on the gold set
    .venv/Scripts/python.exe scripts/s3a_live.py rescore       # part 3: re-score cached raw answers (no calls)
    .venv/Scripts/python.exe scripts/s3a_live.py cite          # part 4: re-verify the 4 S2 animals' citations (code fetch)
    .venv/Scripts/python.exe scripts/s3a_live.py experiment    # part 8: 2 pairs x 6 prompt variants x 2 repeats
    .venv/Scripts/python.exe scripts/s3a_live.py review        # part 9: review sheet + contact sheet (no calls)

Caps (runaway guards only, about 3x planned S3a use on top of the shared counter docs/live/budget.json):
images 120, Spark 550, SAM 325, Spark Open 650.
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

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "docs" / "evolution" / "benchmark"
LIVE = ROOT / "docs" / "evolution" / "live"
OUT = LIVE / "s3a"
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)
os.environ.update({"CHIMERA_LIVE_BUDGET_FILE": str(ROOT / "docs" / "live" / "budget.json"),
                   "CHIMERA_LIVE_LOG": str(ROOT / "docs" / "LIVE_LOG.md"),
                   "CHIMERA_LIVE_MAX_IMAGES": "120", "CHIMERA_LIVE_MAX_SPARK": "550", "CHIMERA_LIVE_MAX_SAM": "325",
                   "CHIMERA_LIVE_MAX_SPARK_BASETEN": "650"})

from app.adapters.usage import CallRecord, budget_used, current_calls, current_step
from app.config import Settings
from app.evolution import critic as C
from app.evolution.engine import EvoEngine
from app.evolution.genome import Genome, validate_plan
from app.evolution.inspect import Item, inspect_checklist, plan_items
from app.evolution.judge import checklist_for, generated_checklist, third_animals
from app.evolution.live import ASK_INSTRUCTIONS, DESCRIBE_INSTRUCTIONS
from app.services import build_services


def w(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, bytes):
        path.write_bytes(obj)
    else:
        path.write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str),
                        encoding="utf-8")


def r(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def setup(part: str, cache: str, record: bool = True) -> tuple[EvoEngine, list[CallRecord], dict[str, int]]:
    if record:
        os.environ["CHIMERA_RECORD_DIR"] = str(OUT / part / "raw")
    settings = Settings(chimera_mode="real", local_data_dir=str(ROOT / ".localdata" / cache))
    if not settings.meta_api_key:
        sys.exit("META_API_KEY is not set")
    calls: list[CallRecord] = []
    current_calls.set(calls)
    return EvoEngine(build_services(settings)), calls, budget_used()


def calls_summary(calls: list[CallRecord], before: dict[str, int]) -> dict[str, Any]:
    by: dict[str, dict[str, int]] = {}
    for c in calls:
        prov = getattr(c, "provider", "") or ("baseten" if c.kind == "spark_baseten" else "meta")
        k = f"{prov}:{c.kind}:{c.purpose}"
        by.setdefault(k, {"ok": 0, "failed": 0})["ok" if c.outcome == "ok" else "failed"] += 1
    return {"budget": {"before": before, "after": budget_used()}, "calls": by}


async def learned(eng: EvoEngine) -> None:
    for name in ("chinese pangolin", "rhinoceros beetle"):  # learned entries: no model call
        res = await eng.resolve(name)
        assert res.status == "resolved", res.note


def gold() -> list[dict[str, Any]]:
    return r(BENCH / "gold_set.json")["items"]


def plan_of(item: dict[str, Any]) -> Genome:
    return validate_plan(r(ROOT / item["plan"]))


def wording() -> dict[str, Any]:
    """Everything a critic reads, so each iteration is recorded and hashed."""
    return {"describe": DESCRIBE_INSTRUCTIONS, "ask": ASK_INSTRUCTIONS}


def version(tax: Any) -> str:
    """A hash of the instructions and every gold question: any wording change is a new iteration folder."""
    qs = sorted(q.text for item in gold() for q in C.questions(plan_of(item), tax))
    return hashlib.sha256(json.dumps([wording(), qs], sort_keys=True).encode()).hexdigest()[:8]


# ------------------------------------------------------------------ part 3: calibration


class Meter:
    async def call(self, kind: str, purpose: str, aw: Any) -> Any:
        return await aw


async def old_critic(eng: EvoEngine, image: bytes, g: Genome) -> dict[str, Any]:
    """The S2 inspect, reproduced: the plan-worded checklist on Spark Open, creature count, third animals, SAM
    presence for parts."""
    r_ = eng.route_for(g)
    hand = checklist_for(r_)
    checklist = hand or generated_checklist(g, eng.tax)
    crit = await eng.spark.checklist(image, checklist)
    third = third_animals(crit, eng.tax.animals[g.parents.sire], eng.tax.animals[g.parents.dam], eng.tax, r_)
    items = [Item(t, "pad", False) for t in checklist] if hand else [i for i in plan_items(g, eng.tax)
                                                                     if i.text in checklist]
    out = await inspect_checklist(image, g, eng.tax, items, crit, third, eng.segmenter, Meter())
    return {"checklist": checklist, "critic": crit, "third": third, "inspect": out}


def score_item(raws: dict[str, C.Raw], g: Genome, eng: EvoEngine, names: list[str]) -> dict[str, Any]:
    sub = {n: raws[n] for n in names if n in raws}
    res = C.evaluate(sub, g, eng.tax, eng.route_for(g))
    return {"verdict": res["verdict"], "signals": [{k: s[k] for k in ("source", "key", "text", "status", "answers")}
                                                    for s in res["signals"]]}


async def part_calibrate() -> None:
    eng, calls, before = setup("calibration", "s3a_calibrate")
    await learned(eng)
    ver = version(eng.tax)
    it_dir = BENCH / "calibration" / ver
    w(it_dir / "wording.json", {**wording(), "questions": {i["id"]: [q.text for q in C.questions(plan_of(i), eng.tax)]
                                                           for i in gold()}})
    critics = C.critics_for(eng.spark)
    print("critics:", list(critics), "| version", ver)
    for item in gold():
        g = plan_of(item)
        image = (ROOT / item["image"]).read_bytes()
        key = item["id"].replace("/", "__")
        qs = C.questions(g, eng.tax)
        raw_path = it_dir / f"{key}.json"
        if raw_path.exists():
            print("cached", item["id"])
            continue
        current_step.set(f"s3a:calibrate:{item['id']}")
        done = await asyncio.gather(*(C.run_critic(n, s, image, qs, Meter()) for n, s in critics.items()))
        raws = dict(done)
        old_path = BENCH / "calibration" / "old" / f"{key}.json"
        if not old_path.exists():
            w(old_path, await old_critic(eng, image, g))
        w(raw_path, {"id": item["id"], "questions": [asdict(q) for q in qs],
                     "raw": {n: asdict(x) for n, x in raws.items()}})
        print("done", item["id"], {n: (x.error or "ok") for n, x in raws.items()})
    w(it_dir / "calls.json", calls_summary(calls, before))
    rescore(ver)


def rescore(ver: str | None = None) -> dict[str, Any]:
    """Catch rate on known failures and false alarms on known goods, for the old critic, each new critic alone and
    the pair, from cached raw answers (no calls). Questions are regenerated from the current code, so a question
    wording change needs a new calibrate run; scoring-rule changes do not."""
    from app.evolution.data import taxonomy
    from app.evolution.resolve import animal_from_entry

    tax = taxonomy().copy()
    for k, e in r(ROOT / "data" / "learned_animals.json")["animals"].items():
        if k in ("chinese_pangolin", "european_rhinoceros_beetle"):
            tax.add(animal_from_entry(e), [])
    ver = ver or version(tax)
    it_dir = BENCH / "calibration" / ver

    class E:  # the bits of the engine evaluate needs
        def __init__(self) -> None:
            self.tax = tax

        def route_for(self, g: Genome) -> Any:
            from app.evolution.route import route

            return route(tax.animals[g.parents.sire], tax.animals[g.parents.dam], tax, myth=g.mode == "mythic")

    eng = E()
    rows = []
    for item in gold():
        key = item["id"].replace("/", "__")
        p = it_dir / f"{key}.json"
        if not p.exists():
            continue
        g = plan_of(item)
        data = r(p)
        asked = {q["text"] for q in data["questions"]}
        now = {q.text for q in C.questions(g, tax)}
        raws = {n: C.Raw(**x) for n, x in data["raw"].items()}
        names = list(raws)
        old = r(BENCH / "calibration" / "old" / f"{key}.json")
        row = {"id": item["id"], "label": item["label"], "failures": item["failures"],
               "stale_questions": sorted(now - asked),
               "old": {"verdict": "fail" if old["inspect"]["failures"] else "pass",
                       "signals": [f["text"] for f in old["inspect"]["failures"]]}}
        for n in names:
            row[n] = score_item(raws, g, eng, [n])  # type: ignore[arg-type]
        row["pair"] = score_item(raws, g, eng, names)  # type: ignore[arg-type]
        rows.append(row)
    systems = ["old", *[n for n in rows[0] if n not in ("id", "label", "failures", "stale_questions", "old", "pair")],
               "pair"] if rows else []
    metrics = {}
    for s in systems:
        fails = [x for x in rows if x["label"] == "fail"]
        goods = [x for x in rows if x["label"] == "good"]
        metrics[s] = {"caught": sum(x[s]["verdict"] == "fail" for x in fails), "of_failures": len(fails),
                      "false_alarms": sum(x[s]["verdict"] == "fail" for x in goods), "of_goods": len(goods)}
    union_caught = sum(any(x[s]["verdict"] == "fail" for s in systems if s != "old") for x in rows
                       if x["label"] == "fail")
    report = {"version": ver, "metrics": metrics, "new_union_caught": union_caught, "rows": rows}
    w(it_dir / "scores.json", report)
    for s, m in metrics.items():
        print(f"{s:12s} caught {m['caught']}/{m['of_failures']}  false alarms {m['false_alarms']}/{m['of_goods']}")
    for x in rows:
        print(f"\n{x['id']} [{x['label']}]" + (f" STALE {x['stale_questions']}" if x["stale_questions"] else ""))
        print("   old :", x["old"]["verdict"], x["old"]["signals"][:4])
        for s in systems[1:]:
            print(f"   {s}:", x[s]["verdict"], [(z["key"], z["status"]) for z in x[s]["signals"]])
    return report


# ------------------------------------------------------------------ part 4: re-verify the S2 citations

CITE_NAMES = ["axolotl", "chinese pangolin", "rhinoceros beetle", "woolly mammoth"]


async def part_cite() -> None:
    """No model call: each stored S2 citation is checked for its source tier and for its quote on the page,
    fetched in code. The axolotl is a database animal, so its S2 citations come from the S2 report."""
    from app.evolution.citecheck import summary

    eng, calls, before = setup("cite", "s3a_cite", record=False)
    out = OUT / "cite"
    reports = []
    for name in CITE_NAMES:
        given = None
        s2 = r(LIVE / "s2" / "cited" / f"{name.replace(' ', '_')}.json")
        if s2.get("source") == "database":
            given = {f["field"]: {"url": f["url"], "evidence": f["evidence"]} for f in s2["fields"]
                     if f["status"] != "uncited" and f["url"]}
        rep = await eng.resolver.reverify(name, given)
        rep["summary"] = summary(rep["checks"])
        reports.append(rep)
        w(out / f"{name.replace(' ', '_')}.json", rep)
        print(f"{name}: {rep['summary']}")
        for f, c in rep["checks"].items():
            print(f"   {f:24s} {c['status']:16s} {c['host']:32s} {c['reason'][:70]}")
    w(out / "summary.json", {"reports": [{k: x[k] for k in ("query", "animal", "source", "summary", "stored")}
                                         for x in reports], **calls_summary(calls, before)})


# ------------------------------------------------------------------ entry

PARTS = {"calibrate": part_calibrate, "cite": part_cite}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in {*PARTS, "rescore"}:
        sys.exit(f"usage: s3a_live.py {{{'|'.join([*PARTS, 'rescore'])}}}")
    if sys.argv[1] == "rescore":
        rescore(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        asyncio.run(PARTS[sys.argv[1]]())
