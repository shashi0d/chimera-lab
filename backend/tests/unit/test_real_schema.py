"""D1: the real chimera_data.json schema (via the verbatim real-schema fixture)."""

import json

import pytest

from app.data.loader import ChimeraData, load_data, parse_parent
from app.data.rule_map import RULE_CHECKS
from app.models.schemas import AnimalMatch, AnimalReading, FusionPlan, PartDonors
from app.pipeline.steps import rules_check as rc
from app.pipeline.steps.hybrid_check import to_myth, to_real_hybrid
from tests.conftest import FIXTURES

REAL = load_data(FIXTURES / "chimera_data.real_schema.json")


def row(name: str) -> dict:
    return next(r for r in REAL.section("animals") if r["common_name"] == name)


def side(name: str):
    r = row(name)
    facts = {k: v for k, v in r.items() if v and isinstance(v, str)}
    m = AnimalMatch(animal_id=r["animal_id"], tier=1, common_name=r["common_name"], scientific_name=r["scientific_name"],
                    matched_on="scientific_name", facts=facts)
    return (AnimalReading(is_animal=True, common_name=r["common_name"], scientific_name=r["scientific_name"]), m)


def synthetic(**facts):
    return (AnimalReading(is_animal=True, common_name=facts.pop("name", "x")),
            AnimalMatch(animal_id="x", tier=1, common_name="x", matched_on="common_name", facts=facts))


# ------------------------------------------------------------------ D1-01 hybrids


def test_parse_parent_roles():
    assert parse_parent("Panthera tigris (father)") == ("Panthera tigris", "father")
    assert parse_parent("Equus asinus (mother)") == ("Equus asinus", "mother")
    assert parse_parent("Canis lupus (unknown)") == ("Canis lupus", None)
    assert parse_parent("hybrid:liger (mother)") == ("hybrid:liger", "mother")


def test_lion_tiger_finds_liger_and_tigon_with_cross_direction():
    found = {h.row["hybrid_id"]: to_real_hybrid(h, {"A": "lion", "B": "tiger"}) for h in REAL.find_hybrids("lion", "tiger")}
    assert set(found) == {"liger", "tigon"}
    tigon = found["tigon"]
    assert (tigon.father, tigon.mother) == ("Panthera tigris", "Panthera leo")
    assert tigon.cross == "father: tiger (Panthera tigris) × mother: lion (Panthera leo)"
    assert tigon.confidence == "captive_only" and tigon.matched_via == "scientific_name"
    assert (found["liger"].father, found["liger"].mother) == ("Panthera leo", "Panthera tigris")


def test_horse_donkey_finds_mule_either_order():
    for a, b in (("horse", "donkey"), ("donkey", "horse")):
        names = {"A": a, "B": b}
        hy = {h.row["hybrid_id"]: to_real_hybrid(h, names) for h in REAL.find_hybrids(a, b)}
        assert {"mule", "hinny"} <= set(hy)
        assert (hy["mule"].father, hy["mule"].mother) == ("Equus asinus", "Equus caballus")
    # the exact order (input A = parent1) sorts first
    assert REAL.find_hybrids("donkey", "horse")[0].row["hybrid_id"] == "mule"


def test_hybrid_parent_is_reported_not_resolved():
    res = {r["hybrid_id"]: (p1, p2) for r, p1, p2 in REAL.hybrid_resolution()}
    p1, p2 = res["liliger"]
    assert p1.animal_ids == ["lion"] and p2.animal_ids == [] and p2.via == "hybrid"


def test_genus_fallback_and_duplicate_scientific_names():
    data = ChimeraData({
        "animals": [
            {"animal_id": "gray_wolf", "common_name": "gray wolf", "scientific_name": "Canis lupus"},
            {"animal_id": "domestic_dog", "common_name": "domestic dog", "scientific_name": "Canis lupus"},
            {"animal_id": "coyote", "common_name": "coyote", "scientific_name": "Canis latrans"},
        ],
        "tier2_animals": [{"animal_id": "canis_aureus", "scientific_name": "Canis aureus", "genus": "Canis"}],
        "hybrids": [{"hybrid_id": "coydog", "hybrid_name": "coydog", "parent1": "Canis latrans (father)",
                     "parent2": "Canis familiaris (mother)"}],
    }, "full")
    _, p1, p2 = data.hybrid_resolution()[0]
    assert p1.via == "scientific_name" and p2.via == "genus"
    assert set(p2.animal_ids) == {"gray_wolf", "domestic_dog", "coyote"}  # tier 1 only, both Canis lupus rows kept
    assert to_real_hybrid(data.find_hybrids("coyote", "domestic_dog")[0], {"A": "coyote", "B": "dog"}).matched_via == "genus"


# ------------------------------------------------------------------ D1-03 measurements


def test_measurements_for_returns_every_row():
    rows = REAL.measurements_for("lion")
    raw = [m for m in json.loads((FIXTURES / "chimera_data.real_schema.json").read_text())["measurements"] if m["animal_id"] == "lion"]
    assert len(rows) == len(raw) > 1
    assert {r["measurement"] for r in rows} >= {"body_mass", "body_length"}


# ------------------------------------------------------------------ D1-04 mythology


def test_eagle_lion_resembles_griffin_by_name():
    myths = [to_myth(m) for m in REAL.find_mythology(row("bald eagle"), row("lion"))]
    assert myths[0].creature_name == "griffin"
    assert myths[0].matched == {"A": "eagle", "B": "lion"} and myths[0].match_kind == {"A": "name", "B": "name"}
    assert myths[0].culture == "Greek" and myths[0].source_url.startswith("https://")
    assert myths[0].verified is False  # "line-checked by Muse (not re-checked by Claude)"
    # sphinx also has a bird and a lion, matched through the broad word "bird"
    sphinx = next(m for m in myths if m.creature_name == "sphinx")
    assert sphinx.match_kind["A"] == "taxon" and sphinx.has_human_part


def test_horse_eagle_resembles_hippogriff_and_lion_snake_word_needs_a_snake():
    assert to_myth(REAL.find_mythology(row("horse"), row("bald eagle"))[0]).creature_name == "hippogriff"
    assert [m.row["creature_name"] for m in REAL.find_mythology(row("lion"), row("tiger"))] == []


def test_only_explicitly_verified_rows_are_verified():
    data = ChimeraData({"animals": [row("lion"), row("bald eagle")], "mythology": [
        {"creature_name": "x", "culture": "c", "component_animals": "eagle|lion", "component_parts": "", "has_human_part": "no",
         "verification": "verified against source", "source_url": "u"},
        {"creature_name": "y", "culture": "c", "component_animals": "eagle|lion", "component_parts": "", "has_human_part": "no",
         "verification": "URL loads only; parts not line-checked", "source_url": "u"},
    ]}, "full")
    verified = {to_myth(m).creature_name: to_myth(m).verified for m in data.find_mythology(row("lion"), row("bald eagle"))}
    assert verified == {"x": True, "y": False}


# ------------------------------------------------------------------ D1-02 rules


def test_rule_map_names_only_real_checks_and_fixture_covers_every_check():
    assert {c for c, _ in RULE_CHECKS.values()} <= set(rc.CHECKS)
    fixture_checks = {REAL.rule_check(r) for r in REAL.rules} - {None}
    assert fixture_checks == {c for c, _ in RULE_CHECKS.values()}
    assert len(REAL.rules) >= 12


def test_summary_counts_mapped_and_unmapped():
    s = rc.summarize(REAL)
    assert s["mapped"] == len(RULE_CHECKS) and s["unmapped"] == 6 and s["mapped"] == s["pair"] + s["plan"]


def run_pair(a, b, **kw):
    hits, ran = rc.evaluate(REAL, rc.RuleInput(a, b, **kw), "pair")
    return {h.rule_id: h for h in hits}, ran


def test_lion_octopus_pair_rules():
    hits, ran = run_pair(side("lion"), side("common octopus"))
    assert ran == rc.summarize(REAL)["pair"]
    assert {"R-A8-02", "R-A5-01", "R-A8-03", "R-A5-03"} <= set(hits)
    assert "lives only in the sea" in hits["R-A5-03"].detail
    assert "R-A2-03" not in hits  # 272 / 3 is far below 1000x


def test_mass_ratio_1000_uses_range_bounds():
    big = synthetic(name="elephant", body_mass_kg="2700-6000")
    small = synthetic(name="bee", body_mass_kg="0.0001-0.0002")
    assert "up to" in rc.mass_ratio_1000(big, small)
    # 126-272 vs 0.9-1.4: 272 / 0.9 ≈ 302x, below the threshold
    assert rc.mass_ratio_1000(side("lion"), side("scarlet macaw")) is None


def test_unrecorded_active_time_adds_nothing_and_never_blocks():
    a = synthetic(name="a", active_time="unrecorded")
    b = synthetic(name="b", active_time="diurnal")
    assert rc.active_time_conflict(a, b) is None
    note = rc.active_time_unrecorded(a, b)
    assert "adds nothing" in note
    assert RULE_CHECKS["R-A4-P04"][1] == "info"
    night = synthetic(name="owl", active_time="nocturnal|unrecorded")
    assert rc.active_time_conflict(night, b)  # remaining values still compared


def plan(body_plan, **donors):
    return FusionPlan(body_plan=body_plan, part_donors=PartDonors(**{"head": "A", "body": "A", "limbs": "A",
                                                                      "covering": "A", "tail": "A", **donors}))


def run_plan(a, b, p):
    ri = rc.RuleInput(a, b, allowed_body_plans=REAL.body_plans)
    ri.fusion = rc.fusion_profile(a, b, p)
    hits, _ = rc.evaluate(REAL, ri, "plan")
    return {h.rule_id for h in hits}


def test_fly_needs_a_flying_parent_and_swim_a_swimming_one():
    lion, fox = side("lion"), side("red fox")
    assert {"R-A4-02", "R-A1-04"} <= run_plan(lion, fox, plan("winged"))
    assert "R-A4-03" in run_plan(lion, fox, plan("finned"))
    eagle = side("bald eagle")
    assert "R-A4-02" not in run_plan(lion, eagle, plan("winged", limbs="B"))


def test_planned_body_plan_must_be_in_the_data_set():
    assert "R-A1-01" in run_plan(side("lion"), side("tiger"), plan("avian"))
    assert "R-A1-01" not in run_plan(side("lion"), side("tiger"), plan("quadruped"))


@pytest.mark.parametrize("fixture", ["chimera_data.sample.json", "chimera_data.real_schema.json"])
def test_both_fixtures_report_health(fixture):
    h = load_data(FIXTURES / fixture).health(set(rc.CHECKS))
    assert h["problems"] == [] and h["rules_mapped"] > 0 and h["hybrids_resolved"] > 0


def test_health_flags_silent_zero():
    data = ChimeraData({"hybrids": [{"hybrid_id": "x", "parent1": "Nope nope (father)", "parent2": "Nada nada (mother)"}],
                        "rules": [{"rule_id": "R-Z9-99", "rule_text": "unknown"}]}, "full")
    problems = data.health(set(rc.CHECKS))["problems"]
    assert any("0 of 1 hybrids" in p for p in problems) and any("0 of 1 rules" in p for p in problems)
