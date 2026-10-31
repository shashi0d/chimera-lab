"""E2c: the real-hybrid route (a known pair or a documented cross).

1. The prompt opens with the hybrid's name and cross, describes the frame in host terms
   first, then names the donor once in one grouped clause of features.
2. No habitat cue: a documented hybrid is a known animal, not an adapted design (D-056).
3. The critic may name the hybrid itself ("mule"); that counts as naming both parents.
4. The SAM cap defaults to 15.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.adapters import usage
from app.evolution.data import known_pairs
from app.evolution.judge import critic_score, third_animals
from app.evolution.prompt import compile_prompt
from app.evolution.route import LABEL_CLOSE, LABEL_HYBRID, is_real_hybrid, route
from tests.evolution.conftest import plan_for

MULE_OPENER = "A mule (donkey sire x horse mare), a real hybrid animal."
MULE_FRAME = "Horse-sized body, deep chest, long back, long neck, horse proportions"
MULE_DONOR = "with the donkey's long ears, short thick head, short upright mane, thin legs, small hooves and tufted tail"

# Every concrete (sire, dam) a known pair covers.
PAIRS = sorted({(s, d) for p in known_pairs() for s in p["sire"] for d in p["dam"] if s != d}
               | {(d, s) for p in known_pairs() if p.get("either_order") for s in p["sire"] for d in p["dam"] if s != d})


def _after_opener(prompt: str) -> str:
    return prompt.split("a real hybrid animal.", 1)[1]


def _count(text: str, name: str) -> int:
    return len(re.findall(rf"\b{re.escape(name)}(?!-like|-sized)\b", text, re.IGNORECASE))


# ------------------------------------------------------------------ 1. prompt


@pytest.mark.parametrize("seed", range(3))
def test_mule_prompt_order_and_wording(engine, seed):
    g, r = plan_for(engine, "donkey", "horse", seed=seed)
    assert is_real_hybrid(r) and is_real_hybrid(g)
    p = compile_prompt(g, engine.tax)
    assert p.startswith(MULE_OPENER + " " + MULE_FRAME + ", " + MULE_DONOR + "; plain coat, no stripes or spots."), p
    rest = _after_opener(p)
    assert rest.index(MULE_FRAME) < rest.index("donkey")  # frame in host terms first
    assert _count(rest, "donkey") == 1  # the donor is named once, not per detail
    assert "Silhouette:" not in p and "Details:" not in p and "Host frame" not in p


def test_liger_prompt_opens_with_name_and_cross(engine):
    g, _ = plan_for(engine, "lion", "tiger")
    p = compile_prompt(g, engine.tax)
    assert p.startswith("A liger (lion sire x tiger dam), a real hybrid animal. Very large cat body"), p
    rest = _after_opener(p)
    assert _count(rest, "tiger") == 1 and "faint tiger-type stripes at about 30 percent" in rest


def test_hinny_prompt(engine):
    p = compile_prompt(plan_for(engine, "horse", "donkey")[0], engine.tax)
    assert p.startswith("A hinny (horse stallion x donkey jenny), a real hybrid animal. Equine body"), p
    assert _count(_after_opener(p), "donkey") == 1


@pytest.mark.parametrize("sire,dam", PAIRS)
def test_every_known_pair_uses_the_real_hybrid_prompt(engine, sire, dam):
    g, r = plan_for(engine, sire, dam)
    assert is_real_hybrid(r) and r.pair
    p = compile_prompt(g, engine.tax)
    a, b = (engine.tax.animals[x].common_name.lower() for x in (sire, dam))
    assert re.match(rf"An? {re.escape(r.pair['name'])} \(.+\), a real hybrid animal\. ", p), p
    assert "{host}" not in p and "Habitat cue" not in p and "Details:" not in p
    for donor in {a, b} - ({engine.tax.animals[g.host].common_name.lower()} if g.host else set()):
        assert _count(_after_opener(p), donor) <= 1, p


def test_other_routes_keep_the_design_prompt(engine):
    for sire, dam, label in [("lion", "eagle", None), ("tiger", "leopard", LABEL_CLOSE)]:
        g, r = plan_for(engine, sire, dam)
        assert not is_real_hybrid(r) and (label is None or label in r.labels)
        p = compile_prompt(g, engine.tax)
        assert p.startswith("Silhouette: ") and "real hybrid animal" not in p and "Habitat cue" in p


def test_polish_must_keep_the_opener(engine):
    from app.evolution.prompt import check_polish

    g, _ = plan_for(engine, "donkey", "horse")
    p = compile_prompt(g, engine.tax)
    assert check_polish(p, p.replace("tufted tail", "tufted tail,"), g, engine.tax) is None
    assert check_polish(p, p.replace("A mule", "A donkey"), g, engine.tax) == "silhouette sentence changed"


# ------------------------------------------------------------------ 2. habitat


@pytest.mark.parametrize("habitat", [None, "forest", "grassland", "desert", "tundra"])
@pytest.mark.parametrize("sire,dam", [("donkey", "horse"), ("lion", "tiger"), ("polar_bear", "brown_bear")])
def test_real_hybrids_get_no_habitat_cue(engine, sire, dam, habitat):
    g, r = plan_for(engine, sire, dam, habitat=habitat)
    assert g.habitat.adjustments == [] and g.habitat.visible_trait is None
    assert not any(f.startswith("habitat") for tr in g.traits.values() for f in tr.flags)
    assert not any(f.startswith("habitat") for f in g.size.flags)
    assert "RC-R4-11" not in g.card_trace
    from app.evolution.checks import soft_penalties

    assert "RC-R4-11" not in {i["card"] for i in soft_penalties(g, r, engine.tax)[0]}


def test_liger_pattern_strength_is_not_moved_by_habitat(engine):
    open_g, _ = plan_for(engine, "lion", "tiger", habitat="grassland")
    closed_g, _ = plan_for(engine, "lion", "tiger", habitat="forest")
    assert open_g.traits["coat_pattern"].strength == closed_g.traits["coat_pattern"].strength == pytest.approx(0.3)


def test_habitat_deltas_from_a_model_plan_are_undone(engine):
    g, r = plan_for(engine, "lion", "tiger")
    raw = g.model_copy(deep=True)
    raw.traits["coat_pattern"].strength = 0.4
    raw.traits["coat_pattern"].flags.append("habitat pattern +0.10")
    raw.habitat.adjustments = ["bolder tiger-type stripes for a closed habitat"]
    raw.habitat.visible_trait = raw.habitat.adjustments[0]
    out = engine.finish(raw, r)
    assert out.traits["coat_pattern"].strength == pytest.approx(0.3)
    assert out.habitat.adjustments == [] and out.habitat.visible_trait is None


def test_close_relatives_still_get_a_habitat_cue(engine):
    g, _ = plan_for(engine, "tiger", "leopard", habitat="grassland")
    assert g.habitat.visible_trait and "fainter leopard-type rosettes" in " ".join(g.habitat.adjustments)


# ------------------------------------------------------------------ 3. critic


def test_hybrid_name_counts_as_both_parents(tax):
    donkey, horse, lion, tiger = (tax.animals[x] for x in ("donkey", "horse", "lion", "tiger"))
    one = {"creatures": 1}
    assert critic_score({**one, "animals": ["mule"]}, donkey, horse, ["mule"]) == 1.0
    assert critic_score({**one, "animals": ["Mules"]}, donkey, horse, ["mule"]) == 1.0
    assert critic_score({**one, "animals": ["donkey", "horse"]}, donkey, horse, ["mule"]) == 1.0
    assert critic_score({**one, "animals": ["donkey"]}, donkey, horse, ["mule"]) == 0.5
    assert critic_score({**one, "animals": ["mule"]}, donkey, horse) == 0.0  # not on the real-hybrid route
    assert critic_score({**one, "animals": ["liger"]}, lion, tiger, ["liger"]) == 1.0
    assert critic_score({"creatures": 2, "animals": ["liger"]}, lion, tiger, ["liger"]) == 0.0
    assert critic_score({**one, "animals": ["muledeer"]}, donkey, horse, ["mule"]) == 0.0  # whole word only


def test_aliases_count_and_are_not_third_animals(tax):
    polar, brown = tax.animals["polar_bear"], tax.animals["brown_bear"]
    r = route(polar, brown, tax)
    assert critic_score({"creatures": 1, "animals": ["pizzly bear"]}, polar, brown, ["pizzly"]) == 1.0
    assert third_animals({"animals": ["pizzly", "grolar bear"]}, polar, brown, tax, r) == []


def _scripted(engine, animals: list[str]):
    async def critic(image: bytes) -> dict[str, Any]:
        return {"animals": animals, "creatures": 1, "notes": "scripted"}

    engine.spark.critic = critic  # type: ignore[method-assign]


async def test_fuse_mule_uses_the_real_hybrid_prompt(engine):
    # E2d replaced the open critic on this route with a checklist (tests/evolution/test_e2d_checklist.py).
    doc = await engine.fuse(sire_name="donkey", dam_name="horse")
    assert LABEL_HYBRID in doc["genome"]["labels"] and doc["prompt_compiled"].startswith(MULE_OPENER)
    assert doc["judge"]["third_animal"] == [] and len(doc["render_attempts"]) == 1


async def test_fuse_chimera_does_not_accept_a_hybrid_name(engine):
    _scripted(engine, ["liger"])
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert doc["judge"]["scores"]["critic"] == 0.0
    assert doc["render_attempts"][0]["third_animal"] == ["liger"]


# ------------------------------------------------------------------ 4. SAM cap


def test_sam_cap_defaults_to_15(monkeypatch):
    for k in ("CHIMERA_LIVE_MAX_SAM", "CHIMERA_LIVE_MAX_IMAGES", "CHIMERA_LIVE_MAX_SPARK"):
        monkeypatch.delenv(k, raising=False)
    assert usage._limits() == {"image": 15, "spark": 60, "sam": 15}
