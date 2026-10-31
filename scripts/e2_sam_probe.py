"""E2 step 3: exactly one live SAM 3.1 call, raw response saved for the mask parser.

Usage (from the repo root, META_API_KEY in the environment):
    .venv/Scripts/python.exe scripts/e2_sam_probe.py

No retry: one attempt, counted against the live budget (docs/live/budget.json, kind "sam").
The response is saved unelided (the mask data is what the parser needs); the request's
image data URL is elided. Exit 2 on model_not_found or an auth error.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("CHIMERA_LIVE_BUDGET_FILE", str(ROOT / "docs" / "live" / "budget.json"))
os.environ.setdefault("CHIMERA_LIVE_LOG", str(ROOT / "docs" / "LIVE_LOG.md"))
os.environ.setdefault("CHIMERA_LIVE_MAX_SAM", "8")

from app.adapters.meta.client import _elide
from app.adapters.usage import budget_used, current_step
from app.config import Settings
from app.errors import ChimeraError
from app.evolution.live import MetaSegmenter, build_sam_request

IMAGE = ROOT / "docs" / "live" / "fusions" / "horse_donkey.webp"
OUT = ROOT / "backend" / "tests" / "fixtures" / "recorded"


def _write(name: str, doc: dict) -> Path:
    text = json.dumps(doc, indent=1, ensure_ascii=False)
    key = os.environ.get("META_API_KEY") or ""
    if (key and key in text) or "Bearer " in text:
        raise RuntimeError("refusing to save a recording that contains credentials")
    path = OUT / name
    path.write_text(text + "\n", encoding="utf-8")
    return path


async def main() -> int:
    settings = Settings(chimera_mode="real")
    if not settings.meta_api_key:
        print("META_API_KEY is not set")
        return 3
    os.environ.setdefault("META_API_KEY", settings.meta_api_key)  # a .env key: keep the recording leak check armed
    seg = MetaSegmenter(settings)
    body = build_sam_request(IMAGE.read_bytes(), "animal", seg.model_id)
    print("budget before:", budget_used())
    current_step.set("e2-sam-probe")
    try:
        payload = await seg.http.call("sam", "sam", seg.model_id, body, responses=True, raw=True)  # one attempt
    except ChimeraError as e:
        detail = {"code": e.code.value, "message": e.message, **e.details}
        print("budget after:", budget_used())
        print("SAM probe failed:", json.dumps(detail, ensure_ascii=False, default=str)[:2000])
        _write("sam_error-01.json", {"purpose": "sam", "image": IMAGE.name, "request": _elide(body), "error": detail})
        return 2
    print("budget after:", budget_used())
    path = _write("sam-01.json", {"purpose": "sam", "image": IMAGE.name, "request": _elide(body), "response": payload})
    print("saved", path.relative_to(ROOT), f"({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
