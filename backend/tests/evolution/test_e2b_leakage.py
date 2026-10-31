"""E2b: third-animal leakage. One test group per fix:

1. pattern phrases always name donor and type, or say "plain coat, no stripes or spots"
2. mule and hinny overrides have a plain coat
3. the habitat step only scales an existing pattern, never adds markings
4. a polish that adds an animal or contradicts the limb plan or mane is rejected
5. a critic naming a third animal triggers one re-render with the compiled prompt
6. SAM is prompted with "animal"; a mask in pieces is one creature when the critic says so
"""

from __future__ import annotations

import itertools
import re
from typing import Any

import pytest

from app.evolution.data import PLAIN_COAT, coat_pattern
from app.evolution.judge import SAM_PROMPT, silhouette_score, third_animals
from app.evolution.prompt import BARE_PATTERN, PATTERN_WORDS, check_polish, compile_prompt
from tests.evolution.conftest import plan_for

SWEEP = ["lion", "tiger", "plains_zebra", "horse", "donkey", "leopard", "golden_eagle", "common_octopus", "giraffe",
         "polar_bear", "brown_bear", "dromedary_camel", "llama", "green_iguana", "emperor_scorpion", "cheetah"]
ALLOWED = re.compile(r"\b[\w'-]+-type [^;.]+|no stripes or spots")


def _leftover_pattern_words(prompt: str, silhouette: str, parents: list[str]) -> list[str]:
    body = ALLOWED.sub("", prompt.replace(silhouette, ""))  # override silhouettes quote sources (zebroid stripes)
    for name in parents:  # a parent's own name ("plains zebra", "leopard") is not a pattern word
        body = re.sub(re.escape(name), "", body, flags=re.IGNORECASE)
    return PATTERN_WORDS.findall(body)


# ------------------------------------------------------------------ 1. prompt compiler


@pytest.mark.parametrize("sire,dam", list(itertools.permutations(SWEEP, 2)))
def test_every_pattern_phrase_names_donor_and_type(engine, sire, dam):
    for myth in (False, True):
        g, _ = plan_for(engine, sire, dam, myth=myth)
        p = compile_prompt(g, engine.tax)
        sil = g.silhouette.strip().rstrip(".")
        assert not BARE_PATTERN.findall(p.replace(sil[0].upper() + sil[1:], "")), p
        names = [engine.tax.animals[x].common_name for x in (g.parents.sire, g.parents.dam)]
        assert not _leftover_pattern_words(p, sil[0].upper() + sil[1:], names), p
        if not (coat_pattern(sire) or coat_pattern(dam)):
            assert PLAIN_COAT in p, p


def test_named_examples(engine):
    liger, _ = plan_for(engine, "lion", "tiger")
    assert "faint tiger-type stripes at about" in compile_prompt(liger, engine.tax)
    griffin, _ = plan_for(engine, "lion", "eagle")
    p = compile_prompt(griffin, engine.tax)
    assert PLAIN_COAT in p and "lion-type" not in p and "golden eagle-type" not in p
    tiger_eagle, _ = plan_for(engine, "tiger", "eagle")
    assert "tiger-type stripes" in compile_prompt(tiger_eagle, engine.tax)


def test_model_notes_with_patterns_or_limb_conflicts_are_dropped(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    g.traits["limbs"].note = "limbs are four lion legs; no forelimb-to-wing substitution"
    g.traits["coat_color"].note = "more patterned, irregular coat markings"
    p = compile_prompt(g, engine.tax)
    assert "four lion legs" not in p and "markings" not in p
    assert "golden eagle wings in place of the forelegs" in p


def test_hybrid_pattern_donor_must_have_a_pattern(engine, tax):
    for seed in range(10):
        g, _ = plan_for(engine, "polar_bear", "brown_bear", seed=seed)  # neither bear has stripes or spots
        assert g.traits["coat_pattern"].donor is None and "plain" in g.traits["coat_pattern"].flags


# ------------------------------------------------------------------ 2. mule and hinny


@pytest.mark.parametrize("sire,dam", [("donkey", "horse"), ("horse", "donkey")])
@pytest.mark.parametrize("seed", range(5))
def test_mule_and_hinny_have_a_plain_coat(engine, sire, dam, seed):
    g, r = plan_for(engine, sire, dam, seed=seed)
    assert r.pair["id"] in ("mule", "hinny")
    tr = g.traits["coat_pattern"]
    assert (tr.op, tr.donor, tr.strength) == ("PICK", None, None) and "plain" in tr.flags
    p = compile_prompt(g, engine.tax)
    assert PLAIN_COAT in p and "donkey-type" not in p and "stripe" not in p.replace("no stripes or spots", "")


# ------------------------------------------------------------------ 3. habitat


@pytest.mark.parametrize("habitat", ["forest", "wetland", "dry woodland", "grassland", "desert", "tundra"])
def test_habitat_never_adds_markings(engine, habitat):
    for sire, dam in [("lion", "eagle"), ("donkey", "horse"), ("eagle", "octopus"), ("horse", "dromedary_camel")]:
        g, _ = plan_for(engine, sire, dam, habitat=habitat)
        text = " ".join(g.habitat.adjustments)
        assert not PATTERN_WORDS.search(text), text
        assert not any(f.startswith("habitat pattern") for f in g.traits["coat_pattern"].flags)


def test_habitat_scales_an_existing_pattern(engine):
    # E2c: real hybrids (the liger) get no habitat step, so this uses close relatives with no documented cross.
    open_g, _ = plan_for(engine, "tiger", "leopard", habitat="grassland")
    closed_g, _ = plan_for(engine, "tiger", "leopard", habitat="forest")
    assert closed_g.traits["coat_pattern"].strength - open_g.traits["coat_pattern"].strength == pytest.approx(0.2)
    assert "fainter leopard-type rosettes" in " ".join(open_g.habitat.adjustments)


# ------------------------------------------------------------------ 4. polish


def test_polish_rejections(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    orig = compile_prompt(g, engine.tax)
    assert check_polish(orig, orig.replace("plain light background", "plain, light background"), g, engine.tax) is None
    assert "not a parent: leopard" in check_polish(orig, orig + " Leopard spots on the body.", g, engine.tax)
    assert "zebra" in check_polish(orig, orig.replace("lion coat", "zebra coat"), g, engine.tax)
    assert "contradicts the plan" in check_polish(orig, orig + " It walks on four lion legs.", g, engine.tax)
    assert "mane" in check_polish(orig, orig + " A full lion mane.", g, engine.tax)
    assert "pattern" in check_polish(orig, orig + " A patterned coat.", g, engine.tax)
    mule, _ = plan_for(engine, "donkey", "horse")
    m = compile_prompt(mule, engine.tax)
    assert "wings" in check_polish(m, m + " Small wings.", mule, engine.tax)


async def test_rejected_polish_falls_back_to_the_compiled_prompt(engine):
    async def leaky(prompt: str) -> str:
        return prompt + " Leopard rosettes on the flanks."

    engine.spark.polish = leaky  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert doc["polish"].startswith("rejected: adds an animal that is not a parent: leopard")
    assert doc["prompt"] == doc["prompt_compiled"]


# ------------------------------------------------------------------ 5. critic: third animal


def test_third_animal_detection(tax):
    lion, eagle, donkey, horse = (tax.animals[x] for x in ("lion", "golden_eagle", "donkey", "horse"))
    assert third_animals({"animals": ["lion", "leopard", "eagle"]}, lion, eagle, tax) == ["leopard"]
    assert third_animals({"animals": ["lion", "bird"]}, lion, eagle, tax) == []  # group word for the eagle
    assert third_animals({"animals": ["donkey", "zebra"]}, donkey, horse, tax) == ["zebra"]
    from app.evolution.route import route

    assert third_animals({"animals": ["mule"]}, donkey, horse, tax, route(donkey, horse, tax)) == []


def _scripted_critic(engine, answers: list[list[str]]):
    calls: list[int] = []

    async def critic(image: bytes) -> dict[str, Any]:
        calls.append(1)
        n = (len(calls) - 1) // 2  # full image and thumbnail per render
        return {"animals": answers[min(n, len(answers) - 1)], "creatures": 1, "notes": "scripted"}

    engine.spark.critic = critic  # type: ignore[method-assign]


async def test_third_animal_rerenders_once_with_the_compiled_prompt(engine):
    _scripted_critic(engine, [["lion", "leopard", "golden eagle"], ["lion", "golden eagle"]])
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert [a["third_animal"] for a in doc["render_attempts"]] == [["leopard"], []]
    assert doc["render_attempts"][1]["prompt"] == "compiled" and doc["prompt"] == doc["prompt_compiled"]
    assert doc["warnings"] == [] and doc["first_image_key"]
    assert doc["meta_calls"] == {"spark": 6, "image": 2, "sam": 2}


async def test_third_animal_twice_is_kept_with_a_warning(engine):
    # E2d: the mule now gets the checklist critic, so the open critic is scripted on a chimera.
    _scripted_critic(engine, [["lion", "golden eagle", "zebra"]])
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert len(doc["render_attempts"]) == 2  # exactly one re-render, no loop
    assert doc["warnings"] == ["third animal after one re-render: zebra"]
    assert doc["meta_calls"]["image"] == 2


async def test_no_third_animal_no_rerender(engine):
    doc = await engine.fuse(sire_name="lion", dam_name="tiger")
    assert len(doc["render_attempts"]) == 1 and doc["meta_calls"] == {"spark": 4, "image": 1, "sam": 1}


# ------------------------------------------------------------------ 6. SAM scorer


async def test_sam_is_prompted_with_animal(engine):
    seen: list[str] = []
    inner = engine.segmenter.segment

    async def spy(image: bytes, label: str) -> bytes:
        seen.append(label)
        return await inner(image, label)

    engine.segmenter.segment = spy  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="eagle", dam_name="octopus")
    assert seen == ["animal"] == [SAM_PROMPT] and doc["judge"]["sam_prompt"] == "animal"


def test_pieces_count_as_one_creature_when_the_critic_says_one():
    stats = {"fill": 0.36, "aspect": 0.98, "components": 2}
    assert silhouette_score(stats, "winged", critic_one=True) == silhouette_score({**stats, "components": 1}, "winged")
    assert silhouette_score(stats, "winged", critic_one=False) == pytest.approx(
        silhouette_score({**stats, "components": 1}, "winged") * 0.5, abs=1e-3)
