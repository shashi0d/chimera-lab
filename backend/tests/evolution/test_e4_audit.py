"""E4 step 3: the function audit (ALGORITHM.md 4.5b, R9 section 2).

Each function, pass and fail, code-decided (with the card cited) and model-judged (one Spark call per
creature covering every uncovered function, before the render).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.evolution.audit import plan_text, run_audit, uncovered
from app.evolution.genome import FUNCTIONS
from tests.evolution.conftest import plan_for


def _audit(g) -> dict[str, Any]:
    return {i.function: i for i in g.audit}


def _plan(engine, sire, dam, mode="speculative", **kw):
    a, b = engine.tax.resolve(sire), engine.tax.resolve(dam)
    g, r = engine.seed_plan(a, b, mode == "mythic", **kw)
    g.design_mode = mode
    return engine.finish(g, r), r


@pytest.mark.parametrize("sire,dam", [("lion", "tiger"), ("lion", "eagle"), ("eagle", "octopus"), ("donkey", "horse")])
def test_every_plan_audits_all_six_functions_in_order(engine, sire, dam):
    g, _ = plan_for(engine, sire, dam)
    assert [i.function for i in g.audit] == list(FUNCTIONS)
    assert all(i.result in ("pass", "repaired", "labeled", "licensed", "pending") for i in g.audit)
    assert "RC-R9-02" in g.card_trace


# ------------------------------------------------------------------ breathing


def test_breathing_gills_alone_on_land_is_not_a_pass(engine):
    g, _ = _plan(engine, "tiger_shark", "lion", host_pick="sire")  # a shark body on a rocky coast
    b = _audit(g)["breathing"]
    assert b.result != "pass" and "RC-R9-03" in b.cards


def test_breathing_gills_in_water_pass(engine):
    g, _ = _plan(engine, "tiger_shark", "lion", host_pick="sire", habitat="marine")
    b = _audit(g)["breathing"]
    assert b.result == "pass" and "water" in b.detail


async def test_donor_gills_dropped_in_realistic_kept_as_frills_otherwise(engine):
    await engine.resolve("pangolin")
    real, _ = _plan(engine, "axolotl", "pangolin", "realistic")
    spec, _ = _plan(engine, "axolotl", "pangolin", "speculative")
    rb, sb = _audit(real)["breathing"], _audit(spec)["breathing"]
    assert rb.result == "repaired" and {"RC-R9-03", "RC-R9-12"} <= set(rb.cards) and "collapse in air" in rb.detail
    assert not any("gills" in a for a in real.limb_plan.appendages)
    assert sb.result == "pass" and any("gills" in a for a in spec.limb_plan.appendages) and "display" in sb.detail


def test_breathing_unknown_organ_is_model_judged(engine):
    g, _ = plan_for(engine, "moon_jellyfish", "lion", host_pick="sire")
    assert _audit(g)["breathing"].source == "model-judged" and "breathing" in uncovered(g)


# ------------------------------------------------------------------ feeding


def test_feeding_teeth_fit_diet_code_decided(engine):
    f = _audit(plan_for(engine, "lion", "tiger")[0])["feeding"]
    assert f.result == "pass" and f.cards == ["RC-R9-04"] and f.source == "code"


def test_feeding_beak_is_never_a_reason_to_reject(engine):
    f = _audit(plan_for(engine, "eagle", "octopus")[0])["feeding"]
    assert f.result == "pass" and "RC-R9-05" in f.cards and "never a reason to reject" in f.detail


def test_feeding_behavior_follows_the_head_donor(engine):
    g, r = plan_for(engine, "lion", "eagle")
    bad = g.model_copy(deep=True)
    bad.traits["behavior"] = bad.traits["behavior"].model_copy(update={"donor": "golden_eagle"})
    bad.traits["head"] = bad.traits["head"].model_copy(update={"donor": "lion"})
    run_audit(bad, engine.tax, r)
    f = _audit(bad)["feeding"]
    assert bad.traits["behavior"].donor == "lion" or f.result == "pass"


async def test_feeding_uncovered_mouthparts_are_model_judged(engine):
    await engine.resolve("pangolin")
    g, _ = _plan(engine, "axolotl", "pangolin")
    f = _audit(g)["feeding"]
    assert f.result == "pending" and f.source == "model-judged" and "toothless tongue" in f.detail


# ------------------------------------------------------------------ support


def test_support_scaled_up_legs_change_shape(engine):
    from app.evolution.physics import run_checks

    g, r = plan_for(engine, "lion", "eagle")
    big = g.model_copy(deep=True)
    big.size.mass_kg = engine.tax.animals["lion"].mass_kg * 3
    run_checks(big, engine.tax)
    run_audit(big, engine.tax, r)
    s = _audit(big)["support"]
    assert s.result == "repaired" and "RC-R9-06" in s.cards and "legs changed shape" in s.detail


def test_support_matching_legs_pass(engine):
    s = _audit(plan_for(engine, "lion", "eagle")[0])["support"]
    assert s.result == "pass"


async def test_support_insect_parts_at_large_size_are_labeled_with_the_oxygen_caveat(engine):
    await engine.resolve("rhinoceros beetle")
    g, _ = _plan(engine, "rhinoceros beetle", "brown bear", "realistic")
    s = _audit(g)["support"]
    assert s.result == "labeled" and {"RC-R3-09", "RC-R9-08"} <= set(s.cards) and "debated" in s.detail


def test_support_small_insect_part_creature_needs_no_license(engine):
    g, _ = plan_for(engine, "emperor_scorpion", "seven_spotted_ladybug")
    s = _audit(g)["support"]
    assert s.result in ("pass", "repaired")


# ------------------------------------------------------------------ movement


def test_movement_flight_anatomy_reported(engine):
    m = _audit(plan_for(engine, "lion", "eagle")[0])["movement"]
    assert m.result == "labeled" and {"RC-R3-03", "RC-R3-04", "RC-R9-13"} <= set(m.cards)


def test_movement_digging_behavior_gets_digging_forelimbs(engine):
    g, r = plan_for(engine, "lion", "meerkat")
    bad = g.model_copy(deep=True)
    bad.traits["behavior"] = bad.traits["behavior"].model_copy(update={"donor": "meerkat"})
    run_audit(bad, engine.tax, r)
    m = _audit(bad)["movement"]
    assert "RC-R9-13" in m.cards and "thick forelimbs" in (bad.traits["limbs"].note or "")


def test_movement_jobless_part_dropped_in_realistic_only(engine):
    spec, _ = _plan(engine, "lion", "goldfish", "speculative")  # broad fins on a land body: no job out of water
    real, _ = _plan(engine, "lion", "goldfish", "realistic")
    assert spec.traits["tail"].part == "broad fins" and "RC-R9-12" in _audit(spec)["movement"].cards
    assert real.traits["tail"].part is None and _audit(real)["movement"].result == "repaired"


# ------------------------------------------------------------------ heat and senses


def test_heat_hot_habitat_adjusted(engine):
    h = _audit(plan_for(engine, "lion", "eagle", habitat="desert")[0])["heat"]
    assert h.result == "repaired" and "RC-R4-04" in h.cards


def test_heat_real_hybrid_has_no_habitat_step(engine):
    h = _audit(plan_for(engine, "donkey", "horse")[0])["heat"]
    assert h.result == "pass" and "D-056" in h.detail


def test_heat_unprofiled_habitat_is_model_judged(engine):
    g, _ = plan_for(engine, "lion", "eagle", habitat="volcanic island")
    assert _audit(g)["heat"].source == "model-judged" and "heat" in uncovered(g)


def test_senses_head_and_eyes(engine):
    s = _audit(plan_for(engine, "eagle", "octopus")[0])["senses"]
    assert s.result == "pass" and s.cards == ["RC-R6-03", "RC-R6-04"]


# ------------------------------------------------------------------ the one model judgment


async def test_one_spark_call_covers_every_uncovered_function(engine):
    seen: list[list[str]] = []
    inner = engine.spark.judge_functions

    async def spy(text: str, fns: list[str]):
        seen.append(fns)
        assert "Parents:" in text and "{" not in text  # plain words, no JSON
        return await inner(text, fns)

    engine.spark.judge_functions = spy  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="moon_jellyfish", dam_name="lion", host="sire", habitat="volcanic island")
    assert len(seen) == 1 and set(seen[0]) >= {"breathing", "heat"}
    audit = {i["function"]: i for i in doc["genome"]["audit"]}
    assert all(audit[f]["source"] == "model-judged" and audit[f]["result"] == "pass" for f in seen[0])
    assert doc["meta_calls"]["spark"] == 6  # plan, polish, audit, checklist, thumbnail, open critic


async def test_no_uncovered_function_means_no_audit_call(engine):
    doc = await engine.fuse(sire_name="lion", dam_name="tiger")
    assert all(i["result"] != "pending" for i in doc["genome"]["audit"])
    assert doc["meta_calls"]["spark"] == 5


async def test_failed_model_judgment_is_labeled_not_passed(engine):
    from app.errors import ChimeraError
    from app.models.schemas import ErrorCode

    async def broken(text, fns):
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "down")

    engine.spark.judge_functions = broken  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="moon_jellyfish", dam_name="lion", host="sire")
    b = {i["function"]: i for i in doc["genome"]["audit"]}["breathing"]
    assert b["result"] == "labeled" and "unavailable" in b["detail"]
    assert "unchecked: breathing not confirmed" in doc["genome"]["labels"]


async def test_model_repair_reaches_the_plan_and_oxygen_is_hedged(engine):
    async def judged(text, fns):
        return [{"function": f, "result": "repaired", "repair": "a broad sensory fringe",
                 "detail": "giant size works because of high oxygen"} for f in fns]

    engine.spark.judge_functions = judged  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="moon_jellyfish", dam_name="lion", host="sire")
    b = {i["function"]: i for i in doc["genome"]["audit"]}["breathing"]
    assert b["result"] == "repaired" and "debated, not settled" in b["detail"]
    assert "a broad sensory fringe" in doc["genome"]["traits"]["body"]["note"]


def test_plan_text_is_plain_words(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    text = plan_text(g, engine.tax)
    assert "golden eagle" in text and "kg" in text and "_" not in text


def test_feeding_teeth_that_contradict_the_diet_are_flagged(engine):
    from dataclasses import replace

    engine.tax.animals["lion"] = replace(engine.tax.animals["lion"], mouthparts="grinding teeth")  # this engine only
    f = _audit(plan_for(engine, "lion", "eagle")[0])["feeding"]
    assert f.result == "labeled" and f.cards == ["RC-R9-04"] and "do not match a carnivore diet" in f.detail


def test_movement_plain_four_legs_pass(engine):
    m = _audit(plan_for(engine, "lion", "cheetah")[0])["movement"]
    assert m.result == "pass" and m.detail == "walks on four legs"
