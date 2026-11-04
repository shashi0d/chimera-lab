"""S2 part 7: the whole fix pack end to end in mock mode, on the E4 live case (rhinoceros beetle x brown bear,
speculative), starting from the beetle exactly as E4 learned it. Parts 1 to 6 each have their own test file;
this one checks they work together through engine.fuse()."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from app.evolution.engine import EvoEngine
from app.evolution.parts import dorsal_wings
from tests.conftest import make_settings, offline_services

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "s2"


@pytest.fixture
def e4_engine(tmp_path: Path) -> EvoEngine:
    store = tmp_path / "learned.json"
    shutil.copy(FIX / "learned_beetle_e4.json", store)
    return EvoEngine(offline_services(make_settings(tmp_path, evo_learned_path=str(store))), offline=True)


async def test_beetle_bear_with_the_full_fix_pack(e4_engine):
    doc = await e4_engine.fuse(sire_name="rhinoceros beetle", dam_name="brown bear", mode="speculative")
    g, tax = doc["genome"], e4_engine.tax
    lp = g["limb_plan"]
    # 1a: no insect wings in the forelimb slot; over budget, so dropped
    assert (lp["forelimbs"]["kind"], lp["hindlimbs"]["kind"]) == ("legs", "legs") and lp["extra_wings"] is None
    assert "dropped part: wings" in g["traits"]["body"]["flags"]
    # 1b: the beetle's class has no tail: its head horn instead; the learned entry was corrected and logged
    assert g["traits"]["tail"]["part"] is None and "european rhinoceros beetle head horn" in lp["appendages"]
    assert not tax.resolve("european_rhinoceros_beetle").winged
    # 1c: the donor is named once in one grouped clause, as materials and shapes
    p = doc["prompt_compiled"]
    details = p[p.index("Details:"):re.search(r"\. (Coat texture|The covering follows)", p).start()]  # S3b
    assert len(re.findall(r"european rhinoceros beetle(?!-type)", details)) == 1
    assert "chitin plates" in details and "exoskeleton" not in details
    # 1d: the silhouette matches the limb plan
    assert "wing" not in g["silhouette"] and "two hind legs" not in g["silhouette"]
    # 2: no notes, no forced choice
    assert "host value" not in p and "forced_choice" not in doc["judge"]
    # 3: code filled the derived lists
    assert g["card_trace"] and [x["id"] for x in g["licenses"]] == ["arthropod_large"]
    # 5: the card names the providers
    assert doc["card"]["providers"]["render"].startswith("meta:")
    # 6 (S3a): inspect ran the plan-blind protocol: structure, integration and placement questions, counts
    keys = {it["key"] for it in doc["inspect"]["before"]["items"]}
    assert {"frame", "head", "no_wings", "whole_animal", "insect_legs", "grows_out", "on_top", "continuous",
            "scattered", "walking_legs", "separate_bodies"} <= keys  # S3b: the exoskeleton covers the legs (RC-R10-16)
    assert doc["inspect"]["before"]["sam_calls"] == 1  # the head horn; absences are never SAM-tested


async def test_a_model_plan_for_a_large_arthropod_pair_is_not_rejected_for_a_code_owned_label(e4_engine):
    # S2 live finding: labels became code-owned (part 3), but the pre-finish check still demanded the RC-R3-09
    # label, which only finish() adds; every large-arthropod model plan was rejected. Labels are now checked
    # on the finished plan only.
    doc = await e4_engine.fuse(sire_name="rhinoceros beetle", dam_name="brown bear", mode="speculative")
    assert doc["model_plan"] == "accepted"
    from app.evolution.physics import LABEL_ARTHROPOD

    assert LABEL_ARTHROPOD in doc["genome"]["labels"]


async def test_mythic_beetle_bear_keeps_dorsal_wings_with_a_license(e4_engine):
    doc = await e4_engine.fuse(sire_name="rhinoceros beetle", dam_name="brown bear", mode="mythic")
    g = doc["genome"]
    assert [x["id"] for x in g["licenses"]] == ["arthropod_large", "insect_wings"]
    from app.evolution.genome import validate_plan

    assert dorsal_wings(validate_plan(g), e4_engine.tax)
    items = [it for it in doc["inspect"]["before"]["items"] if it["sam"] == "wings"]
    assert items and "four walking legs" in items[0]["text"]
