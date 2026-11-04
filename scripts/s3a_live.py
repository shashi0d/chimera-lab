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
    ver = version(eng.tax) + (f"_{sys.argv[2]}" if len(sys.argv) > 2 else "")  # a label forces a fresh run
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


def rescore(ver: str | None = None, out_name: str = "scores.json") -> dict[str, Any]:
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
    w(it_dir / out_name, report)
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


# ------------------------------------------------------------------ part 8: the integration experiment

EXP = OUT / "experiment"
REPEATS = 2
VARIANTS = ("V0", "V1", "V2", "V3", "V4", "V5")
VARIANT_NAMES = {"V0": "baseline (current compiled prompt)", "V1": "covering replacement (RC-R10-12)",
                 "V2": "V1 + functional analogy (RC-R10-13)", "V3": "V2 + anatomy anchors (RC-R10-14)",
                 "V4": "V2 + donor portrait as material reference (@Image1)",
                 "V5": "growth by edit (plain host, then one edit turn)"}
# Pair-specific wording. The plan is the same for every variant; only the wording of the covering changes.
PAIRS: dict[str, dict[str, Any]] = {
    "beetle_bear": {
        "sire": "rhinoceros beetle", "dam": "brown bear", "host": "dam", "mode": "speculative",
        "covering": "hard, glossy chitin plates with fine seams", "short": "chitin plates",
        "analogy": ("the covering is a carapace grown in the skin like an armadillo's, shaped like a beetle's two "
                    "elytra: one domed dorsal shield from the shoulders to the hips, in two halves meeting at a midline "
                    "seam, never scattered plates"),
        "anchors": ("anatomical anchors: the horn is rooted on the nasal bone like a rhinoceros horn, its base merging "
                    "into the skin of the snout and brow; the shield is anchored along the spine"),
        "edit_extra": ("a single curved horn of hard, glossy chitin rooted on the nasal bone like a rhinoceros "
                       "horn, its base merging into the skin of the brow"),
        "portrait": ("A single european rhinoceros beetle (Oryctes nasicornis) on its own, full body, top three-quarter "
                     "view, its glossy reddish-brown wing cases clearly visible, plain light background, natural "
                     "history illustration."),
    },
    "axolotl_pangolin": {
        "sire": "axolotl", "dam": "chinese pangolin", "host": "sire", "mode": "realistic",
        "covering": "large overlapping keratin scales", "short": "keratin scales",
        "analogy": ("the scales are a pangolin's scale layer grown in the skin: overlapping keratin scales rooted in the "
                    "skin like a pangolin's, in rows that overlap from head to tail like roof tiles, one continuous "
                    "layer over the back and flanks"),
        "anchors": ("anatomical anchors: the scale rows are anchored along the spine and follow the body's curve to the "
                    "tail; the external gills stay rooted at the sides of the head"),
        "edit_extra": "",
        "portrait": ("A single Chinese pangolin (Manis pentadactyla) on its own, full body, side view, its overlapping "
                     "scales clearly visible, plain light background, natural history illustration."),
    },
}


def _cover(eng: EvoEngine, g: Genome) -> tuple[str, str, str]:
    host = eng.tax.animals[g.host]
    cover = C._host_cover(host)
    cover = "smooth skin" if cover == "skin" else cover
    return host.common_name.lower(), cover, C._regions(g.traits["coat_texture"].region)


def variant_prompts(eng: EvoEngine, g: Genome, spec: dict[str, Any]) -> dict[str, Any]:
    """Every variant's exact text from the one plan. V0 is compile_prompt unchanged; V1 to V4 replace only the
    covering phrase; V5 is a plain host render plus one edit instruction."""
    import re

    from app.evolution.prompt import compile_prompt

    v0 = compile_prompt(g, eng.tax)
    hn, cover, where = _cover(eng, g)
    m = re.search(re.escape(spec["covering"]) + r" in its own colors, in a few large patches over the [^,]+, with clean "
                  r"edges, color and surface unchanged inside each patch", v0)
    assert m, "covering phrase not found in the compiled prompt"
    v1c = (f"a covering of {spec['covering']} in its own colors that replaces the {hn}'s {cover} over the {where}: "
           f"it grows in the skin as the {hn}'s own covering there, not as pieces added on top; the {cover} stops at "
           f"the covering's edge, and the belly and legs keep the {hn}'s own {cover}")
    v2c = f"{v1c}; {spec['analogy']}"
    v3c = f"{v2c}; {spec['anchors']}"
    swap = lambda c: v0.replace(m.group(0), c).replace("Coat texture and patches follow the body outline.",
                                                       "The covering follows the body outline.")
    v4 = swap(v2c) + (f" Material reference: use @Image1 only for the material of the {spec['short']}: their color, "
                      f"surface texture and seams. Do not copy its body, head, legs or shape; the creature is the {hn} "
                      "described above.")
    host_only = v0.split(" Details:")[0].replace(
        re.search(r"A single creature that combines [^.]+\.", v0).group(0), f"A single {hn}.")  # type: ignore[union-attr]
    tail = v0[v0.index(" Bilaterally symmetrical"):]
    v5_host = f"{host_only} Details: {hn} body and legs, with its own {cover} everywhere, plain coat.{tail}"
    extra = f" Also grow {spec['edit_extra']}." if spec["edit_extra"] else ""
    v5_edit = (f"Grow, from the skin of the {where}, {v2c}.{extra} Keep the pose, the head, the legs, the {cover} "
               "everywhere else, the background and everything else the same.")
    return {"V0": v0, "V1": swap(v1c), "V2": swap(v2c), "V3": swap(v3c), "V4": v4,
            "V5": {"host": v5_host, "edit": v5_edit}, "portrait": spec["portrait"]}


def _ext(content_type: str) -> str:
    return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(content_type, "webp")


async def part_experiment() -> None:
    from app.evolution.inspect import inspect

    eng, calls, before = setup("experiment", "s3a_experiment")
    critics = C.critics_for(eng.spark)
    meter = eng.meter
    for key, spec in PAIRS.items():
        pdir = EXP / key
        s = (await eng.resolve(spec["sire"])).animal
        d = (await eng.resolve(spec["dam"])).animal
        g0, r_ = eng.seed_plan(s, d, host_pick=spec["host"], design_mode=spec["mode"])
        g = eng.finish(g0, r_)
        w(pdir / "plan.json", g.model_dump())
        prompts = variant_prompts(eng, g, spec)
        w(pdir / "prompts.json", prompts)
        portrait = None
        if (pdir / "portrait.png").exists() or any(pdir.glob("portrait.*")):
            portrait = next(pdir.glob("portrait.*")).read_bytes()
        for v in VARIANTS:
            for n in range(1, REPEATS + 1):
                vdir = pdir / f"{v}_r{n}"
                if (vdir / "inspect.json").exists():
                    print("cached", key, v, n)
                    continue
                current_step.set(f"s3a:experiment:{key}:{v}:{n}")
                rec: dict[str, Any] = {"pair": key, "variant": v, "variant_name": VARIANT_NAMES[v], "repeat": n}
                if v == "V4":
                    if portrait is None:
                        img_p = await meter.call("image", "portrait", eng.renderer.generate(prompts["portrait"], [], "1:1"))
                        w(pdir / f"portrait.{_ext(img_p.content_type)}", img_p.data)
                        w(pdir / "portrait_prompt.txt", prompts["portrait"])
                        portrait = img_p.data
                    img = await meter.call("image", "render", eng.renderer.generate(prompts["V4"], [portrait], "1:1"))
                    rec["prompt"] = prompts["V4"]
                    rec["references"] = ["@Image1 = portrait (material only)"]
                elif v == "V5":
                    base = await meter.call("image", "render", eng.renderer.generate(prompts["V5"]["host"], [], "1:1"))
                    w(vdir / f"host.{_ext(base.content_type)}", base.data)
                    img = await meter.call("image", "edit", eng.renderer.generate(prompts["V5"]["edit"], [], "1:1",
                                                                                   base.response_id))
                    rec["prompt"] = prompts["V5"]["host"]
                    rec["edit_instruction"] = prompts["V5"]["edit"]
                    rec["previous_response_id"] = base.response_id
                else:
                    img = await meter.call("image", "render", eng.renderer.generate(prompts[v], [], "1:1"))
                    rec["prompt"] = prompts[v]
                w(vdir / f"image.{_ext(img.content_type)}", img.data)
                w(vdir / "prompt.txt", rec["prompt"] + (f"\n\n[edit turn]\n{rec['edit_instruction']}"
                                                        if "edit_instruction" in rec else ""))
                rec["response_id"] = img.response_id
                insp = await inspect(img.data, g, eng.tax, critics, eng.segmenter, meter, r_)
                rec["inspect"] = insp
                rec["integration"] = {row["key"]: {"status": row["status"], "answers": row["answers"]}
                                      for row in insp["items"] if row["group"] in ("integration", "placement")}
                w(vdir / "inspect.json", rec)
                print(key, v, n, "| signals:", [(f["key"], f["status"]) for f in insp["failures"]])
    w(EXP / "calls.json", calls_summary(calls, before))


# ------------------------------------------------------------------ part 9: review sheet and contact sheet

def _thumb_b64(path: Path, px: int = 560) -> str:
    import base64
    import io

    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((px, px))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=84)
    return base64.b64encode(buf.getvalue()).decode()


def _records() -> list[dict[str, Any]]:
    recs = []
    for key in PAIRS:
        for v in VARIANTS:
            for n in range(1, REPEATS + 1):
                d = EXP / key / f"{v}_r{n}"
                if (d / "inspect.json").exists():
                    rec = r(d / "inspect.json")
                    rec["dir"] = d
                    rec["image_path"] = next(d.glob("image.*"))
                    recs.append(rec)
    return recs


def part_review() -> None:
    import html as H

    recs = _records()
    if not recs:
        sys.exit("no experiment records yet")
    pair_title = {"beetle_bear": "Rhinoceros beetle x brown bear (speculative, bear host)",
                  "axolotl_pangolin": "Axolotl x Chinese pangolin (realistic, axolotl host, pangolin scales)"}
    cards_html = []
    for key in PAIRS:
        cards_html.append(f'<h2 id="{key}">{H.escape(pair_title[key])}</h2>')
        for v in VARIANTS:
            group = [x for x in recs if x["pair"] == key and x["variant"] == v]
            if not group:
                continue
            cards_html.append(f'<h3>{v}: {H.escape(VARIANT_NAMES[v])}</h3><div class="row">')
            for x in group:
                rid = f"{key}.{v}.r{x['repeat']}"
                insp = x["inspect"]
                integ = "".join(
                    f"<tr><td>{H.escape(row['text'])}</td><td>{H.escape(str(row['expect']))}</td>"
                    + "".join(f"<td>{H.escape(str(a))}</td>" for a in row["answers"].values())
                    + f'<td class="st {row["status"]}">{row["status"]}</td></tr>'
                    for row in insp["items"] if row["group"] in ("integration", "placement"))
                crit_names = "".join(f"<th>{H.escape(c)}</th>" for c in insp["critics"])
                sig = "".join(f'<li><span class="st {s["status"]}">{s["status"]}</span> {H.escape(s["text"])}</li>'
                              for s in insp["failures"]) or "<li>none: every check passed</li>"
                desc = "".join(f"<p><b>{H.escape(c)}:</b> {H.escape(str(d.get('description', ''))[:900])}</p>"
                               for c, d in insp["descriptions"].items())
                prompt = H.escape(x["prompt"])
                edit = (f'<p class="lbl">Edit turn (previous_response_id)</p><pre>{H.escape(x["edit_instruction"])}</pre>'
                        if x.get("edit_instruction") else "")
                refs = f'<p class="lbl">References: {H.escape(", ".join(x["references"]))}</p>' if x.get("references") else ""
                host_img = ""
                if (x["dir"] / "host.png").exists() or list(x["dir"].glob("host.*")):
                    hp = next(x["dir"].glob("host.*"))
                    host_img = (f'<p class="lbl">Plain host render (before the edit)</p>'
                                f'<img class="small" alt="host render" src="data:image/jpeg;base64,{_thumb_b64(hp, 280)}">')
                rating = "".join(
                    f'<label>{lab} <select data-k="{k}"><option value="">-</option>'
                    + "".join(f"<option>{i}</option>" for i in range(1, 6)) + "</select></label>"
                    for k, lab in (("integrated", "Integrated (1-5)"), ("placement", "Placement correct (1-5)"),
                                   ("real", "Looks like a real animal (1-5)")))
                cards_html.append(f'''<article class="card" data-id="{rid}">
<header><b>{rid}</b> <span class="verdict {'fail' if insp['failures'] else 'pass'}">critic: {'fail signals' if insp['failures'] else 'pass'}</span></header>
<img alt="{rid}" src="data:image/jpeg;base64,{_thumb_b64(x['image_path'])}">
{host_img}
<div class="rate">{rating}<label class="notes">Notes <textarea data-k="notes" rows="2"></textarea></label></div>
<details><summary>Critic: integration and placement answers</summary>
<table><tr><th>Question</th><th>Expected</th>{crit_names}<th>Result</th></tr>{integ}</table></details>
<details><summary>Critic: all fail signals ({len(insp['failures'])})</summary><ul>{sig}</ul></details>
<details><summary>Critic: free descriptions (plan-blind)</summary>{desc}</details>
<details><summary>Exact prompt</summary>{refs}<pre>{prompt}</pre>{edit}</details>
</article>''')
            cards_html.append("</div>")
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>S3a Integration Review</title>
<style>
:root {{ --bg:#faf8f4; --fg:#1d1b18; --muted:#6b655c; --card:#fff; --line:#e3ddd2; --pass:#2f7d4f; --fail:#b3402a; --unc:#a8730b; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#161513; --fg:#ece8e1; --muted:#a39d93; --card:#201f1c; --line:#38352f; --pass:#5cbf86; --fail:#e5765e; --unc:#e0b04a; }} }}
:root[data-theme="dark"] {{ --bg:#161513; --fg:#ece8e1; --muted:#a39d93; --card:#201f1c; --line:#38352f; --pass:#5cbf86; --fail:#e5765e; --unc:#e0b04a; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:24px 16px 64px; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:1240px; margin:0 auto; }}
h1 {{ font-size:24px; margin:0 0 4px; }} h2 {{ margin:40px 0 4px; font-size:20px; border-bottom:1px solid var(--line); padding-bottom:6px; }}
h3 {{ margin:22px 0 10px; font-size:16px; color:var(--muted); font-weight:600; }}
.intro {{ color:var(--muted); max-width:820px; }}
.row {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:16px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; min-width:0; }}
.card header {{ display:flex; justify-content:space-between; gap:8px; margin-bottom:8px; font-size:14px; }}
.card img {{ width:100%; height:auto; border-radius:6px; display:block; }}
.card img.small {{ width:50%; }}
.verdict {{ font-size:12px; padding:2px 8px; border-radius:99px; border:1px solid currentColor; }}
.verdict.pass, .st.pass {{ color:var(--pass); }} .verdict.fail, .st.fail {{ color:var(--fail); }} .st.uncertain {{ color:var(--unc); }}
.rate {{ display:grid; gap:6px; margin:10px 0; font-size:13px; }}
.rate label {{ display:flex; justify-content:space-between; align-items:center; gap:8px; }}
.rate label.notes {{ flex-direction:column; align-items:stretch; }}
select, textarea {{ font:inherit; color:var(--fg); background:var(--bg); border:1px solid var(--line); border-radius:6px; padding:3px 6px; }}
details {{ margin-top:6px; font-size:13px; }} summary {{ cursor:pointer; color:var(--muted); }}
table {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:6px; }} td, th {{ border-top:1px solid var(--line); padding:4px; text-align:left; vertical-align:top; }}
pre {{ white-space:pre-wrap; word-break:break-word; font-size:12px; background:var(--bg); padding:8px; border-radius:6px; }}
.lbl {{ color:var(--muted); font-size:12px; margin:8px 0 2px; }}
.bar {{ position:sticky; top:0; background:var(--bg); padding:8px 0; display:flex; gap:10px; flex-wrap:wrap; align-items:center; z-index:2; border-bottom:1px solid var(--line); }}
button {{ font:inherit; padding:6px 12px; border-radius:6px; border:1px solid var(--line); background:var(--card); color:var(--fg); cursor:pointer; }}
#status {{ color:var(--muted); font-size:13px; }}
</style></head>
<body><main>
<h1>S3a integration experiment: owner review</h1>
<p class="intro">Every image from the experiment, grouped by pair and prompt variant. The plan is identical within each pair; only the wording of the donor covering changes (V0 baseline to V5 growth by edit). Rate each image 1 to 5: <b>integrated</b> (does the donor covering grow out of the body with a natural transition, or sit on top as pieces), <b>placement correct</b> (where the plan puts it: back and flanks; belly and legs keep the host covering) and <b>looks like a real animal</b>. Ratings are kept in this browser while you work; use <i>Export ratings</i> to save them as JSON and send the file back. The critic results are the plan-blind protocol (two critics, describe first, balanced checklist).</p>
<div class="bar"><button id="export">Export ratings (JSON)</button><button id="clear">Clear ratings</button><span id="status"></span></div>
{''.join(cards_html)}
</main>
<script>
const KEY = "s3a-review-ratings";
function load() {{ try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ return {{}}; }} }}
function save(d) {{ try {{ localStorage.setItem(KEY, JSON.stringify(d)); }} catch (e) {{}} }}
const data = load();
document.querySelectorAll(".card").forEach(card => {{
  const id = card.dataset.id; const r = data[id] || {{}};
  card.querySelectorAll("[data-k]").forEach(el => {{
    if (r[el.dataset.k] !== undefined) el.value = r[el.dataset.k];
    el.addEventListener("input", () => {{ data[id] = data[id] || {{}}; data[id][el.dataset.k] = el.value; save(data); status(); }});
  }});
}});
function status() {{
  const n = Object.values(data).filter(r => r.integrated && r.placement && r.real).length;
  document.getElementById("status").textContent = n + " of {len(recs)} images fully rated";
}}
status();
document.getElementById("export").onclick = () => {{
  const blob = new Blob([JSON.stringify({{sheet: "s3a_review", rated_at: new Date().toISOString(), ratings: data}}, null, 1)], {{type: "application/json"}});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "s3a_ratings.json"; a.click();
}};
document.getElementById("clear").onclick = () => {{ for (const k in data) delete data[k]; save(data); location.reload(); }};
</script>
</body></html>'''
    w(BENCH / "s3a_review.html", page)
    contact_sheet(recs)
    print("wrote", BENCH / "s3a_review.html", "and", BENCH / "s3a_contact_sheet.png", f"({len(recs)} images)")


def contact_sheet(recs: list[dict[str, Any]], tile: int = 300) -> None:
    """One PNG: per pair, 6 variant columns x 2 repeat rows, labeled."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("arial.ttf", 18)
        small = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = small = ImageFont.load_default()
    head, lab = 40, 26
    block = head + lab + REPEATS * (tile + 22)
    sheet = Image.new("RGB", (len(VARIANTS) * tile + 60, len(PAIRS) * block + 10), (250, 248, 244))
    d = ImageDraw.Draw(sheet)
    for pi, key in enumerate(PAIRS):
        y0 = pi * block + 6
        d.text((10, y0 + 8), key.replace("_", " x "), fill=(29, 27, 24), font=font)
        for vi, v in enumerate(VARIANTS):
            x = 60 + vi * tile
            d.text((x + 6, y0 + head), f"{v} {VARIANT_NAMES[v].split(' (')[0][:30]}", fill=(90, 85, 78), font=small)
            for n in range(1, REPEATS + 1):
                y = y0 + head + lab + (n - 1) * (tile + 22)
                if vi == 0:
                    d.text((14, y + tile // 2), f"r{n}", fill=(90, 85, 78), font=font)
                rec = next((x_ for x_ in recs if x_["pair"] == key and x_["variant"] == v and x_["repeat"] == n), None)
                if rec is None:
                    continue
                with Image.open(rec["image_path"]) as im:
                    im = im.convert("RGB")
                    im.thumbnail((tile - 8, tile - 8))
                    sheet.paste(im, (x + 4, y))
                ok = not rec["inspect"]["failures"]
                d.text((x + 6, y + tile - 4), "critic pass" if ok else f"{len(rec['inspect']['failures'])} signals",
                       fill=(47, 125, 79) if ok else (179, 64, 42), font=small)
    sheet.save(BENCH / "s3a_contact_sheet.png")


# ------------------------------------------------------------------ entry

PARTS = {"calibrate": part_calibrate, "cite": part_cite, "experiment": part_experiment}

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "review":
        part_review()
        sys.exit(0)
    if len(sys.argv) < 2 or sys.argv[1] not in {*PARTS, "rescore"}:
        sys.exit(f"usage: s3a_live.py {{{'|'.join([*PARTS, 'rescore'])}}}")
    if sys.argv[1] == "rescore":
        rescore(sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else "rescore.json")
    else:
        asyncio.run(PARTS[sys.argv[1]]())
