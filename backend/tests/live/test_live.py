"""L1-07: live tests against the real Meta API. Skipped unless CHIMERA_LIVE=1.

Budget: the hard live budget in docs/live/budget.json caps the whole phase at
15 image generations and 60 Muse Spark calls (every attempt counts). Every call
is logged to docs/LIVE_LOG.md and recorded (key-free) to tests/fixtures/recorded/.
Outputs (identification table, run JSON, images) go to docs/live/.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from app.config import REPO_ROOT, Settings

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("CHIMERA_LIVE") != "1", reason="live Meta API tests need CHIMERA_LIVE=1"),
]

LIVE = Path(__file__).resolve().parents[1] / "fixtures" / "live"
DOCS = REPO_ROOT / "docs" / "live"
DATA = REPO_ROOT / "data" / "chimera_data.json"
if not DATA.exists():  # L1-08: fall back to the real-schema fixture, and say so in the outputs
    DATA = Path(__file__).resolve().parents[1] / "fixtures" / "chimera_data.real_schema.json"

if os.environ.get("CHIMERA_LIVE") == "1":
    os.environ.setdefault("CHIMERA_LIVE_BUDGET_FILE", str(DOCS / "budget.json"))
    os.environ.setdefault("CHIMERA_LIVE_LOG", str(REPO_ROOT / "docs" / "LIVE_LOG.md"))
    os.environ.setdefault("CHIMERA_RECORD_DIR", str(Path(__file__).resolve().parents[1] / "fixtures" / "recorded"))

EXPECTED = {
    "lion": "lion",
    "tiger": "tiger",
    "horse": "horse",
    "donkey": "donkey",
    "bald_eagle": "bald_eagle",
    "common_octopus": "common_octopus",
}


def fixture(name: str) -> Path:
    return next(LIVE.glob(f"{name}.*"))


def live_settings(tmp: Path) -> Settings:
    return Settings(chimera_mode="real", data_path=str(DATA), local_data_dir=str(tmp), retry_base_seconds=1.0,
                    retry_max_attempts=2, runs_per_minute_per_session=100)


# ------------------------------------------------------------------ identification


async def test_identify_all_six_fixtures():
    from app.adapters.meta.client import MetaVision
    from app.adapters.usage import current_step
    from app.data.loader import load_data
    from app.pipeline.steps.match import match_reading

    s = live_settings(Path("/tmp"))
    vision = MetaVision(s.meta_api_base_url, s.meta_api_key or "", s.meta_vision_model, timeout=s.identify_timeout_seconds)
    data = load_data(DATA)
    rows, failures = [], []
    for name, want in EXPECTED.items():
        current_step.set(f"identify:{name}")
        reading = await vision.describe_animal(fixture(name).read_bytes(), "A")
        match = match_reading(data, reading)
        got = match.animal_id if match else None
        rows.append({"fixture": name, "common_name": reading.common_name, "scientific_name": reading.scientific_name,
                     "confidence": reading.confidence, "body_plan": reading.body_plan,
                     "matched": got, "matched_on": match.matched_on if match else None, "expected": want})
        if got != want:
            failures.append(f"{name}: read {reading.common_name} / {reading.scientific_name} -> {got}, expected {want}")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "identify.json").write_text(json.dumps({"data": str(DATA.name), "results": rows}, indent=1) + "\n")
    assert not failures, failures


# ------------------------------------------------------------------ fusions

FUSIONS = {
    "lion_tiger": ("lion", "tiger", None),
    "horse_donkey": ("horse", "donkey", None),
    "bald_eagle_lion": ("bald_eagle", "lion", None),
    "lion_octopus": ("lion", "common_octopus", None),
    "lion_eagle_pinned": ("lion", "bald_eagle", {"head": "A", "body": "auto", "limbs": "B", "covering": "auto", "tail": "auto"}),
}


def graph(asset_a: str, asset_b: str, donors: dict | None) -> dict:
    fuse = {"id": "fuse", "type": "fusion", "version": 2, "position": {"x": 300, "y": 0}}
    if donors:
        fuse["config"] = {"donors": donors}
    return {
        "schemaVersion": 1, "graphId": "live",
        "nodes": [
            {"id": "a", "type": "image-input", "version": 1, "position": {"x": 0, "y": 0}, "data": {"assetId": asset_a}},
            {"id": "b", "type": "image-input", "version": 1, "position": {"x": 0, "y": 200}, "data": {"assetId": asset_b}},
            fuse,
        ],
        "edges": [
            {"id": "e1", "source": "a", "sourcePort": "out", "target": "fuse", "targetPort": "a"},
            {"id": "e2", "source": "b", "sourcePort": "out", "target": "fuse", "targetPort": "b"},
        ],
    }


async def run_fusion(case: str, tmp_path: Path) -> dict:
    from app.main import create_app

    a_name, b_name, donors = FUSIONS[case]
    app = create_app(live_settings(tmp_path))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://live", timeout=60,
                                 headers={"X-Session-Id": "live-session-01"}) as c:
        ids = []
        for n in (a_name, b_name):
            f = fixture(n)
            r = await c.post("/assets", files={"file": (f.name, f.read_bytes(), "image/webp")})
            assert r.status_code == 201, r.text
            ids.append(r.json()["assetId"])
        r = await c.post("/runs", json={"graph": graph(ids[0], ids[1], donors), "nodeId": "fuse"},
                         headers={"Idempotency-Key": f"live-{case}"})
        assert r.status_code == 201, r.text
        run_id = r.json()["id"]
        for _ in range(600):
            run = (await c.get(f"/runs/{run_id}")).json()
            if run["status"] in ("succeeded", "failed", "cancelled", "interrupted"):
                break
            await asyncio.sleep(1)
        out = DOCS / "fusions"
        out.mkdir(parents=True, exist_ok=True)
        if run.get("result"):
            img = await c.get(run["result"]["imageUrl"])
            ext = {"image/webp": "webp", "image/png": "png", "image/jpeg": "jpg"}.get(img.headers["content-type"], "bin")
            (out / f"{case}.{ext}").write_bytes(img.content)
            run["result"]["savedImage"] = f"docs/live/fusions/{case}.{ext}"
        run["inputs"] = {"A": fixture(a_name).name, "B": fixture(b_name).name, "donors": donors, "data": DATA.name}
        (out / f"{case}.json").write_text(json.dumps(run, indent=1, ensure_ascii=False) + "\n")
        return run


def spec_of(run: dict) -> dict:
    assert run["status"] == "succeeded", (run["status"], run.get("error"), [(s["key"], s["status"], s["detail"]) for s in run["steps"]])
    return run["result"]["spec"]


async def test_fusion_lion_tiger(tmp_path):
    spec = spec_of(await run_fusion("lion_tiger", tmp_path))
    tigon = next((h for h in spec["realHybrids"] if h["name"] == "tigon"), None)
    assert tigon and tigon["father"] == "Panthera tigris" and tigon["mother"] == "Panthera leo"


async def test_fusion_horse_donkey(tmp_path):
    spec = spec_of(await run_fusion("horse_donkey", tmp_path))
    assert "mule" in {h["name"] for h in spec["realHybrids"]}


async def test_fusion_bald_eagle_lion(tmp_path):
    spec = spec_of(await run_fusion("bald_eagle_lion", tmp_path))
    assert spec["mythology"] and spec["mythology"][0]["creatureName"] == "griffin"


async def test_fusion_lion_octopus(tmp_path):
    spec = spec_of(await run_fusion("lion_octopus", tmp_path))
    assert [w for w in spec["warnings"] if w["severity"] == "warning"]


async def test_fusion_lion_eagle_pinned(tmp_path):
    spec = spec_of(await run_fusion("lion_eagle_pinned", tmp_path))
    assert spec["partDonors"]["head"] == "A" and spec["partDonors"]["limbs"] == "B"
    assert spec["donorSource"]["head"] == "user" and spec["donorSource"]["limbs"] == "user"
