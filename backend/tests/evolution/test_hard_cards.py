"""One automated test (at least) per hard card, ALGORITHM.md section 8."""

from __future__ import annotations

import itertools

import pytest
from pydantic import ValidationError

from app.evolution.checks import hard_violations
from app.evolution.data import cards
from app.evolution.engine import cache_key
from app.evolution.genome import Genome, LimbSlot, Trait
from app.evolution.physics import LABEL_ARTHROPOD, LABEL_SIX, run_checks
from app.evolution.route import LABEL_CHIMERA, LABEL_SPECULATIVE, find_known_pair, route
from tests.evolution.conftest import plan_for

HARD = {"RC-R1-01", "RC-R1-14", "RC-R2-01", "RC-R2-03", "RC-R2-11", "RC-R2-16", "RC-R3-01", "RC-R3-02", "RC-R3-09",
        "RC-R5-01", "RC-R5-10"}
WORKED = [("donkey", "horse"), ("lion", "tiger"), ("lion", "eagle"), ("eagle", "octopus")]


def ids(violations):
    return {v.card for v in violations}


def test_every_hard_card_has_a_test_here():
    assert set(cards().hard_ids()) == HARD


# ---------------------------------------------------------------- RC-R1-01


def test_rc_r1_01_no_field_assigns_dominance(engine):
    g, _ = plan_for(engine, "lion", "tiger")
    with pytest.raises(ValidationError):
        Genome.model_validate({**g.model_dump(), "dominant_parent": "lion"})
    with pytest.raises(ValidationError):
        Genome.model_validate({**g.model_dump(), "traits": {**g.model_dump()["traits"],
                                                            "body": {"op": "PICK", "donor": "lion", "dominance": 1}}})


@pytest.mark.parametrize("sire,dam", WORKED)
def test_rc_r1_01_inheritance_is_per_trait(engine, sire, dam):
    g, r = plan_for(engine, sire, dam)
    assert not ids(hard_violations(g, r, engine.tax))
    donors = {d for tr in g.traits.values() for d in tr.donors()}
    assert {g.parents.sire, g.parents.dam} <= donors | {g.limb_plan.forelimbs.donor}


def test_rc_r1_01_whole_parent_plan_is_blocked(engine):
    g, r = plan_for(engine, "lion", "tiger")
    for tag in g.traits:
        g.traits[tag] = Trait(op="PICK", donor="lion")
    assert "RC-R1-01" in ids(hard_violations(g, r, engine.tax))


# ---------------------------------------------------------------- RC-R1-14, RC-R2-16, RC-R5-10


def test_rc_r1_14_r2_16_r5_10_every_distant_pair_routes_speculative(tax):
    animals = list(tax.animals.values())
    checked = 0
    for s, d in itertools.permutations(animals, 2):
        if s.genus == d.genus or tax.documented_hybrid(s, d) or find_known_pair(s, d):
            continue
        for myth in (False, True):
            r = route(s, d, tax, myth=myth)
            assert r.mode in ("chimera", "mythic"), (s.id, d.id)
            assert LABEL_CHIMERA in r.labels or LABEL_SPECULATIVE in r.labels
            assert {"RC-R1-14", "RC-R2-16", "RC-R5-10"} <= set(r.cards)
        checked += 1
    assert checked > 30000  # the full 200-animal sweep


@pytest.mark.parametrize("sire,dam", [("lion", "eagle"), ("eagle", "octopus"), ("horse", "blue_crab"), ("tiger", "emperor_scorpion")])
def test_rc_r1_14_r2_16_r5_10_plans_keep_the_label(engine, sire, dam):
    for myth in (False, True):
        g, r = plan_for(engine, sire, dam, myth=myth)
        assert any("speculative" in lbl for lbl in g.labels)
        stripped = g.model_copy(update={"labels": [lbl for lbl in g.labels if "speculative" not in lbl]})
        assert {"RC-R1-14", "RC-R5-10"} <= ids(hard_violations(stripped, r, engine.tax))
        as_hybrid = g.model_copy(update={"mode": "hybrid"})
        assert "RC-R2-16" in ids(hard_violations(as_hybrid, r, engine.tax))


# ---------------------------------------------------------------- RC-R2-01


async def test_rc_r2_01_order_matters(engine):
    assert cache_key("lion", "tiger", False, None, None, 0) != cache_key("tiger", "lion", False, None, None, 0)
    a = await engine.fuse(sire_name="lion", dam_name="tiger")
    b = await engine.fuse(sire_name="tiger", dam_name="lion")
    assert a["cache_key"] != b["cache_key"]
    assert a["genome"]["id"] != b["genome"]["id"]
    assert (a["genome"]["parents"], b["genome"]["parents"]) == ({"sire": "lion", "dam": "tiger"}, {"sire": "tiger", "dam": "lion"})
    assert a["genome"]["known_pair"] == "liger" and b["genome"]["known_pair"] == "tigon"
    assert a["genome"]["size"]["mass_kg"] > b["genome"]["size"]["mass_kg"]  # reciprocal crosses differ


def test_rc_r2_01_swapped_parents_are_blocked(engine):
    g, r = plan_for(engine, "lion", "tiger")
    swapped = g.model_copy(update={"parents": g.parents.model_copy(update={"sire": "tiger", "dam": "lion"})})
    assert "RC-R2-01" in ids(hard_violations(swapped, r, engine.tax))


# ---------------------------------------------------------------- RC-R2-03


@pytest.mark.parametrize("seed", range(5))
def test_rc_r2_03_mule_matches_override_field_by_field(engine, seed):
    g, r = plan_for(engine, "donkey", "horse", seed=seed)
    pair = find_known_pair(engine.tax.animals["donkey"], engine.tax.animals["horse"])
    assert pair["id"] == "mule" and pair["locked"]
    for tag, spec in pair["traits"].items():
        assert g.traits[tag].model_dump(exclude_none=True, exclude_defaults=True) == spec, tag
    assert g.size.mass_kg == engine.tax.animals["horse"].mass_kg  # horse height
    assert g.host == "horse"
    assert not ids(hard_violations(g, r, engine.tax))


async def test_rc_r2_03_mule_fields_cannot_be_edited(engine):
    from app.errors import ChimeraError

    mule = await engine.fuse(sire_name="donkey", dam_name="horse")
    with pytest.raises(ChimeraError) as e:
        await engine.edit(mule["genome"]["id"], "traits.ears", {"op": "PICK", "donor": "horse"})
    assert e.value.details["violations"][0]["card"] == "RC-R2-03"


# ---------------------------------------------------------------- RC-R2-11


@pytest.mark.parametrize("sire,dam", [("polar_bear", "brown_bear"), ("brown_bear", "polar_bear"), ("polar bear", "grizzly")])
def test_rc_r2_11_polar_grizzly_routes_hybrid(engine, sire, dam):
    g, r = plan_for(engine, sire, dam)
    assert r.mode == "hybrid" and g.mode == "hybrid"
    assert r.pair["id"] == "hybrid_bear" and "RC-R2-11" in g.card_trace
    assert "RC-R2-11" in ids(hard_violations(g.model_copy(update={"mode": "chimera"}), r, engine.tax))


# ---------------------------------------------------------------- RC-R3-01, RC-R3-02


def test_rc_r3_01_wings_take_the_forelimb_slot(engine):
    g, r = plan_for(engine, "lion", "eagle")
    assert g.mode == "chimera"
    assert g.limb_plan.forelimbs.kind == "wings" and g.limb_plan.extra_wings is None
    assert g.limb_plan.limb_count() == 4
    assert not ids(hard_violations(g, r, engine.tax))


def test_rc_r3_02_six_limbs_only_mythic_with_label(engine):
    g, r = plan_for(engine, "lion", "eagle", myth=True)
    assert g.mode == "mythic" and g.limb_plan.forelimbs.kind == "legs" and g.limb_plan.extra_wings
    assert LABEL_SIX in g.labels and not ids(hard_violations(g, r, engine.tax))
    unlabeled = g.model_copy(update={"labels": [lbl for lbl in g.labels if lbl != LABEL_SIX]})
    assert {"RC-R3-01", "RC-R3-02"} <= ids(hard_violations(unlabeled, r, engine.tax))


def test_rc_r3_02_six_limbs_in_chimera_mode_blocked_then_repaired(engine):
    g, r = plan_for(engine, "lion", "eagle")
    six = g.model_copy(deep=True)
    six.limb_plan.forelimbs = LimbSlot(kind="legs", donor="lion")
    six.limb_plan.extra_wings = LimbSlot(kind="wings", donor="golden_eagle")
    assert {"RC-R3-01", "RC-R3-02"} <= ids(hard_violations(six, r, engine.tax))
    run_checks(six, engine.tax)  # the limb-budget check repairs instead of passing silently
    assert six.limb_plan.forelimbs.kind == "wings" and six.limb_plan.extra_wings is None
    assert any(c.step == "limb_budget" and c.result == "repaired" for c in six.checks)


# ---------------------------------------------------------------- RC-R3-09


def test_rc_r3_09_arthropod_parts_at_large_size_are_labeled(engine):
    g, r = plan_for(engine, "tiger", "emperor_scorpion")
    assert g.host == "tiger" and g.size.mass_kg > 20
    assert LABEL_ARTHROPOD in g.labels and "insect breathing" in LABEL_ARTHROPOD
    assert any(c.step == "size_ceiling" and "RC-R3-09" in c.cards for c in g.checks)
    stripped = g.model_copy(update={"labels": [lbl for lbl in g.labels if lbl != LABEL_ARTHROPOD]})
    assert "RC-R3-09" in ids(hard_violations(stripped, r, engine.tax))


def test_rc_r3_09_small_arthropod_fusion_needs_no_label(engine):
    g, _ = plan_for(engine, "emperor_scorpion", "blue_crab")  # both arthropods, no mass on record
    assert LABEL_ARTHROPOD not in g.labels


# ---------------------------------------------------------------- RC-R5-01


@pytest.mark.parametrize("sire,dam", [("lion", "eagle"), ("eagle", "octopus"), ("tiger", "emperor_scorpion")])
def test_rc_r5_01_no_blend_inside_a_patch(engine, sire, dam):
    for myth in (False, True):
        g, r = plan_for(engine, sire, dam, myth=myth)
        patch = {reg for tr in g.traits.values() if tr.op == "PATCH" for reg in tr.region or []}
        assert patch
        for tag, tr in g.traits.items():
            if tr.op == "BLEND":
                assert tag not in ("coat_pattern", "coat_color", "coat_texture")
                assert not set(tr.region or []) & patch
        bad = g.model_copy(deep=True)
        bad.traits["coat_color"] = Trait(op="BLEND", donor=[g.parents.sire, g.parents.dam], value=0.5)
        assert "RC-R5-01" in ids(hard_violations(bad, r, engine.tax))


async def test_rc_r5_01_invalid_offspring_are_filtered_before_render(engine):
    seed = await engine.fuse(sire_name="lion", dam_name="eagle")
    engine.spark.invalid_every = 2
    before = engine.meter.snapshot()
    out = await engine.evolve(seed["genome"]["id"], rounds=1, batch=4)
    used = engine.meter.since(before)
    assert len(out["rejected"]) == 2
    assert all(v["card"] == "RC-R5-01" for rej in out["rejected"] for v in rej["violations"])
    assert used["image"] == 2  # no image budget spent on invalid plans (RC-R8-03)
