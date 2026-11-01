"""S5 live benchmark: each case of data/evo_benchmark.json once with the agent and once with the fixed pipeline.

    .venv/Scripts/python.exe scripts/s5_live.py run [case ids] [--max N]   # next creature(s): b01 agent, b01 fixed, ...
    .venv/Scripts/python.exe scripts/s5_live.py status
    .venv/Scripts/python.exe scripts/s5_live.py score                      # scores.json from the saved results

Resumable (S3c, D-090): the agent's run is saved after every tool step; doc.json is written last and marks a
creature done; a rerun skips done creatures and keeps a partial folder as <kind>_partialN. One foreground process,
`--max 1` per invocation. Caps per creature as in S3c (evo_config agent: 4 renders, 30 tool calls, 6 edits).

Outputs per creature, docs/evolution/live/s5/<case>/<agent|fixed>/: image.webp, plan.json, prompt_final.txt,
prompt_compiled.txt, critic.json (each critic's answer per item), inspect_final.json (the final image's full inspect:
rows, failures, both critics' descriptions), anatomy_map.png and anatomy_map.json, meta.json (wall time, renders,
edits, tool calls, calls per provider and purpose), doc.json; the agent adds trace.json, trace.md, messages.json,
candidates.json and every image with its prompt and plan.
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
import s3c_live as C

os.environ.update({"CHIMERA_LIVE_MAX_IMAGES": "320", "CHIMERA_LIVE_MAX_SPARK": "1000", "CHIMERA_LIVE_MAX_SAM": "480",
                   "CHIMERA_LIVE_MAX_SPARK_BASETEN": "2000"})

from app.adapters.usage import current_calls, current_step  # noqa: E402
from app.evolution.anatomy import anatomy_map  # noqa: E402
from app.evolution.benchmark import cases, score_all  # noqa: E402
from app.evolution.genome import Genome  # noqa: E402

OUT = S.LIVE / "s5"
S.OUT = OUT
w, claim = C.w, C.claim


def by_provider(calls: list[Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for c in calls:
        prov = getattr(c, "provider", "") or ("baseten" if c.kind == "spark_baseten" else "meta")
        key = f"{c.kind}:{c.purpose}"
        out.setdefault(prov, {})
        out[prov][key] = out[prov].get(key, 0) + 1
    return out


def todo(only: list[str]) -> list[tuple[dict[str, Any], str, Path]]:
    return [(c, kind, OUT / c["id"] / kind) for c in cases() if not only or c["id"] in only
            for kind in ("agent", "fixed")]


async def run_agent(eng: Any, c: dict[str, Any], vdir: Path) -> dict[str, Any]:
    doc, run = await eng.agent_fuse(c["sire"], c["dam"], c["mode"], seed=0, image_dir=vdir,
                                    on_step=lambda r, _s: C.save_step(vdir, r))
    if not doc.get("genome"):
        raise RuntimeError(f"no creature: {doc.get('error')}")
    C.save_step(vdir, run)
    im = run.state.images[doc["image_id"]]
    w(vdir / "plan.json", doc["genome"])
    w(vdir / "image.webp", im.load())
    w(vdir / "prompt_final.txt", doc["prompt"])
    w(vdir / "prompt_compiled.txt", doc["prompt_compiled"])
    w(vdir / "inspect_final.json", doc["inspect"])
    w(vdir / "anatomy_map.json", doc["card"]["anatomy_map"])
    return {"doc": {k: v for k, v in doc.items() if k not in ("genome", "inspect", "trace")},
            "renders": run.state.renders, "edits": run.state.edits, "tool_calls": run.state.calls,
            "host": doc["genome"]["host"], "stop": run.state.stop, "final_image": doc["image_id"],
            "final_choice": doc["card"].get("final_choice")}


async def run_fixed(eng: Any, c: dict[str, Any], vdir: Path) -> dict[str, Any]:
    note = None
    try:
        doc = await eng.fuse(sire_name=c["sire"], dam_name=c["dam"], mode=c["mode"], seed=0)
    except Exception as e:  # noqa: BLE001
        if "needs_choice" not in str(e):
            raise
        note = "needs_choice on a structural tie (D-085); fused with host=sire (the old rule) to compare"
        doc = await eng.fuse(sire_name=c["sire"], dam_name=c["dam"], mode=c["mode"], seed=0, host="sire")
    files = eng.services.settings.resolved_local_dir() / "files"
    image = (files / doc["image_key"]).read_bytes()
    w(vdir / "image.webp", image)
    if doc.get("first_image_key") and (files / doc["first_image_key"]).exists():
        w(vdir / "first_pass.webp", (files / doc["first_image_key"]).read_bytes())
    insp = doc["inspect"]
    final = insp.get("after") if insp.get("kept") == "edited" and insp.get("after") else insp["before"]
    w(vdir / "plan.json", doc["genome"])
    w(vdir / "prompt_compiled.txt", doc["prompt_compiled"])
    w(vdir / "prompt_final.txt", doc["prompt"])
    w(vdir / "critic.json", {"before": C.critic_rows(insp["before"]), "after": C.critic_rows(insp.get("after")),
                             "kept": insp["kept"]})
    w(vdir / "inspect_final.json", final)
    g = Genome.model_validate(doc["genome"])
    overlay, amap = await anatomy_map(image, g, eng.tax, eng.segmenter, eng.meter)
    w(vdir / "anatomy_map.png", overlay)
    w(vdir / "anatomy_map.json", amap)
    return {"doc": {**{k: v for k, v in doc.items() if k not in ("genome", "inspect", "judge")}, "tie_note": note},
            "renders": 1, "edits": 1 if insp.get("after") else 0, "tool_calls": None, "host": doc["genome"]["host"],
            "kept": insp["kept"], "note": note}


async def run(only: list[str], limit: int | None) -> None:
    engines: dict[str, Any] = {}
    n_new = 0
    for c, kind, vdir in todo(only):
        if (vdir / "doc.json").exists():
            print("done already", c["id"], kind)
            continue
        if limit is not None and n_new >= limit:
            print(f"stopping after {limit} new creature(s); rerun to continue")
            break
        claim(vdir)
        vdir.mkdir(parents=True, exist_ok=True)
        if kind not in engines:
            engines[kind] = S.setup(kind, f"s5_{kind}")[0]
        eng = engines[kind]
        os.environ["CHIMERA_RECORD_DIR"] = str(OUT / "raw" / kind)  # S.setup sets one global record dir
        calls: list[Any] = []  # this creature's calls only
        current_calls.set(calls)
        start = 0
        current_step.set(f"s5:{kind}:{c['id']}")
        t0 = time.monotonic()
        n_new += 1
        try:
            res = await (run_agent if kind == "agent" else run_fixed)(eng, c, vdir)
        except Exception as e:  # noqa: BLE001 - recorded; the folder stays partial and a rerun redoes it
            w(vdir / "error.json", {"error": f"{type(e).__name__}: {e}"})
            print("ERROR", c["id"], kind, type(e).__name__, str(e)[:300])
            continue
        mine = calls[start:]
        meta = {"case": c["id"], "kind": kind, "sire": c["sire"], "dam": c["dam"], "mode": c["mode"],
                "wall_seconds": round(time.monotonic() - t0, 1), "renders": res["renders"], "edits": res["edits"],
                "tool_calls": res["tool_calls"], "host": res["host"], "note": res.get("note"),
                "calls_by_provider": by_provider(mine),
                "failed_calls": sum(1 for x in mine if getattr(x, "outcome", "ok") != "ok"),
                **{k: res[k] for k in ("stop", "final_image", "final_choice", "kept") if k in res}}
        w(vdir / "meta.json", meta)
        w(vdir / "doc.json", res["doc"])  # last: done
        print(c["id"], kind, "| renders", res["renders"], "| calls", res["tool_calls"], "| wall", meta["wall_seconds"],
              "| host", res["host"], flush=True)


def status() -> None:
    for c, kind, vdir in todo([]):
        st = "done" if (vdir / "doc.json").exists() else "partial" if vdir.exists() else "to do"
        print(f"{c['id']} {kind:6} {c['sire']} x {c['dam']} ({c['mode']}): {st}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    keys, lim = C._args(sys.argv[2:])
    if cmd == "run":
        asyncio.run(run(keys, lim))
    elif cmd == "status":
        status()
    elif cmd == "score":
        w(OUT / "scores.json", score_all(OUT))
        print(json.dumps(score_all(OUT)["totals"], indent=1))
    else:
        sys.exit("usage: s5_live.py run [case ids] [--max N] | status | score")
