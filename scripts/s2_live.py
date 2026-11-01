"""S2 live runs. One part per invocation (keys from .env; never printed or saved):

    .venv/Scripts/python.exe scripts/s2_live.py cite         # part 4: re-resolve 4 animals with web-cited traits
    .venv/Scripts/python.exe scripts/s2_live.py beetlebear   # part 8: rhinoceros beetle x brown bear, speculative

Caps (runaway guards only, shared counter docs/live/budget.json): images 80, Spark 250, SAM 80, Spark Open 600.
Outputs: docs/evolution/live/s2/<part>/ with key-free raw recordings in raw/.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evolution" / "live" / "s2"
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)
os.environ.update({"CHIMERA_LIVE_BUDGET_FILE": str(ROOT / "docs" / "live" / "budget.json"),
                   "CHIMERA_LIVE_LOG": str(ROOT / "docs" / "LIVE_LOG.md"),
                   "CHIMERA_LIVE_MAX_IMAGES": "80", "CHIMERA_LIVE_MAX_SPARK": "250", "CHIMERA_LIVE_MAX_SAM": "80",
                   "CHIMERA_LIVE_MAX_SPARK_BASETEN": "600"})

from app.adapters.usage import CallRecord, budget_used, current_calls, current_step
from app.config import Settings
from app.evolution.engine import EvoEngine
from app.services import build_services

CITE_NAMES = ["axolotl", "chinese pangolin", "rhinoceros beetle", "woolly mammoth"]


def w(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, bytes):
        path.write_bytes(obj)
    else:
        path.write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str),
                        encoding="utf-8")


def setup(part: str, cache: str) -> tuple[EvoEngine, list[CallRecord], dict[str, int]]:
    os.environ["CHIMERA_RECORD_DIR"] = str(OUT / part / "raw")
    (OUT / part).mkdir(parents=True, exist_ok=True)
    settings = Settings(chimera_mode="real", local_data_dir=str(ROOT / ".localdata" / cache))
    if not settings.meta_api_key:
        sys.exit("META_API_KEY is not set")
    calls: list[CallRecord] = []
    current_calls.set(calls)
    return EvoEngine(build_services(settings)), calls, budget_used()


def finish(part: str, calls: list[CallRecord], before: dict[str, int], extra: dict[str, Any]) -> None:
    after = budget_used()
    by: dict[str, dict[str, int]] = {}
    for c in calls:
        prov = getattr(c, "provider", "") or ("baseten" if c.kind == "spark_baseten" else "meta")
        k = f"{prov}:{c.kind}"
        by.setdefault(k, {"ok": 0, "failed": 0})["ok" if c.outcome == "ok" else "failed"] += 1
    w(OUT / part / "summary.json", {**extra, "budget": {"before": before, "after": after},
                                    "calls_by_provider": by, "attempts": [asdict(c) for c in calls]})
    print("budget", before, "->", after, "| calls", by)


async def part_cite() -> None:
    eng, calls, before = setup("cited", "s2_cite")
    reports = []
    for name in CITE_NAMES:
        current_step.set(f"s2:cite:{name}")
        rep = await eng.resolver.cite(name)
        reports.append(rep)
        w(OUT / "cited" / f"{name.replace(' ', '_')}.json", rep)
        counts: dict[str, int] = {}
        for r in rep.get("fields", []):
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"{name}: {rep['status']} {rep.get('note', '')} {counts}")
    finish("cited", calls, before, {"reports": reports})


PARTS = {"cite": part_cite}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PARTS:
        sys.exit(f"usage: s2_live.py {{{'|'.join(PARTS)}}}")
    asyncio.run(PARTS[sys.argv[1]]())
