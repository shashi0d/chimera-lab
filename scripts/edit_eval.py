"""Edit bench: run the Lab's three edit tools (Revise, Paint, Draw) on one creature with the live models, so a change
to how we guide the image model can be compared side by side.

    .venv/Scripts/python scripts/edit_eval.py --out <dir> --pipeline baseline   # the code as of the last release
    .venv/Scripts/python scripts/edit_eval.py --out <dir> --pipeline current    # backend/app/agentapi/edit_pipeline.py

Each case writes <out>/<pipeline>/<case>.png plus the guide images it sent, and <out>/index.html shows every
pipeline's result next to the original. Costs one image call per case (plus vision calls for the current pipeline).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SOURCE = ROOT / "frontend" / "public" / "example" / "tiger-bat.webp"
CREATURE = json.loads((ROOT / "frontend" / "src" / "tutorial" / "creature.json").read_text(encoding="utf-8"))

# ------------------------------------------------------------------ test cases (on the 1600x1600 Nightstripe)


def _mask(size: tuple[int, int], draw: Any) -> bytes:
    m = Image.new("RGBA", size, (0, 0, 0, 0))
    draw(ImageDraw.Draw(m))
    out = io.BytesIO()
    m.save(out, "PNG")
    return out.getvalue()


def _sketch(size: tuple[int, int], draw: Any) -> bytes:
    return _mask(size, draw)


SIZE = (1600, 1600)
CASES: list[dict[str, Any]] = [
    {"id": "revise-feathers", "op": "revise", "instruction": "Make its wings feathered like an eagle's, white and gold"},
    {"id": "revise-snow", "op": "revise", "instruction": "Turn it into a snow tiger: white fur with dark grey stripes"},
    {"id": "paint-wing", "op": "paint", "instruction": "Make this wing a feathered bird wing, white and gold",
     "mask": lambda d: d.polygon([(0, 330), (470, 250), (560, 520), (520, 980), (300, 1000), (60, 900), (0, 700)],
                                 fill=(255, 0, 200, 255))},
    {"id": "paint-eyes", "op": "paint", "instruction": "Make the eyes glow bright icy blue",
     "mask": lambda d: (d.ellipse([650, 470, 790, 590], fill=(255, 0, 200, 255)),
                        d.ellipse([810, 470, 950, 590], fill=(255, 0, 200, 255)))},
    {"id": "sketch-horns", "op": "sketch", "instruction": "",
     "sketch": lambda d: (d.line([(720, 420), (690, 330), (640, 250), (600, 210)], fill=(230, 30, 30, 255), width=18,
                                 joint="curve"),
                          d.line([(880, 420), (910, 330), (960, 250), (1000, 210)], fill=(230, 30, 30, 255), width=18,
                                 joint="curve"))},
    {"id": "sketch-tail-spikes", "op": "sketch", "instruction": "spikes along the tail",
     "sketch": lambda d: [d.polygon([(1150 + i * 22, 1080 + i * 30), (1185 + i * 22, 1020 + i * 30),
                                     (1200 + i * 22, 1095 + i * 30)], outline=(30, 90, 230, 255), width=8)
                          for i in range(5)]},
]


def doc() -> dict[str, Any]:
    v = CREATURE["version"]
    return {"profile": v["card"]["profile"] if v.get("card") else v.get("profile"), "style": "anime",
            "generation": {"parents": [{"commonName": "Tiger"}, {"commonName": "Bat"}]}, "referenceOnly": True}


# ------------------------------------------------------------------ pipelines


async def baseline(svc: Any, settings: Any, case: dict[str, Any], original: bytes) -> tuple[bytes, dict[str, bytes]]:
    """The edit code as released (lab.py before edit_pipeline.py): its prompts and guides, called the same way."""
    from app.adapters.retrying import RetryingImageGen
    from app.agentapi import lab as old  # run before edit_pipeline.py replaced these

    gen = RetryingImageGen(svc.image_gen, settings)
    d = doc()
    bg = str(settings.evo_fusion_background).strip()
    if case["op"] == "revise":
        prompt = ("Revise the image according to the creator's instruction. Keep the creature, art style, framing and "
                  "everything not mentioned as similar as possible. " + case["instruction"] + " " + bg)
        img = await gen.generate(prompt, [original], "1:1")
        return img.data, {}
    if case["op"] == "paint":
        mask = _mask(SIZE, case["mask"])
        marked = old.mark_region(original, mask)
        prompt = old.paint_prompt(d, case["instruction"]) + " " + bg
        cand = await gen.generate(prompt, [marked, original], "1:1")
        return old.composite_region(original, cand.data, mask), {"guide": marked, "raw": cand.data}
    sketch = _sketch(SIZE, case["sketch"])
    guide = old.composite_sketch(original, sketch)
    prompt = old.sketch_prompt(d, case["instruction"]) + " " + bg
    img = await gen.generate(prompt, [guide, original], "1:1")
    return img.data, {"guide": guide}


async def current(svc: Any, settings: Any, case: dict[str, Any], original: bytes) -> tuple[bytes, dict[str, bytes]]:
    from app.agentapi import edit_pipeline as ep

    d = doc()
    trace: dict[str, bytes] = {}
    if case["op"] == "revise":
        res = await ep.revise(svc, settings, d, original, case["instruction"], chain=None, trace=trace)
    elif case["op"] == "paint":
        res = await ep.paint(svc, settings, d, original, _mask(SIZE, case["mask"]), case["instruction"], trace=trace)
    else:
        res = await ep.sketch(svc, settings, d, original, _sketch(SIZE, case["sketch"]), case["instruction"], trace=trace)
    return res.image.data, trace


# ------------------------------------------------------------------ run and report


def _png(data: bytes) -> bytes:
    out = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(out, "PNG")
    return out.getvalue()


def write_index(out: Path) -> None:
    pipes = sorted(p.name for p in out.iterdir() if p.is_dir())
    rows = []
    for case in CASES:
        cells = ['<td><img src="original.png"><br>original</td>']
        for p in pipes:
            meta_file = out / p / f"{case['id']}.json"
            meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
            extra = "".join(f'<br><a href="{p}/{case["id"]}.{k}.png">{k}</a>' for k in meta.get("trace", []))
            note = meta.get("note", "")
            img = f'<img src="{p}/{case["id"]}.png">' if (out / p / f"{case['id']}.png").exists() else "(none)"
            cells.append(f"<td>{img}<br><b>{p}</b> · {meta.get('seconds', '?')}s{extra}<br><small>{note}</small></td>")
        what = case.get("instruction") or "(drawing only)"
        rows.append(f"<tr><th>{case['id']}<br><small>{case['op']}: {what}</small></th>{''.join(cells)}</tr>")
    (out / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Edit bench</title><style>body{font:13px system-ui;margin:16px}"
        "td,th{vertical-align:top;padding:6px;border-bottom:1px solid #ddd;text-align:left;max-width:360px}"
        "img{width:340px;height:340px;object-fit:contain;background:#fff;border:1px solid #ccc}</style>"
        f"<h1>Edit bench</h1><table>{''.join(rows)}</table>", encoding="utf-8")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pipeline", choices=["baseline", "current"], required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    from app.config import Settings
    from app.services import build_services

    out = Path(args.out)
    (out / args.pipeline).mkdir(parents=True, exist_ok=True)
    settings = Settings(supabase_url=None, supabase_service_key=None, local_data_dir=str(out / ".data"))
    svc = build_services(settings)
    original = SOURCE.read_bytes()
    (out / "original.png").write_bytes(_png(original))
    run = baseline if args.pipeline == "baseline" else current
    cases = [c for c in CASES if not args.only or c["id"] in args.only.split(",")]

    async def one(case: dict[str, Any]) -> None:
        t0 = time.monotonic()
        try:
            result, trace = await run(svc, settings, case, original)
        except Exception as exc:  # keep the other cases going
            (out / args.pipeline / f"{case['id']}.json").write_text(json.dumps({"note": f"failed: {exc}"}))
            print(case["id"], "FAILED", exc)
            return
        (out / args.pipeline / f"{case['id']}.png").write_bytes(_png(result))
        for k, v in trace.items():
            (out / args.pipeline / f"{case['id']}.{k}.png").write_bytes(_png(v) if v[:4] != b"TEXT" else v)
        meta = {"seconds": round(time.monotonic() - t0, 1), "trace": [k for k in trace if trace[k][:4] != b"TEXT"],
                "note": " | ".join(v[4:].decode() for v in trace.values() if v[:4] == b"TEXT")}
        (out / args.pipeline / f"{case['id']}.json").write_text(json.dumps(meta))
        print(case["id"], "ok", meta["seconds"], "s")

    await asyncio.gather(*(one(c) for c in cases))
    write_index(out)
    print("open", out / "index.html")


if __name__ == "__main__":
    asyncio.run(main())
