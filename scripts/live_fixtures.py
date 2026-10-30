"""L1-06: generate the six live fixture photos with muse-image-1.0 (text-to-image), once.

Existing files are never regenerated. Every call goes through the hard live budget
(CHIMERA_LIVE_BUDGET_FILE) and is logged to docs/LIVE_LOG.md and recorded (L1-09).
Run: CHIMERA_LIVE=1 .venv/bin/python scripts/live_fixtures.py [name ...]
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("CHIMERA_LIVE_BUDGET_FILE", str(ROOT / "docs" / "live" / "budget.json"))
os.environ.setdefault("CHIMERA_LIVE_LOG", str(ROOT / "docs" / "LIVE_LOG.md"))
os.environ.setdefault("CHIMERA_RECORD_DIR", str(ROOT / "backend" / "tests" / "fixtures" / "recorded"))

from app.adapters.meta.client import MetaImageGen, image_mime  # noqa: E402
from app.adapters.usage import current_step  # noqa: E402
from app.config import Settings  # noqa: E402

OUT = ROOT / "backend" / "tests" / "fixtures" / "live"
SUBJECTS = {
    "lion": "an adult male African lion with a full mane, standing in dry savanna grass",
    "tiger": "an adult Bengal tiger walking along a forest edge",
    "horse": "a bay domestic horse standing in a green paddock, full body side view",
    "donkey": "a grey domestic donkey standing on a dirt path, full body side view",
    "bald_eagle": "a bald eagle perched on a branch, wings folded, full body",
    "common_octopus": "a common octopus (Octopus vulgaris) on a rocky sea floor, arms spread",
}
PROMPT = ("A photorealistic wildlife photograph of {subject}. Natural light, sharp focus, the whole animal clearly "
          "visible and centred, plain uncluttered background, no people, no text, no watermark.")
EXT = {"image/webp": "webp", "image/png": "png", "image/jpeg": "jpg"}


async def main(names: list[str]) -> None:
    s = Settings()
    if not s.meta_api_key:
        raise SystemExit("META_API_KEY is not set")
    gen = MetaImageGen(s.meta_api_base_url, s.meta_api_key, s.meta_image_model, timeout=180)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        if list(OUT.glob(f"{name}.*")):
            print(f"skip {name}: already generated")
            continue
        current_step.set(f"fixture:{name}")
        img = await gen.generate(PROMPT.format(subject=SUBJECTS[name]), [], "1:1")
        path = OUT / f"{name}.{EXT[image_mime(img.data)]}"
        path.write_bytes(img.data)
        print(f"wrote {path.name} ({len(img.data)} bytes, {img.content_type}, response {img.response_id}, usage {img.usage})")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(SUBJECTS)))
