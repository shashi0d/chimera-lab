"""The /evo endpoints (section 5), the rule-card loader (section 2) and engine guards."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import REPO_ROOT
from app.errors import ChimeraError
from app.evolution.card import safe_text
from app.evolution.data import cards
from app.evolution.engine import EvoEngine
from app.evolution.prompt import compile_prompt, has_franchise
from tests.conftest import IMAGES, make_settings
from tests.evolution.conftest import plan_for


def test_loader_matches_committed_cards(tmp_path):
    out = tmp_path / "cards.json"
    res = subprocess.run([sys.executable, str(REPO_ROOT / "scripts/build_rule_cards.py"),
                          str(REPO_ROOT / "docs/evolution/research"), str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    built = json.loads(out.read_text(encoding="utf-8"))
    assert built == json.loads((REPO_ROOT / "data/rule_cards.json").read_text(encoding="utf-8"))
    assert len(built) == 109  # E4: R9 adds 15 cards
    assert {c["doc"].split("_")[0] for c in built} == {f"R{i}" for i in range(1, 10)}  # RESEARCH_SUMMARY skipped
    assert all(set(c) == {"id", "doc", "rule", "applies_to", "strength", "status", "source"} for c in built)


def test_prompts_quote_cards_verbatim(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    text = engine.plan_prompt(g, "task")
    book = cards()
    for cid in book.hard_ids():
        assert f"{cid} (hard): {book[cid].rule}" in text


def test_franchise_names_never_reach_the_prompt(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    g.traits["body"].note = "like Dolcetto from a manga"
    assert not has_franchise(compile_prompt(g, engine.tax))


def test_card_wording_guards():
    assert "debated hypothesis" in safe_text("Floppy ears follow the domestication syndrome", False)
    assert "contested" in safe_text("This myth came from a fossil", False)
    assert "not claimed to be viable" in safe_text("This creature would be viable", True)


async def test_real_mode_refuses_before_any_call(tmp_path):
    svc = SimpleNamespace(settings=make_settings(tmp_path, chimera_mode="real"), image_gen=None)  # no META_API_KEY
    eng = EvoEngine(svc)  # type: ignore[arg-type]
    with pytest.raises(ChimeraError):
        await eng.fuse(sire_name="lion", dam_name="tiger")
    assert eng.meter.counts == {"spark": 0, "image": 0, "sam": 0}


async def test_evo_endpoints(client):
    r = await client.get("/evo/cards")
    assert r.status_code == 200 and r.json()["count"] == 109 and len(r.json()["hard"]) == 17

    r = await client.post("/evo/fuse", json={"sire": {"name": "lion"}, "dam": {"name": "eagle"}})
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body["genome"]["id"]
    assert body["route"]["mode"] == "chimera" and body["card"]["label"].startswith("speculative chimera")

    r = await client.get(f"/evo/creature/{cid}")
    assert r.status_code == 200 and r.json()["genome"]["id"] == cid and r.json()["image_url"]

    r = await client.post("/evo/evolve", json={"creature_id": cid, "rounds": 1, "batch": 2})
    assert r.status_code == 200, r.text
    assert r.json()["cells"] and r.json()["meta_calls"] == {"spark": 1 + 2 * 4, "image": 2, "sam": 2}

    r = await client.post(f"/evo/creature/{cid}/edit", json={"gene": "habitat", "value": "desert"})
    assert r.status_code == 200, r.text
    child = r.json()["genome"]
    assert child["habitat"]["name"] == "desert" and child["lineage"]["parent_ids"] == [cid]

    r = await client.post(f"/evo/creature/{cid}/edit", json={"gene": "traits.coat_color",
                                                              "value": {"op": "BLEND", "donor": ["lion", "golden_eagle"], "value": 0.5}})
    assert r.status_code == 422 and r.json()["error"]["details"]["violations"][0]["card"] == "RC-R5-01"

    assert (await client.get("/evo/creature/crt_missing")).status_code == 404
    assert (await client.post("/evo/fuse", json={"sire": {"name": "lion"}, "dam": {"name": "unicorn"}})).status_code == 422
    assert (await client.post("/evo/fuse", json={"sire": {}, "dam": {"name": "lion"}})).status_code == 422
    assert (await client.get("/health")).status_code == 200  # the current app keeps working


async def test_fuse_from_image_identifies_with_one_spark_call(client):
    lion = base64.b64encode((IMAGES / "lion.jpg").read_bytes()).decode()
    r = await client.post("/evo/fuse", json={"sire": {"image_b64": lion}, "dam": {"name": "tiger"}})
    assert r.status_code == 200, r.text
    assert r.json()["genome"]["known_pair"] == "liger"
    assert r.json()["meta_calls"] == {"spark": 6, "image": 1, "sam": 1}  # identify + plan, polish, 3 critics


def test_fixture_image_exists():
    assert Path(IMAGES / "lion.jpg").exists()
