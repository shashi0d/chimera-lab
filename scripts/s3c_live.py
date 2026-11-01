"""S3c live runs: the agent end to end (part 3), and the fixed pipeline once per pair for comparison.

    .venv/Scripts/python.exe scripts/s3c_live.py agent [run keys] [--max N]   # 2 repeats per pair, Spark Open drives
    .venv/Scripts/python.exe scripts/s3c_live.py fixed [run keys] [--max N]   # engine.fuse once per pair (baseline)
    .venv/Scripts/python.exe scripts/s3c_live.py status                       # what is done, partial or to do

Safe to run long and to resume (S3c finish):
- The pairs run one after another in this one foreground process (no background shells). `--max N` stops after N
  new creatures, so each invocation can stay short; rerun to continue.
- An agent creature is saved after every tool step: trace.json, trace.md, messages.json, candidates.json, each
  image (written to its folder when it arrives) with its exact prompt, plan and critic answers. doc.json is written
  last and marks the creature finalized.
- A rerun skips every pair and repeat with doc.json on disk. A folder without doc.json (a run that stopped midway)
  is kept as <repeat>_partialN for the record and that repeat starts again.

Keys come from .env and are never printed or saved. Caps are runaway guards only on top of the shared counter
docs/live/budget.json. Outputs: docs/evolution/live/s3c/<agent|fixed>/<run>/<repeat>/.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3a_live as S

os.environ.update({"CHIMERA_LIVE_MAX_IMAGES": "260", "CHIMERA_LIVE_MAX_SPARK": "900", "CHIMERA_LIVE_MAX_SAM": "260",
                   "CHIMERA_LIVE_MAX_SPARK_BASETEN": "1400"})

from app.adapters.usage import current_step  # noqa: E402

OUT = S.LIVE / "s3c"
S.OUT = OUT
REPEATS = 2
# key, sire, dam, mode, held out (the S3c finish order)
RUNS = [
    ("tortoise_goat", "tortoise", "domestic goat", "realistic", False),  # the tie case
    ("fox_owl", "red fox", "barn owl", "speculative", True),  # held out: never used for tuning
    ("crab_wolf", "crab", "gray wolf", "speculative", False),
    ("beetle_bear", "rhinoceros beetle", "brown bear", "speculative", False),
]


def w(path: Path, data: Any) -> None:
    """Write through a temp file and rename, so a stop mid-write never leaves a half file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, bytes):
        tmp.write_bytes(data)
    elif isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def critic_rows(raw: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Each item with every critic's answer, the deciding status (Meta) and the pair status (information)."""
    if not raw:
        return []
    return [{"key": r["key"], "group": r["group"], "text": r["text"], "expect": r.get("expect"),
             "answers": r.get("answers"), "status": r["status"], "pair_status": r.get("pair_status"),
             "sam_found": r.get("sam_found")} for r in raw.get("items", [])]


def save_step(vdir: Path, run: Any) -> None:
    """Everything the run has so far (images are already in vdir: the run writes them there)."""
    w(vdir / "trace.json", run.trace)
    w(vdir / "trace.md", run.trace_md())
    w(vdir / "messages.json", run.messages)
    w(vdir / "candidates.json", run.state.candidates or [])
    if run.session is not None:
        w(vdir / "plan_current.json", run.session.plan.model_dump())
    imgs = {}
    for iid in run.state.order:
        im = run.state.images[iid]
        if not (vdir / f"{iid}_prompt.txt").exists():
            w(vdir / f"{iid}_prompt.txt", im.prompt)
            if im.extra.get("prompt_compiled"):
                w(vdir / f"{iid}_prompt_compiled.txt", im.extra["prompt_compiled"])
            w(vdir / f"{iid}_plan.json", im.plan.model_dump())
        imgs[iid] = {"file": im.path.name, "kind": im.kind, "parent": im.parent, "plan_id": im.plan_id,
                     "verdict": (im.inspect or {}).get("verdict"), "failures": (im.inspect or {}).get("failures"),
                     "drift": (im.inspect or {}).get("drift"), "critic": critic_rows(im.raw_inspect),
                     "decision": ((im.raw_inspect or {}).get("items") and "meta_spark decides") or None}
    w(vdir / "critic.json", imgs)
    w(vdir / "progress.json", {"calls": run.state.calls, "renders": run.state.renders, "edits": run.state.edits,
                               "images": run.state.order, "finalized": run.state.finalized is not None,
                               "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S")})


def save_final(vdir: Path, doc: dict[str, Any], run: Any) -> None:
    save_step(vdir, run)
    if doc.get("genome"):
        im = run.state.images[doc["image_id"]]
        w(vdir / "plan.json", doc["genome"])
        w(vdir / "image.webp", im.load())
        w(vdir / "prompt_final.txt", doc["prompt"])
        w(vdir / "prompt_compiled.txt", doc["prompt_compiled"])
    w(vdir / "doc.json", {k: v for k, v in doc.items() if k not in ("genome", "inspect", "trace")})  # last: done


def claim(vdir: Path) -> bool:
    """True when this repeat must run. A finalized one is skipped; a partial one is kept aside and redone."""
    if (vdir / "doc.json").exists():
        return False
    if vdir.exists() and any(vdir.iterdir()):
        k = 1
        while (aside := vdir.with_name(f"{vdir.name}_partial{k}")).exists():
            k += 1
        vdir.rename(aside)
        print("partial run kept as", aside.name, "- starting", vdir.name, "again")
    return True


def log_calls(part: str, calls: list[Any], before: dict[str, int], summary: list[dict[str, Any]]) -> None:
    if not calls:
        return
    path = OUT / part / "calls_log.json"
    hist = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    hist.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **S.calls_summary(calls, before), "summary": summary})
    w(path, hist)


def todo(part: str, only: list[str]) -> list[tuple[Any, ...]]:
    reps = int(os.environ.get("S3C_REPEATS", REPEATS)) if part == "agent" else 1
    tag = os.environ.get("S3C_TAG", "")
    out = []
    for key, sire, dam, mode, held in RUNS:
        if only and key not in only:
            continue
        for n in range(1, reps + 1):
            vdir = OUT / part / key / f"r{n}{tag}"
            out.append((key, sire, dam, mode, held, n, vdir))
    return out


async def part_agent(only: list[str], limit: int | None) -> None:
    eng, calls, before = S.setup("agent", os.environ.get("S3C_CACHE", "s3c_agent"))
    summary: list[dict[str, Any]] = []
    try:
        for key, sire, dam, mode, held, n, vdir in todo("agent", only):
            if (vdir / "doc.json").exists():
                print("done already", key, vdir.name)
                continue
            if limit is not None and len(summary) >= limit:
                print(f"stopping after {limit} new creature(s); rerun to continue")
                break
            claim(vdir)
            current_step.set(f"s3c:agent:{key}:{vdir.name}")
            vdir.mkdir(parents=True, exist_ok=True)
            try:
                doc, run = await eng.agent_fuse(sire, dam, mode, seed=n - 1, image_dir=vdir,
                                                on_step=lambda r, _s, d=vdir: save_step(d, r))
            except Exception as e:  # noqa: BLE001 - recorded; the folder stays partial and a rerun redoes it
                w(vdir / "error.json", {"error": f"{type(e).__name__}: {e}"})
                print("ERROR", key, n, type(e).__name__, str(e)[:300])
                summary.append({"run": key, "repeat": n, "error": f"{type(e).__name__}: {str(e)[:200]}"})
                continue
            save_final(vdir, doc, run)
            rem = (doc.get("card") or {}).get("remaining_failures")
            summary.append({"run": key, "repeat": n, "held_out": held, "renders": run.state.renders,
                            "edits": run.state.edits, "tool_calls": run.state.calls, "stop": run.state.stop,
                            "final_image": doc.get("image_id"), "remaining": rem,
                            "host": (doc.get("genome") or {}).get("host")})
            print(key, n, "| renders", run.state.renders, "| calls", run.state.calls, "| remaining",
                  [r["key"] for r in rem or []], "| stop", run.state.stop, flush=True)
    finally:
        log_calls("agent", calls, before, summary)


async def part_fixed(only: list[str], limit: int | None) -> None:
    """The fixed pipeline once per pair (seed 0), for the agent-vs-pipeline comparison. A structural tie has no
    automatic host any more (D-085): the run records needs_choice and then fuses with the first-named parent, the
    rule the agent replaced, so the two can be compared."""
    eng, calls, before = S.setup("fixed", os.environ.get("S3C_CACHE", "s3c_fixed"))
    summary: list[dict[str, Any]] = []
    try:
        for key, sire, dam, mode, _held, _n, vdir in todo("fixed", only):
            if (vdir / "doc.json").exists():
                print("done already", key)
                continue
            if limit is not None and len(summary) >= limit:
                print(f"stopping after {limit} new creature(s); rerun to continue")
                break
            claim(vdir)
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
                summary.append({"run": key, "error": f"{type(e).__name__}: {str(e)[:200]}"})
                continue
            files = eng.services.settings.resolved_local_dir() / "files"
            w(vdir / "image.webp", (files / doc["image_key"]).read_bytes())
            if doc.get("first_image_key") and (files / doc["first_image_key"]).exists():
                w(vdir / "first_pass.webp", (files / doc["first_image_key"]).read_bytes())
            w(vdir / "plan.json", doc["genome"])
            w(vdir / "prompt_compiled.txt", doc["prompt_compiled"])
            w(vdir / "prompt_final.txt", doc["prompt"])
            w(vdir / "critic.json", {"before": critic_rows(doc["inspect"]["before"]),
                                     "after": critic_rows(doc["inspect"].get("after")),
                                     "kept": doc["inspect"]["kept"]})
            w(vdir / "doc.json", {**{k: v for k, v in doc.items() if k not in ("genome", "inspect", "judge")},
                                  "tie_note": note})
            ins = doc["inspect"].get("after") or doc["inspect"]["before"]
            fails = [(f["key"], f["status"]) for f in ins["failures"]]
            summary.append({"run": key, "kept": doc["inspect"]["kept"], "signals": fails, "tie_note": note,
                            "host": doc["genome"]["host"]})
            print(key, "| kept", doc["inspect"]["kept"], "| signals", fails, flush=True)
    finally:
        log_calls("fixed", calls, before, summary)


def status() -> None:
    for part in ("agent", "fixed"):
        for key, *_rest, n, vdir in todo(part, []):
            st = "done" if (vdir / "doc.json").exists() else "partial" if vdir.exists() else "to do"
            print(f"{part:6} {key:14} {vdir.name:4} {st}")


def _args(argv: list[str]) -> tuple[list[str], int | None]:
    limit = None
    if "--max" in argv:
        i = argv.index("--max")
        limit = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    return argv, limit


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    keys, lim = _args(sys.argv[2:])
    if cmd == "agent":
        asyncio.run(part_agent(keys, lim))
    elif cmd == "fixed":
        asyncio.run(part_fixed(keys, lim))
    elif cmd == "status":
        status()
    else:
        sys.exit("usage: s3c_live.py agent|fixed [run keys] [--max N] | status")
