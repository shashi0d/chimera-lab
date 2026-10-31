"""E2 step 4: the 4 worked examples, live, parents by name, one image each. No evolve.

Usage (from the repo root, META_API_KEY in the environment):
    .venv/Scripts/python.exe scripts/e2_live_run.py

Caps for this run (hard, cross-process, every attempt counts): images 20, Spark 70, SAM 8,
on the shared counter docs/live/budget.json. An example that fails twice is skipped.
Outputs go to docs/evolution/live/e2/ (per example: image, plan, prompts, critic answers,
scores, SAM mask, call records) plus summary.json. Raw key-free request/response pairs
go to docs/evolution/live/e2/raw/.
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
# E2b: `e2_live_run.py e2b 1 3` writes to docs/evolution/live/e2b/ and runs only examples 1 and 3.
RUN = sys.argv[1] if len(sys.argv) > 1 else "e2"
ONLY = {int(x) for x in sys.argv[2:]}
OUT = ROOT / "docs" / "evolution" / "live" / RUN
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update({
    "CHIMERA_LIVE_BUDGET_FILE": str(ROOT / "docs" / "live" / "budget.json"),
    "CHIMERA_LIVE_LOG": str(ROOT / "docs" / "LIVE_LOG.md"),
    "CHIMERA_RECORD_DIR": str(OUT / "raw"),
    "CHIMERA_LIVE_MAX_IMAGES": "20",
    "CHIMERA_LIVE_MAX_SPARK": "70",
    "CHIMERA_LIVE_MAX_SAM": "8",
})

from app.adapters.usage import CallRecord, budget_used, current_calls, current_step
from app.config import Settings
from app.errors import ChimeraError
from app.evolution.engine import EvoEngine
from app.models.schemas import ErrorCode
from app.services import build_services

EXAMPLES = [("1_donkey_x_horse", "donkey", "horse"), ("2_lion_x_tiger", "lion", "tiger"),
            ("3_lion_x_eagle", "lion", "eagle"), ("4_eagle_x_octopus", "eagle", "octopus")]
EXAMPLES = [e for i, e in enumerate(EXAMPLES, 1) if not ONLY or i in ONLY]
PREDICTED = {"spark": 4, "image": 1, "sam": 1}  # first plan, polish, critic, thumbnail critic; render; SAM
RERENDER = {"spark": 2, "image": 1, "sam": 1}  # E2b: one re-render after a third animal (critic x2, render, SAM)


class MaskTap:
    """Keeps the last SAM mask so it can be saved next to the image."""

    def __init__(self, inner):
        self.inner, self.model_id, self.last = inner, inner.model_id, None

    async def segment(self, image: bytes, label: str) -> bytes:
        self.last = (label, await self.inner.segment(image, label))
        return self.last[1]


def _w(path: Path, obj) -> None:
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str),
                    encoding="utf-8")


async def run_example(eng: EvoEngine, tap: MaskTap, slug: str, sire: str, dam: str, attempt: int,
                      calls: list[CallRecord]) -> dict:
    current_step.set(f"{RUN}:{slug}:try{attempt}")
    before = len(calls)
    out = OUT / slug
    out.mkdir(parents=True, exist_ok=True)
    try:
        doc = await eng.fuse(sire_name=sire, dam_name=dam, seed=0)
    except Exception as e:
        recs = [asdict(c) for c in calls[before:]]
        _w(out / f"failure_try{attempt}.json", {"error": repr(e), "details": getattr(e, "details", None),
                                                "traceback": traceback.format_exc(), "calls": recs})
        raise
    image = (eng.services.settings.resolved_local_dir() / "files" / doc["image_key"]).read_bytes()
    (out / "image.webp").write_bytes(image)
    if tap.last:
        (out / "sam_mask.png").write_bytes(tap.last[1])
    if doc.get("first_image_key"):
        first = eng.services.settings.resolved_local_dir() / "files" / doc["first_image_key"]
        (out / "image_try1_third_animal.webp").write_bytes(first.read_bytes())
    g = doc["genome"]
    _w(out / "plan.json", g)
    _w(out / "prompt_compiled.txt", doc["prompt_compiled"])
    _w(out / "prompt_final.txt", doc["prompt"])
    j = doc["judge"]
    _w(out / "critic.json", {"critic": j["critic"], "critic_thumbnail": j["critic_thumbnail"], "mask": j["mask"],
                             "sam_prompt": tap.last[0] if tap.last else None, "soft_cards": j["soft_cards"],
                             "scores": g["scores"], "third_animal": j.get("third_animal"),
                             "render_attempts": doc.get("render_attempts"), "warnings": doc.get("warnings"),
                             "polish": doc.get("polish")})
    recs = [asdict(c) for c in calls[before:]]
    _w(out / "calls.json", recs)
    return {"slug": slug, "sire": sire, "dam": dam, "try": attempt, "creature_id": g["id"], "route": doc["route"],
            "host": g["host"], "labels": g["labels"], "scores": g["scores"], "critic": j["critic"],
            "critic_thumbnail": j["critic_thumbnail"], "mask": j["mask"], "model_plan": doc["model_plan"],
            "meta_calls": doc["meta_calls"], "attempts": len(recs), "polish": doc.get("polish"),
            "render_attempts": doc.get("render_attempts"), "warnings": doc.get("warnings")}


async def main() -> int:
    settings = Settings(chimera_mode="real", local_data_dir=str(ROOT / ".localdata" / f"{RUN}_live"))
    if not settings.meta_api_key:
        print("META_API_KEY is not set")
        return 3
    os.environ.setdefault("META_API_KEY", settings.meta_api_key)  # a .env key: keep the recording leak check armed
    OUT.mkdir(parents=True, exist_ok=True)
    eng = EvoEngine(build_services(settings))
    tap = MaskTap(eng.segmenter)
    eng.segmenter = tap
    calls: list[CallRecord] = []
    current_calls.set(calls)
    budget_before = budget_used()
    print("budget before:", budget_before)
    results, failures, skipped = [], [], []
    for slug, sire, dam in EXAMPLES:
        for attempt in (1, 2):
            try:
                res = await run_example(eng, tap, slug, sire, dam, attempt, calls)
                results.append(res)
                print(f"{slug}: ok (try {attempt}) quality={res['scores'].get('quality')} critic={res['critic']}")
                break
            except Exception as e:  # noqa: BLE001
                failures.append({"slug": slug, "try": attempt, "error": repr(e)[:500]})
                print(f"{slug}: FAILED try {attempt}: {e!r}"[:600])
                if isinstance(e, ChimeraError) and e.code == ErrorCode.BUDGET_EXCEEDED:
                    break  # the cap is reached: retrying cannot help
        else:
            skipped.append(slug)
    budget_after = budget_used()
    attempts: dict[str, int] = {"spark": 0, "image": 0, "sam": 0}
    for c in calls:
        attempts[c.kind] += 1
    summary = {"budget_before": budget_before, "budget_after": budget_after,
               "caps": {"image": 20, "spark": 70, "sam": 8},
               "predicted_per_example": PREDICTED, "predicted_per_rerender": RERENDER,
               "predicted_total": {k: v * len(EXAMPLES) for k, v in PREDICTED.items()},
               "logical_calls_meter": eng.meter.snapshot(), "attempts_by_kind": attempts,
               "attempts_non_ok": [asdict(c) for c in calls if c.outcome != "ok"],
               "results": results, "failures": failures, "skipped": skipped}
    _w(OUT / "summary.json", summary)
    print("budget after:", budget_after)
    print("attempts:", attempts, "meter:", eng.meter.snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
