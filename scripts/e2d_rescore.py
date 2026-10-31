"""E2d: re-score existing live images with the real-hybrid feature-checklist critic. No image, no SAM.

Usage (from the repo root, META_API_KEY in .env or the environment):
    .venv/Scripts/python.exe scripts/e2d_rescore.py

Two Spark calls per image (full image and the 192 px thumbnail, same checklist and forced choice):
the E2c mule and, as a check, the E2 liger. Caps: images 20, Spark 70, SAM 15 on the shared
counter docs/live/budget.json. Silhouette and soft-penalty scores are reused from the image's
original run; only the critic and thumbnail parts are new. Outputs: docs/evolution/live/e2d/.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evolution" / "live" / "e2d"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update({
    "CHIMERA_LIVE_BUDGET_FILE": str(ROOT / "docs" / "live" / "budget.json"),
    "CHIMERA_LIVE_LOG": str(ROOT / "docs" / "LIVE_LOG.md"),
    "CHIMERA_RECORD_DIR": str(OUT / "raw"),
    "CHIMERA_LIVE_MAX_IMAGES": "20",
    "CHIMERA_LIVE_MAX_SPARK": "70",
    "CHIMERA_LIVE_MAX_SAM": "15",
})

from app.adapters.usage import budget_used, current_calls, current_step
from app.config import Settings
from app.evolution.data import taxonomy
from app.evolution.judge import (
    WEIGHTS,
    checklist_choices,
    checklist_for,
    checklist_score,
    thumbnail,
)
from app.evolution.live import LiveEvoSpark
from app.evolution.route import route

IMAGES = [("1_donkey_x_horse", "e2c", "donkey", "horse"), ("2_lion_x_tiger", "e2", "lion", "tiger")]


def _w(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


async def rescore(spark: LiveEvoSpark, slug: str, run: str, sire: str, dam: str) -> dict:
    tax = taxonomy()
    s, d = tax.resolve(sire), tax.resolve(dam)
    r = route(s, d, tax)
    items, choices = checklist_for(r), checklist_choices(s, d, r)
    src = ROOT / "docs" / "evolution" / "live" / run / slug
    image = (src / "image.webp").read_bytes()
    old = json.loads((src / "critic.json").read_text(encoding="utf-8"))
    current_step.set(f"e2d:{slug}")
    full = await spark.checklist(image, items, choices)
    thumb = await spark.checklist(thumbnail(image), items, choices)
    s_old = old["scores"]
    new = {"critic": checklist_score(full), "silhouette": s_old["silhouette"], "thumbnail": checklist_score(thumb),
           "soft_penalty": s_old["soft_penalty"]}
    new["quality"] = round(WEIGHTS["critic"] * new["critic"] + WEIGHTS["silhouette"] * new["silhouette"]
                           + WEIGHTS["thumbnail"] * new["thumbnail"] + WEIGHTS["rules"] * (1 - new["soft_penalty"]), 3)
    result = {"slug": slug, "image": f"docs/evolution/live/{run}/{slug}/image.webp", "known_pair": r.pair["id"],
              "checklist": items, "choices": choices, "full": full, "thumbnail": thumb,
              "forced_choice": {"full": full["choice"], "thumbnail": thumb["choice"]},
              "scores_before": s_old, "open_critic_before": {"full": old["critic"], "thumbnail": old["critic_thumbnail"]},
              "scores_after": new}
    out = OUT / slug
    out.mkdir(parents=True, exist_ok=True)
    _w(out / "checklist.json", result)
    return result


async def main() -> int:
    settings = Settings(chimera_mode="real", local_data_dir=str(ROOT / ".localdata" / "e2d_live"))
    if not settings.meta_api_key:
        print("META_API_KEY is not set")
        return 2
    os.environ.setdefault("META_API_KEY", settings.meta_api_key)  # so the recording leak check sees it
    spark = LiveEvoSpark(settings)
    before = budget_used()
    print("budget before:", before)
    calls: list = []
    current_calls.set(calls)
    results, failures = [], []
    for slug, run, sire, dam in IMAGES:
        for attempt in (1, 2):
            try:
                res = await rescore(spark, slug, run, sire, dam)
            except Exception as e:  # noqa: BLE001 - record and move on; an image that fails twice is skipped
                failures.append({"slug": slug, "try": attempt, "error": repr(e)})
                print(f"{slug}: failed (try {attempt}): {e!r}")
                continue
            results.append(res)
            print(f"{slug}: critic={res['scores_after']['critic']} thumb={res['scores_after']['thumbnail']} "
                  f"choice={res['forced_choice']} quality {res['scores_before']['quality']} -> "
                  f"{res['scores_after']['quality']}")
            break
    after = budget_used()
    print("budget after:", after)
    _w(OUT / "summary.json", {"budget_before": before, "budget_after": after,
                              "caps": {"image": 20, "spark": 70, "sam": 15},
                              "predicted": {"spark": 2 * len(IMAGES), "image": 0, "sam": 0},
                              "calls": [asdict(c) for c in calls], "failures": failures, "results": results})
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
