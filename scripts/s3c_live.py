"""S3c live runs: the agent end to end (part 3), and the fixed pipeline once per pair for comparison.

    .venv/Scripts/python.exe scripts/s3c_live.py agent [run keys]      # 2 repeats per pair, Spark Open drives
    .venv/Scripts/python.exe scripts/s3c_live.py fixed [run keys]      # engine.fuse once per pair (baseline)

Keys come from .env and are never printed or saved. Caps are runaway guards only, about 3x the planned S3c use on
top of the shared counter docs/live/budget.json (images 84, Meta Spark 483, SAM 80, Spark Open 507 before S3c).

Outputs: docs/evolution/live/s3c/<agent|fixed>/<run>/<repeat>/ with trace.json, trace.md, messages.json (exactly
what the agent was sent and answered), candidates.json, plan.json, every image with its exact prompt, critic.json
(each critic's answer per item, per image) and doc.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3a_live as S

os.environ.update({"CHIMERA_LIVE_MAX_IMAGES": "180", "CHIMERA_LIVE_MAX_SPARK": "800", "CHIMERA_LIVE_MAX_SAM": "180",
                   "CHIMERA_LIVE_MAX_SPARK_BASETEN": "1150"})

from app.adapters.usage import current_step  # noqa: E402

OUT = S.LIVE / "s3c"
S.OUT = OUT
REPEATS = 2
# key, sire, dam, mode, held out
RUNS = [
    ("beetle_bear", "rhinoceros beetle", "brown bear", "speculative", False),
    ("tortoise_goat", "tortoise", "domestic goat", "realistic", False),
    ("crab_wolf", "crab", "gray wolf", "speculative", False),
    ("fox_owl", "red fox", "barn owl", "speculative", True),  # held out: never used for tuning
]


def w(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    elif isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def critic_rows(raw: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Each item with every critic's answer, the deciding status (Meta) and the pair status (information)."""
    if not raw:
        return []
    return [{"key": r["key"], "group": r["group"], "text": r["text"], "expect": r.get("expect"),
             "answers": r.get("answers"), "status": r["status"], "pair_status": r.get("pair_status"),
             "sam_found": r.get("sam_found")} for r in raw.get("items", [])]


def save_agent(vdir: Path, doc: dict[str, Any], run: Any) -> None:
    w(vdir / "trace.json", run.trace)
    w(vdir / "trace.md", run.trace_md())
    w(vdir / "messages.json", run.messages)
    w(vdir / "candidates.json", run.state.candidates or [])
    imgs = {}
    for iid in run.state.order:
        im = run.state.images[iid]
        w(vdir / f"{iid}.webp", im.load())
        w(vdir / f"{iid}_prompt.txt", im.prompt)
        if im.extra.get("prompt_compiled"):
            w(vdir / f"{iid}_prompt_compiled.txt", im.extra["prompt_compiled"])
        w(vdir / f"{iid}_plan.json", im.plan.model_dump())
        imgs[iid] = {"kind": im.kind, "parent": im.parent, "plan_id": im.plan_id,
                     "verdict": (im.inspect or {}).get("verdict"), "failures": (im.inspect or {}).get("failures"),
                     "drift": (im.inspect or {}).get("drift"), "critic": critic_rows(im.raw_inspect),
                     "decision": ((im.raw_inspect or {}).get("items") and "meta_spark decides") or None}
    w(vdir / "critic.json", imgs)
    if doc.get("genome"):
        w(vdir / "plan.json", doc["genome"])
        w(vdir / "image.webp", run.state.images[doc["image_id"]].load())
        w(vdir / "prompt_final.txt", doc["prompt"])
        w(vdir / "prompt_compiled.txt", doc["prompt_compiled"])
    w(vdir / "doc.json", {k: v for k, v in doc.items() if k not in ("genome", "inspect", "trace")})


async def part_agent(only: list[str]) -> None:
    eng, calls, before = S.setup("agent", os.environ.get("S3C_CACHE", "s3c_agent"))
    summary = []
    for key, sire, dam, mode, held in RUNS:
        if only and key not in only:
            continue
        for n in range(1, int(os.environ.get("S3C_REPEATS", REPEATS)) + 1):
            vdir = OUT / "agent" / key / f"r{n}{os.environ.get('S3C_TAG', '')}"
            if (vdir / "doc.json").exists():
                print("cached", key, n)
                continue
            current_step.set(f"s3c:agent:{key}:{n}")
            try:
                doc, run = await eng.agent_fuse(sire, dam, mode, seed=n - 1)
            except Exception as e:  # noqa: BLE001 - recorded, the run continues
                w(vdir / "error.json", {"error": f"{type(e).__name__}: {e}"})
                print("ERROR", key, n, type(e).__name__, str(e)[:300])
                continue
            save_agent(vdir, doc, run)
            rem = (doc.get("card") or {}).get("remaining_failures")
            summary.append({"run": key, "repeat": n, "held_out": held, "renders": run.state.renders,
                            "edits": run.state.edits, "tool_calls": run.state.calls, "stop": run.state.stop,
                            "final_image": doc.get("image_id"), "remaining": rem,
                            "host": (doc.get("genome") or {}).get("host")})
            print(key, n, "| renders", run.state.renders, "| calls", run.state.calls, "| remaining",
                  [r["key"] for r in rem or []], "| stop", run.state.stop)
    w(OUT / "agent" / f"calls_{'_'.join(only) or 'all'}.json", {**S.calls_summary(calls, before), "summary": summary})


async def part_fixed(only: list[str]) -> None:
    """The fixed pipeline once per pair (seed 0), for the agent-vs-pipeline comparison. A structural tie has no
    automatic host any more (D-085): the run records needs_choice and then fuses with the first-named parent, the
    rule the agent replaced, so the two can be compared."""
    eng, calls, before = S.setup("fixed", os.environ.get("S3C_CACHE", "s3c_fixed"))
    summary = []
    for key, sire, dam, mode, _held in RUNS:
        if only and key not in only:
            continue
        vdir = OUT / "fixed" / key / "r1"
        if (vdir / "doc.json").exists():
            print("cached", key)
            continue
        current_step.set(f"s3c:fixed:{key}")
        note = None
        try:
            try:
                doc = await eng.fuse(sire_name=sire, dam_name=dam, mode=mode, seed=0)
            except Exception as e:  # noqa: BLE001
                if "needs_choice" not in str(e):
                    raise
                note = "needs_choice on a structural tie (D-085); fused with host=sire (the old rule) to compare"
                doc = await eng.fuse(sire_name=sire, dam_name=dam, mode=mode, seed=0, host="sire")
        except Exception as e:  # noqa: BLE001
            w(vdir / "error.json", {"error": f"{type(e).__name__}: {e}"})
            print("ERROR", key, type(e).__name__, str(e)[:300])
            continue
        files = eng.services.settings.resolved_local_dir() / "files"
        w(vdir / "image.webp", (files / doc["image_key"]).read_bytes())
        if doc.get("first_image_key") and (files / doc["first_image_key"]).exists():
            w(vdir / "first_pass.webp", (files / doc["first_image_key"]).read_bytes())
        w(vdir / "plan.json", doc["genome"])
        w(vdir / "prompt_compiled.txt", doc["prompt_compiled"])
        w(vdir / "prompt_final.txt", doc["prompt"])
        w(vdir / "critic.json", {"before": critic_rows(doc["inspect"]["before"]),
                                 "after": critic_rows(doc["inspect"].get("after")), "kept": doc["inspect"]["kept"]})
        w(vdir / "doc.json", {**{k: v for k, v in doc.items() if k not in ("genome", "inspect", "judge")},
                              "tie_note": note})
        fails = [(f["key"], f["status"]) for f in (doc["inspect"].get("after") or doc["inspect"]["before"])["failures"]]
        summary.append({"run": key, "kept": doc["inspect"]["kept"], "signals": fails, "tie_note": note,
                        "host": doc["genome"]["host"]})
        print(key, "| kept", doc["inspect"]["kept"], "| signals", fails)
    w(OUT / "fixed" / f"calls_{'_'.join(only) or 'all'}.json", {**S.calls_summary(calls, before), "summary": summary})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "agent":
        asyncio.run(part_agent(sys.argv[2:]))
    elif cmd == "fixed":
        asyncio.run(part_fixed(sys.argv[2:]))
    else:
        sys.exit("usage: s3c_live.py agent [run keys] | fixed [run keys]")
