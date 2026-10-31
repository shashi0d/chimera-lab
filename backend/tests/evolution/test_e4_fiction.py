"""E4 step 4: the fiction budget and design modes (ALGORITHM.md 3.1 and 4.5c, R9 section 3)."""

from __future__ import annotations

import pytest

from app.evolution.audit import Need
from app.evolution.checks import hard_violations
from app.evolution.fiction import bendable, budget, check_licensable, make_license, never_licensable, settle
from app.evolution.genome import License
from app.evolution.physics import LABEL_ARTHROPOD, LABEL_SIX
from app.evolution.prompt import compile_prompt


def _plan(engine, sire, dam, mode, **kw):
    a, b = engine.tax.resolve(sire), engine.tax.resolve(dam)
    g, r = engine.seed_plan(a, b, design_mode=mode, **kw)
    return engine.finish(g, r), r


def _fn(g, name):
    return next(i for i in g.audit if i.function == name)


def test_budget_per_mode():
    assert (budget("realistic"), budget("speculative"), budget("mythic")) == (0, 1, 3)


# ------------------------------------------------------------------ licenses granted, with compensation


def test_mythic_lion_eagle_licenses_six_limbs(engine):
    g, r = _plan(engine, "lion", "eagle", "mythic")
    assert g.limb_plan.extra_wings is not None and LABEL_SIX in g.labels
    assert [lic.id for lic in g.licenses] == ["six_limbs"] and g.licenses[0].card == "RC-R3-02"
    assert _fn(g, "movement").result == "licensed"
    assert g.licenses[0].compensation in (g.traits["body"].note or "")
    assert "Declared fiction: six limbs (four legs plus wings), shown with wings rooted" in compile_prompt(g, engine.tax)
    assert any("believability drops with each extra license" in x for x in g.labels)  # RC-R9-11
    assert not hard_violations(g, r, engine.tax)


async def test_speculative_beetle_bear_takes_one_size_license_with_visible_compensation(engine):
    await engine.resolve("rhinoceros beetle")
    g, r = _plan(engine, "rhinoceros beetle", "brown bear", "speculative")
    assert [lic.id for lic in g.licenses] == ["arthropod_large"]
    comp = g.licenses[0].compensation
    assert "thick supporting legs" in comp and "breathing openings" in comp
    assert comp in (g.traits["limbs"].note or "") and comp in compile_prompt(g, engine.tax)
    assert LABEL_ARTHROPOD in g.labels  # the honest label stays: a license is declared, never hidden
    assert _fn(g, "support").result == "licensed"
    assert not hard_violations(g, r, engine.tax)


async def test_realistic_takes_no_license_and_labels_what_cannot_be_repaired(engine):
    await engine.resolve("rhinoceros beetle")
    g, r = _plan(engine, "rhinoceros beetle", "brown bear", "realistic")
    assert g.licenses == [] and _fn(g, "support").result == "labeled" and LABEL_ARTHROPOD in g.labels
    assert "over the realistic budget of 0" in _fn(g, "support").detail
    m, rm = _plan(engine, "lion", "eagle", "realistic")
    assert m.limb_plan.extra_wings is None and m.licenses == []


# ------------------------------------------------------------------ over budget


def test_over_budget_licenses_the_unrepairable_need_and_repairs_the_rest(engine):
    g, r = _plan(engine, "lion", "eagle", "mythic")
    g.design_mode = "speculative"
    g.licenses = []
    settle(g, [Need("six_limbs", "movement", "four legs plus wings"),
               Need("arthropod_large", "support", "arthropod parts at size")], engine.tax)
    assert [lic.id for lic in g.licenses] == ["arthropod_large"]  # not repairable, so it gets the one license
    assert g.limb_plan.extra_wings is None and LABEL_SIX not in g.labels  # six limbs repaired down to the budget
    assert _fn(g, "movement").result == "repaired"


def test_land_gills_repaired_in_realistic_licensed_in_speculative(engine):
    real, _ = _plan(engine, "tiger_shark", "lion", "realistic", host_pick="sire")
    spec, rs = _plan(engine, "tiger_shark", "lion", "speculative", host_pick="sire")
    assert _fn(real, "breathing").result == "repaired" and "vestigial slits" in real.traits["body"].note
    assert [lic.id for lic in spec.licenses] == ["land_gills"] and _fn(spec, "breathing").result == "licensed"
    assert "air-breathing system" in compile_prompt(spec, engine.tax)
    assert not hard_violations(spec, rs, engine.tax)


# ------------------------------------------------------------------ never licensable


@pytest.mark.parametrize("card", ["RC-R1-14", "RC-R2-16", "RC-R5-10", "RC-R9-01", "RC-R9-09", "provenance",
                                  "RC-R9-14", "RC-R6-03", "RC-R6-04", "RC-R6-11", "RC-R7-07", "ground contact"])
def test_honesty_and_floor_rules_are_never_licensable(card):
    assert card in never_licensable() and not check_licensable(card)


def test_only_r9_bendable_rules_can_be_licensed():
    assert {b["card"] for b in bendable().values()} == {"RC-R3-09", "RC-R3-02", "RC-R3-05", "RC-R9-03", "RC-R3-11"}
    with pytest.raises(ValueError):
        make_license("honest_labels", "please")
    assert all(b["compensation"] for b in bendable().values())


def test_rc_r9_10_budget_and_licensability_are_hard(engine):
    g, r = _plan(engine, "lion", "eagle", "mythic")
    real = g.model_copy(deep=True)
    real.design_mode = "realistic"
    assert "RC-R9-10" in {v.card for v in hard_violations(real, r, engine.tax)}
    honest = g.model_copy(deep=True)
    honest.licenses = [License(id="x", card="RC-R9-01", rule="mixed labels", compensation="none", reason="no")]
    assert "RC-R9-10" in {v.card for v in hard_violations(honest, r, engine.tax)}
    bare = g.model_copy(deep=True)
    bare.traits["body"] = bare.traits["body"].model_copy(update={"note": None})
    assert "RC-R9-10" in {v.card for v in hard_violations(bare, r, engine.tax)}  # compensation must be shown


# ------------------------------------------------------------------ modes through fuse


async def test_compare_renders_realistic_plus_the_chosen_mode(engine):
    out = await engine.fuse(sire_name="lion", dam_name="eagle", mode="compare", compare_with="mythic")
    a, b = out["pair"]
    assert out["modes"] == ["realistic", "mythic"]
    assert a["genome"]["design_mode"] == "realistic" and b["genome"]["design_mode"] == "mythic"
    assert a["genome"]["licenses"] == [] and b["genome"]["licenses"][0]["id"] == "six_limbs"
    assert out["meta_calls"]["image"] == 2 and a["genome"]["id"] != b["genome"]["id"]


async def test_mode_is_part_of_the_cache_key(engine):
    a = await engine.fuse(sire_name="lion", dam_name="eagle", mode="realistic")
    b = await engine.fuse(sire_name="lion", dam_name="eagle", mode="speculative")
    assert a["cache_key"] != b["cache_key"] and not b["cached"]


async def test_unknown_mode_is_refused(engine):
    from app.errors import ChimeraError

    with pytest.raises(ChimeraError):
        await engine.fuse(sire_name="lion", dam_name="eagle", mode="fantasy")


async def test_fuse_endpoint_compare(client):
    r = await client.post("/evo/fuse", json={"sire": {"name": "lion"}, "dam": {"name": "eagle"}, "mode": "compare"})
    assert r.status_code == 200, r.text
    assert [d["genome"]["design_mode"] for d in r.json()["pair"]] == ["realistic", "speculative"]
