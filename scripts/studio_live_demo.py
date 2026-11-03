"""Run a paid, live studio concept and revision of the monkey/spider example."""
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)
from app.config import Settings
from app.main import create_app


async def main():
    out = ROOT / "docs" / "evolution" / "live" / "studio_demo"
    out.mkdir(parents=True, exist_ok=True)
    settings = Settings(chimera_mode="real", local_data_dir=str(ROOT / ".localdata" / "studio_demo"), evo_seed_on_start=False,
                        evo_daily_runs=10, evo_visitor_daily_runs=10)
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                 headers={"X-Session-Id": "studio-live-demo"}, timeout=None) as client:
        print("Generating concept with Baseten and Meta...", flush=True)
        r = await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider",
            "brief": "I want a monkey's upper body with the rest of its body being a spider's hips and eight spider legs."})
        print("Concept status:", r.status_code, flush=True)
        r.raise_for_status()
        concept = r.json()
        (out / "concept.json").write_text(json.dumps(concept, indent=2), encoding="utf-8")
        img = await client.get(concept["imageUrl"])
        img.raise_for_status()
        (out / "concept.webp").write_bytes(img.content)
        print("Revising selected concept with Meta...", flush=True)
        r = await client.post(f"/evo/studio/versions/{concept['id']}/revise",
                              json={"instruction": "Make the spider legs longer and more delicate while keeping the monkey upper body and spider abdomen."})
        print("Revision status:", r.status_code, flush=True)
        r.raise_for_status()
        revised = r.json()
        (out / "revision.json").write_text(json.dumps(revised, indent=2), encoding="utf-8")
        img = await client.get(revised["imageUrl"])
        img.raise_for_status()
        (out / "revision.webp").write_bytes(img.content)
        print("Saved concept and revision to", out, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
