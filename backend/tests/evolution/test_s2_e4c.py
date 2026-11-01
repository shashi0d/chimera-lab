"""S2 part 1 (E4c): wing rules by donor type, class part lists, grouped donor clause, silhouette agreement.

Regression case: the E4 live beetle x bear plan (insect wings in the forelimb slot, "jointed tail segments" on a
beetle), replayed through finish() with the beetle entry exactly as E4 saved it."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from app.evolution.checks import hard_violations
from app.evolution.engine import EvoEngine
from app.evolution.genome import validate_plan
from app.evolution.parts import (
    best_part,
    check_traits,
    class_parts,
    dorsal_wings,
    forbidden,
    match,
    valid_part,
)
from app.evolution.prompt import compile_prompt, donor_clause
from app.evolution.route import silhouette_issues
from app.services import build_services
from tests.conftest import make_settings
from tests.evolution.conftest import plan_for

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "s2"
CLASSES = ("Insecta", "Arachnida", "Malacostraca", "Mammalia", "Aves", "Reptilia", "Amphibia", "Actinopterygii",
           "Chondrichthyes", "Cephalopoda", "Gastropoda")


def _mode(engine, sire, dam, mode, **kw):
    a, b = engine.tax.resolve(sire), engine.tax.resolve(dam)
    g, r = engine.seed_plan(a, b, design_mode=mode, **kw)
    return engine.finish(g, r), r


@pytest.fixture
def e4_engine(tmp_path: Path) -> EvoEngine:
    """An engine whose learned store holds the beetle exactly as E4 saved it (body plan multi_legged + winged)."""
    store = tmp_path / "learned.json"
    shutil.copy(FIX / "learned_beetle_e4.json", store)
    return EvoEngine(build_services(make_settings(tmp_path, evo_learned_path=str(store))))


# ------------------------------------------------------------------ a) wing rules


def test_vertebrate_wings_still_take_the_forelimb_slot(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    assert g.limb_plan.forelimbs.kind == "wings" and g.limb_plan.forelimbs.donor == "golden_eagle"
    m, _ = plan_for(engine, "lion", "eagle", myth=True)
    assert m.limb_plan.extra_wings and m.limb_plan.forelimbs.kind == "legs"


async def test_insect_wings_go_on_a_dorsal_mount_and_keep_four_legs(engine):
    await engine.resolve("rhinoceros beetle")  # mock: Dynastes hercules, a flying insect
    g, _ = _mode(engine, "rhinoceros beetle", "brown bear", "mythic")
    lp = g.limb_plan
    assert (lp.forelimbs.kind, lp.hindlimbs.kind) == ("legs", "legs") and lp.extra_wings is None
    assert dorsal_wings(g, engine.tax) and "insect_wings" in [x.id for x in g.licenses]
    assert "shoulder blades" in g.silhouette and "two hind legs" not in g.silhouette
    assert not [v for v in hard_violations(g, engine.route_for(g), engine.tax) if v.card in ("RC-R3-01", "RC-R3-02")]


@pytest.mark.parametrize("mode", ["speculative", "realistic"])
async def test_insect_wings_over_budget_are_dropped(engine, mode):
    await engine.resolve("rhinoceros beetle")
    g, _ = _mode(engine, "rhinoceros beetle", "brown bear", mode)  # speculative: the one license is arthropod size
    assert not dorsal_wings(g, engine.tax) and not g.limb_plan.has_wings()
    assert "dropped part: wings" in g.traits["body"].flags
    assert "insect_wings" not in [x.id for x in g.licenses]
    assert "wing" not in g.silhouette


def test_insect_wings_on_a_small_host_take_the_one_speculative_license(engine):
    g, _ = _mode(engine, "honey_bee", "european_rabbit", "speculative")  # rabbit host 0.44 m: no size license
    assert [x.id for x in g.licenses] == ["insect_wings"] and dorsal_wings(g, engine.tax)
    assert g.licenses[0].compensation in compile_prompt(g, engine.tax)


# ------------------------------------------------------------------ b) class part lists


def test_class_parts_file_covers_the_classes_and_is_marked():
    data = class_parts()
    assert data["provenance"] == "model-estimated, reviewed"
    assert set(CLASSES) <= set(data["classes"])
    for cls in CLASSES:
        entry = data["classes"][cls]
        assert entry["parts"] and entry["never"] and entry["body_plans"] and entry["coverings"]
        assert all({"part", "slot", "shape", "job", "aliases"} <= set(p) for p in entry["parts"])


@pytest.mark.parametrize("cls,text,ok", [
    ("Insecta", "jointed tail segments", False), ("Insecta", "head horn", True), ("Insecta", "membranous wings", True),
    ("Insecta", "fluffy tail", False), ("Malacostraca", "jointed tail segments", True),
    ("Arachnida", "jointed tail segments", True), ("Arachnida", "wings", False), ("Aves", "horns", False),
    ("Mammalia", "keratin scales", True), ("Amphibia", "external gills", True), ("Cephalopoda", "tentacles", True),
])
def test_part_validity_by_class(tax, cls, text, ok):
    animal = next(a for a in tax.animals.values() if a.tax_class == cls or (cls == "Chondrichthyes" and
                                                                                a.tax_class == "Elasmobranchii"))
    assert valid_part(animal, text) is ok


def test_feature_words_a_class_cannot_have():
    assert forbidden("Insecta", "long feathered tail") == ["tail"]  # 'feathered' is not the word 'feather'
    assert forbidden("Malacostraca", "segmented tail") == []  # a valid part's own words never count


def test_most_recognizable_part_comes_from_the_donor_features(e4_engine):
    beetle = e4_engine.tax.resolve("european_rhinoceros_beetle")
    assert best_part(beetle).part == "head horn"  # its first feature: "long curved head horn in males"


def test_saved_traits_must_fit_the_class():
    fixes = check_traits("Insecta", {"body_plan": ["multi_legged", "winged"], "covering": "exoskeleton",
                                     "visible_features": ["glossy elytra", "short tail"]})
    fields = {f["field"]: f for f in fixes}
    assert fields["body_plan"]["now"] == ["multi_legged"] and fields["visible_features"]["now"] == ["glossy elytra"]


def test_the_e4_beetle_entry_is_corrected_on_load_and_logged(e4_engine, tmp_path):
    saved = json.loads((tmp_path / "learned.json").read_text(encoding="utf-8"))["animals"]["european_rhinoceros_beetle"]
    assert saved["traits"]["body_plan"] == ["multi_legged"]
    fix = saved["corrections"][0]
    assert fix["field"] == "body_plan" and fix["was"] == ["multi_legged", "winged"] and fix["by"] == "class_parts.json"
    assert saved["provenance"]["body_plan"] == "model-estimated, corrected by class_parts.json"
    assert not e4_engine.tax.resolve("european_rhinoceros_beetle").winged


async def test_a_new_learned_animal_is_corrected_before_it_is_saved(engine, monkeypatch):
    real = engine.spark.learn_traits

    async def winged_beetle(ident):
        out = await real(ident)
        return {**out, "body_plan": ["multi_legged", "winged"]}

    monkeypatch.setattr(engine.spark, "learn_traits", winged_beetle)
    res = await engine.resolve("rhinoceros beetle")
    entry = engine.resolver.store.lookup("rhinoceros beetle")[0]
    assert entry["traits"]["body_plan"] == ["multi_legged"] and entry["corrections"][0]["field"] == "body_plan"
    assert not res.animal.winged


def test_an_invalid_signature_part_is_replaced(e4_engine):
    g, _ = _mode(e4_engine, "european_rhinoceros_beetle", "brown bear", "speculative")
    assert g.traits["tail"].part is None and g.traits["tail"].donor == "brown_bear"
    assert "european rhinoceros beetle head horn" in g.limb_plan.appendages
    fix = next(c for c in g.checks if c.step == "class_parts")
    assert "jointed tail segments" in fix.detail and "head horn" in fix.detail


def test_a_valid_signature_part_stays(engine):
    g, _ = plan_for(engine, "lion", "american_lobster")
    assert g.traits["tail"].part == "jointed tail segments"
    assert not [c for c in g.checks if c.step == "class_parts"]


# ------------------------------------------------------------------ regression: the E4 live beetle plan


def test_e4_beetle_plan_replayed(e4_engine):
    raw = json.loads((FIX / "e4_beetle_bear_plan.json").read_text(encoding="utf-8"))
    g0 = validate_plan({**raw, "id": "pending"})
    assert g0.limb_plan.forelimbs.kind == "wings" and g0.traits["tail"].part == "jointed tail segments"  # as in E4
    g = e4_engine.finish(g0, e4_engine.route_for(g0))
    lp = g.limb_plan
    assert (lp.forelimbs.kind, lp.hindlimbs.kind) == ("legs", "legs")  # the bear keeps its forelegs
    assert "dropped part: wings" in g.traits["body"].flags and not dorsal_wings(g, e4_engine.tax)
    assert g.traits["tail"].part is None and "european rhinoceros beetle head horn" in lp.appendages
    assert [x.id for x in g.licenses] == ["arthropod_large"]
    p = compile_prompt(g, e4_engine.tax)
    assert "jointed tail" not in p and "in place of the forelegs" not in p and "two hind legs" not in p
    assert "horn of hard, glossy chitin" in p and not silhouette_issues(g, e4_engine.tax)


# ------------------------------------------------------------------ c) grouped donor clause


@pytest.mark.parametrize("sire,dam,mode", [("lion", "eagle", "speculative"), ("lion", "eagle", "mythic"),
                                           ("tiger", "octopus", "speculative"), ("lion", "american_lobster", "mythic"),
                                           ("honey_bee", "european_rabbit", "speculative")])
def test_each_donor_is_named_once_in_one_grouped_clause(engine, sire, dam, mode):
    g, _ = _mode(engine, sire, dam, mode)
    donor = engine.tax.animals[g.other(g.host)].common_name.lower()
    p = compile_prompt(g, engine.tax)
    details = p[p.index("Details:"):p.index(". Coat texture")]
    named = len(re.findall(rf"\b{re.escape(donor)}\b(?!-type)", details))
    assert named == 1, details
    assert details.count(f"from the {donor}, as parts and materials on the") == 1


async def test_donor_surfaces_are_materials_and_shapes(e4_engine):
    g, _ = _mode(e4_engine, "european_rhinoceros_beetle", "brown bear", "speculative")
    clause = donor_clause(g, e4_engine.tax)
    assert "chitin plates" in clause and "exoskeleton" not in clause and "beetle head horn" not in clause
    assert match(e4_engine.tax.resolve("european_rhinoceros_beetle"), "head horn").shape in clause


# ------------------------------------------------------------------ d) silhouette matches the limb plan


@pytest.mark.parametrize("sire,dam,mode", [("lion", "eagle", "speculative"), ("lion", "eagle", "mythic"),
                                           ("lion", "eagle", "realistic"), ("tiger", "octopus", "speculative"),
                                           ("honey_bee", "european_rabbit", "speculative"),
                                           ("honey_bee", "brown_bear", "mythic"), ("donkey", "horse", "speculative")])
def test_silhouette_matches_the_final_limb_plan(engine, sire, dam, mode):
    g, _ = _mode(engine, sire, dam, mode)
    assert silhouette_issues(g, engine.tax) == []


def test_silhouette_mismatch_is_detected(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    assert silhouette_issues(g, engine.tax, "four-legged lion frame")
    m, _ = plan_for(engine, "lion", "goldfish")
    assert silhouette_issues(m, engine.tax, m.silhouette + ", with wings") != []
