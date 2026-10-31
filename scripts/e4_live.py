"""E4 step 7: live check of the open-world engine.

Usage (from the repo root, META_API_KEY in .env or the environment):
    .venv/Scripts/python.exe scripts/e4_live.py

a) Resolve with no images: axolotl, golden retriever, woolly mammoth, jaguar, pangolin.
b) Render axolotl x pangolin, realistic (the audit's breathing is the interesting one).
c) Render lion x eagle, mythic (four legs plus wings, six-limb license declared).
d) Render rhinoceros beetle x brown bear, speculative (one size license with visible compensation).

Caps (hard, cross-process, every attempt counts, shared counter docs/live/budget.json): images 27, Spark 100,
SAM 16. A render that fails twice is skipped; a budget cap stops the run. GBIF is called live (no Meta budget).
Outputs: docs/evolution/live/e4/ (resolutions, per render: image, plan, prompts, judge, card, SAM mask, calls),
plus the raw key-free Meta recordings in raw/ and every GBIF request/response in gbif/.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evolution" / "live" / "e4"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update({
    "CHIMERA_LIVE_BUDGET_FILE": str(ROOT / "docs" / "live" / "budget.json"),
    "CHIMERA_LIVE_LOG": str(ROOT / "docs" / "LIVE_LOG.md"),
    "CHIMERA_RECORD_DIR": str(OUT / "raw"),
    "CHIMERA_LIVE_MAX_IMAGES": "27",
    "CHIMERA_LIVE_MAX_SPARK": "100",
    "CHIMERA_LIVE_MAX_SAM": "16",
})

from app.adapters.usage import CallRecord, budget_used, current_calls, current_step
from app.config import Settings
from app.errors import ChimeraError
from app.evolution.engine import EvoEngine
from app.models.schemas import ErrorCode
from app.services import build_services

NAMES = ["axolotl", "golden retriever", "woolly mammoth", "jaguar", "pangolin"]
RENDERS = [("b_axolotl_x_pangolin", "axolotl", "pangolin", "realistic"),
           ("c_lion_x_eagle", "lion", "eagle", "mythic"),
           ("d_rhinoceros_beetle_x_brown_bear", "rhinoceros beetle", "brown bear", "speculative")]
PREDICTED = {"resolve": {"spark": 6, "image": 0, "sam": 0},
             "b_axolotl_x_pangolin": {"spark": 6, "image": 1, "sam": 1},
             "c_lion_x_eagle": {"spark": 5, "image": 1, "sam": 1},
             "d_rhinoceros_beetle_x_brown_bear": {"spark": 7, "image": 1, "sam": 1}}
CAPS = {"image": 27, "spark": 100, "sam": 16}


class MaskTap:
    def __init__(self, inner):
        self.inner, self.model_id, self.last = inner, inner.model_id, None

    async def segment(self, image: bytes, label: str) -> bytes:
        self.last = (label, await self.inner.segment(image, label))
        return self.last[1]


def _w(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str),
                    encoding="utf-8")


def _count(calls: list[CallRecord], start: int) -> dict[str, int]:
    out = {"spark": 0, "image": 0, "sam": 0}
    for c in calls[start:]:
        out[c.kind] += 1
    return out


async def render(eng: EvoEngine, tap: MaskTap, slug: str, sire: str, dam: str, mode: str, attempt: int,
                 calls: list[CallRecord]) -> dict:
    current_step.set(f"e4:{slug}:try{attempt}")
    start, out = len(calls), OUT / slug
    out.mkdir(parents=True, exist_ok=True)  # run 1 failed here after every Meta call had succeeded
    try:
        doc = await eng.fuse(sire_name=sire, dam_name=dam, mode=mode, seed=0)
    except Exception as e:
        _w(out / f"failure_try{attempt}.json", {"error": repr(e), "details": getattr(e, "details", None),
                                                "traceback": traceback.format_exc(),
                                                "calls": [asdict(c) for c in calls[start:]]})
        raise
    files = eng.services.settings.resolved_local_dir() / "files"
    (out / "image.webp").write_bytes((files / doc["image_key"]).read_bytes())
    if doc.get("first_image_key"):
        (out / "image_try1_third_animal.webp").write_bytes((files / doc["first_image_key"]).read_bytes())
    if tap.last:
        (out / "sam_mask.png").write_bytes(tap.last[1])
        tap.last = None
    g, j = doc["genome"], doc["judge"]
    _w(out / "plan.json", g)
    _w(out / "prompt_compiled.txt", doc["prompt_compiled"])
    _w(out / "prompt_final.txt", doc["prompt"])
    _w(out / "judge.json", {k: j.get(k) for k in ("scores", "checklist", "checklist_source", "critic",
                                                    "critic_thumbnail", "forced_choice", "open_critic", "mask",
                                                    "third_animal", "soft_cards", "sam_prompt")}
       | {"render_attempts": doc.get("render_attempts"), "warnings": doc.get("warnings"), "polish": doc.get("polish"),
          "model_plan": doc.get("model_plan", "not kept in the cached document")})
    _w(out / "card.json", doc["card"])
    _w(out / "calls.json", [asdict(c) for c in calls[start:]])
    return {"slug": slug, "sire": sire, "dam": dam, "mode": mode, "try": attempt, "creature_id": g["id"],
            "route": doc["route"], "labels": g["labels"], "licenses": g["licenses"], "audit": g["audit"],
            "scores": g["scores"], "checklist": j["checklist"], "answers": j["critic"].get("answers"),
            "thumb_answers": j["critic_thumbnail"].get("answers"), "forced_choice": j["forced_choice"],
            "open_critic": j["open_critic"], "third_animal": j["third_animal"], "model_plan": doc.get("model_plan", "not kept in the cached document"),
            "meta_calls": doc["meta_calls"], "attempts_by_kind": _count(calls, start),
            "warnings": doc.get("warnings")}


RECOVER = "--recover" in sys.argv  # rebuild outputs from the engine's cache: no Meta or GBIF call is made


async def main() -> int:
    settings = Settings(chimera_mode="real", local_data_dir=str(ROOT / ".localdata" / "e4_live"))
    if not settings.meta_api_key:
        print("META_API_KEY is not set")
        return 3
    os.environ.setdefault("META_API_KEY", settings.meta_api_key)  # keeps the recording leak check armed
    OUT.mkdir(parents=True, exist_ok=True)
    eng = EvoEngine(build_services(settings))
    tap = MaskTap(eng.segmenter)
    eng.segmenter = tap
    calls: list[CallRecord] = []
    current_calls.set(calls)
    before = budget_used()
    print("budget before:", before)
    stopped = ""

    # a) resolve, no images
    resolutions, start = [], len(calls)
    for name in ([] if RECOVER else NAMES):
        current_step.set(f"e4:resolve:{name}")
        try:
            res = (await eng.resolve(name)).public()
        except ChimeraError as e:
            res = {"query": name, "status": "error", "error": f"{e.code.value}: {e.message}"}
            if e.code == ErrorCode.BUDGET_EXCEEDED:
                stopped = f"cap reached while resolving {name}: {e.message}"
        resolutions.append(res)
        print(f"resolve {name!r}: {res['status']} {res.get('note', '')}"[:300])
        if stopped:
            break
    if not RECOVER:
        _w(OUT / "resolutions.json", resolutions)
    resolve_calls = _count(calls, start)

    # b) to d) renders
    results, failures, skipped = [], [], []
    for slug, sire, dam, mode in ([] if stopped else RENDERS):
        for attempt in (1, 2):
            try:
                res = await render(eng, tap, slug, sire, dam, mode, 0 if RECOVER else attempt, calls)
                results.append(res)
                print(f"{slug}: ok (try {attempt}) quality={res['scores'].get('quality')} "
                      f"licenses={[x['id'] for x in res['licenses']]}")
                break
            except Exception as e:  # noqa: BLE001
                failures.append({"slug": slug, "try": attempt, "error": repr(e)[:500]})
                print(f"{slug}: FAILED try {attempt}: {e!r}"[:600])
                if isinstance(e, ChimeraError) and e.code == ErrorCode.BUDGET_EXCEEDED:
                    stopped = f"cap reached during {slug}: {e.message}"
                    break
        else:
            skipped.append(slug)
        if stopped:
            break

    gbif = getattr(eng.gbif, "recorded", [])
    for i, rec in enumerate(gbif, 1):
        _w(OUT / "gbif" / f"gbif-{i:02d}.json", rec)
    after = budget_used()
    summary = {"budget_before": before, "budget_after": after, "caps": CAPS, "predicted": PREDICTED,
               "made": {"resolve": resolve_calls, **{r["slug"]: r["attempts_by_kind"] for r in results}},
               "attempts_total": _count(calls, 0), "meter": eng.meter.snapshot(), "gbif_calls": len(gbif),
               "attempts_non_ok": [asdict(c) for c in calls if c.outcome != "ok"],
               "resolutions": resolutions, "results": results, "failures": failures, "skipped": skipped,
               "stopped": stopped}
    _w(OUT / ("summary_recover.json" if RECOVER else "summary.json"), summary)
    print("budget after:", after, "| attempts:", _count(calls, 0), "| gbif calls:", len(gbif))
    if stopped:
        print("STOPPED:", stopped)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
