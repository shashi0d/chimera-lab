"""The four worked examples in ALGORITHM.md section 7, generated in mock mode.

Each asserts routing, host, limb plan and label, plus the example's own claims.
Seeds 0 to 9 are all checked: the invariants must not depend on the random draw.
"""

from __future__ import annotations

import pytest

from app.evolution.genome import BEYOND
from app.evolution.physics import LABEL_NONFLYING, LABEL_SIX
from app.evolution.route import LABEL_CHIMERA, LABEL_HYBRID
from tests.evolution.conftest import plan_for

SEEDS = range(10)


@pytest.mark.parametrize("seed", SEEDS)
def test_example_1_donkey_x_horse_is_the_mule(engine, seed):
    g, r = plan_for(engine, "donkey", "horse", seed=seed)
    assert (r.mode, g.known_pair, g.host) == ("hybrid", "mule", "horse")
    lp = g.limb_plan
    assert (lp.forelimbs.kind, lp.hindlimbs.kind, lp.extra_wings, lp.limb_count()) == ("legs", "legs", None, 4)
    assert g.labels[0] == LABEL_HYBRID
    assert "region mosaic as in mules" in g.processes
    for tag in ("head", "ears", "mane", "limbs", "feet", "coat_texture"):
        assert g.traits[tag].donor == "donkey", tag
    assert g.traits["body"].donor == "horse"
    assert {g.traits[t].donor for t in ("face", "skull") if isinstance(g.traits[t].donor, str)} <= {"donkey"}


@pytest.mark.parametrize("seed", SEEDS)
def test_example_2_lion_x_tiger_is_the_liger(engine, seed):
    g, r = plan_for(engine, "lion", "tiger", seed=seed)
    lion, tiger = engine.tax.animals["lion"], engine.tax.animals["tiger"]
    assert (r.mode, g.known_pair, g.host) == ("hybrid", "liger", "lion")
    assert (g.limb_plan.forelimbs.kind, g.limb_plan.hindlimbs.kind, g.limb_plan.limb_count()) == ("legs", "legs", 4)
    assert g.labels[0] == LABEL_HYBRID
    assert g.size.mass_kg > max(lion.mass_kg, tiger.mass_kg) and BEYOND in g.size.flags  # larger than both
    color = g.traits["coat_color"]
    assert color.op == "BLEND" and color.donor == ["lion", "tiger"] and color.value <= 0.35  # tawny, lion-side
    stripes = g.traits["coat_pattern"]
    assert stripes.op == "OVERLAY" and stripes.donor == "tiger" and stripes.strength <= 0.45  # faint
    assert set(stripes.region) == {"flanks", "legs"}
    mane = g.traits["mane"]
    assert mane.donor is None or (mane.strength or 1.0) <= 0.4  # small or no mane
    assert not (mane.donor and (mane.strength or 1.0) >= 0.7 and stripes.strength >= 0.7)  # never both full


@pytest.mark.parametrize("seed", SEEDS)
def test_example_3_lion_x_eagle_chimera(engine, seed):
    g, r = plan_for(engine, "lion", "eagle", seed=seed)
    assert (r.mode, g.host) == ("chimera", "lion")
    lp = g.limb_plan
    assert (lp.forelimbs.kind, lp.forelimbs.donor, lp.hindlimbs.kind, lp.extra_wings) == ("wings", "golden_eagle", "legs", None)
    assert g.size.mass_kg > 40 and lp.wing_use == "gliding_or_display" and LABEL_NONFLYING in g.labels
    assert g.labels[0] == LABEL_CHIMERA
    for tag in ("coat_pattern", "coat_color", "coat_texture"):
        tr = g.traits[tag]
        assert (tr.op, tr.donor, tr.strength) == ("PATCH", "golden_eagle", 1.0)
        assert tr.region[0] == "forequarters" and len(tr.region) <= 3  # few large patches over the forequarters
    assert g.traits["body"].donor == "lion" and g.traits["head"].donor == "lion"


def test_example_3_mythic_variant_has_six_limbs_with_label(engine):
    g, r = plan_for(engine, "lion", "eagle", myth=True)
    assert (r.mode, g.host) == ("mythic", "lion")
    lp = g.limb_plan
    assert (lp.forelimbs.kind, lp.hindlimbs.kind, lp.extra_wings.kind, lp.limb_count()) == ("legs", "legs", "wings", 6)
    assert g.labels[0] == "mythic composite" and LABEL_SIX in g.labels  # RC-R9-01 vocabulary (E4)


@pytest.mark.parametrize("seed", SEEDS)
def test_example_4_eagle_x_octopus_chimera(engine, seed):
    g, r = plan_for(engine, "eagle", "octopus", seed=seed)
    assert (r.mode, g.host) == ("chimera", "golden_eagle")
    lp = g.limb_plan
    assert (lp.forelimbs.kind, lp.hindlimbs.kind, lp.extra_wings, lp.limb_count()) == ("wings", "legs", None, 4)
    assert g.labels[0] == LABEL_CHIMERA
    assert g.traits["head"].donor == "golden_eagle" and g.traits["face"].donor == "golden_eagle"
    tail = g.traits["tail"]
    assert (tail.donor, tail.part) == ("common_octopus", "tentacles") and "jointless" in tail.note
    skin = g.traits["coat_texture"]
    assert (skin.op, skin.donor) == ("PATCH", "common_octopus")


@pytest.mark.parametrize("sire,dam", [("donkey", "horse"), ("lion", "tiger"), ("lion", "eagle"), ("eagle", "octopus")])
async def test_worked_examples_through_fuse(engine, sire, dam):
    doc = await engine.fuse(sire_name=sire, dam_name=dam)
    prompt = doc["prompt"]
    if doc["route"]["known_pair"]:  # E2c: real hybrids open with name and cross, and get no habitat cue
        assert prompt.startswith(f"A {doc['route']['known_pair']} (") and "Habitat cue" not in prompt
    else:
        assert prompt.startswith("Silhouette: ") and "Habitat cue" in prompt
    assert "fully visible" in prompt and "discernible eyes" in prompt and "One creature, full body" in prompt
    assert doc["meta_calls"] == {"spark": 4, "image": 1, "sam": 1}
    assert doc["model_plan"] == "accepted"
    assert 0 <= doc["genome"]["scores"]["quality"] <= 1
    card = doc["card"]
    assert card["label"] == doc["genome"]["labels"][0]
    assert {w["card"] for w in card["why"]} == set(doc["genome"]["card_trace"])
    assert all(w["source"].startswith("http") for w in card["why"])
